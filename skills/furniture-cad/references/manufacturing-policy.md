# Manufacturing Policy

Use this reference after Panel Planning when manufacturing assumptions, BOM
reasoning, or fabrication caveats matter. Manufacturing Policy answers: "How
should it be manufactured?"

This file owns material and process policy. It does not own user intent,
layout organization, panel decomposition, Feature Tree operations, CAD
geometry, runtime commands, or artifact validation.

## Resolve policy

- Material family, grade, thickness policy, grain direction, visible faces, and
  finish expectations.
- Edge banding policy: which exposed edges need banding, banding thickness, and
  whether allowances are preliminary or accepted.
- Joinery policy: screws, dowels, cams, dados, rabbets, grooves, glue, or other
  construction assumptions.
- Hardware policy: hinges, slides, pulls, shelf pins, wall fixing, anti-tip
  hardware, and load assumptions.
- Tolerances and clearances: door gaps, reveal, installation clearance,
  service gaps, floor/wall unevenness, and safety margins.
- BOM policy: whether records are preliminary estimates, accepted purchasing
  records, or manufacturing-ready records.

## Cabinet guidance

- Back strategy may be applied, inset, rebated, grooved, or omitted; keep the
  selected policy explicit.
- Toe-kick, plinth, leg, and base hardware assumptions must be explicit for
  floor cabinets.
- Wall cabinets need explicit fixing, substrate, load, and installation
  assumptions before being called manufacturing-ready.

## Boundary

- Do not create or alter panel roles, panel counts, layout zones, Feature Tree
  nodes, CAD operations, STEP entities, executable JSON, or runtime artifact
  paths.
- Treat package defaults as software behavior, not factory-approved standards.
- Treat hardware estimates, edge banding, and tolerances as preliminary until
  the user accepts the relevant manufacturing policy.
