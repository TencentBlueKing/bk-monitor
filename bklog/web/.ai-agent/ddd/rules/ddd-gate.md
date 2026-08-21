# DDD Enablement Gate

## Purpose

Control whether DDD-specific skills are allowed to execute.

DDD skills MUST NOT be activated merely because the project contains Entity,
Aggregate, Repository, Service, Domain, Model, ValueObject, DomainEvent,
UseCase, Controller, the Repository pattern, Clean Architecture or Hexagonal
Architecture. The existence of these concepts in the target project is NOT
sufficient to activate DDD skills.

## Activation Principle

DDD skills may only be activated when the user's explicit intent requires
Domain-Driven Design. The decision MUST be based primarily on user intent, not
code structure.

## Explicit Activation Signals

使用 DDD、按 DDD 设计、采用领域驱动设计、DDD 设计、DDD 落地、DDD 重构、DDD 优化、
DDD 架构、DDD 建模、DDD 领域建模、DDD 战略设计、DDD 战术设计、Bounded Context 设计、
Aggregate 设计、Domain Model 设计、Domain Event 设计、Context Map 设计、领域模型重构、
领域驱动重构、将当前项目改造成 DDD、按 DDD 最佳实践优化当前项目、建立当前项目的 DDD 模型。

Equivalent English intent MUST also be recognized: Domain-Driven Design, DDD,
domain-driven architecture, DDD architecture, DDD modeling, DDD refactoring,
DDD migration, DDD optimization, bounded context design, aggregate design,
domain model design, domain event design, context mapping.

## Non-Activation Signals

普通代码分析、架构分析、代码重构、性能优化、Bug 修复、API 设计、数据库设计、模块拆分、
微服务拆分、Clean Architecture、Hexagonal Architecture、Repository 模式、Service 层设计、
Entity 设计、TypeScript 类型设计、前端架构、后端架构、测试设计、自动化测试、代码质量分析
— unless the user explicitly connects the task to DDD.

## Keyword Rule

DDD-related keywords alone MUST NOT activate DDD skills.

"帮我分析这个项目的 Repository 层" MUST NOT activate DDD.
"帮我按照 DDD 分析这个项目的 Repository 层" MUST activate DDD.

## Ambiguous Intent

If the request is ambiguous and DDD activation would materially change the
solution, DO NOT silently activate DDD. Ask whether the user wants DDD.

## Activation Scope

Once DDD is explicitly enabled, only the DDD skills required by the current
request SHOULD execute. Do not automatically execute the entire DDD skill chain
unless the user requests 完整 DDD 分析 / 完整 DDD 设计 / DDD 全量落地 /
DDD 全面重构 / end-to-end DDD implementation.

## Termination Rule

If the DDD Gate returns NOT_ENABLED, do not load DDD strategic rules, do not
load DDD tactical rules, do not perform bounded context analysis, do not perform
aggregate analysis, do not generate domain events, do not introduce DDD
architecture, and do not generate DDD migration plans.

## Tooling

`aafe ddd gate "<request>"` returns this decision as JSON.
