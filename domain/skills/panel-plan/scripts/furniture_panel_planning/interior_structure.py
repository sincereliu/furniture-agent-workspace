"""Evaluate front seams, divider intervals, and panel breaks.

Design choices come in as a normalized object. Millimeters come out.
This module does not read prose and does not materialize cabinet panels.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence


_UM = 1000  # 0.001 mm
_HUNDREDTH = 10  # 0.01 mm
_ALIGNS = frozenset({"center", "left_face", "right_face"})
_GRADES = frozenset({"confirmed", "typical", "unknown"})
_SPEC_KEYS = frozenset(
    {
        "width_mm",
        "n_doors",
        "margin_mm",
        "side_thickness_mm",
        "pairs",
        "dividers",
        "panels",
        "breaks",
        "cavity_needs",
        "min_segment_mm",
        "min_segment_grade",
        "min_door_width_mm",
        "max_door_width_mm",
        "door_width_grade",
    }
)
_DIVIDER_KEYS = frozenset({"id", "seam_index", "seam_align", "thickness_mm"})
_PANEL_KEYS = frozenset({"id", "start_mm", "end_mm"})
_BREAK_KEYS = frozenset(
    {"panel_id", "align_divider", "at_mm", "width_mm", "reason"}
)
_NEED_KEYS = frozenset({"cavity_index", "grade", "min_clear_width_mm"})


def evaluate_interior(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Return door seams, divider intervals, cavities, and panel segments.

    ``blocked`` is true when a finding says the layout must not be cut yet.
    Computed millimeters stay in the report either way.
    """
    if not isinstance(spec, Mapping):
        raise ValueError("interior spec must be an object")
    _reject_unknown(spec, _SPEC_KEYS, "interior spec")
    width_u = _units(spec.get("width_mm"), "width_mm")
    if width_u % _HUNDREDTH != 0:
        raise ValueError("width_mm must be a multiple of 0.01")
    if width_u <= 0:
        raise ValueError("width_mm must be positive")
    n_doors = _integer(spec.get("n_doors"), "n_doors")
    if n_doors < 1:
        raise ValueError("n_doors must be at least 1")
    margin_u = _units(spec.get("margin_mm"), "margin_mm")
    if margin_u < 0:
        raise ValueError("margin_mm must be non-negative")
    side_u = _units(spec.get("side_thickness_mm"), "side_thickness_mm")
    if side_u < 0:
        raise ValueError("side_thickness_mm must be non-negative")

    pairs = _pairs(spec.get("pairs", ()), n_doors)
    doors = _layout_doors(width_u, n_doors, margin_u)
    doors["pairs"] = [[left, right] for left, right in pairs]
    findings: list[dict[str, Any]] = []
    if any(width <= 0 for width in doors["width_u"]):
        findings.append(
            _loss(
                "door_width",
                "blocked",
                "门宽不是正数",
                "按非正门宽下料",
                "这一轮没有可审查的门",
            )
        )
    dividers = _place_dividers(spec.get("dividers", ()), doors, n_doors)
    _note_duplicate_seams(dividers, findings)
    cavities = _cavities(width_u, side_u, dividers)
    _note_negative_cavities(cavities, findings)
    _apply_cavity_needs(spec.get("cavity_needs", ()), cavities, findings)
    panels = _panel_segments(
        spec.get("panels", ()),
        spec.get("breaks", ()),
        dividers,
        findings,
    )
    _apply_min_segment(spec, panels, findings)
    _apply_door_width_range(spec, doors, findings)
    return _report(doors, dividers, cavities, panels, findings)


def _layout_doors(
    width_u: int,
    n_doors: int,
    margin_u: int,
) -> dict[str, Any]:
    """Whole-millimeter door widths. Inner gaps stay at twice the margin.

    Extra whole millimeters go to the leftmost doors, one millimeter each.
    Anything under 1 mm stays on the right margin.
    """
    gap_u = 2 * margin_u
    budget_u = width_u - n_doors * gap_u
    if budget_u <= 0:
        widths = [budget_u // n_doors] * n_doors
    else:
        whole_mm, _fraction = divmod(budget_u, _UM)
        base, extra = divmod(whole_mm, n_doors)
        widths = [
            (base + (1 if index < extra else 0)) * _UM
            for index in range(n_doors)
        ]
    starts: list[int] = []
    gaps: list[int] = []
    centers: list[int] = []
    cursor = margin_u
    for index, door_u in enumerate(widths):
        starts.append(cursor)
        door_end = cursor + door_u
        if index == n_doors - 1:
            cursor = door_end
            break
        gaps.append(gap_u)
        centers.append(door_end + gap_u // 2)
        cursor = door_end + gap_u
    return {
        "width_u": widths,
        "left_margin_u": margin_u,
        "right_margin_u": width_u - cursor,
        "start_u": starts,
        "gap_u": gaps,
        "seam_center_u": centers,
    }


def _place_dividers(
    value: Any,
    doors: Mapping[str, Any],
    n_doors: int,
) -> list[dict[str, Any]]:
    items = _sequence(value, "dividers")
    if items and n_doors < 2:
        raise ValueError("a divider needs an inner seam")
    centers: list[int] = doors["seam_center_u"]
    placed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("each divider must be an object")
        _reject_unknown(item, _DIVIDER_KEYS, "divider")
        divider_id = item.get("id")
        if not isinstance(divider_id, str) or not divider_id.strip():
            raise ValueError("divider id must be a non-empty string")
        if divider_id in seen:
            raise ValueError("divider id is duplicated")
        seen.add(divider_id)
        seam = _integer(item.get("seam_index"), "seam_index")
        if seam < 0 or seam >= n_doors - 1:
            raise ValueError("seam_index is outside the inner seams")
        align = item.get("seam_align", "center")
        if align not in _ALIGNS:
            raise ValueError(
                "seam_align must be center, left_face, or right_face"
            )
        thickness_u = _units(item.get("thickness_mm"), "thickness_mm")
        if thickness_u <= 0:
            raise ValueError("thickness_mm must be positive")
        anchor = centers[seam]
        start, end = _anchored_interval(anchor, thickness_u, align)
        placed.append(
            {
                "id": divider_id,
                "seam_index": seam,
                "seam_align": align,
                "anchor_u": anchor,
                "start_u": start,
                "end_u": end,
                "thickness_u": thickness_u,
            }
        )
    return placed


def _anchored_interval(anchor: int, thickness: int, align: str) -> tuple[int, int]:
    if align == "center":
        start = anchor - thickness // 2
        return start, start + thickness
    if align == "left_face":
        return anchor, anchor + thickness
    return anchor - thickness, anchor


def _note_duplicate_seams(
    dividers: Sequence[Mapping[str, Any]],
    findings: list[dict[str, Any]],
) -> None:
    seen: set[int] = set()
    for item in dividers:
        seam = int(item["seam_index"])
        if seam in seen:
            findings.append(
                _loss(
                    "divider_seam",
                    "blocked",
                    f"缝 {seam} 上有两块中立板",
                    "两块板占同一条缝仍去下料",
                    "这一轮定不下中立板",
                )
            )
        seen.add(seam)


def _cavities(
    width_u: int,
    side_u: int,
    dividers: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    left = side_u
    right = width_u - side_u
    ordered = sorted(dividers, key=lambda item: (item["start_u"], item["id"]))
    if not ordered:
        bounds = [(left, right)]
    else:
        bounds = [(left, int(ordered[0]["start_u"]))]
        for prev, nxt in zip(ordered, ordered[1:]):
            bounds.append((int(prev["end_u"]), int(nxt["start_u"])))
        bounds.append((int(ordered[-1]["end_u"]), right))
    return [
        {
            "index": index,
            "clear_u": end - start,
            "status": "ok",
        }
        for index, (start, end) in enumerate(bounds)
    ]


def _note_negative_cavities(
    cavities: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> None:
    for cavity in cavities:
        if int(cavity["clear_u"]) < 0:
            cavity["status"] = "blocked"
            findings.append(
                _loss(
                    "cavity_negative",
                    "blocked",
                    f"腔 {cavity['index']} 的净空是负数",
                    "中立板和侧板叠在一起仍去下料",
                    "这一轮定不下腔",
                )
            )


def _apply_cavity_needs(
    value: Any,
    cavities: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> None:
    for item in _sequence(value, "cavity_needs"):
        if not isinstance(item, Mapping):
            raise ValueError("each cavity need must be an object")
        _reject_unknown(item, _NEED_KEYS, "cavity need")
        index = _integer(item.get("cavity_index"), "cavity_index")
        if index < 0 or index >= len(cavities):
            raise ValueError("cavity_index is outside the cavities")
        grade = item.get("grade")
        if grade not in _GRADES:
            raise ValueError("grade must be confirmed, typical, or unknown")
        cavity = cavities[index]
        clear_u = int(cavity["clear_u"])
        if grade == "unknown":
            if "min_clear_width_mm" in item:
                raise ValueError("an unknown cavity need has no minimum")
            cavity["status"] = _worse(str(cavity["status"]), "blocked")
            findings.append(
                _loss(
                    "cavity_unknown",
                    "blocked",
                    f"腔 {index} 净空 {_mm(clear_u)} mm，用途未知",
                    "没有依据就按这个净空下料",
                    "这一轮不出板",
                )
            )
            continue
        if "min_clear_width_mm" not in item:
            raise ValueError(
                "confirmed and typical cavity needs require min_clear_width_mm"
            )
        minimum = _units(item.get("min_clear_width_mm"), "min_clear_width_mm")
        if clear_u >= minimum:
            continue
        if grade == "confirmed":
            status = "blocked"
            proceed = "按这个净空下料，腔放不下"
            stop = "这一轮没有可审查的板件"
        else:
            status = "assumption"
            proceed = "典型值放不下，照做可能返工"
            stop = "没有可确认的假设方案"
        cavity["status"] = _worse(str(cavity["status"]), status)
        findings.append(
            _loss(
                "cavity_fit",
                status,
                f"腔 {index} 净空 {_mm(clear_u)} mm，需要 {_mm(minimum)} mm",
                proceed,
                stop,
            )
        )


def _panel_segments(
    panels_value: Any,
    breaks_value: Any,
    dividers: Sequence[Mapping[str, Any]],
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    panels = _parse_panels(panels_value)
    divider_by_id = {str(item["id"]): item for item in dividers}
    breaks = _parse_breaks(breaks_value, panels, divider_by_id)
    grouped: dict[str, list[dict[str, Any]]] = {
        str(panel["id"]): [] for panel in panels
    }
    for item in breaks:
        grouped[str(item["panel_id"])].append(item)
    result: list[dict[str, Any]] = []
    for panel in panels:
        segments, widths, problem = _cut_span(panel, grouped[str(panel["id"])])
        if problem:
            findings.append(
                _loss(
                    "break_overlap",
                    "blocked",
                    f"{panel['id']} 的断口重叠或落在板外",
                    "断口对不齐仍去开料",
                    "这一轮定不下这块板",
                )
            )
        result.append(
            {
                "id": panel["id"],
                "segment_u": segments,
                "break_u": widths,
            }
        )
    return result


def _parse_panels(value: Any) -> list[dict[str, Any]]:
    panels: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _sequence(value, "panels"):
        if not isinstance(item, Mapping):
            raise ValueError("each panel must be an object")
        _reject_unknown(item, _PANEL_KEYS, "panel")
        panel_id = item.get("id")
        if not isinstance(panel_id, str) or not panel_id.strip():
            raise ValueError("panel id must be a non-empty string")
        if panel_id in seen:
            raise ValueError("panel id is duplicated")
        seen.add(panel_id)
        start_u = _units(item.get("start_mm"), "start_mm")
        end_u = _units(item.get("end_mm"), "end_mm")
        if end_u <= start_u:
            raise ValueError("panel end_mm must be greater than start_mm")
        panels.append({"id": panel_id, "start_u": start_u, "end_u": end_u})
    return panels


def _parse_breaks(
    value: Any,
    panels: Sequence[Mapping[str, Any]],
    divider_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    panel_ids = {str(panel["id"]) for panel in panels}
    parsed: list[dict[str, Any]] = []
    for item in _sequence(value, "breaks"):
        if not isinstance(item, Mapping):
            raise ValueError("each break must be an object")
        _reject_unknown(item, _BREAK_KEYS, "break")
        panel_id = item.get("panel_id")
        if panel_id not in panel_ids:
            raise ValueError("break panel_id does not match a panel")
        align = item.get("align_divider")
        at_mm = item.get("at_mm", None)
        has_align = align is not None
        has_at = "at_mm" in item
        if has_align == has_at:
            raise ValueError("a break names align_divider or at_mm")
        reason = item.get("reason", "")
        if not isinstance(reason, str):
            raise ValueError("break reason must be a string")
        if has_align:
            if "width_mm" in item:
                raise ValueError(
                    "a divider break takes its width from the divider"
                )
            if not isinstance(align, str) or align not in divider_by_id:
                raise ValueError("align_divider does not match a divider")
            divider = divider_by_id[align]
            start_u = int(divider["start_u"])
            end_u = int(divider["end_u"])
        else:
            start_u = _units(at_mm, "at_mm")
            width_u = (
                0
                if "width_mm" not in item
                else _units(item.get("width_mm"), "width_mm")
            )
            if width_u < 0:
                raise ValueError("break width_mm must be non-negative")
            end_u = start_u + width_u
        parsed.append(
            {
                "panel_id": panel_id,
                "start_u": start_u,
                "end_u": end_u,
            }
        )
    return parsed


def _cut_span(
    panel: Mapping[str, Any],
    breaks: Sequence[Mapping[str, Any]],
) -> tuple[list[int], list[int], bool]:
    start = int(panel["start_u"])
    end = int(panel["end_u"])
    cuts = sorted(
        (int(item["start_u"]), int(item["end_u"])) for item in breaks
    )
    problem = False
    cursor = start
    segments: list[int] = []
    widths: list[int] = []
    previous: tuple[int, int] | None = None
    for cut_start, cut_end in cuts:
        if cut_start < start or cut_end > end or cut_start > cut_end:
            problem = True
        if previous is not None and (
            cut_start < previous[1] or (cut_start, cut_end) == previous
        ):
            problem = True
        if cut_start > cursor:
            segments.append(cut_start - cursor)
        widths.append(max(cut_end - cut_start, 0))
        cursor = max(cursor, cut_end)
        previous = (cut_start, cut_end)
    if cursor < end:
        segments.append(end - cursor)
    elif cursor > end:
        problem = True
    return segments, widths, problem


def _apply_min_segment(
    spec: Mapping[str, Any],
    panels: Sequence[Mapping[str, Any]],
    findings: list[dict[str, Any]],
) -> None:
    has_mm = "min_segment_mm" in spec
    has_grade = "min_segment_grade" in spec
    if not panels:
        if has_mm or has_grade:
            raise ValueError("min_segment_mm applies to panels")
        return
    if not has_mm and not has_grade:
        findings.append(
            _loss(
                "segment_unjudged",
                "unjudged",
                "最小段宽没有车间数据，段长没有判",
                "把没判当成做得出，短板会进车间",
                "没有车间数据就整单停住",
            )
        )
        return
    if not has_mm or not has_grade:
        raise ValueError("min segment needs both millimeters and grade")
    grade = spec.get("min_segment_grade")
    if grade not in {"confirmed", "typical"}:
        raise ValueError("min_segment_grade must be confirmed or typical")
    minimum = _units(spec.get("min_segment_mm"), "min_segment_mm")
    if minimum <= 0:
        raise ValueError("min_segment_mm must be positive")
    for panel in panels:
        short = [
            int(length)
            for length in panel["segment_u"]
            if int(length) < minimum
        ]
        if not short:
            continue
        if grade == "confirmed":
            status = "blocked"
            proceed = "短板仍去开料"
            stop = "这一轮定不下这块板"
        else:
            status = "assumption"
            proceed = "按典型最小段宽，这段可能做不出来"
            stop = "没有可确认的分段方案"
        findings.append(
            _loss(
                "segment_short",
                status,
                f"{panel['id']} 有一段 {_mm(min(short))} mm，最小 {_mm(minimum)} mm",
                proceed,
                stop,
            )
        )


def _apply_door_width_range(
    spec: Mapping[str, Any],
    doors: Mapping[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    """判门宽是否落在车间推荐区间里（下限 350、上限 450 那类数据）。

    只判，不给方案：太窄或太重怎么办由所属 Skill 说明，代码不替人挑扇数。
    区间可以只给一头（只给上限或只给下限）。

    **一头都不给就是不判**，不报 `unjudged`：门是必填项，每次调用都带一条
    "没有车间数据"会变成噪音。未判这件事写在提案契约里，不在回报里刷。
    """
    has_min = "min_door_width_mm" in spec
    has_max = "max_door_width_mm" in spec
    has_grade = "door_width_grade" in spec
    if not has_min and not has_max:
        if has_grade:
            raise ValueError("door_width_grade needs a door width bound")
        return
    if not has_grade:
        raise ValueError("a door width bound needs door_width_grade")
    grade = spec.get("door_width_grade")
    if grade not in {"confirmed", "typical"}:
        raise ValueError("door_width_grade must be confirmed or typical")
    minimum = _units(spec.get("min_door_width_mm"), "min_door_width_mm") if has_min else None
    maximum = _units(spec.get("max_door_width_mm"), "max_door_width_mm") if has_max else None
    for bound in (minimum, maximum):
        if bound is not None and bound <= 0:
            raise ValueError("door width bounds must be positive")
    if minimum is not None and maximum is not None and minimum >= maximum:
        raise ValueError("min_door_width_mm must be under max_door_width_mm")
    if grade == "confirmed":
        status = "blocked"
        narrow_proceed = "按这个门宽下料，门偏窄、容易变形"
        wide_proceed = "按这个门宽下料，门偏重、铰链吃力"
    else:
        status = "assumption"
        narrow_proceed = "低于推荐下限，照做可能不好看或变形"
        wide_proceed = "高于推荐上限，照做可能下垂"
    widths = [int(value) for value in doors["width_u"]]
    if minimum is not None:
        narrow = [(index, width) for index, width in enumerate(widths) if width < minimum]
        if narrow:
            index, width = min(narrow, key=lambda pair: pair[1])
            count = f"（{len(narrow)} 扇）" if len(narrow) > 1 else ""
            findings.append(
                _loss(
                    "door_width_narrow",
                    status,
                    f"门 {index} 宽 {_mm(width)} mm{count}，窄于 {_mm(minimum)} mm",
                    narrow_proceed,
                    "这一轮没有可审查的门",
                )
            )
    if maximum is not None:
        wide = [(index, width) for index, width in enumerate(widths) if width > maximum]
        if wide:
            index, width = max(wide, key=lambda pair: pair[1])
            count = f"（{len(wide)} 扇）" if len(wide) > 1 else ""
            findings.append(
                _loss(
                    "door_width_wide",
                    status,
                    f"门 {index} 宽 {_mm(width)} mm{count}，宽于 {_mm(maximum)} mm",
                    wide_proceed,
                    "这一轮没有可审查的门",
                )
            )


def _report(
    doors: Mapping[str, Any],
    dividers: Sequence[Mapping[str, Any]],
    cavities: Sequence[Mapping[str, Any]],    panels: Sequence[Mapping[str, Any]],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "blocked": any(item["status"] == "blocked" for item in findings),
        "doors": {
            "door_widths_mm": [_mm(int(value)) for value in doors["width_u"]],
            "pairs": [list(pair) for pair in doors["pairs"]],
            "left_margin_mm": _mm(int(doors["left_margin_u"])),
            "right_margin_mm": _mm(int(doors["right_margin_u"])),
            "door_starts_mm": [_mm(int(value)) for value in doors["start_u"]],
            "gaps_mm": [_mm(int(value)) for value in doors["gap_u"]],
            "seam_centers_mm": [
                _mm(int(value)) for value in doors["seam_center_u"]
            ],
        },
        "dividers": [
            {
                "id": item["id"],
                "seam_index": item["seam_index"],
                "seam_align": item["seam_align"],
                "anchor_mm": _mm(int(item["anchor_u"])),
                "start_mm": _mm(int(item["start_u"])),
                "end_mm": _mm(int(item["end_u"])),
            }
            for item in dividers
        ],
        "cavities": [
            {
                "index": item["index"],
                "clear_width_mm": _mm(int(item["clear_u"])),
                "status": item["status"],
            }
            for item in cavities
        ],
        "panels": [
            {
                "id": item["id"],
                "segments_mm": [_mm(int(value)) for value in item["segment_u"]],
                "break_widths_mm": [
                    _mm(int(value)) for value in item["break_u"]
                ],
            }
            for item in panels
        ],
        "findings": findings,
    }


def _pairs(value: Any, n_doors: int) -> list[tuple[int, int]]:
    parsed: list[tuple[int, int]] = []
    seen: set[int] = set()
    for item in _sequence(value, "pairs"):
        if (
            isinstance(item, (str, bytes))
            or not isinstance(item, Sequence)
            or len(item) != 2
        ):
            raise ValueError("each pair must be two door indexes")
        left = _integer(item[0], "pair door")
        right = _integer(item[1], "pair door")
        if right != left + 1:
            raise ValueError("paired doors must be adjacent")
        if left < 0 or right >= n_doors:
            raise ValueError("pair is outside the door row")
        if left in seen or right in seen:
            raise ValueError("a door is in more than one pair")
        seen.add(left)
        seen.add(right)
        parsed.append((left, right))
    return parsed


def _sequence(value: Any, name: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{name} must be a list")
    return list(value)


def _reject_unknown(
    value: Mapping[str, Any],
    allowed: frozenset[str],
    label: str,
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"unknown {label} fields: {', '.join(unknown)}")


def _units(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be finite")
    return int(round(number * _UM))


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _mm(units: int) -> float:
    return units / _UM


def _worse(current: str, incoming: str) -> str:
    rank = {"ok": 0, "assumption": 1, "blocked": 2}
    if rank[incoming] > rank[current]:
        return incoming
    return current


def _loss(
    code: str,
    status: str,
    message: str,
    proceed_loss: str,
    stop_loss: str,
) -> dict[str, str]:
    return {
        "code": code,
        "status": status,
        "message": message,
        "proceed_loss": proceed_loss,
        "stop_loss": stop_loss,
    }
