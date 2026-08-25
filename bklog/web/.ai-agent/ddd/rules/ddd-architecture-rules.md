# DDD Architecture Rules

R-ARCH-001

Domain MUST NOT depend on Infrastructure.

R-ARCH-002

Domain MUST NOT depend on Presentation.

R-ARCH-003

Domain MUST NOT depend on Framework-specific infrastructure unless explicitly justified.

R-ARCH-004

Application Layer MAY depend on Domain.

R-ARCH-005

Infrastructure MAY depend on Application and Domain abstractions.

R-ARCH-006

Presentation MUST NOT directly implement Domain business rules.

R-ARCH-007

Controllers MUST NOT contain core domain invariants.

R-ARCH-008

Persistence models SHOULD NOT leak into Domain models.

R-ARCH-009

External API models SHOULD NOT automatically become Domain models.

R-ARCH-010

ORM entities SHOULD NOT automatically become Domain Entities.

R-ARCH-011

Architecture style MUST be selected based on project constraints.

R-ARCH-012

DDD MUST NOT force Microservices.

R-ARCH-013

DDD MUST NOT require Event Sourcing.

R-ARCH-014

DDD MUST NOT require CQRS.

R-ARCH-015

DDD MUST NOT require a specific programming language or framework.
