"""柜体结构模板 — 蓝图驱动的通用构造器。

通过 build_from_blueprint() 读取 FurnitureSpec 参数，不再需要子类。
"""

from furniture_planner.templates.base import build_from_blueprint

__all__ = ["build_from_blueprint"]