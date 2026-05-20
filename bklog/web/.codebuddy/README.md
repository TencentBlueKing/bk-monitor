# CodeBuddy IDE 配置

本目录为 CodeBuddy IDE 的 AI 配置入口。

# AAFE Architecture Runtime for CodeBuddy

Use .ai-agent as the project architecture runtime. Route requests through runtime/router.yaml, execute pipeline steps, enforce gates, and run refactor critique before finalizing code.



## 配置来源

- `skills/ENTRY.md` - Skills 入口，指向公共配置
- `rules/ENTRY.md` - Rules 入口，指向公共配置

公共配置详见 [../.ai-shared/README.md](../.ai-shared/README.md)

## CodeBuddy 特定配置

如需添加 CodeBuddy 独有的配置，可在本目录下直接创建文件。

## SessionStart Hook（AAFE）

项目级 Hook 写在 `settings.json`，新会话启动时执行 `.codebuddy/hooks/aafe-session-start`，向模型注入 `.ai-agent/runtime/` 下 `engine.md`、`router.yaml`、`gates.yaml` 摘要（stdout 为 CodeBuddy 要求的 JSON：`continue` + `hookSpecificOutput.additionalContext`）。说明与事件列表见 CodeBuddy 文档：https://www.codebuddy.ai/docs/ide/Features/hooks

使用 `bklog/web` 作为 CodeBuddy 工程根目录，并保证脚本可执行：`chmod +x .codebuddy/hooks/aafe-session-start`。
