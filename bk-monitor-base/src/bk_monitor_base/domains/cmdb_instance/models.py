"""CMDB 实例 Elasticsearch 模型定义。

此模块提供 CMDB 实例的 Elasticsearch 文档模型，包括：
- 基础文档类（CWDocument）：提供通用的 ES 操作能力
- 实例模型（CMDBInstance）：CMDB 实例数据存储
- 模型关联关系（CMDBObjRelate）：CMDB 模型间的关联关系
- 实例关联关系（CMDBInstRelate）：CMDB 实例间的关联关系

主要功能：
- 支持多 ES 连接配置
- 支持批量写入和删除
- 支持灵活的查询和聚合
- 自动获取最新索引

Example:
    >>> from bk_monitor_base.domains.cmdb_instance import CMDBInstance
    >>> # 查询主机实例
    >>> total, instances = CMDBInstance.get_search(
    ...     query={"bk_obj_id": "host"},
    ...     page=1,
    ...     size=10
    ... ).execute()
    >>> # 批量写入
    >>> CMDBInstance.bulk_update_or_create("host", [
    ...     {"bk_host_id": 1, "bk_host_name": "host1"}
    ... ])
"""
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportOptionalMemberAccess=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportUnknownLambdaType=false
# pyright: reportPrivateUsage=false

import logging
from datetime import date, datetime
from distutils.version import LooseVersion
from functools import reduce
from typing import Any, TypeVar, cast, final

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from elasticsearch_dsl import (  # reportUnknownVariableType
    A,
    Boolean,
    Date,
    Document,
    Integer,
    Keyword,
    MetaField,
    Q,
    Text,
)
from typing_extensions import override

from bk_monitor_base.config import get_config
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID

from .agent_status import enrich_host_instances_with_agent_status

logger = logging.getLogger(__name__)
config = get_config()
ES_KEY_PREFIX: str = config.common.es_index_prefix
REDIS_KEY_PREFIX: str = config.common.redis_key_prefix

ES_MAX_OFFSET: int = config.elasticsearch["default"].max_offset
ES_MAX_MAPPING_FIELDS: int = config.elasticsearch["default"].max_mapping_fields
ES_NUMBER_OF_SHARDS: int = config.elasticsearch["default"].number_of_shards
ES_NUMBER_OF_REPLICAS: int = config.elasticsearch["default"].number_of_replicas

T = TypeVar("T", bound="CWDocument")


class CWDocument(Document):
    """基础 Elasticsearch 文档类。

    提供通用的 ES 文档操作能力，包括连接管理、批量操作、查询构建等。
    所有 CMDB 相关的文档模型都应继承此类。

    支持的功能：
    - 多 ES 连接配置
    - 工厂方法创建不同连接的模型实例
    - 批量文档操作
    - 灵活的查询构建

    Example:
        >>> # 获取 ES 客户端
        >>> client = CWDocument.get_es_client(using="default")
        >>> # 使用工厂方法创建测试环境的模型
        >>> TestDoc = CWDocument.with_using("test_es")
        >>> instances = TestDoc.search().execute()
    """

    @final
    class Meta:
        dynamic = MetaField("true")
        dynamic_templates = MetaField(
            [
                {
                    "all_as_text": {
                        "match_mapping_type": "*",
                        "mapping": {
                            "type": "text",
                            "norms": False,
                            "fields": {"keyword": {"type": "keyword", "ignore_above": 8191}},
                        },
                    }
                }
            ]
        )

    @classmethod
    def get_es_client(cls, using: str | None = None) -> Elasticsearch:
        """获取 Elasticsearch 客户端。

        Args:
            using: ES 连接别名。如果未指定，则使用配置中的默认值

        Returns:
            Elasticsearch 客户端实例

        Example:
            >>> client = CWDocument.get_es_client()
            >>> test_client = CWDocument.get_es_client(using="test_es")
        """
        if using is None:
            using = config.elasticsearch["default"].es_using

        return cast(Elasticsearch, cls._get_connection(using=using))

    @classmethod
    def init_index(cls, using: str | None = None) -> None:
        """初始化索引（创建索引和映射），并原子地创建写别名和读别名。

        调用前应确保写别名尚不存在（由 ``apps.py`` 的 ``exists_alias`` 检查保证），
        本方法只处理全新创建的场景：

        1. 以 ``{ALIAS}-000001`` 为真实索引名创建索引。
        2. 在同一个创建请求中通过 ``aliases`` 参数原子地建立写别名和读别名。

        Args:
            using: ES 连接别名。如果未指定，则使用配置中的默认值

        Example:
            >>> CMDBInstance.init_index()
            >>> CMDBInstance.init_index(using="test_es")
        """
        if using is None:
            using = config.elasticsearch["default"].es_using

        alias = cls.Index.ALIAS
        read_alias = f"{alias}-read"
        actual_index_name = f"{alias}-000001"

        es_client = cls.get_es_client(using=using)

        # 从 Index.settings 浅拷贝，避免污染类属性
        index_settings = dict(cls.Index.settings)
        # lifecycle.rollover_alias 与手动别名管理冲突，移除
        index_settings.pop("lifecycle", None)

        # 获取 mappings
        index = cls._index.clone(name=actual_index_name)
        index.document(cls)
        mappings = index.to_dict().get("mappings", {})

        body: dict = {
            "settings": index_settings,
            "aliases": {
                alias: {"is_write_index": True},
                read_alias: {},
            },
        }
        if mappings:
            body["mappings"] = mappings

        es_client.indices.create(index=actual_index_name, body=body)
        logger.info(f"索引 {actual_index_name} 创建成功，写别名={alias}，读别名={read_alias}")

    @classmethod
    def bulk_actions(
        cls,
        documents: list[dict[str, Any]],
        es_client: Elasticsearch | None = None,
        ignore_status: list[int] | None = None,
        using: str | None = None,
    ) -> None:
        """批量执行文档操作。

        支持批量索引、更新、删除等操作，适用于大量数据的写入场景。

        Args:
            documents: 文档操作列表，每个元素包含 _op_type、_id、_source 等字段
            es_client: ES 客户端实例。如果未指定，则自动获取
            ignore_status: 忽略的 HTTP 状态码列表。默认为 [404]
            using: ES 连接别名

        Example:
            >>> documents = [
            ...     {"_op_type": "index", "_id": "1", "_source": {"field": "value"}},
            ...     {"_op_type": "delete", "_id": "2"}
            ... ]
            >>> CMDBInstance.bulk_actions(documents)
        """
        if not documents:
            return
        if es_client is None:
            es_client = cls.get_es_client(using=using)
        if ignore_status is None:
            ignore_status = [404]
        # https://elasticsearch-py.readthedocs.io/en/v8.5.3/helpers.html#bulk-helpers
        bulk(
            client=es_client,
            actions=documents,
            stats_only=True,
            chunk_size=500,
            max_chunk_bytes=100 * 1024 * 1024,
            max_retries=3,
            index=cls.Index.ALIAS,
            refresh=True,
            ignore_status=ignore_status,
            raise_on_exception=True,
            raise_on_error=True,
        )

    @classmethod
    def get_search(
        cls,
        query: dict[str, Any] | None = None,
        search: dict[str, Any] | None = None,
        page: int | None = None,
        size: int | None = None,
        sort: str | None = None,
        fields: list[str] | None = None,
        from_dsl: Any | None = None,
        using: str | None = None,
    ) -> Any:
        """构建搜索查询。

        提供灵活的查询构建能力，支持精确匹配、模糊搜索、分页、排序等功能。

        Args:
            query: 精确匹配参数。如 {"bk_obj_id": "host"} 或 {"bk_inst_id": [1, 2, 3]}
            search: 模糊匹配参数。如 {"bk_inst_name": "test"}
            page: 页码，从 1 开始
            size: 每页大小
            sort: 排序字段。如 "create_time" 或 "-create_time"（降序）
            fields: 查询返回的字段列表。如 ["field1", "field2"]
            from_dsl: DSL 查询对象。可用于构建复杂查询
            using: ES 连接别名

        Returns:
            elasticsearch_dsl.Search 对象

        Example:
            >>> # 精确查询
            >>> exact_search = CMDBInstance.get_search(query={"bk_obj_id": "host"})
            >>> # 模糊搜索
            >>> fuzzy_search = CMDBInstance.get_search(search={"bk_inst_name": "web"})
            >>> # 分页查询
            >>> paged_search = CMDBInstance.get_search(page=1, size=10, sort="-create_time")
            >>> response = paged_search.execute()
        """
        dsl = Q()

        if query:
            for k, v in query.items():
                k = cls.get_query_field(k)
                if isinstance(v, list):
                    dsl = dsl & Q("terms", **{k: v})
                else:
                    dsl = dsl & Q("term", **{k: v})
        if search:
            for k, v in search.items():
                k = cls.get_query_field(k)
                dsl = dsl & Q("wildcard", **{k: f"*{v}*"})

        s = cls.search(using=using).query(dsl)

        if from_dsl:
            s = s.query(from_dsl)

        if sort:
            s = s.sort(cls.get_query_field(sort))

        if page and size:
            page, size = int(page), int(size)
            from_ = (page - 1) * size
            s = s.extra(from_=from_, size=size)
        elif size:
            s = s[: int(size)]

        if fields:
            s = s.source(fields)

        # 设置 track_total_hits=True 以获取真实的总数，而不是限制在10000
        s = s.extra(track_total_hits=True)

        return s

    @classmethod
    def get_query_field(cls, field_name: str) -> str:
        """获取查询字段名。

        对于 Text 类型字段，自动添加 .keyword 后缀以支持精确查询和排序。

        Args:
            field_name: 字段名

        Returns:
            查询字段名，可能包含 .keyword 后缀
        """
        field = cls._doc_type.mapping.resolve_field(field_name)
        if field is None or isinstance(field, Text):
            return f"{field_name}.keyword"
        return field_name

    @classmethod  # noqa
    def get_query_instance(
        cls,
        query: dict[str, Any] | None = None,
        search: dict[str, Any] | None = None,
        exclude_search: dict[str, Any] | None = None,
        time_field: str | None = None,
        start_time: str | datetime | date | None = None,
        end_time: str | datetime | date | None = None,
        or_query: dict[str, Any] | None = None,
        exclude_query: dict[str, Any] | None = None,
        global_search: dict[str, Any] | None = None,
        sort: str | None = None,
        query_fields: list[str] | None = None,
        using: str | None = None,
        index: str | None = None,
        from_dict: dict[str, Any] | None = None,
    ) -> Any:
        """
        通过查询条件返回 Search 实例
        :param query: 精确查询, 传参示例 {alarm_field: str/list}
        :param search: 模糊查询, 传参示例 {alarm_field: str}
        :param exclude_search: 不包含，模糊查询, 传参示例 {alarm_field: str}
        :param time_field: 时间段查询, 需要时间段查询的告警时间字段
        :param start_time: str, time_field开始时间
        :param end_time: str, time_field结束时间
        :param or_query: 或查询, 传参示例 {alarm_field: str}
        :param exclude_query: 排除查询, 传参示例 {alarm_field: str/list}
        :param global_search: 多字段模糊搜索, 传参示例 {keyword: str, search_list: [alarm_field1, alarm_field2]}
        :param sort: 排序, 传参实例 alarm_field/-alarm_field(倒序)
        :param query_fields: 查询字段, 传参示例 [alarm_field1, alarm_field2]
        :param using: es_client
        :param index: es_index
        :param from_dict: dsl查询字典，search.from_dict()的入参，当有此值时会基于此查询再附加查询条件
        :return:
        """
        # 构建查询dsl
        dsl = query_dsl = search_dsl = exclude_query_dsl = global_search_dsl = Q()

        # 时间段查询
        if start_time and end_time and time_field:
            if isinstance(start_time, date | datetime):
                start_time = start_time.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(end_time, date | datetime):
                end_time = end_time.strftime("%Y-%m-%d %H:%M:%S")
            dsl = Q("range", **{time_field: {"gte": start_time, "lte": end_time}})

        # 精确查询
        if query:
            for k, v in query.items():
                if isinstance(v, list):
                    query_dsl = query_dsl & Q("terms", **{k: v})
                else:
                    query_dsl = query_dsl & Q("term", **{k: v})

        # 或查询
        if or_query:
            for k, v in or_query.items():
                if isinstance(v, list):
                    query_dsl = query_dsl | Q("terms", **{k: v})
                else:
                    query_dsl = query_dsl | Q("term", **{k: v})

        # 排除查询
        if exclude_query:
            for k, v in exclude_query.items():
                if isinstance(v, list):
                    exclude_query_dsl = exclude_query_dsl & ~Q("terms", **{k: v})
                else:
                    exclude_query_dsl = exclude_query_dsl & ~Q("match", **{k: v})

        # 模糊查询
        if search:
            for k, v in search.items():
                if not v:
                    continue
                else:
                    search_dsl = search_dsl & Q("match_phrase", **{k: v})

        # 模糊排除
        if exclude_search:
            for k, v in exclude_search.items():
                if not v:
                    continue
                else:
                    search_dsl = search_dsl & ~Q("match_phrase", **{k: v})

        # 全局查找
        if global_search and global_search.get("keyword"):
            global_search_dsl = global_search_dsl & reduce(
                lambda x, y: x | y,
                [Q("match_phrase", **{i: global_search["keyword"]}) for i in global_search["search_list"]],
            )

        dsl = dsl & query_dsl & exclude_query_dsl & search_dsl & global_search_dsl
        search = cls.build_base_search(index=index, using=using)

        # 获取查询实例
        if from_dict:
            search = search.update_from_dict(from_dict).query(dsl)
        else:
            search = search.query(dsl)

        # 排序
        if sort:
            search = search.sort(sort)

        # 查询字段
        if query_fields:
            search = search.source(query_fields)

        return search

    @classmethod
    def build_base_search(cls, index: str | None = None, using: str | None = None) -> Any:
        if index:
            search = cls.search(using=using).index(index)
            search._index = index  # 直接修改属性，防止原index方法的index+=逻辑
        else:
            search = cls.search(using=using).index(cls.Index.name)
        return search

    @classmethod
    def es_query(cls, **kwargs: Any) -> list[dict[str, Any]]:
        """
        告警查询并返回特定字段列表
        :param query: 精确查询, 传参示例 {alarm_field: str/list}
        :param search: 模糊查询, 传参示例 {alarm_field: str}
        :param exclude_search: 不包含，模糊查询, 传参示例 {alarm_field: str}
        :param time_field: 时间段查询, 需要时间段查询的告警时间字段
        :param start_time: str, time_field开始时间
        :param end_time: str, time_field结束时间
        :param or_query: 或查询, 传参示例 {alarm_field: str}
        :param exclude_query: 排除查询, 传参示例 {alarm_field: str/list}
        :param global_search: 多字段模糊搜索, 传参示例 {keyword: str, search_list: [alarm_field1, alarm_field2]}
        :param sort: 排序, 传参实例 alarm_field/-alarm_field(倒序)
        :param query_fields: 查询字段, 传参示例 [alarm_field1, alarm_field2]
        :param using: es_client
        :param index: es_index
        :param from_dict: dsl查询字典，search.from_dict()的入参，当有此值时会基于此查询再附加查询条件
        :return:
        """
        scan = kwargs.get("scan", False)
        if "scan" in kwargs:
            del kwargs["scan"]

        format_kwargs = {}
        add_info = kwargs.get("add_info")
        if add_info is not None:
            format_kwargs["add_info"] = add_info
            del kwargs["add_info"]
        format_kwargs["index"] = kwargs.get("index")

        search = cls.get_query_instance(**kwargs)
        if scan:
            response = search.params(preserve_order=True).scan()
        else:
            search = search.extra(size=ES_MAX_OFFSET)
            response = search.execute()

        formatter = getattr(cls, "format", None)
        if formatter:
            return [formatter(cls(**hit.to_dict()), **format_kwargs) for hit in response]
        else:
            return [hit.to_dict() for hit in response]

    @classmethod
    def bulk_delete_by_ids(cls, doc_ids: list[str], using: str | None = None) -> None:
        """批量删除文档（通过文档ID）。

        更高效的删除方法，直接使用 ES 文档 _id 进行删除。
        适用于所有继承自 CWDocument 的子类。

        Args:
            doc_ids: ES 文档 _id 列表
            using: ES 连接别名

        Example:
            >>> CMDBInstance.bulk_delete_by_ids([
            ...     "tenant1_host_1",
            ...     "tenant1_host_2"
            ... ])
            >>> CMDBInstRelate.bulk_delete_by_ids([
            ...     "tenant1_host_module_host_1_module_10",
            ...     "tenant1_host_module_host_2_module_20"
            ... ])
        """
        if not doc_ids:
            return
        documents = [{"_op_type": "delete", "_id": doc_id} for doc_id in doc_ids]
        cls.bulk_actions(documents, using=using)


class BaseInstance(CWDocument):
    """基础实例文档类。

    提供实例文档的通用字段和聚合查询能力。

    Attributes:
        cw_object_model_code: 对象模型编码
        cw_object_model_inst_id: 对象模型实例ID
        unique_id: 唯一标识
        display_name: 显示名称
        bk_biz_ids: 业务ID列表
        sync_time: 同步时间
    """

    cw_object_model_code: Any = Keyword()
    cw_object_model_inst_id: Any = Keyword()
    unique_id: Any = Keyword()
    display_name: Any = Keyword()
    bk_biz_ids: Any = Integer()
    sync_time: Any = Date()
    # 租户id
    bk_tenant_id: Any = Keyword()

    OPTION_VALUES_MAX_SIZE: int = 10000

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        dynamic: Any = MetaField("true")
        dynamic_templates: Any = MetaField(
            [
                {"numeric_values": {"path_match": "alarm.*", "mapping": {"type": "integer", "coerce": True}}},
                {"objects": {"match_mapping_type": "object", "mapping": {"type": "object"}}},
                {
                    "all_as_text": {
                        "match_mapping_type": "*",
                        "mapping": {
                            "type": "text",
                            "norms": False,
                            "fields": {"keyword": {"type": "keyword", "ignore_above": 8191}},
                        },
                    }
                },
            ]
        )

    @classmethod
    def query_option_values(cls, query: Any, fields: Any) -> dict[str, list[str]]:
        """查询字段的可选值列表。

        通过聚合查询获取指定字段的所有不同值，常用于下拉框等场景。

        Args:
            query: 搜索查询对象
            fields: 需要查询可选值的字段列表

        Returns:
            字段可选值字典。如 {"field1": ["value1", "value2"], "field2": ["value3"]}

        Example:
            >>> s = CMDBInstance.get_search(query={"bk_obj_id": "host"})
            >>> values = CMDBInstance.query_option_values(s, ["bk_cloud_id", "bk_os_type"])
            >>> print(values["bk_cloud_id"])
            ['0', '1', '2']
        """
        for i in fields:
            query.aggs.bucket(f"{i}_values", A("terms", field=f"{i}.keyword", size=cls.OPTION_VALUES_MAX_SIZE))

        query = query.extra(size=0)
        response = query.execute()

        res: dict[str, list[str]] = {}
        for field in fields:
            values = getattr(response.aggregations, f"{field}_values")
            res[field] = [i["key"] for i in values.buckets if i["key"]]

        return res


class CMDBDocument(BaseInstance):
    """CMDB 文档基类。

    提供 CMDB 特有的功能，如自动获取最新索引等。
    所有 CMDB 相关的文档模型都应继承此类。
    """

    @override
    @classmethod
    def search(cls, using: str | None = None, index: str | None = None) -> Any:
        """搜索文档。

        覆盖父类的 search 方法，自动获取最新的读索引。

        Args:
            using: ES 连接别名
            index: 索引名。如果未指定则自动获取最新索引

        Returns:
            elasticsearch_dsl.Search 对象

        Example:
            >>> # 自动使用最新索引
            >>> auto_search = CMDBInstance.search()
            >>> # 指定索引
            >>> custom_search = CMDBInstance.search(index="custom_index")
        """
        if index is None:
            try:
                index = cls.get_read_index(using=using)
            except Exception as e:
                logger.warning(f"获取最新CMDB读索引失败: {e}")
        s = super().search(using=using, index=index)
        s = s.extra(track_total_hits=True)
        return s

    @classmethod
    def get_read_index(cls, using: str | None = None):
        """获取最新的读索引。

        优先通过读别名 ``{ALIAS}-read`` 获取目标索引，避免每次查询都做
        ``get_alias`` + ``LooseVersion`` 排序。若读别名不存在，则 fallback
        到原有的别名解析 + 版本排序逻辑。

        Args:
            using: ES 连接别名

        Returns:
            最新的 索引名

        Raises:
            Exception: 当无法获取索引列表时（含 fallback 也失败）

        Example:
            >>> index = CMDBInstance.get_read_index()
            >>> print(index)
            'bk_monitor_base_cmdb_instance_v10'
        """
        es_client = cls.get_es_client(using=using)
        read_alias = f"{cls.Index.ALIAS}-read"

        # 优先尝试读别名
        try:
            indices = es_client.indices.get_alias(name=read_alias, params={"request_timeout": 1})
            if indices:
                read_index = list(indices.keys())[0]
                return read_index
        except Exception:
            # 读别名不存在，fallback 到原有逻辑
            pass

        # fallback：通过写别名获取所有索引，按 LooseVersion 降序取第一个
        index_names = es_client.indices.get_alias(name=cls.Index.ALIAS, params={"request_timeout": 1}).keys()
        sorted_index_names = sorted(index_names, key=LooseVersion, reverse=True)
        read_index = sorted_index_names[0]
        return read_index


class CMDBInstance(CMDBDocument):
    """CMDB 实例文档模型。

    存储 CMDB 中所有对象模型的实例数据，如主机、模块、集群等。

    Attributes:
        bk_obj_id: CMDB 对象模型ID（如 host、module、set 等）
        bk_inst_id: 实例ID
        bk_biz_id: 业务ID
        bk_biz_name: 业务名称
        dynamic_group_id: 动态分组ID

    Example:
        >>> # 批量写入主机实例
        >>> CMDBInstance.bulk_update_or_create("host", [
        ...     {"bk_host_id": 1, "bk_host_name": "host1", "bk_cloud_id": 0},
        ...     {"bk_host_id": 2, "bk_host_name": "host2", "bk_cloud_id": 0}
        ... ])
        >>> # 查询主机实例
        >>> total, instances = CMDBInstance.get_search(
        ...     query={"bk_obj_id": "host", "bk_biz_id": "2"},
        ...     page=1, size=10
        ... ).execute()
        >>> # 删除实例
        >>> CMDBInstance.bulk_delete("host", [1, 2, 3])
    """

    bk_obj_id: Any = Keyword()
    bk_inst_id: Any = Integer()
    bk_biz_id: Any = Keyword()
    bk_biz_name: Any = Keyword()
    dynamic_group_id: Any = Keyword()
    bk_agent_alive: Any = Boolean()
    error: Any = Boolean()
    agent_status_sync_time: Any = Date()

    class Index:
        ALIAS: str = f"{ES_KEY_PREFIX}cmdb_instance"
        PATTERN: str = ALIAS + "*"
        name: str = ALIAS
        settings: dict[str, Any] = {
            "max_result_window": ES_MAX_OFFSET,
            "max_terms_count": 65535 * 3,
            "number_of_shards": ES_NUMBER_OF_SHARDS,
            "number_of_replicas": ES_NUMBER_OF_REPLICAS,
            "lifecycle": {
                "name": ALIAS + "_policy",
                "rollover_alias": ALIAS,
            },
            "mapping.total_fields.limit": ES_MAX_MAPPING_FIELDS,
        }

    @staticmethod
    def get_inst_id_field(bk_obj_id: str) -> str:
        """获取实例ID字段名。

        根据对象模型ID返回对应的实例ID字段名。
        内置对象（host、set、biz、module）使用特定字段名，
        其他对象使用通用的 bk_inst_id 字段。

        Args:
            bk_obj_id: 对象模型ID

        Returns:
            实例ID字段名

        Example:
            >>> CMDBInstance.get_inst_id_field("host")
            'bk_host_id'
            >>> CMDBInstance.get_inst_id_field("mysql")
            'bk_inst_id'
        """
        field = "bk_inst_id"
        if bk_obj_id in ["host", "set", "biz", "module"]:
            field = f"bk_{bk_obj_id}_id"
        return field

    @classmethod
    def bulk_update_or_create(cls, bk_obj_id: str, instances: list[dict[str, Any]]) -> None:
        """批量更新或创建实例。

        对于已存在的实例会更新，不存在的会创建。
        自动过滤掉实例ID为空的无效数据。
        自动设置 sync_time 为当前时间。

        Args:
            bk_obj_id: 对象模型ID（如 host、module、set 等）
            instances: 实例数据列表

        Example:
            >>> CMDBInstance.bulk_update_or_create("host", [
            ...     {"bk_host_id": 1, "bk_host_name": "host1", "bk_tenant_id": "tenant1"},
            ...     {"bk_host_id": 2, "bk_host_name": "host2", "bk_tenant_id": "tenant1"}
            ... ])
        """
        inst_id_field = cls.get_inst_id_field(bk_obj_id)
        valid_instances = [inst for inst in instances if inst[inst_id_field]]
        if bk_obj_id == "host" and valid_instances:
            tenant_host_groups: dict[str, list[dict[str, Any]]] = {}
            for inst in valid_instances:
                tenant_host_groups.setdefault(inst.get("bk_tenant_id", ""), []).append(inst)

            enriched_instances: list[dict[str, Any]] = []
            for bk_tenant_id, tenant_instances in tenant_host_groups.items():
                if not bk_tenant_id:
                    enriched_instances.extend(tenant_instances)
                    continue
                enriched_instances.extend(
                    enrich_host_instances_with_agent_status(
                        bk_tenant_id=bk_tenant_id,
                        host_instances=tenant_instances,
                    )
                )
            valid_instances = enriched_instances

        documents = []
        current_time = datetime.now()

        for inst in valid_instances:
            # 去除_id字段，防止ES写入报错
            inst.pop("_id", None)
            # 自动设置同步时间
            inst["sync_time"] = current_time

            # 租户ID是必须字段
            bk_tenant_id = inst.get("bk_tenant_id", "")
            if not bk_tenant_id:
                logger.warning(f"实例缺少租户ID: {inst}")
                continue

            documents.append(
                {
                    "_op_type": "index",
                    "_id": f"{bk_tenant_id}_{bk_obj_id}_{inst[inst_id_field]}",
                    "bk_obj_id": bk_obj_id,
                    "_source": inst,
                }
            )
        cls.bulk_actions(documents)

    @classmethod
    def bulk_delete(cls, bk_obj_id: str, inst_ids: list[int], bk_tenant_id: str = DEFAULT_TENANT_ID):
        """批量删除实例。

        Args:
            bk_obj_id: 对象模型ID
            inst_ids: 实例ID列表
            bk_tenant_id: 租户ID

        Example:
            >>> CMDBInstance.bulk_delete("host", [1, 2, 3], bk_tenant_id="system")
        """
        documents = []
        for inst_id in inst_ids:
            documents.append(
                {
                    "_op_type": "delete",
                    "_id": f"{bk_tenant_id}_{bk_obj_id}_{inst_id}",
                }
            )
        cls.bulk_actions(documents)

    @classmethod
    def redis_cache_key(cls) -> str:
        """获取 Redis 缓存键。

        Returns:
            Redis 缓存键名
        """
        return f"{REDIS_KEY_PREFIX}cmdb_synced_bk_obj"


class CMDBObjRelate(CMDBDocument):
    """CMDB 模型关联关系文档。

    存储 CMDB 对象模型之间的关联关系定义，如主机和模块之间的关联。

    Attributes:
        bk_obj_asst_id: 模型关联关系ID
        bk_obj_asst_name: 模型关联关系名称
        bk_obj_id: 源模型ID
        bk_asst_obj_id: 目标模型ID
        bk_asst_id: 关联模型的唯一ID
        mapping: 关联关系数量映射

    Example:
        >>> # 创建主机和模块的关联关系
        >>> CMDBObjRelate.bulk_update_or_create([{
        ...     "bk_obj_asst_id": "host_module",
        ...     "bk_obj_id": "host",
        ...     "bk_asst_obj_id": "module"
        ... }])
    """

    bk_obj_asst_id: Any = Keyword()
    bk_obj_asst_name: Any = Keyword()
    bk_obj_id: Any = Keyword()
    bk_asst_obj_id: Any = Keyword()
    bk_asst_id: Any = Keyword()
    mapping: Any = Keyword()
    sync_time: Any = Date()

    class Index:
        ALIAS: str = f"{ES_KEY_PREFIX}cmdb_obj_relate"
        PATTERN: str = ALIAS + "*"
        name: str = ALIAS
        settings: dict[str, Any] = {
            "max_result_window": ES_MAX_OFFSET,
            "max_terms_count": 65535 * 3,
            "number_of_shards": ES_NUMBER_OF_SHARDS,
            "number_of_replicas": ES_NUMBER_OF_REPLICAS,
            "lifecycle": {
                "name": ALIAS + "_policy",
                "rollover_alias": ALIAS,
            },
            "mapping.total_fields.limit": ES_MAX_MAPPING_FIELDS,
        }

    @classmethod
    def bulk_update_or_create(cls, instances: list[dict[str, Any]]) -> None:
        """批量更新或创建模型关联关系。

        Args:
            instances: 关联关系数据列表

        Example:
            >>> CMDBObjRelate.bulk_update_or_create([
            ...     {"bk_obj_asst_id": "rel1", "bk_obj_id": "host",
            ...      "bk_asst_obj_id": "module", "bk_tenant_id": "tenant1"}
            ... ])
        """
        documents = []
        current_time = datetime.now()

        for inst in instances:
            # 去除_id字段，防止ES写入报错
            inst.pop("_id", None)
            # 自动设置同步时间
            inst["sync_time"] = current_time

            # 租户ID是必须字段
            bk_tenant_id = inst.get("bk_tenant_id", "")
            if not bk_tenant_id:
                logger.warning(f"模型关联关系缺少租户ID: {inst}")
                continue

            documents.append(
                {
                    "_op_type": "index",
                    "_id": f"{bk_tenant_id}_{inst['bk_obj_asst_id']}",
                    "_source": inst,
                }
            )
        cls.bulk_actions(documents)

    @classmethod
    def bulk_delete(cls, bk_obj_asst_id: str, bk_tenant_id: str = DEFAULT_TENANT_ID):
        """删除模型关联关系。

        Args:
            bk_obj_asst_id: 模型关联关系ID
            bk_tenant_id: 租户ID

        Example:
            >>> CMDBObjRelate.bulk_delete("host_module", bk_tenant_id="system")
        """
        documents = [
            {
                "_op_type": "delete",
                "_id": f"{bk_tenant_id}_{bk_obj_asst_id}",
            }
        ]
        cls.bulk_actions(documents)


class CMDBInstRelate(CMDBDocument):
    """CMDB 实例关联关系文档。

    存储 CMDB 实例之间的关联关系，如具体某台主机和某个模块的关联。

    Attributes:
        bk_obj_asst_id: 模型关联关系ID
        bk_obj_id: 源模型ID
        bk_asst_obj_id: 目标模型ID
        bk_inst_id: 源实例ID
        bk_asst_inst_id: 目标实例ID

    Example:
        >>> # 创建主机实例和模块实例的关联
        >>> CMDBInstRelate.bulk_update_or_create([{
        ...     "bk_obj_asst_id": "host_module",
        ...     "bk_obj_id": "host",
        ...     "bk_inst_id": "1",
        ...     "bk_asst_obj_id": "module",
        ...     "bk_asst_inst_id": "10"
        ... }])
    """

    bk_obj_asst_id: Any = Keyword()
    bk_obj_id: Any = Keyword()
    bk_asst_obj_id: Any = Keyword()
    bk_inst_id: Any = Keyword()
    bk_asst_inst_id: Any = Keyword()
    sync_time: Any = Date()

    class Index:
        ALIAS: str = f"{ES_KEY_PREFIX}cmdb_inst_relate"
        PATTERN: str = ALIAS + "*"
        name: str = ALIAS
        settings: dict[str, Any] = {
            "max_result_window": ES_MAX_OFFSET,
            "max_terms_count": 65535 * 3,
            "number_of_shards": ES_NUMBER_OF_SHARDS,
            "number_of_replicas": ES_NUMBER_OF_REPLICAS,
            "lifecycle": {
                "name": ALIAS + "_policy",
                "rollover_alias": ALIAS,
            },
            "mapping.total_fields.limit": ES_MAX_MAPPING_FIELDS,
        }

    @classmethod
    def bulk_update_or_create(cls, instances: list[dict[str, Any]]) -> None:
        """批量更新或创建实例关联关系。

        自动设置 sync_time 为当前时间。

        Args:
            instances: 实例关联关系数据列表

        Example:
            >>> CMDBInstRelate.bulk_update_or_create([{
            ...     "bk_obj_asst_id": "host_module",
            ...     "bk_obj_id": "host", "bk_inst_id": "1",
            ...     "bk_asst_obj_id": "module", "bk_asst_inst_id": "10",
            ...     "bk_tenant_id": "tenant1"
            ... }])
        """
        documents = []
        current_time = datetime.now()

        for inst in instances:
            # 去除_id字段，防止ES写入报错
            inst.pop("_id", None)
            # 自动设置同步时间
            inst["sync_time"] = current_time

            # 租户ID是必须字段
            bk_tenant_id = cast(str, inst.get("bk_tenant_id", ""))
            if not bk_tenant_id:
                logger.warning(f"实例关联关系缺少租户ID: {inst}")
                continue

            bk_obj_asst_id = cast(str, inst.get("bk_obj_asst_id", ""))
            bk_obj_id = cast(str, inst.get("bk_obj_id", ""))
            bk_inst_id = cast(str, inst.get("bk_inst_id", ""))
            bk_asst_obj_id = cast(str, inst.get("bk_asst_obj_id", ""))
            bk_asst_inst_id = cast(str, inst.get("bk_asst_inst_id", ""))

            documents.append(
                {
                    "_op_type": "index",
                    "_id": f"{bk_tenant_id}_{bk_obj_asst_id}_{bk_obj_id}_{bk_inst_id}_{bk_asst_obj_id}_{bk_asst_inst_id}",
                    "_source": inst,
                }
            )
        cls.bulk_actions(documents)

    @classmethod
    def bulk_delete(cls, instances: list[dict[str, Any]]):
        """批量删除实例关联关系。

        Args:
            instances: 实例关联关系数据列表

        Example:
            >>> CMDBInstRelate.bulk_delete([{
            ...     "bk_obj_asst_id": "host_module",
            ...     "bk_obj_id": "host", "bk_inst_id": "1",
            ...     "bk_asst_obj_id": "module", "bk_asst_inst_id": "10"
            ... }])
        """
        documents = []
        for inst in instances:
            documents.append(
                {
                    "_op_type": "delete",
                    "_id": "{}_{}_{}_{}_{}_{}".format(
                        inst["bk_tenant_id"],
                        inst["bk_obj_asst_id"],
                        inst["bk_obj_id"],
                        inst["bk_inst_id"],
                        inst["bk_asst_obj_id"],
                        inst["bk_asst_inst_id"],
                    ),
                }
            )
        cls.bulk_actions(documents)
