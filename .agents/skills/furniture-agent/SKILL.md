---
name: furniture-agent
description: Route furniture work through the correct local domain and CAD skills in this repository. Use for any furniture family, furniture requirements, Design Intent, panel structures, BOM or cut-list reasoning, Feature Trees, CAD generation, STEP inspection, artifact validation, or CAD Viewer handoff when instructions are split between skills/furniture-cad and external/text-to-cad/skills.
---

# Furniture Agent

Use this skill as the discoverable entry point for furniture work. Resolve all
paths from the repository root and keep this entry focused on routing.

## Route the request

1. Read `skills/furniture-cad/SKILL.md` for every furniture request and follow
   its stage-specific references.
2. For discussion, Design Intent, furniture structure, panelization, BOM, or
   manufacturing reasoning, stay in the furniture skill and its runtime under
   `skills/furniture-cad/scripts/` unless CAD work was requested.
3. Load the smallest required skill from canonical
   `external/text-to-cad/skills/`:
   - `cad/SKILL.md` for CAD generation, modification, STEP inspection,
     geometry validation, or snapshots.
   - `cad-viewer/SKILL.md` for visual review or artifact links.
   - `step-parts/SKILL.md` for named purchasable components.
   - Other engine skills only when their specific output is requested.
4. Ignore `external/text-to-cad/plugins/cad/skills/`; it is a generated
   production copy.
5. Before claiming executable support, inspect the relevant live code, tests,
   and entry command. Report missing sources instead of substituting remembered
   rules.

## Boundaries

- Keep approved furniture intent as the source of truth.
- Let `skills/furniture-cad/scripts/` own furniture planning and let the
  external engine own generic CAD generation, inspection, snapshots, and
  viewing.
- Reusable workspace scripts, runtime modules, and tests must stay under
  `skills/furniture-cad/scripts/`. One-off scripts must stay under `temp/`.
- Never create root `scripts/`, `packages/`, `tests/`, `scratch/`, or `tmp/`
  code trees. Never write generated Python or other source code under
  `generated/`.
- Run `skills/furniture-cad/scripts/validate_workspace_layout.py` after any
  workspace code-layout change and fix every reported violation.
- Do not edit `external/text-to-cad` to implement furniture-domain behavior.
- Do not hand-edit derived STEP, GLB, BOM, cut-list, or generated Python
  artifacts when an upstream intent or source exists.
- Do not load the entire external skill tree. Select the smallest relevant set.
- Report only validations that actually ran and artifacts that actually exist.
