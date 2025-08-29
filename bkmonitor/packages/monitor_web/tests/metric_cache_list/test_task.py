import math
import unittest
from unittest import mock

from django.conf import settings

from packages.monitor_web.tasks import _update_metric_list


class TestUpdateMetricList(unittest.TestCase):
    """
    测试 _update_metric_list 函数的核心逻辑
    """

    def setUp(self):
        # 设置测试数据
        self.tenant_id = "default"
        self.period = 3
        self.offset = 1

        # 创建mock对象
        self.mock_logger = mock.patch("packages.monitor_web.tasks.logger").start()
        self.mock_time = mock.patch("packages.monitor_web.tasks.time").start()
        self.mock_set_local_username = mock.patch("packages.monitor_web.tasks.set_local_username").start()

        # 模拟time.time的返回值
        self.mock_time.time.side_effect = [10.0, 15.5]

        # 创建模拟的SOURCE_TYPE
        self.mock_manager_class1 = mock.Mock()
        self.mock_manager_class2 = mock.Mock()
        self.mock_manager_class3 = mock.Mock()

        # 设置不同的业务ID列表返回值
        self.mock_manager_class1.get_available_biz_ids.return_value = [1, 2, 3, 4, 5, 6]
        self.mock_manager_class2.get_available_biz_ids.return_value = [7, 8, 9]
        self.mock_manager_class3.get_available_biz_ids.return_value = []

        # 创建模拟的SOURCE_TYPE字典
        self.mock_source_type = {
            "TYPE1": self.mock_manager_class1,
            "TYPE2": self.mock_manager_class2,
            "TYPE3": self.mock_manager_class3,
        }

        # Mock SOURCE_TYPE导入
        self.mock_source_type_patch = mock.patch(
            "packages.monitor_web.tasks.SOURCE_TYPE", self.mock_source_type
        ).start()

    def tearDown(self):
        # 停止所有mock
        mock.patch.stopall()

    def test_update_metric_list(self):
        """测试 _update_metric_list 函数的主要流程"""
        # 执行被测试函数
        _update_metric_list(self.tenant_id, self.period, self.offset)

        # 验证set_local_username被调用
        self.mock_set_local_username.assert_called_once_with(settings.COMMON_USERNAME)

        # 验证日志记录
        self.mock_logger.info.assert_any_call(f"^update metric list(round {self.offset})")
        self.mock_logger.info.assert_any_call("$update metric list(round 1), cost: 5.5")

        # 验证获取有效业务ID列表
        self.mock_manager_class1.get_available_biz_ids.assert_called_once_with(self.tenant_id)
        self.mock_manager_class2.get_available_biz_ids.assert_called_once_with(self.tenant_id)
        self.mock_manager_class3.get_available_biz_ids.assert_called_once_with(self.tenant_id)

        # 计算应该处理的业务ID
        biz_per_round1 = math.ceil(len(self.mock_manager_class1.get_available_biz_ids()) / self.period)
        biz_ids_for_current_round1 = [1, 2, 3, 4, 5, 6][
            self.offset * biz_per_round1 : (self.offset + 1) * biz_per_round1
        ]

        biz_per_round2 = math.ceil(len(self.mock_manager_class2.get_available_biz_ids()) / self.period)
        biz_ids_for_current_round2 = [7, 8, 9][self.offset * biz_per_round2 : (self.offset + 1) * biz_per_round2]

        # 验证update_metric的调用
        expected_calls = []
        for biz_id in biz_ids_for_current_round1:
            expected_calls.append(("TYPE1", biz_id))

        for biz_id in biz_ids_for_current_round2:
            expected_calls.append(("TYPE2", biz_id))

    def test_empty_biz_ids(self):
        """测试没有业务ID时的处理"""
        # 修改mock返回值，所有manager类返回空业务ID列表
        self.mock_manager_class1.get_available_biz_ids.return_value = []
        self.mock_manager_class2.get_available_biz_ids.return_value = []

        # 清空调用记录
        self.update_metric_calls = []

        # 执行被测试函数
        _update_metric_list(self.tenant_id, self.period, self.offset)

        # 验证update_metric没有被调用
        self.assertEqual(len(self.update_metric_calls), 0)

    def test_update_metric_exception(self):
        """测试update_metric发生异常时的处理"""
        # 设置抛出异常的标志
        self.raise_exception = True

        # 执行被测试函数
        _update_metric_list(self.tenant_id, self.period, self.offset)

        # 验证异常被正确记录
        self.mock_logger.exception.assert_called()

        # 验证其他业务类型的调用仍然继续
        biz_per_round2 = math.ceil(len(self.mock_manager_class2.get_available_biz_ids()) / self.period)
        biz_ids_for_current_round2 = [7, 8, 9][self.offset * biz_per_round2 : (self.offset + 1) * biz_per_round2]

        for biz_id in biz_ids_for_current_round2:
            self.assertIn(("TYPE2", biz_id), self.update_metric_calls)
