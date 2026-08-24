# Skill: Pattern Selector

Runs only after `pattern-gate` enabled the system and `pattern-discovery`
identified the problems. Selecting before discovery is guessing.

Candidates come from the 16 pattern domains in
`.ai-agent/frontend-engineering/rules/<domain>-rules.md`, not from a fixed
shortlist.

Selection rules:
1. Score every candidate: ProblemFit + ChangeIsolation + ComplexityReduction +
   ReusePotential + PerformanceBenefit − ImplementationCost − CognitiveCost −
   CouplingRisk − OverengineeringRisk.
2. A benefit only counts when the identified problem asks for it.
3. Select a pattern only when it answers a problem and scores positively.
4. Selecting nothing is a valid outcome (PATTERN-SYSTEM-002).
5. Never return a single pattern as the project's architecture
   (PATTERN-SYSTEM-001); patterns are composed.
6. Record rejected candidates and why.

Required artifacts:
- pattern_selection
- pattern_candidates
- pattern_rejected
