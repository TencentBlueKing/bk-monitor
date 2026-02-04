# AI 公共配置

本目录存放各 AI IDE 插件（Cursor、CodeBuddy 等）的公共配置。

## 目录结构

```
.ai-shared/
├── skills/          # 公共 Skills（AI 能力指南）
│   ├── bk-magicbox-vue/
│   ├── bklog-api-services/
│   ├── bklog-architecture/
│   ├── bklog-coding-patterns/
│   ├── bklog-components/
│   ├── bklog-hooks/
│   └── bklog-utils/
└── rules/           # 公共 Rules（代码规范）
    └── vue-development-mode.mdc
```

## 工作原理

各 IDE 配置目录通过入口文件 (`ENTRY.md`) 指向本公共配置：

- `.cursor/skills/ENTRY.md` -> 指向 `.ai-shared/skills/`
- `.cursor/rules/ENTRY.md` -> 指向 `.ai-shared/rules/`
- `.codebuddy/skills/ENTRY.md` -> 指向 `.ai-shared/skills/`
- `.codebuddy/rules/ENTRY.md` -> 指向 `.ai-shared/rules/`

AI 读取入口文件后，会自动跟随路径读取公共配置。

## 维护说明

1. **添加新的 Skill**: 在 `.ai-shared/skills/` 下创建目录，并更新各 IDE 的 `ENTRY.md`
2. **添加新的 Rule**: 在 `.ai-shared/rules/` 下创建文件，并更新各 IDE 的 `ENTRY.md`
3. **IDE 特定配置**: 如需某个 IDE 独有的配置，直接在对应 IDE 目录下创建

## 优点

- 无需符号链接，跨平台兼容
- 所有配置均可入库
- 维护单一配置源
