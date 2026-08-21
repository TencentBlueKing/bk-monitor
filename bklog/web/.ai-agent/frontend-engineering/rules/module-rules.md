# Module Patterns

覆盖 16 个模式：

- ES Module
- Namespace
- Barrel
- Facade Module
- Feature Module
- Domain Module
- Layer Module
- Dependency Injection
- Plugin
- Registry
- Dynamic Import
- Module Federation
- Micro Frontend
- Package Boundary
- Public API
- Internal API

## Rules

MODULE-001
Every module SHOULD have an explicit public API.

MODULE-002
Internal implementation MUST NOT be exposed unnecessarily.

MODULE-003
Barrel exports MUST NOT create circular dependencies.

MODULE-004
Feature boundaries SHOULD reflect business or user-facing capabilities when appropriate.

MODULE-005
Dynamic module loading MUST define lifecycle.

MODULE-006
Plugin systems MUST define extension contracts.

MODULE-007
Module Federation MUST NOT be introduced solely for technical novelty.

MODULE-008
Cross-module dependencies MUST be explicit.
