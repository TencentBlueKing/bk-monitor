# Skill: Project Architecture Analyzer

Generate and use a compact project architecture locator before broad source reading.

When to use:
- The user asks where a route, page, component, module or design document is implemented.
- The agent needs to understand a project quickly before editing.
- The project structure has changed and the architecture index may be stale.
- Entry / build-tool / AST-based module maps need refresh.

Command:

```bash
aafe analyze
aafe analyze --output=.aafe
aafe analyze --formats=json,jsonl,md,mmd
aafe analyze --mmd
aafe analyze --force
aafe analyze --skip-existing
aafe analyze --llm
```

Generated artifacts:
- configurable analyze output (default `.aafe/`, via `analyze.output` or `--output=`)
- formats: default `json,jsonl,md,mmd` (Agent: json/jsonl; Human: mmd/md)
- per-module slices under `modules/<id>/`
- .ai-agent/skills/project-architecture-locator.md
- .ai-agent/skills/architecture-on-demand.md
- .ai-agent/skills/dataflow-on-demand.md
- .ai-agent/memory/project-architecture.md

Usage rules:
1. Read project-architecture-locator.md first for route/component/module locating.
2. Deep facts live under the configured output (default `.aafe`); load only one `modules/<id>/` slice.
3. Agent reads JSON/JSONL; humans may open `.mmd` when enabled.
4. For deep architecture, use architecture-on-demand.md.
5. For dataflow, use dataflow-on-demand.md.
6. For human architecture docs / Knowledge Center, still use project `.docs` via `--architecture-docs`.
7. Re-run aafe analyze after large routing, component or module changes.

Required artifacts:
- project_architecture_index
