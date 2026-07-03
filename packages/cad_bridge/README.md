# CAD bridge

This package invokes the external text-to-cad STEP CLI without modifying the
external submodule.

The bridge accepts a generated Python source that defines `gen_step()`. It runs
the external `skills/cad/scripts/step` launcher from the furniture workspace,
then verifies that both the STEP file and its adjacent hidden Viewer topology
GLB exist and are non-empty.

It does not send furniture JSON directly to text-to-cad. Furniture intent is
planned into a Feature Tree and translated into build123d source before the
bridge runs.

```python
bridge = CadBridge()
result = bridge.generate_from_source(
    "generated/cabinet/cabinet.py",
    "generated/cabinet/cabinet.step",
)
```
