---
name: frontend-pattern-validation
description: Check the composition against the problems it claims to solve.
---

# Frontend Pattern Validation

## Purpose

Check the composition against the problems it claims to solve.

## Required Rules

- `.ai-agent/frontend-engineering/rules/pattern-composition.md`
- `.ai-agent/frontend-engineering/rules/pattern-overengineering.md`

## Steps

1. Every selected pattern MUST trace back to an identified problem.
2. Every identified problem MUST be either answered by a pattern or explicitly left to direct implementation.
3. Run the anti-pattern audit against the composition itself, not only against the project.
4. Confirm the composition is the minimum sufficient one (RULE-011).

## Output

- PatternValidation { answered, unanswered, antiPatterns, verdict }
