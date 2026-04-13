"""
通过环境变量将 Claude Agent SDK 的请求指向 LiteLLM（或其它 Anthropic 兼容代理）。

本地启动 LiteLLM 的写法可参考（非本仓库维护逻辑，仅作参考）：
  ``learn-claude-code/claude_agent/run_litellm.py``

``main.py`` 仅通过 ``configure_anthropic_for_litellm`` 设置 ``ANTHROPIC_BASE_URL`` / ``ANTHROPIC_API_KEY``，把 Claude Agent SDK 的请求交给 **本机 LiteLLM**；**不在此指定上游模型**，真实模型由 LiteLLM 配置（如 ``model_list``）决定。

``.env`` 中 **本程序会读取**：

- **Agent → LiteLLM**：``BASE_URL``、``API_KEY``（可被命令行 ``--base-url`` / ``--api-key`` 覆盖）

可选 **仅作文档、与 litellm yaml 对齐**（本模块不读取）：``UPSTREAM_MODEL``、``UPSTREAM_API_BASE``、``UPSTREAM_API_KEY``

仍兼容旧名 ``ANTHROPIC_BASE_URL`` / ``ANTHROPIC_API_KEY``。
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

# 与常见 litellm --port 4000 一致
DEFAULT_LITELLM_BASE_URL = "http://127.0.0.1:4000"
DEFAULT_LITELLM_API_KEY = "sk-dummy-key"


def _env_url() -> str | None:
    v = os.environ.get("BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL")
    return v.strip() if v and str(v).strip() else None


def _env_key() -> str | None:
    v = os.environ.get("API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    return v.strip() if v and str(v).strip() else None


def configure_anthropic_for_litellm(
    base_url: str | None = None,
    api_key: str | None = None,
) -> tuple[str, str]:
    """
    设置 ``ANTHROPIC_BASE_URL`` / ``ANTHROPIC_API_KEY``，供 claude-agent-sdk 转发到 LiteLLM。

    优先级（由高到低）：

    - **命令行参数** ``base_url`` / ``api_key``（非空）
    - 环境变量 ``BASE_URL`` / ``API_KEY``（推荐写在 ``.env``）
    - 兼容 ``ANTHROPIC_BASE_URL`` / ``ANTHROPIC_API_KEY``
    - 模块默认值

    同时合并 ``NO_PROXY``，避免本地代理被系统 HTTP 代理拦截。

    Returns:
        实际生效的 ``(base_url, api_key)``（已规范化 URL，无尾部斜杠）。
    """
    raw_url = base_url if (base_url is not None and str(base_url).strip()) else None
    raw_key = api_key if (api_key is not None and str(api_key).strip()) else None

    url = (raw_url or _env_url() or DEFAULT_LITELLM_BASE_URL).strip().rstrip("/")
    key = (raw_key or _env_key() or DEFAULT_LITELLM_API_KEY).strip()

    os.environ["ANTHROPIC_BASE_URL"] = url
    os.environ["ANTHROPIC_API_KEY"] = key

    _merge_no_proxy_for_url(url)

    return url, key


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
