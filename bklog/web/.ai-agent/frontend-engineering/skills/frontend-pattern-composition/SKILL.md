---
name: frontend-pattern-composition
description: Compose the selected patterns into a coherent architecture.
---

# Frontend Pattern Composition

## Purpose

Compose the selected patterns into a coherent architecture.

## Required Rules

- `.ai-agent/frontend-engineering/rules/pattern-composition.md`
- `.ai-agent/frontend-engineering/rules/pattern-boundary.md`

## Steps

1. Assign every pattern an explicit responsibility and boundary.
2. Pull in required collaborators: a pattern missing its dependency is an incomplete design.
3. Detect conflicts — two patterns claiming the same responsibility — and resolve them explicitly.
4. Detect redundancy — interchangeable alternatives to the same problem — and drop the weaker one.
5. Draw the composition graph: relations, flows, lifecycle and failure behavior.
6. Report total complexity. Pattern count is not a quality metric (RULE-012).

## Output

- PatternComposition { patterns, relations, responsibilities, boundaries, flows, conflicts, redundantPatterns, rationale }
