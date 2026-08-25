# Migration Patterns

覆盖 14 个模式：

- Strangler Fig
- Branch by Abstraction
- Parallel Run
- Anti-Corruption Layer
- Facade Migration
- Adapter Migration
- Incremental Migration
- Feature Toggle
- Dark Launch
- Shadow Traffic
- Dual Write
- Read Migration
- Compatibility Layer
- Modularization

## Rules

MIGRATION-001
Large architecture migration MUST be incremental unless explicitly justified.

MIGRATION-002
Branch by Abstraction SHOULD isolate replacement implementations.

MIGRATION-003
Strangler migration MUST define the replacement boundary.

MIGRATION-004
Dual Write MUST define consistency and rollback strategy.

MIGRATION-005
Compatibility layers MUST have an explicit removal strategy.

MIGRATION-006
Feature flags MUST define ownership and cleanup.

MIGRATION-007
Migration MUST preserve existing behavior by default.

MIGRATION-008
Every migration phase MUST have validation criteria.
