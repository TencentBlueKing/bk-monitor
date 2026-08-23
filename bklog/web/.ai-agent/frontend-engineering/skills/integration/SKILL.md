---
name: integration
description: Integration Patterns — 该域的模式选型与约束。仅在 Pattern Gate 启用且问题命中该域时加载。
---

# Integration Patterns

## Prerequisite

只有 `aafe pattern gate` 判定为 enabled，且 Discovery 识别出的问题落在本域时才加载。

## Rules

必读：`.ai-agent/frontend-engineering/rules/integration-rules.md`（9 条）

## 可评分模式

以下模式带有成本收益模型，可直接进入评分与组合：

- **Backend for Frontend** — 前端需要聚合多个后端接口
  - 职责：api-shaping
  - 适用复杂度门槛：3/3
- **Event Bus** — 互不相识的模块之间需要通信
  - 职责：decoupled-messaging
  - 适用复杂度门槛：3/3
  - 职责冲突：observer, mediator
- **WebSocket / SSE** — 需要服务端主动推送
  - 职责：server-push
  - 适用复杂度门槛：2/3
  - 必需配套：fallback
- **Polling** — 需要周期性获取最新数据但不值得长连接
  - 职责：pull-refresh
  - 适用复杂度门槛：1/3

## 完整清单

- Adapter
- Anti-Corruption Layer
- Facade
- Gateway
- BFF
- API Gateway
- Backend for Frontend
- Open Host Service
- Published Language
- Event Bus
- Message Bus
- Pub/Sub
- WebSocket
- SSE
- Polling
- Long Polling
- Webhook
- PostMessage
- BroadcastChannel
- Shared Worker
- Service Worker

## 约束

- 本域模式只解决本域的问题；越界承担其他模式的职责即为 RULE-005 违规。
- 未识别到对应问题时，本域不产出任何模式建议。
