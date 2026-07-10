# furniture-agent service

FastAPI transport for the furniture workflow. Shared cabinet planning,
panelizing, and BOM logic lives in the stage-oriented
`skills/furniture-cad/scripts/furniture`
package; this service only validates HTTP input and maps results to API
responses.

The current `/api/plan-cabinet` route is a legacy stateless transport. New
Project/Revision workflows belong to
`skills/furniture-cad/scripts/furniture/workflow_orchestrator.py` and should be exposed here
through thin endpoints in a later service integration change; domain and
workflow rules must not be duplicated in the HTTP layer.

The current optional FastAPI entry point is
`skills/furniture-cad/scripts/server.py`; this directory no longer owns Python
code.
