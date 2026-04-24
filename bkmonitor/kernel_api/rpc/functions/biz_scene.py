"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from bkmonitor.utils.request import get_request_tenant_id
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from metadata import models
from metadata.models.space.constants import SpaceTypes
from metadata.models.space.utils import reformat_table_id

SCENE_LABELS = {
    "bcs": "容器监控",
    "apm": "APM",
    "plugin": "插件采集",
    "custom_metric": "自定义指标",
    "custom_event": "自定义事件",
    "uptimecheck": "拨测",
}

SCENE_ALIASES = {
    "bcs": "bcs",
    "k8s": "bcs",
    "apm": "apm",
    "plugin": "plugin",
    "plugins": "plugin",
    "collector_plugin": "plugin",
    "custom_metric": "custom_metric",
    "custom_metrics": "custom_metric",
    "time_series": "custom_metric",
    "custom_event": "custom_event",
    "custom_events": "custom_event",
    "event": "custom_event",
    "uptimecheck": "uptimecheck",
    "uptime_check": "uptimecheck",
    "uptime-check": "uptimecheck",
}

INVALID_DATA_ID_VALUES = {None, 0, -1}
INVALID_TABLE_ID_VALUES = {None, ""}
SPACE_VALUE_FIELDS = [
    "id",
    "space_type_id",
    "space_id",
    "space_name",
    "space_code",
    "status",
    "time_zone",
    "language",
    "is_bcs_valid",
    "is_global",
    "bk_tenant_id",
]


def _serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return value


def _get_bk_tenant_id(params: dict[str, Any]) -> str:
    return params.get("bk_tenant_id") or get_request_tenant_id(peaceful=True) or DEFAULT_TENANT_ID


def _normalize_bk_biz_id(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.lstrip("-").isdigit():
        return int(value)
    raise CustomException(message="bk_biz_id 必须是整数或整数字符串")


def _normalize_space_uid(value: Any) -> str:
    if value is None:
        return ""
    normalized_value = str(value).strip()
    if not normalized_value:
        return ""

    parts = normalized_value.split("__", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise CustomException(message="space_uid 格式不合法，应为 <space_type_id>__<space_id>")
    return normalized_value


def _build_space_payload(space_info: dict[str, Any]) -> dict[str, Any]:
    payload = {key: _serialize_value(value) for key, value in space_info.items()}
    payload["space_uid"] = f"{space_info['space_type_id']}__{space_info['space_id']}"
    payload["bk_biz_id"] = (
        int(space_info["space_id"]) if space_info["space_type_id"] == SpaceTypes.BKCC.value else -int(space_info["id"])
    )
    return payload


def _get_space_info_by_space_uid(bk_tenant_id: str, space_uid: str) -> dict[str, Any] | None:
    space_type_id, space_id = space_uid.split("__", 1)
    return (
        models.Space.objects.filter(
            bk_tenant_id=bk_tenant_id,
            space_type_id=space_type_id,
            space_id=space_id,
        )
        .values(*SPACE_VALUE_FIELDS)
        .first()
    )


def _get_space_info_by_bk_biz_id(bk_tenant_id: str, bk_biz_id: int) -> dict[str, Any] | None:
    queryset = models.Space.objects.filter(bk_tenant_id=bk_tenant_id)
    if bk_biz_id >= 0:
        queryset = queryset.filter(space_type_id=SpaceTypes.BKCC.value, space_id=str(bk_biz_id))
    else:
        queryset = queryset.filter(id=abs(bk_biz_id))
    return queryset.values(*SPACE_VALUE_FIELDS).first()


def _get_space_resources(bk_tenant_id: str, space_info: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not space_info:
        return []

    queryset = models.SpaceResource.objects.filter(
        bk_tenant_id=bk_tenant_id,
        space_type_id=space_info["space_type_id"],
        space_id=space_info["space_id"],
    ).values(
        "space_type_id",
        "space_id",
        "bk_tenant_id",
        "resource_type",
        "resource_id",
        "dimension_values",
    )
    return [{key: _serialize_value(value) for key, value in item.items()} for item in queryset]


def _resolve_space_scope(
    bk_tenant_id: str,
    raw_bk_biz_id: Any,
    raw_space_uid: Any,
) -> tuple[int, str, dict[str, Any] | None, list[dict[str, Any]]]:
    bk_biz_id = _normalize_bk_biz_id(raw_bk_biz_id) if raw_bk_biz_id is not None else None
    space_uid = _normalize_space_uid(raw_space_uid)

    if bk_biz_id is None and not space_uid:
        raise CustomException(message="bk_biz_id 或 space_uid 至少需要提供一个")

    space_info = None
    if space_uid:
        space_info = _get_space_info_by_space_uid(bk_tenant_id, space_uid)
        if not space_info:
            raise CustomException(message=f"space_uid 对应的空间不存在: {space_uid}")

        resolved_space = _build_space_payload(space_info)
        if bk_biz_id is not None and bk_biz_id != resolved_space["bk_biz_id"]:
            raise CustomException(
                message=(
                    f"bk_biz_id={bk_biz_id} 与 space_uid={space_uid} 指向的空间不一致，"
                    f"space_uid 实际对应 bk_biz_id={resolved_space['bk_biz_id']}"
                )
            )
        bk_biz_id = resolved_space["bk_biz_id"]
    else:
        bk_biz_id = bk_biz_id or 0
        space_info = _get_space_info_by_bk_biz_id(bk_tenant_id, bk_biz_id)
        if space_info:
            space_uid = f"{space_info['space_type_id']}__{space_info['space_id']}"
        elif bk_biz_id >= 0:
            space_uid = f"{SpaceTypes.BKCC.value}__{bk_biz_id}"

    space = _build_space_payload(space_info) if space_info else None
    space_resources = _get_space_resources(bk_tenant_id, space_info)
    return bk_biz_id or 0, space_uid, space, space_resources


def _normalize_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = value.split(",")
    elif isinstance(value, list | tuple | set):
        raw_values = list(value)
    else:
        raise CustomException(message=f"{field_name} 必须是字符串、列表、元组或集合")

    normalized_values: list[str] = []
    for item in raw_values:
        if item is None:
            continue
        if not isinstance(item, str):
            item = str(item)
        normalized_values.extend([part.strip() for part in item.split(",") if part and part.strip()])
    return sorted(set(normalized_values))


def _normalize_scene_name(value: Any) -> str:
    raw_scenes = _normalize_string_list(value, "scene")
    if not raw_scenes:
        raise CustomException(message="scene 为必填项")
    if len(raw_scenes) != 1:
        raise CustomException(message="scene 目前只支持传入单个场景")

    scene_name = raw_scenes[0].lower()
    normalized_scene = SCENE_ALIASES.get(scene_name)
    if not normalized_scene:
        raise CustomException(message=f"暂不支持的 scene: {raw_scenes[0]}")

    return normalized_scene


def _normalize_data_ids(values: Iterable[Any]) -> list[int]:
    normalized_values: set[int] = set()
    for value in values:
        if value in INVALID_DATA_ID_VALUES:
            continue
        if isinstance(value, int):
            normalized_values.add(value)
            continue
        if isinstance(value, str) and value.isdigit():
            normalized_values.add(int(value))
    return sorted(normalized_values)


def _normalize_table_ids(values: Iterable[Any]) -> list[str]:
    normalized_values: set[str] = set()
    for value in values:
        if value in INVALID_TABLE_ID_VALUES:
            continue
        normalized_values.add(reformat_table_id(str(value)))
    return sorted(normalized_values)


def _build_dsrt_table_ids_map(bk_tenant_id: str, bk_data_ids: list[int]) -> dict[int, list[str]]:
    if not bk_data_ids:
        return {}

    data_id_to_table_ids: dict[int, set[str]] = defaultdict(set)
    queryset = models.DataSourceResultTable.objects.filter(
        bk_tenant_id=bk_tenant_id, bk_data_id__in=bk_data_ids
    ).values("bk_data_id", "table_id")
    for item in queryset:
        data_id_to_table_ids[item["bk_data_id"]].add(reformat_table_id(item["table_id"]))

    return {bk_data_id: sorted(table_ids) for bk_data_id, table_ids in data_id_to_table_ids.items()}


def _build_scene_payload(scene_name: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "scene_name": scene_name,
        "scene_label": SCENE_LABELS[scene_name],
        "count": len(items),
        "items": items,
    }


def _build_data_source_basic_map(bk_tenant_id: str, bk_data_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not bk_data_ids:
        return {}

    queryset = models.DataSource.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id__in=bk_data_ids).values(
        "bk_data_id",
        "data_name",
    )
    return {item["bk_data_id"]: {key: _serialize_value(value) for key, value in item.items()} for item in queryset}


def _build_result_table_basic_map(bk_tenant_id: str, table_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not table_ids:
        return {}

    queryset = models.ResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id__in=table_ids).values(
        "table_id",
        "table_name_zh",
        "data_label",
    )
    return {
        reformat_table_id(item["table_id"]): {
            "table_id": reformat_table_id(item["table_id"]),
            "table_name": _serialize_value(item["table_name_zh"]),
            "data_label": _serialize_value(item["data_label"]),
        }
        for item in queryset
    }


def _build_related_basic_infos(bk_tenant_id: str, link_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_link_records: list[dict[str, Any]] = []
    all_bk_data_ids: set[int] = set()
    all_table_ids: set[str] = set()

    for record in link_records:
        normalized_data_ids = _normalize_data_ids([record.get("bk_data_id")])
        if not normalized_data_ids:
            continue
        normalized_bk_data_id = normalized_data_ids[0]
        table_ids = record.get("table_ids")
        if table_ids is None:
            table_ids = []
        normalized_table_ids = _normalize_table_ids(table_ids)

        normalized_record = {
            "type": record.get("type", ""),
            "bk_data_id": normalized_bk_data_id,
            "table_ids": normalized_table_ids,
        }
        normalized_link_records.append(normalized_record)
        all_bk_data_ids.add(normalized_bk_data_id)
        all_table_ids.update(normalized_table_ids)

    if not normalized_link_records:
        return []

    dsrt_table_ids_map = _build_dsrt_table_ids_map(bk_tenant_id, sorted(all_bk_data_ids))
    for record in normalized_link_records:
        if not record["table_ids"]:
            record["table_ids"] = dsrt_table_ids_map.get(record["bk_data_id"], [])
            all_table_ids.update(record["table_ids"])

    data_source_map = _build_data_source_basic_map(bk_tenant_id, sorted(all_bk_data_ids))
    result_table_map = _build_result_table_basic_map(bk_tenant_id, sorted(all_table_ids))

    results: list[dict[str, Any]] = []
    for record in normalized_link_records:
        data_source_info = data_source_map.get(record["bk_data_id"], {})
        if record["table_ids"]:
            for table_id in record["table_ids"]:
                result_table_info = result_table_map.get(
                    table_id,
                    {"table_id": table_id, "table_name": "", "data_label": ""},
                )
                results.append(
                    {
                        "type": record["type"],
                        "bk_data_id": record["bk_data_id"],
                        "data_name": data_source_info.get("data_name", ""),
                        "table_id": result_table_info["table_id"],
                        "table_name": result_table_info["table_name"],
                        "data_label": result_table_info["data_label"],
                    }
                )
        else:
            results.append(
                {
                    "type": record["type"],
                    "bk_data_id": record["bk_data_id"],
                    "data_name": data_source_info.get("data_name", ""),
                    "table_id": "",
                    "table_name": "",
                    "data_label": "",
                }
            )

    return results


def _collect_bcs_scene(bk_tenant_id: str, bk_biz_id: int) -> dict[str, Any]:
    cluster_queryset = models.BCSClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
    if bk_biz_id < 0:
        space_info = (
            models.Space.objects.filter(
                bk_tenant_id=bk_tenant_id,
                id=abs(bk_biz_id),
                space_type_id=SpaceTypes.BKCI.value,
            )
            .values("space_code")
            .first()
        )
        if not space_info or not space_info["space_code"]:
            cluster_queryset = models.BCSClusterInfo.objects.none()
        else:
            cluster_queryset = models.BCSClusterInfo.objects.filter(
                bk_tenant_id=bk_tenant_id,
                project_id=space_info["space_code"],
            )

    cluster_items = list(
        cluster_queryset.values(
            "cluster_id",
            "bcs_api_cluster_id",
            "bk_biz_id",
            "bk_tenant_id",
            "project_id",
            "status",
            "bk_cloud_id",
            "operator_ns",
            "bk_env",
            "K8sMetricDataID",
            "CustomMetricDataID",
            "K8sEventDataID",
            "CustomEventDataID",
            "is_deleted_allow_view",
        )
    )

    items: list[dict[str, Any]] = []
    for cluster in cluster_items:
        data_links = []

        for link_type, data_id in [
            ("k8s_metric", cluster["K8sMetricDataID"]),
            ("custom_metric", cluster["CustomMetricDataID"]),
            ("k8s_event", cluster["K8sEventDataID"]),
            ("custom_event", cluster["CustomEventDataID"]),
        ]:
            data_links.append({"type": link_type, "bk_data_id": data_id})

        item = {key: _serialize_value(value) for key, value in cluster.items()}
        item["related_infos"] = _build_related_basic_infos(bk_tenant_id, data_links)
        items.append(item)

    return _build_scene_payload("bcs", items)


def _collect_apm_scene(bk_tenant_id: str, bk_biz_id: int) -> dict[str, Any]:
    from apm.models import ApmApplication, LogDataSource, MetricDataSource, ProfileDataSource, TraceDataSource

    applications = list(
        ApmApplication.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id).values(
            "app_name",
            "app_alias",
            "description",
            "is_enabled",
            "is_enabled_trace",
            "is_enabled_metric",
            "is_enabled_log",
            "is_enabled_profiling",
            "bk_biz_id",
            "bk_tenant_id",
        )
    )

    datasource_items_by_app: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for datasource_type, model_class in [
        ("metric", MetricDataSource),
        ("trace", TraceDataSource),
        ("log", LogDataSource),
        ("profiling", ProfileDataSource),
    ]:
        queryset = model_class.objects.filter(bk_biz_id=bk_biz_id).values("app_name", "bk_data_id", "result_table_id")
        for item in queryset:
            datasource_items_by_app[item["app_name"]].append(
                {
                    "type": datasource_type,
                    "bk_data_id": _normalize_data_ids([item["bk_data_id"]])[0]
                    if item["bk_data_id"] not in INVALID_DATA_ID_VALUES
                    else None,
                    "table_id": reformat_table_id(item["result_table_id"]) if item["result_table_id"] else "",
                }
            )

    items: list[dict[str, Any]] = []
    for application in applications:
        datasource_items = datasource_items_by_app.get(application["app_name"], [])
        item = {key: _serialize_value(value) for key, value in application.items()}
        item["related_infos"] = _build_related_basic_infos(
            bk_tenant_id,
            [
                {"type": data["type"], "bk_data_id": data["bk_data_id"], "table_ids": [data["table_id"]]}
                for data in datasource_items
            ],
        )
        items.append(item)

    return _build_scene_payload("apm", items)


def _collect_plugin_scene(bk_tenant_id: str, bk_biz_id: int) -> dict[str, Any]:
    from monitor_web.constants import EVENT_TYPE
    from monitor_web.models import CollectConfigMeta, CollectorPluginMeta, CustomEventGroup
    from monitor_web.plugin.constant import PluginType

    plugins = list(
        CollectorPluginMeta.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id).values(
            "plugin_id", "plugin_type", "tag", "label", "is_internal", "bk_biz_id", "bk_tenant_id"
        )
    )
    process_plugin = (
        CollectorPluginMeta.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=0,
            plugin_type=PluginType.PROCESS,
            plugin_id="bkprocessbeat",
        )
        .values("plugin_id", "plugin_type", "tag", "label", "is_internal", "bk_biz_id", "bk_tenant_id")
        .first()
    )
    if process_plugin:
        plugins.append(process_plugin)
    if not plugins:
        return _build_scene_payload("plugin", [])

    plugin_ids = [item["plugin_id"] for item in plugins]
    current_version_id_map = CollectorPluginMeta.fetch_id__current_version_id_map(bk_tenant_id, plugin_ids)

    from monitor_web.models import PluginVersionHistory

    version_infos = {
        item["plugin_id"]: item
        for item in PluginVersionHistory.objects.filter(id__in=list(current_version_id_map.values())).values(
            "plugin_id", "config_version", "info_version", "stage", "info__plugin_display_name"
        )
    }

    data_name_to_plugin: dict[str, dict[str, Any]] = {
        f"{item['plugin_type']}_{item['plugin_id']}".lower(): item
        for item in plugins
        if item["plugin_type"] not in [PluginType.K8S, PluginType.PROCESS, PluginType.LOG, PluginType.SNMP_TRAP]
    }
    datasource_records = list(
        models.DataSource.objects.filter(
            bk_tenant_id=bk_tenant_id, data_name__in=list(data_name_to_plugin.keys())
        ).values(
            "bk_data_id",
            "data_name",
            "is_enable",
            "is_platform_data_id",
            "created_from",
        )
    )

    plugin_datasources: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for datasource in datasource_records:
        plugin = data_name_to_plugin.get(datasource["data_name"])
        if plugin is None:
            continue
        plugin_id = plugin["plugin_id"]
        normalized_data_ids = _normalize_data_ids([datasource["bk_data_id"]])
        if not normalized_data_ids:
            continue
        normalized_data_id = normalized_data_ids[0]
        plugin_datasources[plugin_id].append(
            {
                "type": "metric",
                "bk_data_id": normalized_data_id,
                "table_ids": [],
            }
        )

    event_group_infos = {
        item["name"]: item
        for item in CustomEventGroup.objects.filter(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            type=EVENT_TYPE.KEYWORDS,
            name__in=[
                f"{plugin['plugin_type']}_{plugin['plugin_id']}"
                for plugin in plugins
                if plugin["plugin_type"] in [PluginType.LOG, PluginType.SNMP_TRAP]
            ],
        ).values("name", "bk_data_id", "table_id")
    }

    process_data_name_map = {
        f"{bk_biz_id}_custom_time_series_process_perf": "process_perf",
        f"{bk_biz_id}_custom_time_series_process_port": "process_port",
    }
    process_datasource_queryset = models.DataSource.objects.filter(
        bk_tenant_id=bk_tenant_id,
        data_name__in=list(process_data_name_map.keys()),
    ).values("bk_data_id", "data_name")
    process_related_infos = [
        {
            "type": process_data_name_map[item["data_name"]],
            "bk_data_id": item["bk_data_id"],
        }
        for item in process_datasource_queryset
    ]

    k8s_related_infos = []
    for cluster in models.BCSClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id).values(
        "K8sMetricDataID",
        "CustomMetricDataID",
        "K8sEventDataID",
        "CustomEventDataID",
    ):
        k8s_related_infos.extend(
            [
                {"type": "k8s_metric", "bk_data_id": cluster["K8sMetricDataID"]},
                {"type": "custom_metric", "bk_data_id": cluster["CustomMetricDataID"]},
                {"type": "k8s_event", "bk_data_id": cluster["K8sEventDataID"]},
                {"type": "custom_event", "bk_data_id": cluster["CustomEventDataID"]},
            ]
        )

    collect_configs_by_plugin: dict[str, list[dict[str, Any]]] = defaultdict(list)
    collect_config_queryset = CollectConfigMeta.objects.filter(
        bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, plugin_id__in=plugin_ids
    ).values(
        "id",
        "plugin_id",
        "name",
        "collect_type",
        "target_object_type",
        "last_operation",
        "operation_result",
        "label",
    )
    for config in collect_config_queryset:
        collect_configs_by_plugin[config["plugin_id"]].append(
            {key: _serialize_value(value) for key, value in config.items()}
        )

    items: list[dict[str, Any]] = []
    for plugin in plugins:
        plugin_id = plugin["plugin_id"]
        plugin_type = plugin["plugin_type"]
        if plugin_type in [PluginType.LOG, PluginType.SNMP_TRAP]:
            event_group_name = f"{plugin_type}_{plugin_id}"
            event_group_info = event_group_infos.get(event_group_name)
            datasource_items = []
            if event_group_info:
                datasource_items.append(
                    {
                        "type": "event",
                        "bk_data_id": event_group_info["bk_data_id"],
                        "table_ids": [event_group_info["table_id"]],
                    }
                )
        elif plugin_type == PluginType.PROCESS:
            datasource_items = process_related_infos
        elif plugin_type == PluginType.K8S:
            datasource_items = k8s_related_infos
        else:
            datasource_items = plugin_datasources.get(plugin_id, [])
        version_info = version_infos.get(plugin_id, {})
        item = {key: _serialize_value(value) for key, value in plugin.items()}
        item["plugin_display_name"] = version_info.get("info__plugin_display_name", "")
        item["version"] = {
            "config_version": version_info.get("config_version"),
            "info_version": version_info.get("info_version"),
            "stage": version_info.get("stage"),
        }
        item["collect_configs"] = collect_configs_by_plugin.get(plugin_id, [])
        item["related_infos"] = _build_related_basic_infos(bk_tenant_id, datasource_items)
        items.append(item)

    return _build_scene_payload("plugin", items)


def _collect_custom_metric_scene(bk_tenant_id: str, bk_biz_id: int) -> dict[str, Any]:
    from monitor_web.models import CustomTSTable

    queryset = CustomTSTable.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id).values(
        "time_series_group_id",
        "bk_data_id",
        "bk_biz_id",
        "bk_tenant_id",
        "name",
        "scenario",
        "table_id",
        "is_platform",
        "data_label",
        "protocol",
        "desc",
        "auto_discover",
    )
    items = []
    for item in queryset:
        payload = {key: _serialize_value(value) for key, value in item.items()}
        payload["related_infos"] = _build_related_basic_infos(
            bk_tenant_id,
            [{"type": "custom_metric", "bk_data_id": item["bk_data_id"], "table_ids": [item["table_id"]]}],
        )
        items.append(payload)

    return _build_scene_payload("custom_metric", items)


def _collect_custom_event_scene(bk_tenant_id: str, bk_biz_id: int) -> dict[str, Any]:
    from monitor_web.models import CustomEventGroup

    queryset = CustomEventGroup.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id).values(
        "bk_event_group_id",
        "bk_data_id",
        "bk_biz_id",
        "bk_tenant_id",
        "name",
        "scenario",
        "table_id",
        "type",
        "is_enable",
        "is_platform",
        "data_label",
    )
    items = []
    for item in queryset:
        payload = {key: _serialize_value(value) for key, value in item.items()}
        payload["related_infos"] = _build_related_basic_infos(
            bk_tenant_id,
            [{"type": "custom_event", "bk_data_id": item["bk_data_id"], "table_ids": [item["table_id"]]}],
        )
        items.append(payload)

    return _build_scene_payload("custom_event", items)


def _collect_uptimecheck_scene(bk_tenant_id: str, bk_biz_id: int) -> dict[str, Any]:
    from monitor.models import UptimeCheckTask

    task_queryset = UptimeCheckTask.objects.filter(bk_biz_id=bk_biz_id).values(
        "id",
        "name",
        "protocol",
        "status",
        "indepentent_dataid",
        "check_interval",
        "labels",
    )
    task_items = list(task_queryset)

    independent_protocols = sorted(
        {str(item["protocol"]).lower() for item in task_items if item["indepentent_dataid"] and item["protocol"]}
    )
    protocol_to_data_name = {protocol: f"uptimecheck_{protocol}_{bk_biz_id}" for protocol in independent_protocols}
    data_name_to_protocol = {value: key for key, value in protocol_to_data_name.items()}

    datasource_queryset = models.DataSource.objects.filter(
        bk_tenant_id=bk_tenant_id,
        data_name__in=list(protocol_to_data_name.values()),
    ).values("bk_data_id", "data_name")
    protocol_to_data_ids: dict[str, list[int]] = defaultdict(list)

    for item in datasource_queryset:
        protocol = data_name_to_protocol.get(item["data_name"])
        if not protocol:
            continue
        protocol_to_data_ids[protocol].extend(_normalize_data_ids([item["bk_data_id"]]))

    items: list[dict[str, Any]] = []
    for task in task_items:
        protocol = str(task["protocol"]).lower() if task["protocol"] else ""
        payload = {key: _serialize_value(value) for key, value in task.items()}
        if task["indepentent_dataid"]:
            payload["related_infos"] = _build_related_basic_infos(
                bk_tenant_id,
                [
                    {"type": protocol, "bk_data_id": bk_data_id}
                    for bk_data_id in _normalize_data_ids(protocol_to_data_ids.get(protocol, []))
                ],
            )
        else:
            payload["related_infos"] = []
        items.append(payload)

    return _build_scene_payload("uptimecheck", items)


@KernelRPCRegistry.register(
    "biz_scene_related_info",
    summary="按业务查询场景关联的数据链路信息",
    description=(
        "基于 bk_biz_id 或 space_uid 查询单个场景关联的基础数据链路信息，"
        "并补充当前空间及对应 SpaceResource 信息。"
        "推荐使用 scene 参数，当前可选值为 bcs、apm、plugin、custom_metric、custom_event、uptimecheck。"
        "同时兼容常见别名，例如 k8s -> bcs、plugins -> plugin、custom_metrics -> custom_metric、"
        "event -> custom_event、uptime_check -> uptimecheck。"
    ),
    params_schema={
        "bk_biz_id": "可选，业务 ID；与 space_uid 至少提供一个",
        "space_uid": "可选，空间 UID；与 bk_biz_id 至少提供一个，若同时提供需指向同一空间",
        "bk_tenant_id": "可选，租户 ID；未传时优先从请求上下文获取，否则回退默认租户",
        "scene": (
            "必填，单个场景名。推荐值：bcs、apm、plugin、custom_metric、custom_event、uptimecheck。"
            "兼容别名：k8s、plugins、collector_plugin、custom_metrics、time_series、event、"
            "custom_events、uptime_check、uptime-check。"
        ),
    },
    example_params={"space_uid": "bkcc__2", "scene": "bcs"},
)
def get_biz_scene_related_info(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = _get_bk_tenant_id(params)
    bk_biz_id, space_uid, space, space_resources = _resolve_space_scope(
        bk_tenant_id=bk_tenant_id,
        raw_bk_biz_id=params.get("bk_biz_id"),
        raw_space_uid=params.get("space_uid"),
    )
    scene = _normalize_scene_name(params.get("scene"))

    scene_collectors = {
        "bcs": _collect_bcs_scene,
        "apm": _collect_apm_scene,
        "plugin": _collect_plugin_scene,
        "custom_metric": _collect_custom_metric_scene,
        "custom_event": _collect_custom_event_scene,
        "uptimecheck": _collect_uptimecheck_scene,
    }

    scene_payload = scene_collectors[scene](bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)

    return {
        "query": {
            "bk_biz_id": bk_biz_id,
            "space_uid": space_uid,
            "bk_tenant_id": bk_tenant_id,
            "scene": scene,
        },
        "space": space,
        "space_resources": space_resources,
        "scene": scene_payload,
    }
