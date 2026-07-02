# Furniture Design Intent

Use this reference before planning geometry. The intent records what the
furniture should be; it is not a modeling order, cut list, or CAD program.

## Output contract

Capture:

- furniture type and user-facing purpose;
- overall `W x D x H` dimensions, with unresolved values as `null`;
- the meaning of any ambiguous dimension labels;
- functional requirements and major layout choices;
- visible style choices;
- high-level structural strategy;
- fit, ergonomic, safety, and fabrication constraints;
- assumptions that need user confirmation.

Do not add part coordinates, panel cut sizes, hardware quantities, CAD API
calls, STEP paths, or a Feature Tree at this stage.

For interactive design requests, stop after the intent unless the user
explicitly requested an end-to-end generation run.

## Coordinate and dimension convention

- `width_mm`: front horizontal span on X.
- `depth_mm`: front-to-back span on Y.
- `height_mm`: vertical span on Z.
- Overall dimensions describe the finished outer envelope unless explicitly
  labeled as internal clearance.
- The origin is the lower-left ground corner of the finished envelope.

When the user gives three unlabeled dimensions, tentatively map them to
`W x D x H`, state that assumption, and correct it if the furniture context
makes the mapping implausible.

## Type-specific resources

For a wardrobe, fill
`design-intent/templates/wardrobe.yaml` and keep it consistent with
`design-intent/schemas/wardrobe.yaml`. The wardrobe resource is an intent
contract only; the current workspace planner cannot generate wardrobe CAD.

For a rectangular table that will be generated, capture the same intent in the
flat executable JSON fields documented in `references/workspace-pipeline.md`.
The optional construction fields are still design decisions and should be
confirmed or clearly stated as assumptions.

For other furniture types, use a concise generic intent with the contract above
and stop before claiming CAD support.
