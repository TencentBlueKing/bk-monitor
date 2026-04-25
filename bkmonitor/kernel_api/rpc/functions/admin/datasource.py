"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from django.db.models import Q

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import (
    build_response,
    count_by_field,
    get_bk_tenant_id,
    normalize_include,
    normalize_ordering,
    normalize_optional_bool,
    normalize_pagination,
    paginate_queryset,
    serialize_model,
    serialize_option,
    serialize_value,
)
from metadata import models

FUNC_DATASOURCE_LIST = "admin.datasource.list"
FUNC_DATASOURCE_DETAIL = "admin.datasource.detail"
FUNC_DATASOURCE_DATA_ID_CONFIG_COMPONENT_CONFIG = "admin.datasource.data_id_config.component_config"

DATASOURCE_FIELDS = [
    "bk_data_id",
    "bk_tenant_id",
    "data_name",
    "data_description",
    "type_label",
    "source_label",
    "custom_label",
    "source_system",
    "is_enable",
    "is_custom_source",
    "is_platform_data_id",
    "space_type_id",
    "space_uid",
    "created_from",
    "mq_cluster_id",
    "mq_config_id",
    "transfer_cluster_id",
    "creator",
    "create_time",
    "last_modify_user",
    "last_modify_time",
]
DATASOURCE_DETAIL_FIELDS = DATASOURCE_FIELDS[:4] + [
    "mq_cluster_id",
    "mq_config_id",
    "etl_config",
    "is_custom_source",
    "type_label",
    "source_label",
    "custom_label",
    "source_system",
    "is_enable",
    "transfer_cluster_id",
    "is_platform_data_id",
    "space_type_id",
    "space_uid",
    "created_from",
    "creator",
    "create_time",
    "last_modify_user",
    "last_modify_time",
]
ORDERING_FIELDS = {
    "bk_data_id",
    "data_name",
    "created_from",
    "source_label",
    "type_label",
    "is_enable",
    "is_custom_source",
    "is_platform_data_id",
    "space_uid",
    "create_time",
    "last_modify_time",
}
INCLUDE_VALUES = {"options", "spaces", "result_tables", "data_id_config", "data_id_config_component_config"}
DEFAULT_DETAIL_INCLUDE = {"spaces", "result_tables"}
KAFKA_CLUSTER_FIELDS = [
    "cluster_id",
    "cluster_name",
    "display_name",
    "cluster_type",
    "is_default_cluster",
    "registered_system",
    "label",
]
KAFKA_TOPIC_FIELDS = ["id", "bk_data_id", "topic", "partition", "batch_size", "flush_interval", "consume_rate"]


def _normalize_bk_data_id(value: Any) -> int:
    if value in (None, ""):
        raise CustomException(message="bk_data_id 为必填项")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message="bk_data_id 必须是整数") from error


def _serialize_datasource(datasource: models.DataSource) -> dict[str, Any]:
    item = serialize_model(datasource, DATASOURCE_FIELDS)
    item["has_token"] = bool(getattr(datasource, "token", ""))
    return item


def _serialize_datasource_detail(datasource: models.DataSource) -> dict[str, Any]:
    item = serialize_model(datasource, DATASOURCE_DETAIL_FIELDS)
    item["has_token"] = bool(getattr(datasource, "token", ""))
    return item


def _serialize_space_datasource(space_datasource: models.SpaceDataSource) -> dict[str, Any]:
    item = serialize_model(
        space_datasource,
        ["space_type_id", "space_id", "bk_tenant_id", "bk_data_id", "from_authorization"],
    )
    item["space_uid"] = f"{space_datasource.space_type_id}__{space_datasource.space_id}"
    return item


def _serialize_datasource_result_table(relation: models.DataSourceResultTable) -> dict[str, Any]:
    return serialize_model(relation, ["bk_data_id", "table_id", "bk_tenant_id", "creator", "create_time"])


def _serialize_result_table(result_table: models.ResultTable) -> dict[str, Any]:
    return serialize_model(
        result_table,
        [
            "table_id",
            "bk_tenant_id",
            "table_name_zh",
            "bk_biz_id",
            "data_label",
            "default_storage",
            "is_enable",
            "is_deleted",
        ],
    )


def _serialize_data_id_config(data_id_config: models.DataIdConfig) -> dict[str, Any]:
    return {
        "namespace": data_id_config.namespace,
        "kind": data_id_config.kind,
        "name": data_id_config.name,
        "bk_data_id": data_id_config.bk_data_id,
        "bk_tenant_id": data_id_config.bk_tenant_id,
        "created_at": serialize_value(data_id_config.create_time),
        "updated_at": serialize_value(data_id_config.last_modify_time),
    }


def _serialize_kafka_cluster(cluster: models.ClusterInfo | None) -> dict[str, Any] | None:
    if cluster is None:
        return None
    return serialize_model(cluster, KAFKA_CLUSTER_FIELDS)


def _serialize_kafka_topic(topic: models.KafkaTopicInfo | None) -> dict[str, Any] | None:
    if topic is None:
        return None
    return serialize_model(topic, KAFKA_TOPIC_FIELDS)


def _get_kafka_topic(datasource: models.DataSource) -> models.KafkaTopicInfo | None:
    topic = models.KafkaTopicInfo.objects.filter(id=datasource.mq_config_id).first()
    if topic is not None:
        return topic
    return models.KafkaTopicInfo.objects.filter(bk_data_id=datasource.bk_data_id).first()


def _build_datasource_queryset(params: dict[str, Any], bk_tenant_id: str):
    queryset = models.DataSource.objects.filter(bk_tenant_id=bk_tenant_id)

    if params.get("bk_data_id") not in (None, ""):
        queryset = queryset.filter(bk_data_id=_normalize_bk_data_id(params.get("bk_data_id")))
    if params.get("data_name"):
        queryset = queryset.filter(data_name__contains=str(params["data_name"]).strip())
    for field in ["created_from", "source_label", "type_label", "space_uid"]:
        if params.get(field) not in (None, ""):
            queryset = queryset.filter(**{field: params[field]})
    if params.get("mq_cluster_id") not in (None, ""):
        try:
            queryset = queryset.filter(mq_cluster_id=int(params["mq_cluster_id"]))
        except (TypeError, ValueError) as error:
            raise CustomException(message="mq_cluster_id 必须是整数") from error
    for field in ["is_enable", "is_custom_source", "is_platform_data_id"]:
        field_value = normalize_optional_bool(params.get(field), field)
        if field_value is not None:
            queryset = queryset.filter(**{field: field_value})
    if params.get("table_id"):
        bk_data_ids = models.DataSourceResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id=str(params["table_id"]).strip()
        ).values_list("bk_data_id", flat=True)
        queryset = queryset.filter(bk_data_id__in=bk_data_ids)

    return queryset


@KernelRPCRegistry.register(
    FUNC_DATASOURCE_LIST,
    summary="Admin 查询 DataSource 列表",
    description="只读查询 DataSource，支持受控过滤、白名单排序和分页；不会返回 token 明文。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "bk_data_id": "可选，数据源 ID",
        "data_name": "可选，数据源名称包含匹配",
        "created_from": "可选，数据源来源",
        "source_label": "可选，数据源标签",
        "type_label": "可选，数据类型标签",
        "is_enable": "可选，是否启用",
        "is_custom_source": "可选，是否自定义数据源",
        "is_platform_data_id": "可选，是否平台级 ID",
        "space_uid": "可选，所属空间 UID",
        "mq_cluster_id": "可选，Kafka 集群 ID 精确匹配",
        "table_id": "可选，通过 DataSourceResultTable 关联过滤",
        "page": "可选，默认 1",
        "page_size": "可选，默认 20，最大 100",
        "ordering": f"可选，白名单字段: {', '.join(sorted(ORDERING_FIELDS))}",
    },
    example_params={"bk_tenant_id": "system", "page": 1, "page_size": 20, "ordering": "-last_modify_time"},
)
def list_datasources(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    page, page_size = normalize_pagination(params)
    ordering = normalize_ordering(params.get("ordering"), ORDERING_FIELDS, default="-last_modify_time")

    queryset = _build_datasource_queryset(params, bk_tenant_id).order_by(ordering, "bk_data_id")
    datasources, total = paginate_queryset(queryset, page=page, page_size=page_size)

    bk_data_ids = [datasource.bk_data_id for datasource in datasources]
    result_table_count_map = count_by_field(
        models.DataSourceResultTable, group_field="bk_data_id", values=bk_data_ids, bk_tenant_id=bk_tenant_id
    )
    space_count_map = count_by_field(
        models.SpaceDataSource, group_field="bk_data_id", values=bk_data_ids, bk_tenant_id=bk_tenant_id
    )
    option_count_map = count_by_field(
        models.DataSourceOption, group_field="bk_data_id", values=bk_data_ids, bk_tenant_id=bk_tenant_id
    )
    data_id_config_ids = set(
        models.DataIdConfig.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=bk_data_ids).values_list(
            "bk_data_id", flat=True
        )
    )
    mq_cluster_ids = [datasource.mq_cluster_id for datasource in datasources]
    kafka_cluster_map = {
        cluster.cluster_id: cluster
        for cluster in models.ClusterInfo.objects.filter(
            bk_tenant_id=bk_tenant_id,
            cluster_id__in=mq_cluster_ids,
            cluster_type=models.ClusterInfo.TYPE_KAFKA,
        )
    }

    items = []
    for datasource in datasources:
        item = _serialize_datasource(datasource)
        item.update(
            {
                "result_table_count": result_table_count_map.get(datasource.bk_data_id, 0),
                "space_count": space_count_map.get(datasource.bk_data_id, 0),
                "option_count": option_count_map.get(datasource.bk_data_id, 0),
                "has_data_id_config": datasource.bk_data_id in data_id_config_ids,
                "kafka_cluster": _serialize_kafka_cluster(kafka_cluster_map.get(datasource.mq_cluster_id)),
            }
        )
        items.append(item)

    return build_response(
        operation="datasource.list",
        func_name=FUNC_DATASOURCE_LIST,
        bk_tenant_id=bk_tenant_id,
        data={"items": items, "page": page, "page_size": page_size, "total": total},
    )


@KernelRPCRegistry.register(
    FUNC_DATASOURCE_DETAIL,
    summary="Admin 查询 DataSource 详情",
    description="只读查询 DataSource 详情，include 支持 options、spaces、result_tables、data_id_config；不会返回 token 明文。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "bk_data_id": "必填，数据源 ID",
        "include": f"可选，展开范围: {', '.join(sorted(INCLUDE_VALUES))}",
    },
    example_params={"bk_tenant_id": "system", "bk_data_id": 50010, "include": ["spaces", "result_tables"]},
)
def get_datasource_detail(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    bk_data_id = _normalize_bk_data_id(params.get("bk_data_id"))
    includes = normalize_include(params.get("include"), INCLUDE_VALUES, default=DEFAULT_DETAIL_INCLUDE)
    warnings_list: list[dict[str, Any]] = []

    try:
        datasource = models.DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id)
    except models.DataSource.DoesNotExist as error:
        raise CustomException(message=f"未找到 DataSource: bk_data_id={bk_data_id}") from error

    kafka_cluster = models.ClusterInfo.objects.filter(
        bk_tenant_id=bk_tenant_id,
        cluster_id=datasource.mq_cluster_id,
        cluster_type=models.ClusterInfo.TYPE_KAFKA,
    ).first()
    kafka_topic = _get_kafka_topic(datasource)

    data: dict[str, Any] = {
        "datasource": _serialize_datasource_detail(datasource),
        "kafka_cluster": _serialize_kafka_cluster(kafka_cluster),
        "kafka_topic_config": _serialize_kafka_topic(kafka_topic),
    }

    if "options" in includes:
        data["options"] = [
            serialize_option(option)
            for option in models.DataSourceOption.objects.filter(
                bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id
            ).order_by("name")
        ]
    if "spaces" in includes:
        data["space_datasources"] = [
            _serialize_space_datasource(space_datasource)
            for space_datasource in models.SpaceDataSource.objects.filter(
                bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id
            ).order_by("space_type_id", "space_id")
        ]
    if "result_tables" in includes:
        relations = list(
            models.DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id).order_by(
                "table_id"
            )
        )
        table_ids = [relation.table_id for relation in relations]
        result_tables = models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids).order_by(
            "table_id"
        )
        data["data_source_result_tables"] = [_serialize_datasource_result_table(relation) for relation in relations]
        data["result_tables"] = [_serialize_result_table(result_table) for result_table in result_tables]
    if "data_id_config" in includes:
        data_id_configs_qs = models.DataIdConfig.objects.filter(
            Q(bk_tenant_id=bk_tenant_id), Q(bk_data_id=bk_data_id)
        ).order_by("namespace", "name")
        data["data_id_configs"] = [_serialize_data_id_config(cfg) for cfg in data_id_configs_qs]
    if "data_id_config_component_config" in includes:
        data_id_configs = list(
            models.DataIdConfig.objects.filter(Q(bk_tenant_id=bk_tenant_id), Q(bk_data_id=bk_data_id)).order_by(
                "namespace", "name"
            )
        )
        items = []
        for cfg in data_id_configs:
            item = _serialize_data_id_config(cfg)
            try:
                item["component_config"] = cfg.component_config
            except Exception:
                item["component_config"] = None
                warnings_list.append(
                    {
                        "code": "COMPONENT_CONFIG_UNAVAILABLE",
                        "message": (
                            f"component_config 获取失败: namespace={cfg.namespace}, kind={cfg.kind}, name={cfg.name}"
                        ),
                    }
                )
            items.append(item)
        data.setdefault("data_id_configs", items)

    return build_response(
        operation="datasource.detail",
        func_name=FUNC_DATASOURCE_DETAIL,
        bk_tenant_id=bk_tenant_id,
        data=data,
        warnings=warnings_list,
    )


@KernelRPCRegistry.register(
    FUNC_DATASOURCE_DATA_ID_CONFIG_COMPONENT_CONFIG,
    summary="Admin 查询单个 DataIdConfig 的 ComponentConfig",
    description="根据 bk_tenant_id、namespace、name 查询单个 DataIdConfig 的 component_config。",
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "namespace": "必填，数据链路命名空间",
        "name": "必填，数据源名称",
    },
    example_params={
        "bk_tenant_id": "system",
        "namespace": "bkmonitor",
        "name": "data-source-name",
    },
)
def get_data_id_config_component_config(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)

    namespace = params.get("namespace")
    if not namespace:
        raise CustomException(message="namespace 为必填项")
    name = params.get("name")
    if not name:
        raise CustomException(message="name 为必填项")

    from metadata.models.data_link.constants import DataLinkKind

    kind = DataLinkKind.DATAID.value

    try:
        cfg = models.DataIdConfig.objects.get(
            bk_tenant_id=bk_tenant_id,
            namespace=str(namespace).strip(),
            name=str(name).strip(),
        )
    except models.DataIdConfig.DoesNotExist as error:
        raise CustomException(message=f"未找到 DataIdConfig: namespace={namespace}, name={name}") from error

    try:
        component_config = cfg.component_config
    except Exception:
        component_config = None

    return build_response(
        operation="datasource.data_id_config.component_config",
        func_name=FUNC_DATASOURCE_DATA_ID_CONFIG_COMPONENT_CONFIG,
        bk_tenant_id=bk_tenant_id,
        data={
            "component_config": component_config,
            "namespace": namespace,
            "kind": kind,
            "name": name,
        },
    )
