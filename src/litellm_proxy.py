"""LLM 接入：把 Claude Agent SDK 连到用户给的上游，必要时在进程内翻译协议。

用户只需给**一组**凭据（base URL + API key + 模型名）。之后是全自动的三步：

1. **探测** —— 拿这组凭据去打上游的 Anthropic ``/v1/messages``。
   401/403 单独归类：那是 key 的问题，不是协议的问题，会直接报错而不是退化去起桥。
2. **能直连就直连** —— SDK 直接指向上游，不启任何代理。
3. **不能就在进程内翻译** —— 上游只认 OpenAI ``/v1/chat/completions`` 时，起一个
   只监听回环、端口由系统分配的极薄 HTTP 端点，内部调 ``litellm.anthropic_messages()``
   做转换。它随 agent 进程生死，同进程所有会话共用，不落任何配置文件。

配置（``.env`` 或命令行），按优先级：

- 命令行 ``--api-base`` / ``--api-key`` / ``--model``
- ``LLM_API_BASE`` / ``LLM_API_KEY`` / ``LLM_MODEL``
- 兼容旧名 ``UPSTREAM_API_BASE`` / ``UPSTREAM_API_KEY`` / ``UPSTREAM_MODEL``

``ANTHROPIC_BASE_URL`` / ``ANTHROPIC_API_KEY`` 由本模块**输出**给 SDK，
不需要用户设置。
"""

from __future__ import annotations

import importlib.util
import json
import os
import queue
import re
import socket
import sys
import threading
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "0.0.0.0", ""})

_KNOWN_PROVIDERS = frozenset(
    {
        "openai", "azure", "anthropic", "vertex_ai", "vertex_ai_beta", "gemini",
        "bedrock", "ollama", "huggingface", "deepseek", "mistral", "cohere",
        "openrouter", "databricks",
    }
)


@dataclass(frozen=True)
class LLMEndpoint:
    """解析结果。``base_url`` / ``api_key`` 已同步写入环境供 SDK 使用。"""

    base_url: str
    api_key: str
    model: str | None
    mode: str      # "direct" | "bridge"
    detail: str

    def describe(self) -> str:
        label = "直连上游" if self.mode == "direct" else "经进程内协议桥转换"
        return f"{label}  {self.base_url}  model={self.model or '(默认)'}  [{self.detail}]"


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------

def _is_local_host(host: str | None) -> bool:
    if not host:
        return False
    h = host.lower()
    return h in _LOCAL_HOSTS or h.startswith("127.")


def host_port_from_base_url(base_url: str) -> tuple[str | None, int]:
    try:
        u = urlparse(base_url)
    except ValueError:
        return None, 80
    return u.hostname, u.port or (443 if (u.scheme or "http") == "https" else 80)


def port_is_listening(port: int, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _merge_no_proxy(base_url: str) -> None:
    """把本机地址并入 NO_PROXY，避免请求被系统代理劫持。"""
    with suppress(ValueError):
        host = urlparse(base_url).hostname
    parts = [p.strip() for p in (os.environ.get("NO_PROXY") or "").split(",") if p.strip()]
    for h in ("127.0.0.1", "localhost", "0.0.0.0", host):
        if h and h not in parts:
            parts.append(h)
    merged = ",".join(parts)
    os.environ["NO_PROXY"] = merged
    os.environ["no_proxy"] = merged


def normalize_api_base(api_base: str) -> str:
    """去掉末尾的 ``/v1``。LiteLLM 与直连都会自行拼接路径，留着会变成 ``/v1/v1/...``。"""
    u = api_base.strip().rstrip("/")
    while u.lower().endswith("/v1"):
        u = u[:-3].rstrip("/")
    return u


def _infer_provider(model_id: str) -> str:
    s = model_id.strip().lower()
    if "gemini" in s:
        return "gemini"
    if "claude" in s:
        return "anthropic"
    return "openai"


def litellm_model_id(model: str) -> str:
    """补全 ``provider/model``：已知前缀保留，否则按模型 ID 推断。"""
    m = model.strip()
    if not m:
        return m
    if "/" in m:
        prov, rest = m.split("/", 1)
        rest = rest.strip()
        if not rest:
            return m
        prov_l = prov.strip().lower()
        return f"{prov_l if prov_l in _KNOWN_PROVIDERS else _infer_provider(rest)}/{rest}"
    return f"{_infer_provider(m)}/{m}"


def bare_model_id(model: str) -> str:
    """去掉 provider 前缀：``anthropic/glm-5`` -> ``glm-5``。直连时 SDK 要裸名。"""
    m = model.strip()
    return m.split("/", 1)[1].strip() or m if "/" in m else m


#: litellm 各 provider 拼 URL 的方式不同，``api_base`` 该带什么版本段也就不同：
#: openai/openrouter 只补 ``/chat/completions``，gemini 只补 ``/models/<m>:generateContent``，
#: 都得由 base 自带版本段；anthropic 会自己补 ``/v1/messages``，base 反而不能带。
_API_BASE_SUFFIX = {"openai": "/v1", "openrouter": "/v1", "gemini": "/v1beta"}


def bridge_model_id(model: str) -> str:
    """协议桥专用的 litellm 模型 ID。

    走到桥这一步，说明上游刚刚**拒绝**了 Anthropic ``/v1/messages``。此时再按
    ``claude`` 字样推断出 ``anthropic/`` provider，litellm 就会拿 Anthropic 协议去打
    一个不认它的网关——必然失败。所以裸名在桥里一律按 OpenAI 兼容处理。

    两个例外：用户显式写了 provider 前缀就照办；``gemini`` 的接口本就不是 OpenAI
    形状（``/models/<m>:generateContent``），仍走 litellm 的 gemini provider。
    """
    m = model.strip()
    if "/" in m and m.split("/", 1)[0].strip().lower() in _KNOWN_PROVIDERS:
        return litellm_model_id(m)          # 用户点名了 provider，尊重
    resolved = litellm_model_id(m)
    prov, _, rest = resolved.partition("/")
    return resolved if prov == "gemini" else f"openai/{rest}"


def litellm_api_base(model: str, api_base: str) -> str:
    """按 provider 把 ``api_base`` 补成 litellm 期望的形态。

    ``normalize_api_base()`` 去掉的 ``/v1`` 对直连和 anthropic provider 是对的，
    但 openai provider 少了它就会打到 ``/chat/completions``（网关多半回 405）。
    """
    base = normalize_api_base(api_base)
    provider = litellm_model_id(model).split("/", 1)[0]
    suffix = _API_BASE_SUFFIX.get(provider, "")
    if suffix and not base.lower().endswith(suffix):
        base += suffix
    return base


# --------------------------------------------------------------------------
# 上游协议探测
# --------------------------------------------------------------------------

def _short_error(text: str, limit: int = 160) -> str:
    """把网关的错误响应压成一行。有些网关 404 会回整页 HTML，原样带进日志没法看。"""
    s = re.sub(r"<[^>]+>", " ", text)           # 剥标签，HTML 错误页只剩正文
    s = " ".join(s.split())
    return s if len(s) <= limit else s[:limit] + "…"


@dataclass(frozen=True)
class ProbeResult:
    """Anthropic ``/v1/messages`` 探测结果。

    ``ok`` 与 ``auth_failed`` 必须分开看：401/403 说明**这把 key 没被接受**，
    跟上游支不支持 Anthropic 协议无关。早期版本把两者混为一谈，key 一过期就
    误判成「上游不支持 Anthropic」转去起桥，而桥用的是同一把 key，只会以更绕的
    方式再失败一次。
    """

    ok: bool
    auth_failed: bool
    detail: str


def probe_anthropic_messages(
    *, base_url: str, api_key: str, model: str, timeout: float = 20.0
) -> ProbeResult:
    """探测上游能否直接处理 Anthropic ``/v1/messages``。

    两种鉴权头都试（``Authorization: Bearer`` 与 ``x-api-key``），中转网关用哪种的都有。
    只有在**每次尝试都是 401/403** 时才判定为凭据问题——只要有一次是别的错
    （404/405 等），那就是路由层面不认这个端点，属于协议不支持。
    """
    endpoint = normalize_api_base(base_url) + "/v1/messages"
    body = json.dumps(
        {"model": model, "max_tokens": 1, "messages": [{"role": "user", "content": "ping"}]}
    ).encode("utf-8")
    base_headers = {"content-type": "application/json", "anthropic-version": "2023-06-01"}
    attempts = [
        ("Bearer", {**base_headers, "Authorization": f"Bearer {api_key}"}),
        ("x-api-key", {**base_headers, "x-api-key": api_key}),
    ]
    failures: list[str] = []
    codes: list[int | None] = []
    for label, headers in attempts:
        req = Request(endpoint, data=body, method="POST", headers=headers)
        try:
            with urlopen(req, timeout=timeout) as resp:
                status = int(getattr(resp, "status", 200))
                if 200 <= status < 300:
                    return ProbeResult(True, False, f"HTTP {status} ({label})")
                codes.append(status)
                failures.append(f"{label}: HTTP {status}")
        except HTTPError as e:
            detail = ""
            with suppress(Exception):
                detail = _short_error(e.read(2048).decode("utf-8", errors="replace"))
            codes.append(e.code)
            failures.append(f"{label}: HTTP {e.code}{': ' + detail if detail else ''}")
        except (URLError, OSError) as e:
            codes.append(None)
            failures.append(f"{label}: {type(e).__name__}: {e}")
    auth_failed = bool(codes) and all(c in (401, 403) for c in codes)
    return ProbeResult(False, auth_failed, "; ".join(failures))


def probe_openai_chat(
    *, base_url: str, api_key: str, model: str, timeout: float = 20.0
) -> tuple[bool, str]:
    """探测上游的 OpenAI ``/v1/chat/completions``，用来判断 key 本身是不是好的。

    只在 Anthropic 探测因 401/403 失败时才需要——两边都不认这把 key，就是 key 的问题；
    这边认那边不认，说明只是 ``/v1/messages`` 的鉴权方式不同，仍可以走桥。
    """
    endpoint = normalize_api_base(base_url) + "/v1/chat/completions"
    body = json.dumps(
        {"model": model, "max_tokens": 1, "messages": [{"role": "user", "content": "ping"}]}
    ).encode("utf-8")
    req = Request(
        endpoint,
        data=body,
        method="POST",
        headers={"content-type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200))
            return 200 <= status < 300, f"HTTP {status}"
    except HTTPError as e:
        # 404/405 = 没这个端点，但至少不是凭据被拒
        return False, f"HTTP {e.code}"
    except (URLError, OSError) as e:
        return False, f"{type(e).__name__}: {e}"


# --------------------------------------------------------------------------
# 进程内协议桥：Anthropic /v1/messages -> 上游 OpenAI /v1/chat/completions
# --------------------------------------------------------------------------
#
# 上游只认 OpenAI 协议时，需要有人把 SDK 发出的 Anthropic 请求翻译过去。
# 这件事交给 ``litellm.anthropic_messages()`` —— 它是 LiteLLM 的**库接口**，
# 不需要跑 LiteLLM 的代理服务器。我们只补一个极薄的 HTTP 端点，因为 SDK 只会
# 通过 ``ANTHROPIC_BASE_URL`` 用 HTTP 说话。
#
# 相比拉子进程跑 `litellm --config`，这样省掉了：配置文件落盘（含明文 key）、
# 端口扫描与占位、跨进程实例登记、脱组子进程的生命周期清理、以及对 LiteLLM
# 私有方法的 monkeypatch。桥随 agent 进程生死，不会留下孤儿。

#: 透传给 litellm 的 Anthropic Messages 参数。白名单而非全量转发，
#: 避免上游因未知字段报错。
_PASSTHROUGH_KEYS = (
    "messages", "system", "max_tokens", "stop_sequences", "stream",
    "temperature", "top_k", "top_p", "tools", "tool_choice", "metadata", "thinking",
)

_bridge_url: str | None = None
_bridge_lock = threading.Lock()


def _make_bridge_app(model: str, api_base: str, api_key: str):
    from aiohttp import web
    import litellm

    # 让 litellm 把 Anthropic 请求发到 /v1/chat/completions，而不是多数中转
    # 不支持的 /v1/responses。
    litellm.use_chat_completions_url_for_anthropic_messages = True
    # SDK 会发 Anthropic 的 thinking，litellm 映射成 OpenAI 的 reasoning_effort；
    # 通用 openai provider 对任意模型都不认这个参数，会抛 UnsupportedParamsError。
    # 桥面对的是各式各样的兼容网关，能力参差不齐，丢掉不认的参数比整个请求失败好。
    litellm.drop_params = True
    target_model = bridge_model_id(model)
    target_api_base = litellm_api_base(target_model, api_base)

    async def handle(request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"type": "error", "error": {"type": "invalid_request_error",
                                                                 "message": "malformed JSON body"}},
                                     status=400)
        kwargs = {k: body[k] for k in _PASSTHROUGH_KEYS if k in body}
        kwargs.setdefault("max_tokens", 4096)
        kwargs["model"] = target_model      # 忽略请求里的模型名，用配置里的
        kwargs["api_base"] = target_api_base
        kwargs["api_key"] = api_key
        streaming = bool(kwargs.get("stream"))

        try:
            result = await litellm.anthropic_messages(**kwargs)
        except Exception as exc:
            return web.json_response(
                {"type": "error", "error": {"type": "api_error", "message": f"{type(exc).__name__}: {exc}"}},
                status=502,
            )

        if not streaming:
            payload = result if isinstance(result, dict) else result.model_dump()
            return web.json_response(payload)

        resp = web.StreamResponse(
            status=200,
            headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"},
        )
        await resp.prepare(request)
        try:
            async for chunk in result:
                await resp.write(chunk if isinstance(chunk, (bytes, bytearray)) else str(chunk).encode())
        except Exception as exc:
            # 流已经开始，只能以 SSE 错误事件收尾
            err = json.dumps({"type": "error",
                              "error": {"type": "api_error", "message": str(exc)}})
            with suppress(Exception):
                await resp.write(f"event: error\ndata: {err}\n\n".encode())
        await resp.write_eof()
        return resp

    app = web.Application()
    app.router.add_post("/v1/messages", handle)
    return app


def start_protocol_bridge(model: str, api_base: str, api_key: str) -> str | None:
    """在后台线程起一个只监听回环、端口由系统分配的协议桥，返回其 base URL。

    单例：同一进程内所有会话共用它。桥是无状态的，并发请求没有问题。
    """
    global _bridge_url
    with _bridge_lock:
        if _bridge_url:
            return _bridge_url
        if importlib.util.find_spec("litellm") is None:
            print("[llm] 未安装 litellm，无法进行协议转换。请 `pip install litellm`",
                  file=sys.stderr, flush=True)
            return None

        ready: queue.Queue = queue.Queue(maxsize=1)

        def _serve() -> None:
            import asyncio

            from aiohttp import web

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                app = _make_bridge_app(model, api_base, api_key)
                runner = web.AppRunner(app)
                loop.run_until_complete(runner.setup())
                site = web.TCPSite(runner, "127.0.0.1", 0)  # 端口交给系统分配
                loop.run_until_complete(site.start())
                port = site._server.sockets[0].getsockname()[1]
                ready.put(port)
                loop.run_forever()
            except Exception as exc:
                ready.put(exc)

        threading.Thread(target=_serve, name="llm-protocol-bridge", daemon=True).start()
        try:
            got = ready.get(timeout=30)
        except queue.Empty:
            print("[llm] 协议桥启动超时", file=sys.stderr, flush=True)
            return None
        if isinstance(got, Exception):
            print(f"[llm] 协议桥启动失败: {got}", file=sys.stderr, flush=True)
            return None
        _bridge_url = f"http://127.0.0.1:{got}"
        return _bridge_url


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------

def _first(*values: str | None) -> str:
    for v in values:
        if v and str(v).strip():
            return str(v).strip()
    return ""


def _publish(base_url: str, api_key: str, model: str) -> None:
    """把解析结果写进环境，供 Claude Agent SDK 与 build_options 读取。

    集中在这里设置，避免各处再去猜 UPSTREAM_* 该怎么转成 SDK 要的形式。
    """
    os.environ["ANTHROPIC_BASE_URL"] = base_url
    os.environ["ANTHROPIC_API_KEY"] = api_key
    if model:
        os.environ.setdefault("CLAUDE_CODE_MODEL", model)
    _merge_no_proxy(base_url)


def resolve_llm_endpoint(
    *,
    api_base: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    force_litellm: bool = False,
) -> LLMEndpoint:
    """解析出 SDK 该连的地址，必要时自动拉起/复用 LiteLLM。

    副作用：设置 ``ANTHROPIC_BASE_URL`` / ``ANTHROPIC_API_KEY`` 与 ``NO_PROXY``。
    """
    base = _first(api_base, os.environ.get("LLM_API_BASE"), os.environ.get("UPSTREAM_API_BASE"))
    key = _first(api_key, os.environ.get("LLM_API_KEY"), os.environ.get("UPSTREAM_API_KEY"))
    mdl = _first(model, os.environ.get("LLM_MODEL"), os.environ.get("UPSTREAM_MODEL"))

    if not (base and key):
        raise SystemExit(
            "[llm] 缺少上游配置。请在 .env 中设置 LLM_API_BASE / LLM_API_KEY "
            "（可选 LLM_MODEL），或用 --api-base / --api-key 传入。"
        )

    base = normalize_api_base(base)
    direct_model = bare_model_id(mdl) if mdl else ""

    # 1) 上游若原生支持 Anthropic 协议，直连最省事，也少一层故障点
    if not force_litellm and direct_model:
        res = probe_anthropic_messages(base_url=base, api_key=key, model=direct_model)
        if res.ok:
            _publish(base, key, direct_model)
            return LLMEndpoint(base, key, direct_model, "direct", res.detail)

        if res.auth_failed:
            # 401/403 不代表上游不支持 Anthropic。先确认这把 key 在 OpenAI 那条路上
            # 是否也被拒——都被拒就是凭据问题，起桥只会把同一个错误包装得更难懂。
            key_ok, chat_detail = probe_openai_chat(base_url=base, api_key=key, model=direct_model)
            if not key_ok:
                raise SystemExit(
                    f"[llm] 上游拒绝了这组凭据（不是协议问题）。\n"
                    f"      /v1/messages:        {res.detail}\n"
                    f"      /v1/chat/completions: {chat_detail}\n"
                    f"      两条路都不认这把 key，协议桥用的也是它，先检查 LLM_API_KEY "
                    f"是否过期、额度是否用尽、LLM_API_BASE 是否写对。"
                )
            print(
                "[llm] /v1/messages 拒绝了这把 key，但 /v1/chat/completions 认它，"
                "改用进程内协议桥转换",
                flush=True,
            )
        else:
            print(
                f"[llm] 上游不支持 Anthropic /v1/messages，改用进程内协议桥转换: {res.detail}",
                flush=True,
            )

    # 2) 否则在进程内起协议桥翻译
    if not mdl:
        raise SystemExit("[llm] 需要协议转换时必须指定模型（LLM_MODEL 或 --model）。")
    local = start_protocol_bridge(mdl, base, key)
    if local is None:
        raise SystemExit("[llm] 无法建立到上游的连接：既不支持直连，协议桥也未能启动。")

    resolved_model = direct_model or bare_model_id(mdl)
    _publish(local, key, resolved_model)
    return LLMEndpoint(local, key, resolved_model, "bridge", local)
