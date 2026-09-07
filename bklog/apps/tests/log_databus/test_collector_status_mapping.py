"""采集项列表状态映射测试。

订阅范围为空（如目标主机已从 CMDB 移除）时，后端聚合给出 UNKNOWN；
若列表枚举把它兜底成 RUNNING，采集项会永远显示“部署中”，前端状态轮询也无法结束。
"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.log_databus.constants import CollectStatus
from apps.log_databus.handlers.collector_handler.log import LogCollectorHandler
from apps.log_search.constants import CollectStatusEnum


class CollectStatusEnumTests(SimpleTestCase):
    def test_every_aggregated_status_maps_explicitly(self):
        """get_subscription_status_by_list 能产出的状态都必须有确定映射。"""
        self.assertEqual(
            {
                original: CollectStatusEnum.get_collect_status(original)
                for original in (
                    CollectStatus.SUCCESS,
                    CollectStatus.FAILED,
                    CollectStatus.TERMINATED,
                    CollectStatus.RUNNING,
                    CollectStatus.PENDING,
                    CollectStatus.PREPARE,
                    CollectStatus.UNKNOWN,
                )
            },
            {
                CollectStatus.SUCCESS: CollectStatusEnum.SUCCESS.value,
                CollectStatus.FAILED: CollectStatusEnum.FAILED.value,
                CollectStatus.TERMINATED: CollectStatusEnum.TERMINATED.value,
                CollectStatus.RUNNING: CollectStatusEnum.RUNNING.value,
                # 节点管理仍在下发的实例状态，归入“部署中”符合原语义
                CollectStatus.PENDING: CollectStatusEnum.RUNNING.value,
                CollectStatus.PREPARE: CollectStatusEnum.PREPARE.value,
                CollectStatus.UNKNOWN: CollectStatusEnum.UNKNOWN.value,
            },
        )

    def test_empty_status_stays_empty(self):
        """状态未就绪时保持空串，前端据此展示 --。"""
        self.assertEqual(CollectStatusEnum.get_collect_status(""), "")
        self.assertEqual(CollectStatusEnum.get_collect_status(None), "")

    def test_unrecognized_status_still_falls_back_to_running(self):
        self.assertEqual(CollectStatusEnum.get_collect_status("SOME_NEW_STATUS"), CollectStatusEnum.RUNNING.value)

    def test_new_statuses_have_their_own_labels(self):
        running_label = CollectStatusEnum.get_choice_label(CollectStatusEnum.RUNNING.value)
        for value in (CollectStatusEnum.UNKNOWN.value, CollectStatusEnum.PREPARE.value):
            label = CollectStatusEnum.get_choice_label(value)
            self.assertNotEqual(label, value, f"{value} 缺少展示文案")
            self.assertNotEqual(label, running_label, f"{value} 不应复用“部署中”文案")


class GetCollectorStatusTests(SimpleTestCase):
    @staticmethod
    def _mock_subscription_status(aggregated_status):
        handler = MagicMock()
        handler.get_subscription_status_by_list.return_value = [
            {"collector_id": 89, "status": aggregated_status, "status_name": "ignored"}
        ]
        return handler

    def _get_status(self, aggregated_status):
        handler = self._mock_subscription_status(aggregated_status)
        with patch(
            "apps.log_databus.handlers.collector_handler.log.CollectorHandler",
            return_value=handler,
        ):
            result = LogCollectorHandler.get_collector_status([89])
        handler.get_subscription_status_by_list.assert_called_once_with([89])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["collector_id"], 89)
        return result[0]

    def test_empty_subscription_scope_is_not_reported_as_deploying(self):
        item = self._get_status(CollectStatus.UNKNOWN)
        self.assertEqual(item["status"], CollectStatusEnum.UNKNOWN.value)
        self.assertEqual(item["status_name"], CollectStatusEnum.get_choice_label(CollectStatusEnum.UNKNOWN.value))

    def test_collector_without_subscription_is_reported_as_prepare(self):
        item = self._get_status(CollectStatus.PREPARE)
        self.assertEqual(item["status"], CollectStatusEnum.PREPARE.value)
        self.assertEqual(item["status_name"], CollectStatusEnum.get_choice_label(CollectStatusEnum.PREPARE.value))

    def test_pending_instances_are_still_reported_as_deploying(self):
        item = self._get_status(CollectStatus.PENDING)
        self.assertEqual(item["status"], CollectStatusEnum.RUNNING.value)
