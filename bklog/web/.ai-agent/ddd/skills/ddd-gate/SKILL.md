# DDD Gate Skill

## Purpose

Determine whether the current user request explicitly requires DDD. This skill MUST execute before every DDD-specific skill.

## Input

- user request
- current project context
- previously established task scope

## Decision

Return exactly one of ENABLED, DISABLED, AMBIGUOUS.

## ENABLED

Use when the user explicitly requests DDD-related work.

- "用 DDD 重构这个项目"
- "按照 DDD 设计这个模块"
- "给当前项目做 DDD 建模"
- "建立 Bounded Context"
- "设计 Aggregate"
- "进行领域驱动设计"

## DISABLED

Use when DDD is not explicitly requested.

- "分析这个项目架构"
- "帮我重构这个 Service"
- "分析 Repository"
- "设计微服务架构"
- "优化代码结构"

## AMBIGUOUS

Use when the request could reasonably mean DDD but does not explicitly establish it, for example "帮我做领域建模". Ask whether the user wants Domain-Driven Design.

## Schema

`.ai-agent/ddd/schemas/ddd-gate.schema.json`
