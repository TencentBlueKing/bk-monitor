from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from apps.utils.context_processors import _current_iam_mode, _resolve_iam_urls, mysetting
from iam_engine.core.config import AuthMode

V3_SAAS_HOST = "https://iam-v3.example.test/saas"
V4_SAAS_HOST = "https://iam-v4.example.test"


@override_settings(
    BK_IAM_SAAS_HOST=V3_SAAS_HOST,
    BK_IAM_V4_SAAS_HOST=V4_SAAS_HOST,
    BK_IAM_V4_APPLY_PATH="/permission/apply",
)
class IAMEntryUrlTest(SimpleTestCase):
    def test_v3_returns_v3_center_and_apply_url(self):
        self.assertEqual(
            _resolve_iam_urls(AuthMode.V3),
            (V3_SAAS_HOST, f"{V3_SAAS_HOST}/apply-join-user-group"),
        )

    def test_v4_returns_v4_center_and_apply_url(self):
        self.assertEqual(
            _resolve_iam_urls(AuthMode.V4),
            (V4_SAAS_HOST, f"{V4_SAAS_HOST}/permission/apply"),
        )

    @override_settings(BK_IAM_V4_SAAS_HOST="")
    def test_v4_falls_back_to_v3_when_center_url_missing(self):
        self.assertEqual(
            _resolve_iam_urls(AuthMode.V4),
            (V3_SAAS_HOST, f"{V3_SAAS_HOST}/apply-join-user-group"),
        )

    @override_settings(BK_IAM_V4_APPLY_PATH="")
    def test_v4_uses_default_apply_path(self):
        self.assertEqual(
            _resolve_iam_urls(AuthMode.V4),
            (V4_SAAS_HOST, f"{V4_SAAS_HOST}/permission/apply"),
        )

    @override_settings(BK_IAM_SAAS_HOST=f"{V3_SAAS_HOST}/", BK_IAM_V4_SAAS_HOST=f"{V4_SAAS_HOST}/")
    def test_trailing_slash_is_stripped(self):
        self.assertEqual(
            _resolve_iam_urls(AuthMode.V3),
            (V3_SAAS_HOST, f"{V3_SAAS_HOST}/apply-join-user-group"),
        )
        self.assertEqual(
            _resolve_iam_urls(AuthMode.V4),
            (V4_SAAS_HOST, f"{V4_SAAS_HOST}/permission/apply"),
        )

    def test_union_mode_resolves_to_current_v4(self):
        provider = Mock()
        provider.get_mode.return_value = AuthMode.UNION
        with patch("apps.iam.mode.get_mode_provider", return_value=provider):
            self.assertIs(_current_iam_mode(), AuthMode.V4)

    def test_mode_resolution_failure_falls_back_to_v3(self):
        with patch("apps.iam.mode.get_mode_provider", side_effect=RuntimeError("toggle unavailable")):
            self.assertIs(_current_iam_mode(), AuthMode.V3)

    def test_context_exposes_iam_urls(self):
        request = Mock()
        request.headers = {"Is-External": "false"}
        request.get_full_path.return_value = "/"
        provider = Mock()
        provider.get_mode.return_value = AuthMode.V4
        with patch("apps.iam.mode.get_mode_provider", return_value=provider):
            context = mysetting(request)

        self.assertEqual(context["BK_IAM_URL"], V4_SAAS_HOST)
        self.assertEqual(context["BK_IAM_APPLY_URL"], f"{V4_SAAS_HOST}/permission/apply")
