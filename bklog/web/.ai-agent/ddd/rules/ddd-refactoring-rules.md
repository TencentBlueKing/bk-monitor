# DDD Refactoring Rules

R-REFACTOR-001

DDD refactoring MUST begin with discovery.

R-REFACTOR-002

DDD refactoring MUST NOT start with directory restructuring.

R-REFACTOR-003

Business behavior MUST be preserved by default.

R-REFACTOR-004

Refactoring SHOULD be incremental.

R-REFACTOR-005

Each migration step MUST have explicit scope.

R-REFACTOR-006

Each migration step MUST define validation criteria.

R-REFACTOR-007

Large-scale DDD migration SHOULD establish characterization tests before moving business logic.

R-REFACTOR-008

A new DDD model MUST be mapped to existing code before deleting legacy structures.

R-REFACTOR-009

DDD refactoring MUST NOT introduce artificial abstractions.

R-REFACTOR-010

Legacy compatibility boundaries SHOULD be introduced when immediate migration is unsafe.

R-REFACTOR-011

Code deletion MUST only happen after replacement behavior is validated.
