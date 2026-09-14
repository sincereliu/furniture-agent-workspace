"""封边皮目录加载器。

封边皮是材质的补充单一真源，两个独立维度：
- material：封边材质（abs/pvc/laser，决定工艺）
- thickness：封边皮自身厚度（0.8/1.0/2.0mm）

宽度（= 板件厚度）与颜色（= 同色，来自 surface 颜色段）是派生属性，不进目录。
键 = 稳定代号（引用用），name = 可读全名（可改）。校验 = 查表。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .catalog_loader import load_yaml

_CATALOG_PATH = Path(__file__).resolve().parent / "edge_banding_catalog.yaml"

_catalog_cache: Dict[str, Any] | None = None


def _load_raw() -> Dict[str, Any]:
    global _catalog_cache
    if _catalog_cache is None:
        _catalog_cache = load_yaml(_CATALOG_PATH)
    return _catalog_cache


def material_keys() -> list[str]:
    """封边材质所有合法键。"""
    section = _load_raw().get("material", {})
    return list(section) if isinstance(section, dict) else []


def thickness_keys() -> list[str]:
    """封边皮厚度所有合法键。"""
    section = _load_raw().get("thickness", {})
    return list(section) if isinstance(section, dict) else []


def material_name(key: str) -> str:
    """封边材质键的可读全名；未知键返回空串。"""
    entry = _load_raw().get("material", {}).get(key)
    return str(entry.get("name", "")) if isinstance(entry, dict) else ""


def thickness_mm(key: str) -> float:
    """封边皮厚度键对应的毫米值；未知键返回 0.0。"""
    entry = _load_raw().get("thickness", {}).get(key)
    return float(entry.get("value_mm", 0.0)) if isinstance(entry, dict) else 0.0
