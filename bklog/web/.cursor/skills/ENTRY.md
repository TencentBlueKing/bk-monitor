# Cursor Skills Entry

> **AI 指令**: 目标是“最少读取 = 可定位”。先读项目地图；只有任务命中对应域时再按需读取其他 Skill。

## Default（必读）

- `../../.ai-agent/project.md` - BKLog Web 单一项目知识入口
- `../../.ai-agent/project-skills/aafe-self-update/SKILL.md` - 项目知识自更新协议
- `../../.ai-agent/project-skills/bklog-architecture/SKILL.md` - 项目最小地图（分层/边界/改动半径）

## AAFE Runtime（复杂任务）

- `../../.ai-agent/runtime/engine.md`
- `../../.ai-agent/runtime/router.yaml`
- `../../.ai-agent/pipelines/*.yaml` 按任务类型选择
- `../../.ai-agent/skills/*.md` 按 AAFE pipeline 调用

## On-demand（按需读取）

- UI/组件相关 → `../../.ai-agent/project-skills/bklog-components/SKILL.md`
- Hooks/响应式逻辑 → `../../.ai-agent/project-skills/bklog-hooks/SKILL.md`
- API/服务层 → `../../.ai-agent/project-skills/bklog-api-services/SKILL.md`
- 工具函数/格式化 → `../../.ai-agent/project-skills/bklog-utils/SKILL.md`
- 命名/落点/约定 → `../../.ai-agent/project-skills/bklog-coding-patterns/SKILL.md`
- MagicBox UI → `../../.ai-agent/project-skills/bk-magicbox-vue/SKILL.md`

Do not read or reference the removed legacy shared AI directory.
