# pyright: reportArgumentType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false

"""
成员数据格式化模块

提供动态分组成员数据的格式化功能：
- 翻译枚举值
- 格式化实例展示名称（bk_inst_display_name）
"""

import logging
import re
from typing import Any

from bk_monitor_base.infras.third_party_api import cmdb
from bk_monitor_base.object_model import list_object_models

logger = logging.getLogger(__name__)


class MemberFormatter:
    """
    成员数据格式化器

    用于在动态分组预览时格式化成员数据，包括：
    1. 翻译枚举字段的值为可读名称
    2. 根据 inst_display_name 表达式生成 bk_inst_display_name 字段

    Example:
        >>> members = [{"bk_host_innerip": "10.0.0.1", "status": "1"}]
        >>> formatted = MemberFormatter.format_members(members, "cw-Host", "default")
        >>> # members 中的枚举字段会被翻译，且添加 bk_inst_display_name 字段
    """

    _CLOUD_AREA_CACHE: dict[str, dict[str, str]] = {}

    @classmethod
    def format_members(
        cls,
        members: list[dict[str, Any]],
        object_model_code: str,
        bk_tenant_id: str = "default",
    ) -> list[dict[str, Any]]:
        """
        格式化成员列表

        处理流程：
        1. 获取对象模型信息（display_fields, inst_display_name, bk_cmdb_obj_id）
        2. 获取枚举字段翻译映射
        3. 翻译枚举值 + 生成实例展示名称

        Args:
            members: 原始成员列表
            object_model_code: 对象模型代码
            bk_tenant_id: 租户ID

        Returns:
            格式化后的成员列表
        """
        if not members:
            return members

        # 获取对象模型信息
        try:
            obj_models = list_object_models(
                object_model_codes=[object_model_code],
                raise_not_found=True,
            )
            obj_model = obj_models[0]
        except Exception as e:
            logger.warning(f"获取对象模型失败: {object_model_code}, 跳过格式化: {e}")
            return members

        # 获取展示字段列表
        display_fields = [
            f["bk_property_id"] for f in obj_model.display_fields if f["bk_property_id"] != "bk_inst_display_name"
        ]

        # 获取枚举字段翻译
        enum_translations = cls._get_enum_translations(
            bk_obj_id=obj_model.bk_cmdb_obj_id,
            bk_tenant_id=bk_tenant_id,
        )
        cloud_area_translations = cls._get_cloud_area_translations(bk_tenant_id=bk_tenant_id)

        # 格式化展示名称（包含枚举翻译）
        members = cls._format_display_name(
            inst_list=members,
            expression=obj_model.inst_display_name or "",
            display_fields=display_fields,
            enum_translations=enum_translations,
            cloud_area_translations=cloud_area_translations,
        )

        return members

    @classmethod
    def _format_display_name(
        cls,
        inst_list: list[dict[str, Any]],
        expression: str,
        display_fields: list[str],
        enum_translations: dict[str, dict[str, str]],
        cloud_area_translations: dict[str, str],
    ) -> list[dict[str, Any]]:
        """
        格式化实例展示名称

        对每个实例：
        1. 翻译枚举字段值
        2. 根据表达式生成 bk_inst_display_name

        Args:
            inst_list: 实例列表
            expression: 展示名称表达式，如 "${bk_host_innerip}"
            display_fields: 展示字段列表
            enum_translations: 枚举值翻译映射 {property_id: {enum_id: enum_name}}

        Returns:
            添加了 bk_inst_display_name 字段的实例列表
        """
        # 提取表达式中的字段 ${field}
        fields_in_expression = re.findall(r"\$\{(\w+)\}", expression)

        for inst in inst_list:
            # 翻译枚举值
            for property_id, enum_map in enum_translations.items():
                inst_value = inst.get(property_id)
                if inst_value is not None and str(inst_value) in enum_map:
                    inst[property_id] = enum_map[str(inst_value)]

            if "bk_cloud_id" in inst and "bk_cloud_id" in display_fields:
                inst["bk_cloud_id"] = cls._format_cloud_area_value(
                    inst.get("bk_cloud_id"),
                    cloud_area_translations,
                )

            # 构建展示名称
            inst_display_name = expression
            for field in fields_in_expression:
                reg_str = f"${{{field}}}"
                if field not in display_fields:
                    replace_str = ""
                else:
                    field_value = inst.get(field)
                    replace_str = "" if field_value is None else str(field_value)
                inst_display_name = inst_display_name.replace(reg_str, replace_str)

            # 如果展示名称为空，使用默认值
            inst["bk_inst_display_name"] = inst_display_name if inst_display_name else "- -"

        return inst_list

    @classmethod
    def _format_cloud_area_value(
        cls,
        cloud_value: Any,
        cloud_area_translations: dict[str, str],
    ) -> str:
        """格式化云区域展示值，避免对已翻译值重复包装。"""
        cloud_id = "" if cloud_value is None else str(cloud_value)
        if cloud_id in cloud_area_translations:
            return cloud_area_translations[cloud_id]

        # 已经是“名称[id]”形式的展示值时直接保留，避免二次格式化成 --[名称[id]]
        if re.fullmatch(r".+\[\d+\]", cloud_id):
            return cloud_id

        return f"--[{cloud_id}]"

    @classmethod
    def _get_enum_translations(
        cls,
        bk_obj_id: str,
        bk_tenant_id: str,
    ) -> dict[str, dict[str, str]]:
        """
        获取枚举字段翻译映射

        调用 CMDB API search_object_attribute 获取对象属性，
        解析枚举类型字段的 option，构建翻译映射。

        Args:
            bk_obj_id: CMDB 对象 ID
            bk_tenant_id: 租户 ID

        Returns:
            枚举字段翻译映射: {property_id: {enum_id: enum_name}}
        """
        try:
            attributes = cmdb.search_object_attribute(
                bk_tenant_id=bk_tenant_id,
                bk_obj_id=bk_obj_id,
            )
        except Exception as e:
            logger.warning(f"获取对象属性失败: bk_obj_id={bk_obj_id}, error={e}")
            return {}

        result: dict[str, dict[str, str]] = {}

        for attr in attributes:
            # 只处理枚举类型
            if attr.get("bk_property_type") != "enum":
                continue

            option = attr.get("option")
            if not option or not isinstance(option, list):
                continue

            property_id = attr.get("bk_property_id")
            if not property_id:
                continue

            # 构建枚举值映射: {id: name}
            enum_map: dict[str, str] = {}
            for opt in option:
                if isinstance(opt, dict) and "id" in opt and "name" in opt:
                    enum_map[str(opt["id"])] = opt["name"]

            if enum_map:
                result[property_id] = enum_map

        return result

    @classmethod
    def _get_cloud_area_translations(cls, bk_tenant_id: str) -> dict[str, str]:
        """获取云区域展示值映射。"""
        if bk_tenant_id in cls._CLOUD_AREA_CACHE:
            return cls._CLOUD_AREA_CACHE[bk_tenant_id]

        try:
            cloud_areas = cmdb.search_cloud_area(bk_tenant_id=bk_tenant_id)
        except Exception as e:
            logger.warning(f"获取云区域失败: bk_tenant_id={bk_tenant_id}, error={e}")
            return {}

        result: dict[str, str] = {}
        for cloud_area in cloud_areas:
            cloud_id = str(cloud_area["bk_cloud_id"])
            cloud_name = cloud_area.get("bk_cloud_name") or "--"
            result[cloud_id] = f"{cloud_name}[{cloud_id}]"

        cls._CLOUD_AREA_CACHE[bk_tenant_id] = result
        return result
