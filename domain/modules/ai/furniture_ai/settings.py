"""模型连接配置读写、脱敏和连接参数准入；不访问家具项目。"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Mapping
from urllib import parse as urllib_parse
from . import codex
from .agy import _sync_agy_model_and_effort
from .contracts import AIConnectionError, VALID_PROVIDERS, VALID_REASONING_EFFORTS
from .discovery import _discover_codex_binary, _discover_agy_binary
from .cli_protocol import _is_localhost_url


LLM_CONFIG_FILENAME = "_llm_config.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _llm_config_path(store_root: str | Path) -> Path:
    return Path(store_root) / LLM_CONFIG_FILENAME


def _mask_api_key(api_key: str) -> str:
    cleaned = api_key.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= 8:
        return "*" * len(cleaned)
    return f"{cleaned[:4]}...{cleaned[-4:]}"


def load_llm_config(store_root: str | Path) -> dict[str, str]:
    """读取本机大模型配置；若未落盘则优先自动选用本机已安装的 OAuth CLI。"""
    path = _llm_config_path(store_root)
    saved: dict[str, Any] = {}
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                saved = raw
        except (OSError, json.JSONDecodeError):
            saved = {}

    codex_bin = _discover_codex_binary()
    agy_bin = _discover_agy_binary()

    default_provider = "openai_compatible"
    default_model = ""
    if not saved and not os.environ.get("FURNITURE_LLM_PROVIDER"):
        if codex_bin:
            default_provider = "codex_cli"
            default_model = "gpt-6.1-sol"
        elif agy_bin:
            default_provider = "agy_cli"
            default_model = "gemini-3.8-flash-high"

    provider = str(
        saved.get("provider")
        or os.environ.get("FURNITURE_LLM_PROVIDER")
        or default_provider
    ).strip()
    if provider not in VALID_PROVIDERS:
        provider = default_provider

    if provider == "codex_cli":
        base_url = "local://codex-cli"
    elif provider == "agy_cli":
        base_url = "local://agy-cli"
    else:
        base_url = str(
            saved.get("base_url")
            or os.environ.get("FURNITURE_LLM_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or "http://127.0.0.1:11434/v1"
        ).strip()

    api_key = str(
        saved.get("api_key")
        or os.environ.get("FURNITURE_LLM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or ""
    ).strip()

    fallback_model = (
        "gpt-6.1-sol"
        if provider == "codex_cli"
        else "gemini-3.8-flash-high"
        if provider == "agy_cli"
        else default_model
    )
    model = str(
        saved.get("model")
        or os.environ.get("FURNITURE_LLM_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or fallback_model
    ).strip()

    reasoning_effort = str(
        saved.get("reasoning_effort")
        or os.environ.get("FURNITURE_LLM_REASONING_EFFORT")
        or "high"
    ).strip().lower()
    if reasoning_effort not in VALID_REASONING_EFFORTS:
        reasoning_effort = "high"

    if provider == "agy_cli":
        model, reasoning_effort = _sync_agy_model_and_effort(model, reasoning_effort)

    return {
        "provider": provider,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "reasoning_effort": reasoning_effort,
    }


def public_llm_config(store_root: str | Path) -> dict[str, Any]:
    """返回给前端页面的脱敏配置状态与本机 CLI 可用性。"""
    cfg = load_llm_config(store_root)
    provider = cfg["provider"]
    codex_available = _discover_codex_binary() is not None
    agy_available = _discover_agy_binary() is not None
    has_key = provider == "openai_compatible" and bool(cfg["api_key"])
    codex_auth = None

    if provider == "codex_cli":
        codex_auth = codex._CLIENT.authentication_state(_discover_codex_binary())
        configured = bool(codex_auth["authenticated"] and cfg["model"])
    elif provider == "agy_cli":
        configured = bool(agy_available and cfg["model"])
    else:
        configured = bool(
            cfg["base_url"]
            and cfg["model"]
            and (has_key or _is_localhost_url(cfg["base_url"]))
        )

    return {
        "provider": provider,
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "reasoning_effort": cfg["reasoning_effort"],
        "has_api_key": has_key,
        "api_key_masked": _mask_api_key(cfg["api_key"]) if has_key else "",
        "configured": configured,
        "codex_auth": codex_auth,
        "local_cli": {
            "codex_available": codex_available,
            "agy_available": agy_available,
        },
    }


def save_llm_config(
    store_root: str | Path,
    *,
    provider: str = "openai_compatible",
    base_url: str = "",
    model: str,
    reasoning_effort: str = "high",
    api_key: str | None = None,
    clear_api_key: bool = False,
) -> dict[str, Any]:
    """保存本机大模型配置到 `store/_llm_config.json`。"""
    normalized_provider = str(provider or "openai_compatible").strip()
    if normalized_provider not in VALID_PROVIDERS:
        raise ValueError(
            f"provider must be one of: {', '.join(sorted(VALID_PROVIDERS))}"
        )
    normalized_model = str(model or "").strip()
    if not normalized_model:
        raise ValueError("model must not be empty")
    normalized_effort = str(reasoning_effort or "high").strip().lower()
    if normalized_effort not in VALID_REASONING_EFFORTS:
        raise ValueError(
            f"reasoning_effort must be one of: {', '.join(sorted(VALID_REASONING_EFFORTS))}"
        )

    if normalized_provider == "codex_cli":
        normalized_url = "local://codex-cli"
    elif normalized_provider == "agy_cli":
        normalized_url = "local://agy-cli"
        normalized_model, normalized_effort = _sync_agy_model_and_effort(
            normalized_model, normalized_effort
        )
    else:
        normalized_url = str(base_url or "").strip()
        if not normalized_url:
            raise ValueError("base_url must not be empty")
        parsed = urllib_parse.urlparse(normalized_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be a valid http(s) URL")

    current = load_llm_config(store_root)
    if clear_api_key:
        final_key = ""
    elif normalized_provider == "codex_cli":
        if api_key and api_key.strip():
            raise ValueError("Codex 使用独立登录，不接收 API Key。")
        # Preserve an existing API provider key, but never persist an inherited
        # environment secret merely because the user saved a Codex model setting.
        path = _llm_config_path(store_root)
        try:
            saved = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, ValueError):
            saved = {}
        final_key = str(saved.get("api_key") or "") if isinstance(saved, dict) else ""
    elif api_key is not None and api_key.strip():
        final_key = api_key.strip()
    else:
        final_key = current["api_key"]

    root = Path(store_root)
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider": normalized_provider,
        "base_url": normalized_url,
        "model": normalized_model,
        "reasoning_effort": normalized_effort,
        "api_key": final_key,
        "updated_at": _utc_now_iso(),
    }
    _llm_config_path(root).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return public_llm_config(root)


def validate_connection_config(config: Mapping[str, str]) -> None:
    provider = config["provider"]
    if provider in {"codex_cli", "agy_cli"}:
        if not config["model"]:
            raise AIConnectionError(
                "LLM_NOT_CONFIGURED",
                "尚未填写模型名称，请先在「模型设置」中确认模型名。",
                status_code=422,
            )
    else:
        if not config["base_url"] or not config["model"]:
            raise AIConnectionError(
                "LLM_NOT_CONFIGURED",
                "尚未配置大模型接口，请先点击右上角「模型设置」选择本机 OAuth CLI 或填写 API 配置。",
                status_code=422,
            )
        if not config["api_key"] and not _is_localhost_url(config["base_url"]):
            raise AIConnectionError(
                "LLM_API_KEY_MISSING",
                "尚未填写 API Key，或可在「模型设置」中切换为「本机 Codex / Gemini 登录态（免 API Key）」。",
                status_code=422,
            )
