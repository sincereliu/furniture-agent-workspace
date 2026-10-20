"""统一的模型连接入口；不读取项目、不执行调用方的工具。"""
from __future__ import annotations
from typing import Any, Callable, Mapping
from . import agy, codex, discovery, openai_compatible
from .contracts import AIConnectionError


def complete(
    config: Mapping[str, str],
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    *,
    on_thinking_delta: Callable[[str], None] | None = None,
    on_reply_delta: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    provider = config.get("provider")
    if provider == "codex_cli":
        return codex.complete(
            config,
            messages,
            tools,
            on_thinking_delta=on_thinking_delta,
            on_reply_delta=on_reply_delta,
        )
    if provider == "agy_cli":
        return agy.complete(
            config,
            messages,
            tools,
            on_thinking_delta=on_thinking_delta,
            on_reply_delta=on_reply_delta,
        )
    return openai_compatible.complete(
        config,
        messages,
        tools,
        on_thinking_delta=on_thinking_delta,
        on_reply_delta=on_reply_delta,
    )


def codex_authentication_state() -> dict[str, Any]:
    return codex._CLIENT.authentication_state(discovery._discover_codex_binary())


def start_codex_login() -> dict[str, Any]:
    binary = discovery._discover_codex_binary()
    if not binary:
        raise AIConnectionError("CODEX_CLI_NOT_FOUND", "本机未安装 Codex。", 422)
    return codex._CLIENT.start_login(binary)


def prewarm_llm(config: Mapping[str, Any]) -> None:
    if config.get("provider") == "codex_cli" and config.get("configured"):
        binary = discovery._discover_codex_binary()
        if binary and config.get("model"):
            codex._CLIENT.prewarm_async(binary, str(config["model"]))


def shutdown() -> None:
    """Release owned persistent connections when the hosting application stops."""
    codex._CLIENT.close()
