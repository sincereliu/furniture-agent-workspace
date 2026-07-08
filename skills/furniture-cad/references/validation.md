# Validation

Use this reference before reporting a plan, manufacturing result, generated
geometry, or artifact as successful. Validation answers: "Which gates must
pass?"

This file owns cross-layer acceptance gates. It does not define user intent,
layout policy, panel records, manufacturing rules, Feature Tree schema, runtime
commands, or STEP entities.

## Cross-layer gates

Before calling a result ready for the next layer, verify the relevant gates:

1. Design Intent records the requested furniture, dimensions, constraints,
   assumptions, and unresolved decisions without hidden defaults.
2. Layout Planning keeps zones, openings, clearances, and installation context
   within the finished envelope.
3. Panel Planning gives each panel a semantic role, positive finished
   dimensions, quantity, orientation, placement, and annotations.
4. Manufacturing Policy states whether material, edge banding, joinery,
   hardware, tolerances, and BOM records are preliminary or accepted.
5. Feature Tree modeling semantics preserve dependencies and do not invent
   unsupported runtime capabilities.
6. Runtime support is verified against the live planner and emitter before
   promising generation.
7. Generated artifacts are reported only when the command actually created
   them and they exist.

## Cabinet-specific gates

- Mating faces and clearances agree with the chosen construction policy.
- Shelves and dividers do not intersect the selected back strategy or door
  envelope.
- Door gaps, door count, and opening strategy are resolved.
- Wall cabinets and tall furniture include fixing and load assumptions.
- Panel, BOM, edge-banding, and hardware outputs come from one approved plan.
- Provisional software defaults have been replaced or accepted for the
  manufacturing context.

## Reporting boundary

- Report only commands, validations, and artifacts that actually ran or exist.
- Do not call BOM, edge-banding, hardware, or cut-list output
  manufacturing-ready until the relevant manufacturing policy and validation
  gates are accepted.
