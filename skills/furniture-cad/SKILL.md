---
name: furniture-cad
description: Turn furniture requests into confirmable design intent, then plan, validate, and optionally generate CAD through this workspace. Use for tables, wardrobes, cabinets, shelves, desks, beds, furniture dimensions and layouts, Feature Trees, or furniture STEP generation. The current executable vertical slice supports rectangular tables; keep other furniture types at design-intent or planning level until their planner is implemented.
---

# Furniture CAD

Use a staged furniture workflow. Keep user intent, the Feature Tree, generated
source, and CAD artifacts as separate layers.

## Core rules

- Default to a confirmable Design Intent before CAD. If the user explicitly
  requests an end-to-end run and the request is complete, continue without an
  extra approval stop.
- Use millimeters unless the user specifies another unit.
- Interpret furniture dimensions as `W x D x H`: X width from left to right, Y
  depth from front to back, and Z height upward.
- Use the lower-left ground corner of the finished furniture envelope as
  `(0, 0, 0)`. Do not silently switch to a centered origin.
- Use `T` or a named thickness field for board thickness; do not overload
  furniture depth.
- Preserve unresolved decisions as `null` at the intent stage. Ask one focused
  question only when fit, ergonomics, safety, or fabrication would otherwise be
  materially wrong.
- Treat the intent as the editable source of truth. Do not hand-edit generated
  Python, STEP, topology GLB, or other derived artifacts.
- Never imply that an unsupported furniture type can be generated. The current
  planner accepts only `table`.

## Workflow

1. Read `references/design-intent.md` and capture the request at the intent
   level. Use the wardrobe template and schema only for wardrobe requests.
2. State important assumptions and unresolved fit- or safety-critical fields.
3. Stop for confirmation unless the user already requested an end-to-end run
   with sufficient parameters.
4. Before planning or generation, read `references/workspace-pipeline.md`.
5. Convert an approved, supported intent into the exact executable input
   contract. Keep semantic decisions in the intent; keep geometry sequencing in
   the Feature Tree.
6. Generate through the workspace entry point. Do not bypass the planner,
   emitter, or CAD bridge with improvised one-off CAD code.
7. Verify the command result and all required artifacts. Report unsupported
   types or validation failures plainly instead of fabricating success.

## Response boundaries

For an intent-only request, return:

- the filled Design Intent;
- a short list of assumptions or unresolved fields;
- one confirmation question.

For an explicit generation request, return:

- the normalized intent and important assumptions;
- the generation/validation result;
- links or paths to the produced artifacts.
