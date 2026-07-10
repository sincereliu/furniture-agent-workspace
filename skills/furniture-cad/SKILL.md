---
name: furniture-cad
description: Turn requests for any furniture family into confirmable Design Intent, Layout Planning, Panel Planning, Manufacturing Policy, Feature Tree planning, and validated CAD through this workspace. Use for furniture dimensions or layouts, structure, panel semantics, manufacturing reasoning, STEP generation, or questions about what the live furniture pipeline supports.
---

# Furniture CAD

Use this skill as a thin router. Keep user intent, spatial organization,
manufacturing parts, manufacturing rules, CAD modeling semantics, runtime
execution, and validation as separate domain layers. Runtime code owns
executable behavior; references in this skill explain how to use it.

Conceptual workflow:

`Design Intent -> Layout Planning -> Panel Planning -> Manufacturing Policy -> Feature Tree -> CAD -> STEP`

These are documentation and reasoning layers. In the current runtime, planning
is still implemented by the existing planner and related workspace packages;
this skill does not define a new planner interface, executable JSON shape, or
runtime step.

## Route by task

1. Read the [furniture catalog](references/intake/catalog.yaml), match the user
   request to one family. Use the catalog fallback when no family matches.
   Default dimensions and parameters live in
   `scripts/furniture/design_spec.py` (dataclass defaults + `CABINET_PRESETS`).
2. For user requirements, dimensions, style, constraints, or early design
   discussion, read [references/design-intent.md](references/design-intent.md).
   Return a confirmable Design Intent and stop unless the user requested later
   stages.
3. For layout, panel semantics, manufacturing policy, Feature Tree reasoning,
   or validation, load the selected catalog entry's applicable
   `planning_references`.
4. Before claiming support, normalizing executable JSON, running generation, or
   reporting artifacts, read
   [references/workspace-pipeline.md](references/workspace-pipeline.md) and
   inspect the named live entry point when capability may have changed.
5. For unsupported furniture families, complete useful intent or modeling-plan
   work, then state the exact execution boundary. Do not invent a new runtime
   path inside the skill.

## Domain references

- [Design Intent](references/design-intent.md): what furniture should be built.
- [Layout Planning](references/layout-planning.md): how it is organized.
- [Panel Planning](references/panel-planning.md): what physical components
  exist.
- [Manufacturing Policy](references/manufacturing-policy.md): how it should be
  manufactured.
- [Feature Tree](references/feature-tree.md): how components should be modeled.
- [Workspace Pipeline](references/workspace-pipeline.md): what the current
  runtime executes.
- [Validation](references/validation.md): which gates must pass before
  reporting success.

## Work in stages

1. Capture and confirm Design Intent: what furniture should be built.
2. Resolve Layout Planning: the major arrangement and furniture-family choices.
3. Resolve Panel Planning: what physical furniture components exist.
4. Resolve Manufacturing Policy: materials, tolerances, joinery, and BOM
   assumptions.
5. Produce Feature Tree modeling semantics before CAD geometry details.
6. Run the skill-owned planner, emitter, and CAD bridge in order when supported.
7. Validate the relevant layers and artifacts before reporting success.

If the user explicitly requests an end-to-end run and supplies enough
information for a supported type, continue without an extra approval stop. Ask
one focused question only when proceeding would make fit, safety, structure, or
fabrication materially wrong.

## Return

- Intent work: the Design Intent, assumptions, unresolved decisions, and at
  most one blocking confirmation question.
- Planning work: the normalized specification, layout decisions, Panel Plan
  semantics, manufacturing policy assumptions, and Feature Tree implications.
- Generation work: the normalized input, command result, validations performed,
  and paths to artifacts that exist.
