"""柜内结构评估的审查清单：腔 / 缝 / 段 / findings 要能被核对。

清单显示的是**评估结果**（还没写进板件），所以：
- 标题底下必须写明这一点，免得读的人当成板件表；
- 只显示评估器算得了的（宽度方向），不编腔高、腔深；
- 凑整口径保持中立：A（某条缝吸收零头）与 B（零头在边距）两种都要显示得出来。
"""

from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_panel_planning.interior_structure import evaluate_interior
from furniture_panel_planning.panel_review import format_interior_review_markdown

from furniture_workflow.agent_tools import FurnitureToolSession
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_store import JsonProjectStore


def twelve_hundred() -> dict:
    """1200 柜：中立板 + 1 单开 + 1 组对开 + 顶板按中立板断开、踢脚运输断开。"""
    return evaluate_interior(
        {
            "width_mm": 1200,
            "n_doors": 3,
            "margin_mm": 1.5,
            "side_thickness_mm": 18,
            "pairs": [[1, 2]],
            "dividers": [
                {"id": "d1", "seam_index": 0, "thickness_mm": 18}
            ],
            "panels": [
                {"id": "top", "start_mm": 0, "end_mm": 1200},
                {"id": "toe", "start_mm": 0, "end_mm": 1200},
            ],
            "breaks": [
                {"panel_id": "top", "align_divider": "d1"},
                {"panel_id": "toe", "at_mm": 600, "reason": "transport"},
            ],
            "cavity_needs": [
                {"cavity_index": 0, "grade": "confirmed", "min_clear_width_mm": 500}
            ],
            "min_segment_mm": 100,
            "min_segment_grade": "confirmed",
        }
    )


class InteriorReviewMarkdownTests(unittest.TestCase):
    def test_it_shows_doors_seams_dividers_cavities_and_segments(self) -> None:
        markdown = format_interior_review_markdown(twelve_hundred())

        self.assertIn("还没写进板件", markdown, "要写明这是评估结果")
        self.assertIn("正面 3 扇门 · 每扇 397 / 397 / 397", markdown)
        self.assertIn("成对门 1–2", markdown)
        self.assertIn("缝 400（3）", markdown)
        self.assertIn("缝 800（3）", markdown)
        self.assertIn("边距 左 1.5 / 右 1.5", markdown)
        self.assertIn("| d1 | 缝 0（center） | 400 | 391~409 |", markdown)
        self.assertIn("| 0 | 373 | blocked |", markdown)
        self.assertIn("| 1 | 773 | ok |", markdown)
        self.assertIn("| top | 2 | 391 / 791 | 18 |", markdown)
        self.assertIn("| toe | 2 | 600 / 600 | 0 |", markdown)

    def test_it_reports_findings_with_both_losses(self) -> None:
        markdown = format_interior_review_markdown(twelve_hundred())
        self.assertIn("**blocked** cavity_fit", markdown)
        self.assertIn("继续的损失：按这个净空下料，腔放不下", markdown)
        self.assertIn("停下的损失：这一轮没有可审查的板件", markdown)
        self.assertIn("总体：blocked（先别下料）", markdown)

    def test_it_does_not_invent_cavity_height_or_depth(self) -> None:
        """评估器只算宽度：腔高、腔深不能出现在清单里。"""
        markdown = format_interior_review_markdown(twelve_hundred())
        self.assertIn("腔高与腔深由层板、用途规则另算", markdown)
        self.assertNotIn("× 2314", markdown)

    def test_a_gap_that_absorbed_rounding_is_marked(self) -> None:
        """A 口径：某条缝吸收了凑整零头（3.0 → 3.4）时要标出来。"""
        report = {
            "blocked": False,
            "doors": {
                "door_widths_mm": [339.8, 339.8],
                "pairs": [[0, 1]],
                "left_margin_mm": 1.5,
                "right_margin_mm": 1.5,
                "door_starts_mm": [1.5, 344.3],
                "gaps_mm": [3.4],
                "seam_centers_mm": [343.2],
            },
            "dividers": [],
            "cavities": [],
            "panels": [],
            "findings": [],
        }
        markdown = format_interior_review_markdown(report)
        self.assertIn("缝 343.2（3.4） ← 吸收凑整零头", markdown)
        self.assertIn("无成对门" if False else "成对门 0–1", markdown)

    def test_rounding_left_on_a_margin_is_marked(self) -> None:
        """B 口径：零头落在右边距时要标出来。"""
        report = {
            "blocked": False,
            "doors": {
                "door_widths_mm": [340, 339],
                "pairs": [],
                "left_margin_mm": 1.5,
                "right_margin_mm": 1.9,
                "door_starts_mm": [1.5, 344.5],
                "gaps_mm": [3.0],
                "seam_centers_mm": [343.0],
            },
            "dividers": [],
            "cavities": [],
            "panels": [],
            "findings": [],
        }
        markdown = format_interior_review_markdown(report)
        self.assertIn("边距 左 1.5 / 右 1.9 ← 零头在边距", markdown)
        self.assertIn("缝 343（3）", markdown, "基值缝不标零头")
        self.assertIn("总体：没有 blocked", markdown)

    def test_empty_structure_says_none(self) -> None:
        report = {
            "blocked": False,
            "doors": {
                "door_widths_mm": [800],
                "pairs": [],
                "left_margin_mm": 1.5,
                "right_margin_mm": 1.5,
                "door_starts_mm": [1.5],
                "gaps_mm": [],
                "seam_centers_mm": [],
            },
            "dividers": [],
            "cavities": [],
            "panels": [],
            "findings": [],
        }
        markdown = format_interior_review_markdown(report)
        self.assertIn("无内缝（单扇门）", markdown)
        self.assertIn("## 中立板\n\n无", markdown)
        self.assertIn("## 分段\n\n无", markdown)


class InteriorReviewToolTests(unittest.TestCase):
    """工具面要把清单排好一起给出来，不让调用方拿 JSON 自己拼格式。"""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.session = FurnitureToolSession(
            FurnitureOrchestrator(
                workspace_root=WORKSPACE_ROOT,
                project_store=JsonProjectStore(self.temporary.name),
            )
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_the_tool_reply_carries_the_ready_to_show_checklist(self) -> None:
        created = self.session.call(
            "furniture_create_project",
            {
                "name": "清单",
                "rooms": [
                    {
                        "id": "room",
                        "name": "房间",
                        "width_mm": 3600,
                        "depth_mm": 3000,
                        "height_mm": 2800,
                        "items": [
                            {
                                "id": "wardrobe",
                                "category": "cabinet",
                                "furniture_category": "floor_cabinet",
                                "width": 1200,
                                "depth": 600,
                                "height": 2400,
                                "placement": {"mode": "wall", "host_wall": "north"},
                            }
                        ],
                    }
                ],
            },
        )
        sized = self.session.call(
            "furniture_evaluate_interior",
            {
                "project_id": created["project"]["id"],
                "interior": {
                    "width_mm": 1200,
                    "n_doors": 3,
                    "margin_mm": 1.5,
                    "side_thickness_mm": 18,
                    "pairs": [[1, 2]],
                    "dividers": [{"id": "d1", "seam_index": 0, "thickness_mm": 18}],
                    "panels": [{"id": "top", "start_mm": 0, "end_mm": 1200}],
                    "breaks": [{"panel_id": "top", "align_divider": "d1"}],
                },
            },
        )

        self.assertTrue(sized["ok"], sized)
        review = sized["interior_review"]
        self.assertIn("还没写进板件", review)
        self.assertIn("正面 3 扇门 · 每扇 397 / 397 / 397", review)
        self.assertIn("| d1 | 缝 0（center） | 400 | 391~409 |", review)
        self.assertIn("| top | 2 | 391 / 791 | 18 |", review)
        self.assertIn("总体：没有 blocked", review)


if __name__ == "__main__":
    unittest.main()
