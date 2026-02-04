# BKLog Web Skills

本目录包含蓝鲸日志平台前端项目的 AI Agent Skills，用于帮助 AI 更好地理解和操作本项目。

## Skills 列表

| Skill | 说明 | 使用场景 |
|-------|------|----------|
| [bklog-architecture](./bklog-architecture/SKILL.md) | 项目整体架构指南 | 了解项目结构、添加新模块、理解数据流 |
| [bklog-components](./bklog-components/SKILL.md) | 公共组件使用指南 | 使用或创建公共组件、了解组件 API |
| [bklog-hooks](./bklog-hooks/SKILL.md) | Vue Hooks 使用指南 | 使用或创建 hooks、处理响应式逻辑 |
| [bklog-api-services](./bklog-api-services/SKILL.md) | API 服务层指南 | 调用后端 API、添加新接口 |
| [bklog-utils](./bklog-utils/SKILL.md) | 工具函数使用指南 | 使用工具函数、数据格式化 |
| [bklog-coding-patterns](./bklog-coding-patterns/SKILL.md) | 代码实现规范 | 编写新代码、保持风格一致性 |
| [bk-magicbox-vue](./bk-magicbox-vue/SKILL.md) | MagicBox 组件库指南 | 使用 UI 组件、实现交互功能 |

## 使用方式

Skills 会在相关场景下自动触发。例如：

- 当你询问"如何添加新的 API 接口"时，会触发 `bklog-api-services` skill
- 当你需要创建新组件时，会触发 `bklog-components` 和 `bklog-coding-patterns` skills
- 当你询问项目架构时，会触发 `bklog-architecture` skill

## 技术栈概览

- **框架**: Vue 2 + TypeScript/TSX + Composition API
- **状态管理**: Vuex
- **路由**: Vue Router
- **UI 组件库**: bk-magic-vue (蓝鲸 MagicBox)
- **HTTP**: axios（封装）
- **样式**: SCSS

## 项目结构速览

```
src/
├── api/            # HTTP 请求封装
├── common/         # 公共工具函数
├── components/     # 公共组件
├── hooks/          # Vue Composition API hooks
├── services/       # API 服务定义
├── store/          # Vuex 状态管理
├── views/          # 页面视图
├── main.js         # 应用入口
└── app.tsx         # 根组件
```

## 相关文档

- 详细架构说明: `../.docs/README.md`
- 架构图集: `../.docs/架构图.md`
- Mermaid 图表: `../.docs/diagrams/`

## 持续优化

这些 skills 会随着项目发展持续更新。如果发现需要补充的内容，请：

1. 在对应的 SKILL.md 文件中添加新内容
2. 保持简洁，只添加 AI 不知道但需要知道的信息
3. 使用代码示例而非冗长的文字说明
