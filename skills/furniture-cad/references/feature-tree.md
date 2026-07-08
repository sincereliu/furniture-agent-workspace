# Feature Tree

Use this reference after Panel Planning and Manufacturing Policy when CAD
modeling semantics are needed. Feature Tree answers: "How should these
components be modeled?"

This file owns CAD modeling intent: feature identities, dependencies,
parameter sources, and assembly structure. It does not own user requirements,
layout choices, manufacturing policy, runtime commands, STEP entities, or
artifact validation.

## Modeling responsibilities

- Convert semantic components into modeling features with stable names.
- Preserve dependencies between components, such as panels depending on the
  finished envelope, shelves depending on bay ranges, and doors depending on
  openings.
- Keep manufacturing annotations available as metadata when useful, without
  turning them into fabrication approval.
- Keep CAD details downstream of the Feature Tree; this layer describes what
  should be modeled, not how a CAD API call is executed.

## Execution boundary

Feature Tree planning may describe modeling semantics even when the current
runtime cannot execute every semantic detail. Executable support belongs to the
Workspace Pipeline layer.

## Boundary

- Do not define Design Intent fields, layout zones, panel decomposition rules,
  manufacturing tolerances, command lines, output paths, STEP topology, or
  validation results here.
- Do not bypass the workspace planner by hand-writing one-off CAD source for
  ordinary furniture generation.
