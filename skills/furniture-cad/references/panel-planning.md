# Panel Planning

Use this reference after Layout Planning and before Manufacturing Policy or
Feature Tree planning. Panel Planning answers: "What physical furniture
components exist?"

This file owns the manufacturing representation of furniture as semantic
components. A Panel represents a manufacturing part, not a CAD solid.

## Layer boundary

Panel Planning converts Design Intent and Layout Planning decisions into
semantic furniture components. It does not define manufacturing rules, Feature
Tree operations, CAD geometry, STEP entities, runtime commands, or planner
interfaces.

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

## Panel rules

- Represent each panel by role and relationship to the finished envelope or
  layout zone.
- Use placement as a furniture-domain position, such as a minimum corner,
  envelope range, face, or relationship to another panel.
- Keep shelves and dividers clear of the selected back construction.
- Keep door and drawer fronts related to their opening strategy and clearance
  envelope.
- Keep BOM and hardware records separate from CAD solids.

## Boundary

- Do not define CAD primitives, boolean operations, Feature Tree dependencies,
  STEP entities, executable JSON, command lines, edge-banding allowances,
  drilling patterns, or factory approval.
- Refer material rules, tolerances, joinery, edge banding, and hardware policy
  to Manufacturing Policy.
- Refer modeling dependencies and CAD representation to Feature Tree.
