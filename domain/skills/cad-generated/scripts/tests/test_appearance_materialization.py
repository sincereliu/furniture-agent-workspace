from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from dataclasses import asdict

from panel_fixtures import cabinet_data, furniture_spec
from furniture_manufacturing.manufacturing_bom import (
    format_bom_markdown,
    plan_manufacturing,
)
from furniture_manufacturing.manufacturing_models import PanelRecord
from furniture_manufacturing.validation import validate_manufacturing
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.structure_planning import CabinetStructure
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import WorkflowStage
from workflow_test_support import confirm_through


def _appearance_valid():
    return {
        "carcass": {"substrate": "particleboard", "surface": "white__soft_touch__plain"},
        "door": {"substrate": "particleboard", "surface": "oak__double_faced__grain"},
        "back": {"substrate": "particleboard", "surface": "white__double_faced__plain"},
    }


class AppearanceValidationTests(unittest.TestCase):
    def _placements(self):
        spec = furniture_spec(n_doors=2)
        return spec, plan_panels(spec, CabinetStructure.from_spec(spec))

    def test_empty_appearance_is_backward_compatible(self) -> None:
        spec, placements = self._placements()
        bom = plan_manufacturing(spec, placements)
        self.assertEqual(bom.appearance, {})

    def test_valid_appearance_is_normalized(self) -> None:
        spec, placements = self._placements()
        bom = plan_manufacturing(spec, placements, appearance=_appearance_valid())
        self.assertEqual(bom.appearance, _appearance_valid())

    def test_unknown_role_is_rejected(self) -> None:
        spec, placements = self._placements()
        bad = {"side": {"substrate": "particleboard", "surface": "white__soft_touch__plain"}}
        with self.assertRaisesRegex(ValueError, "appearance roles"):
            plan_manufacturing(spec, placements, appearance=bad)

    def test_missing_role_is_rejected(self) -> None:
        spec, placements = self._placements()
        app = _appearance_valid()
        app.pop("back")
        with self.assertRaisesRegex(ValueError, "missing selection"):
            plan_manufacturing(spec, placements, appearance=app)

    def test_absent_role_is_rejected(self) -> None:
        spec = furniture_spec(n_doors=0)
        placements = plan_panels(spec, CabinetStructure.from_spec(spec))
        with self.assertRaisesRegex(ValueError, "absent material_role"):
            plan_manufacturing(spec, placements, appearance=_appearance_valid())

    def test_non_object_selection_is_rejected(self) -> None:
        spec, placements = self._placements()
        app = _appearance_valid()
        app["carcass"] = "not-a-dict"
        with self.assertRaisesRegex(ValueError, "must be an object"):
            plan_manufacturing(spec, placements, appearance=app)

    def test_unknown_substrate_is_rejected(self) -> None:
        spec, placements = self._placements()
        app = _appearance_valid()
        app["carcass"]["substrate"] = "mdf"
        with self.assertRaisesRegex(ValueError, "substrate unknown"):
            plan_manufacturing(spec, placements, appearance=app)

    def test_unknown_surface_is_rejected(self) -> None:
        spec, placements = self._placements()
        app = _appearance_valid()
        app["door"]["surface"] = "white__gloss__grain"
        with self.assertRaisesRegex(ValueError, "surface unknown"):
            plan_manufacturing(spec, placements, appearance=app)

    def test_materialization_stamps_substrate_and_surface(self) -> None:
        spec, placements = self._placements()
        app = {
            "carcass": {"substrate": "particleboard", "surface": "white__soft_touch__plain"},
            "door": {"substrate": "eco_board", "surface": "oak__double_faced__grain"},
            "back": {"substrate": "particleboard", "surface": "white__double_faced__plain"},
        }
        bom = plan_manufacturing(spec, placements, appearance=app)
        doors = [p for p in bom.panels if p.panel_type == "door"]
        backs = [p for p in bom.panels if p.panel_type == "back"]
        carcass = [p for p in bom.panels if p.panel_type not in ("door", "back")]
        self.assertTrue(doors)
        self.assertTrue(backs)
        self.assertTrue(carcass)
        for p in doors:
            self.assertEqual(p.substrate, "eco_board")
            self.assertEqual(p.surface, "oak__double_faced__grain")
        for p in backs:
            self.assertEqual(p.substrate, "particleboard")
            self.assertEqual(p.surface, "white__double_faced__plain")
        for p in carcass:
            self.assertEqual(p.substrate, "particleboard")
            self.assertEqual(p.surface, "white__soft_touch__plain")

    def test_no_appearance_leaves_substrate_surface_empty(self) -> None:
        spec, placements = self._placements()
        bom = plan_manufacturing(spec, placements)
        for panel in bom.panels:
            self.assertEqual(panel.substrate, "")
            self.assertEqual(panel.surface, "")

    def test_materialization_completeness_is_validated(self) -> None:
        spec, placements = self._placements()
        bom = plan_manufacturing(spec, placements, appearance=_appearance_valid())
        report = validate_manufacturing(spec, bom, placements)
        codes = {issue.code for issue in report.issues}
        self.assertNotIn("APPEARANCE_NOT_MATERIALIZED", codes)

    def test_missing_materialization_is_flagged(self) -> None:
        spec, placements = self._placements()
        bom = plan_manufacturing(spec, placements, appearance=_appearance_valid())
        bom.panels[0].substrate = ""
        report = validate_manufacturing(spec, bom, placements)
        codes = {issue.code for issue in report.issues}
        self.assertIn("APPEARANCE_NOT_MATERIALIZED", codes)

    def test_panel_record_roundtrip_preserves_materialization(self) -> None:
        spec, placements = self._placements()
        bom = plan_manufacturing(spec, placements, appearance=_appearance_valid())
        door = next(p for p in bom.panels if p.panel_type == "door")
        restored = PanelRecord.from_dict(asdict(door))
        self.assertEqual(restored.substrate, door.substrate)
        self.assertEqual(restored.surface, door.surface)

    def test_end_to_end_appearance_materializes_through_workflow(self) -> None:
        orchestrator = FurnitureOrchestrator(
            workspace_root=WORKSPACE_ROOT, project_store=None
        )
        spec = cabinet_data(n_doors=2)
        spec["appearance"] = _appearance_valid()
        result = confirm_through(
            orchestrator,
            "外观物化",
            spec,
            through_stage=WorkflowStage.MANUFACTURING_PLANNED,
        )
        output = result.revision.stage_outputs[
            WorkflowStage.MANUFACTURING_PLANNED.value
        ]
        doors = [p for p in output["panels"] if p["panel_type"] == "door"]
        backs = [p for p in output["panels"] if p["panel_type"] == "back"]
        self.assertTrue(doors)
        self.assertTrue(backs)
        self.assertTrue(all(p["substrate"] == "particleboard" for p in doors))
        self.assertTrue(
            all(p["surface"] == "oak__double_faced__grain" for p in doors)
        )
        self.assertTrue(
            all(p["surface"] == "white__double_faced__plain" for p in backs)
        )

    def test_bom_markdown_shows_materialized_appearance(self) -> None:
        spec, placements = self._placements()
        bom = plan_manufacturing(spec, placements, appearance=_appearance_valid())
        markdown = format_bom_markdown(bom)
        self.assertIn("材质", markdown)
        self.assertIn("肤感白", markdown)
        self.assertIn("双饰面橡木纹", markdown)


if __name__ == "__main__":
    unittest.main()
