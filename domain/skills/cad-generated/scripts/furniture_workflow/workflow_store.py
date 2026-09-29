"""JSON persistence for Project/Revision aggregates and frozen stage files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from furniture_layout.project_layout import LAYOUT_SCHEMA_VERSION

from .workflow_project import Project, Revision, StageAttempt
from .workflow_state import WorkflowStage

# 与 server.SAFE_PROJECT_ID 同一条：名单里的 id 必须能原样放进预览地址。
_PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def project_preview_status(project: Project, directory_id: str) -> tuple[str, str]:
    """Whether the latest layout can be opened by the current preview."""
    if project.id != directory_id:
        return "unavailable", "工程编号与保存目录不一致"
    if not project.revisions:
        return "unavailable", "工程没有可查看的修订"
    layout = project.latest.layout
    if layout.schema_version != LAYOUT_SCHEMA_VERSION:
        return "incompatible", "布局格式与当前版本不兼容"
    if layout.validate():
        return "unavailable", "最新版布局数据不完整"
    return "ready", ""


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class JsonProjectStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def project_dir(self, project_id: str) -> Path:
        return self.root / project_id

    def layout_path(self, project_id: str, layout_sha256: str) -> Path:
        return self.project_dir(project_id) / "layouts" / f"{layout_sha256}.json"

    def panel_path(self, project_id: str, panel_sha256: str) -> Path:
        return self.project_dir(project_id) / "panels" / f"{panel_sha256}.json"

    def attempt_dir(
        self,
        project_id: str,
        revision_id: str,
        stage: str,
        number: int,
    ) -> Path:
        return (
            self.project_dir(project_id)
            / "revisions"
            / revision_id
            / "attempts"
            / stage
            / f"{number:03d}"
        )

    def save(self, project: Project) -> Path:
        project_dir = self.project_dir(project.id)
        project_dir.mkdir(parents=True, exist_ok=True)
        path = project_dir / "project.json"
        temporary_path = project_dir / "project.json.tmp"
        temporary_path.write_text(
            json.dumps(project.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(path)
        for revision in project.revisions:
            self._write_frozen_layout(project.id, revision)
            self._write_frozen_panel(project.id, revision)
            self._write_attempts(project.id, revision)
        return path

    def load(self, project_id: str) -> Project:
        path = self.project_dir(project_id) / "project.json"
        if not path.is_file():
            raise ValueError(f"project not found: {project_id}")
        return Project.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_projects(self) -> list[dict[str, Any]]:
        """Projects this store can open. Unavailable files are skipped."""
        return [
            row for row in self.inspect_projects() if row["availability"] == "ready"
        ]

    def inspect_projects(self) -> list[dict[str, Any]]:
        """Saved projects and their preview availability, including unreadable files.

        Each row is ``id``, ``name``, ``created_at``, ``revision_number``,
        ``layout_confirmed``, counts, ``availability``, and ``reason``.
        Openable projects come first, newest ``created_at`` first within a group.
        """
        if not self.root.is_dir():
            return []
        rows: list[dict[str, Any]] = []
        for path in self.root.iterdir():
            if not path.is_dir() or not _PROJECT_ID.fullmatch(path.name):
                continue
            file = path / "project.json"
            if not file.is_file():
                continue
            row: dict[str, Any] = {
                "id": path.name,
                "name": path.name,
                "created_at": "",
                "revision_number": 0,
                "layout_confirmed": False,
                "room_count": 0,
                "item_count": 0,
                "availability": "unavailable",
                "reason": "工程文件无法读取或格式不受支持",
            }
            try:
                payload = json.loads(file.read_text(encoding="utf-8"))
            except (
                OSError,
                json.JSONDecodeError,
                ValueError,
            ):
                rows.append(row)
                continue
            if isinstance(payload, dict):
                if isinstance(payload.get("name"), str):
                    row["name"] = payload["name"] or path.name
                if isinstance(payload.get("created_at"), str):
                    row["created_at"] = payload["created_at"]
                if payload.get("id") != path.name:
                    row["reason"] = "工程编号与保存目录不一致"
                    rows.append(row)
                    continue
                revisions = payload.get("revisions")
                if isinstance(revisions, list) and revisions:
                    latest_payload = revisions[-1]
                    if isinstance(latest_payload, dict):
                        if isinstance(latest_payload.get("number"), int):
                            row["revision_number"] = latest_payload["number"]
                        if "layout" not in latest_payload and "intent" in latest_payload:
                            row.update(
                                availability="incompatible",
                                reason="历史格式没有房间布局，当前预览暂不支持",
                            )
                            rows.append(row)
                            continue
            try:
                project = Project.from_dict(payload)
            except (ValueError, KeyError, TypeError, AttributeError):
                rows.append(row)
                continue
            availability, reason = project_preview_status(project, path.name)
            row.update(
                name=project.name or path.name,
                created_at=project.created_at,
                availability=availability,
                reason=reason,
            )
            if project.revisions:
                latest = project.latest
                row.update(
                    revision_number=latest.number,
                    layout_confirmed=bool(latest.layout.confirmed),
                    room_count=len(latest.layout.rooms),
                    item_count=sum(len(scene.items) for scene in latest.layout.rooms),
                )
            rows.append(row)
        rows.sort(key=lambda row: row["created_at"], reverse=True)
        rows.sort(key=lambda row: row["availability"] != "ready")
        return rows

    def _write_frozen_layout(self, project_id: str, revision: Revision) -> None:
        if not revision.layout.confirmed:
            return
        path = self.layout_path(project_id, revision.layout_sha256)
        if path.is_file():
            return
        _write_json(path, revision.layout.to_dict())

    def _write_frozen_panel(self, project_id: str, revision: Revision) -> None:
        if WorkflowStage.PANELS_PLANNED.value not in revision.approved_stages:
            return
        digest = revision.confirmed_panel_sha256 or revision.panel_sha256
        output = revision.stage_outputs.get(WorkflowStage.PANELS_PLANNED.value)
        if not digest or not isinstance(output, dict):
            return
        path = self.panel_path(project_id, digest)
        if path.is_file():
            return
        _write_json(path, output)

    def _write_attempts(self, project_id: str, revision: Revision) -> None:
        for stage, attempts in revision.stage_attempts.items():
            for attempt in attempts:
                self._write_attempt(project_id, revision.id, attempt)

    def _write_attempt(
        self,
        project_id: str,
        revision_id: str,
        attempt: StageAttempt,
    ) -> None:
        directory = self.attempt_dir(
            project_id,
            revision_id,
            attempt.stage,
            attempt.number,
        )
        _write_json(directory / "input.json", attempt.inputs)
        _write_json(
            directory / "status.json",
            {
                "number": attempt.number,
                "stage": attempt.stage,
                "layout_sha256": attempt.layout_sha256,
                "passed": attempt.passed,
                "error": attempt.error,
                "created_at": attempt.created_at,
            },
        )
        if attempt.output is not None:
            _write_json(directory / "output.json", attempt.output)
