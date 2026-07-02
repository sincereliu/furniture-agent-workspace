# furniture-agent-workspace

This workspace is a scaffold for a furniture CAD agent system with a layered architecture.

## Architecture overview

- Workspace acts as the top-level engineering project.
- external/text-to-cad is the external CAD engine dependency.
- packages/cad-bridge isolates the external CAD integration and keeps the rest of the system decoupled.
- packages/furniture-schema defines the furniture parameter model.
- packages/furniture-planner generates the feature tree from the spec.
- validation performs checks and repair operations.
- services/furniture-agent orchestrates the full workflow.
- apps/web or apps/cli provide user-facing entry points.
- skills/furniture-cad stores reusable LLM rules and domain guidance.

## Suggested flow

1. A user request enters through web or CLI.
2. The agent builds a structured specification from the request.
3. The planner converts the specification into a feature tree.
4. Validation checks the plan and repairs issues when needed.
5. The CAD bridge invokes the external engine to produce the final result.
