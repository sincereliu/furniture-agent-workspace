# furniture-agent-workspace

This workspace is a scaffold for a furniture CAD agent system with a layered architecture.

## Architecture overview

- Workspace acts as the top-level engineering project.
- external/text-to-cad is the external CAD engine dependency.
- packages/cad_bridge isolates the external CAD integration and keeps the rest of the system decoupled.
- packages/furniture_schema defines the furniture parameter model.
- packages/furniture_planner generates structural plans from a spec.
- packages/furniture_pipeline owns the reusable cabinet planning, panelizing, and BOM use case.
- validation performs checks and repair operations.
- services/furniture-agent exposes the workflow through HTTP.
- apps/web or apps/cli provide user-facing entry points.
- skills/furniture-cad stores reusable LLM rules and domain guidance.

## Suggested flow

1. A user request enters through web or CLI.
2. The agent builds a structured specification from the request.
3. The planner converts the specification into a feature tree.
4. Validation checks the plan and repairs issues when needed.
5. The CAD bridge invokes the external engine to produce the final result.

## Current executable vertical slice

The first working vertical slice supports a basic rectangular table:

```powershell
.\.venv\Scripts\python.exe scripts\generate_furniture.py examples\table_basic.json --force
```

This writes the normalized intent, Feature Tree, generated build123d source,
STEP file, and hidden Viewer topology GLB under
`generated\table_basic\`. The external text-to-cad submodule remains
unmodified.

Run the unit tests and real CAD smoke generation with:

```powershell
pwsh -File scripts\smoke_test.ps1
```
