# Furniture Design Intent

Use this reference before layout planning, panel decomposition, manufacturing
policy, Feature Tree planning, or runtime execution.
Design Intent answers: "What furniture should be built?"

Design Intent records the user's desired furniture and the reasons behind it.
It is not a Layout Plan, Panel Plan, Manufacturing Policy, Feature Tree,
runtime input, panel cut list, or CAD program.

## Capture

- `type`: furniture family in user language.
- `purpose`: user-facing use and priorities.
- `overall_size`: finished-envelope `width_mm`, `depth_mm`, and `height_mm`;
  keep unknown values as `null`.
- `layout`: desired doors, compartments, shelves, drawers, hanging zones, or
  other user-facing organization decisions.
- `appearance`: visible style and finish choices that affect the design.
- `structure`: high-level construction preferences, without decomposing them
  into layout zones, physical panels, or modeling operations.
- `constraints`: room fit, ergonomics, safety, installation, fabrication, and
  material requirements.
- `assumptions`: defaults tentatively accepted for this request.
- `unresolved`: decisions still requiring confirmation.

State each assumption beside the affected field. Do not hide assumptions in a
closing paragraph.

## Dimension convention

- `width_mm`: left-to-right span on X.
- `depth_mm`: rear-to-front span on Y.
- `height_mm`: vertical span on Z.
- Overall dimensions mean the finished outer envelope unless explicitly labeled
  as internal clearance, carcass size, or room opening.

When the user gives three unlabeled dimensions, tentatively map them to
`W x D x H`, state that assumption, and correct it if the furniture context
makes the mapping implausible.

## Boundaries

- Treat intent as ready for the next planning layer when dimensions and
  family-critical layout decisions are known or explicitly recorded as
  unresolved.
- Stop before panel decomposition. Do not add panel roles, quantities,
  placements, part coordinates, cut sizes, hardware quantities, manufacturing
  policies, CAD API calls, output paths, or a Feature Tree at this stage.
- For interactive design discussion, stop after intent unless the user
  requested planning or end-to-end generation.

## Family-specific decisions

- **Floor cabinet**: carcass construction, back, plinth/toe-kick, doors,
  shelves/dividers, installation, and material thicknesses.
- **Wall cabinet**: carcass construction, back, doors, shelves/dividers,
  wall fixing, substrate, installation clearance, and material thicknesses.
  No toe-kick.
- Other types: capture the generic intent and leave execution support to the
  Workspace Pipeline layer.
