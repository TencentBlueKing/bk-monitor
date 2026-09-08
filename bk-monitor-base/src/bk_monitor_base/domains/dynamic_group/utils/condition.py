# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownVariableType=false

"""
动态分组条件转换工具

提供前端条件到 CMDB 查询条件的转换功能：
- 操作符映射转换
- 字段类型转换
- 条件结构构建
"""

import logging
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class ConditionConverter:
    """
    条件转换器

    将前端传入的动态分组条件转换为 CMDB API 需要的查询条件格式。

    Usage:
        >>> # 构建 CMDB 条件
        >>> condition = ConditionConverter.build_cmdb_condition([
        ...     {"field": "bk_host_innerip", "value": "10.", "operator": "contains"}
        ... ])
        >>> # {"condition": "AND", "rules": [...]}

        >>> # 构建 search_inst API 条件
        >>> condition = ConditionConverter.build_search_inst_condition(
        ...     "bk_switch",
        ...     [{"field": "bk_inst_name", "value": "test", "operator": "equal"}]
        ... )
        >>> # {"bk_switch": [{"field": "bk_inst_name", "operator": "$eq", "value": "test"}]}
    """

    # 操作符映射：前端 -> CMDB（用于 host_property_filter / biz_property_filter）
    OPERATOR_MAP: ClassVar[dict[str, str]] = {
        "equal": "equal",
        "not_equal": "not_equal",
        "in": "in",
        "not_in": "not_in",
        "contains": "contains",
        "not_contains": "not_contains",
        "less": "less",
        "less_or_equal": "less_or_equal",
        "greater": "greater",
        "greater_or_equal": "greater_or_equal",
    }

    # CMDB search_inst API 需要的操作符映射（MongoDB 风格）
    # 用于通用模型实例查询，如 bk_switch、自定义模型等
    CMDB_SEARCH_INST_OPERATOR_MAP: ClassVar[dict[str, str]] = {
        "equal": "$eq",
        "not_equal": "$ne",
        "contains": "$regex",
        "in": "$in",
        "not_in": "$nin",
        "less": "$lt",
        "less_or_equal": "$lte",
        "greater": "$gt",
        "greater_or_equal": "$gte",
    }

    # 字段属性缓存（避免重复查询）
    _FIELD_TYPE_CACHE: dict[str, dict[str, str]] = {}

    @classmethod
    def build_cmdb_condition(cls, condition_list: list[dict[str, Any]]) -> dict[str, Any]:
        """
        构建 CMDB 查询条件结构

        :param condition_list: 前端传入的条件列表
        :return: CMDB 查询条件
        """
        if not condition_list:
            return {"condition": "AND", "rules": []}

        # 如果已经是完整结构，直接返回
        if isinstance(condition_list, dict) and "rules" in condition_list:
            return condition_list

        return {"condition": "AND", "rules": condition_list}

    @classmethod
    def convert_operators(cls, condition: dict[str, Any]) -> dict[str, Any]:
        """
        转换操作符（前端 -> CMDB）

        :param condition: 查询条件
        :return: 转换后的查询条件
        """
        if not condition.get("rules"):
            return condition

        new_rules = []
        for rule in condition["rules"]:
            new_rule = rule.copy()
            operator = rule.get("operator", "equal")
            new_rule["operator"] = cls.OPERATOR_MAP.get(operator, operator)
            new_rules.append(new_rule)

        return {"condition": condition.get("condition", "AND"), "rules": new_rules}

    @classmethod
    def convert_field_types(
        cls,
        bk_tenant_id: str,
        object_model_code: str,
        condition: dict[str, Any],
    ) -> dict[str, Any]:
        """
        根据 CMDB 字段定义转换字段类型

        使用 CMDB API search_object_attribute 查询字段定义，然后根据字段类型转换值：
        - int/long 字段：将字符串转为整数
        - float 字段：将字符串转为浮点数
        - bool 字段：将字符串转为布尔值
        - list 字段：将逗号分隔的字符串转为列表

        :param bk_tenant_id: 租户ID
        :param object_model_code: 对象模型编码
        :param condition: 查询条件
        :return: 转换后的查询条件
        """
        if not condition.get("rules"):
            return condition

        try:
            # 获取字段类型映射
            field_type_map = cls._get_field_type_map(bk_tenant_id, object_model_code)

            if not field_type_map:
                logger.debug(f"未获取到字段类型定义: object_model_code={object_model_code}")
                return condition

            # 转换字段值
            new_rules = []
            for rule in condition["rules"]:
                new_rule = rule.copy()
                field_name = rule.get("field")
                field_type = field_type_map.get(field_name)
                value = rule.get("value")

                if field_type and value is not None:
                    try:
                        new_rule["value"] = cls._convert_value_by_type(value, field_type)
                    except (ValueError, TypeError) as e:
                        # 转换失败时保持原值
                        logger.warning(
                            f"字段值转换失败: field={field_name}, type={field_type}, value={value}, error={e}"
                        )

                new_rules.append(new_rule)

            return {"condition": condition.get("condition", "AND"), "rules": new_rules}

        except Exception as e:
            # 字段类型转换失败不影响查询，返回原条件
            logger.warning(
                f"字段类型转换失败: bk_tenant_id={bk_tenant_id}, object_model_code={object_model_code}, error={e}"
            )
            return condition

    @classmethod
    def _get_field_type_map(cls, bk_tenant_id: str, object_model_code: str) -> dict[str, str]:
        """
        获取对象模型的字段类型映射

        使用缓存机制避免重复查询 CMDB API

        :param bk_tenant_id: 租户ID
        :param object_model_code: 对象模型编码
        :return: 字段名到字段类型的映射
        """
        cache_key = f"{bk_tenant_id}:{object_model_code}"

        # 检查缓存
        if cache_key in cls._FIELD_TYPE_CACHE:
            return cls._FIELD_TYPE_CACHE[cache_key]

        try:
            from bk_monitor_base.infras.third_party_api import cmdb

            # 调用 CMDB API 查询对象属性
            attributes = cmdb.search_object_attribute(
                bk_tenant_id=bk_tenant_id,
                bk_obj_id=object_model_code,
            )

            # 构建字段类型映射
            field_type_map = {}
            for attr in attributes:
                field_id = attr.get("bk_property_id")
                field_type = attr.get("bk_property_type")
                if field_id and field_type:
                    field_type_map[field_id] = field_type

            # 缓存结果
            cls._FIELD_TYPE_CACHE[cache_key] = field_type_map

            logger.debug(
                f"获取字段类型映射成功: object_model_code={object_model_code}, field_count={len(field_type_map)}"
            )

            return field_type_map

        except Exception as e:
            logger.warning(
                f"查询对象属性失败: bk_tenant_id={bk_tenant_id}, object_model_code={object_model_code}, error={e}"
            )
            return {}

    @classmethod
    def _convert_value_by_type(cls, value: Any, field_type: str) -> Any:
        """
        根据字段类型转换值

        :param value: 原始值
        :param field_type: 字段类型（int/long/float/bool/list等）
        :return: 转换后的值
        """
        # 如果值已经是正确类型，直接返回
        if field_type in ("int", "long"):
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                return int(value)
            if isinstance(value, list):
                return [int(v) if isinstance(v, str) else v for v in value]

        elif field_type == "float":
            if isinstance(value, float):
                return value
            if isinstance(value, str):
                return float(value)
            if isinstance(value, list):
                return [float(v) if isinstance(v, str) else v for v in value]

        elif field_type == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes", "on")
            if isinstance(value, int):
                return bool(value)

        elif field_type == "list":
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                # 将逗号分隔的字符串转为列表
                return [v.strip() for v in value.split(",") if v.strip()]

        # 其他类型或无法转换时返回原值
        return value

    @classmethod
    def clear_field_type_cache(cls) -> None:
        """
        清空字段类型缓存

        在需要刷新字段定义时调用（如对象模型更新后）
        """
        cls._FIELD_TYPE_CACHE.clear()
        logger.info("字段类型缓存已清空")

    @classmethod
    def build_search_inst_condition(
        cls,
        bk_obj_id: str,
        condition_list: list[dict[str, Any]],
        inst_id_list: list[int] | None = None,
    ) -> dict[str, Any]:
        """
        构建 search_inst API 的条件格式

        将前端格式转换为 CMDB search_inst API 需要的格式：
        {bk_obj_id: [{"field": ..., "operator": "$eq", "value": ...}]}

        根据 CMDB API 文档 (search_inst.md)，condition 参数格式为：
        {
            "user": [  // 以关联模型名为 key
                {"field": "operator", "operator": "$regex", "value": "admin"}
            ]
        }

        Args:
            bk_obj_id: 对象模型ID (如 "bk_switch")
            condition_list: 前端条件列表，格式如:
                [{"field": "bk_inst_name", "value": "test", "operator": "equal"}]
            inst_id_list: 可选的实例ID列表（用于业务范围筛选等场景）

        Returns:
            search_inst API 格式的条件，格式如:
                {bk_obj_id: [{"field": "bk_inst_name", "operator": "$eq", "value": "test"}]}

        Example:
            >>> # 基本查询
            >>> result = ConditionConverter.build_search_inst_condition(
            ...     "bk_switch",
            ...     [{"field": "bk_inst_name", "value": "test", "operator": "equal"}]
            ... )
            >>> # {"bk_switch": [{"field": "bk_inst_name", "operator": "$eq", "value": "test"}]}

            >>> # 带业务范围筛选
            >>> result = ConditionConverter.build_search_inst_condition(
            ...     "bk_switch",
            ...     [{"field": "status", "value": "1", "operator": "equal"}],
            ...     inst_id_list=[1, 2, 3]
            ... )
            >>> # {"bk_switch": [
            >>> #     {"field": "status", "operator": "$eq", "value": "1"},
            >>> #     {"field": "bk_inst_id", "operator": "$in", "value": [1, 2, 3]}
            >>> # ]}
        """
        # 构建条件列表
        rules = []

        # 1. 转换前端条件为 CMDB 格式
        for rule in condition_list:
            operator = rule.get("operator", "equal")
            cmdb_operator = cls.CMDB_SEARCH_INST_OPERATOR_MAP.get(operator, operator)

            rules.append(
                {
                    "field": rule["field"],
                    "operator": cmdb_operator,
                    "value": rule["value"],
                }
            )

        # 2. 追加业务范围筛选条件（如果有）
        if inst_id_list:
            rules.append(
                {
                    "field": "bk_inst_id",
                    "operator": "$in",
                    "value": inst_id_list,
                }
            )

        return {bk_obj_id: rules}

    @classmethod
    def build_for_dynamic_group(
        cls,
        condition_list: list[dict[str, Any]],
        object_model_code: str | None = None,
        bk_tenant_id: str = "system",
    ) -> dict[str, Any]:
        """
        将动态分组的条件列表转换为 CMDB API 的查询条件格式

        此方法整合了条件构建和字段类型转换：
        1. 构建基础条件结构
        2. 如果提供了对象模型编码，进行字段类型转换

        注意：操作符转换已移到 GenericInstMemberFetcher 中处理，
        因为 search_inst API 需要 MongoDB 风格操作符，而 host/biz API 不需要

        Args:
            condition_list: 动态分组的条件列表，格式如:
                [{"field": "bk_host_innerip", "value": "10.", "operator": "contains"}]
            object_model_code: 对象模型编码（用于字段类型转换）
            bk_tenant_id: 租户ID（用于字段类型转换）

        Returns:
            CMDB API 的查询条件格式
        """
        if not condition_list:
            return {"condition": "AND", "rules": []}

        # 1. 构建基础条件结构
        cmdb_condition = cls.build_cmdb_condition(condition_list)

        # 2. 字段类型转换（如果提供了对象模型编码）
        if object_model_code and bk_tenant_id:
            try:
                cmdb_condition = cls.convert_field_types(
                    bk_tenant_id=bk_tenant_id,
                    object_model_code=object_model_code,
                    condition=cmdb_condition,
                )
            except Exception as e:
                # 字段类型转换失败不影响查询
                logger.warning(f"字段类型转换失败: object_model_code={object_model_code}, error={e}")

        return cmdb_condition

    @classmethod
    def build_cmdb_instance_dsl(
        cls,
        bk_tenant_id: str,
        bk_obj_id: str,
        condition_list: list[dict[str, Any]],
        bk_biz_id: int | None = None,
    ) -> dict[str, Any]:
        """将动态分组条件转换为 CMDBInstance DSL。"""
        from bk_monitor_base.domains.cmdb_instance.models import CMDBInstance

        converted_condition = cls.build_for_dynamic_group(
            condition_list=condition_list,
            object_model_code=bk_obj_id,
            bk_tenant_id=bk_tenant_id,
        )

        must: list[dict[str, Any]] = [
            {"term": {CMDBInstance.get_query_field("bk_tenant_id"): bk_tenant_id}},
            {"term": {CMDBInstance.get_query_field("bk_obj_id"): bk_obj_id}},
        ]
        must_not: list[dict[str, Any]] = []

        if bk_biz_id:
            must.append({"term": {CMDBInstance.get_query_field("bk_biz_id"): str(bk_biz_id)}})

        for rule in converted_condition.get("rules", []):
            field = rule.get("field")
            if not field:
                continue

            value = rule.get("value")
            operator = rule.get("operator", "equal")
            query_field = CMDBInstance.get_query_field(field)

            if operator == "equal":
                must.append({"term": {query_field: value}})
            elif operator == "not_equal":
                must_not.append({"term": {query_field: value}})
            elif operator == "in":
                must.append({"terms": {query_field: value if isinstance(value, list) else [value]}})
            elif operator == "not_in":
                must_not.append({"terms": {query_field: value if isinstance(value, list) else [value]}})
            elif operator == "contains":
                must.append({"wildcard": {query_field: f"*{value}*"}})
            elif operator == "not_contains":
                must_not.append({"wildcard": {query_field: f"*{value}*"}})
            elif operator in {"less", "less_or_equal", "greater", "greater_or_equal"}:
                range_operator_map = {
                    "less": "lt",
                    "less_or_equal": "lte",
                    "greater": "gt",
                    "greater_or_equal": "gte",
                }
                must.append({"range": {query_field: {range_operator_map[operator]: value}}})
            else:
                logger.warning("unsupported dynamic group operator for cmdb instance: %s", operator)

        return {"bool": {"must": must, "must_not": must_not}}
