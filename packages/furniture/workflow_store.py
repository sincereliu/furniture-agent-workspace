"""Small JSON persistence adapter for Project/Revision aggregates."""

from __future__ import annotations

import json
from pathlib import Path

from furniture.workflow_project import Project


class JsonProjectStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def save(self, project: Project) -> Path:
        project_dir = self.root / project.id
        project_dir.mkdir(parents=True, exist_ok=True)
        path = project_dir / "project.json"
        temporary_path = project_dir / "project.json.tmp"
        temporary_path.write_text(
            json.dumps(project.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(path)
        return path

    def load(self, project_id: str) -> Project:
        path = self.root / project_id / "project.json"
        if not path.is_file():
            raise ValueError(f"project not found: {project_id}")
        return Project.from_dict(json.loads(path.read_text(encoding="utf-8")))

