# CodeBuddy IDE 配置

本目录为 CodeBuddy IDE 的 AI 配置入口。

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

## CodeBuddy Specific Files

- `rules/ENTRY.md` - CodeBuddy rule entry pointing to `.ai-agent`
- `skills/ENTRY.md` - CodeBuddy skill entry pointing to `.ai-agent`
- `aafe.md` - CodeBuddy AAFE Runtime summary

## SessionStart Hook（AAFE）

Project-level Hook is configured in `settings.json`. New sessions execute `.codebuddy/hooks/aafe-session-start`, injecting summaries from `.ai-agent/runtime/` into the model context.

Use `bklog/web` as the CodeBuddy project root and keep scripts executable: `chmod +x .codebuddy/hooks/aafe-session-start`.
