"""Make finite HTTP requests to an ASGI app using only the standard library."""

from __future__ import annotations

import json
from types import SimpleNamespace


async def request(app, path, *, method="GET", payload=None, client="127.0.0.1"):
    body = b"" if payload is None else json.dumps(payload).encode("utf-8")
    messages = []
    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    await app({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path,
        "raw_path": path.encode("utf-8"), "query_string": b"", "root_path": "",
        "headers": [(b"host", b"127.0.0.1"), (b"content-type", b"application/json")],
        "client": (client, 1234), "server": ("127.0.0.1", 80),
    }, receive, send)
    start = next(message for message in messages if message["type"] == "http.response.start")
    response_body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return SimpleNamespace(
        status_code=start["status"], body=response_body,
        text=response_body.decode("utf-8"),
        headers={key.decode(): value.decode() for key, value in start["headers"]},
    )
