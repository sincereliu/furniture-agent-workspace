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

**改动记录**

- 2026-10-16：给每块板加了 `grain_axis`（顺纹方向），于是四份摘要全变。
  已核对**只多了这个字段**：把 `grain_axis` 递归摘掉之后，四份摘要与改之前的基线
  逐字相同（尺寸、位置、接触、装配一个都没动）。加它是因为顺纹方向是板件的属性，
  要能按订单改、并随板件一起冻结；默认值由板件类型在 `grain_rules.GRAIN_BY_TYPE` 给。
- 2026-10-19：门板多了 `door_hinge_side`（铰链侧），于是四份摘要全变（四例都带对开门）。
  已核对**只多了这个字段**：把 `door_hinge_side` 递归摘掉之后，四份摘要与改之前的基线
  逐字相同（核对脚本见提交说明）。加它是因为"门往哪边开"是**设计决定**，该由板件阶段
  给并随板件冻结，而不是制造阶段按门序猜；对开腔由几何定（左 left、右 right），
  单开腔由提案给，定不下来的留空。
- 2026-10-20：spec 多了板幅 `sheet_width_mm` / `sheet_length_mm`（1220×2440 或
  1220×2745，工艺卡默认前者），于是四份摘要全变。已核对**只多了这两个字段**：
  把这两个键递归摘掉之后，四份摘要与改之前的基线逐字相同
  （`temp/verify_baseline_delta.py`）。加它是因为"板件两个平面尺寸进不进得去料"
  是判 error 的前提，不能由校验临时猜一档。这一步没有动任何板件尺寸、位置与接触：
  四个用例都没有中立板，背板仍是一整块 `back_panel`。
- 2026-10-24：**抽屉原先没有被基线覆盖**（四个用例都是门柜）。改盒高口径
  （盒高 = 格高 − 上下间隙，按 10 取整；盒深取抽芯档，后缝是结果）时补了一条
  三抽用例 `drawers_three`，因此 `_BASELINE` 多一项。**原有四份摘要逐字不变**——
  抽屉与门柜互斥，抽屉改动不影响门柜产出。
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
#: 2026-10-20 因新增板幅 `sheet_width_mm` / `sheet_length_mm` 重新生成（见头部"改动记录"）。
_BASELINE = {
    "single_double_door": "bab007ef56d9b6ad2d51d9f4cc5666fb35c30c581c61cc8bdac0683e55903b9f",
    "wardrobe_with_shelves": "ceb228128880bdda65cadd424386b51ea66f514c993884c1a6d30b06778b29e2",
    "wall_cabinet": "15a9008422c571b78b8526d96f4f666dc8d0bc05a0d6ad31a1f7aecee780e724",
    "two_cabinets": "68075a34b9f01e9c807d9be13a95111e9dc00b266582806acd6e524463c20a2e",
    # 2026-10-24 新增（不是重建）：抽屉原先没有基线用例，盒高改口径后补一条。
    "drawers_three": "29797716068723a4a379862e7eea934f5c9008e38d79f2bd457afce0d69e0b0c",
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
    # 抽屉三抽：盒高按格高取整、盒深取抽芯档、后缝是结果。这个案例自带覆盖参数，
    # 因为后缝下限要求提案给一个正数（三节轨 > 0）。
    "drawers_three": {
        "rooms": [_room([_item("drawer_cab")])],
        "parameters": "floor_cabinet",
        "overrides": {
            "n_doors": 0,
            "shelves": [],
            "top_gap_mm": 0.0,
            "drawer_count": 3,
            "drawer_back_clearance": 20.0,
        },
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
            **panel_parameters(case["parameters"], **case.get("overrides", {})),
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
