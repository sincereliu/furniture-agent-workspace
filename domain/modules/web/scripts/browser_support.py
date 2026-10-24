"""Temporary static fixture service shared by Web's browser checks.

Production only serves furniture_web/static; /web-checks exists in this fixture.
"""
from __future__ import annotations

from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import unquote, urlsplit

WEB_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = WEB_ROOT.parents[2]
STATIC = WEB_ROOT / "furniture_web/static"
NODE_TESTS = WEB_ROOT / "tests/node"
BROWSER_TESTS = WEB_ROOT / "tests/browser"


class StaticHandler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        path = unquote(urlsplit(path).path)
        for prefix, root in (
            ("/web-checks/", BROWSER_TESTS),
            ("/layout-view/", STATIC),
            ("/vendor/three/0.186.0/", WORKSPACE / "vendor/three/0.186.0"),
        ):
            if path.startswith(prefix):
                candidate = (root / path[len(prefix):]).resolve()
                if candidate.is_relative_to(root.resolve()) and candidate.is_file():
                    return str(candidate)
        return str(STATIC / "__not_found__")

    def log_message(self, *_args) -> None:
        pass


@contextmanager
def static_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), StaticHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def install_room_probe(surface, *, entry_hook: str, imports: str = "",
                       gesture_hook: str = "", lease_hook: str = "") -> None:
    """Inject probes into controller closures in test responses only."""
    hooks = (
        ("index.js", "return Object.freeze({onProjectUpdated", entry_hook, imports),
        ("gestures.js", "return {displayScene", gesture_hook, ""),
        ("lease.js", "return {applyLease", lease_hook, ""),
    )
    for filename, marker, hook, prefix in hooks:
        if not hook:
            continue

        def instrument(route, request, marker=marker, hook=hook, prefix=prefix):
            response = route.fetch()
            body = response.text()
            if marker not in body:
                raise RuntimeError(f"Room probe insertion point missing: {marker}")
            route.fulfill(response=response, body=prefix + body.replace(marker, hook + "\n" + marker, 1))

        surface.route(f"**/pages/room/{filename}*", instrument)
