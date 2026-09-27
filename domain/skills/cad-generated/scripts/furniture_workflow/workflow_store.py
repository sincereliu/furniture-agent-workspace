"""JSON persistence for Project/Revision aggregates and frozen stage files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .workflow_project import Project, Revision, StageAttempt
from .workflow_state import WorkflowStage

# 与 server.SAFE_PROJECT_ID 同一条：名单里的 id 必须能原样放进预览地址。
_PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]+$")


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
        """Projects this store can open. Unreadable files are skipped.

        Each row is ``id``, ``name``, ``created_at``, ``revision_number``,
        and ``layout_confirmed``. Newest ``created_at`` comes first.
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
            try:
                project = Project.from_dict(json.loads(file.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError, ValueError, KeyError, TypeError):
                continue
            if project.id != path.name or not project.revisions:
                continue
            latest = project.latest
            rows.append(
                {
                    "id": project.id,
                    "name": project.name,
                    "created_at": project.created_at,
                    "revision_number": latest.number,
                    "layout_confirmed": bool(latest.layout.confirmed),
                }
            )
        rows.sort(key=lambda row: row["created_at"], reverse=True)
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
