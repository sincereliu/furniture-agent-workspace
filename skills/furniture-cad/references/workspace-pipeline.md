# Workspace Furniture Pipeline

Read this reference before claiming executable support, normalizing input,
running generation, or reporting artifacts.

## Current capability

The live entry point `packages/furniture_planner/planner.py` accepts:

- `floor_cabinet`: fixed carcass template with back, toe-kick, shelves, doors;
- `wall_cabinet`: fixed carcass template with back, shelves, doors, no toe-kick.

These are narrow templates, not arbitrary furniture configurators. Inspect
`planner.py` and the corresponding template before promising a layout variant.
Other furniture families are intent/modeling-plan only until implemented.

## Executable JSON

All numeric values are millimeters. Every supported type requires:

```json
{
  "type": "floor_cabinet",
  "width": 800,
  "depth": 600,
  "height": 2000,
  "board_thickness": 18,
  "back_thickness": 9,
  "door_thickness": 18,
  "toe_kick_height": 50,
  "back_offset": 18,
  "door_margin": 1.5,
  "door_hinge_gap": 2,
  "shelf_count": 4,
  "n_doors": 2
}
```

For `wall_cabinet`, the default dimensions are narrower: `width` 800, `height`
900, `depth` 350, `toe_kick_height` 0, `shelf_count` 1.

Default dimensions and parameters live in
`packages/furniture_schema/spec.py` (`CABINET_PRESETS` for per-type defaults,
dataclass fields for global constants). Do not ask the user to fill them unless
an override is requested or required by the design.

The executable contract is flat JSON.

Proceed to execution only when the overall dimensions are numeric and the
requested variant matches a live template. Otherwise stop at intent or
modeling-plan work and state the unsupported boundary.

## Generation

From the workspace root, run:

```powershell
.\.venv\Scripts\python.exe scripts\generate_furniture.py <spec.json> --force
```

Use `--name <artifact-name>` when the desired artifact name differs from the
spec filename. Names may contain only letters, numbers, hyphens, and
underscores.

The command writes to `generated/<artifact-name>/`:

- `<artifact-name>.intent.json`;
- `<artifact-name>.feature-tree.json`;
- `<artifact-name>.py`;
- `<artifact-name>.step`;
- the hidden adjacent Viewer topology GLB produced by the CAD bridge.

The pipeline is:

`intent JSON -> furniture planner -> Feature Tree -> furniture CAD emitter ->
text-to-cad bridge -> STEP + Viewer topology`

Do not send furniture JSON directly to text-to-cad. Do not bypass the planner
with one-off CAD source or modify the external submodule for ordinary furniture
generation.

## Panel and BOM path

`packages/furniture_pipeline/cabinet.py` exposes `plan_cabinet()` for the two
cabinet types. It returns placements, panel records, and an estimated BOM.
The main generation CLI does not currently persist BOM or cut-list artifacts.
Do not report such files unless a command actually created them.

Treat hardware estimates, edge banding, and tolerances as preliminary until the
user accepts the relevant manufacturing policy.

## Verification

Run the test suite after changing the skill's capability claims or pipeline:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

For a real CAD generation, require a zero exit code and verify that the
reported STEP and topology artifacts exist and are non-empty. Use
`pwsh -File scripts\smoke_test.ps1` when validating the full external CAD
integration.