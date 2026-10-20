"""Codex 子进程的路径与环境契约；不读取或复制任何 OAuth 凭据。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping


WORKSPACE_ROOT = Path(__file__).resolve().parents[4]


def validate_codex_home(candidate: Path, *, workspace: Path, app_home: Path) -> Path:
    """拒绝仓库内、App 数据目录内及其父目录；resolve 同时检查目录联接。"""
    resolved = candidate.resolve()
    for protected in (workspace.resolve(), app_home.resolve()):
        if resolved.is_relative_to(protected) or protected.is_relative_to(resolved):
            raise ValueError("独立 Codex 数据目录必须位于仓库和 Codex App 数据目录之外。")
    if any((parent / ".git").exists() for parent in (resolved, *resolved.parents)):
        raise ValueError("独立 Codex 数据目录不能放入 Git 工作区。")
    return resolved


def isolated_codex_home() -> Path:
    # MSIX can virtualize even an absolute AppData/Local path into the App cache.
    # The profile-level directory avoids that redirection as well as CODEX_HOME.
    candidate = Path.home() / ".furniture-agent" / "codex-home"
    resolved = validate_codex_home(
        candidate, workspace=WORKSPACE_ROOT, app_home=Path.home() / ".codex",
    )
    inherited = os.environ.get("CODEX_HOME")
    if inherited:
        validate_codex_home(resolved, workspace=WORKSPACE_ROOT, app_home=Path(inherited))
    if resolved.is_relative_to((Path.home() / "AppData").resolve()):
        raise ValueError("独立 Codex 数据目录不能重定向到 AppData 或应用包缓存。")
    for name in ("auth.json", "config.toml", "runtime", "log"):
        if not (resolved / name).resolve().is_relative_to(resolved):
            raise ValueError("独立 Codex 数据路径不能通过链接指向外部目录。")
    return resolved


def isolated_environment(home: Path, source: Mapping[str, str]) -> dict[str, str]:
    """只构造子进程环境；父进程和系统环境保持原值。"""
    blocked_prefixes = ("CODEX_", "OPENAI_", "AZURE_OPENAI_", "GEMINI_", "FURNITURE_LLM_")
    env = {
        key: value for key, value in source.items()
        if not key.upper().startswith(blocked_prefixes) and key.upper() != "ACCESS_TOKEN"
    }
    env["CODEX_HOME"] = str(home)
    env["CODEX_SQLITE_HOME"] = str(home)
    return env


def isolated_process_options() -> tuple[Path, dict[str, str], list[str]]:
    home = isolated_codex_home()
    runtime = home / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    # Pin credential storage to this home; never use the App's OS keyring entry.
    overrides = {
        "cli_auth_credentials_store": "file",
        "sqlite_home": str(home),
        "log_dir": str(home / "log"),
        "check_for_update_on_startup": False,
    }
    args = []
    for name, value in overrides.items():
        args.extend(["-c", f"{name}={json.dumps(value)}"])
    return runtime, isolated_environment(home, os.environ), args
