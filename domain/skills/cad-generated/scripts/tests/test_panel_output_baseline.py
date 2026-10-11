"""板件产出的绝对基线：老输入的结果不许被顺手改坏。

**为什么需要它**

规则断言（`test_panel_rule_contracts` 等）只守住"我预期会变的地方"；这份快照守住
"我没预期会变的地方"。动板件、制造这类**结构性代码**之前先跑它：

- 改了板件代码，老工程的产出跟着变了 → **红**，先判断是不是故意的；
- 意外变化：改代码，**不要改基线**；
- 故意变化（例：门宽算法换口径）：按下面步骤重新生成基线，并在提交信息里写清
  "什么变了、为什么变了"——没有这句话的基线更新等于把安全网拆了。

**重新生成**

跑 `temp/capture_panel_baseline.py`（或看本条测试 FAIL 时打印的实际摘要），
把 `_BASELINE` 里对应的值换成新的。

**覆盖**：单柜双门 / 带层板的衣柜 / 吊柜 / 两台柜的工程。
下游（制造、特征树、CAD、交付）由板件派生，不在这里单独钉。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_workflow.workflow_digest import stable_digest
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import WorkflowStage
from furniture_workflow.workflow_store import JsonProjectStore

from panel_fixtures import panel_parameters
from workflow_test_support import confirm_through

#: 冻结的板件产出摘要。改动它之前先读文件头部的"重新生成"一节。
_BASELINE = {
    "single_double_door": "16bbd676f15a289d6d15bb6342ae86ddcdf970d803b606ca58209990ffd6c5e5",
    "wardrobe_with_shelves": "30aa5f2cb906e35fb8b29d569c438c4c36e90439fbc7814c637290be4a67b82b",
    "wall_cabinet": "950c0f88ccbabbd742464daacfe3c733406c8caefd50f2d3da73296750c2fb16",
    "two_cabinets": "5fd88a69b61c4f70d20edbc02f7d8feca94af4c453038df6d834f68409b0091b",
}


def _room(items: list[dict]) -> dict:
    return {"id": "room", "name": "房间", "width_mm": 3600, "depth_mm": 3000,
            "height_mm": 2800, "items": items}


def _item(item_id: str, *, width: float = 800, depth: float = 600,
          height: float = 1000, category: str = "floor_cabinet",
          host_wall: str = "north", origin_z_mm: float = 0) -> dict:
    return {
        "id": item_id,
        "category": "cabinet",
        "furniture_category": category,
        "width": width,
        "depth": depth,
        "height": height,
        "placement": {"mode": "wall", "host_wall": host_wall,
                      "origin_z_mm": origin_z_mm},
    }


CASES: dict[str, dict] = {
    "single_double_door": {
        "rooms": [_room([_item("cabinet_1")])],
        "parameters": "floor_cabinet",
    },
    "wardrobe_with_shelves": {
        "rooms": [_room([_item("wardrobe", width=1200, height=2400)])],
        "parameters": "floor_cabinet",
    },
    "wall_cabinet": {
        "rooms": [_room([_item("hang", width=900, depth=350, height=700,
                               category="wall_cabinet", origin_z_mm=1500)])],
        "parameters": "wall_cabinet",
    },
    "two_cabinets": {
        "rooms": [_room([_item("cabinet_1"),
                         _item("cabinet_2", width=900, host_wall="east")])],
        "parameters": "floor_cabinet",
    },
}


def panel_digest(case: dict) -> str:
    """跑一个工程到板件阶段，返回 `panel_plan` 的稳定摘要。"""
    with tempfile.TemporaryDirectory() as tmp:
        store = JsonProjectStore(Path(tmp) / "store")
        orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT, project_store=store
        )
        spec = {
            "rooms": json.loads(json.dumps(case["rooms"])),
            "movable_shelf_connector": "two_in_one",
            "door_hinge_side": None,
            **panel_parameters(case["parameters"]),
        }
        result = confirm_through(
            orchestrator, "基线", spec, through_stage=WorkflowStage.PANELS_PLANNED
        )
        return stable_digest(result.revision.stage_outputs["panel_plan"])


class PanelOutputBaselineTests(unittest.TestCase):
    def test_legacy_panel_output_matches_the_frozen_baseline(self) -> None:
        """老工程的板件产出必须与冻结基线一致。

        红了先判断：**意外变化就改代码，故意变化才重新生成基线**（并在提交信息里
        写清为什么）。不要为了让测试变绿而直接替换摘要。
        """
        actual = {name: panel_digest(case) for name, case in CASES.items()}
        for name, expected in _BASELINE.items():
            with self.subTest(case=name):
                self.assertEqual(
                    actual[name],
                    expected,
                    f"{name} 的板件产出变了。若是故意改动，按本文件头部步骤重新生成基线，"
                    f"并写明原因；实际摘要 = {actual[name]}",
                )

    def test_the_baseline_is_deterministic(self) -> None:
        """同一份输入跑两次摘要必须一样——不然基线本身没有意义。"""
        first = panel_digest(CASES["two_cabinets"])
        second = panel_digest(CASES["two_cabinets"])
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
