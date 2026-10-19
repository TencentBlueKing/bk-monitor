# BKLog Web AI 约束

执行 BKLog 前端任务时遵守以下边界：

1. **可操作目录只有 `bklog/web`**。禁止改仓库根、根级 `tests/`、根级 `.cursor/`、`bkmonitor/` 或其他外层目录。
2. **`bklog/web/.ai-agent/` 和 `bklog/web/tests/` 只留服务本地**，不要提交到 GitHub。
3. UI 用例只写在 `bklog/web/tests/ui-ai/cases/`，不要写到仓库根 `tests/ui-ai/`。
4. 项目 SKILL 只写在 `bklog/web/.ai-agent/project-skills/<domain>/SKILL.md`，由本地 `skill-index.md` 触发。不要提交 SKILL 正文或编辑器技能指针。
5. 后续 AIBOT 读取本文件与本地 `.ai-agent` 即可触发技能，不要为了发现技能去改外层目录。
