from __future__ import annotations

import json
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
    viewer_package_path: Optional[str] = None
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
        gen_launcher: Optional[str | Path] = None,
        timeout_seconds: int = 300,
    ) -> None:
        default_workspace_root = Path(__file__).resolve().parents[5]
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
        self.gen_launcher = Path(
            gen_launcher
            or self.external_repo_root / "skills" / "cad" / "scripts" / "gen"
        ).resolve()
        self.timeout_seconds = timeout_seconds

    def generate_from_source(
        self,
        source_path: str | Path,
        output_path: Optional[str | Path] = None,
        *,
        force: bool = False,
    ) -> BridgeResult:
        """Generate STEP and a component Viewer package from a gen_step() source."""
        resolved_source = self._workspace_path(source_path)
        resolved_output = self._workspace_path(
            output_path
            if output_path is not None
            else self._default_step_output(resolved_source)
        )
        viewer_package_path = self._expected_viewer_package(resolved_source)
        topology_path = viewer_package_path / "assembly.json"

        configuration_error = self._configuration_error(resolved_source, resolved_output)
        if configuration_error:
            return BridgeResult(
                status="failed",
                message=configuration_error,
                source_path=str(resolved_source),
                step_path=str(resolved_output),
                topology_path=str(topology_path),
                viewer_package_path=str(viewer_package_path),
            )

        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        command = [
            str(self.python_executable),
            str(self.gen_launcher),
            resolved_source.as_posix(),
            "--write",
            resolved_output.as_posix(),
            "--json",
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
                viewer_package_path=str(viewer_package_path),
            )

        payload, payload_error = self._generation_payload(completed.stdout)
        if payload is not None:
            viewer_package_path = self._workspace_path(str(payload["packagePath"]))
            topology_path = viewer_package_path / "assembly.json"

        missing_artifacts = [
            path
            for path in (resolved_output, topology_path)
            if not path.is_file() or path.stat().st_size == 0
        ]
        viewer_package_error = self._viewer_package_error(viewer_package_path)
        if (
            completed.returncode == 0
            and payload_error is None
            and not missing_artifacts
            and viewer_package_error is None
        ):
            return BridgeResult(
                status="ok",
                message="text-to-cad generated STEP and component Viewer package.",
                source_path=str(resolved_source),
                step_path=str(resolved_output),
                topology_path=str(topology_path),
                viewer_package_path=str(viewer_package_path),
                stdout=completed.stdout,
                stderr=completed.stderr,
                returncode=completed.returncode,
            )

        details: list[str] = []
        if completed.returncode != 0:
            details.append("text-to-cad scripts/gen returned a non-zero exit code")
        if payload_error:
            details.append(payload_error)
        if missing_artifacts:
            details.append(
                "Missing or empty artifacts: "
                + ", ".join(str(path) for path in missing_artifacts)
            )
        if viewer_package_error:
            details.append(viewer_package_error)
        return BridgeResult(
            status="failed",
            message="; ".join(details),
            source_path=str(resolved_source),
            step_path=str(resolved_output),
            topology_path=str(topology_path),
            viewer_package_path=str(viewer_package_path),
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
        )

    def _workspace_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.workspace_root / candidate
        return candidate.resolve()

    @staticmethod
    def _expected_viewer_package(source_path: Path) -> Path:
        return (
            source_path.parent
            / "__cadgen__"
            / "models"
            / source_path.name
        ).resolve()

    @staticmethod
    def _default_step_output(source_path: Path) -> Path:
        if source_path.name.lower().endswith(".step.py"):
            return source_path.with_suffix("")
        return source_path.with_suffix(".step")

    @staticmethod
    def _generation_payload(stdout: str) -> tuple[dict[str, object] | None, str | None]:
        for line in reversed(stdout.splitlines()):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("ok") is not True:
                return None, "text-to-cad scripts/gen reported an unsuccessful result"
            package_path = payload.get("packagePath")
            if not isinstance(package_path, str) or not package_path.strip():
                return None, "text-to-cad scripts/gen did not report packagePath"
            return payload, None
        return None, "text-to-cad scripts/gen did not emit a JSON result"

    @staticmethod
    def _viewer_package_error(package_path: Path) -> str | None:
        descriptor_path = package_path / "assembly.json"
        if not descriptor_path.is_file() or descriptor_path.stat().st_size == 0:
            return f"Viewer package descriptor is missing or empty: {descriptor_path}"
        try:
            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return f"Viewer package descriptor is invalid: {exc}"
        components = descriptor.get("components") if isinstance(descriptor, dict) else None
        if not isinstance(components, dict) or not components:
            return f"Viewer package has no components: {descriptor_path}"
        package_root = package_path.resolve()
        for component in components.values():
            glb_ref = component.get("glb") if isinstance(component, dict) else None
            if not isinstance(glb_ref, str) or not glb_ref:
                return f"Viewer package contains a component without a GLB reference: {descriptor_path}"
            component_path = (package_path / glb_ref).resolve()
            try:
                component_path.relative_to(package_root)
            except ValueError:
                return f"Viewer package component escapes the package directory: {glb_ref}"
            if not component_path.is_file() or component_path.stat().st_size == 0:
                return f"Viewer package component is missing or empty: {component_path}"
        return None

    def _configuration_error(self, source_path: Path, output_path: Path) -> Optional[str]:
        if not self.python_executable.is_file():
            return f"Project Python interpreter not found: {self.python_executable}"
        if not self.gen_launcher.exists():
            return f"text-to-cad gen launcher not found: {self.gen_launcher}"
        if self.gen_launcher.is_dir() and not (self.gen_launcher / "__main__.py").is_file():
            return f"text-to-cad gen launcher has no __main__.py: {self.gen_launcher}"
        if not source_path.is_file():
            return f"CAD source file not found: {source_path}"
        if source_path.suffix.lower() != ".py":
            return f"CAD source must be a Python file containing gen_step(): {source_path}"
        if output_path.suffix.lower() != ".step":
            return f"CAD output must use .step with text-to-cad scripts/gen: {output_path}"
        return None
