#!/usr/bin/env python3
"""直连 LinkAPI（OpenAI 兼容 `/v1/chat/completions`）测试模型是否可用。

默认从仓库根目录 `.env` 读取 ``UPSTREAM_API_BASE``、``UPSTREAM_API_KEY``、``UPSTREAM_MODEL``。
``UPSTREAM_MODEL`` 若为 ``openai/xxx``，会去掉 ``openai/`` 再作为请求体里的 ``model``。

用法:
  python scripts/test_linkapi_chat.py
  python scripts/test_linkapi_chat.py --model claude-sonnet-4-5-20250929
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass


def _merge_env_from_dotenv_file() -> None:
    """无 python-dotenv 时，从仓库 .env 解析 KEY=VALUE 写入 os.environ（不覆盖已有环境变量）。"""
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


def _chat_completions_url(api_base: str) -> str:
    """与 ``litellm_proxy.normalize_upstream_api_base_for_litellm`` 一致：去掉末尾 ``/v1`` 后固定拼 ``/v1/chat/completions``。"""
    u = api_base.strip().rstrip("/")
    while u.lower().endswith("/v1"):
        u = u[:-3].rstrip("/")
    return f"{u}/v1/chat/completions"


def _strip_litellm_provider_prefix(model: str) -> str:
    """LinkAPI 为 OpenAI 兼容：请求体里只传上游裸模型 ID，去掉 litellm 风格前缀。"""
    s = model.strip()
    for prefix in (
        "openai/",
        "openai:",
        "anthropic/",
        "anthropic:",
        "gemini/",
        "gemini:",
    ):
        if s.startswith(prefix):
            return s[len(prefix) :]
    return s


def main() -> int:
    _load_dotenv()
    _merge_env_from_dotenv_file()
    p = argparse.ArgumentParser(description="Test LinkAPI chat completions")
    p.add_argument(
        "--base-url",
        default=(os.environ.get("UPSTREAM_API_BASE") or "").strip(),
        metavar="URL",
        help="例如 https://api.linkapi.ai 或 https://api.linkapi.ai/v1（默认 UPSTREAM_API_BASE）",
    )
    p.add_argument(
        "--api-key",
        default=(os.environ.get("UPSTREAM_API_KEY") or "").strip(),
        metavar="KEY",
        help="默认 UPSTREAM_API_KEY",
    )
    p.add_argument(
        "--model",
        default=(os.environ.get("UPSTREAM_MODEL") or "claude-sonnet-4-5-20250929").strip(),
        metavar="NAME",
        help="默认 UPSTREAM_MODEL（可带 openai/、anthropic/ 等前缀，脚本会去掉后再请求）",
    )
    p.add_argument("--timeout", type=float, default=120.0, help="秒，默认 120")
    args = p.parse_args()

    base = args.base_url
    key = args.api_key
    model = _strip_litellm_provider_prefix(args.model)

    if not base:
        print("错误: 未设置 --base-url 或环境变量 UPSTREAM_API_BASE", file=sys.stderr)
        return 2
    if not key:
        print("错误: 未设置 --api-key 或环境变量 UPSTREAM_API_KEY", file=sys.stderr)
        return 2

    url = _chat_completions_url(base)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "只回复两个字母：OK"}],
        "max_tokens": 64,
        "temperature": 0,
    }
    raw_body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=raw_body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
    )

    print(f"POST {url}", flush=True)
    print(f"model={model}", flush=True)

    try:
        with urlopen(req, timeout=args.timeout) as resp:
            text = resp.read().decode("utf-8")
    except HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}", file=sys.stderr)
        print(err, file=sys.stderr)
        return 1
    except URLError as e:
        print(f"请求失败: {e}", file=sys.stderr)
        return 1

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print(text[:4000], flush=True)
        return 1

    choices = data.get("choices") or []
    if not choices:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 1

    msg = (choices[0].get("message") or {}) if isinstance(choices[0], dict) else {}
    content = msg.get("content", "")
    print("--- assistant 正文 ---", flush=True)
    print(content if content else json.dumps(data, ensure_ascii=False, indent=2)[:3000], flush=True)
    print("---", flush=True)
    print("成功: 已收到 choices[0].message", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
