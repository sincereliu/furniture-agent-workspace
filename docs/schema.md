# Schema

The schema layer defines the shared contract for furniture generation.

## Core idea

Furniture requests should be normalized into a structured spec before planning or execution begins.

## Suggested schema concepts

- furniture type, such as table, bed, or cabinet
- dimensions including width, depth, height
- structural options such as materials, joints, or style hints
- constraints and validation rules
- output expectations for the CAD generation step

## Design intent

The schema should stay stable and independent from the CAD engine. This allows the planner, validator, and agent to operate on a clear model without being tightly coupled to external tools.
