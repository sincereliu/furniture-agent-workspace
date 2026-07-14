from __future__ import annotations

import re
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
SKILLS_ROOT = WORKSPACE_ROOT / "skills"

STAGE_SKILLS = {
    "design_intent": "furniture-design-intent",
    "layout_planned": "furniture-layout",
    "panels_planned": "furniture-panel-planning",
    "manufacturing_planned": "furniture-manufacturing",
    "feature_tree_planned": "furniture-feature-tree",
    "cad_generated": "furniture-cad",
    "delivery_validated": "furniture-delivery-validation",
}

STAGE_REFERENCES = {
    "furniture-design-intent": (
        "references/design-intent.md",
        "references/intake/catalog.yaml",
    ),
    "furniture-layout": ("references/layout-planning.md",),
    "furniture-panel-planning": ("references/panel-planning.md",),
    "furniture-manufacturing": ("references/manufacturing-policy.md",),
    "furniture-feature-tree": ("references/feature-tree.md",),
    "furniture-cad": ("references/workspace-pipeline.md",),
    "furniture-delivery-validation": ("references/validation.md",),
}

STAGE_RUNTIME_PACKAGES = {
    "furniture-design-intent": "furniture_design_intent",
    "furniture-layout": "furniture_layout",
    "furniture-panel-planning": "furniture_panel_planning",
    "furniture-manufacturing": "furniture_manufacturing",
    "furniture-feature-tree": "furniture_feature_tree",
    "furniture-cad": "furniture_cad",
    "furniture-delivery-validation": "furniture_delivery_validation",
}


class SkillArchitectureTests(unittest.TestCase):
    def test_seven_stages_have_one_skill_each(self) -> None:
        claimed_stages: dict[str, str] = {}

        for stage, skill_name in STAGE_SKILLS.items():
            skill_root = SKILLS_ROOT / skill_name
            skill_file = skill_root / "SKILL.md"
            agent_file = skill_root / "agents" / "openai.yaml"
            self.assertTrue(skill_file.is_file(), skill_file)
            self.assertTrue(agent_file.is_file(), agent_file)

            skill_text = skill_file.read_text(encoding="utf-8")
            match = re.search(r"^阶段：`([^\`]+)`$", skill_text, re.MULTILINE)
            self.assertIsNotNone(match, skill_file)
            claimed_stage = match.group(1)
            self.assertEqual(claimed_stage, stage, skill_file)
            self.assertNotIn(claimed_stage, claimed_stages)
            claimed_stages[claimed_stage] = skill_name

        self.assertEqual(claimed_stages, STAGE_SKILLS)

    def test_router_uses_explicit_stage_skill_paths(self) -> None:
        router = (
            WORKSPACE_ROOT / ".agents" / "skills" / "furniture-agent" / "SKILL.md"
        ).read_text(encoding="utf-8")

        for stage, skill_name in STAGE_SKILLS.items():
            self.assertIn(
                f"`{stage}`：`skills/{skill_name}/SKILL.md`",
                router,
            )

    def test_stage_references_live_with_their_owning_skill(self) -> None:
        for skill_name, references in STAGE_REFERENCES.items():
            skill_root = SKILLS_ROOT / skill_name
            for relative_path in references:
                self.assertTrue((skill_root / relative_path).is_file())

        cad_references = SKILLS_ROOT / "furniture-cad" / "references"
        for moved_reference in (
            "design-intent.md",
            "layout-planning.md",
            "panel-planning.md",
            "manufacturing-policy.md",
            "feature-tree.md",
            "validation.md",
        ):
            self.assertFalse((cad_references / moved_reference).exists())

    def test_each_stage_skill_owns_its_runtime_package(self) -> None:
        for skill_name, package_name in STAGE_RUNTIME_PACKAGES.items():
            package_root = SKILLS_ROOT / skill_name / "scripts" / package_name
            self.assertTrue(package_root.is_dir(), package_root)
            self.assertTrue((package_root / "__init__.py").is_file(), package_root)

        workflow_package = (
            SKILLS_ROOT / "furniture-cad" / "scripts" / "furniture_workflow"
        )
        self.assertTrue((workflow_package / "workflow_orchestrator.py").is_file())

    def test_layout_does_not_own_panel_or_manufacturing_runtime(self) -> None:
        layout_package = (
            SKILLS_ROOT
            / "furniture-layout"
            / "scripts"
            / "furniture_layout"
        )
        layout_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in layout_package.glob("*.py")
        )
        self.assertNotIn("PanelPlacement", layout_source)
        self.assertNotIn("cut_box", layout_source)
        self.assertFalse((layout_package / "layout_template.py").exists())

        panel_package = (
            SKILLS_ROOT
            / "furniture-panel-planning"
            / "scripts"
            / "furniture_panel_planning"
        )
        manufacturing_package = (
            SKILLS_ROOT
            / "furniture-manufacturing"
            / "scripts"
            / "furniture_manufacturing"
        )
        self.assertTrue((panel_package / "cabinet_panel_planner.py").is_file())
        self.assertFalse((panel_package / "manufacturing_edge_banding.py").exists())
        self.assertTrue((manufacturing_package / "manufacturing_edge_banding.py").is_file())


if __name__ == "__main__":
    unittest.main()
