---
name: furniture-cad
description: Turn furniture requests into staged, confirmable design intent, furniture plans, and validated CAD through this workspace. Use for tables, wardrobes, floor or wall cabinets, shelves, desks, beds, panel-cabinet structure, dimensions, layouts, Feature Trees, preliminary panel/BOM reasoning, or STEP generation. Route by stage and furniture family; only claim executable CAD support that the live workspace actually implements.
---

# Furniture CAD

Keep user intent, domain planning, the Feature Tree, generated source, and CAD
artifacts as separate layers. Treat this skill as the agent's routing and domain
guidance layer, not as a second CAD engine.

## Invariants

- Use millimeters unless the user specifies another unit.
- Interpret overall dimensions as `W x D x H`: X left-to-right, Y from the
  rear toward the user-facing front, and Z upward.
- Use the lower-left-rear ground corner of the finished furniture envelope as
  `(0, 0, 0)`. Compute centers only inside an implementation that requires them.
- Use `T` or a named thickness field for material thickness; never overload
  furniture depth.
- Preserve unresolved decisions as `null` at the intent stage.
- Treat the approved intent as the editable source of truth. Do not hand-edit
  derived Python, STEP, topology GLB, BOM, or cut-list artifacts.
- Report only validations and artifacts that actually ran or exist.

## Route the request

1. **Intent or design discussion:** Read `references/design-intent.md`. Return a
   confirmable Design Intent and stop unless the user requested more.
2. **Panel cabinet, wardrobe, floor cabinet, or wall cabinet:** Also read
   `references/panel-cabinetry.md`. Use its structure rules as planning
   knowledge, not as proof that generation is implemented.
3. **Feature Tree or modeling plan:** Convert an approved intent into semantic
   parts, dependencies, sizes, and lower-left positions. Keep manufacturing
   annotations separate from geometry.
4. **CAD generation:** Read `references/workspace-pipeline.md`, then use the
   workspace entry point. The live executable planner currently supports only a
   basic rectangular `table`.
5. **BOM, panel list, edge banding, or manufacturing output:** Produce only a
   clearly labeled preliminary result unless the live package implements and
   validates that output. Do not treat migrated defaults as a factory-approved
   standard without user confirmation.

## Interaction rules

- Default to Design Intent before geometry. If the user explicitly requests an
  end-to-end run and supplies enough information for a supported type, continue
  without an extra approval stop.
- Ask one focused question only when fit, ergonomics, safety, structure, or
  fabrication would otherwise be materially wrong.
- State assumptions beside the affected field instead of hiding them in prose.
- For unsupported types, complete the useful intent or planning work and state
  the exact execution boundary plainly.

## Generate and verify

For a supported generation request:

1. Normalize the approved intent to the executable input contract.
2. Run the planner, emitter, and CAD bridge in that order.
3. Do not bypass the pipeline with one-off CAD code or direct edits to
   `external/text-to-cad`.
4. Require a successful command result and non-empty required artifacts.
5. Return the normalized intent, important assumptions, validation result, and
   artifact paths.

For an intent-only request, return the filled intent, unresolved fields, and at
most one confirmation question.
