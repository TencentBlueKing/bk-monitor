"""以指定用户身份读取一个显式业务空间中的产品配置。仅分派已登记的只读操作。"""

from bkmonitor.iam import ActionEnum, Permission
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin import alarm_config, apm, grafana
from kernel_api.rpc.functions.admin.common import ResourceNotFound, build_response, require_bk_tenant_id
from kernel_api.rpc.functions.admin.space import _apply_space_bk_biz_id_filter, _split_space_uid
from metadata.models import Space

# 每个入口只转交对应查询的产品参数。范围、实例授权条件由本函数提供。
OPERATIONS = {}


def group(prefix, action, endpoints):
    for endpoint, fields in endpoints.items():
        OPERATIONS[f"{prefix}.{endpoint}"] = (action, set(fields.split()))


group(
    "alarm_strategy",
    ActionEnum.VIEW_RULE,
    {"list": "strategy_id name scenario source is_enabled", "detail": "strategy_id"},
)
group(
    "alarm_config",
    ActionEnum.VIEW_RULE,
    {
        "assignment_list": "id keyword is_enabled priority",
        "assignment_detail": "id",
        "assign_rule_list": "id",
        "action_list": "id keyword is_enabled plugin_id",
        "action_detail": "id",
        "strategy_binding_list": "id",
    },
)
group(
    "alarm_config",
    ActionEnum.VIEW_NOTIFY_TEAM,
    {"user_group_list": "id keyword is_enabled need_duty", "user_group_detail": "id", "duty_arrange_list": "id"},
)
group(
    "alarm_config",
    ActionEnum.VIEW_DOWNTIME,
    {"shield_list": "id keyword is_enabled category status", "shield_detail": "id"},
)
group(
    "rotation",
    ActionEnum.VIEW_NOTIFY_TEAM,
    {"rule_list": "rule_id name", "arrange_list": "rule_id", "plan_list": "user_group_id at"},
)
group(
    "record_rule_v4",
    ActionEnum.VIEW_RECORDING_RULE,
    {"list": "name status", "detail": "id", "config": "id", "version_list": "id", "event_list": "id event_type"},
)
group(
    "uptime_check",
    ActionEnum.VIEW_SYNTHETIC,
    {
        "task_list": "name protocol status task_id",
        "task_detail": "task_id",
        "node_list": "name node_id",
        "node_detail": "node_id",
    },
)
group(
    "collect_config",
    ActionEnum.VIEW_COLLECTION,
    {
        "list": "name plugin_id id",
        "detail": "id",
        "version_list": "id",
        "version_detail": "id deployment_id",
        "target_status": "id diff",
    },
)
group(
    "collect_plugin",
    ActionEnum.VIEW_PLUGIN,
    {
        "list": "plugin_id plugin_type",
        "detail": "plugin_id",
        "version_list": "plugin_id stage",
        "version_detail": "plugin_id config_version info_version",
    },
)
group(
    "custom_report",
    ActionEnum.VIEW_CUSTOM_METRIC,
    {
        "list": "report_type group_name",
        "detail": "report_type group_id",
        "scope_list": "group_id",
        "metric_list": "group_id scope_id",
    },
)
group(
    "apm",
    ActionEnum.VIEW_APM_APPLICATION,
    {
        "application_list": "keyword",
        "application_detail": "application_id",
        "service_list": "application_id service_name kind",
        "topo": "application_id limit",
    },
)
group(
    "rum",
    ActionEnum.VIEW_RUM_APPLICATION,
    {"application_list": "keyword", "datasource_list": "app_name", "config_list": "app_name"},
)
group(
    "grafana",
    ActionEnum.VIEW_SINGLE_DASHBOARD,
    {"list": "keyword", "config": "dashboard_id version", "version_list": "dashboard_id"},
)
group("bcs_cluster", ActionEnum.VIEW_BUSINESS, {"detail": "cluster_id", "list": "cluster_id"})


PUBLIC_USER_GROUP_READS = {
    "alarm_config.user_group_list": alarm_config.list_configs,
    "alarm_config.user_group_detail": alarm_config.get_config,
    "alarm_config.duty_arrange_list": alarm_config.related,
}


def resolve_space(params, tenant):
    spaces = Space.objects.filter(bk_tenant_id=tenant)
    biz, uid = params.get("bk_biz_id"), params.get("space_uid")
    if biz is None and not uid:
        raise CustomException(message="必须指定 bk_biz_id 或 space_uid")
    if biz is not None:
        if type(biz) is not int or biz == 0:
            raise CustomException(message="请选择具体业务或空间")
        spaces = _apply_space_bk_biz_id_filter(spaces, biz)
    if uid:
        space_type, space_id = _split_space_uid(uid)
        spaces = spaces.filter(space_type_id=space_type, space_id=space_id)
    return spaces.first()


def application_data(name, params, permission, action):
    from rum.models import RumApplication

    is_apm = name.startswith("apm.")
    model = apm.apm_models.ApmApplication if is_apm else RumApplication
    apps = model.objects.filter(bk_tenant_id=params["bk_tenant_id"], bk_biz_id=params["bk_biz_id"])
    listing = name.endswith(".application_list")
    if not listing:
        apps = apps.filter(id=params["application_id"]) if is_apm else apps.filter(app_name=params["app_name"])
    keyword = params.get("keyword")
    if keyword:
        from django.db.models import Q

        apps = apps.filter(Q(app_name__icontains=keyword) | Q(app_alias__icontains=keyword))
    visible = permission.filter_visible_resource_ids(
        action,
        "apm_application" if is_apm else "rum_application",
        apps.values_list("id", flat=True),
        bk_biz_id=params["bk_biz_id"],
    )
    if not visible.all_granted:
        apps = apps.filter(id__in=visible.visible_ids)
    if listing or name == "apm.application_detail":
        fields = (
            ["id", "app_name", "app_alias", "bk_biz_id", "description"]
            if is_apm
            else ["id", "app_name", "app_alias", "bk_biz_id", "description", "type", "is_enabled"]
        )
        rows = apps.order_by("id").values(*fields)
        if is_apm:
            from django.db.models import F

            rows = apps.order_by("id").values(*fields[1:], application_id=F("id"))
        if not listing:
            row = rows.first()
            return {"application": row} if row else None
        return grafana._page(rows, params)
    if not apps.exists():
        return None
    return KernelRPCRegistry.execute("admin." + name, params)["data"]


def dashboard_data(name, p, permission):
    from bk_dataview.permissions import GrafanaRole
    from monitor_web.grafana.permissions import DashboardPermission

    rows = grafana._dashboards(p)
    if name != "grafana.list":
        rows = rows.filter(id=p["dashboard_id"])
    if not rows.exists():
        return grafana.dashboard_page(rows.none(), p) if name == "grafana.list" else None
    if not any(
        permission.is_allowed_by_biz(p["bk_biz_id"], action)
        for action in (ActionEnum.VIEW_DASHBOARD, ActionEnum.MANAGE_DASHBOARD, ActionEnum.MANAGE_DATASOURCE)
    ):
        role, permissions = DashboardPermission.get_visible_dashboards(
            permission.username, str(p["bk_biz_id"]), force_check=True, bk_tenant_id=permission.bk_tenant_id
        )
        if role < GrafanaRole.Viewer:
            rows = rows.filter(uid__in=permissions)
    if name == "grafana.list":
        return grafana.dashboard_page(rows, p)
    if name == "grafana.version_list":
        return grafana.list_versions(p, dashboards=rows)["data"]
    return grafana.get_config(p, dashboards=rows)["data"]


def read_config(name, params, space, permission, action):
    biz = space.get_bk_biz_id()
    p = {**params, "bk_biz_id": biz, "bk_tenant_id": permission.bk_tenant_id}
    if name.startswith(("apm.", "rum.", "grafana.")):
        if not permission.is_allowed_by_biz(biz, ActionEnum.VIEW_BUSINESS):
            return None
        if name.startswith("grafana."):
            return dashboard_data(name, p, permission)
        return application_data(name, p, permission, action)
    if name.startswith("custom_report."):
        report_type = p.get("report_type", "custom_metric")
        if report_type == "custom_event":
            action = ActionEnum.VIEW_CUSTOM_EVENT
        elif report_type != "custom_metric":
            raise CustomException(message="不支持该自定义上报类型")
    if not permission.is_allowed_by_biz(biz, action):
        if name != "uptime_check.task_list" or not permission.is_allowed_by_biz(biz, ActionEnum.VIEW_BUSINESS):
            return None
    if name.startswith("record_rule_v4."):
        p["space_uid"] = space.space_uid
    if name in PUBLIC_USER_GROUP_READS:
        return PUBLIC_USER_GROUP_READS[name]("user_group", p, include_public=True)["data"]
    if name == "bcs_cluster.detail":
        from kernel_api.rpc.functions.admin import bcs_cluster

        cluster = bcs_cluster.models.BCSClusterInfo.objects.filter(
            bk_tenant_id=permission.bk_tenant_id, bk_biz_id=biz, cluster_id=p["cluster_id"]
        ).first()
        return {"cluster": bcs_cluster._serialize_bcs_cluster(cluster)} if cluster else None
    response = KernelRPCRegistry.execute("admin." + name, p)
    if name == "collect_config.target_status" and response["warnings"]:
        # 管理接口用 warning 表示节点管理故障，不能把降级的空列表当成用户查询成功。
        raise CustomException(message="无法获取采集目标状态")
    return response["data"]


@KernelRPCRegistry.register(
    "admin.user_query",
    summary="按用户 IAM 查询业务配置",
    description="指定用户、租户、业务或空间和只读操作。列表按授权范围分页，越权不返回业务数据。",
    params_schema={
        "type": "object",
        "required": ["username", "bk_tenant_id", "operation", "query"],
        "anyOf": [{"required": ["bk_biz_id"]}, {"required": ["space_uid"]}],
        "properties": {
            "username": {"type": "string"},
            "bk_tenant_id": {"type": "string"},
            "bk_biz_id": {"type": "integer"},
            "space_uid": {"type": "string"},
            "operation": {"enum": sorted(OPERATIONS)},
            "query": {"type": "object"},
        },
    },
    example_params={
        "username": "alice",
        "bk_tenant_id": "system",
        "bk_biz_id": 2,
        "operation": "alarm_strategy.list",
        "query": {"page": 1},
    },
)
def user_query(params):
    tenant = require_bk_tenant_id(params)
    if tenant in ("*", "__all__"):
        raise CustomException(message="请选择具体租户")
    username = params.get("username")
    name = params.get("operation")
    if not isinstance(username, str) or not username.strip() or name not in OPERATIONS:
        raise CustomException(message="请提供用户和已登记的查询操作")
    action, fields = OPERATIONS[name]
    query = params.get("query", {})
    if name.endswith("list"):
        fields = fields | {"page", "page_size"}
    if not isinstance(query, dict) or query.keys() - fields:
        raise CustomException(message="不支持的查询参数")
    space = resolve_space(params, tenant)
    result = None
    if space and space.get_bk_biz_id() != 0:
        permission = Permission(username=username, bk_tenant_id=tenant)
        permission.skip_check = False
        try:
            result = read_config(name, query, space, permission, action)
        except ResourceNotFound:
            result = None
    return build_response(
        operation="user_query",
        func_name="admin.user_query",
        bk_tenant_id=tenant,
        data={"allowed": result is not None, "result": result},
    )
