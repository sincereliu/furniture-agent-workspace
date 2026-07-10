# Furniture skill runtime

This is the `furniture-cad` skill's private runtime package. Keeping it beside
the skill avoids splitting one workflow across root-level `packages/`,
`scripts/`, and `tests/` directories:

1. `design_*` — Design Intent and executable dimensions.
2. `layout_*` — layout planning and cabinet placement.
3. `panel_*` — panel semantics and production records.
4. `manufacturing_*` — edge banding, drilling, hardware, and BOM policy.
5. `feature_tree_*` — Feature Tree construction and CAD-source emission.
6. `cad_bridge.py` — invocation and verification of external STEP generation.
7. `workflow_*` — orchestration, revisions, validation, and artifact lineage.

`planner.py` is the narrow stateless planning facade. Furniture JSON must pass
through planning and Feature Tree generation before `cad_bridge.py` calls the
external `text-to-cad` engine.
