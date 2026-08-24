---
name: frontend-pattern-discovery
description: Identify the architectural and business problems, before any pattern is named.
---

# Frontend Pattern Discovery

## Purpose

Identify the architectural and business problems, before any pattern is named.

## Required Rules

- `.ai-agent/frontend-engineering/rules/pattern-selection.md`

## Steps

1. Analyze module boundaries, component boundaries, state boundaries, data flow, event flow, async flow, dependency graph, rendering flow, API boundaries, business logic, UI logic, infrastructure logic, extension points, variation points and performance bottlenecks.
2. Describe the actual problems. Do NOT immediately assign design patterns.
3. Separate problems observed in the codebase from problems inferred from the request wording.
4. Assess problem complexity; it sets the over-engineering bar for every later step.

## Output

- ProblemModel
- DependencyModel
- VariationModel
- DataFlowModel
- StateModel
- InteractionModel
- ArchitectureModel
