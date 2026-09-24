"""编辑租约：同一时刻只有一个写者能动这个项目。

为什么需要它：页面（拖动）和助手（对话）都能改同一个项目的布局。两边同时改，
后写的会盖掉先写的——`expected_version` 只能事后发现（409），不能事前避免。

为什么放在磁盘上：租约是**状态**，而写者不在同一个进程里——页面走 HTTP 服务进程，
助手直接调 orchestrator 跑在另一个进程。内存里的锁互相看不见，所以它落在
`store/<project-id>/edit-lease.json`（tmp + replace 原子写），两边读同一份。

三条规矩：

- **有 TTL**：多久没续租就算掉线。页面每 5 秒心跳，助手每步续一次；`LEASE_TTL_SECONDS`
  之内没人续，租约自动失效（关标签页、崩溃、断网都不用管）。
- **不静默接管**：被别人持有就是 `LeaseHeld`，调用方要么等、要么明说"让出"。
  助手在这一层之上做的是"人把活交给我 = 授权"，由 `handover_to_agent()` 显式转移，
  并让页面看得见"助手正在处理"。
- **随时可强制收回**：`transfer()` 是原子的，人永远抢得回来。租约不是用来把主人关在门外的。

这一层只管"谁在写"；能不能写（本机来源、灰度开关）在 `server.access_scope()` / `may_edit()`，
写到一半发现画面过期仍是 409。
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

#: 多久没续租就算掉线。页面心跳 5 秒一次（容 9 次丢失），助手每一步续一次。
LEASE_TTL_SECONDS = 45
#: 页面心跳间隔——只给页面用，助手按步续租。
LEASE_HEARTBEAT_SECONDS = 5

HOLDER_PAGE = "page"
HOLDER_AGENT = "agent"
HOLDERS = frozenset({HOLDER_PAGE, HOLDER_AGENT})

LEASE_FILE_NAME = "edit-lease.json"
_HISTORY_LIMIT = 20


class LeaseHeld(RuntimeError):
    """租约被别人拿着。不要抢——要么等，要么明说"让出"。"""

    def __init__(self, lease: "Lease") -> None:
        super().__init__(
            f"edit lease is held by {lease.holder} ({lease.label}), "
            f"expires in {lease.expires_in():.0f}s"
        )
        self.lease = lease


class LeaseLost(RuntimeError):
    """手上的租约已经不是自己的了（被收回、或已过期被别人拿走）。"""

    def __init__(self, lease: "Lease | None") -> None:
        super().__init__(
            "edit lease is no longer yours"
            + (f"; it is held by {lease.holder} ({lease.label})" if lease else "")
        )
        self.lease = lease


@dataclass(frozen=True)
class Lease:
    """一次编辑权。

    `token` 是**秘密**：写请求要带回来，快照里绝不外发。
    `id` 是**公开**的：谁都能看到"这锁是谁的"，页面据此分辨
    "那个 page 就是我"还是"另一个窗口"。
    """

    token: str
    holder: str
    label: str = ""
    id: str = ""
    acquired_at: str = ""
    expires_at: str = ""
    history: tuple[dict[str, Any], ...] = field(default=())

    def expires_in(self, *, now: float | None = None) -> float:
        moment = _now() if now is None else now
        return max(0.0, _parse(self.expires_at) - moment)

    def is_active(self, *, now: float | None = None) -> bool:
        return self.expires_in(now=now) > 0

    def to_dict(self, *, now: float | None = None) -> dict[str, Any]:
        return {
            "id": self.id,
            "token": self.token,
            "holder": self.holder,
            "label": self.label,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "expires_in": round(self.expires_in(now=now), 1),
        }

    def snapshot(self, *, now: float | None = None) -> dict[str, Any]:
        """给人看的那一份：不含 token（页面/助手都不需要别人的凭据）。"""
        return {
            "id": self.id,
            "holder": self.holder,
            "label": self.label,
            "expires_in": round(self.expires_in(now=now), 1),
        }


def lease_path(store_root: str | Path, project_id: str) -> Path:
    return Path(store_root) / project_id / LEASE_FILE_NAME


def read_lease(
    store_root: str | Path,
    project_id: str,
    *,
    now: float | None = None,
) -> Lease | None:
    """当前有效的租约；过期文件视作没有（但不删——留着当痕迹，下次申请覆盖）。"""
    path = lease_path(store_root, project_id)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or not payload.get("token"):
        return None
    lease = Lease(
        token=str(payload["token"]),
        holder=str(payload.get("holder") or HOLDER_PAGE),
        label=str(payload.get("label") or ""),
        id=str(payload.get("id") or ""),
        acquired_at=str(payload.get("acquired_at") or ""),
        expires_at=str(payload.get("expires_at") or ""),
        history=tuple(payload.get("history") or ()),
    )
    return lease if lease.is_active(now=now) else None


def acquire(
    store_root: str | Path,
    project_id: str,
    *,
    holder: str,
    label: str = "",
    token: str | None = None,
    now: float | None = None,
) -> Lease:
    """申请或续租。同一个 token 续租；被别人拿着就抛 `LeaseHeld`。"""
    _require_holder(holder)
    moment = _now() if now is None else now
    current = read_lease(store_root, project_id, now=moment)
    if current is not None and current.token != token:
        # 被别人拿着（token 不符，或调用方压根没带 token）。
        raise LeaseHeld(current)
    if current is not None:
        lease = _build(
            token=current.token,
            holder=holder,
            label=label or current.label,
            id=current.id,
            moment=moment,
            history=current.history,
            action="renew",
        )
    else:
        # 空位：用调用方带来的 token（页面把它存在 sessionStorage 里，跨申请保持一致），
        # 没带就发一个新的。
        lease = _build(
            token=token or _new_token(),
            holder=holder,
            label=label,
            moment=moment,
            history=(),
            action="acquire",
        )
    _write(store_root, project_id, lease)
    return lease


def transfer(
    store_root: str | Path,
    project_id: str,
    *,
    to: str,
    label: str = "",
    reason: str = "",
    now: float | None = None,
) -> Lease:
    """把编辑权交给谁（原子的）。两处用它：人交给助手、人强制收回。

    不做"只有持有者才能让出"的检查——**人永远抢得回来**；租约不是用来把主人关在门外的。
    """
    _require_holder(to)
    moment = _now() if now is None else now
    current = read_lease(store_root, project_id, now=moment)
    lease = _build(
        token=_new_token(),
        holder=to,
        label=label,
        moment=moment,
        history=(current.history if current else ()),
        action=f"transfer:{reason}" if reason else "transfer",
    )
    _write(store_root, project_id, lease)
    return lease


def release(
    store_root: str | Path,
    project_id: str,
    *,
    token: str,
    now: float | None = None,
) -> bool:
    """归还租约（页面关掉、助手做完）。不是你的 token 就抛 `LeaseLost`。"""
    moment = _now() if now is None else now
    current = read_lease(store_root, project_id, now=moment)
    if current is None:
        return False
    if token and current.token != token:
        raise LeaseLost(current)
    lease = _build(
        token=current.token,
        holder=current.holder,
        label=current.label,
        id=current.id,
        moment=moment,
        history=current.history,
        action="release",
        expired=True,
    )
    _write(store_root, project_id, lease)
    return True


def check_write(
    store_root: str | Path,
    project_id: str,
    *,
    token: str | None = None,
    now: float | None = None,
) -> Lease | None:
    """写之前问一句：现在能不能写？

    - 没人持有（或已过期）→ 放行，返回 `None`（调用方通常紧接着自己 `acquire`）。
    - 持有者就是带 token 的这位 → 放行。
    - 被别人持有 → 抛 `LeaseHeld`（HTTP 层翻成 423）。
    """
    current = read_lease(store_root, project_id, now=now)
    if current is None:
        return None
    if token and current.token == token:
        return current
    raise LeaseHeld(current)


def handover_to_agent(
    store_root: str | Path,
    project_id: str,
    *,
    label: str = "助手",
    reason: str = "handover",
    now: float | None = None,
) -> tuple[Lease, bool]:
    """人把活交给助手 = 授权让出。返回 (租约, 是否真的发生了转移)。

    只有"页面正持有时"才算一次让出（`taken_over=True`）——助手要据此告诉人
    "页面已切成只读，我做完还给你"，而不是默默把人锁在外面。
    """
    current = read_lease(store_root, project_id, now=now)
    if current is not None and current.holder == HOLDER_AGENT:
        return (
            acquire(
                store_root,
                project_id,
                holder=HOLDER_AGENT,
                label=label or current.label,
                token=current.token,
                now=now,
            ),
            False,
        )
    lease = transfer(
        store_root,
        project_id,
        to=HOLDER_AGENT,
        label=label,
        reason=reason,
        now=now,
    )
    return lease, current is not None


def _build(
    *,
    token: str,
    holder: str,
    label: str,
    moment: float,
    history: tuple[dict[str, Any], ...],
    action: str,
    id: str = "",
    expired: bool = False,
) -> Lease:
    expires = moment if expired else moment + LEASE_TTL_SECONDS
    entry = {
        "at": _iso(moment),
        "action": action,
        "holder": holder,
        "label": label,
    }
    return Lease(
        token=token,
        holder=holder,
        label=label,
        id=id or f"lease-{uuid4().hex[:8]}",
        acquired_at=_iso(moment),
        expires_at=_iso(expires),
        history=tuple([*history, entry][-_HISTORY_LIMIT:]),
    )


def _write(store_root: str | Path, project_id: str, lease: Lease) -> None:
    path = lease_path(store_root, project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**lease.to_dict(), "history": list(lease.history)}
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary, path)


def _require_holder(holder: str) -> None:
    if holder not in HOLDERS:
        raise ValueError("lease holder must be one of: " + ", ".join(sorted(HOLDERS)))


def _new_token() -> str:
    return f"lease_{uuid4().hex[:16]}"


def _now() -> float:
    return time.time()


def _iso(moment: float) -> str:
    return datetime.fromtimestamp(moment, tz=timezone.utc).isoformat()


def _parse(value: str) -> float:
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return 0.0


__all__ = [
    "HOLDER_AGENT",
    "HOLDER_PAGE",
    "HOLDERS",
    "LEASE_HEARTBEAT_SECONDS",
    "LEASE_TTL_SECONDS",
    "Lease",
    "LeaseHeld",
    "LeaseLost",
    "acquire",
    "check_write",
    "handover_to_agent",
    "lease_path",
    "read_lease",
    "release",
    "transfer",
]
