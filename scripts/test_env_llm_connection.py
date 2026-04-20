#!/usr/bin/env python3
"""根据仓库根目录 ``.env`` 测试 LLM 连接与协议说明。

1. **Agent 侧**（``BASE_URL`` + ``API_KEY``）：探测 ``/health``、``/v1/models``；若配置了 ``API_KEY`` 则再 **POST /v1/messages**（Anthropic 协议，经 LiteLLM）。
2. **上游**（``UPSTREAM_*``）：``GET /v1/models``；**POST /v1/messages**（Anthropic）；**POST /v1/chat/completions**（OpenAI）。

Anthropic 请求体符合 Messages API；鉴权依次尝试 ``Authorization: Bearer`` 与 ``x-api-key``（与网关实现有关）。

用法::

  python scripts/test_env_llm_connection.py
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.litellm_proxy import (  # noqa: E402
    normalize_upstream_api_base_for_litellm,
    normalize_upstream_model_for_litellm,
)

ANTHROPIC_VERSION = "2023-06-01"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass


def _merge_env_from_dotenv_file() -> None:
    path = REPO_ROOT / ".env"
    if not path.is_file():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if "=" not in s:
                continue
            k, _, v = s.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except OSError:
        pass


def _redact(s: str | None, keep: int = 4) -> str:
    if not s:
        return "(empty)"
    if len(s) <= keep * 2:
        return "***"
    return f"{s[:keep]}...{s[-keep:]}"


def _req(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 25.0,
) -> tuple[int | None, str]:
    h = dict(headers or {})
    r = Request(url, method=method, headers=h, data=body)
    try:
        with urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.getcode() or 200, raw[:4000]
    except HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        return e.code, err[:4000]
    except URLError as e:
        return None, str(e)
    except (TimeoutError, socket.timeout) as e:
        return None, f"timeout after {timeout}s: {e}"


def _strip_litellm_model_for_openai_body(model: str) -> str:
    s = model.strip()
    for p in ("openai/", "anthropic/", "gemini/"):
        if s.startswith(p):
            return s[len(p) :]
    return s


def _anthropic_messages_body(bare_model: str) -> bytes:
    payload: dict[str, Any] = {
        "model": bare_model,
        "max_tokens": 32,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
    }
    return json.dumps(payload).encode("utf-8")


def try_post_anthropic_messages(
    url: str,
    api_key: str,
    bare_model: str,
    timeout: float = 120.0,
) -> tuple[int | None, str, str]:
    """
    依次用 Bearer 与 x-api-key 尝试 Anthropic Messages API。
    返回 (http_code, body_snippet, auth_mode_used)。
    """
    body = _anthropic_messages_body(bare_model)
    attempts: list[tuple[str, dict[str, str]]] = [
        (
            "Authorization: Bearer + anthropic-version",
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "anthropic-version": ANTHROPIC_VERSION,
            },
        ),
        (
            "x-api-key + anthropic-version",
            {
                "x-api-key": api_key,
                "Content-Type": "application/json",
                "anthropic-version": ANTHROPIC_VERSION,
            },
        ),
    ]
    last_code: int | None = None
    last_body = ""
    last_mode = ""
    for label, headers in attempts:
        code, text = _req(url, method="POST", headers=headers, body=body, timeout=timeout)
        last_code, last_body, last_mode = code, text, label
        if code == 200:
            return code, text, label
    return last_code, last_body, last_mode


def main() -> int:
    _load_dotenv()
    _merge_env_from_dotenv_file()

    base_url = (
        os.environ.get("BASE_URL")
        or os.environ.get("ANTHROPIC_BASE_URL")
        or "http://127.0.0.1:4000"
    ).strip().rstrip("/")
    api_key = (os.environ.get("API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or "").strip()

    up_model = (os.environ.get("UPSTREAM_MODEL") or "").strip()
    up_base = (os.environ.get("UPSTREAM_API_BASE") or "").strip().rstrip("/")
    up_key = (os.environ.get("UPSTREAM_API_KEY") or "").strip()

    tm_env = (os.environ.get("ANTHROPIC_TEST_MODEL") or "").strip()
    if tm_env:
        test_model = tm_env
    elif up_model:
        test_model = _strip_litellm_model_for_openai_body(
            normalize_upstream_model_for_litellm(up_model)
        )
    else:
        test_model = "claude-sonnet-4-6"

    print("=== .env 中的模型与端点（密钥已脱敏）===\n")
    print(f"BASE_URL (Agent → 通常为 LiteLLM): {base_url}")
    print(f"API_KEY: {_redact(api_key)}")
    print(f"试连用模型名 (Anthropic body): {test_model!r}  （可用 ANTHROPIC_TEST_MODEL 覆盖）")
    print()
    print("协议说明：Claude Agent SDK 使用 **Anthropic Messages**（POST /v1/messages），")
    print("         一般把 BASE_URL 指到 LiteLLM，由 LiteLLM 再转上游。\n")

    auth = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    print("--- [1] Agent 侧：BASE_URL 可达性 ---")
    for path, label in (
        ("/health", "LiteLLM 健康检查（若有）"),
        ("/v1/models", "代理模型列表"),
    ):
        url = f"{base_url}{path}"
        code, body = _req(url, headers=auth)
        if code is None:
            print(f"  {label}: FAIL {body[:200]}")
        else:
            snippet = body[:120].replace("\n", " ") + ("..." if len(body) > 120 else "")
            print(f"  {label}: HTTP {code}  {snippet}")

    if api_key:
        ag_url = f"{base_url}/v1/messages"
        print(f"\n  POST {ag_url}  （Anthropic 协议 → LiteLLM）")
        c_ag, b_ag, mode_ag = try_post_anthropic_messages(ag_url, api_key, test_model, timeout=120.0)
        print(f"       → HTTP {c_ag}  鉴权尝试: {mode_ag}")
        if c_ag == 200:
            print("       Agent 侧 Anthropic 试连: 成功。")
        else:
            print(f"       响应片段: {b_ag[:400]}")
    else:
        print("\n  （未设置 API_KEY，跳过 POST /v1/messages 到 BASE_URL）")

    print("\n--- [2] 上游 UPSTREAM_*（与 LiteLLM 配置一致）---")
    if not (up_model and up_base and up_key):
        print("  未完整设置 UPSTREAM_MODEL / UPSTREAM_API_BASE / UPSTREAM_API_KEY，跳过上游试连。")
        return 0

    norm_model = normalize_upstream_model_for_litellm(up_model)
    norm_base = normalize_upstream_api_base_for_litellm(up_base)
    prov = norm_model.split("/", 1)[0] if "/" in norm_model else "?"

    print(f"  UPSTREAM_MODEL (raw):     {up_model!r}")
    print(f"  规范化后 litellm model:   {norm_model!r}")
    print(f"  推断 LiteLLM provider:    {prov!r}")
    print(f"  UPSTREAM_API_BASE (raw):  {up_base!r}")
    print(f"  规范化后 api_base:        {norm_base!r}")
    print(f"  UPSTREAM_API_KEY:         {_redact(up_key)}")
    bare = _strip_litellm_model_for_openai_body(norm_model)

    h_up = {"Authorization": f"Bearer {up_key}", "Content-Type": "application/json"}

    models_url = f"{norm_base}/v1/models"
    code, body = _req(models_url, headers=h_up)
    print(f"\n  GET  {models_url}")
    print(f"       → HTTP {code}")

    msg_url = f"{norm_base}/v1/messages"
    print(f"\n  POST {msg_url}  （Anthropic Messages，直连上游）")
    print(f"       model={bare!r}")
    c_msg, b_msg, mode_msg = try_post_anthropic_messages(msg_url, up_key, bare, timeout=120.0)
    print(f"       → HTTP {c_msg}  鉴权: {mode_msg}")
    if c_msg == 200:
        print("       上游 Anthropic 协议试连: 成功。")
    else:
        print(f"       响应片段: {b_msg[:500]}")

    chat_url = f"{norm_base}/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": bare,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 8,
        "temperature": 0,
    }
    body_b = json.dumps(payload).encode("utf-8")
    c_chat, b_chat = _req(chat_url, method="POST", headers=h_up, body=body_b, timeout=120.0)
    print(f"\n  POST {chat_url}  （OpenAI Chat Completions）")
    print(f"       model={bare!r}")
    print(f"       → HTTP {c_chat}")
    if c_chat == 200:
        print("       上游 OpenAI 兼容试连: 成功。")
    else:
        print(f"       响应片段: {b_chat[:500]}")

    ok_msg = c_msg == 200
    ok_chat = c_chat == 200
    if ok_msg or ok_chat:
        print("\n结论: 上游至少一种协议可用（Anthropic Messages 和/或 OpenAI Chat）。")
        return 0
    print("\n结论: 上游 Anthropic 与 OpenAI 试连均未返回 200，请检查模型名、密钥与网关文档。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
