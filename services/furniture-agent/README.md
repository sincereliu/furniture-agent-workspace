# furniture-agent service

FastAPI transport for the furniture workflow. Shared cabinet planning,
panelizing, and BOM logic lives in the stage-oriented `packages/furniture`
package; this service only validates HTTP input and maps results to API
responses.

The current `/api/plan-cabinet` route is a legacy stateless transport. New
Project/Revision workflows belong to
`packages/furniture/workflow_orchestrator.py` and should be exposed here
through thin endpoints in a later service integration change; domain and
workflow rules must not be duplicated in the HTTP layer.
