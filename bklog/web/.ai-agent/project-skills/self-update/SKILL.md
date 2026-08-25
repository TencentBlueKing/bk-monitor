---
name: self-update
description: How to grow project.md and project-skills after architecture or domain changes. Use WHEN refreshing project knowledge.
---

# Project Skill · Self Update

## When to use

- After major route/module/API changes
- When project knowledge docs are stale

## Protocol

1. Run `aafe analyze` to refresh machine facts under analyze output.
2. Update `.ai-agent/project.md` Quick Map if entry/domains changed.
3. Update only the affected `.ai-agent/project-skills/<domain>/SKILL.md`.
4. Do not copy knowledge into editor directories (`.cursor`, etc.).

## Maintain

`aafe update` refreshes runtime adapters; it must not wipe this skill.
