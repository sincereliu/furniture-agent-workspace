# CAD bridge

This package provides a thin adapter layer between the furniture agent and the external text-to-cad repository.

## How it works

1. The furniture agent creates a structured spec.
2. The bridge writes that spec to a JSON request file.
3. The bridge invokes an external command configured by the environment or by the caller.
4. The result is returned in a stable, project-specific shape.

## Example

```python
from pathlib import Path
import importlib.util

module_path = Path("packages/cad-bridge/adapter.py")
spec = importlib.util.spec_from_file_location("cad_bridge_adapter", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

bridge = module.CadBridge(command_template="python {repo}/scripts/whatever.py --request {request} --output {output}")
result = bridge.generate({"type": "table", "width": 1200, "depth": 700, "height": 750})
print(result)
```

In practice, you can point the bridge to the specific CLI or Python entrypoint that the external repository exposes.
