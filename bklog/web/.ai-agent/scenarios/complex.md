# Scenario Pack: Complex Frontend

Use this pack as the default scenario for non-trivial frontend systems.

Workflow:
1. Split the feature by real business modules before selecting patterns.
2. Select patterns independently for domain, application, infrastructure and presentation modules.
3. Keep each selected pattern inside its module boundary.
4. Land each pattern with contract, implementation and verification.
5. Reject one global pattern when module responsibilities differ.

Module pattern map:
- domain: State Machine, Repository Port, Domain Service, Specification
- application: Command, Pipeline, Use Case Orchestrator
- infrastructure: Adapter, Registry, Strategy
- presentation: Composition, Observer, State Machine
- graph-runtime: Command, Strategy, Registry, Observer
