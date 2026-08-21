---
name: architecture
description: Project architecture map — routes, modules, boundaries. Use WHEN locating pages, modules, or design docs.
---

# Project Skill · Architecture

## When to use

- Locate routes, pages, modules, or architecture boundaries
- Before broad source search for feature ownership

## Protocol

1. Read `.ai-agent/project.md` Quick Map.
2. Read `.ai-agent/skills/project-architecture-locator.md` if present.
3. For deep facts: `.ai-agent/skills/architecture-on-demand.md` against analyze output (default `.aafe/`).
4. Do not invent DDD layers; prefer static facts + evidence.

## Maintain

Update this skill after major routing or module boundary changes. Run `aafe analyze` to refresh machine facts.
