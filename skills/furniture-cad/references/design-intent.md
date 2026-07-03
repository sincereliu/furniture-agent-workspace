# Furniture Design Intent

Use this reference before planning geometry. Design Intent records what should
be built and why. It is not a Feature Tree, panel cut list, or CAD program.

## Capture

- `type`: furniture family in user language; also record the executable type
  when the runtime supports it.
- `purpose`: user-facing use and priorities.
- `overall_size`: finished-envelope `width_mm`, `depth_mm`, and `height_mm`;
  keep unknown values as `null`.
- `layout`: doors, compartments, shelves, drawers, hanging zones, or other
  major organization decisions.
- `appearance`: visible style and finish choices that affect the design.
- `structure`: high-level construction choices, without part coordinates.
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
- The origin is the lower-left-rear ground corner of the finished envelope.

When the user gives three unlabeled dimensions, tentatively map them to
`W x D x H`, state that assumption, and correct it if the furniture context
makes the mapping implausible.

## Boundaries

- Treat intent as ready for planning when dimensions and family-critical layout
  decisions are known or explicitly recorded as unresolved.
- Do not add part coordinates, cut sizes, hardware quantities, CAD API calls,
  output paths, or a Feature Tree at this stage.
- For interactive design discussion, stop after intent unless the user
  requested planning or end-to-end generation.
- For supported generation, normalize the approved intent to the flat JSON
  contract in `workspace-pipeline.md`; do not maintain a second furniture-type
  execution schema inside the skill.
- For unsupported furniture, keep the user-facing intent useful and explicitly
  separate it from executable support.

## Family-specific decisions

- **Floor cabinet**: carcass construction, back, plinth/toe-kick, doors,
  shelves/dividers, installation, and material thicknesses.
- **Wall cabinet**: carcass construction, back, doors, shelves/dividers,
  wall fixing, substrate, installation clearance, and material thicknesses.
  No toe-kick.
- Other types: capture the generic intent, then verify runtime support before
  promising generation.