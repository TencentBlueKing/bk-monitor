from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import SimpleTestCase
from django.utils.functional import Promise
from iam.meta import get_action_name, get_system_name

from apps.iam.backends.v3 import meta
from apps.iam.exceptions import GetSystemInfoError
from apps.iam.handlers.actions import ActionEnum


def make_client(result):
    client = MagicMock()
    client._client.query = MagicMock(return_value=result)
    return client


class SetupMetaTest(SimpleTestCase):
    def setUp(self):
        self.addCleanup(setattr, meta, "_registered_system_id", meta._registered_system_id)
        meta._registered_system_id = None

    def test_registers_system_and_action_names(self):
        meta.setup_meta("bk_log_search_test")

        self.assertEqual(get_system_name("bk_log_search_test"), settings.BK_IAM_SYSTEM_NAME)
        self.assertIsNotNone(get_action_name("bk_log_search_test", ActionEnum.VIEW_BUSINESS.id))

    def test_monitor_system_name_is_lazy_so_the_language_is_not_frozen(self):
        # meta 只注册一次，即时翻译会把进程内第一个请求的语言固定给后续所有请求。
        meta.setup_meta("bk_log_search_test")

        self.assertIsInstance(get_system_name("bk_monitorv3"), Promise)

    def test_registration_is_skipped_for_the_same_system_id(self):
        with patch.object(meta, "setup_system") as setup_system:
            meta.setup_meta("bk_log_search_test")
            meta.setup_meta("bk_log_search_test")

        self.assertEqual(setup_system.call_count, 2)

    def test_registration_runs_again_when_the_system_id_changes(self):
        with patch.object(meta, "setup_system") as setup_system:
            meta.setup_meta("system-a")
            meta.setup_meta("system-b")

        registered = [call.kwargs["system_id"] for call in setup_system.call_args_list]
        self.assertEqual(registered, ["system-a", "bk_monitorv3", "system-b", "bk_monitorv3"])


class GetSystemInfoTest(SimpleTestCase):
    def test_returns_the_action_list_on_success(self):
        client = make_client((True, "ok", {"actions": [{"id": "view_business"}]}))

        self.assertEqual(meta.get_system_info(client, "bk_log_search_test"), {"actions": [{"id": "view_business"}]})
        client._client.query.assert_called_once_with("bk_log_search_test")

    def test_raises_a_domain_error_carrying_the_upstream_message(self):
        client = make_client((False, "system not found", None))

        # 占位符必须按名字填：位置参数会先抛 KeyError，让接口变成 500 而不是可读的业务错误。
        with self.assertRaises(GetSystemInfoError) as caught:
            meta.get_system_info(client, "bk_log_search_test")

        self.assertIn("system not found", caught.exception.message)
