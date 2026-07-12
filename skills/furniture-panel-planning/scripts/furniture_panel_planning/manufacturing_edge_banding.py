"""封边规则引擎 — 根据板件类型判断每块板哪些边需要封边。"""

from __future__ import annotations

from typing import Dict

# 默认封边规则（硬编码兜底值，不依赖外部 YAML 也可运行）
DEFAULT_EDGE_RULES: Dict[str, Dict[str, str]] = {
    "side":         {"前": "ABS 1.0mm同色", "上": "ABS 1.0mm同色", "下": "ABS 1.0mm同色"},
    "top":          {"前": "ABS 1.0mm同色"},
    "bottom":       {"前": "ABS 1.0mm同色"},
    "fixed_shelf":  {"前": "ABS 1.0mm同色"},
    "movable_shelf":{"前": "ABS 1.0mm同色"},
    "divider":      {"前": "ABS 1.0mm同色"},
    "toe_kick":     {},
    "back":         {},
    "door":         {"四边": "ABS 1.0mm白色"},
}


def load_edge_rules(yaml_path: str | None = None) -> Dict[str, Dict[str, str]]:
    """从 YAML 配置文件加载封边规则。

    Args:
        yaml_path: edge_banding.yaml 路径，None 则使用默认规则

    Returns:
        {panel_type: {edge: material}, ...}
    """
    if yaml_path is None:
        return dict(DEFAULT_EDGE_RULES)

    try:
        import yaml  # type: ignore
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("edge_banding", DEFAULT_EDGE_RULES)
    except Exception:
        return dict(DEFAULT_EDGE_RULES)


def get_edge_banding(
    panel_type: str,
    rules: Dict[str, Dict[str, str]] | None = None,
) -> Dict[str, str]:
    """获取某类板件的封边规则。

    Args:
        panel_type: 板件类型（side / top / bottom / shelf / back / door / toe_kick）
        rules: 封边规则字典，None 则使用默认规则

    Returns:
        {边: 封边材料, ...}，如 {"前": "ABS 1.0mm同色", "四边": "ABS 1.0mm白色"}
    """
    if rules is None:
        rules = DEFAULT_EDGE_RULES
    return dict(rules.get(panel_type, {}))
