"""HTTP adapter for the optional page assistant; no import of server.py."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

import furniture_ai as ai
from furniture_ai import AIConnectionError as WebChatError
from .conversation import clear_chat_history, get_project_chat_state, send_project_chat_message


class LlmConfigSaveRequest(BaseModel):
    """本机大模型连接配置（保存在本机 `store/_llm_config.json`，不上传仓库）。"""

    model_config = ConfigDict(extra="forbid")

    provider: Literal["codex_cli", "agy_cli", "openai_compatible"] = "codex_cli"
    base_url: str = Field(default="")
    model: str = Field(..., min_length=1)
    reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"] = "high"
    api_key: str | None = None
    clear_api_key: bool = False


class ProjectChatMessageRequest(BaseModel):
    """网页端右侧 AI 对话框发来的一条消息。"""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1)


def require_local_codex_access(request: Request, may_edit: Callable[[Request], bool]) -> None:
    """登录只允许本机页面/进程；拒绝跨站请求和伪造 Host。"""
    if not may_edit(request) or request.url.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise HTTPException(status_code=403, detail="codex login is local only")
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(status_code=403, detail="cross-origin codex login denied")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(status_code=403, detail="cross-site codex login denied")


def create_router(
    *,
    workspace_root: Path,
    store_root: Callable[[], Path],
    load_project: Callable[[str], Any],
    may_edit: Callable[[Request], bool],
) -> APIRouter:
    """Bind explicit host services without storing global application state."""
    router = APIRouter()

    @router.get("/api/llm/config")
    async def get_local_llm_config(request: Request):
        """读取本机大模型脱敏配置（仅本机可用）。"""
        if not may_edit(request):
            raise HTTPException(status_code=403, detail="llm config is local only")
        return await asyncio.to_thread(ai.public_llm_config, store_root())


    @router.post("/api/llm/config")
    async def save_local_llm_config(req: LlmConfigSaveRequest, request: Request):
        """保存本机大模型配置（仅本机可用）。"""
        if not may_edit(request):
            raise HTTPException(status_code=403, detail="llm config is local only")
        try:
            return await asyncio.to_thread(
                ai.save_llm_config,
                store_root(),
                provider=req.provider,
                base_url=req.base_url,
                model=req.model,
                reasoning_effort=req.reasoning_effort,
                api_key=req.api_key,
                clear_api_key=req.clear_api_key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


    @router.get("/api/llm/codex/status")
    async def get_codex_login_status(request: Request):
        require_local_codex_access(request, may_edit)
        state = await asyncio.to_thread(ai.codex_authentication_state)
        return JSONResponse(state, headers={"Cache-Control": "no-store"})


    @router.post("/api/llm/codex/login")
    async def start_codex_login(request: Request):
        require_local_codex_access(request, may_edit)
        try:
            state = await asyncio.to_thread(ai.start_codex_login)
            return JSONResponse(state, headers={"Cache-Control": "no-store"})
        except WebChatError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message}) from exc


    @router.get("/api/project/{project_id}/chat")
    async def get_project_chat_endpoint(project_id: str, request: Request):
        """读取项目对话记录、本机模型配置状态与当前阶段快照（仅本机可用）。"""
        if not may_edit(request):
            raise HTTPException(status_code=403, detail="project chat is local only")
        load_project(project_id)
        try:
            return await asyncio.to_thread(
                get_project_chat_state,
                project_id,
                workspace_root=workspace_root,
                store_root=store_root(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


    @router.post("/api/project/{project_id}/chat")
    async def send_project_chat_endpoint(
        project_id: str,
        req: ProjectChatMessageRequest,
        request: Request,
    ):
        """向项目 AI 助手发送一条消息并执行工具调用（仅本机可用）。"""
        if not may_edit(request):
            raise HTTPException(status_code=403, detail="project chat is local only")
        load_project(project_id)
        try:
            return await asyncio.to_thread(
                send_project_chat_message,
                project_id,
                req.message,
                workspace_root=workspace_root,
                store_root=store_root(),
            )
        except WebChatError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


    @router.delete("/api/project/{project_id}/chat")
    async def clear_project_chat_endpoint(project_id: str, request: Request):
        """清空当前项目的对话历史（仅本机可用）。"""
        if not may_edit(request):
            raise HTTPException(status_code=403, detail="project chat is local only")
        load_project(project_id)
        try:
            clear_chat_history(store_root(), project_id)
        except WebChatError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        return {"cleared": True}

    return router


async def shutdown_connections() -> None:
    """Stop the feature's model connections after the host drains requests."""
    await asyncio.to_thread(ai.shutdown)
