# Skill: Knowledge Center Architecture Context

Generated: 2026-07-29T06:39:32.825Z
Project: blueking-log

## Purpose

Use the existing architecture documents and Mermaid diagrams as the first context for AI project management. Do not build a separate deep documentation site or invent domain entities not present in the project.

## Sources

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
- `.docs/diagrams/README.md` [architecture-doc] 前端架构流程图
- `.docs/README.md` [architecture-doc] bklog/web 前端架构与路由数据流说明
- `.docs/日志检索V3架构与数据链路.md` [architecture-doc] 日志检索 V3 架构与数据链路
- `.docs/架构图.md` [architecture-doc] bklog/web 当前前端架构与日志检索数据流

## Execution Rules

1. Read the relevant source document and diagram before planning a task.
2. Map requested changes to modules, routes, stores, APIs, workers, storage and tests.
3. Use architecture diagrams as relationship and flow evidence.
4. Prefer current code when documentation conflicts and record the conflict.
5. Before publishing knowledge, include source paths, commit/version, confidence and review status.
6. For changes to streaming, parsing, pagination, cancellation, cache or IndexedDB, calculate downstream impact and minimum verification paths.
