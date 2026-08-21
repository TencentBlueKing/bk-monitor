---
name: frontend-pattern-anti-pattern
description: Identify anti-patterns in the project and in the proposed composition.
---

# Frontend Anti-Pattern Detection

## Purpose

Identify anti-patterns in the project and in the proposed composition.

## Required Rules

- `.ai-agent/frontend-engineering/rules/anti-pattern.md`
- `.ai-agent/frontend-engineering/rules/pattern-overengineering.md`

## Steps

1. Match the project against the anti-pattern catalog. Findings need evidence.
2. Audit the proposed composition for Pattern Overuse and Premature Abstraction.
3. Report severity: project evidence outranks a passing mention in the request.
4. Every finding MUST carry a remediation direction.

## Output

- AntiPatternFinding[] { id, rule, kind, severity, description, remediation, evidence }
