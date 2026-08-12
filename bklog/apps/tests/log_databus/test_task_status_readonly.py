"""采集任务状态只读语义测试。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.log_databus.handlers.collector.host import HostCollectorHandler
from apps.log_databus.constants import CollectStatus, RunStatus
from apps.log_databus.serializers import SubscriptionStatusSerializer, TaskStatusSerializer
from apps.log_databus.views.collector_views import CollectorViewSet
from apps.iam import ActionEnum


class HostTaskStatusReadonlyTests(SimpleTestCase):
    @patch(
        "apps.log_databus.views.collector_views.Permission.get_auth_info",
        return_value={"bk_app_code": "__not_whitelisted__"},
    )
    def test_task_status_permission_matches_read_only_semantics(self, _mock_get_auth_info):
        view = CollectorViewSet()
        view.action = "task_status"

        view.request = SimpleNamespace(query_params={"read_only": "true"})
        self.assertEqual(view.get_permissions()[0].actions, [ActionEnum.VIEW_COLLECTION])

        view.request = SimpleNamespace(query_params={})
        self.assertEqual(view.get_permissions()[0].actions, [ActionEnum.VIEW_COLLECTION])

        view.request = SimpleNamespace(query_params={"read_only": "false"})
        self.assertEqual(view.get_permissions()[0].actions, [ActionEnum.MANAGE_COLLECTION])

    def test_task_status_serializer_defaults_to_read_only(self):
        serializer = TaskStatusSerializer(data={})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIs(serializer.validated_data["read_only"], True)

        serializer = TaskStatusSerializer(data={"read_only": False})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIs(serializer.validated_data["read_only"], False)

    def test_subscription_status_serializer_preserves_plugin_default(self):
        serializer = SubscriptionStatusSerializer(data={})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIs(serializer.validated_data["include_plugin_status"], True)

        serializer = SubscriptionStatusSerializer(data={"include_plugin_status": False})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIs(serializer.validated_data["include_plugin_status"], False)

    @staticmethod
    def build_handler(**overrides):
        handler = HostCollectorHandler.__new__(HostCollectorHandler)
        data = {
            "is_custom_scenario": False,
            "subscription_id": 20,
            "task_id_list": ["30"],
            "target_node_type": "TOPO",
            "target_nodes": [],
            "bk_biz_id": 2,
            "collector_scenario_id": "row",
            "params": {"paths": ["/var/log/messages"]},
        }
        data.update(overrides)
        handler.data = SimpleNamespace(**data)
        handler.format_task_instance_status = MagicMock(return_value=[])
        handler._get_status_content = MagicMock(return_value=[])
        return handler

    @patch("apps.log_databus.handlers.collector.host.NodeApi.get_subscription_task_status.bulk_request")
    def test_task_status_does_not_create_missing_subscription(self, mock_bulk_request):
        handler = self.build_handler(subscription_id=None)
        handler._update_or_create_subscription = MagicMock()

        result = handler.get_task_status(["30"], read_only=True)

        self.assertEqual(result, {"task_ready": False, "contents": []})
        handler._update_or_create_subscription.assert_not_called()
        mock_bulk_request.assert_not_called()

    @patch("apps.log_databus.handlers.collector.host.NodeApi.get_subscription_task_status.bulk_request")
    def test_task_status_returns_unknown_when_no_task_ids(self, mock_bulk_request):
        handler = self.build_handler(task_id_list=None)

        result = handler.get_task_status([], read_only=True)

        self.assertEqual(result, {"task_ready": False, "contents": []})
        mock_bulk_request.assert_not_called()

    @patch(
        "apps.log_databus.handlers.collector.host.NodeApi.get_subscription_task_status.bulk_request",
        return_value=[{"task_id": 30}, {"task_id": 31}],
    )
    def test_task_status_filters_explicit_task_ids(self, mock_bulk_request):
        handler = self.build_handler(task_id_list=["31"])

        result = handler.get_task_status(["30"], read_only=True)

        self.assertEqual(result, {"task_ready": True, "contents": []})
        handler.format_task_instance_status.assert_called_once_with(
            [{"task_id": 30}], latest_task_id="30"
        )
        mock_bulk_request.assert_called_once()
        request_params = mock_bulk_request.call_args.kwargs["params"]
        self.assertEqual(request_params["task_id_list"], ["30"])
        self.assertIs(request_params["need_aggregate_all_tasks"], False)

    @patch(
        "apps.log_databus.handlers.collector.host.NodeApi.get_subscription_task_status.bulk_request",
        return_value=[],
    )
    def test_legacy_task_status_still_creates_missing_subscription(self, mock_bulk_request):
        handler = self.build_handler(subscription_id=None)

        def create_subscription(**kwargs):
            handler.data.subscription_id = 99

        handler._update_or_create_subscription = MagicMock(side_effect=create_subscription)

        result = handler.get_task_status(["30"])

        self.assertEqual(result, {"task_ready": True, "contents": []})
        handler._update_or_create_subscription.assert_called_once()
        request_params = mock_bulk_request.call_args.kwargs["params"]
        self.assertEqual(request_params["subscription_id"], 99)

    @patch(
        "apps.log_databus.handlers.collector.host.NodeApi.get_subscription_task_status.bulk_request",
        return_value=[],
    )
    def test_legacy_task_status_without_task_ids_keeps_aggregate_query(self, mock_bulk_request):
        handler = self.build_handler()

        result = handler.get_task_status([])

        self.assertEqual(result, {"task_ready": True, "contents": []})
        request_params = mock_bulk_request.call_args.kwargs["params"]
        self.assertNotIn("task_id_list", request_params)
        self.assertIs(request_params["need_aggregate_all_tasks"], True)

    @patch(
        "apps.log_databus.handlers.collector.host.NodeApi.get_subscription_task_status.bulk_request",
        return_value=[],
    )
    def test_legacy_task_status_preserves_latest_task_filter(self, _mock_bulk_request):
        handler = self.build_handler()
        handler.data.task_id_list = [10, 20]
        handler.format_task_instance_status = MagicMock(return_value=[])

        handler.get_task_status([], read_only=False)

        handler.format_task_instance_status.assert_called_once_with([], latest_task_id="20")

    def test_task_status_keeps_latest_retry_result_per_instance(self):
        result = HostCollectorHandler.keep_latest_task_status_per_instance(
            [
                {"instance_id": "host-1", "task_id": 30, "status": "FAILED"},
                {"instance_id": "host-2", "task_id": 30, "status": "SUCCESS"},
                {"instance_id": "host-1", "task_id": 31, "status": "SUCCESS"},
            ]
        )

        self.assertEqual(
            result,
            [
                {"instance_id": "host-1", "task_id": 31, "status": "SUCCESS"},
                {"instance_id": "host-2", "task_id": 30, "status": "SUCCESS"},
            ],
        )

        reverse_result = HostCollectorHandler.keep_latest_task_status_per_instance(
            [
                {"instance_id": "host-1", "task_id": 31, "status": "SUCCESS"},
                {"instance_id": "host-1", "task_id": 30, "status": "FAILED"},
            ]
        )
        self.assertEqual(reverse_result, [{"instance_id": "host-1", "task_id": 31, "status": "SUCCESS"}])

    def test_subscription_status_preserves_unknown_and_terminated(self):
        def instance(status):
            return {
                "status": status,
                "instance_id": "host|instance|host|1",
                "instance_info": {
                    "host": {
                        "bk_host_id": 1,
                        "bk_host_innerip": "127.0.0.1",
                        "bk_host_name": "host-1",
                        "bk_cloud_id": 0,
                    }
                },
                "create_time": "2026-08-12 10:00:00",
            }

        result = HostCollectorHandler.format_subscription_instance_status(
            [instance(CollectStatus.UNKNOWN), instance(CollectStatus.TERMINATED)], []
        )

        self.assertEqual(
            [(item["status"], item["status_name"]) for item in result],
            [
                (CollectStatus.UNKNOWN, RunStatus.UNKNOWN),
                (CollectStatus.TERMINATED, RunStatus.TERMINATED),
            ],
        )

    @patch("apps.log_databus.handlers.collector.host.NodeApi.get_subscription_task_status.bulk_request")
    def test_subscription_status_without_subscription_is_read_only(self, mock_bulk_request):
        handler = self.build_handler(subscription_id=None, target_nodes=[{"bk_inst_id": 1}])

        result = handler.get_subscription_status()

        self.assertEqual(result["contents"][0]["child"], [])
        mock_bulk_request.assert_not_called()

    @patch("apps.log_databus.handlers.collector.host.NodeApi.plugin_search.batch_request")
    @patch(
        "apps.log_databus.handlers.collector.host.NodeApi.get_subscription_task_status.bulk_request",
        return_value=[],
    )
    def test_subscription_status_can_skip_plugin_query(self, _mock_bulk_request, mock_plugin_search):
        handler = self.build_handler()
        handler.format_subscription_instance_status = MagicMock(return_value=[])

        result = handler.get_subscription_status(include_plugin_status=False)

        self.assertEqual(result, {"contents": []})
        mock_plugin_search.assert_not_called()
