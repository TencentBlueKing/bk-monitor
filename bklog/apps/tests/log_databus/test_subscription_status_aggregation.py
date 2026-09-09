"""采集项订阅状态聚合测试。

目标主机从 CMDB 移除后订阅范围变空，节点管理统计各状态 count 全为 0、instances 也为 0。
此时若聚合成 UNKNOWN，会被 CollectStatusEnum 兜底成 RUNNING，采集项永远显示“部署中”，
且停用/删除按钮不可点而无法清理；而统计尚未产出的瞬时态仍需保持 UNKNOWN 以续上前端轮询。
"""

from django.test import SimpleTestCase

from apps.log_databus.constants import CollectStatus, RunStatus
from apps.log_databus.handlers.collector.base import CollectorHandler
from apps.log_search.constants import CollectStatusEnum

SUBSCRIPTION_ID = 180
COLLECTOR_ID = 89


def build_statistic(instances, counts=None):
    """构造 NodeApi.subscription_statistic 中单个订阅的返回结构。"""
    counts = counts or {}
    return {
        "subscription_id": SUBSCRIPTION_ID,
        "status": [
            {"status": status, "count": counts.get(status, 0)}
            for status in (
                CollectStatus.SUCCESS,
                CollectStatus.PENDING,
                CollectStatus.RUNNING,
                CollectStatus.FAILED,
                CollectStatus.TERMINATED,
            )
        ],
        "versions": [],
        "instances": instances,
    }


class FormatSubscriptionStatusTests(SimpleTestCase):
    def aggregate(self, instances, counts=None):
        return_data, remaining = CollectorHandler.format_subscription_status(
            [build_statistic(instances, counts)],
            [SUBSCRIPTION_ID],
            {SUBSCRIPTION_ID: COLLECTOR_ID},
        )
        # 已聚合出状态的订阅必须从待补齐列表中移除，否则调用方会再按“未查到订阅”追加一条重复记录
        self.assertEqual(remaining, [])
        self.assertEqual(len(return_data), 1)
        return return_data[0]

    def test_empty_subscription_scope_is_reported_as_failed(self):
        """订阅范围为空时采集不可能成功，应直接给出失败而非未知。"""
        item = self.aggregate(instances=0)

        self.assertEqual(item["status"], CollectStatus.FAILED)
        self.assertEqual(item["status_name"], RunStatus.FAILED)
        self.assertEqual((item["total"], item["success"], item["failed"], item["pending"]), (0, 0, 0, 0))
        # 列表页据此显示“异常”并放开停用按钮，用户可停用后删除这个已失效的采集项
        self.assertEqual(CollectStatusEnum.get_collect_status(item["status"]), CollectStatusEnum.FAILED.value)

    def test_statistic_not_ready_stays_unknown_to_keep_polling(self):
        """订阅已下发但统计尚未产出属瞬时态，需保持兜底成部署中以便前端继续轮询。"""
        item = self.aggregate(instances=3)

        self.assertEqual(item["status"], CollectStatus.UNKNOWN)
        self.assertEqual(item["status_name"], RunStatus.UNKNOWN)
        self.assertEqual(item["total"], 3)
        self.assertEqual(CollectStatusEnum.get_collect_status(item["status"]), CollectStatusEnum.RUNNING.value)

    def test_known_status_aggregation_is_unchanged(self):
        """有实例状态时的聚合规则不受本次改动影响。"""
        cases = {
            CollectStatus.PENDING: (CollectStatus.RUNNING, RunStatus.RUNNING),
            CollectStatus.RUNNING: (CollectStatus.RUNNING, RunStatus.RUNNING),
            CollectStatus.FAILED: (CollectStatus.FAILED, RunStatus.FAILED),
            CollectStatus.SUCCESS: (CollectStatus.SUCCESS, RunStatus.SUCCESS),
            CollectStatus.TERMINATED: (CollectStatus.TERMINATED, RunStatus.TERMINATED),
        }
        for raw_status, (expected_status, expected_name) in cases.items():
            with self.subTest(status=raw_status):
                item = self.aggregate(instances=1, counts={raw_status: 1})
                self.assertEqual((item["status"], item["status_name"]), (expected_status, expected_name))

        item = self.aggregate(instances=2, counts={CollectStatus.SUCCESS: 1, CollectStatus.FAILED: 1})
        self.assertEqual((item["status"], item["status_name"]), (CollectStatus.FAILED, RunStatus.PARTFAILED))
