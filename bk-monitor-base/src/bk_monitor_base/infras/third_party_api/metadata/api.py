from typing import Any, NotRequired, TypedDict, cast

from .client import (
    create_cluster_info_client,
    create_data_id_client,
    create_event_group_client,
    create_result_table_client,
    create_result_table_metric_split_client,
    create_time_series_group_client,
    delete_cluster_info_client,
    delete_event_group_client,
    delete_time_series_group_client,
    full_cmdb_node_info_client,
    get_data_id_client,
    get_event_group_client,
    get_label_client,
    get_result_table_client,
    get_result_table_storage_client,
    get_time_series_group_client,
    list_result_table_client,
    list_transfer_cluster_client,
    modify_cluster_info_client,
    modify_data_id_client,
    modify_event_group_client,
    modify_result_table_client,
    modify_time_series_group_client,
    query_cluster_info_client,
    query_event_group_client,
    query_tag_values_client,
    query_time_series_group_client,
)

__all__ = [
    # DataSource
    "create_data_source",
    "get_data_source",
    "modify_data_source",
    # ResultTable
    "create_result_table",
    "get_result_table",
    "modify_result_table",
    "list_result_table",
    "full_cmdb_node_info",
    "create_result_table_metric_split",
    # TimeSeriesGroup
    "query_time_series_group",
    "create_time_series_group",
    "modify_time_series_group",
    "get_time_series_group",
    "delete_time_series_group",
    # EventGroup
    "create_event_group",
    "modify_event_group",
    "get_event_group",
    "delete_event_group",
    "query_event_group_client",
    # Label
    "list_label",
    # TagValues
    "query_tag_values",
    # Kafka
    "kafka_tail",
    # params or results
    "CreateDataSourceParams",
    "CreateTimeSeriesGroupParams",
    "ModifyDataSourceParams",
    "ModifyTimeSeriesGroupParams",
    "GetDataSourceResult",
    "QueryEventGroupResult",
]


class CreateDataSourceParams(TypedDict, total=False):
    """创建数据源 参数"""

    data_name: str  # 数据源名称
    etl_config: str  # 清洗模板配置
    source_label: str  # 数据源标签
    type_label: str  # 数据类型标签
    is_custom_source: bool  # 是否用户自定义数据源

    # 以下均为可选项
    operator: NotRequired[str]  # 操作者
    data_description: NotRequired[str]  # 数据源描述
    mq_cluster: NotRequired[int]  # 数据源使用的消息集群ID
    bk_biz_id: NotRequired[int]  # 业务ID
    space_uid: NotRequired[str]  # 空间uid
    option: NotRequired[dict[str, Any]]  # 数据源配置项
    is_platform_data_id: NotRequired[bool]  # 是否为平台级数据源


def create_data_source(
    bk_tenant_id: str,
    operator: str,
    data_name: str,
    etl_config: str,
    source_label: str,
    type_label: str,
    bk_biz_id: int | None = None,
    bk_data_id: int | None = None,
    mq_cluster: int | None = None,
    mq_config: dict[str, Any] | None = None,
    data_description: str | None = None,
    is_custom_source: bool = True,
    option: dict[str, Any] | None = None,
    custom_label: str | None = None,
    transfer_cluster_id: str | None = None,
    space_uid: str | None = None,
    authorized_spaces: list[str] | None = None,
    is_platform_data_id: bool = False,
    space_type_id: str | None = None,
    data_label: str = "",
) -> int:
    """创建数据源

    Args:
        bk_tenant_id: 租户ID
        operator: 操作者
        data_name: 数据源名称
        etl_config: 清洗模板配置
        source_label: 数据源标签
        type_label: 数据类型标签
        bk_biz_id: 业务ID
        bk_data_id: 数据源ID
        mq_cluster: 数据源使用的消息集群ID
        mq_config: 数据源消息队列配置
        data_description: 数据源描述
        is_custom_source: 是否用户自定义数据源，默认 True
        option: 数据源配置项
        custom_label: 自定义标签
        transfer_cluster_id: transfer集群ID
        space_uid: 空间英文名称，默认 ""
        authorized_spaces: 授权使用的空间 ID 列表
        is_platform_data_id: 是否为平台级 ID，默认 False
        space_type_id: 数据源所属类型，默认 SpaceTypes.ALL.value
        data_label: 数据标签，默认 ""

    Returns:
        数据源ID (bk_data_id)

    Raises:
        BkApiError: 接口调用失败
    """
    # 构建参数字典，仅包含非 None 的值
    params: dict[str, Any] = {
        "data_name": data_name,
        "etl_config": etl_config,
        "source_label": source_label,
        "type_label": type_label,
        "operator": operator,
        "is_custom_source": is_custom_source,
        "is_platform_data_id": is_platform_data_id,
        "data_label": data_label,
    }

    # 添加可选参数（仅当值不为 None 时）
    if bk_biz_id is not None:
        params["bk_biz_id"] = bk_biz_id
    if bk_data_id is not None:
        params["bk_data_id"] = bk_data_id
    if mq_cluster is not None:
        params["mq_cluster"] = mq_cluster
    if mq_config is not None:
        params["mq_config"] = mq_config
    if data_description is not None:
        params["data_description"] = data_description
    if option is not None:
        params["option"] = option
    if custom_label is not None:
        params["custom_label"] = custom_label
    if transfer_cluster_id is not None:
        params["transfer_cluster_id"] = transfer_cluster_id
    if authorized_spaces is not None:
        params["authorized_spaces"] = authorized_spaces
    if space_type_id is not None:
        params["space_type_id"] = space_type_id
    if space_uid is not None:
        params["space_uid"] = space_uid

    response = create_data_id_client(bk_tenant_id=bk_tenant_id, params=params)
    return response["bk_data_id"]


class GetDataSourceResult(TypedDict):
    """获取数据源 返回值"""

    bk_data_id: int
    data_id: int
    bk_tenant_id: str
    mq_config: dict[str, Any]
    etl_config: str
    option: dict[str, Any]
    type_label: str
    source_label: str
    token: str
    transfer_cluster_id: str
    data_name: str
    is_platform_data_id: bool
    space_type_id: str
    space_uid: str
    bk_biz_id: int
    data_description: str
    result_table_list: list[Any]


def get_data_source(
    bk_tenant_id: str, bk_data_id: int | None = None, data_name: str | None = None
) -> GetDataSourceResult:
    """获取数据源"""

    if not bk_data_id and not data_name:
        raise ValueError("Either 'bk_data_id' or 'data_name' must be provided")

    params: dict[str, Any] = {}
    if bk_data_id:
        params["bk_data_id"] = bk_data_id

    if data_name:
        params["data_name"] = data_name

    return get_data_id_client(bk_tenant_id=bk_tenant_id, params=params)


class ModifyDataSourceParams(TypedDict):
    """修改数据源 参数"""

    data_id: int  # 数据源ID

    data_name: NotRequired[str]  # 数据源名称
    data_description: NotRequired[str]  # 数据源描述
    etl_config: NotRequired[str]  # 清洗模板配置
    operator: NotRequired[str]  # 操作者
    option: NotRequired[dict[str, Any]]  # 数据源配置项
    is_platform_data_id: NotRequired[bool]  # 是否为平台级数据源
    is_enable: NotRequired[bool]  # 是否启用


def modify_data_source(
    bk_tenant_id: str,
    operator: str,
    data_id: int,
    data_name: str | None = None,
    data_description: str | None = None,
    option: dict[str, Any] | None = None,
    is_enable: bool | None = None,
    is_platform_data_id: bool | None = None,
    authorized_spaces: list[str] | None = None,
    space_type_id: str | None = None,
    etl_config: str | None = None,
) -> GetDataSourceResult:
    """修改数据源

    Args:
        bk_tenant_id: 租户ID
        operator: 操作者
        data_id: 数据源ID
        data_name: 数据源名称
        data_description: 数据源描述
        option: 数据源配置项
        is_enable: 是否启用
        is_platform_data_id: 是否为平台级数据源
        authorized_spaces: 授权使用的空间 ID 列表
        space_type_id: 数据源所属类型
        etl_config: 清洗模板配置

    Returns:
        数据源信息

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {
        "data_id": data_id,
        "operator": operator,
    }

    if data_name is not None:
        params["data_name"] = data_name
    if data_description is not None:
        params["data_description"] = data_description
    if option is not None:
        params["option"] = option
    if is_enable is not None:
        params["is_enable"] = is_enable
    if is_platform_data_id is not None:
        params["is_platform_data_id"] = is_platform_data_id
    if authorized_spaces is not None:
        params["authorized_spaces"] = authorized_spaces
    if space_type_id is not None:
        params["space_type_id"] = space_type_id
    if etl_config is not None:
        params["etl_config"] = etl_config

    return modify_data_id_client(bk_tenant_id=bk_tenant_id, params=params)


class FieldConfig(TypedDict, total=False):
    """字段配置"""

    field_name: str  # 字段名
    field_type: str  # 字段类型，可以为float, string, boolean和timestamp
    tag: str  # 字段标签，可以为metric, dimension, timestamp, group
    description: str  # 字段描述信息
    alias_name: str  # 入库别名
    option: dict[str, Any]  # 字段选项配置
    is_config_by_user: bool  # 用户是否启用该字段配置


class CreateResultTableParams(TypedDict):
    """创建结果表参数"""

    bk_data_id: int  # 数据源ID
    table_id: str  # 结果表ID，格式应该为 库.表(例如，system.cpu)
    table_name_zh: str  # 结果表中文名
    is_custom_table: bool  # 是否用户自定义结果表
    schema_type: str  # 结果表字段配置方案, free(无schema配置), fixed(固定schema)
    default_storage: str  # 默认存储类型，目前支持influxdb
    label: str  # 结果表标签

    operator: NotRequired[str]  # 操作者
    field_list: NotRequired[list[FieldConfig]]  # 字段信息
    bk_biz_id: NotRequired[int]  # 业务ID
    default_storage_config: NotRequired[dict[str, Any]]  # 默认的存储信息
    external_storage: NotRequired[dict[str, Any]]  # 额外存储配置
    option: NotRequired[dict[str, Any]]  # 结果表的额外配置信息
    is_time_field_only: NotRequired[bool]  # 默认字段是否仅需要time
    time_alias_name: NotRequired[str]  # 时间字段上传时需要使用其他字段名


class ModifyResultTableParams(TypedDict):
    """修改结果表参数"""

    table_id: str  # 结果表ID
    operator: NotRequired[str]  # 操作者
    label: str  # 结果表标签

    field_list: NotRequired[list[FieldConfig]]  # 全量的字段列表
    table_name_zh: NotRequired[str]  # 结果表中文名
    default_storage: NotRequired[str]  # 结果表默认存储类型
    is_time_field_only: NotRequired[bool]  # 默认字段是否仅需要time
    external_storage: NotRequired[dict[str, Any]]  # 额外存储配置
    is_enable: NotRequired[bool]  # 是否启用结果表


class ResultTableResult(TypedDict):
    """结果表返回值"""

    table_id: str  # 结果表ID
    table_name_zh: str  # 结果表中文名
    is_custom_table: bool  # 是否自定义结果表
    schema_type: str  # 结果表schema配置方案
    default_storage: str  # 默认存储方案
    storage_list: list[str]  # 所有存储列表
    creator: str  # 创建者
    create_time: str  # 创建时间
    last_modify_user: str  # 最后修改者
    last_modify_time: str  # 最后修改时间
    field_list: list[dict[str, Any]]  # 字段列表
    label: str  # 结果表标签
    bk_biz_id: int  # 业务ID


def create_result_table(
    bk_tenant_id: str,
    operator: str,
    bk_data_id: int,
    table_id: str,
    table_name_zh: str,
    is_custom_table: bool,
    schema_type: str,
    default_storage: str,
    bk_biz_id_alias: str | None = None,
    field_list: list[FieldConfig] | None = None,
    query_alias_settings: list[dict[str, Any]] | None = None,
    bk_biz_id: int = 0,
    label: str = "others",
    external_storage: dict[str, Any] | None = None,
    is_time_field_only: bool = False,
    option: dict[str, Any] | None = None,
    time_alias_name: str | None = None,
    time_option: dict[str, Any] | None = None,
    is_sync_db: bool = True,
    data_label: str = "",
    default_storage_config: dict[str, Any] | None = None,
) -> str:
    """创建结果表

    根据给定的配置参数，创建一个结果表

    Args:
        bk_tenant_id: 租户ID
        operator: 操作者
        bk_data_id: 数据源ID
        table_id: 结果表ID
        table_name_zh: 结果表中文名
        is_custom_table: 是否用户自定义结果表
        schema_type: 结果表字段配置方案
        default_storage: 默认存储类型
        bk_biz_id_alias: 过滤条件业务ID别名
        field_list: 字段列表
        query_alias_settings: 查询别名设置
        bk_biz_id: 结果表所属业务ID，默认 0
        label: 结果表标签，默认 "others"
        external_storage: 额外存储配置
        is_time_field_only: 是否仅需要提供时间默认字段，默认 False
        option: 结果表选项内容
        time_alias_name: 时间节点
        time_option: 时间字段选项配置
        is_sync_db: 是否需要同步创建真实表，默认 True
        data_label: 数据标签，默认 ""
        default_storage_config: 默认存储参数

    Returns:
        结果表ID (table_id)

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {
        "bk_data_id": bk_data_id,
        "table_id": table_id,
        "table_name_zh": table_name_zh,
        "is_custom_table": is_custom_table,
        "schema_type": schema_type,
        "default_storage": default_storage,
        "operator": operator,
        "bk_biz_id": bk_biz_id,
        "label": label,
        "is_time_field_only": is_time_field_only,
        "is_sync_db": is_sync_db,
        "data_label": data_label,
    }

    if bk_biz_id_alias is not None:
        params["bk_biz_id_alias"] = bk_biz_id_alias
    if field_list is not None:
        params["field_list"] = field_list
    if query_alias_settings is not None:
        params["query_alias_settings"] = query_alias_settings
    if external_storage is not None:
        params["external_storage"] = external_storage
    if option is not None:
        params["option"] = option
    if time_alias_name is not None:
        params["time_alias_name"] = time_alias_name
    if time_option is not None:
        params["time_option"] = time_option
    if default_storage_config is not None:
        params["default_storage_config"] = default_storage_config

    response = create_result_table_client(bk_tenant_id=bk_tenant_id, params=params)
    return response


def get_result_table(bk_tenant_id: str, table_id: str) -> ResultTableResult:
    """获取结果表信息

    根据给定的结果表ID，返回这个结果表的具体信息

    Args:
        bk_tenant_id: 租户ID
        table_id: 结果表ID

    Returns:
        结果表信息

    Raises:
        BkApiError: 接口调用失败
    """
    return get_result_table_client(bk_tenant_id=bk_tenant_id, params={"table_id": table_id})


def modify_result_table(
    bk_tenant_id: str,
    operator: str,
    table_id: str,
    bk_biz_id_alias: str | None = None,
    field_list: list[FieldConfig] | None = None,
    query_alias_settings: list[dict[str, Any]] | None = None,
    table_name_zh: str | None = None,
    default_storage: str | None = None,
    label: str | None = None,
    external_storage: dict[str, Any] | None = None,
    option: dict[str, Any] | None = None,
    is_enable: bool | None = None,
    is_time_field_only: bool = False,
    is_reserved_check: bool = True,
    time_option: dict[str, Any] | None = None,
    data_label: str | None = None,
    need_delete_storages: dict[str, Any] | None = None,
) -> ResultTableResult:
    """修改结果表

    根据给定的配置参数，修改一个结果表的配置

    Args:
        bk_tenant_id: 租户ID
        operator: 操作者
        table_id: 结果表ID
        bk_biz_id_alias: 过滤条件业务ID别名
        field_list: 字段列表
        query_alias_settings: 查询别名设置
        table_name_zh: 结果表中文名
        default_storage: 默认存储方案
        label: 结果表标签
        external_storage: 额外存储配置
        option: 结果表选项内容
        is_enable: 是否启用结果表
        is_time_field_only: 默认字段仅有time，默认 False
        is_reserved_check: 检查内置字段，默认 True
        time_option: 时间字段选项配置
        data_label: 数据标签
        need_delete_storages: 需要删除的额外存储

    Returns:
        修改后的结果表信息

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {
        "table_id": table_id,
        "operator": operator,
        "is_time_field_only": is_time_field_only,
        "is_reserved_check": is_reserved_check,
    }

    if bk_biz_id_alias is not None:
        params["bk_biz_id_alias"] = bk_biz_id_alias
    if field_list is not None:
        params["field_list"] = field_list
    if query_alias_settings is not None:
        params["query_alias_settings"] = query_alias_settings
    if table_name_zh is not None:
        params["table_name_zh"] = table_name_zh
    if default_storage is not None:
        params["default_storage"] = default_storage
    if label is not None:
        params["label"] = label
    if external_storage is not None:
        params["external_storage"] = external_storage
    if option is not None:
        params["option"] = option
    if is_enable is not None:
        params["is_enable"] = is_enable
    if time_option is not None:
        params["time_option"] = time_option
    if data_label is not None:
        params["data_label"] = data_label
    if need_delete_storages is not None:
        params["need_delete_storages"] = need_delete_storages

    return modify_result_table_client(bk_tenant_id=bk_tenant_id, params=params)


def list_result_table(
    bk_tenant_id: str,
    datasource_type: str | None = None,
    bk_biz_id: int | None = None,
    is_public_include: int | None = None,
    is_config_by_user: bool = True,
    page: int | None = None,
    page_size: int | None = None,
) -> list[ResultTableResult]:
    """查询结果表列表

    根据给定的过滤条件，查询符合条件的结果表列表

    Args:
        bk_tenant_id: 租户ID
        datasource_type: 需要过滤的结果表类型，可选值：system(系统结果表), bk_data(计算平台结果表)
        bk_biz_id: 需要过滤的业务ID
        is_public_include: 是否需要包含全业务结果表，0 - 不包含 / 1 - 包含 / 2 - 只看全业务
        is_config_by_user: 是否需要包含非用户配置的字段
        page: 分页页码
        page_size: 每页数量

    Returns:
        结果表列表

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {
        "is_config_by_user": is_config_by_user,
    }

    if datasource_type is not None:
        params["datasource_type"] = datasource_type

    if bk_biz_id is not None:
        params["bk_biz_id"] = bk_biz_id

    if is_public_include is not None:
        params["is_public_include"] = is_public_include

    if page is not None:
        params["page"] = page

    if page_size is not None:
        params["page_size"] = page_size

    return list_result_table_client(bk_tenant_id=bk_tenant_id, params=params)


def full_cmdb_node_info(bk_tenant_id: str, table_id: str | None = None):
    """补充CMDB节点信息

    Args:
        bk_tenant_id: 租户ID
        table_id: 结果表id

    Raises:
        BkApiError: 接口调用失败
    """

    if not table_id:
        raise ValueError("'table_id' must be provided")

    params: dict[str, Any] = {}
    if table_id:
        params["table_id"] = table_id

    return full_cmdb_node_info_client(bk_tenant_id=bk_tenant_id, params=params)


def create_result_table_metric_split(
    bk_tenant_id: str, cmdb_level: str | None = None, table_id: str | None = None, operator: str | None = None
) -> dict[str, Any]:
    """
    创建一个结果表CMDB拆分

    Args:
        bk_tenant_id: 租户ID
        cmdb_level: 拆分表cmdb_level
        table_id: 结果表id
        operator: 操作者

    Returns:
        结果表信息

    Raises:
        BkApiError: 接口调用失败
    """
    if not cmdb_level and not table_id and not operator:
        raise ValueError("Either 'cmdb_level' or 'table_id' or 'operator' must be provided")

    params: dict[str, Any] = {}
    if cmdb_level:
        params["cmdb_level"] = cmdb_level
    if table_id:
        params["table_id"] = table_id
    if operator:
        params["operator"] = operator

    return create_result_table_metric_split_client(bk_tenant_id=bk_tenant_id, params=params)


class TimeSeriesGroupResult(TypedDict):
    """时序分组 返回值"""

    bk_tenant_id: str
    bk_biz_id: int
    bk_data_id: int
    time_series_group_id: int
    time_series_group_name: str
    table_id: str
    label: str
    data_label: str
    is_split_measurement: bool
    metric_info_list: list[dict[str, Any]]
    is_enable: bool


def query_time_series_group(
    bk_tenant_id: str,
    bk_biz_id: int | None = None,
    time_series_group_name: str | None = None,
    label: str | None = None,
    page: int = 1,
    page_size: int = 500,
) -> list[dict[str, Any]] | dict[str, Any]:
    """查询自定义时序分组

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 业务ID
        time_series_group_name: 时序分组名称
        label: 自定义分组标签
        page: 页数
        page_size: 页长

    Returns:
        时序分组列表/分页时序分组信息{"count": int, "info": list[时序分组信息]}

    Raises:
        BkApiError: 接口调用失败
    """

    params: dict[str, Any] = {}
    if bk_biz_id:
        params["bk_biz_id"] = bk_biz_id

    if time_series_group_name:
        params["time_series_group_name"] = time_series_group_name

    if label:
        params["label"] = label

    # Note: page_size不同时返回数据结构不一样
    # 如果开启分页，返回值包含count信息
    if page_size > 0:
        params.update({"page": page, "page_size": page_size})
        result: dict[str, Any] = query_time_series_group_client(bk_tenant_id=bk_tenant_id, params=params)
        return result

    # 如果没有分页信息
    ts_groups: list[TimeSeriesGroupResult] = query_time_series_group_client(bk_tenant_id=bk_tenant_id, params=params)
    return cast(list[dict[str, Any]], ts_groups)


class CreateTimeSeriesGroupParams(TypedDict, total=False):
    """创建时序分组 参数"""

    bk_biz_id: int
    time_series_group_name: str
    bk_data_id: int
    label: str
    operator: str
    is_split_measurement: bool
    data_label: NotRequired[str]
    table_id: NotRequired[str]
    metric_info_list: NotRequired[list[dict[str, Any]]]
    additional_options: NotRequired[dict[str, Any]]


def create_time_series_group(
    bk_tenant_id: str,
    operator: str,
    bk_data_id: int,
    bk_biz_id: int,
    time_series_group_name: str,
    label: str,
    metric_info_list: list[dict[str, Any]] | None = None,
    table_id: str | None = None,
    is_split_measurement: bool = False,
    default_storage_config: dict[str, Any] | None = None,
    additional_options: dict[str, Any] | None = None,
    data_label: str = "",
) -> TimeSeriesGroupResult:
    """创建时序分组

    Args:
        bk_tenant_id: 租户ID
        operator: 创建者
        bk_data_id: 数据源ID
        bk_biz_id: 业务ID
        time_series_group_name: 自定义时序分组名
        label: 自定义时序分组标签
        metric_info_list: 自定义时序metric列表
        table_id: 结果表id
        is_split_measurement: 是否启动自动分表逻辑，默认 False
        default_storage_config: 默认存储参数
        additional_options: 附带创建的ResultTableOption
        data_label: 数据标签，默认 ""

    Returns:
        时序分组信息

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {
        "bk_data_id": bk_data_id,
        "bk_biz_id": bk_biz_id,
        "time_series_group_name": time_series_group_name,
        "label": label,
        "operator": operator,
        "is_split_measurement": is_split_measurement,
        "data_label": data_label,
    }

    if metric_info_list is not None:
        params["metric_info_list"] = metric_info_list
    if table_id is not None:
        params["table_id"] = table_id
    if default_storage_config is not None:
        params["default_storage_config"] = default_storage_config
    if additional_options is not None:
        params["additional_options"] = additional_options

    return create_time_series_group_client(bk_tenant_id=bk_tenant_id, params=params)


class ModifyTimeSeriesGroupParams(TypedDict, total=False):
    """修改时序分组 参数"""

    time_series_group_id: int
    operator: str

    time_series_group_name: NotRequired[str]
    label: NotRequired[str]
    enable_field_black_list: NotRequired[bool]
    is_enable: NotRequired[bool]
    data_label: NotRequired[str]
    field_list: NotRequired[list[dict[str, Any]]]
    metric_info_list: NotRequired[list[dict[str, Any]]]


def modify_time_series_group(
    bk_tenant_id: str,
    operator: str,
    time_series_group_id: int,
    time_series_group_name: str | None = None,
    label: str | None = None,
    field_list: list[dict[str, Any]] | None = None,
    is_enable: bool | None = None,
    metric_info_list: list[dict[str, Any]] | None = None,
    enable_field_black_list: bool | None = None,
    data_label: str | None = None,
) -> TimeSeriesGroupResult:
    """修改时序分组

    Args:
        bk_tenant_id: 租户ID
        operator: 修改者
        time_series_group_id: 自定义时序分组ID
        time_series_group_name: 自定义时序分组名
        label: 自定义时序分组标签
        field_list: 字段列表
        is_enable: 是否启用自定义分组
        metric_info_list: metric信息
        enable_field_black_list: 黑名单的启用状态
        data_label: 数据标签

    Returns:
        时序分组信息

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {
        "time_series_group_id": time_series_group_id,
        "operator": operator,
    }

    if time_series_group_name is not None:
        params["time_series_group_name"] = time_series_group_name
    if label is not None:
        params["label"] = label
    if field_list is not None:
        params["field_list"] = field_list
    if is_enable is not None:
        params["is_enable"] = is_enable
    if metric_info_list is not None:
        params["metric_info_list"] = metric_info_list
    if enable_field_black_list is not None:
        params["enable_field_black_list"] = enable_field_black_list
    if data_label is not None:
        params["data_label"] = data_label

    return modify_time_series_group_client(bk_tenant_id=bk_tenant_id, params=params)


def kafka_tail(bk_tenant_id: str, bk_data_id: int, namespace: str, size: int = 1) -> dict[str, Any]:
    """Kafka日志追踪接口

    Args:
        bk_tenant_id: 租户ID
        bk_data_id: 数据源ID
        namespace: 命名空间
        size: 返回日志条数，默认1条

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    from .client import kafka_tail_client

    return kafka_tail_client(
        bk_tenant_id=bk_tenant_id,
        params={"data_id": bk_data_id, "namespace": namespace, "size": size},
    )


class GetTimeSeriesGroupResult(TypedDict):
    """获取时序分组详情 返回值"""

    time_series_group_id: int  # 自定义时序分组ID
    bk_data_id: int  # 数据源ID
    bk_biz_id: int  # 业务ID
    time_series_group_name: str  # 自定义时序分组名
    label: str  # 自定义时序标签
    is_enable: bool  # 是否启用
    creator: str  # 创建者
    create_time: str  # 创建时间
    last_modify_user: str  # 最后修改者
    last_modify_time: str  # 最后修改时间
    metric_info_list: list[dict[str, Any]]  # Metric列表
    shipper_list: NotRequired[list[dict[str, Any]]]  # 结果表配置信息


def get_time_series_group(
    bk_tenant_id: str,
    time_series_group_id: int,
    with_result_table_info: bool = False,
) -> list[GetTimeSeriesGroupResult]:
    """获取时序分组详情

    根据给定的时序分组ID，查询其具体信息

    Args:
        bk_tenant_id: 租户ID
        time_series_group_id: 自定义时序分组ID
        with_result_table_info: 是否返回存储信息

    Returns:
        时序分组详情

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {"time_series_group_id": time_series_group_id}
    if with_result_table_info:
        params["with_result_table_info"] = with_result_table_info

    return get_time_series_group_client(bk_tenant_id=bk_tenant_id, params=params)


def delete_time_series_group(
    bk_tenant_id: str,
    operator: str,
    time_series_group_id: int,
) -> None:
    """删除时序分组

    根据给定的时序分组ID，删除该分组

    Args:
        bk_tenant_id: 租户ID
        operator: 操作者
        time_series_group_id: 自定义时序分组ID

    Raises:
        BkApiError: 接口调用失败
    """
    return delete_time_series_group_client(
        bk_tenant_id=bk_tenant_id,
        params={"time_series_group_id": time_series_group_id, "operator": operator},
    )


class EventInfoConfig(TypedDict):
    """事件信息配置"""

    event_name: str  # 事件名
    dimension_list: list[str]  # 维度列表


class CreateEventGroupParams(TypedDict):
    """创建事件分组 参数"""

    bk_data_id: int  # 数据源ID
    bk_biz_id: int  # 业务ID
    event_group_name: str  # 事件分组名
    label: str  # 事件分组标签，用于表示事件监控对象，应该复用result_table_label类型下的标签
    operator: str  # 操作者

    event_info_list: NotRequired[list[EventInfoConfig]]  # 事件列表


class EventGroupResult(TypedDict):
    """事件分组 返回值"""

    event_group_id: int  # 事件分组ID
    bk_data_id: int  # 数据源ID
    bk_biz_id: int  # 业务ID
    event_group_name: str  # 事件分组名
    label: str  # 事件标签
    table_id: str  # 结果表
    is_enable: bool  # 是否启用
    creator: str  # 创建者
    create_time: str  # 创建时间
    last_modify_user: str  # 最后修改者
    last_modify_time: str  # 最后修改时间
    event_info_list: list[dict[str, Any]]  # 事件列表


def create_event_group(
    bk_tenant_id: str,
    operator: str,
    bk_data_id: int,
    bk_biz_id: int,
    event_group_name: str,
    label: str,
    event_info_list: list[EventInfoConfig] | None = None,
    data_label: str = "",
) -> EventGroupResult:
    """创建事件分组

    给定一个数据源和业务，创建一个归属的事件分组ID

    Args:
        bk_tenant_id: 租户ID
        operator: 创建者
        bk_data_id: 数据源ID
        bk_biz_id: 业务ID
        event_group_name: 事件分组名
        label: 事件分组标签
        event_info_list: 事件列表
        data_label: 数据标签，默认 ""

    Returns:
        事件分组信息

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {
        "bk_data_id": bk_data_id,
        "bk_biz_id": bk_biz_id,
        "event_group_name": event_group_name,
        "label": label,
        "operator": operator,
        "data_label": data_label,
    }

    if event_info_list is not None:
        params["event_info_list"] = event_info_list

    return create_event_group_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )


class ModifyEventGroupParams(TypedDict):
    """修改事件分组 参数"""

    event_group_id: int  # 事件组ID
    operator: str  # 操作者

    event_group_name: NotRequired[str]  # 事件分组名
    label: NotRequired[str]  # 事件分组标签
    event_info_list: NotRequired[list[EventInfoConfig]]  # 事件列表
    is_enable: NotRequired[bool]  # 是否停用事件组


def modify_event_group(
    bk_tenant_id: str,
    event_group_id: int,
    operator: str,
    event_group_name: str | None = None,
    label: str | None = None,
    event_info_list: list[EventInfoConfig] | None = None,
    is_enable: bool | None = None,
    data_label: str | None = None,
) -> EventGroupResult:
    """修改事件分组

    给定一个事件分组ID，修改某些具体的信息

    Args:
        bk_tenant_id: 租户ID
        event_group_id: 事件分组ID
        operator: 修改者
        event_group_name: 事件分组名
        label: 事件分组标签
        event_info_list: 事件列表
        is_enable: 是否启用事件分组
        data_label: 数据标签

    Returns:
        事件分组信息

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {
        "event_group_id": event_group_id,
        "operator": operator,
    }

    if event_group_name is not None:
        params["event_group_name"] = event_group_name
    if label is not None:
        params["label"] = label
    if event_info_list is not None:
        params["event_info_list"] = event_info_list
    if is_enable is not None:
        params["is_enable"] = is_enable
    if data_label is not None:
        params["data_label"] = data_label

    return modify_event_group_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )


class GetEventGroupResult(TypedDict):
    """获取事件分组详情 返回值"""

    event_group_id: int  # 事件分组ID
    bk_data_id: int  # 数据源ID
    bk_biz_id: int  # 业务ID
    event_group_name: str  # 事件分组名
    label: str  # 事件标签
    is_enable: bool  # 是否启用
    creator: str  # 创建者
    create_time: str  # 创建时间
    last_modify_user: str  # 最后修改者
    last_modify_time: str  # 最后修改时间
    event_info_list: list[dict[str, Any]]  # 事件列表
    shipper_list: NotRequired[list[dict[str, Any]]]  # 结果表配置信息


def get_event_group(
    bk_tenant_id: str,
    event_group_id: int,
    with_result_table_info: bool = False,
) -> GetEventGroupResult:
    """获取事件分组详情

    根据给定的事件分组ID，查询其具体信息

    Args:
        bk_tenant_id: 租户ID
        event_group_id: 事件分组ID
        with_result_table_info: 是否返回存储信息

    Returns:
        事件分组详情

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {"event_group_id": event_group_id}
    if with_result_table_info:
        params["with_result_table_info"] = with_result_table_info

    return get_event_group_client(bk_tenant_id=bk_tenant_id, params=params)


class QueryEventGroupResult(TypedDict):
    """查询事件分组详情 返回值"""

    event_group_id: int  # 事件分组ID
    bk_data_id: int  # 数据源ID
    bk_biz_id: int  # 业务ID
    table_id: int  # 结果表ID
    event_group_name: str  # 事件分组名
    label: str  # 事件标签
    is_enable: bool  # 是否启用
    creator: str  # 创建者
    create_time: str  # 创建时间
    last_modify_user: str  # 最后修改者
    last_modify_time: str  # 最后修改时间
    event_info_list: list[dict[str, Any]]  # 事件列表
    status: str  # 事件分组状态


def query_event_group(
    bk_tenant_id: str,
    event_group_name: str | None = None,
    label: str | None = None,
    bk_biz_id: int | None = None,
    bk_data_ids: list[int] | None = None,
) -> list[QueryEventGroupResult]:
    """查询事件分组列表

    根据给定的过滤条件，查询符合条件的事件分组列表

    Args:
        bk_tenant_id: 租户ID
        event_group_name: 事件分组名称
        label: 事件标签
        bk_biz_id: 业务ID
        bk_data_ids: 数据源ID列表

    Returns:
        事件分组列表

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {}

    if event_group_name is not None:
        params["event_group_name"] = event_group_name
    if label is not None:
        params["label"] = label
    if bk_biz_id is not None:
        params["bk_biz_id"] = bk_biz_id
    if bk_data_ids is not None:
        params["bk_data_ids"] = bk_data_ids

    return query_event_group_client(bk_tenant_id=bk_tenant_id, params=params)


def delete_event_group(
    bk_tenant_id: str,
    operator: str,
    event_group_id: int,
) -> None:
    """删除事件分组

    根据给定的事件分组ID，删除该分组

    Args:
        bk_tenant_id: 租户ID
        operator: 操作者
        event_group_id: 事件分组ID

    Raises:
        BkApiError: 接口调用失败
    """
    delete_event_group_client(
        bk_tenant_id=bk_tenant_id,
        params={"event_group_id": event_group_id, "operator": operator},
    )


class LabelInfo(TypedDict):
    """标签信息"""

    label_id: str  # 标签ID（英文名）
    label_name: str  # 标签名（中文名）
    label_type: str  # 标签分类
    level: int | None  # 标签层级
    parent_label: str | None  # 父级标签ID
    index: int  # 标签在同level下的排序顺序


class ListLabelResult(TypedDict, total=False):
    """获取标签列表 返回值"""

    source_label: list[LabelInfo]  # 数据源标签
    type_label: list[LabelInfo]  # 数据类型标签
    result_table_label: list[LabelInfo]  # 结果表标签


def list_label(
    bk_tenant_id: str,
    label_type: str,
    level: int | None = None,
    include_admin_only: bool = False,
) -> ListLabelResult:
    """获取标签列表

    根据请求的参数，返回各个请求数据标签，包含了数据源标签及结果表各级标签

    Args:
        bk_tenant_id: 租户ID
        label_type: 标签分类，可选值：source_label, type_label, result_table_label
        level: 标签层级，从1开始计算，该配置只在label_type为result_table_label时生效
        include_admin_only: 是否展示管理员可见标签

    Returns:
        标签列表

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {
        "label_type": label_type,
        "include_admin_only": include_admin_only,
    }
    if level is not None:
        params["level"] = level

    return get_label_client(bk_tenant_id=bk_tenant_id, params=params)


def query_tag_values(
    bk_tenant_id: str,
    table_id: str,
    tag_name: str,
) -> dict[str, list[str]]:
    """查询tag/dimension的可选值

    查询数据源指定tag/dimension的可选值

    Args:
        bk_tenant_id: 租户ID
        table_id: 结果表ID
        tag_name: tag/dimension字段名

    Returns:
        tag/dimension的可选值列表

    Raises:
        BkApiError: 接口调用失败
    """
    response = query_tag_values_client(
        bk_tenant_id=bk_tenant_id,
        params={"table_id": table_id, "tag_name": tag_name},
    )
    return response


def query_cluster_info(
    bk_tenant_id: str,
    cluster_id: int | None = None,
    cluster_name: str | None = None,
    cluster_type: str | None = None,
    is_plain_text: bool = False,
) -> list[dict[str, Any]]:
    """查询存储集群信息

    Args:
        bk_tenant_id: 租户ID
        cluster_id: 存储集群ID
        cluster_name: 存储集群名
        cluster_type: 存储集群类型
        is_plain_text: 是否需要明文显示登陆信息

    Returns:
        存储集群信息列表

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {}
    if cluster_id is not None:
        params["cluster_id"] = cluster_id
    if cluster_name is not None:
        params["cluster_name"] = cluster_name
    if cluster_type is not None:
        params["cluster_type"] = cluster_type
    params["is_plain_text"] = is_plain_text

    response = query_cluster_info_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    return response


def list_transfer_cluster(
    bk_tenant_id: str,
) -> list[dict[str, Any]]:
    """获取所有transfer集群信息

    Args:
        bk_tenant_id: 租户ID

    Returns:
        transfer集群信息列表

    Raises:
        BkApiError: 接口调用失败
    """

    response = list_transfer_cluster_client(bk_tenant_id=bk_tenant_id)
    return response


def get_result_table_storage(
    bk_tenant_id: str,
    result_table_list: list[str] | None = None,
    storage_type: str | None = None,
    is_plain_text: bool = False,
) -> list[dict[str, Any]]:
    """获取监控结果表存储信息

    Args:
        bk_tenant_id: 租户ID
        result_table_list: 结果表ID列表
        storage_type: 存储类型
        is_plain_text: 是否需要明文显示登陆信息

    Returns:
        结果表存储信息列表

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {"is_plain_text": is_plain_text}
    if result_table_list is not None:
        params["result_table_list"] = result_table_list
    if storage_type is not None:
        params["storage_type"] = storage_type
    response = get_result_table_storage_client(bk_tenant_id=bk_tenant_id, params=params)
    return response


def create_cluster_info(
    bk_tenant_id: str,
    cluster_type: str,
    domain_name: str,
    port: int,
    operator: str,
    cluster_name: str = "",
    display_name: str | None = None,
    description: str = "",
    auth_info: dict[str, str] | None = None,
    version: str = "",
    custom_option: str = "",
    schema: str = "",
    is_ssl_verify: bool = False,
    ssl_verification_mode: str = "",
    ssl_certificate_authorities: str = "",
    ssl_certificate: str = "",
    ssl_certificate_key: str = "",
    ssl_insecure_skip_verify: bool = False,
    extranet_domain_name: str = "",
    extranet_port: int = 0,
) -> int:
    """创建存储集群

    Args:
        bk_tenant_id: 租户ID
        cluster_type: 集群类型
        domain_name: 集群域名
        port: 集群端口
        operator: 操作者
        cluster_name: 集群名
        display_name: 集群显示名称
        description: 存储集群描述
        auth_info: 身份认证信息
        version: 版本信息
        custom_option: 自定义标签
        schema: 链接协议
        is_ssl_verify: 是否需要SSL验证
        ssl_verification_mode: 校验模式
        ssl_certificate_authorities: CA 证书内容
        ssl_certificate: SSL/TLS 证书内容
        ssl_certificate_key: SSL/TLS 私钥内容
        ssl_insecure_skip_verify: 是否跳过服务端校验
        extranet_domain_name: 外网集群域名
        extranet_port: 外网集群端口

    Returns:
        存储集群ID

    Raises:
        BkApiError: 接口调用失败
    """
    auth_info = auth_info or {}
    display_name = display_name or cluster_name

    params: dict[str, Any] = {
        "cluster_type": cluster_type,
        "domain_name": domain_name,
        "port": port,
        "auth_info": auth_info,
        "operator": operator,
    }
    if cluster_name:
        params["cluster_name"] = cluster_name
    if display_name:
        params["display_name"] = display_name
    if description:
        params["description"] = description
    if version:
        params["version"] = version
    if custom_option:
        params["custom_option"] = custom_option
    if schema:
        params["schema"] = schema
    if is_ssl_verify:
        params["is_ssl_verify"] = is_ssl_verify
    if ssl_verification_mode:
        params["ssl_verification_mode"] = ssl_verification_mode
    if ssl_certificate_authorities:
        params["ssl_certificate_authorities"] = ssl_certificate_authorities
    if ssl_certificate:
        params["ssl_certificate"] = ssl_certificate
    if ssl_certificate_key:
        params["ssl_certificate_key"] = ssl_certificate_key
    if ssl_insecure_skip_verify:
        params["ssl_insecure_skip_verify"] = ssl_insecure_skip_verify
    if extranet_domain_name:
        params["extranet_domain_name"] = extranet_domain_name
    if extranet_port:
        params["extranet_port"] = extranet_port
    response = create_cluster_info_client(bk_tenant_id=bk_tenant_id, params=params)
    return response


def modify_cluster_info(
    bk_tenant_id: str,
    operator: str,
    cluster_id: int | None = None,
    cluster_type: str | None = None,
    cluster_name: str | None = None,
    display_name: str | None = None,
    description: str | None = None,
    auth_info: dict[str, str] | None = None,
    custom_option: str | None = None,
    schema: str | None = None,
    is_ssl_verify: bool | None = None,
    ssl_verification_mode: str | None = None,
    ssl_certificate_authorities: str | None = None,
    ssl_certificate: str | None = None,
    ssl_certificate_key: str | None = None,
    ssl_insecure_skip_verify: bool | None = None,
    extranet_domain_name: str | None = None,
    extranet_port: int | None = None,
) -> dict[str, Any]:
    """修改存储集群

    Args:
        bk_tenant_id: 租户ID
        cluster_type: 集群类型
        operator: 操作者
        cluster_id: 存储集群ID
        cluster_name: 集群名
        display_name: 集群显示名称
        description: 存储集群描述
        auth_info: 身份认证信息
        version: 版本信息
        custom_option: 自定义标签
        schema: 链接协议
        is_ssl_verify: 是否需要SSL验证
        ssl_verification_mode: 校验模式
        ssl_certificate_authorities: CA 证书内容
        ssl_certificate: SSL/TLS 证书内容
        ssl_certificate_key: SSL/TLS 私钥内容
        ssl_insecure_skip_verify: 是否跳过服务端校验
        extranet_domain_name: 外网集群域名
        extranet_port: 外网集群端口

    Returns:
        存储集群信息

    Raises:
        BkApiError: 接口调用失败
    """

    params: dict[str, Any] = {
        "operator": operator,
    }
    if cluster_type is not None:
        params["cluster_type"] = cluster_type
    if cluster_id is not None:
        params["cluster_id"] = cluster_id
    if auth_info is not None:
        params["auth_info"] = auth_info
    if cluster_name is not None:
        params["cluster_name"] = cluster_name
    if display_name is not None:
        params["display_name"] = display_name
    if description is not None:
        params["description"] = description
    if custom_option is not None:
        params["custom_option"] = custom_option
    if schema is not None:
        params["schema"] = schema
    if is_ssl_verify is not None:
        params["is_ssl_verify"] = is_ssl_verify
    if ssl_verification_mode is not None:
        params["ssl_verification_mode"] = ssl_verification_mode
    if ssl_certificate_authorities is not None:
        params["ssl_certificate_authorities"] = ssl_certificate_authorities
    if ssl_certificate is not None:
        params["ssl_certificate"] = ssl_certificate
    if ssl_certificate_key is not None:
        params["ssl_certificate_key"] = ssl_certificate_key
    if ssl_insecure_skip_verify is not None:
        params["ssl_insecure_skip_verify"] = ssl_insecure_skip_verify
    if extranet_domain_name is not None:
        params["extranet_domain_name"] = extranet_domain_name
    if extranet_port is not None:
        params["extranet_port"] = extranet_port
    response = modify_cluster_info_client(bk_tenant_id=bk_tenant_id, params=params)
    return response


def delete_cluster_info(
    bk_tenant_id: str,
    operator: str,
    cluster_id: int | None = None,
    cluster_name: str | None = None,
) -> Any:
    """删除集群存储

    Args:
        bk_tenant_id: 租户ID
        operator: 操作者
        cluster_id: 存储集群ID
        cluster_name: 集群名

    Returns:
        删除结果

    Raises:
        BkApiError: 接口调用失败
    """

    params: dict[str, Any] = {
        "operator": operator,
    }
    if cluster_id is not None:
        params["cluster_id"] = cluster_id
    if cluster_name is not None:
        params["cluster_name"] = cluster_name

    response = delete_cluster_info_client(bk_tenant_id=bk_tenant_id, params=params)
    return response
