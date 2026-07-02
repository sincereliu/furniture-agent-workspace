# Workspace Furniture Pipeline

Read this reference before running planning or CAD generation.

## Current capability

The executable vertical slice supports only a basic rectangular `table`.
`packages/furniture-planner/planner.py` rejects every other `type`.

The accepted input is JSON:

```json
{
  "type": "table",
  "width": 1200,
  "depth": 700,
  "height": 750,
  "top_thickness": 30,
  "leg_size": 60,
  "leg_inset": 50
}
```

All numeric fields are millimeters. `width`, `depth`, and `height` are required.
The planner defaults `top_thickness` to `30`, `leg_size` to `60`, and
`leg_inset` to `50`.

The planner also enforces:

- every size is positive;
- `leg_inset` is non-negative;
- `height > top_thickness`;
- width and depth can each contain two insets and one leg size.

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

Do not send furniture JSON directly to text-to-cad and do not modify the
external submodule for ordinary furniture generation.

## Verification

Run the project verification workflow when changing the pipeline:

```powershell
pwsh -File scripts\smoke_test.ps1
```

For a single generation, require a zero exit code and verify that the reported
STEP and topology artifacts exist and are non-empty.
