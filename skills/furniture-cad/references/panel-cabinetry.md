# Panel Cabinetry

Read this reference for wardrobes, floor cabinets, wall cabinets, storage
cabinets, panel lists, edge banding, or preliminary BOM reasoning.

The rules below are distilled from the earlier `furniture` skill. They are
domain knowledge for intent and planning. The old Python generator is not part
of this skill and is not a runtime dependency.

## Coordinate convention

This workspace uses the lower-left **rear** ground corner of the finished
envelope:

- X: left to right;
- Y: rear toward the user-facing front;
- Z: floor upward.

This matches the earlier skill. Preserve its Y direction when migrating
structural formulas: back-panel features stay at smaller Y values and doors
stay at larger Y values. Still port behavior through semantic planner features
and range-based tests rather than copying CAD code wholesale.

## Structural families

### Floor cabinet

- Use floor-standing side panels.
- Place top and bottom panels between the sides unless the intent says
  otherwise.
- Include a plinth or toe-kick only when requested or accepted as a default.
- Keep doors above the toe-kick when the toe-kick is exposed.
- Resolve whether the finished height includes legs, plinth, countertop, or
  decorative panels.

### Wall cabinet

- Use full-height sides with top and bottom panels between them by default.
- Do not add a toe-kick.
- Capture wall fixing, load, and installation clearance as safety-critical
  unresolved fields when they are unknown.
- Treat an under-cabinet lighting recess as an explicit option.

### Wardrobe

- Start from a panel carcass, then describe hanging, shelf, and drawer zones
  explicitly.
- Do not reduce every wardrobe to “floor cabinet plus hanging rod”; door system,
  anti-tip fixing, compartment spans, and clothing clearance affect structure.
- Keep the existing wardrobe Design Intent template as the specialized intent
  contract. It does not prove wardrobe CAD support.

## Provisional defaults

Use these only as stated assumptions. Confirm them before a manufacturing-grade
BOM or cut list:

| Decision | Migrated default |
|---|---:|
| Carcass thickness | 18 mm |
| Back thickness | 9 mm |
| Door thickness | 18 mm |
| Toe-kick height | 50 mm |
| Back-panel recess from rear | 18 mm |
| Door perimeter margin | 1.5 mm |
| Door-to-carcass front gap | 2 mm |

Material grade, sheet size, grain direction, edge banding, hardware, tolerances,
and joinery belong in a versioned manufacturing policy or project spec. Do not
hard-code them in `SKILL.md` or duplicate them across planner and emitter code.

## Panel planning rules

- Represent each panel semantically: role, finished size, thickness, material,
  lower-left position, orientation, quantity, and manufacturing annotations.
- Keep geometric dimensions separate from cut dimensions and edge-banding
  allowances.
- Derive panel positions from carcass relationships and finished envelope
  ranges. Avoid center-origin explanations.
- Keep shelves and dividers clear of a recessed back panel.
- Treat doors as front-mounted components with explicit gaps and overlay/inset
  strategy.
- Keep BOM and hardware records separate from CAD solids. A visible model is not
  by itself a validated manufacturing result.

## Validation gates

Before claiming a cabinet plan is executable, verify:

1. every panel has positive dimensions and stays within its intended envelope;
2. mating faces and clearances agree with the chosen construction;
3. shelves and dividers do not intersect the back panel or doors;
4. door gaps, counts, and opening strategy are resolved;
5. wall cabinets and tall wardrobes include fixing/load assumptions;
6. the planner supports the furniture family;
7. BOM, edge banding, and hardware outputs are generated from the same approved
   plan rather than independently guessed.
