"""Current Action policies use the SDK unchanged, without legacy queries."""

from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from iam import IAM, Action, MultiActionRequest, Request, Resource, Subject
from iam.exceptions import AuthAPIError

from apps.iam.backends.v3.client import build_v3_client
from apps.log_search.models import GlobalConfig


@override_settings(
    APP_CODE="bk_log_search",
    SECRET_KEY="offline-only",
    BK_IAM_APIGATEWAY_URL="https://iam.example.test/api",
    BK_IAM_SYSTEM_ID="bk_log_search",
)
class V3ClientTest(SimpleTestCase):
    def make_client(self):
        client = build_v3_client("tenant-1")
        client._client = Mock()
        return client

    def request(self, batch=False):
        kwargs = dict(
            system="bk_log_search",
            subject=Subject("user", "alice"),
            resources=[Resource("bk_log_search", "space", "2", {"_bk_iam_path_": "/space,2/", "id": "2"})],
            environment=None,
        )
        if batch:
            return MultiActionRequest(actions=[Action("search_log_v2"), Action("view_collection_v2")], **kwargs)
        return Request(action=Action("search_log_v2"), **kwargs)

    def test_client_uses_sdk_and_tenant_credentials(self):
        client = build_v3_client("tenant-1")
        self.assertIs(type(client), IAM)
        self.assertEqual(client._client._app_code, "bk_log_search")
        self.assertEqual(client._client._bk_tenant_id, "tenant-1")

    def test_legacy_configuration_is_never_read(self):
        for value in (True, False, None, GlobalConfig.DoesNotExist(), RuntimeError("DB unavailable")):
            with self.subTest(value=value), patch.object(GlobalConfig.objects, "get") as query:
                if isinstance(value, Exception):
                    query.side_effect = value
                else:
                    query.return_value = Mock(configs=value)
                client = self.make_client()
                client._client.v2_policy_query.return_value = (True, "", {})
                client._client.v2_policy_query_by_actions.return_value = (True, "", [])
                self.assertEqual(client._do_policy_query(self.request()), {})
                self.assertEqual(client._do_policy_query_by_actions(self.request(True)), [])
                client._client.policy_query.assert_not_called()
                client._client.policy_query_by_actions.assert_not_called()
                query.assert_not_called()

    def test_policy_payload_result_and_error_contract(self):
        for batch in (False, True):
            for with_resources in (False, True):
                for ok in (False, True):
                    with self.subTest(batch=batch, resources=with_resources, ok=ok):
                        client = self.make_client()
                        request = self.request(batch)
                        method = client._do_policy_query_by_actions if batch else client._do_policy_query
                        wire = client._client.v2_policy_query_by_actions if batch else client._client.v2_policy_query
                        result = [{"action": {"id": "search_log_v2"}, "condition": {}}] if batch else {}
                        wire.return_value = (ok, "unavailable", result)
                        if ok:
                            self.assertEqual(method(request, with_resources), result)
                        else:
                            with self.assertRaises(AuthAPIError):
                                method(request, with_resources)
                        expected = request.to_dict()
                        if not with_resources:
                            expected["resources"] = []
                        wire.assert_called_once_with("bk_log_search", expected)
                        client._client.policy_query.assert_not_called()
                        client._client.policy_query_by_actions.assert_not_called()

    def test_allow_deny_and_cached_reads_use_current_policy(self):
        for allowed in (False, True):
            with self.subTest(allowed=allowed):
                client = self.make_client()
                request = self.request()
                request.subject = Subject("user", f"v2-only-{allowed}")
                # Even an available legacy grant must not override the current denial.
                client._client.policy_query.return_value = (True, "", {"op": "any", "field": "", "value": []})
                client._client.v2_policy_query.return_value = (
                    True,
                    "",
                    {"op": "any", "field": "", "value": []} if allowed else {},
                )
                self.assertEqual(client.is_allowed_with_cache(request), allowed)
                self.assertEqual(client.is_allowed_with_cache(request), allowed)
                client._client.v2_policy_query.assert_called_once()
                client._client.policy_query.assert_not_called()

    def test_grafana_command_still_loads_without_old_upgrade_command(self):
        from apps.log_databus.management.commands.migrate_grafana import Command

        command = Command()
        self.assertTrue(callable(command.get_grafana_config))
        self.assertFalse(hasattr(command, "migrate_permissions"))
