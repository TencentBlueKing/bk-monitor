"""
流控维度匹配器

基于 gen_condition_matcher 的设计模式，实现统一抽象的流控维度匹配功能。
支持多种匹配方法和逻辑连接符，用于判断数据是否命中流控规则。
"""

import logging
from typing import Any

from django.db.models.sql.where import AND, OR

from bkmonitor.utils.range import load_condition_instance

logger = logging.getLogger("circuit_breaking.matcher")


class CircuitBreakingMatcher:
    """
        流控维度匹配器

        基于配置规则匹配数据维度，判断是否需要进行流控。
    支持多种匹配方法：eq, neq, lt, lte, gt, gte, reg, nreg, include, exclude, issuperset 等。
        支持 AND/OR 逻辑连接符。
    """

    # 支持的匹配方法（与 load_condition_instance 中的 CONDITION_CLASS_MAP 对齐）
    SUPPORTED_METHODS = {
        "eq": "等于",
        "neq": "不等于",
        "lt": "小于",
        "lte": "小于等于",
        "gt": "大于",
        "gte": "大于等于",
        "reg": "正则匹配",
        "nreg": "正则不匹配",
        "include": "包含",
        "exclude": "不包含",
        "issuperset": "是超集",
    }

    def __init__(self, config_rules: list[dict[str, Any]]):
        """
        初始化匹配器

        Args:
            config_rules: 流控配置规则列表
                格式: [
                    {
                        "key": "bk_biz_id",
                        "method": "eq",
                        "value": ["100", "200"],
                        "condition": "and"  # 可选，默认为 "and"
                    },
                    ...
                ]
        """
        self.config_rules = config_rules or []
        self.condition_matcher = None

        if self.config_rules:
            self.condition_matcher = self._build_condition_matcher()

    def __bool__(self) -> bool:
        """
        是否有效

        Returns:
            bool: 是否有效
        """
        return bool(len(self.config_rules))

    def _build_condition_matcher(self):
        """
        构建条件匹配器，参考 gen_condition_matcher 的实现

        Returns:
            条件匹配器实例
        """
        if not self.config_rules:
            return None

        or_cond = []
        and_cond = []

        for cond in self.config_rules:
            # 验证配置格式
            if not self._validate_rule(cond):
                logger.warning(f"[circuit breaking] Invalid circuit breaking rule: {cond}")
                continue

            # 构建条件对象
            condition_obj = {"field": cond["key"], "method": cond["method"], "value": cond["value"]}

            # 获取连接符，默认为 AND，确保为字符串后再大写比较
            connector = cond.get("condition", AND)
            connector_upper = str(connector).upper()
            if connector_upper == AND:
                and_cond.append(condition_obj)
            elif connector_upper == OR:
                # 遇到 OR 时，将当前的 and_cond 加入 or_cond，开始新的 and_cond
                if and_cond:
                    or_cond.append(and_cond)
                and_cond = [condition_obj]
            else:
                logger.warning(f"[circuit breaking] Unsupported connector: {connector}, using AND instead")
                and_cond.append(condition_obj)

        # 添加最后的 and_cond
        if and_cond:
            or_cond.append(and_cond)

        if not or_cond:
            return None

        try:
            return load_condition_instance(or_cond, default_value_if_not_exists=False)
        except Exception as e:
            logger.error(f"[circuit breaking] Failed to build condition matcher: {e}")
            return None

    def _validate_rule(self, rule: dict[str, Any]) -> bool:
        """
        验证规则配置的有效性

        Args:
            rule: 单个规则配置

        Returns:
            bool: 是否有效
        """
        required_fields = ["key", "method", "value"]

        # 检查必需字段
        for field in required_fields:
            if field not in rule:
                return False

        # 检查方法是否支持
        method = rule["method"]
        if method not in self.SUPPORTED_METHODS:
            logger.warning(f"[circuit breaking] Unsupported method: {method}")
            return False

        # 检查值的格式
        value = rule["value"]
        if not isinstance(value, list | tuple | str | int | float):
            return False

        return True

    def _normalize_dimensions(self, dimensions: dict[str, Any]) -> dict[str, str]:
        """
        标准化维度数据，将所有值转换为字符串

        Args:
            dimensions: 原始维度数据字典

        Returns:
            Dict[str, str]: 标准化后的维度数据
        """
        normalized_dimensions = {}
        for key, value in dimensions.items():
            if value is not None:
                normalized_dimensions[key] = str(value)
            else:
                normalized_dimensions[key] = ""
        return normalized_dimensions

    def is_match(self, dimensions: dict[str, Any]) -> bool:
        """
        判断给定的维度数据是否匹配流控规则

        Args:
            dimensions: 维度数据字典
                格式: {
                    "bk_biz_id": 100,
                    "strategy_id": 123,
                    "data_source_label": "bk_monitor",
                    "data_type_label": "time_series",
                    "strategy_source": "bk_monitor:time_series"
                }

        Returns:
            bool: 是否匹配（True表示命中流控规则）
        """
        if not self.condition_matcher:
            return False

        try:
            normalized_dimensions = self._normalize_dimensions(dimensions)
            return self.condition_matcher.is_match(normalized_dimensions)
        except Exception as e:
            logger.error(f"[circuit breaking] Error matching dimensions {dimensions}: {e}")
            return False

    def get_match_summary(self, dimensions: dict[str, Any]) -> dict[str, Any]:
        """
        获取匹配摘要信息（轻量级，用于日志记录）

        Args:
            dimensions: 维度数据字典

        Returns:
            Dict: 匹配摘要信息
                {
                    "is_match": bool,           # 是否匹配
                    "rule_count": int,          # 总规则数
                    "dimensions": dict          # 标准化后的维度数据
                }
        """
        normalized_dimensions = self._normalize_dimensions(dimensions)
        is_match = self.is_match(dimensions)

        return {"is_match": is_match, "rule_count": len(self.config_rules), "dimensions": normalized_dimensions}


def create_circuit_breaking_matcher(config_rules: list[dict[str, Any]]) -> CircuitBreakingMatcher | None:
    """
    创建流控维度匹配器的工厂函数

    Args:
        config_rules: 流控配置规则列表

    Returns:
        CircuitBreakingMatcher: 匹配器实例，如果配置为空则返回 None
    """
    if not config_rules:
        return None

    return CircuitBreakingMatcher(config_rules)


def gen_circuit_breaking_matcher(cb_config: list[dict[str, Any]]) -> CircuitBreakingMatcher | None:
    """
    生成流控条件匹配器，参考 gen_condition_matcher 的命名风格

    Args:
        cb_config: 流控配置列表

    Returns:
        CircuitBreakingMatcher: 流控匹配器实例
    """
    return create_circuit_breaking_matcher(cb_config)
