from typing import Any, TypedDict

from .client import (
    access_deploy_plan_client,
    add_data_flow_node_client,
    apply_data_flow_client,
    apply_data_link_client,
    auth_projects_data_check_client,
    auth_result_table_client,
    batch_auth_result_table_client,
    bulk_list_result_table_client,
    create_data_flow_client,
    create_data_hub_client,
    create_data_storages_client,
    databus_cleans_client,
    delete_data_flow_client,
    delete_data_link_client,
    get_bkbase_raw_data_with_data_id_client,
    get_data_flow_client,
    get_data_flow_graph_client,
    get_data_flow_list_client,
    get_data_link_client,
    get_databus_cleans_client,
    get_kafka_info_client,
    get_latest_deploy_data_flow_client,
    get_result_table_client,
    list_data_link_client,
    notify_log_data_id_changed_client,
    query_auth_projects_data_client,
    query_metric_and_dimension_client,
    restart_data_flow_client,
    start_data_flow_client,
    start_databus_cleans_client,
    stop_data_flow_client,
    stop_databus_cleans_client,
    tail_kafka_data_client,
    update_data_flow_node_client,
    update_databus_cleans_client,
)


def notify_log_data_id_changed(bk_tenant_id: str, data_id: int) -> Any:
    """
    通知计算平台数据源变更

    Args:
        bk_tenant_id: 租户ID
        data_id: 数据ID

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    return notify_log_data_id_changed_client(
        bk_tenant_id=bk_tenant_id,
        params={"data_id": data_id},
    )


def apply_data_link(bk_tenant_id: str, config: list[Any]) -> dict[str, Any]:
    """
    申请数据链路

    Args:
        bk_tenant_id: 租户ID
        config: 资源描述

    Returns:
        链路信息

    Raises:
        BkApiError: 接口调用失败
    """
    result = apply_data_link_client(
        bk_tenant_id=bk_tenant_id,
        params={"config": config},
    )
    return result


def get_bkbase_raw_data_with_data_id(bk_tenant_id: str, bkbase_data_id: int) -> dict[str, Any]:
    """
    获取计算平台对应的data_id的raw_data信息，适用于获取V3链路迁移至V4链路后的data_name

    Args:
        bk_tenant_id: 租户ID
        bkbase_data_id: 计算平台对应的data_id

    Returns:
        原始数据表信息

    Raises:
        BkApiError: 接口调用失败
    """
    result = get_bkbase_raw_data_with_data_id_client(
        bk_tenant_id=bk_tenant_id,
        params={"bkbase_data_id": bkbase_data_id},
    )
    return result


def delete_data_link(bk_tenant_id: str, kind: str, namespace: str, name: str) -> Any:
    """
    删除数据链路

    Args:
        bk_tenant_id: 租户ID
        kind: 资源类型
        namespace: 命名空间
        name: 资源名称

    Returns:
        删除结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = delete_data_link_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "kind": kind,
            "namespace": namespace,
            "name": name,
        },
    )
    return result


def auth_result_table(bk_tenant_id: str, project_id: int, object_id: str, bk_biz_id: int) -> Any:
    """
    授权接口(管理员接口): 给项目加表权限

    Args:
        bk_tenant_id: 租户ID
        project_id: 计算平台项目
        object_id: 计算平台结果表ID
        bk_biz_id: 业务ID

    Returns:
        授权结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = auth_result_table_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "project_id": project_id,
            "object_id": object_id,
            "bk_biz_id": bk_biz_id,
        },
    )
    return result


def batch_auth_result_table(bk_tenant_id: str, project_id: int, object_ids: list[str], bk_biz_id: int) -> Any:
    """
    批量授权接口(管理员接口): 给项目加表权限

    Args:
        bk_tenant_id: 租户ID
        project_id: 计算平台项目
        object_ids: 计算平台结果表ID
        bk_biz_id: 业务ID

    Returns:
        授权结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = batch_auth_result_table_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "project_id": project_id,
            "object_ids": object_ids,
            "bk_biz_id": bk_biz_id,
        },
    )
    return result


def auth_projects_data_check(
    bk_tenant_id: str, project_id: int, result_table_id: str, action_id: str = "result_table.query_data"
) -> Any:
    """
    检查项目是否有结果表权限

    Args:
        bk_tenant_id: 租户ID
        project_id: 计算平台项目
        result_table_id: 结果表名称
        action_id: 动作方式

    Returns:
        检查结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = auth_projects_data_check_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "project_id": project_id,
            "result_table_id": result_table_id,
            "action_id": action_id,
        },
    )
    return result


def query_auth_projects_data(
    bk_tenant_id: str, project_id: int, object_ids: list[str], action_id: str = "result_table.query_data"
) -> dict[str, Any]:
    """
    批量检查项目是否有结果表权限

    Args:
        bk_tenant_id: 租户ID
        project_id: 计算平台项目
        object_ids: 计算平台结果表ID
        action_id: 业务ID

    Returns:
        结果表在项目下的权限信息{"permissions": ["xxx"], "no_permissions": ["xxx1"]}

    Raises:
        BkApiError: 接口调用失败
    """
    result = query_auth_projects_data_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "project_id": project_id,
            "object_ids": object_ids,
            "action_id": action_id,
        },
    )
    return result


def access_deploy_plan(
    bk_tenant_id: str,
    data_scenario: str,
    bk_biz_id: int,
    access_raw_data: dict[str, Any],
    access_conf_info: dict[str, Any] | None = None,
    description: str = "",
    data_scenario_id: str = "",
) -> dict[str, Any]:
    """
    提交接入部署计划(数据源接入)

    Args:
        bk_tenant_id: 租户ID
        data_scenario: 计算平台项目
        data_scenario_id: 计算平台结果表ID
        bk_biz_id: 业务ID
        access_raw_data: 原始数据描述
        access_conf_info: 接入配置描述
        description: 描述信息

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    params = {
        "data_scenario": data_scenario,
        "bk_biz_id": bk_biz_id,
        "access_raw_data": access_raw_data,
        "description": description,
    }
    if data_scenario_id:
        params["data_scenario_id"] = data_scenario_id
    if access_conf_info is not None:
        params["access_conf_info"] = access_conf_info

    result = access_deploy_plan_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    return result


def get_databus_cleans(
    bk_tenant_id: str,
    raw_data_id: str,
) -> list[dict[str, Any]]:
    """
    获取数据清洗信息列表

    Args:
        bk_tenant_id: 租户ID
        raw_data_id: 数据接入源ID

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = get_databus_cleans_client(
        bk_tenant_id=bk_tenant_id,
        params={"raw_data_id": raw_data_id},
    )
    return result


def query_metric_and_dimension(
    bk_tenant_id: str, storage: str, result_table_id: str, values: list[str], version: str = ""
) -> dict[str, Any]:
    """
    查询指标和维度

    Args:
        bk_tenant_id: 租户ID
        storage: 存储类型
        result_table_id: 结果表ID
        values: 维度列表
        version: 数据格式版本

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    params = {
        "storage": storage,
        "result_table_id": result_table_id,
        "values": values,
    }
    if version:
        params["version"] = version
    result = query_metric_and_dimension_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )
    return result


def list_data_link(
    bk_tenant_id: str,
    kind: str,
    namespace: str = "bkmonitor",
) -> list[dict[str, Any]]:
    """
    拉取计算平台V4资源列表

    Args:
        bk_tenant_id: 租户ID
        kind: 资源类型
        namespace: 命名空间

    Returns:
        资源列表

    Raises:
        BkApiError: 接口调用失败
    """

    result = list_data_link_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "kind": kind,
            "namespace": namespace,
        },
    )
    return result


class DataBusCleansField(TypedDict):
    """
    数据清洗字段
    field_name: 字段英文标识
    field_type: 字段类型
    field_alias: 字段别名
    is_dimension: 是否为维度字段
    field_index: 字段顺序索引
    """

    field_name: str  # 字段英文标识
    field_type: str  # 字段类型
    field_alias: str  # 字段别名
    is_dimension: bool  # 是否为维度字段
    field_index: int  # 字段顺序索引


class DataBusCleansParams(TypedDict):
    """
    数据清洗参数
    """

    raw_data_id: str  # 数据接入源ID
    json_config: str  # 数据清洗配置，json格式
    pe_config: str  # 清洗规则的pe配置
    bk_biz_id: int  # 业务ID
    clean_config_name: str  # 清洗配置名称
    result_table_name: str  # 清洗配置输出的结果表英文标识
    result_table_name_alias: str  # 清洗配置输出的结果表别名
    fields: list[DataBusCleansField]  # 输出字段列表
    description: str  # 清洗配置描述信息
    bk_username: str  # 用户名
    result_table_id: str  # 结果表 ID
    processing_id: str  # 数据处理 ID


def databus_cleans(bk_tenant_id: str, params: DataBusCleansParams) -> dict[str, Any]:
    """
    接入数据清洗

    Args:
        bk_tenant_id: 租户ID
        params: 数据清洗参数

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """

    result = databus_cleans_client(bk_tenant_id=bk_tenant_id, params=params)
    return result


def start_databus_cleans(
    bk_tenant_id: str, result_table_id: str, storages: list[str] | None = None, processing_id: str = ""
) -> dict[str, Any]:
    """
    启动清洗配置

    Args:
        bk_tenant_id: 租户ID
        result_table_id: 数据清洗参数
        storages: 分发任务的存储列表
        processing_id: 数据处理 ID

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    if not storages:
        storages = ["kafka"]
    result = start_databus_cleans_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "result_table_id": result_table_id,
            "storages": storages,
            "processing_id": processing_id,
        },
    )
    return result


def get_data_link(bk_tenant_id: str, kind: str, namespace: str, name: str) -> dict[str, Any]:
    """
    获取数据链路

    Args:
        bk_tenant_id: 租户ID
        kind: 资源类型
        namespace: 命名空间
        name: 资源名称

    Returns:
        资源列表

    Raises:
        BkApiError: 接口调用失败
    """
    result = get_data_link_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "kind": kind,
            "namespace": namespace,
            "name": name,
        },
    )
    return result


def bulk_list_result_table(
    bk_tenant_id: str,
    related: list[str] | None = None,
    bk_biz_id: list[int] | None = None,
    storages: list[str] | None = None,
    page_size: int = 5000,
) -> list[Any]:
    """
    按照业务ID批量拉取计算平台结果表元信息

    Args:
        bk_tenant_id: 租户ID
        related: 查询条件
        bk_biz_id: 业务ID列表
        storages: 存储列表
        page_size: 分页大小

    Returns:
        资源列表

    Raises:
        BkApiError: 接口调用失败
    """
    generate_type = "user"
    if not related:
        related = ["fields", "storages"]

    # 分页拉取，当前接口为返回 total_count 因此同步翻页拉取
    result_table_list: list[dict[str, Any]] = []
    page = 1
    params: dict[str, Any] = {
        "related": related,
        "bk_biz_id": bk_biz_id,
        "storages": storages,
        "generate_type": generate_type,
    }
    while True:
        params.update({"page": page})
        data: list[dict[str, Any]] = bulk_list_result_table_client(bk_tenant_id=bk_tenant_id, params=params)
        data_length = len(data)
        # 过滤存储类型
        if storages:
            expect_storages: set[str] = set(storages)
            tables: list[dict[str, Any]] = []
            for table in data:
                table: dict[str, Any]
                storages: set[str] = {key for key, info in table["storages"].items() if info["active"]}
                if not expect_storages & storages:
                    continue
                tables.append(table)
        else:
            tables: list[dict[str, Any]] = data
        result_table_list.extend(tables)
        if data_length < page_size:
            break
        page += 1
    return result_table_list


def delete_data_flow(bk_tenant_id: str, flow_id: int) -> dict[str, Any]:
    """
    删除DataFlow

    Args:
        bk_tenant_id: 租户ID
        flow_id: DataFlow的ID

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = delete_data_flow_client(bk_tenant_id=bk_tenant_id, params={"flow_id": flow_id})
    return result


def get_kafka_info(bk_tenant_id: str, tags: str = "bkmonitor_outer") -> list[dict[str, Any]]:
    """
    查询计算平台使用的 kafka 信息

    Args:
        bk_tenant_id: 租户ID
        tags: tag标识

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = get_kafka_info_client(bk_tenant_id=bk_tenant_id, params={"tags": tags})
    return result


def get_latest_deploy_data_flow(bk_tenant_id: str, flow_id: int) -> dict[str, Any]:
    """
    获取DataFlow的最近部署信息

    Args:
        bk_tenant_id: 租户ID
        flow_id: DataFlow的ID

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = get_latest_deploy_data_flow_client(bk_tenant_id=bk_tenant_id, params={"flow_id": flow_id})
    return result


def get_result_table(bk_tenant_id: str, result_table_id: str, related: list[str] | None = None) -> dict[str, Any]:
    """
    查询指定结果表

    Args:
        bk_tenant_id: 租户ID
        result_table_id: 结果表名称
        related: 查询条件
    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    if not related:
        related = ["fields", "storages"]
    result = get_result_table_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "result_table_id": result_table_id,
            "related": related,
        },
    )
    return result


def start_data_flow(
    bk_tenant_id: str,
    flow_id: int,
    consuming_mode: str = "continue",
    cluster_group: str = "default",
    check_and_start_clean_task: bool = True,
) -> dict[str, Any]:
    """
    启动DataFlow

    Args:
        bk_tenant_id: 租户ID
        flow_id: DataFlow的ID
        consuming_mode: 数据处理模式
        cluster_group: 计算集群组
        check_and_start_clean_task: 是否检查并启动清洗任务
    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = start_data_flow_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "flow_id": flow_id,
            "consuming_mode": consuming_mode,
            "cluster_group": cluster_group,
            "check_and_start_clean_task": check_and_start_clean_task,
        },
    )
    return result


def stop_data_flow(bk_tenant_id: str, flow_id: int) -> dict[str, Any]:
    """
    停止DataFlow

    Args:
        bk_tenant_id: DataFlow ID
        flow_id: DataFlow的ID
    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = stop_data_flow_client(bk_tenant_id=bk_tenant_id, params={"flow_id": flow_id})
    return result


def stop_databus_cleans(
    bk_tenant_id: str,
    result_table_id: str,
    storages: list[str] | None = None,
) -> dict[str, Any]:
    """
    停止清洗配置

    Args:
        bk_tenant_id: 租户ID
        result_table_id: 清洗结果表名称
        storages: 分发任务的存储列表
    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    if not storages:
        storages = ["kafka"]
    result = stop_databus_cleans_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "result_table_id": result_table_id,
            "storages": storages,
        },
    )
    return result


def tail_kafka_data(bk_tenant_id: str, name: str, namespace: str = "bkmonitor", limit: int = 10) -> list[str]:
    """
    停止清洗配置

    Args:
        bk_tenant_id: 租户ID
        name: 数据源名称（计算平台）
        namespace: 命名空间
        limit: 条数
    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = tail_kafka_data_client(
        bk_tenant_id=bk_tenant_id, params={"name": name, "namespace": namespace, "limit": limit}
    )
    return result


class DataFlowNode(TypedDict):
    """
    计算平台流程节点
    """

    id: int
    node_type: str
    result_table_ids: list[str]
    name: str
    bk_biz_id: int
    cluster: str
    from_result_table_ids: list[str]
    expires: int
    schemaless: bool
    from_nodes: list[dict[str, Any]]


def apply_data_flow(bk_tenant_id: str, project_id: str, flow_name: str, nodes: list[DataFlowNode]) -> dict[str, Any]:
    """
    创建计算平台流程

    Args:
        bk_tenant_id: 租户ID
        project_id: 计算平台的项目ID
        flow_name: 命名空间
        nodes: 流程节点
    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = apply_data_flow_client(
        bk_tenant_id=bk_tenant_id, params={"project_id": project_id, "flow_name": flow_name, "nodes": nodes}
    )
    return result


class DataHubCommonParams(TypedDict):
    bk_biz_id: int
    maintainer: str
    bk_username: str
    data_scenario: str


class DataHubRawDataParams(TypedDict):
    raw_data_name: str
    raw_data_alias: str
    sensitivity: str
    data_encoding: str
    data_region: str
    description: str
    data_source_tags: list[str]
    tags: list[str]
    data_scenario: dict[str, Any]


def create_data_hub(
    bk_tenant_id: str,
    common: DataHubCommonParams,
    raw_data: DataHubRawDataParams,
    clean: list[dict[str, Any]],
    storage: list[str] | None = None,
) -> dict[str, Any]:
    """
    创建数据入库

    Args:
        bk_tenant_id: 租户ID
        common: 公共配置
        raw_data: 原始数据配置
        clean: 数据清洗
        storage: 数据存储
    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = create_data_hub_client(
        bk_tenant_id=bk_tenant_id, params={"common": common, "raw_data": raw_data, "clean": clean, "storage": storage}
    )
    return result


class CreateDataStorageFieldParams(TypedDict):
    """
    数据存储字段
    """

    physical_field: str  # 物理表字段
    field_name: str  # 字段英文标识
    field_type: str  # 字段类型
    field_alias: str  # 字段别名
    is_dimension: bool  # 是否为维度字段
    field_index: int  # 字段顺序索引


def create_data_storages(
    bk_tenant_id: str,
    raw_data_id: str,
    data_type: str,
    result_table_name: str,
    result_table_name_alias: str,
    storage_type: str,
    storage_cluster: str,
    expires: int,
    fields: list[CreateDataStorageFieldParams],
    config: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """
    创建数据入库

    Args:
        bk_tenant_id: 租户ID
        raw_data_id: 公共配置
        data_type: 原始数据配置
        result_table_name: 数据清洗
        result_table_name_alias: 数据存储
        storage_type: 数据存储
        storage_cluster: 数据存储
        expires: 数据存储
        fields: 数据存储
        config: 数据存储
    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """

    result = create_data_storages_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "raw_data_id": raw_data_id,
            "data_type": data_type,
            "result_table_name": result_table_name,
            "result_table_name_alias": result_table_name_alias,
            "storage_type": storage_type,
            "storage_cluster": storage_cluster,
            "expires": expires,
            "fields": fields,
            "config": config,
        },
    )
    return result


class UpdateDatabusCleanFieldParams(TypedDict):
    """
    输出字段列表
    """

    field_name: str  # 字段英文标识
    field_type: str  # 字段类型
    field_alias: str  # 字段别名
    is_dimension: bool  # 是否为维度字段
    field_index: int  # 字段顺序索引


def update_databus_cleans(
    bk_tenant_id: str,
    processing_id: str,
    raw_data_id: str,
    json_config: str,
    bk_biz_id: int,
    clean_config_name: str,
    result_table_name: str,
    result_table_name_alias: str,
    fields: list[UpdateDatabusCleanFieldParams],
    description: str = "",
    pe_config: str = "",
) -> dict[str, Any]:
    """
    更新数据清洗

    Args:
        bk_tenant_id: 租户ID
        processing_id: 清洗配置ID
        raw_data_id: 数据接入源ID
        json_config: 数据清洗配置，json格式
        bk_biz_id: 业务ID
        clean_config_name: 清洗配置名称
        result_table_name: 清洗配置输出的结果表英文标识
        result_table_name_alias: 清洗配置输出的结果表别名
        fields: 输出字段列表
        description: 清洗配置描述信息
        pe_config: 清洗规则的pe配置
    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """

    result = update_databus_cleans_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "processing_id": processing_id,
            "raw_data_id": raw_data_id,
            "json_config": json_config,
            "bk_biz_id": bk_biz_id,
            "clean_config_name": clean_config_name,
            "result_table_name": result_table_name,
            "result_table_name_alias": result_table_name_alias,
            "fields": fields,
            "description": description,
            "pe_config": pe_config,
        },
    )
    return result


def update_data_flow_node(
    bk_tenant_id: str,
    flow_id: int,
    node_id: int,
    from_links: list[dict[str, Any]],
    node_type: str,
    config: dict[str, Any],
    frontend_info: dict[str, Any],
) -> dict[str, Any]:
    """
    更新DataFlow节点

    Args:
        bk_tenant_id: 租户ID
        flow_id: DataFlow的ID
        node_id: DataFlow的节点ID
        from_links: 与上游节点的连线信息
        node_type: 节点类型
        config: 节点配置
        frontend_info: DataFlow画布上的位置信息

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = update_data_flow_node_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "flow_id": flow_id,
            "node_id": node_id,
            "from_links": from_links,
            "node_type": node_type,
            "config": config,
            "frontend_info": frontend_info,
        },
    )
    return result


def add_data_flow_node(
    bk_tenant_id: str,
    flow_id: int,
    from_links: list[dict[str, Any]],
    node_type: str,
    config: dict[str, Any],
    frontend_info: dict[str, Any],
) -> dict[str, Any]:
    """
    添加DataFlow节点

    Args:
        bk_tenant_id: 租户ID
        flow_id: DataFlow的ID
        from_links: 与上游节点的连线信息
        node_type: 节点类型
        config: 节点配置
        frontend_info: DataFlow画布上的位置信息

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = add_data_flow_node_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "flow_id": flow_id,
            "from_links": from_links,
            "node_type": node_type,
            "config": config,
            "frontend_info": frontend_info,
        },
    )
    return result


def get_data_flow_list(bk_tenant_id: str, project_id: int) -> list[dict[str, Any]]:
    """
    获取DataFlow列表信息

    Args:
        bk_tenant_id: 租户ID
        project_id: 计算平台的项目ID

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = get_data_flow_list_client(bk_tenant_id=bk_tenant_id, params={"project_id": project_id})
    return result


def get_data_flow(bk_tenant_id: str, flow_id: int) -> dict[str, Any]:
    """
    获取DataFlow信息

    Args:
        bk_tenant_id: 租户ID
        flow_id: DataFlow的ID

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = get_data_flow_client(bk_tenant_id=bk_tenant_id, params={"flow_id": flow_id})
    return result


def get_data_flow_graph(bk_tenant_id: str, flow_id: int) -> dict[str, Any]:
    """
    获取DataFlow里的画布信息,即画布中的节点信息

    Args:
        bk_tenant_id: 租户ID
        flow_id: DataFlow的ID

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = get_data_flow_graph_client(bk_tenant_id=bk_tenant_id, params={"flow_id": flow_id})
    return result


def create_data_flow(
    bk_tenant_id: str, project_id: int, flow_name: str, nodes: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """
    创建DataFlow

    Args:
        bk_tenant_id: 租户ID
        project_id: 计算平台的项目ID
        flow_name: DataFlow名称
        nodes: 节点列表

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    if nodes is None:
        nodes = []
    result = create_data_flow_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "project_id": project_id,
            "flow_name": flow_name,
            "nodes": nodes,
        },
    )
    return result


def restart_data_flow(
    bk_tenant_id: str,
    flow_id: int,
    consuming_mode: str = "continue",
    cluster_group: str = "default",
) -> dict[str, Any]:
    """
    重启DataFlow

    Args:
        bk_tenant_id: 租户ID
        flow_id: DataFlow的ID
        consuming_mode: 数据处理模式
        cluster_group: 计算集群组

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    result = restart_data_flow_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "flow_id": flow_id,
            "consuming_mode": consuming_mode,
            "cluster_group": cluster_group,
        },
    )
    return result
