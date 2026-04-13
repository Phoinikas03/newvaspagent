"""
在 ``BASE_URL`` 指向本机且端口未监听时，尝试用 ``subprocess`` 启动 LiteLLM。

依赖环境变量（与 ``.env`` 中一致）：

- ``UPSTREAM_MODEL``、``UPSTREAM_API_BASE``、``UPSTREAM_API_KEY``：写入临时 yaml 的 ``litellm_params``。

若未设置上游三项，则**不**自启，并打印提示（需手动启动 LiteLLM 或其它代理）。
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "litellm_autostart_config.yaml"
LOG_PATH = REPO_ROOT / "litellm_autostart.log"

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


def maybe_start_litellm(base_url: str, *, disable: bool = False) -> None:
    """
    若 ``disable`` 为真，或 ``base_url`` 非本机，或端口已可连，则直接返回。
    否则在具备 ``UPSTREAM_*`` 时写入 ``litellm_autostart_config.yaml`` 并启动 ``litellm``。
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

    if shutil.which("litellm") is None:
        print(
            "[llm] 未找到 `litellm` 命令（PATH 中无）。请 `pip install litellm` 后重试，或手动启动代理。",
            file=sys.stderr,
            flush=True)
        return

    CONFIG_PATH.write_text(_build_yaml(model, api_base, api_key), encoding="utf-8")

    log_f = LOG_PATH.open("a", encoding="utf-8", buffering=1)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    log_f.write(f"\n--- autostart {ts} ---\n")
    log_f.flush()

    cmd = [
        "litellm",
        "--config",
        str(CONFIG_PATH),
        "--port",
        str(port),
    ]
    print(f"[llm] 正在自启 LiteLLM: port={port}  config={CONFIG_PATH}", flush=True)

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            cwd=str(REPO_ROOT),
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
