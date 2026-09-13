"""材料目录加载器。

材料目录是材质的单一真源，分两个独立维度：
- substrate：基材（饰面下的芯材种类）
- surface：表面（颜色__表面处理__纹理）

键 = 稳定代号（引用用），name = 可读全名（可改）。校验 = 查表，
不做别名/同义词映射，不按规则派生组合（组合当前为显式枚举）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

_CATALOG_PATH = Path(__file__).resolve().parent / "materials_catalog.yaml"

_catalog_cache: Dict[str, Any] | None = None


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader，但在同一映射里出现重复键时报错（落实「键唯一」）。"""


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"materials_catalog.yaml 出现重复键: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _load_raw() -> Dict[str, Any]:
    global _catalog_cache
    if _catalog_cache is None:
        with open(_CATALOG_PATH, encoding="utf-8") as f:
            _catalog_cache = yaml.load(f, Loader=_UniqueKeyLoader) or {}
    return _catalog_cache


def substrate_keys() -> list[str]:
    """基材维度所有合法键。"""
    section = _load_raw().get("substrate", {})
    return list(section) if isinstance(section, dict) else []


def surface_keys() -> list[str]:
    """表面维度所有合法键。"""
    section = _load_raw().get("surface", {})
    return list(section) if isinstance(section, dict) else []


def substrate_name(key: str) -> str:
    """基材键的可读全名；未知键返回空串。"""
    entry = _load_raw().get("substrate", {}).get(key)
    return str(entry.get("name", "")) if isinstance(entry, dict) else ""


def surface_name(key: str) -> str:
    """表面键的可读全名；未知键返回空串。"""
    entry = _load_raw().get("surface", {}).get(key)
    return str(entry.get("name", "")) if isinstance(entry, dict) else ""
