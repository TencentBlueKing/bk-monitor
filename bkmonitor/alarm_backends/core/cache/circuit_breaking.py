"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any

from alarm_backends.core.cache.base import CacheManager
from alarm_backends.core.cache.key import PUBLIC_KEY_PREFIX
from constants.action import ActionPluginType

logger = logging.getLogger("circuit_breaking")


class CircuitBreakingModule(Enum):
    """
    熔断模块枚举
    定义了所有支持熔断的模块名称
    """

    ACCESS_DATA = "access.data"
    ALERT_BUILDER = "alert.builder"
    ACTION = "action"

    @classmethod
    def get_all_values(cls) -> list[str]:
        """获取所有模块名称列表"""
        return [module.value for module in cls]

    @classmethod
    def is_valid_module(cls, module: str) -> bool:
        """检查模块名称是否有效"""
        return module in cls.get_all_values()


class CircuitBreakingCacheManager(CacheManager):
    """
    熔断配置缓存管理器
    """

    CACHE_KEY_PREFIX = f"{PUBLIC_KEY_PREFIX}.cache.circuit_breaking"
    CACHE_TIMEOUT = 60 * 60 * 24  # 24小时

    @classmethod
    def get_cache_key(cls, module: str) -> str:
        """
        获取模块熔断配置的缓存key
        :param module: 模块名称，如 access.data
        :return: 缓存key
        """
        return f"{cls.CACHE_KEY_PREFIX}.{module}"

    @classmethod
    def get_config(cls, module: str) -> list[dict[str, Any]]:
        """
        获取指定模块的熔断配置
        :param module: 模块名称
        :return: 熔断配置列表
        """
        if not module:
            return []

        cache_key = cls.get_cache_key(module)
        try:
            config_data = cls.cache.get(cache_key)
            if config_data:
                return json.loads(config_data)
            return []
        except Exception as e:
            logger.error(f"[circuit breaking] Failed to get circuit breaking config for module {module}: {e}")
            return []

    @classmethod
    def set_config(cls, module: str, config: list[dict[str, Any]]) -> bool:
        """
        设置指定模块的熔断配置
        :param module: 模块名称
        :param config: 熔断配置列表
        :return: 是否设置成功
        """
        # 验证模块名称是否有效
        if not CircuitBreakingModule.is_valid_module(module):
            logger.warning(
                f"[circuit breaking] Invalid module name: {module}. Valid modules: {CircuitBreakingModule.get_all_values()}"
            )
            # 不阻止设置，只记录警告，保持向后兼容性

        cache_key = cls.get_cache_key(module)
        try:
            config_data = json.dumps(config, ensure_ascii=False)
            cls.cache.set(cache_key, config_data, cls.CACHE_TIMEOUT)
            if len(config) > 0:
                logger.info(f"[circuit breaking] Set circuit breaking config for module {module}: {len(config)} rules")
            else:
                logger.info(f"[circuit breaking] Clear circuit breaking config for module {module}")
            return True
        except Exception as e:
            logger.error(f"[circuit breaking] Failed to set circuit breaking config for module {module}: {e}")
            return False

    @classmethod
    def delete_config(cls, module: str) -> bool:
        """
        删除指定模块的熔断配置
        :param module: 模块名称
        :return: 是否删除成功
        """
        cache_key = cls.get_cache_key(module)
        try:
            cls.cache.delete(cache_key)
            logger.info(f"[circuit breaking] Deleted circuit breaking config for module {module}")
            return True
        except Exception as e:
            logger.error(f"[circuit breaking] Failed to delete circuit breaking config for module {module}: {e}")
            return False

    @classmethod
    def add_rule(cls, module: str, rule: dict[str, Any]) -> bool:
        """
        为指定模块添加熔断规则
        :param module: 模块名称
        :param rule: 熔断规则
        :return: 是否添加成功
        """
        config = cls.get_config(module)
        config.append(rule)
        return cls.set_config(module, config)

    @classmethod
    def get_all_modules(cls) -> dict[str, list[dict[str, Any]]]:
        """
        获取所有配置了熔断规则的模块及其配置
        使用预定义的模块枚举，避免Redis keys命令的性能问题
        :return: 以模块名为key，熔断规则配置为value的字典
        """
        try:
            configured_modules = {}
            # 遍历所有预定义的模块，检查是否有配置
            for module in CircuitBreakingModule.get_all_values():
                config = cls.get_config(module)
                if config:  # 只有当配置不为空时才添加到结果中
                    configured_modules[module] = config
            return configured_modules
        except Exception as e:
            logger.error(f"[circuit breaking] Failed to get all circuit breaking modules: {e}")
            return {}

    # ==================== 预设快捷设置函数 ====================

    @classmethod
    def set_strategy_source_circuit_breaking(
        cls,
        module: str,
        strategy_sources: list[str],
        method: str = "eq",
        condition: str = "and",
        description: str | None = None,
    ) -> bool:
        """
        快捷设置基于strategy_source的熔断规则

        :param module: 模块名称，如 "access.data"
        :param strategy_sources: 数据源组合列表，如 ["bk_monitor:time_series", "bk_log_search:log"]
        :param method: 匹配方法，默认 "eq"
        :param condition: 条件逻辑，默认 "and"
        :param description: 规则描述
        :return: 是否设置成功
        """
        if not strategy_sources:
            logger.warning("[circuit breaking] strategy_sources cannot be empty")
            return False

        rule = {"key": "strategy_source", "method": method, "value": strategy_sources, "condition": condition}

        if description:
            rule["description"] = description
        else:
            rule["description"] = f"创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        logger.info(
            f"[circuit breaking] Setting strategy_source circuit breaking for module {module}: {strategy_sources}"
        )
        return cls.add_rule(module, rule)

    @classmethod
    def set_bk_biz_id_circuit_breaking(
        cls,
        module: str,
        bk_biz_ids: list[str],
        method: str = "eq",
        condition: str = "and",
        description: str | None = None,
    ) -> bool:
        """
        快捷设置基于bk_biz_id的熔断规则

        :param module: 模块名称，如 "access.data"
        :param bk_biz_ids: 业务ID列表，如 ["100", "200"]
        :param method: 匹配方法，默认 "eq"
        :param condition: 条件逻辑，默认 "and"
        :param description: 规则描述
        :return: 是否设置成功
        """
        if not bk_biz_ids:
            logger.warning("[circuit breaking] bk_biz_ids cannot be empty")
            return False

        rule = {"key": "bk_biz_id", "method": method, "value": bk_biz_ids, "condition": condition}

        if description:
            rule["description"] = description
        else:
            rule["description"] = f"创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        logger.info(f"[circuit breaking] Setting bk_biz_id circuit breaking for module {module}: {bk_biz_ids}")
        return cls.add_rule(module, rule)

    @classmethod
    def set_data_source_circuit_breaking(
        cls,
        module: str,
        data_source_labels: list[str],
        data_type_labels: list[str] | None = None,
        method: str = "eq",
        condition: str = "and",
        description: str | None = None,
    ) -> bool:
        """
        快捷设置基于数据源标签的熔断规则

        :param module: 模块名称，如 "access.data"
        :param data_source_labels: 数据源标签列表，如 ["bk_monitor", "bk_log_search"]
        :param data_type_labels: 数据类型标签列表，如 ["time_series", "log"]，可选
        :param method: 匹配方法，默认 "eq"
        :param condition: 条件逻辑，默认 "and"
        :param description: 规则描述
        :return: 是否设置成功
        """
        if not data_source_labels:
            logger.warning("[circuit breaking] data_source_labels cannot be empty")
            return False

        # 添加数据源标签规则
        source_rule = {
            "key": "data_source_label",
            "method": method,
            "value": data_source_labels,
            "condition": condition,
        }

        if description:
            source_rule["description"] = description
        else:
            source_rule["description"] = f"创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        success = cls.add_rule(module, source_rule)

        # 如果指定了数据类型标签，添加数据类型规则
        if data_type_labels and success:
            type_rule = {
                "key": "data_type_label",
                "method": method,
                "value": data_type_labels,
                "condition": "and",  # 与数据源标签形成AND关系
            }
            type_rule["description"] = f"创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            success = cls.add_rule(module, type_rule)

        logger.info(
            f"[circuit breaking] Setting data_source circuit breaking for module {module}: "
            f"sources={data_source_labels}, types={data_type_labels}"
        )
        return success

    @classmethod
    def set_strategy_circuit_breaking(
        cls,
        module: str,
        strategy_ids: list[str | int],
        description: str | None = None,
    ) -> bool:
        """
        按策略ID设置熔断规则的快捷方法

        :param module: 模块名称，如 "access.data"
        :param strategy_ids: 策略ID列表
        :param description: 规则描述
        :return: 是否设置成功
        """
        if not strategy_ids:
            logger.warning("[circuit breaking] Strategy IDs must be provided")
            return False

        # 将策略ID转换为字符串列表
        str_strategy_ids = [str(sid) for sid in strategy_ids]

        # 构建熔断规则
        rule = {
            "key": "strategy_id",
            "method": "eq",
            "value": str_strategy_ids,
            "condition": "and",
            "description": description or f"创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        }

        # 添加规则
        success = cls.add_rule(module, rule)

        if success:
            logger.info(f"[circuit breaking] Setting strategy circuit breaking for module {module}: {str_strategy_ids}")
        else:
            logger.error(f"[circuit breaking] Failed to set strategy circuit breaking for module {module}")

        return success

    @classmethod
    def set_plugin_type_circuit_breaking(
        cls,
        module: str,
        plugin_types: list[str],
        method: str = "eq",
        condition: str = "and",
        description: str | None = None,
    ) -> bool:
        """
        快捷设置基于plugin_type的熔断规则（主要用于action模块）

        :param module: 模块名称，如 "action"
        :param plugin_types: 套餐类型列表，如 ["notice", "webhook", "itsm"]
        :param method: 匹配方法，默认 "eq"
        :param condition: 条件逻辑，默认 "and"
        :param description: 规则描述
        :return: 是否设置成功
        """
        if not plugin_types:
            logger.warning("[circuit breaking] plugin_types cannot be empty")
            return False

        rule = {"key": "plugin_type", "method": method, "value": plugin_types, "condition": condition}

        if description:
            rule["description"] = description
        else:
            rule["description"] = f"创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        logger.info(f"[circuit breaking] Setting plugin_type circuit breaking for module {module}: {plugin_types}")
        return cls.add_rule(module, rule)

    @classmethod
    def clear(
        cls,
        module: str | None = None,
    ) -> bool:
        """
        清空现有配置

        :param module: 模块名称，如果为None则清空所有模块的配置
        :return: 是否清空成功
        """
        if module is None:
            # 清空所有模块的配置
            success = True
            cleared_count = 0
            for module_name in CircuitBreakingModule.get_all_values():
                if cls.set_config(module_name, []):
                    cleared_count += 1
                else:
                    success = False
                    logger.error(f"[circuit breaking] Failed to clear config for module {module_name}")

            if success:
                logger.info(
                    f"[circuit breaking] Successfully cleared all circuit breaking configs ({cleared_count} modules)"
                )
            else:
                logger.warning(
                    f"[circuit breaking] Partially cleared circuit breaking configs ({cleared_count} modules)"
                )

            return success
        else:
            # 清空指定模块的配置
            return cls.set_config(module, [])


# ==================== 预设快捷设置便捷函数 ====================


def set_strategy_source_circuit_breaking(
    module: str, strategy_sources: list[str], method: str = "eq", condition: str = "and", description: str | None = None
) -> bool:
    """
    快捷设置基于strategy_source的熔断规则（便捷函数）

    :param module: 模块名称，如 "access.data"
    :param strategy_sources: 数据源组合列表，如 ["bk_monitor:time_series", "bk_log_search:log"]
    :param method: 匹配方法，默认 "eq"
    :param condition: 条件逻辑，默认 "and"
    :param description: 规则描述
    :return: 是否设置成功
    """
    return CircuitBreakingCacheManager.set_strategy_source_circuit_breaking(
        module, strategy_sources, method, condition, description
    )


def set_bk_biz_id_circuit_breaking(
    module: str, bk_biz_ids: list[str], method: str = "eq", condition: str = "and", description: str | None = None
) -> bool:
    """
    快捷设置基于bk_biz_id的熔断规则（便捷函数）

    :param module: 模块名称，如 "access.data"
    :param bk_biz_ids: 业务ID列表，如 ["100", "200"]
    :param method: 匹配方法，默认 "eq"
    :param condition: 条件逻辑，默认 "and"
    :param description: 规则描述
    :return: 是否设置成功
    """
    return CircuitBreakingCacheManager.set_bk_biz_id_circuit_breaking(
        module, bk_biz_ids, method, condition, description
    )


def set_data_source_circuit_breaking(
    module: str,
    data_source_labels: list[str],
    data_type_labels: list[str] | None = None,
    method: str = "eq",
    condition: str = "and",
    description: str | None = None,
) -> bool:
    """
    快捷设置基于数据源标签的熔断规则（便捷函数）

    :param module: 模块名称，如 "access.data"
    :param data_source_labels: 数据源标签列表，如 ["bk_monitor", "bk_log_search"]
    :param data_type_labels: 数据类型标签列表，如 ["time_series", "log"]，可选
    :param method: 匹配方法，默认 "eq"
    :param condition: 条件逻辑，默认 "and"
    :param description: 规则描述
    :return: 是否设置成功
    """
    return CircuitBreakingCacheManager.set_data_source_circuit_breaking(
        module, data_source_labels, data_type_labels, method, condition, description
    )


def set_strategy_circuit_breaking(
    module: str,
    strategy_ids: list[str | int],
    description: str | None = None,
) -> bool:
    """
    按策略ID设置熔断规则的快捷方法（便捷函数）

    :param module: 模块名称，如 "access.data"
    :param strategy_ids: 策略ID列表
    :param description: 规则描述
    :return: 是否设置成功
    """
    return CircuitBreakingCacheManager.set_strategy_circuit_breaking(module, strategy_ids, description)


def set_plugin_type_circuit_breaking(
    module: str,
    plugin_types: list[str],
    method: str = "eq",
    condition: str = "and",
    description: str | None = None,
) -> bool:
    """
    快捷设置基于plugin_type的熔断规则（便捷函数，主要用于action模块）

    :param module: 模块名称，如 "action"
    :param plugin_types: 套餐类型列表，如 ["notice", "webhook", "itsm"]
    :param method: 匹配方法，默认 "eq"
    :param condition: 条件逻辑，默认 "and"
    :param description: 规则描述
    :return: 是否设置成功
    """
    return CircuitBreakingCacheManager.set_plugin_type_circuit_breaking(
        module, plugin_types, method, condition, description
    )


def clear(
    module: str | None = None,
) -> bool:
    """
    清空现有配置

    :param module: 模块名称，如果为None则清空所有模块的配置
    :return: 是否清空成功
    """
    return CircuitBreakingCacheManager.clear(module)


# 通知套餐
NOTICE_PLUGIN_TYPES = [ActionPluginType.NOTICE, ActionPluginType.COLLECT]

# 消息队列推送套餐
MESSAGE_QUEUE_PLUGIN_TYPES = [ActionPluginType.MESSAGE_QUEUE]

# webhook套餐
WEBHOOK_PLUGIN_TYPES = [ActionPluginType.WEBHOOK]

# 常见的数据源组合 - 基于 constants.data_source.DATA_CATEGORY
COMMON_DATA_SOURCE_COMBINATIONS = [
    "bk_monitor:time_series",  # 监控采集指标
    "prometheus:time_series",  # Prometheus指标
    "bk_log_search:time_series",  # 日志平台指标
    "bk_monitor:event",  # 系统事件
    "bk_data:time_series",  # 计算平台指标
    "custom:event",  # 自定义事件
    "custom:time_series",  # 自定义指标
    "bk_log_search:log",  # 日志平台关键字
    "bk_monitor:log",  # 日志关键字事件
    "bk_fta:event",  # 第三方告警
    "bk_fta:alert",  # 关联告警
    "bk_monitor:alert",  # 关联策略
    "bk_apm:time_series",  # Trace明细指标
    "bk_apm:log",  # Trace数据
]


# ==================== 使用示例 ====================


example_usage = """预设快捷设置函数的使用示例:
module = "access.data"
module = "alert.builder"
module = "action"

# 示例1: 设置基于strategy_source的熔断
set_strategy_source_circuit_breaking(
    module=module,
    strategy_sources=["bk_monitor:time_series", "bk_log_search:log"],
)

# 示例2: 设置基于bk_biz_id的熔断
set_bk_biz_id_circuit_breaking(
    module=module,
    bk_biz_ids=["100", "200"],
)

# 示例3: 设置策略熔断规则
set_strategy_circuit_breaking(
    module=module,
    strategy_ids=[12345, 67890],
    description="测试策略熔断",
)

# 示例4: 设置基于通知的熔断（用于action模块）
set_plugin_type_circuit_breaking(
    module="action",
    plugin_types=NOTICE_PLUGIN_TYPES,
    description="熔断通知套餐",
)

# 示例5: 熔断业务100下的bk_monitor:time_series
set_bk_biz_id_circuit_breaking(module=module, bk_biz_ids=["100"])
set_strategy_source_circuit_breaking(module=module, strategy_sources=["bk_monitor:time_series"])

# 示例6: action模块组合熔断 - 熔断业务100下的消息队列推送
set_bk_biz_id_circuit_breaking(module="action", bk_biz_ids=["100"])
set_plugin_type_circuit_breaking(module="action", plugin_types=MESSAGE_QUEUE_PLUGIN_TYPES)

# 示例7: 清空指定模块的所有规则
clear(module=module)

# 示例8: 清空所有模块的所有规则
clear()
"""

print(example_usage)
