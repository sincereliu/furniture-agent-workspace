from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import yaml


WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
SKILLS_ROOT = WORKSPACE_ROOT / "domain" / "skills"

INTENT_SCRIPTS_ROOT = SKILLS_ROOT / "design-intent" / "scripts"
if str(INTENT_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(INTENT_SCRIPTS_ROOT))

from furniture_design_intent.design_intent import SUPPORTED_TYPES

STAGE_SKILLS = {
    "design_intent": "design-intent",
    "panels_planned": "panel-plan",
    "manufacturing_planned": "manufacturing-plan",
    "feature_tree_planned": "feature-tree",
    "cad_generated": "cad-artifacts",
    "delivery_validated": "delivery-report",
}

STAGE_REFERENCES = {
    "design-intent": (
        "references/intent-capture-rules.md",
        "references/intake/catalog.yaml",
    ),
    "layout-plan": ("references/spatial-layout-rules.md",),
    "panel-plan": (
        "references/panel-definition-rules.md",
    ),
    "manufacturing-plan": ("references/manufacturing-rules.md",),
    "feature-tree": ("references/feature-tree-rules.md",),
    "cad-artifacts": ("references/runtime-contract.md",),
    "delivery-report": ("references/delivery-checklist.md",),
}

STAGE_RUNTIME_PACKAGES = {
    "design-intent": "furniture_design_intent",
    "layout-plan": "furniture_layout",
    "panel-plan": "furniture_panel_planning",
    "manufacturing-plan": "furniture_manufacturing",
    "feature-tree": "furniture_feature_tree",
    "cad-artifacts": "furniture_cad",
    "delivery-report": "furniture_delivery_validation",
}


class SkillArchitectureTests(unittest.TestCase):
    def test_llm_runtime_boundary_policy_is_discoverable(self) -> None:
        policy_relative_path = (
            ".agents/skills/furniture-agent/references/"
            "llm-runtime-boundary.md"
        )
        policy_path = WORKSPACE_ROOT / policy_relative_path
        self.assertTrue(policy_path.is_file(), policy_path)

        router_path = (
            WORKSPACE_ROOT / ".agents" / "skills" / "furniture-agent" / "SKILL.md"
        )
        router = router_path.read_text(encoding="utf-8")
        self.assertIn("references/llm-runtime-boundary.md", router, router_path)

        repository_instructions = (WORKSPACE_ROOT / "AGENTS.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(policy_relative_path, repository_instructions)

    def test_six_serial_stages_have_one_skill_each(self) -> None:
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
        layout_skill = (SKILLS_ROOT / "layout-plan" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("独立按需步骤", layout_skill)
        self.assertNotRegex(layout_skill, re.compile(r"^阶段：`", re.MULTILINE))

    def test_router_uses_explicit_stage_skill_paths(self) -> None:
        router = (
            WORKSPACE_ROOT / ".agents" / "skills" / "furniture-agent" / "SKILL.md"
        ).read_text(encoding="utf-8")

        for stage, skill_name in STAGE_SKILLS.items():
            self.assertIn(
                f"`{stage}`：`domain/skills/{skill_name}/SKILL.md`",
                router,
            )
        self.assertIn(
            "独立能力（不在上述串联阶段内）",
            router,
        )
        self.assertIn("`domain/skills/layout-plan/SKILL.md`", router)

    def test_scientific_skills_are_routed_on_demand_to_stage_owned_adapters(
        self,
    ) -> None:
        router_path = (
            WORKSPACE_ROOT / ".agents" / "skills" / "furniture-agent" / "SKILL.md"
        )
        router = router_path.read_text(encoding="utf-8")
        for skill_name in (
            "uncertainty-and-units",
            "pymoo",
            "experimental-design",
            "statistical-analysis",
            "simpy",
        ):
            self.assertIn(f"{skill_name}/SKILL.md", router, router_path)

        owned_adapters = (
            (
                "panel-plan",
                "furniture_panel_planning/quantitative_audit.py",
            ),
            (
                "panel-plan",
                "furniture_panel_planning/design_optimization.py",
            ),
            (
                "manufacturing-plan",
                "furniture_manufacturing/prototype_experiment.py",
            ),
            (
                "manufacturing-plan",
                "furniture_manufacturing/test_statistics.py",
            ),
            (
                "manufacturing-plan",
                "furniture_manufacturing/production_simulation.py",
            ),
        )
        for skill_name, relative_path in owned_adapters:
            path = SKILLS_ROOT / skill_name / "scripts" / relative_path
            self.assertTrue(path.is_file(), path)

        self.assertFalse(
            (
                WORKSPACE_ROOT
                / ".agents"
                / "skills"
                / "scientific-agent-skills"
            ).exists()
        )

    def test_stage_references_live_with_their_owning_skill(self) -> None:
        for skill_name, references in STAGE_REFERENCES.items():
            skill_root = SKILLS_ROOT / skill_name
            for relative_path in references:
                self.assertTrue((skill_root / relative_path).is_file())

        cad_references = SKILLS_ROOT / "cad-artifacts" / "references"
        for moved_reference in (
            "intent-capture-rules.md",
            "spatial-layout-rules.md",
            "panel-definition-rules.md",
            "manufacturing-rules.md",
            "feature-tree-rules.md",
            "delivery-checklist.md",
        ):
            self.assertFalse((cad_references / moved_reference).exists())

        topology_root = (
            SKILLS_ROOT
            / "panel-plan"
            / "references"
            / "cabinet-topologies"
        )
        self.assertTrue((topology_root / "floor_cabinet.yaml").is_file())
        self.assertTrue((topology_root / "wall_cabinet.yaml").is_file())
        self.assertFalse(
            (
                SKILLS_ROOT
                / "design-intent"
                / "references"
                / "cabinet_topologies"
            ).exists()
        )

    def test_intent_catalog_executable_families_match_runtime_supported_types(
        self,
    ) -> None:
        catalog_path = (
            SKILLS_ROOT
            / "design-intent"
            / "references"
            / "intake"
            / "catalog.yaml"
        )
        catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
        executable_families = {
            name
            for name, family in catalog.get("families", {}).items()
            if family.get("executable") is True
        }
        self.assertEqual(
            executable_families,
            set(SUPPORTED_TYPES),
            "catalog.yaml `executable: true` families must match SUPPORTED_TYPES",
        )

    def test_each_stage_skill_owns_its_runtime_package(self) -> None:
        for skill_name, package_name in STAGE_RUNTIME_PACKAGES.items():
            package_root = SKILLS_ROOT / skill_name / "scripts" / package_name
            self.assertTrue(package_root.is_dir(), package_root)
            self.assertTrue((package_root / "__init__.py").is_file(), package_root)

        workflow_package = (
            SKILLS_ROOT / "cad-artifacts" / "scripts" / "furniture_workflow"
        )
        self.assertTrue((workflow_package / "workflow_orchestrator.py").is_file())

    def test_stage_validation_rules_do_not_live_in_the_orchestrator(self) -> None:
        validators = {
            "design-intent": "furniture_design_intent/validation.py",
            "layout-plan": "furniture_layout/validation.py",
            "panel-plan": "furniture_panel_planning/validation.py",
            "manufacturing-plan": "furniture_manufacturing/validation.py",
            "feature-tree": "furniture_feature_tree/validation.py",
            "cad-artifacts": "furniture_cad/validation.py",
            "delivery-report": (
                "furniture_delivery_validation/validation.py"
            ),
        }
        for skill_name, relative_path in validators.items():
            self.assertTrue(
                (SKILLS_ROOT / skill_name / "scripts" / relative_path).is_file()
            )

        orchestrator = (
            SKILLS_ROOT
            / "cad-artifacts"
            / "scripts"
            / "furniture_workflow"
            / "workflow_orchestrator.py"
        ).read_text(encoding="utf-8")
        for forbidden_definition in (
            "def _validate_intent(",
            "def _validate_layout(",
            "def _validate_panels(",
            "def _validate_manufacturing(",
            "def _validate_feature_tree(",
            "def _validate_cad(",
            "def _validate_artifacts(",
            "def _write_artifacts(",
        ):
            self.assertNotIn(forbidden_definition, orchestrator)
        self.assertIn("def _validate_stage_output(", orchestrator)
        self.assertIn("from .workflow_artifact_writer import", orchestrator)

        delivery_validation = (
            SKILLS_ROOT
            / "delivery-report"
            / "scripts"
            / "furniture_delivery_validation"
            / "validation.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("furniture_workflow", delivery_validation)

    def test_layout_does_not_own_panel_or_manufacturing_runtime(self) -> None:
        layout_package = (
            SKILLS_ROOT
            / "layout-plan"
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
            / "panel-plan"
            / "scripts"
            / "furniture_panel_planning"
        )
        manufacturing_package = (
            SKILLS_ROOT
            / "manufacturing-plan"
            / "scripts"
            / "furniture_manufacturing"
        )
        self.assertTrue((panel_package / "cabinet_panel_planner.py").is_file())
        self.assertFalse((panel_package / "manufacturing_edge_banding.py").exists())
        self.assertTrue((manufacturing_package / "manufacturing_edge_banding.py").is_file())

    def test_geometric_rules_live_in_their_owning_stages(self) -> None:
        intent_package = (
            SKILLS_ROOT
            / "design-intent"
            / "scripts"
            / "furniture_design_intent"
        )
        panel_package = (
            SKILLS_ROOT
            / "panel-plan"
            / "scripts"
            / "furniture_panel_planning"
        )
        self.assertFalse((intent_package / "design_spec.py").exists())
        self.assertFalse((intent_package / "translation.py").exists())

        input_adapter = (
            SKILLS_ROOT
            / "cad-artifacts"
            / "scripts"
            / "furniture_workflow"
            / "input_adapter.py"
        )
        self.assertTrue(input_adapter.is_file())

        layout_validation = (
            SKILLS_ROOT
            / "layout-plan"
            / "scripts"
            / "furniture_layout"
            / "validation.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("NON_POSITIVE_INTERNAL_CLEARANCE", layout_validation)
        self.assertNotIn("INTERNAL_CLEARANCE_MISMATCH", layout_validation)

        panel_validation = (
            SKILLS_ROOT
            / "panel-plan"
            / "scripts"
            / "furniture_panel_planning"
            / "validation.py"
        ).read_text(encoding="utf-8")
        panel_spec = (panel_package / "panel_spec.py").read_text(encoding="utf-8")
        self.assertIn("def resolve_back_mount(", panel_spec)
        self.assertIn("NON_POSITIVE_INTERNAL_CLEARANCE", panel_validation)
        self.assertIn("STRUCTURE_GEOMETRY_MISMATCH", panel_validation)
        self.assertIn(
            "NON_POSITIVE_TOE_KICK_SUPPORT_SPACING",
            panel_validation,
        )
        self.assertIn("BACK_RAIL_COUNT_MISMATCH", panel_validation)

        manufacturing_validation = (
            SKILLS_ROOT
            / "manufacturing-plan"
            / "scripts"
            / "furniture_manufacturing"
            / "validation.py"
        ).read_text(encoding="utf-8")
        self.assertIn("GROOVE_OUTSIDE_TARGET", manufacturing_validation)
        # 五金专属几何规则随各 Connector 自洽（仍属制造阶段运行时）
        hinge_connector = (
            SKILLS_ROOT
            / "manufacturing-plan"
            / "scripts"
            / "furniture_manufacturing"
            / "connectors"
            / "hinge.py"
        ).read_text(encoding="utf-8")
        self.assertIn("HINGE_HOLE_OUTSIDE_DOOR", hinge_connector)

        feature_tree_emitter = (
            SKILLS_ROOT
            / "feature-tree"
            / "scripts"
            / "furniture_feature_tree"
            / "feature_tree_emitter.py"
        ).read_text(encoding="utf-8")
        self.assertIn("_validate_operation_bounds", feature_tree_emitter)

    def test_back_mount_contract_is_synchronized_across_stage_skills(
        self,
    ) -> None:
        expected_terms = {
            ".agents/skills/furniture-agent/SKILL.md": (
                "back_mount",
                "从板件阶段开始",
            ),
            "domain/skills/panel-plan/SKILL.md": (
                "back_mount",
                "背拉条",
            ),
            "domain/skills/manufacturing-plan/SKILL.md": (
                "groove",
                "背拉条",
            ),
            "domain/skills/manufacturing-plan/references/runtime-map.md": (
                "BackMountConnector",
                "generate_holes_for_panels",
            ),
            "domain/skills/feature-tree/SKILL.md": (
                "insert/cover",
                "drilled-holes",
            ),
            "domain/skills/cad-artifacts/SKILL.md": (
                "back_mount/back_rail_height",
                "drilled-holes",
            ),
            (
                "domain/skills/delivery-report/"
                "references/delivery-checklist.md"
            ): (
                "back_mount",
                "五金数量与主孔、配合孔数量一致",
            ),
        }

        for relative_path, terms in expected_terms.items():
            path = WORKSPACE_ROOT / relative_path
            text = path.read_text(encoding="utf-8")
            for term in terms:
                self.assertIn(term, text, path)

        for relative_path in (
            "domain/skills/design-intent/SKILL.md",
            "domain/skills/layout-plan/SKILL.md",
        ):
            text = (WORKSPACE_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertNotIn("auto/groove/insert/cover", text)

    def test_corrected_stage_boundaries_match_runtime_ownership(self) -> None:
        expected_terms = {
            "domain/skills/design-intent/SKILL.md": (
                "草稿尺寸可为 `null`",
                "furniture_type",
                "成品外包络",
            ),
            "domain/skills/layout-plan/SKILL.md": (
                "door_count",
                "不参与房间定位",
                "左后下落地角",
            ),
            "domain/skills/manufacturing-plan/SKILL.md": (
                "readiness=preliminary/accepted/factory_ready",
                "FurnitureOrchestrator.run_next()",
                "references/runtime-map.md",
            ),
            "domain/skills/delivery-report/SKILL.md": (
                "前五个串联阶段",
                "不解析 STEP 几何",
                "未执行",
            ),
        }
        for relative_path, terms in expected_terms.items():
            path = WORKSPACE_ROOT / relative_path
            text = path.read_text(encoding="utf-8")
            for term in terms:
                self.assertIn(term, text, path)


if __name__ == "__main__":
    unittest.main()
