# Architecture

The repository is organized as a layered system for furniture CAD generation.

## Layer responsibilities

- Workspace: the top-level engineering project that coordinates all modules.
- external/text-to-cad: the external CAD engine used for geometry generation.
- packages/cad-bridge: an adapter layer that isolates the external dependency and exposes a stable interface.
- packages/furniture-schema: the canonical schema for furniture parameters and input contracts.
- packages/furniture-planner: converts a structured spec into a feature tree representation.
- validation: checks constraints, validates the plan, and applies repair strategies.
- services/furniture-agent: the orchestrator that coordinates intent parsing, planning, validation, and execution.
- apps/web and apps/cli: user-facing interfaces for interaction.
- skills/furniture-cad: reusable LLM rules and domain knowledge for furniture generation.

## Recommended execution flow

1. The user sends a request through a web app or CLI.
2. The agent interprets the request and produces a structured spec.
3. The planner creates a feature tree from the spec.
4. Validation checks the tree and repairs invalid or incomplete parts.
5. The execution layer calls the CAD bridge, which talks to the external CAD engine.
6. The final CAD artifact is returned to the user.
