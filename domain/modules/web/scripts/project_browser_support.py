"""Isolated project store and HTTP service for Web browser checks."""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
from urllib.request import urlopen
from unittest import mock

WORKSPACE = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(WORKSPACE / "domain/stages/cad-generated/scripts"))
from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE)


@contextmanager
def isolated_project_server():
    """Use a unique temporary store; never connect checks to a user's service."""
    import server
    import uvicorn

    with tempfile.TemporaryDirectory(prefix="furniture-web-browser-") as directory, \
            mock.patch.object(server, "OUTPUT_ROOT", Path(directory)), \
            mock.patch.object(server, "STORE_ROOT", Path(directory)), \
            mock.patch.dict(os.environ, {"FURNITURE_PREVIEW_BROWSER": "0"}):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        service = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1",
            port=sock.getsockname()[1], log_level="error", lifespan="off"))
        thread = threading.Thread(target=lambda: service.run(sockets=[sock]), daemon=True)
        base = f"http://127.0.0.1:{sock.getsockname()[1]}"
        try:
            thread.start()
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                try:
                    with urlopen(base + "/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(.05)
            else:
                raise RuntimeError("temporary preview service did not become healthy")
            yield base
        finally:
            service.should_exit = True
            thread.join(timeout=10)
            sock.close()
            if thread.is_alive():
                raise RuntimeError("temporary preview service did not stop")
