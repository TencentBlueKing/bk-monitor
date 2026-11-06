# pyright: reportArgumentType=false
# pyright: reportOperatorIssue=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnknownVariableType=false
# pyright: reportImplicitStringConcatenation=false
# pyright: reportUntypedFunctionDecorator=false
# pyright: reportImplicitOverride=false

"""
动态分组成员获取器

使用策略模式处理不同对象模型类型的成员数据获取逻辑
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from typing_extensions import override

from bk_monitor_base.domains.cmdb_instance import search_all_instances_by_dsl, search_instances_by_dsl
from bk_monitor_base.domains.object_model.constants import BuiltinObjectModelCode
from bk_monitor_base.infras.third_party_api import cmdb
from bk_monitor_base.object_model import list_object_models

logger = logging.getLogger(__name__)


class MemberFetcher(ABC):
    """成员获取器抽象基类"""

    @staticmethod
    def _build_page_number(page: cmdb.PageParams) -> tuple[int, int]:
        limit = int(page.get("limit", 20))
        start = int(page.get("start", 0))
        if limit <= 0:
            return 1, 20
        return start // limit + 1, limit

    @abstractmethod
    def fetch(
        self,
        bk_tenant_id: str,
        bk_biz_id: int,
        condition: dict[str, Any],
        page: cmdb.PageParams,
        fields: list[str] | None = None,
    ) -> tuple[int, list[dict[str, Any]]]:
        """
        获取成员列表

        Args:
            bk_tenant_id: 租户ID
            bk_biz_id: 业务ID
            condition: CMDB 查询条件
            page: 分页参数
            fields: 返回字段列表，如果为 None 则返回所有字段

        Returns:
            (总数量, 成员列表)
        """
        pass

    @abstractmethod
    def fetch_all(
        self,
        bk_tenant_id: str,
        bk_biz_id: int,
        condition: dict[str, Any],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取全部成员列表（自动翻页）

        Args:
            bk_tenant_id: 租户ID
            bk_biz_id: 业务ID
            condition: CMDB 查询条件
            fields: 返回字段列表，如果为 None 则返回所有字段

        Returns:
            成员列表（全部数据）
        """
        pass


class HostMemberFetcher(MemberFetcher):
    """主机成员获取器"""

    # 主机查询必需的字段
    REQUIRED_FIELDS: ClassVar[list[str]] = ["bk_host_id", "bk_agent_id", "bk_host_innerip", "bk_cloud_id"]

    @staticmethod
    def _build_host_member(host: dict[str, Any]) -> dict[str, Any]:
        host_id = host.get("bk_host_id") or host.get("bk_inst_id")
        return {
            **host,
            "bk_inst_id": host_id,
            "ip_list": [
                {
                    "ip": host.get("bk_host_innerip", ""),
                    "bk_biz_id": host.get("bk_biz_id", 0),
                    "bk_host_id": host_id,
                    "bk_inst_id": host_id,
                    "bk_cloud_id": host.get("bk_cloud_id", 0),
                    "bk_host_innerip": host.get("bk_host_innerip", ""),
                    "bk_agent_id": host.get("bk_agent_id", ""),
                    "error": bool(host.get("error", True)),
                }
            ],
        }

    @override
    def fetch(
        self,
        bk_tenant_id: str,
        bk_biz_id: int,
        condition: dict[str, Any],
        page: cmdb.PageParams,
        fields: list[str] | None = None,
    ) -> tuple[int, list[dict[str, Any]]]:
        """
        获取主机列表

        从 CMDBInstance 索引中分页查询主机实例。

        Args:
            bk_tenant_id: 租户ID
            bk_biz_id: 业务ID
            condition: CMDB 查询条件
            page: 分页参数
            fields: 返回字段列表，会自动追加必需字段和条件中的字段
        """
        from bk_monitor_base.domains.dynamic_group.utils.condition import ConditionConverter

        query_fields = self._build_query_fields(fields, condition)
        page_no, page_size = self._build_page_number(page)
        dsl = ConditionConverter.build_cmdb_instance_dsl(
            bk_tenant_id=bk_tenant_id,
            bk_obj_id="host",
            condition_list=condition.get("rules", []),
            bk_biz_id=bk_biz_id,
        )
        count, host_list = search_instances_by_dsl(
            dsl=dsl,
            page=page_no,
            size=page_size,
            fields=query_fields,
        )
        return count, [self._build_host_member(host) for host in host_list]

    @override
    def fetch_all(
        self,
        bk_tenant_id: str,
        bk_biz_id: int,
        condition: dict[str, Any],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取所有主机成员（自动翻页）

        从 CMDBInstance 索引中查询所有主机实例。

        Args:
            bk_tenant_id: 租户ID
            bk_biz_id: 业务ID
            condition: CMDB 查询条件
            fields: 返回字段列表，会自动追加必需字段和条件中的字段

        Returns:
            成员列表（全部数据）
        """
        from bk_monitor_base.domains.dynamic_group.utils.condition import ConditionConverter

        query_fields = self._build_query_fields(fields, condition)
        dsl = ConditionConverter.build_cmdb_instance_dsl(
            bk_tenant_id=bk_tenant_id,
            bk_obj_id="host",
            condition_list=condition.get("rules", []),
            bk_biz_id=bk_biz_id,
        )
        host_list = search_all_instances_by_dsl(
            dsl=dsl,
            fields=query_fields,
        )
        return [self._build_host_member(host) for host in host_list]

    def _build_query_fields(
        self,
        fields: list[str] | None,
        condition: dict[str, Any],
    ) -> list[str] | None:
        """
        构建查询字段列表

        Args:
            fields: 用户指定的字段列表
            condition: 查询条件，需要提取条件中的字段

        Returns:
            合并后的字段列表，如果 fields 为 None 则返回 None（查询所有字段）
        """
        if fields is None:
            return None

        # 使用集合去重
        query_fields = set(fields)

        # 追加必需字段
        query_fields.update(self.REQUIRED_FIELDS)

        # 追加条件中的字段
        rules = condition.get("rules", [])
        for rule in rules:
            if "field" in rule:
                query_fields.add(rule["field"])

        return list(query_fields)


class BizMemberFetcher(MemberFetcher):
    """业务成员获取器"""

    # 业务查询必需的字段
    REQUIRED_FIELDS: ClassVar[list[str]] = ["bk_biz_id", "bk_biz_name"]

    @override
    def fetch(
        self,
        bk_tenant_id: str,
        bk_biz_id: int,
        condition: dict[str, Any],
        page: cmdb.PageParams | None,
        fields: list[str] | None = None,
    ) -> tuple[int, list[dict[str, Any]]]:
        """
        获取业务列表

        从 CMDBInstance 索引中分页查询业务实例。

        Args:
            bk_tenant_id: 租户ID
            bk_biz_id: 业务ID（业务查询中不使用）
            condition: CMDB 查询条件
            page: 分页参数
            fields: 返回字段列表，会自动追加必需字段
        """
        from bk_monitor_base.domains.dynamic_group.utils.condition import ConditionConverter

        query_fields = self._build_query_fields(fields)
        page_no, page_size = self._build_page_number(page or {"start": 0, "limit": 20})
        dsl = ConditionConverter.build_cmdb_instance_dsl(
            bk_tenant_id=bk_tenant_id,
            bk_obj_id="biz",
            condition_list=condition.get("rules", []),
        )
        return search_instances_by_dsl(
            dsl=dsl,
            page=page_no,
            size=page_size,
            fields=query_fields,
        )

    @override
    def fetch_all(
        self,
        bk_tenant_id: str,
        bk_biz_id: int,
        condition: dict[str, Any],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取所有业务成员（循环分页）

        从 CMDBInstance 索引中查询全部业务实例。

        Args:
            bk_tenant_id: 租户ID
            bk_biz_id: 业务ID（业务查询中不使用）
            condition: CMDB 查询条件
            fields: 返回字段列表，会自动追加必需字段

        Returns:
            成员列表（全部数据）
        """
        from bk_monitor_base.domains.dynamic_group.utils.condition import ConditionConverter

        query_fields = self._build_query_fields(fields)
        dsl = ConditionConverter.build_cmdb_instance_dsl(
            bk_tenant_id=bk_tenant_id,
            bk_obj_id="biz",
            condition_list=condition.get("rules", []),
        )
        return search_all_instances_by_dsl(
            dsl=dsl,
            fields=query_fields,
        )

    def _build_query_fields(self, fields: list[str] | None) -> list[str] | None:
        """
        构建查询字段列表

        Args:
            fields: 用户指定的字段列表

        Returns:
            合并后的字段列表，如果 fields 为 None 则返回 None（查询所有字段）
        """
        if fields is None:
            return None

        query_fields = set(fields)
        query_fields.update(self.REQUIRED_FIELDS)
        return list(query_fields)


class GenericInstMemberFetcher(MemberFetcher):
    """通用实例成员获取器"""

    # 通用实例查询必需的字段
    REQUIRED_FIELDS: ClassVar[list[str]] = ["bk_inst_id", "bk_inst_name"]

    def __init__(self, bk_obj_id: str, host_related_field: str = ""):
        """
        Args:
            bk_obj_id: CMDB 对象ID
            host_related_field: 主机关联字段名，用于查询实例关联的主机列表
        """
        self.bk_obj_id: str = bk_obj_id
        self.host_related_field: str = host_related_field

    @override
    def fetch(
        self,
        bk_tenant_id: str,
        bk_biz_id: int,
        condition: dict[str, Any],
        page: cmdb.PageParams,
        fields: list[str] | None = None,
    ) -> tuple[int, list[dict[str, Any]]]:
        """
        获取通用实例列表

        从 CMDBInstance 索引中分页查询通用实例，并补充关联主机列表。

        Args:
            bk_tenant_id: 租户ID
            bk_biz_id: 业务ID
            condition: CMDB 查询条件
            page: 分页参数
            fields: 返回字段列表，会自动追加必需字段
        """
        from bk_monitor_base.domains.dynamic_group.utils.condition import ConditionConverter
        from bk_monitor_base.domains.dynamic_group.utils.enricher import HostRelationEnricher

        query_fields = self._build_query_fields(fields)
        page_no, page_size = self._build_page_number(page)
        dsl = ConditionConverter.build_cmdb_instance_dsl(
            bk_tenant_id=bk_tenant_id,
            bk_obj_id=self.bk_obj_id,
            condition_list=condition.get("rules", []),
            bk_biz_id=bk_biz_id,
        )
        count, result_list = search_instances_by_dsl(
            dsl=dsl,
            page=page_no,
            size=page_size,
            fields=list(query_fields[self.bk_obj_id]) if query_fields else None,
        )

        # 使用 HostRelationEnricher 为实例添加关联的主机信息 (ip_list)
        if self.host_related_field:
            enricher = HostRelationEnricher(
                bk_tenant_id=bk_tenant_id,
                bk_obj_id=self.bk_obj_id,
                host_related_field=self.host_related_field,
            )
            result_list = enricher.enrich(result_list, bk_biz_id=bk_biz_id)
        else:
            # 没有配置关联字段，所有实例的 ip_list 都为空
            result_list = [{**inst, "ip_list": []} for inst in result_list]

        return count, result_list

    @override
    def fetch_all(
        self,
        bk_tenant_id: str,
        bk_biz_id: int,
        condition: dict[str, Any],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取所有通用实例成员（自动翻页）

        从 CMDBInstance 索引中查询全部通用实例，并补充关联主机列表。

        Args:
            bk_tenant_id: 租户ID
            bk_biz_id: 业务ID
            condition: CMDB 查询条件
            fields: 返回字段列表，会自动追加必需字段

        Returns:
            成员列表（全部数据）
        """
        from bk_monitor_base.domains.dynamic_group.utils.condition import ConditionConverter
        from bk_monitor_base.domains.dynamic_group.utils.enricher import HostRelationEnricher

        query_fields = self._build_query_fields(fields)
        dsl = ConditionConverter.build_cmdb_instance_dsl(
            bk_tenant_id=bk_tenant_id,
            bk_obj_id=self.bk_obj_id,
            condition_list=condition.get("rules", []),
            bk_biz_id=bk_biz_id,
        )
        result_list = search_all_instances_by_dsl(
            dsl=dsl,
            fields=list(query_fields[self.bk_obj_id]) if query_fields else None,
        )

        # 使用 HostRelationEnricher 为实例添加关联的主机信息 (ip_list)
        if self.host_related_field:
            enricher = HostRelationEnricher(
                bk_tenant_id=bk_tenant_id,
                bk_obj_id=self.bk_obj_id,
                host_related_field=self.host_related_field,
            )
            result_list = enricher.enrich(result_list, bk_biz_id=bk_biz_id)
        else:
            # 没有配置关联字段，所有实例的 ip_list 都为空
            result_list = [{**inst, "ip_list": []} for inst in result_list]

        return result_list

    def _build_query_fields(self, fields: list[str] | None) -> dict[str, list[str]] | None:
        """
        构建查询字段列表

        统一返回 {bk_obj_id: [field1, field2, ...]} 结构，便于调用方复用。

        Args:
            fields: 用户指定的字段列表

        Returns:
            CMDB search_inst API 需要的 fields 格式，如果 fields 为 None 则返回 None
        """
        if fields is None:
            # 返回默认的必需字段
            return {self.bk_obj_id: list(self.REQUIRED_FIELDS)}

        query_fields = set(fields)
        query_fields.update(self.REQUIRED_FIELDS)
        return {self.bk_obj_id: list(query_fields)}


class MemberFetcherRegistry:
    """成员获取器注册表"""

    def __init__(self):
        self._fetchers: dict[str, MemberFetcher] = {}

    def register(self, object_model_code: str, fetcher: MemberFetcher) -> None:
        """
        注册成员获取器

        Args:
            object_model_code: 对象模型代码
            fetcher: 成员获取器实例
        """
        self._fetchers[object_model_code] = fetcher

    def get(self, object_model_code: str) -> MemberFetcher | None:
        """
        获取成员获取器

        Args:
            object_model_code: 对象模型代码

        Returns:
            成员获取器实例，如果未注册则返回 None
        """
        return self._fetchers.get(object_model_code)

    def get_or_create_generic(self, object_model_code: str) -> MemberFetcher:
        """
        获取成员获取器，如果未注册则创建通用实例获取器

        Args:
            object_model_code: 对象模型代码

        Returns:
            成员获取器实例

        Raises:
            ValueError: 当 object_model_code 不存在时
        """
        fetcher = self.get(object_model_code)
        if fetcher is None:
            # 通过 list_object_models 获取真实的 bk_cmdb_obj_id 和 host_related_field
            try:
                object_models = list_object_models(object_model_codes=[object_model_code], raise_not_found=True)
                if not object_models:
                    raise ValueError(f"对象模型不存在: {object_model_code}")

                object_model = object_models[0]
                bk_obj_id = object_model.bk_cmdb_obj_id
                # 获取主机关联字段，用于查询实例关联的主机列表
                host_related_field = getattr(object_model, "host_related_field", "") or ""

                logger.info(
                    f"为对象模型创建通用成员获取器: object_model_code={object_model_code}, "
                    f"bk_cmdb_obj_id={bk_obj_id}, host_related_field={host_related_field}"
                )
            except Exception as e:
                logger.error(f"获取对象模型失败: object_model_code={object_model_code}, error={e}")
                raise ValueError(f"无法获取对象模型 {object_model_code} 的 bk_cmdb_obj_id: {e}")

            fetcher = GenericInstMemberFetcher(bk_obj_id, host_related_field)
            # 动态注册
            self.register(object_model_code, fetcher)
        return fetcher


# 创建全局注册表并注册内置类型
_registry = MemberFetcherRegistry()
_registry.register(BuiltinObjectModelCode.HOST, HostMemberFetcher())
_registry.register(BuiltinObjectModelCode.BIZ, BizMemberFetcher())


def get_member_fetcher(object_model_code: str) -> MemberFetcher:
    """
    获取成员获取器

    Args:
        object_model_code: 对象模型代码

    Returns:
        成员获取器实例

    Raises:
        ValueError: 当 object_model_code 不存在时
    """
    return _registry.get_or_create_generic(object_model_code)


def register_member_fetcher(object_model_code: str, fetcher: MemberFetcher) -> None:
    """
    注册自定义成员获取器

    Args:
        object_model_code: 对象模型代码
        fetcher: 成员获取器实例

    Example:
        >>> class CustomFetcher(MemberFetcher):
        ...     def fetch(self, ...):
        ...         # 自定义实现
        ...         pass
        >>> register_member_fetcher("cw-CustomObject", CustomFetcher())
    """
    _registry.register(object_model_code, fetcher)
