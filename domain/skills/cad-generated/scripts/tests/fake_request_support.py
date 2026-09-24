"""测试用的极简 `Request` 替身。

写权限只有一个判据（`server.access_scope`），它只看 `request.client.host`；
编辑租约看请求头 `X-Edit-Lease`。所以替身只需要这两项。
要测"非本机来源被拒"就用 `remote_request()`，要测正常写路径就用 `local_request()`——
别在测试里散落裸字符串主机名。
"""

from __future__ import annotations

LOCAL_HOST = "127.0.0.1"
REMOTE_HOST = "8.8.8.8"


class FakeClient:
    def __init__(self, host: str) -> None:
        self.host = host


class FakeRequest:
    def __init__(
        self,
        host: str = LOCAL_HOST,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.client = FakeClient(host)
        self.headers = dict(headers or {})


def local_request(headers: dict[str, str] | None = None) -> FakeRequest:
    """本机来源：写操作放行。"""
    return FakeRequest(LOCAL_HOST, headers)


def remote_request(headers: dict[str, str] | None = None) -> FakeRequest:
    """非本机来源：写操作一律 403。"""
    return FakeRequest(REMOTE_HOST, headers)


def lease_request(token: str) -> FakeRequest:
    """本机来源 + 带上编辑租约凭据。"""
    return FakeRequest(LOCAL_HOST, {"X-Edit-Lease": token})
