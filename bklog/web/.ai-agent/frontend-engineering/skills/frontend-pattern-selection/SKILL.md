---
name: frontend-pattern-selection
description: Score candidate patterns against the identified problems.
---

# Frontend Pattern Selection

## Purpose

Score candidate patterns against the identified problems.

## Required Rules

- `.ai-agent/frontend-engineering/rules/pattern-selection.md`
- `.ai-agent/frontend-engineering/rules/pattern-overengineering.md`

## Steps

1. For each problem, collect candidate patterns from the relevant domains.
2. Score every candidate with the formula in `rules/pattern-selection.md`.
3. Select only candidates that answer an identified problem and score positively.
4. Record rejected candidates and why; the reasoning matters more than the shortlist.
5. Selecting nothing is a valid result (PATTERN-SYSTEM-002).

## Output

- PatternCandidate[]
- SelectedPattern[]
- RejectedPattern[]
- Reasons[]
