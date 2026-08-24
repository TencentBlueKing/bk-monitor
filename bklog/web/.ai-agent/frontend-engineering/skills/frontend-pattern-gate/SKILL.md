---
name: frontend-pattern-gate
description: Decide whether the frontend design-pattern system may run at all.
---

# Frontend Pattern Gate

## Purpose

Decide whether the frontend design-pattern system may run at all.

## Required Rules

- `.ai-agent/frontend-engineering/rules/pattern-gate.md`

## Steps

1. Run `aafe pattern gate "<request>"`.
2. disabled → stop. Handle the task as ordinary development work.
3. ambiguous → ask the user whether they want design-pattern analysis. Do not activate silently.
4. enabled → record the decision and continue to Discovery, not to Selection.

## Output

- PatternGateDecision { enabled, decision, scope, requestedCapabilities, signals }
