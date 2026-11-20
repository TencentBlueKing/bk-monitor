"""共享小函数：批次只聚合结果和路由，不串联升级阶段。"""

import json

from django.conf import settings

from metadata import models
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.data_link_configs import DataIdConfig
from metadata.service.upgrade_v4.routes import ROUTE_MODES, refresh_routes


def require_single_tenant():
    if settings.ENABLE_MULTI_TENANT_MODE:
        raise ValueError("此模块仅用于单租户原地升级")


def set_option(table_id, name, value, *, bk_tenant_id="system"):
    models.ResultTableOption.objects.update_or_create(
        bk_tenant_id=bk_tenant_id,
        table_id=table_id,
        name=name,
        defaults={"value": json.dumps(value), "value_type": "bool", "creator": "system"},
    )


def set_source_options(source, options):
    for option in options:
        value = option["value"]
        value_type = option.get("value_type") or ("bool" if isinstance(value, bool) else "string")
        models.DataSourceOption.objects.update_or_create(
            bk_tenant_id=source.bk_tenant_id,
            bk_data_id=source.bk_data_id,
            name=option["name"],
            defaults={
                "value": json.dumps(value) if value_type != "string" else value,
                "value_type": value_type,
                "creator": "system",
            },
        )


def register_source(source, bk_biz_id, namespace="bkmonitor"):
    # 每次重试都重新 apply 同一已登记身份，恢复“名称已落库但远端注册失败”的状态。
    source.register_to_bkbase(bk_biz_id=bk_biz_id, namespace=namespace, update_created_from=False)


def changed(source, table_ids):
    return {
        "data_id": source.bk_data_id,
        "table_ids": list(table_ids),
        "spaces": list(
            models.SpaceDataSource.objects.filter(bk_tenant_id=source.bk_tenant_id, bk_data_id=source.bk_data_id)
            .values_list("space_type_id", "space_id")
            .distinct()
        ),
    }


def run_batch(items, migrate, *, route_refresh="rt_and_data_label", is_publish=True, bk_tenant_id="system"):
    require_single_tenant()
    if route_refresh not in ROUTE_MODES:
        raise ValueError(f"未知路由刷新模式: {route_refresh}")
    results = []
    for item in items:
        try:
            result = migrate(item)
            results.append({"item": item, "success": True, **result})
        except Exception as error:
            # 一项失败不阻止其余项；失败可能已写部分配置，重跑原参数续做。
            results.append({"item": item, "success": False, "error": str(error)})
    routing = refresh_routes(
        table_ids=[table for result in results if result["success"] for table in result.get("table_ids", [])],
        spaces=[space for result in results if result["success"] for space in result.get("spaces", [])],
        mode=route_refresh,
        is_publish=is_publish,
        bk_tenant_id=bk_tenant_id,
    )
    return {"results": results, "routes": routing}


def check_data_link(data_id, *, bk_tenant_id="system"):
    """单独查询所有已登记链路组件状态；不等待、不切换归属。"""
    components = list(DataIdConfig.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=data_id))
    links = list(models.DataLink.objects.filter(bk_tenant_id=bk_tenant_id, bk_data_id=data_id))
    for link in links:
        for model in link.get_related_component_classes():
            components.extend(
                model.objects.filter(
                    bk_tenant_id=bk_tenant_id, namespace=link.namespace, data_link_name=link.data_link_name
                )
            )
    statuses = []
    for component in components:
        statuses.append(
            {"name": component.name, "kind": type(component).__name__, "status": component.component_status}
        )
    return {"data_id": data_id, "links": [link.data_link_name for link in links], "components": statuses}


def finalize_transfer(data_ids, *, bk_tenant_id="system"):
    """调用者验收后显式交接；失败重入会继续清理，不因已为 BKDATA 而跳过。"""
    require_single_tenant()
    results = []
    for data_id in dict.fromkeys(data_ids):
        source = models.DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=data_id)
        source.created_from = DataIdCreatedFromSystem.BKDATA.value
        source.save(update_fields=["created_from"])
        source.delete_consul_config()
        results.append(data_id)
    return results
