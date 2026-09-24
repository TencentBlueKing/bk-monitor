"""
动态分组成员比对工具

提供成员列表比对功能：
- 比较新旧成员列表，返回需要添加和删除的成员ID列表
- 检测 ip_list 变更
"""

import copy
import logging
from typing import Any

logger = logging.getLogger(__name__)


class MemberComparator:
    """
    成员比对器

    比较动态分组的新旧成员列表，识别需要添加、删除的成员，
    以及检测 ip_list 的变化。

    Usage:
        >>> # 比较成员列表
        >>> add_list, delete_list, first_related = MemberComparator.compare(
        ...     object_model_code="cw-Host",
        ...     new_members=[{"bk_inst_id": 1, "ip_list": [...]}, ...],
        ...     old_members=[{"bk_inst_id": 2, "ip_list": [...]}, ...]
        ... )

        >>> # 获取 ip_list 变更的成员
        >>> update_members, need_push_kafka = MemberComparator.get_updated_members(
        ...     old_members=[...],
        ...     new_members=[...]
        ... )
    """

    @classmethod
    def compare(
        cls,
        object_model_code: str,
        new_members: list[dict[str, Any]],
        old_members: list[dict[str, Any]],
    ) -> tuple[list[int], list[int], bool]:
        """
        比较新旧成员列表，返回需要添加和删除的成员ID列表

        该方法仅用于判断动态分组中的实例是否发生变更。

        Args:
            object_model_code: 对象模型代码
            new_members: 新成员列表，格式 [{"bk_inst_id": 1, "ip_list": [...]}, ...]
            old_members: 旧成员列表，格式同上

        Returns:
            tuple: (add_list, delete_list, first_related)
                - add_list: 需要添加的成员 bk_inst_id 列表
                - delete_list: 需要删除的成员 bk_inst_id 列表
                - first_related: 是否存在首次关联（某实例的 ip_list 从空变为非空）
        """
        from bk_monitor_base.domains.object_model.constants import BuiltinObjectModelCode

        add_list: list[int] = []
        delete_list: list[int] = []
        first_related = False

        if object_model_code == BuiltinObjectModelCode.HOST:
            # 主机类型：只比较 bk_inst_id
            old_inst_ids = {m["bk_inst_id"] for m in old_members}
            new_inst_ids = {m["bk_inst_id"] for m in new_members}
            delete_list = list(old_inst_ids - new_inst_ids)
            add_list = list(new_inst_ids - old_inst_ids)
        else:
            # 非主机类型：需要考虑 ip_list 的变化
            old_inst_ids = {m["bk_inst_id"] for m in old_members}
            new_inst_ids = {m["bk_inst_id"] for m in new_members}

            if old_inst_ids == new_inst_ids:
                # 成员ID列表相同，检查是否有 ip_list 变化
                old_map = {m["bk_inst_id"]: m for m in old_members}
                new_map = {m["bk_inst_id"]: m for m in new_members}
                if old_map != new_map:
                    # ip_list 变化了
                    first_related = True
            else:
                # 成员ID列表不同
                delete_list = list(old_inst_ids - new_inst_ids)
                add_list = list(new_inst_ids - old_inst_ids)

                # 检查是否有首次关联（原有实例的 ip_list 从空变为非空）
                old_map = {m["bk_inst_id"]: m.get("ip_list", []) for m in old_members}
                new_map = {m["bk_inst_id"]: m.get("ip_list", []) for m in new_members}
                for inst_id in old_inst_ids & new_inst_ids:
                    if not old_map.get(inst_id) and new_map.get(inst_id):
                        first_related = True
                        break

        return add_list, delete_list, first_related

    @classmethod
    def get_updated_members(
        cls,
        old_members: list[dict[str, Any]],
        new_members: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], bool]:
        """
        获取成员 ip_list 变更了的实例

        用于检测成员ID没有变化但 ip_list 发生变化的情况。
        比较时会忽略 ip_list 中每个 IP 的 error 字段。

        Args:
            old_members: 旧成员列表，格式 [{"bk_inst_id": 1, "ip_list": [...]}, ...]
            new_members: 新成员列表，格式同上

        Returns:
            tuple: (update_members, need_push_kafka)
                - update_members: ip_list 变更的成员列表（完整的新成员数据）
                - need_push_kafka: 是否需要推送 Kafka（忽略 error 字段后仍有变化）
        """
        old_inst_id_dict: dict[int, dict[str, Any]] = {}
        new_inst_id_dict: dict[int, dict[str, Any]] = {}
        update_members: list[dict[str, Any]] = []
        need_push_kafka = False

        # 构建旧成员映射
        for old_member in old_members:
            old_inst_id_dict[old_member["bk_inst_id"]] = old_member

        # 构建新成员映射
        for new_member in new_members:
            new_inst_id_dict[new_member["bk_inst_id"]] = new_member

        # 比较相同 bk_inst_id 的成员
        for old_inst_id, old_member in old_inst_id_dict.items():
            if old_inst_id in new_inst_id_dict:
                new_member = new_inst_id_dict[old_inst_id]
                # 如果完全相同则跳过
                if old_member == new_member:
                    continue
                # 有变化，记录到更新列表
                update_members.append(new_member)
                # 忽略 error 字段后再比较，判断是否需要推送 Kafka
                tmp_old_member = cls._strip_error_from_member(old_member)
                tmp_new_member = cls._strip_error_from_member(new_member)
                if tmp_old_member != tmp_new_member:
                    need_push_kafka = True

        return update_members, need_push_kafka

    @classmethod
    def _strip_error_from_member(cls, member: dict[str, Any]) -> dict[str, Any]:
        """
        移除 ip_list 中每个 IP 的 error 字段

        Args:
            member: 成员数据

        Returns:
            移除 error 字段后的成员数据副本
        """
        result = copy.deepcopy(member)
        for ip_info in result.get("ip_list", []):
            ip_info.pop("error", None)
        return result

    @classmethod
    def filter_by_condition(
        cls,
        data: list[dict[str, Any]],
        search_condition: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        根据搜索条件在客户端过滤数据

        Args:
            data: 数据列表
            search_condition: 搜索条件列表

        Returns:
            过滤后的数据列表
        """
        from bk_monitor_base.domains.dynamic_group.constants import DynamicGroupOperator

        if not search_condition:
            return data

        filtered_data: list[dict[str, Any]] = []
        for item in data:
            match = True
            for condition in search_condition:
                field: str | None = condition.get("field")
                value: Any = condition.get("value")
                operator: str = condition.get("operator", DynamicGroupOperator.EQUAL)

                if field is None:
                    continue

                item_value: Any = item.get(field)

                # 根据操作符进行匹配
                if operator == DynamicGroupOperator.EQUAL:
                    if item_value != value:
                        match = False
                        break
                elif operator == DynamicGroupOperator.NOT_EQUAL:
                    if item_value == value:
                        match = False
                        break
                elif operator == DynamicGroupOperator.CONTAINS:
                    if value is not None and str(value) not in str(item_value):
                        match = False
                        break
                elif operator == DynamicGroupOperator.NOT_CONTAINS:
                    if value is not None and str(value) in str(item_value):
                        match = False
                        break
                elif operator == DynamicGroupOperator.IN:
                    if isinstance(value, list | tuple | set) and item_value not in value:
                        match = False
                        break
                elif operator == DynamicGroupOperator.NOT_IN:
                    if isinstance(value, list | tuple | set) and item_value in value:
                        match = False
                        break

            if match:
                filtered_data.append(item)

        return filtered_data
