from django.db.models import Q
from rest_framework import serializers

from core.drf_resource.exceptions import CustomException
from .common import BusinessPage, db_page, list_page, query


class Applications(BusinessPage):
    keyword = serializers.CharField(required=False)


class AppPage(BusinessPage):
    app_name = serializers.CharField()


class Records(AppPage):
    mode = serializers.ChoiceField(choices=("session", "view", "span"), default="session")
    start_time = serializers.IntegerField(min_value=0)
    end_time = serializers.IntegerField(min_value=0)
    session_id = serializers.CharField(required=False)

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError("结束时间必须晚于开始时间")
        return attrs


def apps(p):
    from rum.models import RumApplication

    return RumApplication.objects.filter(bk_tenant_id=p["bk_tenant_id"], bk_biz_id=p["bk_biz_id"])


def app(p):
    current = apps(p).filter(app_name=p["app_name"]).only("id", "app_name", "bk_biz_id").first()
    if current is None:
        raise CustomException(message="当前租户和业务下未找到 RUM 应用")
    return current


@query("rum.application_list", "RUM 应用及启用状态", Applications)
def applications(p):
    rows = apps(p)
    if "keyword" in p:
        rows = rows.filter(Q(app_name__icontains=p["keyword"]) | Q(app_alias__icontains=p["keyword"]))
    return db_page(
        rows.order_by("id").values(
            "id",
            "bk_biz_id",
            "app_name",
            "app_alias",
            "description",
            "type",
            "is_enabled",
            "update_user",
            "update_time",
        ),
        p,
    )


@query("rum.datasource_list", "RUM 日志和时序数据源绑定", AppPage, {"app_name": "checkout"})
def datasources(p):
    from rum.models import MetricDataSource, RumDataSource

    current = app(p)
    key = {"bk_biz_id": current.bk_biz_id, "app_name": current.app_name}
    fields = ["id", "bk_data_id", "result_table_id"]
    sources = []
    for kind, model, extra in (
        ("rum", RumDataSource, ["index_set_id", "index_set_name"]),
        ("metric", MetricDataSource, ["time_series_group_id", "data_label"]),
    ):
        sources.extend(
            {**row, "kind": kind} for row in model.objects.filter(**key).order_by("id").values(*fields, *extra)
        )
    return list_page(sources, p)


@query("rum.config_list", "RUM 采样、Apdex 和限流配置", AppPage, {"app_name": "checkout"})
def configs(p):
    from rum.models import RumAppConfig

    current = app(p)
    rows = RumAppConfig.objects.filter(bk_biz_id=current.bk_biz_id, app_name=current.app_name)
    return db_page(rows.order_by("id").values("id", "config_type", "config_value", "scope_type", "scope_key"), p)


@query(
    "rum.record_list",
    "RUM 访问记录取证（Unix 秒）",
    Records,
    {"app_name": "checkout", "start_time": 1795300000, "end_time": 1795303600},
    safety="inspect",
)
def records(p):
    from bkmonitor.data_source.format import flatten_dict_data
    from rum_web.handlers.level.factory import RumLevelHandlerFactory
    from rum_web.models.application import Application
    from rum_web.query.resources import _build_data_sources

    current = app(p)
    mirror = Application.objects.filter(
        bk_biz_id=current.bk_biz_id,
        bk_tenant_id=p["bk_tenant_id"],
        application_id=current.id,
        app_name=current.app_name,
    ).first()
    if mirror is None:
        raise CustomException(message="该应用缺少 RUM SaaS 检索配置")
    handler = RumLevelHandlerFactory.create(p["mode"], _build_data_sources([mirror]))
    search = {key: p[key] for key in ("start_time", "end_time")}
    if "session_id" in p:
        search["filters"] = [{"key": "attributes.session.id", "operator": "equal", "value": [p["session_id"]]}]
    rows = handler.list_records(**search, offset=(p["page"] - 1) * p["page_size"], limit=p["page_size"])
    total = handler.total(**search)["total"]
    # 只展示定位记录需要的字段，不返回访问 URL 参数、HTTP 头、原始载荷。
    keys = (
        "trace_id",
        "span_id",
        "span_name",
        "start_time",
        "end_time",
        "duration",
        "time",
        "view_count",
        "action_count",
        "error_count",
        "web_vitals.lcp",
        "web_vitals.inp",
        "web_vitals.cls",
        "elapsed_time",
        "attributes.session.id",
        "attributes.view.id",
        "attributes.view.name",
        "status.code",
    )
    return [{k: v for k, v in flatten_dict_data(row).items() if k in keys} for row in rows], total
