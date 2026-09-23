"""测试用的极简 `Request` 替身。

写权限只有一个判据（`server.access_scope`），它只看 `request.client.host`，
所以替身只需要这一项。要测"非本机来源被拒"就用 `remote_request()`，
要测正常写路径就用 `local_request()`——别在测试里散落裸字符串主机名。
"""

from __future__ import annotations

LOCAL_HOST = "127.0.0.1"
REMOTE_HOST = "8.8.8.8"


class FakeClient:
    def __init__(self, host: str) -> None:
        self.host = host


class FakeRequest:
    def __init__(self, host: str = LOCAL_HOST) -> None:
        self.client = FakeClient(host)


def local_request() -> FakeRequest:
    """本机来源：写操作放行。"""
    return FakeRequest(LOCAL_HOST)


def remote_request() -> FakeRequest:
    """非本机来源：写操作一律 403。"""
    return FakeRequest(REMOTE_HOST)
