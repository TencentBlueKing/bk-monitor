# Frontend Pattern Enablement Gate

## Purpose

Control whether frontend design-pattern skills may be activated.

## Activation Principle

Frontend design-pattern skills are opt-in.

They MUST NOT be activated merely because the project contains: class,
interface, factory, service, observer, event, store, reducer, hook, component,
adapter, strategy, singleton, facade, command, middleware.

The existence of a pattern-like implementation MUST NOT activate pattern skills.

## Explicit Activation

设计模式、前端设计模式、设计模式优化、设计模式重构、设计模式落地、使用设计模式、
按设计模式设计、模式组合、前端架构模式、设计模式分析、识别设计模式、
重构成某种设计模式、优化模式组合。

Equivalent English intent: design patterns, frontend design patterns,
pattern-based architecture, pattern refactoring, pattern optimization,
design pattern analysis, pattern composition.

Naming a specific pattern with intent — "用 Strategy Pattern 重构计价"、"策略模式"
— also activates the system.

## Non-Activation

普通代码重构、性能优化、Bug 修复、组件开发、API 开发、状态管理、React 开发、
Vue 开发、TypeScript 开发、CSS 优化、构建优化、架构分析 — unless design-pattern
intent is explicit.

## Important

Architecture analysis MUST NOT automatically become pattern analysis.
Performance optimization MUST NOT automatically become performance-pattern analysis.
State management MUST NOT automatically activate State Pattern Skills.

Only explicit pattern intent activates this system.

## Decision

Run `aafe pattern gate "<request>"`:

- `disabled` → 按普通任务处理，不做模式识别、选型或组合
- `ambiguous` → 先问用户是否要按设计模式做，不要静默启用
- `enabled` → 进入 Discovery，而不是直接选型
