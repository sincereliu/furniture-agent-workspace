# Furniture Intake Routing

Read this reference for every new furniture request. Its job is to decide what
the agent must learn and which references or execution skills are needed.

## Select the intake template

| User request | Intake template | Additional furniture reference |
|---|---|---|
| table, desk-like rectangular table | `table-intake.yaml` | none |
| floor/base/storage cabinet | `floor-cabinet-intake.yaml` | `panel-cabinetry.md` |
| wall/hanging cabinet | `wall-cabinet-intake.yaml` | `panel-cabinetry.md` |
| wardrobe/closet | `wardrobe-intake.yaml` | `panel-cabinetry.md` |
| another furniture family | generic fields in `design-intent.md` | verify support |

Do not wait for every field before selecting the furniture references. The
family name is enough to route. Use missing fields to decide the next question.

## Select the stage

| Requested outcome | Load or invoke |
|---|---|
| discuss, design, clarify requirements | intake template + `design-intent.md` |
| cabinet structure, panels, BOM reasoning | above + `panel-cabinetry.md` |
| Feature Tree, CAD, STEP | above + `workspace-pipeline.md`; then external CAD skill |
| STEP visual review | CAD Viewer skill after an artifact exists |

## Apply the gates

1. **Routing gate:** furniture family and requested outcome are known.
2. **Intent gate:** dimensions and family-critical layout decisions are known,
   or explicitly recorded as unresolved.
3. **Execution gate:** every required flat runtime field is numeric and the
   requested variant matches a live template.
4. **Manufacturing gate:** material, joinery, hardware, edge banding,
   tolerances, installation, and safety assumptions are accepted.

Ask one focused question at a time. Prefer the missing answer that can change
the furniture family, finished envelope, major structure, or safety.

## Template semantics

- `routing` contains constants used to select references and runtime paths.
- `intent` contains user decisions; `null` means unresolved.
- `runtime` mirrors fields that can be normalized into executable JSON.
- `manufacturing` contains decisions that must not be guessed for a final BOM.
- `limits` warns when the current live template cannot express the full intent.

Never send an intake template directly to the planner. Normalize only its
`runtime` values to the flat JSON contract in `workspace-pipeline.md`.
