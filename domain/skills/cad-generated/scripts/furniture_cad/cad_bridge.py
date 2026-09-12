from __future__ import annotations

import json
import os
import shutil
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
    """Run a cadgen model script from the owning workspace.

    Default entry is ``python <source.py> --json`` (text-to-cad 0.5.1).
    ``gen_launcher`` is only a test override that still speaks the old
    ``source --write out --json`` fake-CLI protocol.
    """

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
        self.gen_launcher = (
            Path(gen_launcher).resolve() if gen_launcher is not None else None
        )
        self.timeout_seconds = timeout_seconds

    def generate_from_source(
        self,
        source_path: str | Path,
        output_path: Optional[str | Path] = None,
        *,
        force: bool = False,
    ) -> BridgeResult:
        """Generate STEP and a Viewer view from a cadgen ``@step`` model."""
        resolved_source = self._workspace_path(source_path)
        resolved_output = self._workspace_path(
            output_path
            if output_path is not None
            else self._default_step_output(resolved_source)
        )
        viewer_package_path = self._expected_viewer_package(resolved_source)
        topology_path = viewer_package_path / "assembly.json"
        cache_dir = resolved_source.parent / ".cadgen-store"

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
        command = self._build_command(resolved_source, resolved_output, force=force)
        env = os.environ.copy()
        env["CADGEN_DAEMON"] = "0"
        env["CADGEN_CACHE_DIR"] = str(cache_dir)
        cadgen_src = self._cadgen_src()
        if cadgen_src is not None:
            env["PYTHONPATH"] = os.pathsep.join(
                [str(cadgen_src), env.get("PYTHONPATH", "")]
            ).rstrip(os.pathsep)

        try:
            completed = subprocess.run(
                command,
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return BridgeResult(
                status="failed",
                message=f"Unable to execute cadgen model: {exc}",
                source_path=str(resolved_source),
                step_path=str(resolved_output),
                topology_path=str(topology_path),
                viewer_package_path=str(viewer_package_path),
            )

        payload, payload_error = self._generation_payload(completed.stdout)
        if payload is not None:
            package_ref = payload.get("packagePath")
            if isinstance(package_ref, str) and package_ref.strip():
                viewer_package_path = self._workspace_path(package_ref)
                topology_path = viewer_package_path / "assembly.json"
            document = payload.get("document")
            if isinstance(document, str) and document.strip():
                self._copy_step_if_needed(document, resolved_output)
            tree_hash = payload.get("tree")
            if isinstance(tree_hash, str) and tree_hash.strip():
                view_error = self._export_viewer_view(
                    tree_hash, viewer_package_path, cache_dir, cadgen_src
                )
                if view_error:
                    payload_error = payload_error or view_error
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
                message="cadgen generated STEP and Viewer package.",
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
            details.append("cadgen model returned a non-zero exit code")
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

    def _build_command(
        self, source_path: Path, output_path: Path, *, force: bool
    ) -> list[str]:
        if self.gen_launcher is not None:
            command = [
                str(self.python_executable),
                str(self.gen_launcher),
                source_path.as_posix(),
                "--write",
                output_path.as_posix(),
                "--json",
            ]
            if force:
                command.append("--force")
            return command
        command = [str(self.python_executable), str(source_path), "--json"]
        if force:
            command.append("--force")
        return command

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

    def _cadgen_src(self) -> Path | None:
        candidate = self.external_repo_root / "packages" / "cadgen" / "src"
        return candidate if candidate.is_dir() else None

    def _copy_step_if_needed(self, document: str, output_path: Path) -> None:
        source = Path(document)
        if not source.is_absolute():
            source = (self.workspace_root / source).resolve()
        else:
            source = source.resolve()
        if not source.is_file() or source == output_path:
            return
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output_path)

    @staticmethod
    def _export_viewer_view(
        tree_hash: str,
        dest: Path,
        cache_dir: Path,
        cadgen_src: Path | None,
    ) -> str | None:
        previous = os.environ.get("CADGEN_CACHE_DIR")
        os.environ["CADGEN_CACHE_DIR"] = str(cache_dir)
        inserted = False
        if cadgen_src is not None:
            src = str(cadgen_src)
            if src not in sys.path:
                sys.path.insert(0, src)
                inserted = True
        try:
            from cadgen.store.view import export_view

            dest.mkdir(parents=True, exist_ok=True)
            export_view(tree_hash, dest)
        except Exception as exc:
            return f"cadgen viewer view export failed: {exc}"
        finally:
            if inserted:
                try:
                    sys.path.remove(str(cadgen_src))
                except ValueError:
                    pass
            if previous is None:
                os.environ.pop("CADGEN_CACHE_DIR", None)
            else:
                os.environ["CADGEN_CACHE_DIR"] = previous
        return None

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
                return None, "cadgen reported an unsuccessful result"
            package_path = payload.get("packagePath")
            document = payload.get("document")
            tree = payload.get("tree")
            has_package = isinstance(package_path, str) and bool(package_path.strip())
            has_document = isinstance(document, str) and bool(document.strip())
            has_tree = isinstance(tree, str) and bool(tree.strip())
            if has_package or has_document or has_tree:
                return payload, None
            return None, "cadgen JSON result had no document, tree, or packagePath"
        return None, "cadgen did not emit a JSON result"

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
            if not isinstance(component, dict):
                return f"Viewer package contains a component without a mesh: {descriptor_path}"
            mesh_ref = None
            for key in ("glb", "surf", "brep"):
                value = component.get(key)
                if isinstance(value, str) and value.strip():
                    mesh_ref = value
                    break
            if not mesh_ref:
                return (
                    f"Viewer package contains a component without a mesh reference: "
                    f"{descriptor_path}"
                )
            component_path = (package_path / mesh_ref).resolve()
            try:
                component_path.relative_to(package_root)
            except ValueError:
                return f"Viewer package component escapes the package directory: {mesh_ref}"
            if not component_path.is_file() or component_path.stat().st_size == 0:
                return f"Viewer package component is missing or empty: {component_path}"
        return None

    def _configuration_error(self, source_path: Path, output_path: Path) -> Optional[str]:
        if not self.python_executable.is_file():
            return f"Project Python interpreter not found: {self.python_executable}"
        if self.gen_launcher is not None:
            if not self.gen_launcher.exists():
                return f"test gen launcher not found: {self.gen_launcher}"
            if self.gen_launcher.is_dir() and not (
                self.gen_launcher / "__main__.py"
            ).is_file():
                return f"test gen launcher has no __main__.py: {self.gen_launcher}"
        if not source_path.is_file():
            return f"CAD source file not found: {source_path}"
        if source_path.suffix.lower() != ".py":
            return f"CAD source must be a Python model script: {source_path}"
        if output_path.suffix.lower() != ".step":
            return f"CAD output must use .step: {output_path}"
        return None
