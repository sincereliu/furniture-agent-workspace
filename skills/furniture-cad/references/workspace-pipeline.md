# Workspace Furniture Pipeline

Read this reference before claiming executable support, normalizing input,
running generation, or reporting runtime artifacts.

Workspace Pipeline answers: "What does the current workspace execute?"

This file owns runtime contracts, commands, generated artifact paths, and
current executable limits. It does not own user intent, layout planning, panel
semantics, manufacturing policy, Feature Tree design rules, or validation
gates.

## Current capability

The live entry point `skills/furniture-cad/scripts/furniture/planner.py` accepts:

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
`skills/furniture-cad/scripts/furniture/design_spec.py` (`CABINET_PRESETS` for per-type defaults,
dataclass fields for global constants). Do not ask the user to fill them unless
an override is requested or required by the design.

The executable contract is flat JSON.

Proceed to execution only when the overall dimensions are numeric and the
requested variant matches a live template. Otherwise stop at the appropriate
DDD planning layer and state the unsupported boundary.

## Generation

From the workspace root, run:

```powershell
.\.venv\Scripts\python.exe skills\furniture-cad\scripts\generate_furniture.py <spec.json> --force
```

Use `--name <artifact-name>` when the desired artifact name differs from the
spec filename. Names may contain only letters, numbers, hyphens, and
underscores.

The command writes to `generated/<artifact-name>/`:

- `<artifact-name>.feature-tree.json`;
- `<artifact-name>.bom.md`;
- `<artifact-name>.step`;
- the hidden adjacent Viewer topology GLB produced by the CAD bridge.

The derived build123d Python source is temporary and is written only under
`temp/cad-source/<artifact-name>/`. It must never be persisted under
`generated/`.

The legacy CLI does not create a Project/Revision record. The application-layer
`skills/furniture-cad/scripts/furniture/workflow_orchestrator.py` owns the traceable workflow and
writes `design-intent.json`, `feature-tree.json`, and `bom.md` into a revision
directory. It writes derived CAD source under `temp/cad-source/<revision-id>/`
before optionally invoking the CAD bridge.
`skills/furniture-cad/scripts/furniture/workflow_store.py` persists the Project/Revision state as
`project.json`.

The runtime pipeline is:

`intent JSON -> existing furniture planner -> conceptual Panel Plan -> Feature
Tree -> furniture CAD emitter -> text-to-cad bridge -> STEP + Viewer topology`

The conceptual Panel Plan is represented by the existing planner flow. It does
not add a new runtime command, planner interface, executable JSON shape,
Feature Tree operation set, or STEP entity model.

Do not send furniture JSON directly to text-to-cad. Do not bypass the planner
with one-off CAD source or modify the external submodule for ordinary furniture
generation.

## Runtime panel and BOM path

`skills/furniture-cad/scripts/furniture/layout_pipeline.py` exposes `plan_cabinet()` for the two
cabinet types. It returns placements, panel records, and an estimated BOM.
Treat those panel records as the current runtime expression of Panel Planning,
not as a separate executable stage.
The main generation CLI persists a BOM Markdown report, but it does not persist
a cut-list artifact. Do not report a cut list unless a command actually created
one.
