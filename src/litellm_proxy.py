"""
本仓库内 **LiteLLM 相关逻辑**（原 ``litellm_env.py`` 与本代理合并）：

1. **``configure_anthropic_for_litellm``**（当前进程）  
   设置 ``ANTHROPIC_BASE_URL`` / ``ANTHROPIC_API_KEY``，使 Claude Agent SDK 把请求发到本机 LiteLLM
  （或任意 Anthropic 兼容 URL）。读 ``BASE_URL`` / ``API_KEY`` 或 ``--base-url`` / ``--api-key``；
   并合并 ``NO_PROXY``，避免本机地址被系统代理劫持。

2. **``maybe_start_litellm``**（按需子进程）  
   当 ``BASE_URL`` 指向本机、且配置了 ``UPSTREAM_*`` 时，从 **4000** 起寻找第一个空闲端口，
   更新 ``ANTHROPIC_BASE_URL`` 为该端口，写 ``litellm_autostart_config.yaml`` 并拉起 LiteLLM（与已有实例隔离）。

3. **子进程入口**（``__main__``）  
   启动 LiteLLM 与官方 CLI 一致，并打补丁使 Anthropic ``/v1/messages`` 走 ``/v1/chat/completions``，
   避免仅支持 Chat Completions 的中转在 ``/v1/responses`` 上失败。

``.env`` 中常见变量：``BASE_URL`` / ``API_KEY``（→ Agent）；``UPSTREAM_MODEL`` / ``UPSTREAM_API_BASE`` / ``UPSTREAM_API_KEY``（→ 上游）。
``UPSTREAM_API_BASE`` 可写 ``https://host`` 或 ``https://host/v1``；写入 LiteLLM 前会去掉末尾 ``/v1``，避免与 LiteLLM 内置路径拼成 ``/v1/v1/...``。
仍兼容旧名 ``ANTHROPIC_BASE_URL`` / ``ANTHROPIC_API_KEY``。
"""
from __future__ import annotations

import atexit
from contextlib import suppress
import importlib.util
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "litellm_autostart_config.yaml"
LOG_PATH = REPO_ROOT / "litellm_autostart.log"

# 与常见 litellm --port 4000 一致（Agent → 本机 LiteLLM）
DEFAULT_LITELLM_BASE_URL = "http://127.0.0.1:4000"
DEFAULT_LITELLM_API_KEY = "sk-dummy-key"

# 自启 LiteLLM 时从该端口起寻找第一个未被占用的端口（4000→4001→…）
LITELLM_AUTOSTART_PORT_MIN = 4000
LITELLM_AUTOSTART_PORT_SCAN_MAX = 1000

# 用户已写 ``provider/model`` 且 provider 已知则原样使用；否则按模型 ID 推断：
# 含 claude → anthropic；含 gemini → gemini；其余 → openai
_LITELLM_KNOWN_PROVIDER_PREFIXES = frozenset(
    {
        "openai",
        "azure",
        "anthropic",
        "vertex_ai",
        "vertex_ai_beta",
        "gemini",
        "bedrock",
        "ollama",
        "huggingface",
        "deepseek",
        "mistral",
        "cohere",
        "openrouter",
        "databricks",
    }
)


def _env_url() -> str | None:
    v = os.environ.get("BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL")
    return v.strip() if v and str(v).strip() else None


def _env_key() -> str | None:
    v = os.environ.get("API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    return v.strip() if v and str(v).strip() else None


def _merge_no_proxy_for_url(base_url: str) -> None:
    host: str | None
    try:
        host = urlparse(base_url).hostname
    except Exception:
        host = None

    existing = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    parts = [p.strip() for p in existing.split(",") if p.strip()]
    seen = set(parts)
    hosts = ["127.0.0.1", "localhost", "0.0.0.0"]
    if host in {"127.0.0.1", "localhost", "0.0.0.0", "::1"}:
        hosts.append(host)
    for h in hosts:
        if h and h not in seen:
            seen.add(h)
            parts.append(h)
    merged = ",".join(parts)
    os.environ["NO_PROXY"] = merged
    os.environ["no_proxy"] = merged


def configure_anthropic_for_litellm(
    base_url: str | None = None,
    api_key: str | None = None,
) -> tuple[str, str]:
    """
    设置 ``ANTHROPIC_BASE_URL`` / ``ANTHROPIC_API_KEY``，供 claude-agent-sdk 转发到 LiteLLM。

    优先级：命令行参数 > ``BASE_URL`` / ``API_KEY``（或 ``ANTHROPIC_*``）> 下方默认值。

    Returns:
        实际生效的 ``(base_url, api_key)``（URL 无尾部斜杠）。
    """
    raw_url = base_url if (base_url is not None and str(base_url).strip()) else None
    raw_key = api_key if (api_key is not None and str(api_key).strip()) else None

    url = (raw_url or _env_url() or DEFAULT_LITELLM_BASE_URL).strip().rstrip("/")
    key = (raw_key or _env_key() or DEFAULT_LITELLM_API_KEY).strip()

    os.environ["ANTHROPIC_BASE_URL"] = url
    os.environ["ANTHROPIC_API_KEY"] = key

    _merge_no_proxy_for_url(url)

    return url, key


_LOCAL_HOSTS = frozenset(
    {"127.0.0.1", "localhost", "::1", "0.0.0.0", ""}
)


def _default_port_for_scheme(scheme: str) -> int:
    return 443 if (scheme or "http").lower() == "https" else 80


def host_port_from_base_url(base_url: str) -> tuple[str | None, int]:
    try:
        u = urlparse(base_url)
    except Exception:
        return None, _default_port_for_scheme("http")
    host = u.hostname
    port = u.port
    if port is None:
        port = _default_port_for_scheme(u.scheme or "http")
    return host, port


def _is_local_host(host: str | None) -> bool:
    if not host:
        return False
    h = host.lower()
    return h in _LOCAL_HOSTS or h.startswith("127.")


def port_is_listening(host: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def first_free_port(
    host: str,
    *,
    start: int = LITELLM_AUTOSTART_PORT_MIN,
    max_scan: int = LITELLM_AUTOSTART_PORT_SCAN_MAX,
) -> int | None:
    """
    从 ``start`` 起递增，返回第一个 **当前无服务监听** 的端口（本机可 bind）。
    若连续 ``max_scan`` 个端口均被占用则返回 ``None``。
    """
    end = start + max_scan
    for port in range(start, end):
        if not port_is_listening(host, port, timeout=0.12):
            return port
    return None


def normalize_upstream_api_base_for_litellm(api_base: str) -> str:
    """
    LiteLLM 会在 ``api_base`` 后拼接 ``/v1/messages``、``/v1/chat/completions`` 等。
    若 ``UPSTREAM_API_BASE`` 已以 ``/v1`` 结尾，会变成 ``.../v1/v1/...``，此处去掉末尾的 ``/v1``（可重复去至稳定）。
    """
    u = api_base.strip().rstrip("/")
    while u.lower().endswith("/v1"):
        u = u[:-3].rstrip("/")
    return u


def _infer_litellm_provider_from_model_id(model_id: str) -> str:
    """
    根据裸模型 ID 推断 LiteLLM 的 provider 前缀（小写比较）。
    Claude 系 → anthropic；Gemini → gemini；其它 → openai。
    """
    s = model_id.strip().lower()
    if "gemini" in s:
        return "gemini"
    if "claude" in s:
        return "anthropic"
    return "openai"


def normalize_upstream_model_for_litellm(model: str) -> str:
    """补全 ``provider/model``：已知前缀保留；否则按模型 ID 推断 anthropic / gemini / openai。"""
    m = model.strip()
    if not m:
        return m
    if "/" in m:
        prov, rest = m.split("/", 1)
        prov_l = prov.strip().lower()
        rest = rest.strip()
        if not rest:
            return m
        if prov_l in _LITELLM_KNOWN_PROVIDER_PREFIXES:
            return f"{prov_l}/{rest}"
        p = _infer_litellm_provider_from_model_id(rest)
        return f"{p}/{rest}"
    p = _infer_litellm_provider_from_model_id(m)
    return f"{p}/{m}"


def direct_model_from_upstream(model: str) -> str:
    """
    提取直连 Anthropic 兼容接口时应使用的裸模型名。
    例如 ``anthropic/glm-5.1`` -> ``glm-5.1``。
    """
    m = model.strip()
    if not m:
        return m
    if "/" not in m:
        return m
    _prov, rest = m.split("/", 1)
    return rest.strip() or m


def _build_yaml(model: str, api_base: str, api_key: str) -> str:
    normalized = normalize_upstream_model_for_litellm(model)
    base = normalize_upstream_api_base_for_litellm(api_base)
    return (
        "model_list:\n"
        '  - model_name: "*"\n'
        "    litellm_params:\n"
        f"      model: {json.dumps(normalized)}\n"
        f"      api_base: {json.dumps(base)}\n"
        f"      api_key: {json.dumps(api_key)}\n"
        "      drop_params: true\n"
    )


# 自启 LiteLLM 子进程（``start_new_session=True`` 与父进程脱组，不能依赖「父进程退出内核顺带杀子」）
_AUTOSTART_LITELLM_PROC: subprocess.Popen | None = None
_AUTOSTART_CLEANUP_REGISTERED = False


def _kill_autostart_litellm_child() -> None:
    global _AUTOSTART_LITELLM_PROC
    proc = _AUTOSTART_LITELLM_PROC
    _AUTOSTART_LITELLM_PROC = None
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _register_autostart_cleanup(proc: subprocess.Popen) -> None:
    global _AUTOSTART_LITELLM_PROC, _AUTOSTART_CLEANUP_REGISTERED
    _AUTOSTART_LITELLM_PROC = proc
    if _AUTOSTART_CLEANUP_REGISTERED:
        return
    _AUTOSTART_CLEANUP_REGISTERED = True
    atexit.register(_kill_autostart_litellm_child)

    def _on_sigterm(_signum: int, _frame: object) -> None:
        """systemd/docker 等发 SIGTERM 时，先杀子进程再退出（仅 atexit 时子进程可能仍短暂存活）。"""
        _kill_autostart_litellm_child()
        sys.exit(143)

    with suppress(AttributeError, ValueError, OSError):
        signal.signal(signal.SIGTERM, _on_sigterm)


def _litellm_package_available() -> bool:
    return importlib.util.find_spec("litellm") is not None


def run_litellm_proxy_main() -> int:
    """子进程入口：与 ``litellm --config ... --port ...`` 相同，带 Anthropic 上游补丁。"""
    os.environ.setdefault(
        "LITELLM_USE_CHAT_COMPLETIONS_URL_FOR_ANTHROPIC_MESSAGES",
        "true",
    )
    from litellm import run_server
    import litellm
    from litellm.llms.anthropic.experimental_pass_through.adapters.handler import (
        LiteLLMMessagesToCompletionTransformationHandler,
    )

    _orig = (
        LiteLLMMessagesToCompletionTransformationHandler._route_openai_thinking_to_responses_api_if_needed
    )

    def _wrapped(completion_kwargs, *, thinking):
        if getattr(litellm, "use_chat_completions_url_for_anthropic_messages", False):
            return
        return _orig(completion_kwargs, thinking=thinking)

    LiteLLMMessagesToCompletionTransformationHandler._route_openai_thinking_to_responses_api_if_needed = (
        staticmethod(_wrapped)
    )

    sys.argv[0] = "litellm"
    rc = run_server()
    return int(rc) if rc is not None else 0


def maybe_prefer_direct_upstream(base_url: str) -> tuple[str, str]:
    """
    若当前仍是本机默认/代理地址，且 ``UPSTREAM_*`` 提供的上游已支持 Anthropic ``/v1/messages``，
    则优先把 Claude Agent SDK 直连到远端；否则保留原本的本机地址，后续可继续回退到 LiteLLM。
    """
    host, _ignored_port = host_port_from_base_url(base_url)
    if host and not _is_local_host(host):
        return base_url, (os.environ.get("ANTHROPIC_API_KEY") or "").strip()

    model = (os.environ.get("UPSTREAM_MODEL") or "").strip()
    api_base = (os.environ.get("UPSTREAM_API_BASE") or "").strip()
    api_key = (os.environ.get("UPSTREAM_API_KEY") or "").strip()
    if not (model and api_base and api_key):
        return base_url, (os.environ.get("ANTHROPIC_API_KEY") or "").strip()

    direct_base = normalize_upstream_api_base_for_litellm(api_base)
    direct_model = direct_model_from_upstream(model)
    if not direct_base or not direct_model:
        return base_url, (os.environ.get("ANTHROPIC_API_KEY") or "").strip()

    ok, detail = probe_anthropic_messages_endpoint(
        base_url=direct_base,
        api_key=api_key,
        model=direct_model,
    )
    if not ok:
        print(
            f"[llm] 远端 Anthropic 直连探测失败，回退 LiteLLM: {detail}",
            flush=True,
        )
        return base_url, (os.environ.get("ANTHROPIC_API_KEY") or "").strip()

    direct_base = direct_base.rstrip("/")
    os.environ["ANTHROPIC_BASE_URL"] = direct_base
    os.environ["ANTHROPIC_API_KEY"] = api_key
    _merge_no_proxy_for_url(direct_base)
    print(f"[llm] 远端 Anthropic 直连可用，跳过 LiteLLM: {direct_base}", flush=True)
    return direct_base, api_key


def probe_anthropic_messages_endpoint(
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout: float = 20.0,
) -> tuple[bool, str]:
    """
    轻量探测远端是否能处理 Anthropic ``/v1/messages``。

    返回 ``(是否可直连, 说明)``。仅作为路由判定，不代表后续所有推理都必定成功。
    """
    endpoint = base_url.strip().rstrip("/") + "/v1/messages"
    body = json.dumps(
        {
            "model": model,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "ping"}],
        }
    ).encode("utf-8")
    attempts = [
        (
            "Bearer",
            {
                "content-type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "anthropic-version": "2023-06-01",
            },
        ),
        (
            "x-api-key",
            {
                "content-type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        ),
    ]
    failures: list[str] = []
    for label, headers in attempts:
        req = Request(endpoint, data=body, method="POST", headers=headers)
        try:
            with urlopen(req, timeout=timeout) as resp:
                status = getattr(resp, "status", 200)
                if 200 <= int(status) < 300:
                    return True, f"HTTP {status} ({label})"
                failures.append(f"{label}: HTTP {status}")
        except HTTPError as e:
            detail = ""
            with suppress(Exception):
                detail = e.read(512).decode("utf-8", errors="replace").strip()
            failures.append(f"{label}: HTTP {e.code}{': ' + detail if detail else ''}")
        except URLError as e:
            failures.append(f"{label}: {type(e.reason).__name__}: {e.reason}")
        except OSError as e:
            failures.append(f"{label}: {type(e).__name__}: {e}")
    return False, "; ".join(failures)


def maybe_start_litellm(base_url: str, *, disable: bool = False) -> None:
    """
    若 ``disable`` 为真，或 ``base_url`` 非本机，则直接返回。
    否则在具备 ``UPSTREAM_*`` 时：从 **4000** 起选第一个空闲端口，写 ``ANTHROPIC_BASE_URL`` 并启动子进程 LiteLLM。

    若需使用已手动启动的代理（例如固定占用 4000），请使用 ``--no-litellm-autostart``。

    Args:
        base_url: 与 ``configure_anthropic_for_litellm`` 生效后的 ``ANTHROPIC_BASE_URL``（仅用于判断是否本机）。
        disable: 对应 ``--no-litellm-autostart``。
    """
    if disable:
        return

    host, _ignored_port = host_port_from_base_url(base_url)
    if not host or not _is_local_host(host):
        print(f"[llm] BASE_URL 非本机 ({host!r})，跳过 LiteLLM 自启", flush=True)
        return

    connect_host = "127.0.0.1" if host in ("0.0.0.0", "::1", "") else host
    if connect_host == "::1":
        connect_host = "127.0.0.1"

    model = (os.environ.get("UPSTREAM_MODEL") or "").strip()
    api_base = (os.environ.get("UPSTREAM_API_BASE") or "").strip()
    api_key = (os.environ.get("UPSTREAM_API_KEY") or "").strip()

    _norm_model = normalize_upstream_model_for_litellm(model)
    if model and _norm_model != model:
        print(f"[llm] UPSTREAM_MODEL 规范化: {model!r} -> {_norm_model!r}", flush=True)
    _norm_base = normalize_upstream_api_base_for_litellm(api_base)
    if api_base and _norm_base != api_base.strip():
        print(f"[llm] UPSTREAM_API_BASE 规范化: {api_base.strip()!r} -> {_norm_base!r}", flush=True)

    if not (model and api_base and api_key):
        print(
            "[llm] 未设置 UPSTREAM_MODEL / UPSTREAM_API_BASE / UPSTREAM_API_KEY，"
            "无法自动生成 LiteLLM 配置；请手动启动代理或补全 .env",
            file=sys.stderr,
            flush=True,
        )
        return

    if not _litellm_package_available():
        print(
            "[llm] 当前 Python 环境中未安装 litellm 包。请 `pip install 'litellm[proxy]'` 后重试。",
            file=sys.stderr,
            flush=True,
        )
        return

    port = first_free_port(connect_host)
    if port is None:
        print(
            f"[llm] 自 {LITELLM_AUTOSTART_PORT_MIN} 起连续 {LITELLM_AUTOSTART_PORT_SCAN_MAX} "
            "个端口均被占用，无法自启 LiteLLM。",
            file=sys.stderr,
            flush=True,
        )
        return

    new_base = f"http://{connect_host}:{port}".rstrip("/")
    os.environ["ANTHROPIC_BASE_URL"] = new_base
    _merge_no_proxy_for_url(new_base)
    print(f"[llm] 自启 LiteLLM 选用空闲端口: {port}（已设置 ANTHROPIC_BASE_URL={new_base}）", flush=True)

    CONFIG_PATH.write_text(_build_yaml(model, api_base, api_key), encoding="utf-8")

    log_f = LOG_PATH.open("w", encoding="utf-8", buffering=1)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    log_f.write(f"\n--- autostart {ts} ---\n")
    log_f.flush()

    cmd = [
        sys.executable,
        "-m",
        "src.litellm_proxy",
        "--config",
        str(CONFIG_PATH),
        "--port",
        str(port),
    ]
    print(
        f"[llm] 正在自启 LiteLLM: port={port}  module=src.litellm_proxy  config={CONFIG_PATH}",
        flush=True,
    )

    env = os.environ.copy()
    env.setdefault(
        "LITELLM_USE_CHAT_COMPLETIONS_URL_FOR_ANTHROPIC_MESSAGES",
        "true",
    )

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            cwd=str(REPO_ROOT),
            env=env,
            start_new_session=True,
        )
    except OSError as e:
        print(f"[llm] 启动 LiteLLM 失败: {e}", file=sys.stderr, flush=True)
        return

    _register_autostart_cleanup(proc)

    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            print(
                f"[llm] LiteLLM 进程已退出（code={proc.returncode}）。"
                f"请查看 {LOG_PATH}",
                file=sys.stderr,
                flush=True,
            )
            return
        if port_is_listening(connect_host, port, timeout=0.25):
            print(f"[llm] LiteLLM 已监听 {connect_host}:{port}", flush=True)
            return
        time.sleep(0.35)

    print(
        f"[llm] 等待 {connect_host}:{port} 超时；进程仍在则稍后可连，详见 {LOG_PATH}",
        file=sys.stderr,
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(run_litellm_proxy_main())
