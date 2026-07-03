# Furniture Intake Routing

Read this reference for every new furniture request. Its job is to decide what
the agent must learn and which references or execution skills are needed.

## Select the intake template

| User request | Intake template | Additional furniture reference |
|---|---|---|
| table, desk-like rectangular table | `intake/table.yaml` | none |
| floor/base/storage cabinet | `intake/floor-cabinet.yaml` | `panel-cabinetry.md` |
| wall/hanging cabinet | `intake/wall-cabinet.yaml` | `panel-cabinetry.md` |
| wardrobe/closet | `intake/wardrobe.yaml` | `panel-cabinetry.md` |
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
3. **Execution gate:** overall dimensions are numeric and the requested variant
   matches a live template.
4. **Manufacturing gate:** material, joinery, hardware, edge banding,
   tolerances, installation, and safety assumptions are accepted.

Ask one focused question at a time. Prefer the missing answer that can change
the furniture family, finished envelope, major structure, or safety.

## Template boundary

- Keep only furniture type, finished size, and a few family-defining choices.
- Use `null` for a user decision that is not known yet.
- Do not include board thickness, back offset, gaps, hardware, edge banding,
  tolerances, or other program-owned defaults.
- Ask about a technical default only when the user wants to override it or when
  it blocks fit, safety, or the requested structure.

Never send an intake template directly to the planner. The program must read
its own defaults and normalize the approved minimal intent to the executable
contract.
