from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, override_settings
from opentelemetry import context as otel_context
from opentelemetry.instrumentation.utils import _SUPPRESS_INSTRUMENTATION_KEY

from common.context_processors import get_basic_context, get_core_context


def make_request(bk_token: str = "test-token"):
    request = RequestFactory().get("/")
    request.user = SimpleNamespace(username="test-user", is_superuser=False)
    request.LANGUAGE_CODE = "zh-hans"
    request.COOKIES["bk_token"] = bk_token
    return request


@mock.patch("core.drf_resource.api.bk_login.get_user_info")
@mock.patch("common.context_processors.TokenVerifier", create=True)
def test_get_core_context_uses_login_token_user_info(mock_token_verifier, mock_get_user_info):
    mock_token_verifier.return_value.get_user_info.return_value = (
        True,
        {"username": "test-user", "time_zone": "Asia/Shanghai"},
    )

    context = get_core_context(make_request())

    assert context["USER_TIME_ZONE"] == "Asia/Shanghai"
    mock_token_verifier.return_value.get_user_info.assert_called_once_with("test-token")
    mock_get_user_info.assert_not_called()


@mock.patch("common.context_processors.TokenVerifier")
def test_get_core_context_skips_user_info_without_login_token(mock_token_verifier):
    context = get_core_context(make_request(bk_token=""))

    assert context["USER_TIME_ZONE"] == ""
    mock_token_verifier.assert_not_called()


@mock.patch("common.context_processors.TokenVerifier")
def test_get_core_context_ignores_unsuccessful_user_info(mock_token_verifier):
    mock_token_verifier.return_value.get_user_info.return_value = (
        False,
        {"username": "test-user", "time_zone": "Africa/Abidjan"},
    )

    context = get_core_context(make_request())

    assert context["USER_TIME_ZONE"] == ""


@mock.patch("common.context_processors.TokenVerifier")
def test_get_core_context_ignores_another_tokens_user_info(mock_token_verifier):
    mock_token_verifier.return_value.get_user_info.return_value = (
        True,
        {"username": "another-user", "time_zone": "Africa/Abidjan"},
    )

    context = get_core_context(make_request())

    assert context["USER_TIME_ZONE"] == ""


@mock.patch("common.context_processors.TokenVerifier")
def test_get_core_context_does_not_log_login_token(mock_token_verifier, caplog):
    mock_token_verifier.return_value.get_user_info.side_effect = RuntimeError("request failed for test-token")

    context = get_core_context(make_request())

    assert context["USER_TIME_ZONE"] == ""
    assert "test-token" not in caplog.text


@mock.patch("common.context_processors.TokenVerifier")
def test_get_core_context_suppresses_token_request_instrumentation(mock_token_verifier):
    suppression_values = []

    def get_user_info(_bk_token):
        suppression_values.append(otel_context.get_value(_SUPPRESS_INSTRUMENTATION_KEY))
        return True, {"username": "test-user", "time_zone": "Asia/Shanghai"}

    mock_token_verifier.return_value.get_user_info.side_effect = get_user_info

    get_core_context(make_request())

    assert suppression_values == [True]
    assert otel_context.get_value(_SUPPRESS_INSTRUMENTATION_KEY) is None


@override_settings(AIDEV_API_BASE_URL="https://example.com")
def test_get_basic_context_disables_ai_assistant_by_environment_variable():
    with (
        mock.patch.dict("common.context_processors.os.environ", {"ENABLE_AI_ASSISTANT": "disabled"}),
        mock.patch("common.context_processors.get_core_context", return_value={}),
        mock.patch("common.context_processors.is_ipv6_biz", return_value=False),
    ):
        context = get_basic_context(make_request(), [{"bk_biz_id": 2}], 2)

    assert context["ENABLE_AI_ASSISTANT"] == "false"
