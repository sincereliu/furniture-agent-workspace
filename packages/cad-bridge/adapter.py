from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class BridgeResult:
    status: str
    message: str
    output_dir: Optional[str] = None
    request_path: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    returncode: Optional[int] = None


class CadBridge:
    """A thin adapter that isolates the external text-to-cad dependency."""

    def __init__(
        self,
        external_repo_root: Optional[str | Path] = None,
        command_template: Optional[str] = None,
    ) -> None:
        default_root = Path(__file__).resolve().parents[2] / "external" / "text-to-cad"
        self.external_repo_root = Path(external_repo_root or default_root).resolve()
        self.command_template = command_template or os.environ.get("TEXT_TO_CAD_COMMAND")

    def generate(self, spec: dict[str, Any], output_dir: Optional[str | Path] = None) -> BridgeResult:
        """Write a normalized request to disk and optionally invoke an external command."""
        output_dir_path = Path(output_dir or self.external_repo_root / "generated").resolve()
        output_dir_path.mkdir(parents=True, exist_ok=True)

        request_path = output_dir_path / "request.json"
        request_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

        if not self.command_template:
            return BridgeResult(
                status="prepared",
                message="Request payload written; no executor configured yet.",
                output_dir=str(output_dir_path),
                request_path=str(request_path),
            )

        expanded_command = self.command_template.format(
            request=str(request_path),
            output=str(output_dir_path),
            repo=str(self.external_repo_root),
        )

        try:
            completed = subprocess.run(
                shlex.split(expanded_command),
                cwd=self.external_repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            return BridgeResult(
                status="failed",
                message=f"Unable to execute bridge command: {exc}",
                output_dir=str(output_dir_path),
                request_path=str(request_path),
            )

        if completed.returncode == 0:
            return BridgeResult(
                status="ok",
                message="External CAD command completed successfully.",
                output_dir=str(output_dir_path),
                request_path=str(request_path),
                stdout=completed.stdout,
                stderr=completed.stderr,
                returncode=completed.returncode,
            )

        return BridgeResult(
            status="failed",
            message="External CAD command failed.",
            output_dir=str(output_dir_path),
            request_path=str(request_path),
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
        )
