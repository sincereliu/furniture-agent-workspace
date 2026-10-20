"""本机 CLI 可执行文件发现；不读取登录文件。"""
from __future__ import annotations
from pathlib import Path
import shutil
import time


_BIN_CACHE_TTL_SECONDS = 60.0


_CODEX_BIN_CACHE: tuple[float, str | None] | None = None


_AGY_BIN_CACHE: tuple[float, str | None] | None = None


def _discover_codex_binary() -> str | None:
    """查找本机已安装的官方 Codex CLI 可执行文件（带内存缓存，不读取任何认证文件）。"""
    global _CODEX_BIN_CACHE
    now = time.monotonic()
    if _CODEX_BIN_CACHE is not None and (now - _CODEX_BIN_CACHE[0]) < _BIN_CACHE_TTL_SECONDS:
        return _CODEX_BIN_CACHE[1]
    on_path = shutil.which("codex")
    if on_path:
        _CODEX_BIN_CACHE = (now, on_path)
        return on_path
    found: str | None = None
    try:
        codex_bin_root = Path.home() / "AppData" / "Local" / "OpenAI" / "Codex" / "bin"
        if codex_bin_root.is_dir():
            candidates = sorted(
                codex_bin_root.rglob("codex.exe"),
                key=lambda p: p.stat().st_mtime if p.exists() else 0,
                reverse=True,
            )
            if candidates:
                found = str(candidates[0])
    except OSError:
        found = None
    _CODEX_BIN_CACHE = (now, found)
    return found


def _discover_agy_binary() -> str | None:
    """查找本机已安装的官方 Antigravity (AGY / Gemini) CLI 可执行文件（带内存缓存）。"""
    global _AGY_BIN_CACHE
    now = time.monotonic()
    if _AGY_BIN_CACHE is not None and (now - _AGY_BIN_CACHE[0]) < _BIN_CACHE_TTL_SECONDS:
        return _AGY_BIN_CACHE[1]
    on_path = shutil.which("agy")
    if on_path:
        _AGY_BIN_CACHE = (now, on_path)
        return on_path
    found: str | None = None
    try:
        local_agy = Path.home() / "AppData" / "Local" / "agy" / "bin" / "agy.EXE"
        if local_agy.is_file():
            found = str(local_agy)
    except OSError:
        found = None
    _AGY_BIN_CACHE = (now, found)
    return found
