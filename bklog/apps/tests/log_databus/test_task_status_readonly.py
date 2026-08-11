"""采集任务状态只读语义测试。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.log_databus.handlers.collector.host import HostCollectorHandler


class HostTaskStatusReadonlyTests(SimpleTestCase):
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

        result = handler.get_task_status(["30"])

        self.assertEqual(result, {"task_ready": False, "contents": []})
        handler._update_or_create_subscription.assert_not_called()
        mock_bulk_request.assert_not_called()

    @patch("apps.log_databus.handlers.collector.host.NodeApi.get_subscription_task_status.bulk_request")
    def test_task_status_returns_unknown_when_no_task_ids(self, mock_bulk_request):
        handler = self.build_handler(task_id_list=None)

        result = handler.get_task_status([])

        self.assertEqual(result, {"task_ready": False, "contents": []})
        mock_bulk_request.assert_not_called()

    @patch(
        "apps.log_databus.handlers.collector.host.NodeApi.get_subscription_task_status.bulk_request",
        return_value=[{"task_id": 30}, {"task_id": 31}],
    )
    def test_task_status_filters_explicit_task_ids(self, mock_bulk_request):
        handler = self.build_handler(task_id_list=["31"])

        result = handler.get_task_status(["30"])

        self.assertEqual(result, {"task_ready": True, "contents": []})
        handler.format_task_instance_status.assert_called_once_with(
            [{"task_id": 30}], latest_task_id="30"
        )
        mock_bulk_request.assert_called_once()
        request_params = mock_bulk_request.call_args.kwargs["params"]
        self.assertEqual(request_params["task_id_list"], ["30"])
        self.assertIs(request_params["need_aggregate_all_tasks"], False)

    @patch("apps.log_databus.handlers.collector.host.NodeApi.get_subscription_task_status.bulk_request")
    def test_subscription_status_without_subscription_is_read_only(self, mock_bulk_request):
        handler = self.build_handler(subscription_id=None, target_nodes=[{"bk_inst_id": 1}])

        result = handler.get_subscription_status()

        self.assertEqual(result["contents"][0]["child"], [])
        mock_bulk_request.assert_not_called()
