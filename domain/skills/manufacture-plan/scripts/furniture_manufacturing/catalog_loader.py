"""YAML 目录加载公共工具。

所有单一真源目录（材料、封边皮等）共用：重复键检测 + 加载。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


class UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader，但在同一映射里出现重复键时报错（落实「键唯一」）。"""


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"目录出现重复键: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_yaml(path: Path) -> Dict[str, Any]:
    """加载 yaml 目录并拒绝重复键。"""
    with open(path, encoding="utf-8") as f:
        return yaml.load(f, Loader=UniqueKeyLoader) or {}
