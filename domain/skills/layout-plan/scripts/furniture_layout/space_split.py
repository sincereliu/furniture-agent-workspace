"""沿墙铺满：一段墙长拆成若干台柜子。

一台的宽度上限是该柜类两扇门的门宽上限。放得进一台就是一台；
放不下就分成两台、三台……沿墙接开，宽度加起来等于这段墙。
"""

from __future__ import annotations

from math import ceil, isfinite


def unit_widths(span_mm: float, cap_mm: float) -> tuple[float, ...]:
    """把一段墙长拆成若干台的宽度。每台不超过上限，加起来等于这段墙。

    多出来的毫米放在远端那几台，所以前面几台一样宽，最后一台不会超过上限。
    """
    if isinstance(span_mm, bool) or not isinstance(span_mm, (int, float)) or not isfinite(span_mm):
        raise ValueError("wall span must be a finite number")
    if isinstance(cap_mm, bool) or not isinstance(cap_mm, (int, float)) or not isfinite(cap_mm):
        raise ValueError("unit width cap must be a finite number")
    if span_mm <= 0:
        raise ValueError("wall span must be positive")
    if cap_mm <= 0:
        raise ValueError("unit width cap must be positive")
    if span_mm <= cap_mm:
        return (float(span_mm),)
    count = int(ceil(span_mm / cap_mm))
    if abs(span_mm - round(span_mm)) <= 1e-6:
        total = int(round(span_mm))
        base, extra = divmod(total, count)
        widths = [float(base)] * count
        for index in range(count - extra, count):
            widths[index] += 1.0
        return tuple(widths)
    share = span_mm / count
    return tuple(share for _ in range(count))


__all__ = ["unit_widths"]
