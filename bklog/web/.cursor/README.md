# Cursor IDE 配置

本目录为 Cursor IDE 的 AI 配置入口。

## Single AI Runtime Entry

Use `.ai-agent` as the single project AI runtime and knowledge root.

- AAFE runtime: `../.ai-agent/runtime/`
- AAFE pipelines: `../.ai-agent/pipelines/`
- AAFE memory: `../.ai-agent/memory/`
- BKLog project map: `../.ai-agent/project.md`
- BKLog project skills: `../.ai-agent/project-skills/`
- BKLog project rules: `../.ai-agent/rules/`
- Self-update protocol: `../.ai-agent/project-skills/aafe-self-update/SKILL.md`

Do not reference the removed legacy shared AI directory.

## Cursor Specific Files

- `rules/ENTRY.md` - Cursor rule entry pointing to `.ai-agent`
- `skills/ENTRY.md` - Cursor skill entry pointing to `.ai-agent`
- `rules/aafe-architecture-runtime.mdc` - AAFE Runtime always-on rule
- `hooks/aafe-session-start` - session-start context hook
