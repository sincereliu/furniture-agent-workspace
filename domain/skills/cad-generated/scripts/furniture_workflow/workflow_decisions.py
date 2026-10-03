"""决策台账：客户说过的话、我们的翻译，以及它有没有被确认。

为什么要有它：`layout_plan` 里那些是**结果**，`working_ops` 记的是**改了什么**——
两处都答不出"这句话是谁说的、我们把它落成了什么、他点头了没有"。三天后没人分得清
哪一格是客户要的、哪一格是助手替他定的，而下游一切（板件、加工、交付）都建立在这些决定上。

三条规矩（口径见 `references/decision-log-design.md`）：

- **只追加**：改主意是加一条，并把被改的那几条写进 `targets`；旧的一条不动。
  所以"他什么时候改的、改成什么"永远查得回来。
- **不冒充谁**：`speaker` 缺省 `agent`，`status` 缺省 `assumption`。要标成客户说的、
  客户确认的，必须显式写出来；而且只有客户（或转达人）能确认，助手不能自己点头。
- **确认是动作，不是状态**：`status=confirmed` 的条目用 `targets` 指回它确认的那几条。

归属：`schema` + `validation`——规范字段、枚举、引用完整性。
"这句话是什么意思"**不在这里**：那是 LLM 的提案（见 `.agents/skills/furniture-agent/references/llm-runtime-boundary.md`），
代码只把提案收成规范结构并保证自洽。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping

from .workflow_state import utc_now

#: 一条说法能带的字段。多一个都拒——不认历史别名是这套协议的既有规矩。
#: `utterance` 是**客户的原话**：从对话里来的客户条目必须有，助手自己的假设可以没有——
#: 助手本来就没有"原话"可引，硬要一句只会逼出编造的引语。
DECISION_KEYS = frozenset(
    {
        "utterance",
        "interpretation",
        "speaker",
        "status",
        "targets",
        "applies_to",
        "source",
    }
)
#: 谁说的。`relay` 是别人转达的客户话（销售、设计师…），不许当成客户本人。
SPEAKERS = ("customer", "relay", "agent")
#: 这条说法此刻算不算数。缺省 `assumption`：助手假设，等人确认。
STATUSES = ("assumption", "confirmed", "withdrawn")
#: 从哪来的：`tool` = 对话里说出来的（有原话）；`page` = 客户在页面上按的按钮（**没有原话**，
#: 由服务端按固定措辞生成）。分开记，是为了让"没有原话"不等于"原话丢了"。
SOURCES = ("tool", "page")
DEFAULT_SPEAKER = "agent"
DEFAULT_STATUS = "assumption"
DEFAULT_SOURCE = "tool"
#: 只有人能点头。助手的条目永远不能把自己标成"已确认"。
_CONFIRMING_SPEAKERS = frozenset({"customer", "relay"})
#: 能改变别人的那两档：确认、撤回。
_DECIDING_STATUSES = frozenset({"confirmed", "withdrawn"})
_ID_PREFIX = "dec_"


def admit_decisions(
    raw: Any,
    *,
    existing_ids: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """校验一批待追加的说法，返回规范化条目；不落盘、不发号。

    形状不对、字段不认识、枚举不在册、指向了不存在的条目——一律抛 `ValueError`，
    调用方据此**在动手改项目之前**拒绝整批（不留半成品）。

    一次调用里的新说法**不能互相指向**：`targets` 只能指已经在台账里的 id。
    这跟真实时序一致——先记下说法，客户后来点头是下一次调用的事。
    """
    if raw is None:
        return []
    if isinstance(raw, (str, bytes)) or not isinstance(raw, list):
        raise ValueError("decisions must be a list")
    known = {str(value) for value in existing_ids}
    return [
        _admit_one(item, index=index, known=known)
        for index, item in enumerate(raw, start=1)
    ]


def append_decisions(
    ledger: list[dict[str, Any]],
    admitted: Iterable[Mapping[str, Any]],
    *,
    revision_number: int | None = None,
    at: str | None = None,
    actor: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """把已准入的说法追加进台账并发号。台账只增不减。

    `actor` 只由**运行时**给（从编辑租约读出来的"谁记的"）——它不是调用方能填的字段，
    所以不在 `DECISION_KEYS` 里：谁写的这件事不能靠自称。
    """
    added: list[dict[str, Any]] = []
    number = _next_number(ledger)
    moment = at or utc_now()
    for item in admitted:
        entry: dict[str, Any] = {
            **deepcopy(dict(item)),
            "id": f"{_ID_PREFIX}{number + len(added)}",
            "at": moment,
        }
        if revision_number is not None:
            entry["revision_number"] = int(revision_number)
        if actor is not None:
            entry["actor"] = deepcopy(dict(actor))
        added.append(entry)
    ledger.extend(added)
    return added


def decision_states(entries: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """每条说法**此刻**算不算数。

    后续条目里最后一条指向它的"确认/撤回"说了算；没人指向它就是它自己写的那一档。
    派生而不是改写：台账里的条目一个字都不动，所以历史永远读得出原样。
    """
    ordered = list(entries)
    states: dict[str, str] = {}
    for position, entry in enumerate(ordered):
        decision_id = str(entry.get("id") or "")
        state = str(entry.get("status") or DEFAULT_STATUS)
        for later in ordered[position + 1:]:
            targets = _entry_refs(later.get("targets"))
            if decision_id and decision_id in targets:
                later_status = str(later.get("status") or DEFAULT_STATUS)
                if later_status in _DECIDING_STATUSES:
                    state = later_status
        states[decision_id] = state
    return states


def pending_decision_ids(entries: Iterable[Mapping[str, Any]]) -> list[str]:
    """还没人确认的说法（助手假设）——"还差哪几条要问客户"就是它。"""
    ordered = list(entries)
    states = decision_states(ordered)
    return [
        str(entry.get("id") or "")
        for entry in ordered
        if states.get(str(entry.get("id") or "")) == DEFAULT_STATUS
    ]


def parse_ref(ref: str) -> tuple[str, str | None]:
    """把 `applies_to` 里的一条引用拆成 `(对象 id, 字段名 | None)`。

    两种写法都收：`cabinet_1`（这一件）与 `cabinet_1.offset_mm`（这一件的某一处）。
    """
    object_id, _, field = str(ref).partition(".")
    return object_id, (field or None)


def changed_item_fields(
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
) -> dict[str, tuple[Any, Any]]:
    """两次家具快照之间**真正变了**的字段 → `{字段: (旧值, 新值)}`。

    用"改前 vs 改后"而不是"这次发的是什么 op"：拖回原位、改了个一样的值都不算改动，
    台账不该为一次没发生的改动作废任何东西。快照形状见 `_item_snapshot()`。
    """
    old_placement = dict((before or {}).get("placement") or {})
    new_placement = dict((after or {}).get("placement") or {})
    changes: dict[str, tuple[Any, Any]] = {}
    for key in sorted(set(old_placement) | set(new_placement)):
        if key == "fill":
            # fill 件的宽与偏移由墙上空段派生，不是"谁改的"。
            continue
        if old_placement.get(key) != new_placement.get(key):
            changes[key] = (old_placement.get(key), new_placement.get(key))
    for key in ("width", "depth", "height"):
        old_value = (before or {}).get(key)
        new_value = (after or {}).get(key)
        if old_value != new_value:
            changes[key] = (old_value, new_value)
    return changes


def stale_pending_ids(
    entries: Iterable[Mapping[str, Any]],
    changes: Mapping[str, Mapping[str, tuple[Any, Any]]],
) -> list[str]:
    """这次动作**直接动摇**了哪几条待确认的假设。

    `changes` 是 `{对象 id: {字段: (旧值, 新值)}}`。规则（宁可不动作，也不误作废）：

    - 只看**还待确认**的条目——已经确认过的是"客户点过头的东西"，代码不许替他改；
    - 只看 `对象.字段` 这种**精确引用**：纯对象级的引用太模糊，不动它；
    - 字段必须真的变了（值相等不算）。
    """
    ordered = list(entries)
    states = decision_states(ordered)
    stale: list[str] = []
    for entry in ordered:
        decision_id = str(entry.get("id") or "")
        if states.get(decision_id) != DEFAULT_STATUS:
            continue
        for ref in _entry_refs(entry.get("applies_to")):
            object_id, field = parse_ref(ref)
            if not field:
                continue
            if field in (changes.get(object_id) or {}):
                stale.append(decision_id)
                break
    return stale


def auto_withdrawn_entries(
    entries: Iterable[Mapping[str, Any]],
    changes: Mapping[str, Mapping[str, tuple[Any, Any]]],
    *,
    speaker: str = "customer",
    source: str = "page",
    limit: int = 3,
) -> list[dict[str, Any]]:
    """为"被动摇的待确认假设"生成作废条目（还没准入）。

    措辞在这里统一写：谁的动作、改了哪一处、从多少到多少——出问题时一眼看得出为什么作废。
    一次动作涉及多处时只列前 `limit` 处，其余写成"等 N 处"。
    """
    stale = stale_pending_ids(entries, changes)
    if not stale:
        return []
    details: list[str] = []
    total = 0
    for object_id, fields in changes.items():
        for field, (old_value, new_value) in fields.items():
            total += 1
            if len(details) < limit:
                details.append(
                    f"{object_id}.{field} 从 {_format_value(old_value)} "
                    f"改成 {_format_value(new_value)}"
                )
    summary = "；".join(details)
    if total > len(details):
        summary += f" 等 {total} 处"
    who = "客户" if speaker == "customer" else "助手"
    return [
        {
            "interpretation": f"{who}直接改了 {summary}，与这条假设不一致，自动作废",
            "speaker": speaker,
            "status": "withdrawn",
            "targets": [decision_id],
            "source": source,
        }
        for decision_id in stale
    ]


def _format_value(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def decision_views(entries: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """给人、给页面看的那一份（原话、翻译、谁说的、哪一版记的）。"""
    keys = (
        "id",
        "at",
        "revision_number",
        "speaker",
        "status",
        "source",
        "utterance",
        "interpretation",
        "targets",
        "applies_to",
        "actor",
    )
    return [
        {key: deepcopy(entry[key]) for key in keys if key in entry}
        for entry in entries
        if isinstance(entry, Mapping)
    ]


def pending_decision_views(entries: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """待确认的那几条，按记录顺序。"""
    pending = set(pending_decision_ids(entries))
    return [view for view in decision_views(entries) if view.get("id") in pending]


def _admit_one(item: Any, *, index: int, known: set[str]) -> dict[str, Any]:
    where = f"decisions[{index}]"
    if not isinstance(item, Mapping):
        raise ValueError(f"{where} must be an object")
    unknown = sorted(set(item) - DECISION_KEYS)
    if unknown:
        raise ValueError(f"unknown field in {where}: " + ", ".join(unknown))
    speaker = _choice(
        item.get("speaker", DEFAULT_SPEAKER), SPEAKERS, f"{where}.speaker"
    )
    status = _choice(item.get("status", DEFAULT_STATUS), STATUSES, f"{where}.status")
    source = _choice(
        item.get("source", DEFAULT_SOURCE), SOURCES, f"{where}.source"
    )
    # 从对话里来的客户话必须有原话；助手自己的假设、以及页面上的按钮（本来就没有话）
    # 可以没有——硬要求一句"原话"只会逼出编造的引语，那正是这本账要防的事。
    if speaker in _CONFIRMING_SPEAKERS and source != "page":
        utterance = _text(item.get("utterance"), f"{where}.utterance")
    else:
        utterance = _optional_text(item.get("utterance"), f"{where}.utterance")
    interpretation = _text(item.get("interpretation"), f"{where}.interpretation")
    targets = _refs(item.get("targets"), f"{where}.targets")
    applies_to = _refs(item.get("applies_to"), f"{where}.applies_to")
    missing = sorted(set(targets) - known)
    if missing:
        raise ValueError(
            f"{where}.targets must name existing decisions: " + ", ".join(missing)
        )
    if status == "withdrawn" and not targets:
        raise ValueError(
            f"{where}: status=withdrawn must name the decisions it withdraws"
        )
    if status == "confirmed" and speaker not in _CONFIRMING_SPEAKERS:
        raise ValueError(
            f"{where}: only the customer (or a relay) can confirm; "
            f"speaker={DEFAULT_SPEAKER} is not a confirmation"
        )
    return {
        "utterance": utterance,
        "interpretation": interpretation,
        "speaker": speaker,
        "status": status,
        "targets": targets,
        "applies_to": applies_to,
        "source": source,
    }


def _entry_refs(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return []


def _refs(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be a list of ids")
    refs: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{name} must contain non-empty strings")
        refs.append(item.strip())
    if len(refs) != len(set(refs)):
        raise ValueError(f"{name} must not repeat an id")
    return refs


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any, name: str) -> str:
    """可以不写，但写了就得是字符串——空字符串按"没写"算。"""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value.strip()


def _choice(value: Any, allowed: tuple[str, ...], name: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(f"{name} must be one of: " + ", ".join(allowed))
    return value


def _next_number(ledger: Iterable[Mapping[str, Any]]) -> int:
    highest = 0
    for entry in ledger:
        raw = str(entry.get("id") or "")
        suffix = raw[len(_ID_PREFIX):] if raw.startswith(_ID_PREFIX) else ""
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return highest + 1


__all__ = [
    "DECISION_KEYS",
    "DEFAULT_SPEAKER",
    "DEFAULT_SOURCE",
    "DEFAULT_STATUS",
    "SOURCES",
    "SPEAKERS",
    "STATUSES",
    "admit_decisions",
    "append_decisions",
    "auto_withdrawn_entries",
    "changed_item_fields",
    "decision_states",
    "decision_views",
    "parse_ref",
    "pending_decision_ids",
    "pending_decision_views",
    "stale_pending_ids",
]
