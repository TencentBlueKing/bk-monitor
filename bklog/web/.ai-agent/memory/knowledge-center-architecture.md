# Knowledge Center Architecture Sources

Generated: 2026-07-29T06:39:32.825Z
Project: blueking-log

This generated memory is the primary architecture context for Knowledge Center and AI project management. Prefer these sources before broad code search. The source documents and Mermaid diagrams are authoritative project context; do not invent a CRM domain model when the project describes another domain.

## Architecture Sources

- `.docs/diagrams/A-整体前端架构图.mmd` [diagram] A-整体前端架构图
- `.docs/diagrams/B-应用启动时序图.mmd` [diagram] B-应用启动时序图
- `.docs/diagrams/C-路由守卫执行流程.mmd` [diagram] C-路由守卫执行流程
- `.docs/diagrams/D-Retrieve检索模块初始化数据流.mmd` [diagram] D-Retrieve检索模块初始化数据流
- `.docs/diagrams/E-HTTP请求处理流程.mmd` [diagram] E-HTTP请求处理流程
- `.docs/diagrams/F-Vuex-Store状态流转图.mmd` [diagram] F-Vuex-Store状态流转图
- `.docs/diagrams/G-检索模块API调用链路图.mmd` [diagram] G-检索模块API调用链路图
- `.docs/diagrams/H-Manage管理模块组件结构图.mmd` [diagram] H-Manage管理模块组件结构图
- `.docs/diagrams/I-完整页面请求时序图.mmd` [diagram] I-完整页面请求时序图
- `.docs/diagrams/J-API-Key映射查找流程.mmd` [diagram] J-API-Key映射查找流程
- `.docs/diagrams/K-分层架构全景图.mmd` [diagram] K-分层架构全景图
- `.docs/diagrams/L-空间切换数据流.mmd` [diagram] L-空间切换数据流
- `.docs/diagrams/README.md` [architecture-doc] 前端架构流程图 — 文件列表 > 使用方式 > 方式一：在线预览 > 方式二：本地预览 > 方式三：集成到文档 > 架构图 > 主题配置 > 图例说明
- `.docs/README.md` [architecture-doc] bklog/web 前端架构与路由数据流说明 — 当前文档入口 > 1. 代码入口与整体架构 > 2. 启动时序（从加载到可用） > 3. 路由系统设计（模块拆分 + 守卫） > 4. App 壳组件调用关系（全局 UI 容器） > 5. Store（Vuex）关键状态与数据流入口 > 6. HTTP/API 层设计（请求队列、缓存、取消、错误处理） > 7. 路由模块详解：组件调用与数据流 > 8. API Key（http.request 的 name）如何映射到真实接口
- `.docs/日志检索V3架构与数据链路.md` [architecture-doc] 日志检索 V3 架构与数据链路 — 1. 当前结论 > 2. 入口与模块边界 > 3. 页面初始化链路 > 4. 主查询链路 > 4.1 查询参数与分支 > 4.2 主线程到 Worker > 4.3 Worker 解析与落盘 > 5. 存储与渲染数据流 > 5.1 IndexedDB 结构 > 5.2 缓存和回收 > 6. 并发、取消与竞态控制 > 7. 结果模块边界
- `.docs/架构图.md` [architecture-doc] bklog/web 当前前端架构与日志检索数据流 — 1. 总体架构 > 2. 设计变化 > 3. 相关图表 > 4. 代码定位

## Operating Rules

- Read the relevant architecture document and diagram before planning changes.
- Treat Mermaid diagrams as relationship and flow evidence, not as executable code.
- Prefer current source code when documentation conflicts, and record the conflict for review.
- Use `aafe analyze --architecture-docs=<path>` after architecture documents change.
- Use the architecture sources to guide AI task planning, impact analysis, test selection and knowledge updates.
