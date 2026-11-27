from django.db.models import Q
from rest_framework import serializers

from bkmonitor.models.fta.plugin import EventPluginInstance, EventPluginV2
from kernel_api.rpc.functions.admin.space import tenant_business_ids

from .common import BusinessListPage, business_scope, db_page, query


class Plugins(BusinessListPage):
    plugin_id = serializers.CharField(required=False)
    version = serializers.CharField(required=False)
    keyword = serializers.CharField(required=False)
    status = serializers.CharField(required=False)


class Instances(BusinessListPage):
    plugin_id = serializers.CharField(required=False)
    version = serializers.CharField(required=False)
    instance_id = serializers.IntegerField(min_value=1, required=False)
    data_id = serializers.IntegerField(min_value=0, required=False)
    name = serializers.CharField(required=False)


def scoped_rows(model, p):
    if "bk_biz_id" in p and p["bk_biz_id"] != 0:
        business_scope(p)
    businesses = [p["bk_biz_id"]] if "bk_biz_id" in p else tenant_business_ids(p["bk_tenant_id"])
    return model.objects.filter(bk_biz_id__in=[0, *businesses])


@query("alarm_source.plugin_list", "查询告警源插件及已发布版本", Plugins)
def plugins(p):
    rows = scoped_rows(EventPluginV2, p)
    if "keyword" in p:
        rows = rows.filter(Q(plugin_display_name__icontains=p["keyword"]) | Q(plugin_id__icontains=p["keyword"]))
    rows = rows.filter(**{key: p[key] for key in ("plugin_id", "version", "status") if key in p})
    return db_page(
        rows.order_by("plugin_id", "-is_latest", "-id").values(
            "plugin_display_name",
            "plugin_id",
            "version",
            "is_latest",
            "plugin_type",
            "status",
            "bk_biz_id",
            "scenario",
            "tags",
            "summary",
            "author",
            "is_enabled",
            "update_time",
        ),
        p,
    )


@query("alarm_source.instance_list", "查询告警源接入实例及使用的插件版本", Instances)
def instances(p):
    rows = scoped_rows(EventPluginInstance, p)
    if "instance_id" in p:
        rows = rows.filter(pk=p["instance_id"])
    if "name" in p:
        rows = rows.filter(name__icontains=p["name"])
    rows = rows.filter(**{key: p[key] for key in ("plugin_id", "version", "data_id") if key in p})
    return db_page(
        rows.order_by("-id").values(
            "id",
            "name",
            "bk_biz_id",
            "plugin_id",
            "version",
            "data_id",
            "is_enabled",
            "create_time",
            "update_time",
        ),
        p,
    )


class InstanceDetail(BusinessListPage):
    instance_id = serializers.IntegerField(min_value=1)


@query(
    "alarm_source.instance_detail", "查询实例接收方式、配置参数名和清洗目标字段", InstanceDetail, {"instance_id": 17}
)
def instance_detail(p):
    rows = scoped_rows(EventPluginInstance, p).filter(pk=p["instance_id"])
    items, total = db_page(rows.order_by("id"), p)
    return [
        {
            "name": item.name,
            "id": item.pk,
            "bk_biz_id": item.bk_biz_id,
            "data_id": item.data_id,
            "version": item.version,
            "plugin_id": item.plugin_id,
            "is_enabled": item.is_enabled,
            "collect_type": item.collect_type,
            "config_fields": [v["field"] for v in item.config_params if v.get("field")],
            "normalization_fields": [v["field"] for v in item.normalization_config if v.get("field")],
            "clean_rule_count": len(item.clean_configs),
        }
        for item in items
    ], total


@query(
    "alarm_source.alert_config_list",
    "查询实例生效的插件公共及实例专属告警匹配规则",
    InstanceDetail,
    {"instance_id": 17},
)
def alert_configs(p):
    instance = scoped_rows(EventPluginInstance, p).filter(pk=p["instance_id"]).first()
    if instance is None:
        return [], 0
    return db_page(
        instance.list_alert_config().values(
            "id", "name", "plugin_id", "plugin_instance_id", "order", "is_manual", "is_enabled", "rules"
        ),
        p,
    )


class PluginVersion(BusinessListPage):
    plugin_id = serializers.CharField()
    version = serializers.CharField()


@query(
    "alarm_source.plugin_detail",
    "查看指定版本插件的接入参数与清洗字段",
    PluginVersion,
    {"plugin_id": "nightingale", "version": "1.0.2"},
)
def plugin_detail(p):
    rows = scoped_rows(EventPluginV2, p).filter(plugin_id=p["plugin_id"], version=p["version"])
    items, total = db_page(rows.order_by("id"), p)
    return [
        {
            "plugin_display_name": row.plugin_display_name,
            "plugin_id": row.plugin_id,
            "version": row.version,
            "config_fields": [v["field"] for v in row.config_params if v.get("field")],
            "normalization_fields": [v["field"] for v in row.normalization_config if v.get("field")],
            "clean_rule_count": len(row.clean_configs),
            "summary": row.summary,
            "description": row.description,
            "plugin_type": row.plugin_type,
            "status": row.status,
            "is_latest": row.is_latest,
        }
        for row in items
    ], total
