# Layout Planning

Use this reference after Design Intent and before Panel Planning.
Layout Planning answers: "How is the furniture organized?"

This file owns spatial organization: zones, compartments, openings, shelves,
drawers, doors, hanging areas, service clearances, and furniture-family layout
choices. It does not define physical panel records, manufacturing allowances,
Feature Tree operations, CAD solids, runtime commands, or validation results.

## Coordinate convention

- Use millimeters unless the user explicitly requests another unit.
- Interpret overall dimensions as `W x D x H`: X left to right, Y rear to
  user-facing front, and Z upward.
- Use the lower-left-rear ground corner of the finished envelope as
  `(0, 0, 0)`.
- Describe layout regions as envelope ranges and offsets. Do not convert them
  into CAD primitive centers in this layer.

## Resolve for layout

- Whether dimensions describe the finished envelope, carcass, internal
  clearance, or installation opening.
- The major organization: open bays, doors, shelves, dividers, drawers,
  hanging zones, service spaces, or decorative zones.
- Door strategy at the layout level: open, hinged, sliding, overlay, inset,
  count, and required clearances.
- Shelf or divider strategy at the layout level: fixed, adjustable, count,
  approximate spans, and load-sensitive zones.
- Base strategy at the layout level: floor-standing sides, legs, plinth, or
  toe-kick.
- Installation context: wall fixing zones, anti-tip needs, service gaps, room
  obstacles, and access constraints.

## Family guidance

### Floor cabinet

- Resolve whether overall height includes plinth, legs, countertop, or
  decorative panels.
- Keep door and drawer fronts above an exposed toe-kick zone.
- Treat the base/plinth choice as an explicit layout decision, not a universal
  rule.
- Floor cabinets may include drawers, dividers, shelves, and hanging rods as
  optional layout zones when requested.

### Wall cabinet

- Do not add a toe-kick zone.
- Treat wall fixing, expected load, substrate, and installation clearance as
  safety-critical unresolved layout fields when unknown.
- Include lighting recesses, fillers, and service gaps only when requested.

## Boundary

- Do not define panel roles, panel quantities, finished panel dimensions,
  edge-banding policy, drilling, hardware counts, Feature Tree nodes, CAD API
  calls, STEP entities, or runtime artifact paths.
- Pass resolved layout decisions to Panel Planning.
