# Skill: Project Architecture Analyzer

Generate and use a compact project architecture locator before broad source reading.

When to use:
- The user asks where a route, page, component, module or design document is implemented.
- The agent needs to understand a project quickly before editing.
- The project structure has changed and the architecture index may be stale.

Command:

```bash
aafe analyze
```

Generated artifacts:
- .ai-agent/skills/project-architecture-locator.md
- .ai-agent/memory/project-architecture.md

Usage rules:
1. Read project-architecture-locator.md first for route/component/module locating.
2. Read only the files listed as relevant before doing wider search.
3. For architecture or requirement questions, read listed design documents before implementation files.
4. Re-run aafe analyze after large routing, component or module changes.

Required artifacts:
- project_architecture_index
