# Furniture skill map

## Canonical roots

| Repository path | Responsibility | Authority |
|---|---|---|
| `skills/furniture-cad` | Furniture intent, dimensions, coordinate conventions, cabinet structure, and workspace execution guidance | Furniture domain source |
| `external/text-to-cad/skills` | Generic CAD generation, inspection, validation, snapshots, exports, and Viewer workflows | CAD engine source |
| `external/text-to-cad/plugins/cad/skills` | Generated plugin bundle | Do not use as a separate local source |

## Routing

| Request | Load |
|---|---|
| Furniture discussion or Design Intent | `skills/furniture-cad/SKILL.md` and its Design Intent reference |
| Cabinet or wardrobe structure and placement | Furniture skill plus its cabinet references |
| Live workspace pipeline, BOM, or panelization | Furniture skill plus live `packages/`, `scripts/`, and `tests/` |
| Create or modify CAD, generate or inspect STEP | External `cad/SKILL.md` after furniture intent is settled |
| Review generated CAD visually | External `cad-viewer/SKILL.md` |
| Find an off-the-shelf component | External `step-parts/SKILL.md` |
| DXF, G-code, implicit CAD, or robot-description output | Matching external skill only when requested |

## Capability checks

Recheck these live surfaces instead of copying a support matrix into this
entry skill:

- `packages/furniture_planner/`
- `packages/furniture_pipeline/`
- `packages/furniture_panelizer/`
- `packages/furniture_cad_emitter/`
- `packages/cad_bridge/`
- `scripts/`
- `tests/`

The workspace evolves faster than its prose. When code, tests, and skill text
disagree, report the mismatch and use verified executable behavior as the
current boundary.
