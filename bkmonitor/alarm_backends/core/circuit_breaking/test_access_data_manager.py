#!/usr/bin/env python3
"""
AccessDataCircuitBreakingManager 自测脚本
验证熔断判定结果的正确性
"""

import sys
import os
import logging
from typing import Any

# 添加项目路径到sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from alarm_backends.core.circuit_breaking.manager import AccessDataCircuitBreakingManager
from alarm_backends.core.cache.circuit_breaking import (
    CircuitBreakingCacheManager,
    set_strategy_source_circuit_breaking,
    set_bk_biz_id_circuit_breaking,
    set_data_source_circuit_breaking,
    clear,
)

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class AccessDataCircuitBreakingTest:
    """AccessDataCircuitBreakingManager 测试类"""

    def __init__(self):
        self.module = "access.data"
        self.manager = AccessDataCircuitBreakingManager(self.module)
        self.test_results = []

    def run_test_case(self, test_name: str, test_data: dict[str, Any], expected: bool) -> bool:
        """
        运行单个测试用例
        :param test_name: 测试用例名称
        :param test_data: 测试数据
        :param expected: 期望结果
        :return: 测试是否通过
        """
        try:
            result = self.manager.is_circuit_breaking(**test_data)
            passed = result == expected

            status = "✅ PASS" if passed else "❌ FAIL"
            logger.info(f"{status} {test_name}")
            logger.info(f"  输入数据: {test_data}")
            logger.info(f"  期望结果: {expected}")
            logger.info(f"  实际结果: {result}")

            self.test_results.append(
                {"name": test_name, "data": test_data, "expected": expected, "actual": result, "passed": passed}
            )

            return passed

        except Exception as e:
            logger.error(f"❌ ERROR {test_name}: {e}")
            self.test_results.append(
                {
                    "name": test_name,
                    "data": test_data,
                    "expected": expected,
                    "actual": None,
                    "passed": False,
                    "error": str(e),
                }
            )
            return False

    def test_strategy_source_circuit_breaking(self):
        """测试基于strategy_source的熔断"""
        logger.info("\n=== 测试 strategy_source 熔断 ===")
        # 清空现有配置
        clear(self.module)
        # 1. 设置基于strategy_source的熔断
        set_strategy_source_circuit_breaking(
            module=self.module, strategy_sources=["bk_log_search:log"], description="测试用例1: strategy_source熔断"
        )
        # 重新初始化manager以加载新配置
        self.manager = AccessDataCircuitBreakingManager(self.module)

        # 打印当前配置
        config = CircuitBreakingCacheManager.get_config(self.module)
        logger.info(f"当前熔断配置: {config}")

        # 应该触发熔断的情况
        self.run_test_case(
            "strategy_source熔断 - bk_log_search:log",
            {"data_source_label": "bk_log_search", "data_type_label": "log"},
            True,
        )

        # 不应该触发熔断的情况
        self.run_test_case(
            "strategy_source熔断 - bk_monitor:time_series",
            {"data_source_label": "bk_monitor", "data_type_label": "time_series"},
            False,
        )

        self.run_test_case(
            "strategy_source不熔断 - bk_monitor:log",
            {"data_source_label": "bk_monitor", "data_type_label": "log"},
            False,
        )

        self.run_test_case(
            "strategy_source不熔断 - prometheus:time_series",
            {"data_source_label": "prometheus", "data_type_label": "time_series"},
            False,
        )

    def test_bk_biz_id_circuit_breaking(self):
        """测试基于bk_biz_id的熔断"""
        logger.info("\n=== 测试 bk_biz_id 熔断 ===")
        # 清空现有配置
        clear(self.module)

        # 2. 设置基于bk_biz_id的熔断
        set_bk_biz_id_circuit_breaking(
            module=self.module, bk_biz_ids=["100", "-200"], description="测试用例2: bk_biz_id熔断"
        )

        # 重新初始化manager以加载新配置
        self.manager = AccessDataCircuitBreakingManager(self.module)

        # 打印当前配置
        config = CircuitBreakingCacheManager.get_config(self.module)
        logger.info(f"当前熔断配置: {config}")
        # 应该触发熔断的情况
        self.run_test_case("bk_biz_id熔断 - 业务100", {"bk_biz_id": 100}, True)
        self.run_test_case("bk_biz_id熔断 - 业务100", {"bk_biz_id": -200}, True)

        self.run_test_case(
            "bk_biz_id熔断 - 业务200",
            {"bk_biz_id": "200"},  # 测试字符串类型
            False,
        )

        # 不应该触发熔断的情况
        self.run_test_case("bk_biz_id不熔断 - 业务999", {"bk_biz_id": 999}, False)

    def test_data_source_label_circuit_breaking(self):
        """测试基于数据源标签的熔断"""
        logger.info("\n=== 测试数据源标签熔断 ===")
        # 清空现有配置
        clear(self.module)

        # 3. 设置基于数据源标签的熔断
        set_data_source_circuit_breaking(
            module=self.module,
            data_source_labels=["bk_log_search"],
            data_type_labels=["time_series"],
            description="测试用例3: 数据源标签熔断",
        )
        # 重新初始化manager以加载新配置
        self.manager = AccessDataCircuitBreakingManager(self.module)

        # 打印当前配置
        config = CircuitBreakingCacheManager.get_config(self.module)
        logger.info(f"当前熔断配置: {config}")
        # 应该触发熔断的情况（需要同时匹配data_source_label和data_type_label）
        self.run_test_case(
            "数据源标签熔断 - bk_log_search + time_series",
            {"data_source_label": "bk_log_search", "data_type_label": "time_series"},
            True,
        )

        # 不应该触发熔断的情况
        self.run_test_case(
            "数据源标签不熔断 - bk_log_search + log",
            {"data_source_label": "bk_log_search", "data_type_label": "log"},
            False,
        )

        self.run_test_case(
            "数据源标签不熔断 - bk_monitor + time_series",
            {"data_source_label": "bk_monitor", "data_type_label": "time_series"},
            False,
        )

    def test_strategy_only_circuit_breaking(self):
        """测试策略级别的熔断"""
        logger.info("\n=== 测试策略级别熔断 ===")
        # 清空现有配置
        clear(self.module)

        # 先添加策略级别的熔断规则
        CircuitBreakingCacheManager.set_strategy_circuit_breaking(self.module, ["1001", "1002"])

        # 重新初始化manager以加载新配置
        self.manager = AccessDataCircuitBreakingManager(self.module)

        # 打印当前配置
        config = CircuitBreakingCacheManager.get_config(self.module)
        logger.info(f"当前熔断配置: {config}")

        # 重新初始化manager
        self.manager = AccessDataCircuitBreakingManager(self.module)

        # 测试策略级别熔断
        try:
            self.run_test_case("策略级别熔断 - 策略1001", {"strategy_id": 1001}, True)
            self.run_test_case("策略级别熔断 - 策略9999", {"strategy_id": 9999}, False)

        except Exception as e:
            logger.error(f"❌ 策略级别熔断测试失败: {e}")

    def test_circuit_breaking_before_pull(self):
        """测试数据查询前的策略级别熔断检查"""
        logger.info("\n=== 测试数据查询前策略级别熔断检查 ===")

        # 测试策略级别熔断场景（只检查策略ID维度）
        test_cases = [
            {"test_name": "策略级别熔断 - 策略ID 12345", "test_data": {"strategy_id": 12345}, "expected": True},
            {"test_name": "策略级别熔断 - 策略ID 67890", "test_data": {"strategy_id": 67890}, "expected": True},
            {"test_name": "策略级别熔断 - 不匹配的策略ID", "test_data": {"strategy_id": 99999}, "expected": False},
            {"test_name": "策略级别熔断 - 策略ID为空", "test_data": {}, "expected": False},
        ]
        # 清空现有配置
        clear(self.module)

        # 先添加策略级别的熔断规则
        CircuitBreakingCacheManager.add_rule(
            self.module,
            {
                "key": "strategy_id",
                "method": "eq",
                "value": ["12345", "67890"],
                "condition": "or",
                "description": "策略级别熔断测试",
            },
        )

        # 重新初始化manager以加载新配置
        self.manager = AccessDataCircuitBreakingManager(self.module)

        # 打印当前配置
        config = CircuitBreakingCacheManager.get_config(self.module)
        logger.info(f"当前熔断配置: {config}")

        # 重新初始化manager
        self.manager = AccessDataCircuitBreakingManager(self.module)

        for test_case in test_cases:
            self.run_test_case(**test_case)

    def test_items_property_modification(self):
        """测试items属性的修改功能"""
        logger.info("\n=== 测试items属性修改功能 ===")

        try:
            # 模拟AccessDataProcess类的items属性行为
            class MockAccessDataProcess:
                def __init__(self):
                    self.strategy_group_key = "test_group"

                def _load_items(self):
                    # 模拟返回3个item
                    return [f"item_{i}" for i in range(3)]

                @property
                def items(self):
                    if not hasattr(self, "_items") or self._items is None:
                        self._items = self._load_items()
                    return self._items

                @items.setter
                def items(self, value):
                    self._items = value

            # 创建测试实例
            processor = MockAccessDataProcess()

            # 测试初始加载
            initial_items = processor.items
            logger.info(f"初始items: {initial_items}")
            assert len(initial_items) == 3, "初始items数量应为3"

            # 测试修改items
            filtered_items = ["item_0", "item_2"]  # 模拟熔断后剩余的items
            processor.items = filtered_items

            # 验证修改后的items
            modified_items = processor.items
            logger.info(f"修改后items: {modified_items}")
            assert len(modified_items) == 2, "修改后items数量应为2"
            assert modified_items == filtered_items, "修改后的items应与设置的值相同"

            logger.info("✅ items属性修改功能测试通过")

        except Exception as e:
            logger.error(f"❌ items属性修改功能测试失败: {e}")

        logger.info("-" * 50)

    def test_edge_cases(self):
        """测试边界情况"""
        logger.info("\n=== 测试边界情况 ===")

        # 空数据
        self.run_test_case("边界情况 - 空数据", {}, False)

        # None值
        self.run_test_case("边界情况 - None值", {"bk_biz_id": None, "data_source_label": None}, False)

        # 不存在的字段
        self.run_test_case("边界情况 - 不存在的字段", {"unknown_field": "test"}, False)

    def run_all_tests(self):
        """运行所有测试"""
        logger.info("开始运行 AccessDataCircuitBreakingManager 自测...")

        # 运行各项测试
        self.test_strategy_source_circuit_breaking()
        self.test_bk_biz_id_circuit_breaking()
        self.test_data_source_label_circuit_breaking()
        self.test_strategy_only_circuit_breaking()
        self.test_circuit_breaking_before_pull()
        self.test_items_property_modification()
        self.test_edge_cases()

        # 输出测试结果统计
        return self.print_test_summary()

    def print_test_summary(self):
        """打印测试结果统计"""
        logger.info("\n" + "=" * 60)
        logger.info("测试结果统计")
        logger.info("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["passed"])
        failed_tests = total_tests - passed_tests

        logger.info(f"总测试数: {total_tests}")
        logger.info(f"通过数: {passed_tests}")
        logger.info(f"失败数: {failed_tests}")
        logger.info(f"通过率: {passed_tests / total_tests * 100:.1f}%")

        if failed_tests > 0:
            logger.info("\n失败的测试用例:")
            for result in self.test_results:
                if not result["passed"]:
                    logger.info(f"  ❌ {result['name']}")
                    if "error" in result:
                        logger.info(f"     错误: {result['error']}")
                    else:
                        logger.info(f"     期望: {result['expected']}, 实际: {result['actual']}")

        logger.info("=" * 60)

        return passed_tests == total_tests


def main():
    """主函数"""
    try:
        # 创建测试实例并运行测试
        test = AccessDataCircuitBreakingTest()
        success = test.run_all_tests()

        if success:
            logger.info("🎉 所有测试通过!")
            sys.exit(0)
        else:
            logger.error("💥 部分测试失败!")
            sys.exit(1)

    except Exception as e:
        logger.error(f"测试运行失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
