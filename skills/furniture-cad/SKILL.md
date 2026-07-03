---
name: furniture-cad
description: Turn furniture requests into confirmable design intent, structured furniture specifications, panel-cabinet plans, preliminary BOM reasoning, Feature Trees, and validated CAD through this workspace. Use for tables, wardrobes, floor cabinets, wall cabinets, furniture dimensions or layouts, cabinet structure, panel placement, STEP generation, or questions about what the live furniture pipeline supports.
---

# Furniture CAD

Use this skill as a thin router. Keep user intent, executable input, domain
planning, generated geometry, and manufacturing output as separate layers.
Runtime code owns executable behavior; references in this skill explain how to
use it.

## Route by task

1. For requirements, dimensions, style, layout, or early design discussion,
   read [references/design-intent.md](references/design-intent.md). Return a
   confirmable Design Intent and stop unless the user requested planning or
   generation.
2. For wardrobes, floor cabinets, wall cabinets, panel placement, panel lists,
   edge banding, or BOM reasoning, also read
   [references/panel-cabinetry.md](references/panel-cabinetry.md).
3. Before claiming support, normalizing executable JSON, running generation, or
   reporting artifacts, read
   [references/workspace-pipeline.md](references/workspace-pipeline.md) and
   inspect the named live entry point when capability may have changed.
4. For unsupported furniture families, complete useful intent or modeling-plan
   work, then state the exact execution boundary. Do not invent a new runtime
   path inside the skill.

## Shared invariants

- Use millimeters unless the user explicitly requests another unit.
- Interpret overall dimensions as `W x D x H`: X left to right, Y rear to
  user-facing front, and Z upward.
- Use the lower-left-rear ground corner of the finished envelope as
  `(0, 0, 0)`. Part positions are minimum corners.
- Preserve unresolved intent decisions as `null` or an explicit unresolved
  list. Never silently fill safety-, fit-, or fabrication-critical values.
- Treat approved intent or executable JSON as source data. Do not hand-edit
  derived Feature Trees, Python, STEP, topology GLB, BOM, or cut-list output.
- Treat package defaults as software behavior, not factory-approved standards.
- Report only commands, validations, and artifacts that actually ran or exist.

## Work in stages

1. Capture and confirm Design Intent.
2. Normalize supported work to the live JSON contract.
3. Produce semantic parts and dependencies before CAD details.
4. Run the workspace planner, emitter, and CAD bridge in order.
5. Validate geometry and artifacts before reporting success.
6. Derive panel/BOM output from the same approved specification or plan.

If the user explicitly requests an end-to-end run and supplies enough
information for a supported type, continue without an extra approval stop. Ask
one focused question only when proceeding would make fit, safety, structure, or
fabrication materially wrong.

## Return

- Intent work: the Design Intent, assumptions, unresolved decisions, and at
  most one blocking confirmation question.
- Planning work: the normalized specification, semantic structure, and clearly
  labeled provisional manufacturing assumptions.
- Generation work: the normalized input, command result, validations performed,
  and paths to artifacts that exist.
