# DDD Tactical Design Rules

R-TACTICAL-001

Entity MUST have meaningful identity and lifecycle continuity.

R-TACTICAL-002

Value Object SHOULD be used when identity is not required.

R-TACTICAL-003

Value Objects SHOULD be immutable where practical.

R-TACTICAL-004

Aggregate MUST define a consistency boundary.

R-TACTICAL-005

Aggregate MUST protect business invariants.

R-TACTICAL-006

Aggregate MUST NOT be created merely by grouping related database tables.

R-TACTICAL-007

Aggregate SHOULD remain as small as business consistency allows.

R-TACTICAL-008

Aggregate Root MUST control access to internal Aggregate state.

R-TACTICAL-009

References between Aggregates SHOULD use identity rather than direct object references.

R-TACTICAL-010

Cross-Aggregate consistency SHOULD NOT automatically require one transaction.

R-TACTICAL-011

Domain Service SHOULD only exist when domain behavior does not naturally belong to an Entity or Aggregate.

R-TACTICAL-012

Application Service MUST NOT become a dumping ground for domain rules.

R-TACTICAL-013

Repository SHOULD represent persistence access for Aggregate Roots.

R-TACTICAL-014

Repository abstraction SHOULD belong to the Domain boundary when dependency inversion requires it.

R-TACTICAL-015

Repository implementation MUST remain outside the Domain layer.

R-TACTICAL-016

Domain Event MUST represent a meaningful business occurrence.

R-TACTICAL-017

Factories SHOULD only be introduced when object creation contains meaningful domain logic.

R-TACTICAL-018

Specification SHOULD only be introduced when reusable domain predicates provide meaningful value.

R-TACTICAL-019

DDD patterns MUST NOT be introduced only to satisfy pattern completeness.
