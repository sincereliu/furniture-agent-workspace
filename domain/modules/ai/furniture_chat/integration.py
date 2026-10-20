"""The one host attachment point for the optional assistant."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from .http import create_router, shutdown_connections
from .page import ROOT, page_extension


class _ChatStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


def install(
    app: FastAPI,
    *,
    workspace_root: Path,
    store_root: Callable[[], Path],
    load_project: Callable[[str], Any],
    may_edit: Callable[[Request], bool],
) -> None:
    app.include_router(create_router(
        workspace_root=workspace_root,
        store_root=store_root,
        load_project=load_project,
        may_edit=may_edit,
    ))
    app.mount("/web-chat", _ChatStaticFiles(directory=ROOT / "static"), name="web_chat")
    app.state.page_extension_factory = page_extension
    app.on_event("shutdown")(shutdown_connections)
