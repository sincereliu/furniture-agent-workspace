---
name: furniture-agent
description: Route furniture work through the correct local domain and CAD skills in this repository. Use for furniture requirements, Design Intent, tables, wardrobes, floor or wall cabinets, panel structures, BOM or cut-list reasoning, Feature Trees, CAD generation, STEP inspection, artifact validation, or CAD Viewer handoff when instructions are split between skills/furniture-cad and external/text-to-cad/skills.
---

# Furniture Agent

Act as this repository's entry point for furniture work. Discover and route to
the maintained local skills; do not duplicate their domain or CAD instructions
here.

## Resolve the skill sources

Resolve all paths from the repository root containing this `skills/` directory.

1. Treat `skills/furniture-cad/SKILL.md` as the furniture-domain source. Read it
   for every furniture request, then load only the references needed for the
   current stage.
2. Treat `external/text-to-cad/skills/` as the canonical CAD-engine skill
   source. Load an external skill only when its capability is needed.
3. Ignore `external/text-to-cad/plugins/cad/skills/` during local development.
   It is a generated production copy of the canonical external skill tree.
4. Read `references/skill-map.md` when selecting an external skill or checking
   the boundary between workspace and engine responsibilities.

If a required path is absent, inspect the live checkout and report the missing
source instead of silently substituting remembered rules.

## Route the request

1. Inspect the live code, tests, and current skill text before making
   executable-capability claims. Prefer verified code over stale support lists.
2. Classify the requested stage:
   - For discussion, requirements, dimensions, or Design Intent, stay in the
     furniture-domain skill and stop before CAD unless generation was asked.
   - For furniture structure, placement, panelization, BOM, or manufacturing
     reasoning, use the furniture-domain skill and live `packages/`.
   - For CAD generation, modification, STEP inspection, geometry validation,
     or snapshots, also load `external/text-to-cad/skills/cad/SKILL.md`.
   - For visual review or artifact links, load
     `external/text-to-cad/skills/cad-viewer/SKILL.md`.
   - For named purchasable components, load
     `external/text-to-cad/skills/step-parts/SKILL.md` before inventing a
     placeholder.
   - Route DXF, G-code, implicit CAD, URDF, SRDF, or SDF only when the requested
     output requires the corresponding external skill.
3. Keep approved furniture intent as the source of truth. Let workspace
   packages own furniture planning and let the external engine own generic CAD
   generation, inspection, snapshots, and viewing.
4. Run and report only validations required by the task and successfully
   executed.

## Boundaries

- Do not edit `external/text-to-cad` to implement furniture-domain behavior.
- Do not hand-edit derived STEP, GLB, BOM, cut-list, or generated Python
  artifacts when an upstream intent or source exists.
- Do not load the entire external skill tree. Select the smallest relevant set.
- Do not assume support from documentation alone. Confirm the live planner,
  pipeline, tests, and entry command for the requested furniture family.
