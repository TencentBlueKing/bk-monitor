# Testing Patterns

覆盖 23 个模式：

- Test Pyramid
- Testing Trophy
- Unit Test
- Component Test
- Integration Test
- Contract Test
- E2E
- Snapshot
- Golden Master
- Characterization Test
- Property-Based Testing
- Mutation Testing
- Test Double
- Mock
- Stub
- Spy
- Fake
- Fixture
- Test Data Builder
- Object Mother
- Page Object
- Screenplay Pattern
- Contract Testing

## Rules

TEST-001
Tests SHOULD validate behavior rather than implementation details.

TEST-002
Mocks SHOULD NOT replace meaningful integration verification.

TEST-003
Characterization Tests SHOULD be considered before large refactoring.

TEST-004
Contract Tests SHOULD protect integration boundaries.

TEST-005
Test Data Builders SHOULD be used when test object construction becomes complex.

TEST-006
Snapshots MUST NOT replace semantic assertions.

TEST-007
E2E tests SHOULD focus on critical user journeys.

TEST-008
Pattern refactoring MUST include regression validation.
