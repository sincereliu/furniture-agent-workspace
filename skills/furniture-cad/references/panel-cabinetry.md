# Panel Planning

Read this reference for floor cabinets, wall cabinets, storage cabinets,
panel lists, edge banding, or preliminary BOM reasoning.

Panel Planning answers: "What physical furniture components exist?"

This file owns the manufacturing representation of furniture: semantic panels,
component relationships, and manufacturing caveats. A Panel represents a
manufacturing part, not a CAD solid.

The live planner owns placement formulas. `packages/furniture_schema/spec.py`
owns software defaults (dataclass fields + `CABINET_PRESETS`). Do not copy
either into this reference.

## Layer boundary

Panel Planning comes after Design Intent and before Feature Tree generation.
It converts furniture intent and layout choices into semantic furniture
components.

Typical panel roles include:

- left side
- right side
- top
- bottom
- back
- shelf
- divider
- door
- drawer front
- stretcher
- toe kick

Each Panel should conceptually contain:

- semantic role
- finished dimensions
- thickness
- material
- quantity
- orientation
- placement
- manufacturing annotations

Do not define CAD geometry, Feature Tree operations, STEP entities, or runtime
planner interfaces here.

## Coordinate convention

Use the lower-left-rear ground corner of the finished envelope. X goes right,
Y goes toward the user-facing front, and Z goes upward. Every panel position is
its minimum corner. Back features therefore have smaller Y values than doors.

Do not restate numeric placement formulas here. Inspect
`packages/furniture_planner/cabinet_planner.py` and its tests when exact
geometry matters.

## Resolve before Panel Planning

- Whether dimensions describe the finished envelope, carcass, internal
  clearance, or installation opening.
- Carcass construction: top/bottom between sides or covering sides.
- Back strategy: applied, inset, rebated, grooved, or omitted.
- Base strategy: floor-standing sides, legs, plinth, or toe-kick.
- Door strategy: overlay/inset, hinged/sliding/open, count, gaps, and clearances.
- Shelf/divider layout: fixed or adjustable, spans, loads, and clearances.
- Material, thickness, grain, edge banding, joinery, hardware, and tolerances.
- Installation and safety: wall fixing, anti-tip, service gaps, and expected
  loads.

## Family guidance

### Floor cabinet

- Resolve whether overall height includes plinth, legs, countertop, or
  decorative panels.
- Keep doors above an exposed toe-kick.
- Treat the base/plinth choice as an explicit decision, not a universal rule.
- Floor cabinets may include drawers, dividers, and hanging rods as optional
  components.

### Wall cabinet

- Do not add a toe-kick. Set `toe_kick_height` to 0.
- Treat wall fixing, load, substrate, and installation clearance as
  safety-critical unresolved fields when unknown.
- Model lighting recesses, fillers, and service gaps only when requested.

## Panel Planning rules

- Represent each panel by semantic role, finished dimensions, thickness,
  material, quantity, orientation, placement, and manufacturing annotations.
- Keep solid geometry, cut dimensions, edge-banding allowances, drilling, and
  hardware as separate data.
- Derive positions from carcass relationships and envelope ranges.
- Keep shelves/dividers clear of the selected back construction.
- Keep BOM and hardware records separate from CAD solids.

## Validation gates

Before calling a result manufacturing-ready, verify:

1. every panel has positive dimensions and stays within its intended envelope;
2. mating faces and clearances agree with the chosen construction;
3. shelves and dividers do not intersect the back panel or doors;
4. door gaps, counts, and opening strategy are resolved;
5. wall cabinets and tall furniture include fixing/load assumptions;
6. the live planner supports the requested variant, not merely the family name;
7. panel, BOM, edge-banding, and hardware outputs come from one approved plan;
8. provisional software defaults have been replaced or accepted for the
   manufacturing context.
