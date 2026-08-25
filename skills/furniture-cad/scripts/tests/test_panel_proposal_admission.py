from __future__ import annotations

from copy import deepcopy
import sys
import unittest
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_design_intent.design_intent import DesignIntent, OverallSize
from furniture_panel_planning.panel_pipeline import plan_panel_stage
from furniture_panel_planning.panel_spec import PANEL_PROFILES
from furniture_panel_planning.validation import validate_panel_output


def confirmed_intent(furniture_type: str = "floor_cabinet") -> DesignIntent:
    return DesignIntent(
        furniture_type=furniture_type,
        overall_size=OverallSize(800, 600, 1000),
    ).confirm()


class PanelProposalAdmissionTests(unittest.TestCase):
    def test_missing_proposal_does_not_materialize_runtime_defaults(self) -> None:
        with self.assertRaisesRegex(ValueError, "panel proposal is incomplete"):
            plan_panel_stage(confirmed_intent(), {})

    def test_explicit_profile_expands_to_a_complete_traceable_spec(self) -> None:
        output = plan_panel_stage(
            confirmed_intent(),
            {"panel_profile": "floor_cabinet_standard_v1"},
        )

        self.assertEqual(
            set(output["spec"]),
            {
                "furniture_type",
                "width",
                "depth",
                "height",
                *(
                    key
                    for key in PANEL_PROFILES["floor_cabinet_standard_v1"]
                    if key != "furniture_type"
                ),
            },
        )
        self.assertEqual(
            output["proposal_admission"]["panel_profile"],
            "floor_cabinet_standard_v1",
        )
        self.assertTrue(validate_panel_output(confirmed_intent(), output).passed)

    def test_complete_explicit_proposal_needs_no_profile(self) -> None:
        parameters = {
            key: value
            for key, value in PANEL_PROFILES[
                "floor_cabinet_standard_v1"
            ].items()
            if key != "furniture_type"
        }
        output = plan_panel_stage(confirmed_intent(), parameters)

        self.assertIsNone(output["proposal_admission"]["panel_profile"])
        self.assertEqual(
            set(output["proposal_admission"]["explicit_fields"]),
            set(parameters),
        )

    def test_natural_language_enum_is_rejected_before_geometry(self) -> None:
        with self.assertRaisesRegex(ValueError, "back_mount must be one of"):
            plan_panel_stage(
                confirmed_intent(),
                {
                    "panel_profile": "floor_cabinet_standard_v1",
                    "back_mount": "背板入槽",
                },
            )

    def test_profile_must_match_the_confirmed_furniture_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "not compatible"):
            plan_panel_stage(
                confirmed_intent("wall_cabinet"),
                {"panel_profile": "floor_cabinet_standard_v1"},
            )

    def test_full_height_drawer_conflicts_are_rejected_not_ignored(self) -> None:
        with self.assertRaisesRegex(ValueError, "full-height drawers require"):
            plan_panel_stage(
                confirmed_intent(),
                {
                    "panel_profile": "floor_cabinet_standard_v1",
                    "drawer_count": 3,
                    "n_doors": 2,
                    "shelf_count": 4,
                },
            )

    def test_unconfirmed_intent_cannot_enter_panel_admission(self) -> None:
        draft = DesignIntent(
            furniture_type="floor_cabinet",
            overall_size=OverallSize(800, 600, 1000),
        )
        with self.assertRaisesRegex(ValueError, "confirmed DesignIntent"):
            plan_panel_stage(
                draft,
                {"panel_profile": "floor_cabinet_standard_v1"},
            )

    def test_spec_tampering_invalidates_the_admission_hash(self) -> None:
        intent = confirmed_intent()
        output = plan_panel_stage(
            intent,
            {"panel_profile": "floor_cabinet_standard_v1"},
        )
        tampered = deepcopy(output)
        tampered["spec"]["board_thickness"] = 19.0

        report = validate_panel_output(intent, tampered)

        self.assertFalse(report.passed)
        self.assertIn(
            "PANEL_SPEC_ADMISSION_HASH_MISMATCH",
            {issue.code for issue in report.issues},
        )


if __name__ == "__main__":
    unittest.main()
