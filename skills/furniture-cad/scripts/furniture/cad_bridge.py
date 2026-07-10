from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class BridgeResult:
    status: str
    message: str
    source_path: Optional[str] = None
    step_path: Optional[str] = None
    topology_path: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    returncode: Optional[int] = None


class CadBridge:
    """Invoke the external text-to-cad STEP CLI from the owning workspace."""

    def __init__(
        self,
        workspace_root: Optional[str | Path] = None,
        external_repo_root: Optional[str | Path] = None,
        python_executable: Optional[str | Path] = None,
        step_launcher: Optional[str | Path] = None,
        timeout_seconds: int = 300,
    ) -> None:
        default_workspace_root = Path(__file__).resolve().parents[4]
        self.workspace_root = Path(workspace_root or default_workspace_root).resolve()
        self.external_repo_root = Path(
            external_repo_root
            or self.workspace_root / "external" / "text-to-cad"
        ).resolve()

        default_python = (
            self.workspace_root / ".venv" / "Scripts" / "python.exe"
            if sys.platform == "win32"
            else self.workspace_root / ".venv" / "bin" / "python"
        )
        self.python_executable = Path(python_executable or default_python).resolve()
        self.step_launcher = Path(
            step_launcher
            or self.external_repo_root / "skills" / "cad" / "scripts" / "step"
        ).resolve()
        self.timeout_seconds = timeout_seconds

    def generate_from_source(
        self,
        source_path: str | Path,
        output_path: Optional[str | Path] = None,
        *,
        force: bool = False,
    ) -> BridgeResult:
        """Generate STEP and Viewer topology artifacts from a gen_step() source."""
        resolved_source = self._workspace_path(source_path)
        resolved_output = self._workspace_path(
            output_path if output_path is not None else resolved_source.with_suffix(".step")
        )
        topology_path = resolved_output.with_name(f".{resolved_output.name}.glb")

        configuration_error = self._configuration_error(resolved_source, resolved_output)
        if configuration_error:
            return BridgeResult(
                status="failed",
                message=configuration_error,
                source_path=str(resolved_source),
                step_path=str(resolved_output),
                topology_path=str(topology_path),
            )

        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        command = [
            str(self.python_executable),
            str(self.step_launcher),
            resolved_source.as_posix(),
            "--output",
            resolved_output.as_posix(),
        ]
        if force:
            command.append("--force")

        try:
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return BridgeResult(
                status="failed",
                message=f"Unable to execute text-to-cad STEP generation: {exc}",
                source_path=str(resolved_source),
                step_path=str(resolved_output),
                topology_path=str(topology_path),
            )

        missing_artifacts = [
            path
            for path in (resolved_output, topology_path)
            if not path.is_file() or path.stat().st_size == 0
        ]
        if completed.returncode == 0 and not missing_artifacts:
            return BridgeResult(
                status="ok",
                message="text-to-cad generated STEP and Viewer topology artifacts.",
                source_path=str(resolved_source),
                step_path=str(resolved_output),
                topology_path=str(topology_path),
                stdout=completed.stdout,
                stderr=completed.stderr,
                returncode=completed.returncode,
            )

        detail = (
            "Missing or empty artifacts: "
            + ", ".join(str(path) for path in missing_artifacts)
            if missing_artifacts
            else "The text-to-cad command returned a non-zero exit code."
        )
        return BridgeResult(
            status="failed",
            message=detail,
            source_path=str(resolved_source),
            step_path=str(resolved_output),
            topology_path=str(topology_path),
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
        )

    def _workspace_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.workspace_root / candidate
        return candidate.resolve()

    def _configuration_error(self, source_path: Path, output_path: Path) -> Optional[str]:
        if not self.python_executable.is_file():
            return f"Project Python interpreter not found: {self.python_executable}"
        if not self.step_launcher.exists():
            return f"text-to-cad STEP launcher not found: {self.step_launcher}"
        if not source_path.is_file():
            return f"CAD source file not found: {source_path}"
        if source_path.suffix.lower() != ".py":
            return f"CAD source must be a Python file containing gen_step(): {source_path}"
        if output_path.suffix.lower() not in {".step", ".stp"}:
            return f"CAD output must use .step or .stp: {output_path}"
        return None
