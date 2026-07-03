# furniture-agent service

FastAPI transport for the furniture workflow. Shared cabinet planning,
panelizing, and BOM logic lives in `packages/furniture_pipeline`; this service
only validates HTTP input and maps pipeline results to API responses.
