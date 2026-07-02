# Furniture Skill Migration

## Decision

Keep `skills/furniture-cad` as one thin agent entry point. Move reusable
furniture knowledge into progressive references and keep executable behavior in
workspace packages. Do not copy the earlier all-in-one skill directory into
this workspace.

## Source-to-target map

| Earlier `furniture` content | Target in this workspace | Action |
|---|---|---|
| `SKILL.md` workflow and defaults | `skills/furniture-cad/SKILL.md` plus references | Distill and route by stage |
| `references/cabinet-structures.md` | `references/panel-cabinetry.md` | Migrate structural semantics |
| `references/panel-placement.md` | planner rules and tests | Preserve rear-to-front Y and verify ranges |
| `configs/*.yaml` | future versioned domain-policy package | Do not duplicate inside skill prose |
| `templates/*.py` | future planner strategies | Port behavior, not source layout |
| `core/panel.py` | future furniture schema/domain package | Remove CAD-solid ownership from the record |
| `core/generator.py` | planner plus emitter packages | Split planning from geometry emission |
| `core/assembly_adapter.py` | `packages/cad-bridge` | Use the existing bridge instead |
| order scripts and output layout | service or CLI layer | Keep out of the skill |
| generated caches and historical comparison files | nowhere | Do not migrate |

## Why a direct copy is unsafe

- The earlier package mixes LLM instructions, business rules, CAD objects,
  templates, order storage, and export commands.
- Its rear-to-front Y convention is valid and now matches this workspace, but
  the old formulas still need semantic planner tests before reuse.
- It exports STEP directly, bypassing the current planner, emitter, and CAD
  bridge.
- Defaults are duplicated between Python and YAML, which invites drift.
- Its skill description promises cabinet generation and BOM output that the
  current workspace has not yet implemented or validated.

## Implementation sequence

1. Stabilize a CAD-independent furniture schema for intent, semantic parts,
   materials, and manufacturing annotations.
2. Add panel-cabinet planner strategies with range-based coordinate tests.
3. Extend the emitter to consume semantic panel features without embedding
   business defaults.
4. Add BOM and edge-banding outputs derived from the same approved Feature Tree.
5. Add floor-cabinet, wall-cabinet, and wardrobe end-to-end fixtures.
6. Only then change the skill capability statement from planning-only to
   executable cabinet generation.
