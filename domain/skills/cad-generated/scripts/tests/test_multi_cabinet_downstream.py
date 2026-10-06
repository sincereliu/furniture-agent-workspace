"""多柜下游：布局里摆了几台柜，制造与特征树就该覆盖几台。

以前下游只读 `cabinets[0]`（主柜），所以拆成三台只有一台能走到车间。
本文件盯住**制造 + 特征树**这一刀；CAD 与交付清单的逐柜还没做
（见 [编排未落地需求](../../references/backlog.md)），做完在同一个文件里补齐。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_delivery_validation.validation import validate_delivery
from furniture_manufacturing.manufacturing_handoff import (
    cabinets_from_manufacturing,
    merged_manufacturing_view,
)
from furniture_orchestrator_test_support import fake_orchestrator
from furniture_panel_planning.cabinet_envelope import CabinetEnvelope
from furniture_panel_planning.panel_pipeline import plan_panel_stage
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import WorkflowStage
from furniture_workflow.workflow_store import JsonProjectStore
from panel_fixtures import _fill_shelves, cabinet_envelope, panel_parameters
from workflow_test_support import confirm_through, manufactured_boms


def two_cabinet_rooms() -> list[dict]:
    """一个房间里两台柜：宽度不同、并排摆，好认出哪份 BOM 属于哪台。"""
    return [
        {
            "id": "room",
            "name": "测试房间",
            "width_mm": 4000,
            "depth_mm": 3000,
            "height_mm": 3200,
            "items": [
                {
                    "id": "cabinet_1",
                    "label": "cabinet_1",
                    "category": "柜体",
                    "furniture_category": "floor_cabinet",
                    "width": 800,
                    "depth": 600,
                    "height": 1000,
                    "placement": {
                        "mode": "wall",
                        "host_wall": "north",
                        "origin_z_mm": 0,
                    },
                },
                {
                    "id": "cabinet_2",
                    "label": "cabinet_2",
                    "category": "柜体",
                    "furniture_category": "floor_cabinet",
                    "width": 600,
                    "depth": 600,
                    "height": 1000,
                    "placement": {
                        "mode": "wall",
                        "host_wall": "north",
                        "origin_z_mm": 0,
                    },
                },
            ],
        }
    ]


def two_cabinet_spec() -> dict:
    return {
        "rooms": two_cabinet_rooms(),
        "movable_shelf_connector": "two_in_one",
        "door_hinge_side": None,
        **panel_parameters("floor_cabinet"),
    }


class MultiCabinetDownstreamTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = JsonProjectStore(Path(self.temporary.name) / "store")
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=self.store,
        )
        self.addCleanup(self.temporary.cleanup)

    def test_every_cabinet_gets_its_own_bom_and_feature_tree(self) -> None:
        result = confirm_through(
            self.orchestrator,
            "两台柜",
            two_cabinet_spec(),
            through_stage=WorkflowStage.FEATURE_TREE_PLANNED,
        )
        outputs = result.revision.stage_outputs

        manufactured = cabinets_from_manufacturing(
            outputs[WorkflowStage.MANUFACTURING_PLANNED.value]
        )
        self.assertEqual([item["id"] for item in manufactured], ["cabinet_1", "cabinet_2"])
        for item in manufactured:
            panels = item["bom"]["panels"]
            self.assertTrue(panels, item["id"])
            self.assertTrue(
                all(panel["label"].startswith(f"{item['id']}__") for panel in panels),
                f"{item['id']} 的 BOM 里混进了别台的板件",
            )
        # 尺寸跟着各自的包络走——不是把主柜那份复制一遍。
        self.assertEqual(manufactured[0]["bom"]["width"], 800.0)
        self.assertEqual(manufactured[1]["bom"]["width"], 600.0)

        trees = outputs[WorkflowStage.FEATURE_TREE_PLANNED.value]["cabinets"]
        self.assertEqual([item["id"] for item in trees], ["cabinet_1", "cabinet_2"])
        self.assertTrue(all(item["tree"] for item in trees))
        # 特征树只在这一处（以前还有个主柜那棵的镜像字段，已删）。
        self.assertFalse(hasattr(result.revision, "feature_tree"))

    def test_stage_validation_covers_every_cabinet(self) -> None:
        result = confirm_through(
            self.orchestrator,
            "逐柜验收",
            two_cabinet_spec(),
            through_stage=WorkflowStage.MANUFACTURING_PLANNED,
        )
        reports = [
            report
            for report in result.revision.validations
            if report.stage == WorkflowStage.MANUFACTURING_PLANNED.value
        ]
        self.assertTrue(reports)
        self.assertTrue(all(report.passed for report in reports))

    def test_a_broken_cabinet_fails_the_stage_by_name(self) -> None:
        """一台不合格就整阶段不合格，且问题里点名是哪一台。"""
        result = confirm_through(
            self.orchestrator,
            "点名",
            two_cabinet_spec(),
            through_stage=WorkflowStage.MANUFACTURING_PLANNED,
        )
        edited = deepcopy(
            result.revision.stage_outputs[WorkflowStage.MANUFACTURING_PLANNED.value]
        )
        self.assertEqual(len(edited["cabinets"]), 2)
        edited["cabinets"][1]["bom"]["readiness"] = "claimed_ready"
        revision = self.orchestrator.revise_stage_output(
            result.project,
            WorkflowStage.MANUFACTURING_PLANNED,
            edited,
        )
        self.orchestrator.confirm_stage(
            result.project, WorkflowStage.MANUFACTURING_PLANNED
        )
        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        messages = [issue.message for issue in revision.validations[-1].issues]
        self.assertIn("INVALID_MANUFACTURING_READINESS", {
            issue.code for issue in revision.validations[-1].issues
        })
        self.assertTrue(
            any(message.startswith("cabinet_2: ") for message in messages),
            messages,
        )


class EveryCabinetReachesTheShopTests(unittest.TestCase):
    """验收标准：一个两台柜的项目，两台都出现在制造 / 特征树 / CAD / **交付清单**里。

    这是「多柜真的能用」的验收线——以前只有主柜能走到车间。
    """

    CABINET_KINDS = {
        "bom",
        "cad_source",
        "drilled_holes",
        "drilled_holes_glb",
        "drilled_holes_step",
        "drilled_holes_step_glb",
        "six_side_drill_xml",
        "step",
        "viewer_topology",
    }

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = JsonProjectStore(self.root / "store")
        self.orchestrator = fake_orchestrator(self.root, project_store=self.store)
        self.addCleanup(self.temporary.cleanup)

    def _through_delivery(self):
        return confirm_through(
            self.orchestrator,
            "两台柜到车间",
            two_cabinet_spec(),
            through_stage=WorkflowStage.DELIVERY_VALIDATED,
            output_root=str(self.root / "generated"),
            generate_cad=True,
        )

    def test_both_cabinets_get_a_full_set_of_artifacts(self) -> None:
        result = self._through_delivery()
        revision = result.revision
        self.assertEqual(revision.workflow.current, WorkflowStage.DELIVERY_VALIDATED)
        self.assertEqual(len(result.cabinets), 2)
        self.assertEqual([bridge.status for bridge in result.bridges], ["ok", "ok"])

        kinds_by_cabinet: dict[str, set[str]] = {"cabinet_1": set(), "cabinet_2": set()}
        for artifact in revision.manifest.artifacts:
            cabinet_id = str(artifact.metadata.get("cabinet_id") or "")
            if cabinet_id in kinds_by_cabinet:
                kinds_by_cabinet[cabinet_id].add(artifact.kind)
        for cabinet_id, kinds in kinds_by_cabinet.items():
            self.assertEqual(kinds, self.CABINET_KINDS, cabinet_id)

        cad = revision.stage_outputs[WorkflowStage.CAD_GENERATED.value]
        self.assertEqual(
            [entry["id"] for entry in cad["cabinets"]], ["cabinet_1", "cabinet_2"]
        )
        self.assertTrue(revision.stage_outputs["delivery_validated"]["passed"])

    def test_delivery_notices_when_a_planned_cabinet_is_missing(self) -> None:
        """少了一台的产物 → 交付验证必须报出来（逐柜之前它照样通过）。"""
        result = self._through_delivery()
        revision = result.revision
        revision.manifest.artifacts = [
            artifact
            for artifact in revision.manifest.artifacts
            if not (
                artifact.kind == "step"
                and artifact.metadata.get("cabinet_id") == "cabinet_2"
            )
        ]
        report = validate_delivery(
            revision.manifest,
            source_revision_id=revision.id,
            stage_outputs=revision.stage_outputs,
            approved_stages=revision.approved_stages,
            stage_validations=revision.validations,
            stage_analyses=revision.stage_analyses,
        )
        self.assertFalse(report.passed)
        issue = next(
            item for item in report.issues if item.code == "MISSING_CABINET_ARTIFACT"
        )
        self.assertIn("cabinet_2", issue.message)
        self.assertIn("step", issue.message)


class PerCabinetParametersTests(unittest.TestCase):
    """**逐柜参数**：一份共享提案 + 按柜覆盖，设定跟着各自的柜走。

    以前是一份参数套所有柜（只换柜名），所以"这格挂衣、那格抽屉"表达不了；
    改板件产物之后更糟——会把第一台的 spec 抄成所有柜的参数。
    """

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = JsonProjectStore(Path(self.temporary.name) / "store")
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=self.store,
        )
        self.addCleanup(self.temporary.cleanup)

    def test_each_cabinet_keeps_its_own_proposal_through_the_chain(self) -> None:
        spec = two_cabinet_spec()
        spec["panel_cabinets"] = {"cabinet_2": {"n_doors": 1}}
        # 单门必须明确铰链方向——这类选项也是**按柜**给的，共享一份表达不了。
        spec["manufacturing_cabinets"] = {
            "cabinet_2": {"parameters": {"door_hinge_side": "left"}}
        }
        result = confirm_through(
            self.orchestrator,
            "逐柜参数",
            spec,
            through_stage=WorkflowStage.FEATURE_TREE_PLANNED,
        )
        cabinets = result.revision.stage_outputs[
            WorkflowStage.PANELS_PLANNED.value
        ]["cabinets"]
        self.assertEqual(
            [cabinet["spec"]["n_doors"] for cabinet in cabinets], [2, 1]
        )
        # 下游逐柜：每台的 BOM 也照着**自己**那份设定走。
        boms = manufactured_boms(result.revision)
        door_counts = [
            len([panel for panel in bom["panels"] if panel["panel_type"] == "door"])
            for bom in boms
        ]
        self.assertEqual(door_counts, [2, 1])

    def test_a_revised_spec_stays_with_its_own_cabinet(self) -> None:
        """改第二台的板件产物 → 覆盖只落在第二台，不许抄给第一台。"""
        result = confirm_through(
            self.orchestrator,
            "逐柜改",
            two_cabinet_spec(),
            through_stage=WorkflowStage.PANELS_PLANNED,
        )
        edited = deepcopy(
            result.revision.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        )
        edited["cabinets"][1]["spec"]["n_doors"] = 1
        revision = self.orchestrator.revise_stage_output(
            result.project,
            WorkflowStage.PANELS_PLANNED,
            edited,
        )
        cabinets = revision.stage_inputs["panels"]["cabinets"]
        self.assertEqual(cabinets["cabinet_2"]["n_doors"], 1)
        self.assertEqual(cabinets["cabinet_1"]["n_doors"], 2)


class PerCabinetProposalShapeTests(unittest.TestCase):
    """覆盖的形状规则：柜名必须认识、几何不许越界、参数不许乱塞。"""

    def _envelopes(self):
        return (
            cabinet_envelope("cabinet_1", width=800, height=900),
            cabinet_envelope("cabinet_2", width=600, height=900),
        )

    def _base(self) -> dict:
        overrides = {"shelf_count": 2}
        _fill_shelves(overrides, wall=False, height=900)
        return panel_parameters("floor_cabinet", **overrides)

    def test_overrides_win_field_by_field(self) -> None:
        plan = plan_panel_stage(
            self._envelopes(),
            {"parameters": self._base(), "cabinets": {"cabinet_2": {"n_doors": 1}}},
        )
        self.assertEqual(
            [cabinet["spec"]["n_doors"] for cabinet in plan["cabinets"]], [2, 1]
        )

    def test_unknown_or_illegal_overrides_are_rejected(self) -> None:
        base = self._base()
        with self.assertRaisesRegex(ValueError, "unknown cabinet id: cabinet_9"):
            plan_panel_stage(
                self._envelopes(),
                {"parameters": base, "cabinets": {"cabinet_9": {"n_doors": 1}}},
            )
        with self.assertRaisesRegex(ValueError, "envelope-owned fields: width"):
            plan_panel_stage(
                self._envelopes(),
                {"parameters": base, "cabinets": {"cabinet_2": {"width": 700}}},
            )
        with self.assertRaisesRegex(ValueError, "cabinets must be an object"):
            plan_panel_stage(
                self._envelopes(), {"parameters": base, "cabinets": []}
            )


class PerCabinetAnalysisTests(unittest.TestCase):
    """旁路分析也必须**指名哪一台**：审计逐台跑，择优指名一台、落地只改那一台。

    以前两者都默默取第一台——多柜工程里"对 2 号柜做优化、算的却是 1 号柜"。
    """

    # 用一对**会互相让步**的目标（材料体积 vs 复杂度），前沿里才会出现两个不同方案；
    # 只比"料厚 18/22"时 22 厘在两项上都更差，会被支配掉，前沿只剩一个。
    OPTIMIZATION = {
        "engine": "exact",
        "variables": {"back_mount": ["groove", "cover"]},
        "objectives": ["material_volume_m3", "complexity_score"],
    }

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = JsonProjectStore(Path(self.temporary.name) / "store")
        self.orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT,
            project_store=self.store,
        )
        self.addCleanup(self.temporary.cleanup)
        self.project = confirm_through(
            self.orchestrator,
            "分析",
            two_cabinet_spec(),
            through_stage=WorkflowStage.PANELS_PLANNED,
        ).project

    def test_audit_covers_every_cabinet_and_names_the_culprit(self) -> None:
        record = self.orchestrator.run_stage_analysis(
            self.project, "panel_unit_audit"
        )
        report = record["report"]
        self.assertEqual(report["cabinet_ids"], ["cabinet_1", "cabinet_2"])
        self.assertEqual(len(report["cabinets"]), 2)
        self.assertEqual(
            [cabinet["cabinet_id"] for cabinet in report["cabinets"]],
            ["cabinet_1", "cabinet_2"],
        )
        for issue in report["issues"]:
            self.assertIn(issue["cabinet_id"], {"cabinet_1", "cabinet_2"})
        narrowed = self.orchestrator.run_stage_analysis(
            self.project, "panel_unit_audit", {"cabinet_id": "cabinet_2"}
        )
        self.assertEqual(narrowed["report"]["cabinet_ids"], ["cabinet_2"])
        with self.assertRaisesRegex(ValueError, "cabinet_id is unknown"):
            self.orchestrator.run_stage_analysis(
                self.project, "panel_unit_audit", {"cabinet_id": "cabinet_9"}
            )

    def test_optimization_requires_an_explicit_cabinet(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires cabinet_id"):
            self.orchestrator.run_stage_analysis(
                self.project, "panel_optimization", dict(self.OPTIMIZATION)
            )

    def test_a_candidate_changes_only_its_own_cabinet(self) -> None:
        before = self.store.load(self.project.id).latest.stage_outputs[
            WorkflowStage.PANELS_PLANNED.value
        ]
        record = self.orchestrator.run_stage_analysis(
            self.project,
            "panel_optimization",
            {**self.OPTIMIZATION, "cabinet_id": "cabinet_2"},
        )
        candidates = record["report"]["candidates"]
        self.assertTrue(candidates)
        self.assertTrue(
            all(item["cabinet_id"] == "cabinet_2" for item in candidates)
        )
        self.assertEqual(record["report"]["cabinet_id"], "cabinet_2")
        before_by_id = {cabinet["id"]: cabinet for cabinet in before["cabinets"]}

        # 挑一个**真的改了方案**的候选（前沿里两个方案都在）。
        index = next(
            (
                position
                for position, item in enumerate(candidates)
                if item["resolved_parameters"]["back_mount"]
                != before_by_id["cabinet_2"]["spec"]["back_mount"]
            ),
            None,
        )
        self.assertIsNotNone(index, "前沿里应当有换了背板方案的候选")
        revised = self.orchestrator.apply_panel_optimization_candidate(
            self.project, index
        )
        after = revised.stage_outputs[WorkflowStage.PANELS_PLANNED.value]
        first = {cabinet["id"]: cabinet for cabinet in before["cabinets"]}
        second = {cabinet["id"]: cabinet for cabinet in after["cabinets"]}
        self.assertEqual(second["cabinet_1"]["spec"], first["cabinet_1"]["spec"])
        self.assertNotEqual(second["cabinet_2"]["spec"], first["cabinet_2"]["spec"])
        # 落地的方案正是候选那一档，且只有那一台变了。
        self.assertEqual(
            second["cabinet_2"]["spec"]["back_mount"],
            candidates[index]["resolved_parameters"]["back_mount"],
        )
        self.assertEqual(
            second["cabinet_1"]["spec"]["back_mount"],
            first["cabinet_1"]["spec"]["back_mount"],
        )


class ManufacturingHandoffShapeTests(unittest.TestCase):
    """逐柜产物的形状与解析：不接受被压扁的单份形状，也不静默取第一台。"""

    def _output(self, **readiness: str) -> dict:
        return {
            "cabinets": [
                {
                    "id": cabinet_id,
                    "bom": {
                        "readiness": value,
                        "panels": [{"label": f"{cabinet_id}__left_side"}],
                        "operations": [{"id": f"{cabinet_id}__op_1"}],
                        "materials": [],
                        "hardware": [],
                        "features": [],
                        "connection_points": [],
                    },
                }
                for cabinet_id, value in readiness.items()
            ]
        }

    def test_flattened_shape_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not support: panels"):
            cabinets_from_manufacturing({"panels": []})
        with self.assertRaisesRegex(ValueError, "requires cabinets"):
            cabinets_from_manufacturing({})

    def test_merged_view_concatenates_and_takes_the_weakest_readiness(self) -> None:
        merged = merged_manufacturing_view(
            self._output(cabinet_1="factory_ready", cabinet_2="preliminary")
        )
        self.assertEqual(merged["cabinet_count"], 2)
        self.assertEqual(merged["readiness"], "preliminary")
        self.assertEqual(
            [panel["label"] for panel in merged["panels"]],
            ["cabinet_1__left_side", "cabinet_2__left_side"],
        )
        weakest = merged_manufacturing_view(self._output(cabinet_1="accepted"))
        self.assertEqual(weakest["readiness"], "accepted")


if __name__ == "__main__":
    unittest.main()
