"""从业务资源解析数据源引用；只读，不调用会申请或修复数据源的接入方法。"""

from collections import defaultdict

from django.conf import settings

from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.views.resource_storage import QueryResourceStorageSerializer, matches_selector
from core.drf_resource import Resource, api
from monitor_web.models import CollectConfigMeta, CollectorPluginMeta, CustomEventGroup, CustomTSTable


def reference(scene, resource_id, name, status, data_type, **binding):
    return {
        "scene": scene,
        "resource_id": str(resource_id),
        "resource_name": name,
        "resource_status": status,
        "data_type": data_type,
        **binding,
    }


def collecting_references(bk_tenant_id, bk_biz_id, selectors):
    configs = list(
        CollectConfigMeta.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
        .select_related("deployment_config__plugin_version__info")
        .order_by("id")
    )
    plugins = {
        plugin.plugin_id: plugin
        for plugin in CollectorPluginMeta.objects.filter(
            bk_tenant_id=bk_tenant_id, plugin_id__in={config.plugin_id for config in configs}
        )
    }
    by_plugin = defaultdict(list)
    for config in configs:
        by_plugin[config.plugin_id].append(config)

    result = []
    for plugin_id, plugin_configs in by_plugin.items():
        plugin = plugins.get(plugin_id)
        for config in plugin_configs:
            plugin_type = plugin.plugin_type if plugin else config.collect_type
            is_special = plugin_type in CollectorPluginMeta.VIRTUAL_PLUGIN_TYPE
            scenes = ("plugin", "collect_config") if selectors else (("collect_config",) if is_special else ("plugin",))
            for scene in scenes:
                if scene == "plugin" and config != plugin_configs[0]:
                    continue
                version = config.deployment_config.plugin_version
                item = {
                    "scene": scene,
                    "resource_id": str(config.pk) if scene == "collect_config" else plugin_id,
                    "resource_name": config.name if scene == "collect_config" else version.info.plugin_display_name,
                    "resource_status": config.last_operation if scene == "collect_config" else "configured",
                    "expand_tables": True,
                }
                if not plugin:
                    result.append({**item, "data_type": "metric", "error": "采集项关联的插件不存在"})
                elif plugin_type == CollectorPluginMeta.PluginType.PROCESS:
                    for kind in ("perf", "port"):
                        # 与 ProcessPluginManager 的自定义上报数据名一致。
                        result.append(
                            {
                                **item,
                                "data_type": f"process_{kind}",
                                "data_name": f"{bk_biz_id}_custom_time_series_process_{kind}",
                            }
                        )
                elif plugin_type in (CollectorPluginMeta.PluginType.LOG, CollectorPluginMeta.PluginType.SNMP_TRAP):
                    result.append(
                        {
                            **item,
                            "data_type": "event",
                            "data_name": f"{plugin_type}_{plugin_id}_{plugin.bk_biz_id}",
                        }
                    )
                else:
                    result.append({**item, "data_type": "metric", "data_name": f"{plugin_type}_{plugin_id}".lower()})
    return result


def custom_references(bk_tenant_id, bk_biz_id, scene):
    model = CustomTSTable if scene == "custom_metric" else CustomEventGroup
    return [
        reference(
            scene,
            obj.pk,
            obj.name,
            "enabled" if getattr(obj, "is_enable", True) else "disabled",
            "metric" if scene == "custom_metric" else "event",
            bk_data_id=obj.bk_data_id if obj.bk_data_id > 0 else None,
            table_id=obj.table_id,
            expand_tables=scene == "custom_metric",
        )
        for obj in model.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
    ]


def uptime_references(bk_biz_id):
    # 新服务与旧页面模型指向同一个 monitor_uptimechecktask 表。
    from monitor.models import UptimeCheckTask

    result = []
    for task in UptimeCheckTask.objects.filter(bk_biz_id=bk_biz_id).only(
        "id", "name", "protocol", "status", "indepentent_dataid"
    ):
        protocol = task.protocol.lower()
        if task.indepentent_dataid:
            binding = {"data_name": f"uptimecheck_{protocol}_{bk_biz_id}"}
        else:
            binding = {"bk_data_id": getattr(settings, f"UPTIMECHECK_{protocol.upper()}_DATAID"), "is_builtin": True}
        result.append(
            reference("uptime_check", task.pk, task.name, task.status, protocol, expand_tables=True, **binding)
        )
    return result


def apm_references(bk_tenant_id, bk_biz_id):
    from apm.models import ApmApplication
    from apm.models.datasource import LogDataSource, MetricDataSource, ProfileDataSource, TraceDataSource

    applications = {
        app.app_name: app for app in ApmApplication.objects.filter(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
    }
    result = []
    for kind, model in (
        ("metric", MetricDataSource),
        ("trace", TraceDataSource),
        ("log", LogDataSource),
        ("profile", ProfileDataSource),
    ):
        # DataSource 模型没有租户列，通过已限定租户的业务和应用关联。
        sources = defaultdict(list)
        for source in model.objects.filter(bk_biz_id=bk_biz_id, app_name__in=applications):
            sources[source.app_name].append(source)
        for app in applications.values():
            enabled = app.is_enabled and getattr(
                app, "is_enabled_profiling" if kind == "profile" else f"is_enabled_{kind}"
            )
            if not enabled and not sources[app.app_name]:
                continue
            for source in sources[app.app_name] or [None]:
                binding = (
                    {
                        "bk_data_id": source.bk_data_id if source.bk_data_id > 0 else None,
                        "table_id": source.result_table_id,
                        "is_shared": source.is_shared,
                    }
                    if source
                    else {"error": "应用数据源尚未登记"}
                )
                result.append(
                    reference(
                        "apm",
                        app.app_name,
                        app.app_alias or app.app_name,
                        "enabled" if enabled else "disabled",
                        kind,
                        **binding,
                    )
                )
    return result


class QueryResourceStorageResource(Resource):
    """查询业务场景资源关联的数据源、结果表及存储。"""

    RequestSerializer = QueryResourceStorageSerializer

    def perform_request(self, validated_request_data):
        params = validated_request_data
        tenant = get_request_tenant_id()
        biz = params["bk_biz_id"]
        selectors = params["selectors"]
        scenes = {selector["scene"] for selector in selectors}
        references = []
        if not scenes or scenes & {"plugin", "collect_config"}:
            references.extend(collecting_references(tenant, biz, selectors))
        for scene in ("custom_metric", "custom_event"):
            if not scenes or scene in scenes:
                references.extend(custom_references(tenant, biz, scene))
        if not scenes or "uptime_check" in scenes:
            references.extend(uptime_references(biz))
        if not scenes or "apm" in scenes:
            references.extend(apm_references(tenant, biz))
        result = api.metadata.query_resource_storage(
            **params,
            bk_tenant_id=tenant,
            resources=[item for item in references if matches_selector(item, selectors)],
        )
        cluster_ids = {item["resource_id"] for item in result["items"] if item["scene"] == "bcs"}
        if cluster_ids:
            from bkmonitor.models import BCSCluster

            names = dict(
                BCSCluster.objects.filter(
                    bk_tenant_id=tenant, bk_biz_id=biz, bcs_cluster_id__in=cluster_ids
                ).values_list("bcs_cluster_id", "name")
            )
            for item in result["items"]:
                if item["scene"] == "bcs":
                    item["resource_name"] = names.get(item["resource_id"]) or item["resource_name"]
        return result
