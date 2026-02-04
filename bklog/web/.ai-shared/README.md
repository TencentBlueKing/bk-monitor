# AI 公共配置

## 工作边界

**只处理**: `bklog/web/src/`
**忽略**: `packages/*`

## 快速定位（必记）

| 业务模块 | 核心入口 |
|---------|---------|
| 日志检索 | `store/url-resolver.ts` + `views/retrieve-v3/` |
| 收藏 | `views/retrieve-v3/favorite/` |
| 管理 | `views/manage/` |
| 仪表盘 | `views/dashboard/` |

## 目录结构

```
.ai-shared/
├── skills/          # Skills（项目地图）
│   └── bklog-architecture/SKILL.md  ← 必读
└── rules/           # Rules（否定约束）
    ├── workspace-boundary.mdc       ← 工作边界
    └── vue-development-mode.mdc     ← 开发模式
```

## 使用原则

- Skills：先读架构地图，按需读取其他
- Rules：只写禁止，不写推荐
- 定位：先查模块映射表，再进入代码
