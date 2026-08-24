# Pattern Selection Rules

## Workflow

Problem → Requirement → Variation Point → Boundary → Candidate Patterns →
Trade-off Analysis → Selected Patterns.

Selection MUST NOT start at "candidate patterns". Discovery runs first and
describes problems without naming solutions.

## Scoring

Every candidate MUST be scored, and the score MUST be shown:

```
PatternScore = ProblemFit + ChangeIsolation + ComplexityReduction
             + ReusePotential + PerformanceBenefit
             - ImplementationCost - CognitiveCost - CouplingRisk
             - OverengineeringRisk
```

Each selected pattern MUST report score, problem, benefit, cost, risk,
alternatives and evidence.

A benefit only counts when the identified problem asks for it. Performance
benefit MUST NOT be credited to a pattern selected for a non-performance problem.

## Justification Bar

A pattern is selected only when it answers an identified problem and its score
is positive. Ranking alone MUST NOT produce a selection: "top 3 candidates" is
not a justification.

An empty selection is a valid and sometimes correct outcome.

## Command

`aafe pattern discover "<request>"` → problems only
`aafe pattern select "<request>"`   → scored composition
`aafe pattern audit "<request>"`    → anti-pattern findings
