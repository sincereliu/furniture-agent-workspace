"""JSON persistence for Project/Revision aggregates and frozen stage files."""

from __future__ import annotations

import json
from pathlib import Path

from .workflow_project import Project, Revision, StageAttempt


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

    def intent_path(self, project_id: str, intent_sha256: str) -> Path:
        return self.project_dir(project_id) / "intents" / f"{intent_sha256}.json"

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
            self._write_frozen_intent(project.id, revision)
            self._write_attempts(project.id, revision)
        return path

    def load(self, project_id: str) -> Project:
        path = self.project_dir(project_id) / "project.json"
        if not path.is_file():
            raise ValueError(f"project not found: {project_id}")
        return Project.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _write_frozen_intent(self, project_id: str, revision: Revision) -> None:
        if not revision.intent.confirmed:
            return
        path = self.intent_path(project_id, revision.intent_sha256)
        if path.is_file():
            return
        _write_json(path, revision.intent.to_dict())

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
                "intent_sha256": attempt.intent_sha256,
                "passed": attempt.passed,
                "error": attempt.error,
                "created_at": attempt.created_at,
            },
        )
        if attempt.output is not None:
            _write_json(directory / "output.json", attempt.output)
