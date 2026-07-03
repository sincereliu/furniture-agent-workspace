# Furniture Design Intent

Use this reference before planning geometry. Design Intent records what should
be built and why. It is not a Feature Tree, panel cut list, or CAD program.

First select the matching intake template through `intake-routing.md`. Fill its
`intent` section during discussion and its `runtime` section only when
generation is requested. A template is a question and routing contract, not a
second executable schema.

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

- Table: top form, support/leg arrangement, clearances, and construction.
- Floor or wall cabinet: carcass construction, back, plinth/toe-kick, doors,
  shelves/dividers, installation, and material thicknesses.
- Wardrobe: door system, hanging/shelf/drawer zones, anti-tip or wall fixing,
  compartment spans, and clothing clearance.
- Other types: capture the generic intent, then verify runtime support before
  promising generation.
