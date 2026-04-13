"""
本仓库内 **LiteLLM 相关逻辑**（原 ``litellm_env.py`` 与本代理合并）：

1. **``configure_anthropic_for_litellm``**（当前进程）  
   设置 ``ANTHROPIC_BASE_URL`` / ``ANTHROPIC_API_KEY``，使 Claude Agent SDK 把请求发到本机 LiteLLM
  （或任意 Anthropic 兼容 URL）。读 ``BASE_URL`` / ``API_KEY`` 或 ``--base-url`` / ``--api-key``；
   并合并 ``NO_PROXY``，避免本机地址被系统代理劫持。

2. **``maybe_start_litellm``**（按需子进程）  
   当 ``BASE_URL`` 指向本机且端口未监听、且配置了 ``UPSTREAM_*`` 时，写 ``litellm_autostart_config.yaml``，
   并 ``python -m src.litellm_proxy`` 拉起 LiteLLM，把 **Anthropic 协议** 转为 **上游**（OpenAI 兼容等）。

3. **子进程入口**（``__main__``）  
   启动 LiteLLM 与官方 CLI 一致，并打补丁使 Anthropic ``/v1/messages`` 走 ``/v1/chat/completions``，
   避免仅支持 Chat Completions 的中转在 ``/v1/responses`` 上失败。

``.env`` 中常见变量：``BASE_URL`` / ``API_KEY``（→ Agent）；``UPSTREAM_MODEL`` / ``UPSTREAM_API_BASE`` / ``UPSTREAM_API_KEY``（→ 上游）。
仍兼容旧名 ``ANTHROPIC_BASE_URL`` / ``ANTHROPIC_API_KEY``。
"""
from __future__ import annotations

import atexit
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "litellm_autostart_config.yaml"
LOG_PATH = REPO_ROOT / "litellm_autostart.log"

# 与常见 litellm --port 4000 一致（Agent → 本机 LiteLLM）
DEFAULT_LITELLM_BASE_URL = "http://127.0.0.1:4000"
DEFAULT_LITELLM_API_KEY = "sk-dummy-key"


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
    for h in ("127.0.0.1", "localhost", "0.0.0.0", host):
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


def _build_yaml(model: str, api_base: str, api_key: str) -> str:
    return (
        "model_list:\n"
        '  - model_name: "*"\n'
        "    litellm_params:\n"
        f"      model: {json.dumps(model)}\n"
        f"      api_base: {json.dumps(api_base)}\n"
        f"      api_key: {json.dumps(api_key)}\n"
        "      drop_params: true\n"
    )


def _register_cleanup(proc: subprocess.Popen) -> None:
    def _cleanup() -> None:
        if proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    atexit.register(_cleanup)


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


def maybe_start_litellm(base_url: str, *, disable: bool = False) -> None:
    """
    若 ``disable`` 为真，或 ``base_url`` 非本机，或端口已可连，则直接返回。
    否则在具备 ``UPSTREAM_*`` 时写入配置并启动本模块子进程（LiteLLM）。

    Args:
        base_url: 与 ``configure_anthropic_for_litellm`` 生效后的 ``ANTHROPIC_BASE_URL`` 一致。
        disable: 对应 ``--no-litellm-autostart``。
    """
    if disable:
        return

    host, port = host_port_from_base_url(base_url)
    if not host or not _is_local_host(host):
        print(f"[llm] BASE_URL 非本机 ({host!r})，跳过 LiteLLM 自启", flush=True)
        return

    connect_host = "127.0.0.1" if host in ("0.0.0.0", "::1", "") else host
    if connect_host == "::1":
        connect_host = "127.0.0.1"

    if port_is_listening(connect_host, port):
        print(f"[llm] 端口 {port} 已可连接，跳过 LiteLLM 自启", flush=True)
        return

    model = (os.environ.get("UPSTREAM_MODEL") or "").strip()
    api_base = (os.environ.get("UPSTREAM_API_BASE") or "").strip()
    api_key = (os.environ.get("UPSTREAM_API_KEY") or "").strip()

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

    _register_cleanup(proc)

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
