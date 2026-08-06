from django.test import SimpleTestCase

from apps.iam.iam_engine.core.types import AuthResult, AuthStatus
from apps.iam.iam_engine.provider.composition.union import UnionDecisionPolicy


class AuthResultTest(SimpleTestCase):
    def test_factory_methods_preserve_three_state_semantics(self):
        allow = AuthResult.allow(provider_name="v3")
        deny = AuthResult.deny(provider_name="v4", reason="policy denied")
        error = AuthResult.error(
            provider_name="v4",
            reason="request timeout",
            error_type="TimeoutError",
        )

        self.assertEqual(allow.status, AuthStatus.ALLOW)
        self.assertTrue(allow.allowed)
        self.assertEqual(deny.status, AuthStatus.DENY)
        self.assertFalse(deny.allowed)
        self.assertEqual(error.status, AuthStatus.ERROR)
        self.assertFalse(error.allowed)
        self.assertEqual(error.error_type, "TimeoutError")

    def test_invalid_result_metadata_is_rejected(self):
        with self.assertRaisesMessage(ValueError, "provider_name must not be empty"):
            AuthResult.allow(provider_name="")
        with self.assertRaisesMessage(ValueError, "error result must include a reason"):
            AuthResult(status=AuthStatus.ERROR, provider_name="v4")
        with self.assertRaisesMessage(ValueError, "error_type is only valid for error results"):
            AuthResult(status=AuthStatus.DENY, provider_name="v4", error_type="TimeoutError")


class UnionDecisionPolicyTest(SimpleTestCase):
    CASES = (
        (AuthStatus.ALLOW, AuthStatus.ALLOW, True, False, ("v3", "v4")),
        (AuthStatus.ALLOW, AuthStatus.DENY, True, False, ("v3",)),
        (AuthStatus.ALLOW, AuthStatus.ERROR, True, True, ("v3",)),
        (AuthStatus.DENY, AuthStatus.ALLOW, True, False, ("v4",)),
        (AuthStatus.ERROR, AuthStatus.ALLOW, True, True, ("v4",)),
        (AuthStatus.DENY, AuthStatus.DENY, False, False, ()),
        (AuthStatus.DENY, AuthStatus.ERROR, False, True, ()),
        (AuthStatus.ERROR, AuthStatus.DENY, False, True, ()),
        (AuthStatus.ERROR, AuthStatus.ERROR, False, True, ()),
    )

    def test_complete_decision_matrix(self):
        for v3_status, v4_status, allowed, degraded, hit_providers in self.CASES:
            with self.subTest(v3=v3_status, v4=v4_status):
                results = (
                    self._make_result("v3", v3_status),
                    self._make_result("v4", v4_status),
                )

                decision = UnionDecisionPolicy.decide(results)

                self.assertEqual(decision.allowed, allowed)
                self.assertEqual(decision.degraded, degraded)
                self.assertEqual(decision.hit_provider_names, hit_providers)
                self.assertEqual(decision.provider_results, results)

    def test_no_provider_result_is_safely_denied(self):
        decision = UnionDecisionPolicy.decide(())

        self.assertFalse(decision.allowed)
        self.assertFalse(decision.degraded)
        self.assertEqual(decision.hit_provider_names, ())

    @staticmethod
    def _make_result(provider_name: str, status: AuthStatus) -> AuthResult:
        if status is AuthStatus.ALLOW:
            return AuthResult.allow(provider_name=provider_name)
        if status is AuthStatus.DENY:
            return AuthResult.deny(provider_name=provider_name)
        return AuthResult.error(provider_name=provider_name, reason="provider unavailable")
