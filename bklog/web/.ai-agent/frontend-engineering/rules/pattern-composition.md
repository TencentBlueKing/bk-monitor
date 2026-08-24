# Pattern Composition Rules

## PATTERN-SYSTEM-001

Design patterns are composable problem-solving mechanisms.

A frontend project MUST NOT be designed by selecting one design pattern and
applying it globally.

The system MUST:

1. identify problems first;
2. identify boundaries and variation points;
3. select multiple patterns where necessary;
4. assign each pattern an explicit responsibility;
5. define interactions between patterns;
6. detect conflicts and redundant patterns;
7. evaluate total architectural complexity;
8. select the minimum sufficient pattern composition;
9. validate the resulting architecture against actual project requirements.

A pattern is successful only when the composition improves changeability,
maintainability, isolation, extensibility, correctness, performance and
testability without introducing unnecessary complexity.

## PATTERN-SYSTEM-002

No pattern is mandatory.

The absence of a design pattern is NOT a defect.

A pattern MUST only be introduced when a concrete problem, variation point,
architectural boundary, or measurable constraint justifies its use.

## PATTERN-SYSTEM-003

Pattern selection is contextual.

The same problem MAY require different pattern compositions in different
projects because of framework, runtime, application size, team size, business
complexity, performance constraints, deployment model, existing architecture,
migration cost and testing requirements.

## CORE PRINCIPLE

A real frontend architecture SHOULD be composed of multiple patterns.

A single design pattern MUST NOT be treated as a complete project architecture.

## Rules

RULE-001
Pattern selection MUST begin from architectural and business problems.
Not "which pattern should I use?" but "what problems must this system solve?".

RULE-002
Multiple patterns MAY be combined when they solve different problems.

RULE-003
Every selected pattern MUST have an explicit responsibility.

RULE-004
A pattern MUST NOT be introduced merely because it is a recognized design pattern.

RULE-005
Patterns MUST NOT overlap responsibilities without justification.

RULE-006
The system MUST distinguish Pattern, Architecture, Framework and Implementation Technique.

RULE-007
A pattern combination MUST define responsibility, boundary, input, output,
dependency, interaction, lifecycle and failure behavior.

RULE-008
The selected patterns MUST form a coherent composition.

RULE-009
The agent MUST identify pattern conflicts.

RULE-010
The agent MUST identify unnecessary patterns.

RULE-011
The simplest sufficient composition SHOULD be preferred.

RULE-012
Pattern count MUST NOT be used as a quality metric.

RULE-013
A system using fewer patterns MAY be architecturally superior to a system using
more patterns.

RULE-014
Patterns SHOULD be selected according to the problem's volatility. Stable code
SHOULD NOT receive unnecessary abstraction. Frequently changing behavior SHOULD
receive appropriate variation-isolation patterns.
