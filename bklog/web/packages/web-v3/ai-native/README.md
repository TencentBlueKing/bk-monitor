# AI Native 开发入口

本机制帮助开发者及不同模型定位真实代码、识别影响范围并验证修改。它不执行自主业务写入，也不改变已有产品 AI 模式或后端协议。

在本包目录运行（仓库根目录可加 `--dir bklog/web/packages/web-v3`）：

```sh
pnpm --ignore-workspace ai:context --module=retrieval --limit=30
pnpm --ignore-workspace ai:impact features/grok/services/grok.js --limit=30
pnpm --ignore-workspace ai:index
pnpm --ignore-workspace ai:check
pnpm --ignore-workspace test
pnpm --ignore-workspace build
```

`context` 返回入口优先的有界文件列表、模块描述位置、契约位置、建议验证命令和已知失败记忆；文件总数与截断状态单独输出。`impact` 反向遍历静态依赖，支持循环引用。模块描述通过 `modules.json` 索引，包含真实入口、服务定义、跨域依赖及已有测试；测试为空意味着没有专属测试，不代表通过。

`dependency-graph.json` 包含 ES imports/re-exports、字面量动态 import/require、Worker URL、模板资源、Sass/CSS 引用，以及从原服务注册表解析的字面量 `http.request('namespace/action')` 调用关系。计算型请求、glob、无法识别的服务命名空间进入 dynamic 清单；图谱不等于完整运行时调用图。路由影响是保守的路由文件可达性，包含版本条件分支，不能代替浏览器验收。

`check` 检查迁移文件完整性、禁止回引 src-native、新增无法解析引用、新增底层到业务的依赖、路由对象签名变化与图谱过期。历史快照已退役，AI-Native 只校验当前源码。构建插件另外禁止打包 src-native 模块。`ai:index` 只刷新图谱和模块描述，不自动接受新增依赖债务或路由变化；修改现状台账须说明源码依据和验证结果。

当前 unresolved 清单保留原有未启用分支和缺失类型引用，不是缺文件。保留未解决项，禁止用空实现填补。严格类型检查仍失败，存量债务以 `typecheck-status.json` 为当前门禁。

`source-map.json` 记录迁移清单、目标位置和原始输出摘要；后续有记录的重构可以改变目标内容。5 个 `.DS_Store` 在 excluded 清单说明，业务代码和资源不因此减少。历史快照已退役，AI-Native 只校验当前源码。

任务记录遵循 `task.schema.json`；状态必须经过分析、实施、验证，必要证据缺失保持 NEEDS_REVIEW 或 BLOCKED。失败写入 `failure-memory.json`，包含复现、根因、修复、验证与预防；同一问题重复失败时先做根因分析。不能把目录迁移成功或一次构建成功视为全量功能通过。
