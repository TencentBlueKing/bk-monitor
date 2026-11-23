"""告警配置的分页只读查询。"""

from copy import deepcopy
from dataclasses import dataclass
from functools import partial

from django.conf import settings
from django.db.models import Case, Q, When, Value
from rest_framework import serializers
from rest_framework.schemas.openapi import AutoSchema

from bk_dataview.redaction import redact_config
from bkm_space.api import SpaceApi
from bkmonitor.models import (
    ActionConfig,
    AlertAssignGroup,
    AlertAssignRule,
    DutyArrange,
    DutyRule,
    Shield,
    StrategyActionConfigRelation,
    StrategyModel,
    UserGroup,
)
from bkmonitor.utils import time_tools
from constants.shield import ShieldStatus
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import ResourceNotFound, build_response, paginate_queryset


@dataclass(frozen=True)
class Resource:
    label: str
    model: type
    title: str
    summary: tuple
    detail: tuple
    filters: dict


COMMON = ("id", "bk_biz_id", "is_enabled", "update_user", "update_time")
AUDIT = ("create_user", "create_time")
RESOURCES = {
    "user_group": Resource(
        "用户组",
        UserGroup,
        "name",
        ("timezone", "need_duty", "source"),
        (
            "desc",
            "channels",
            "mention_list",
            "mention_type",
            "alert_notice",
            "action_notice",
            "duty_notice",
            "webhook_action_id",
            "duty_rules",
            "app",
            "path",
        ),
        {"need_duty": serializers.BooleanField(required=False)},
    ),
    "assignment": Resource(
        "告警分派",
        AlertAssignGroup,
        "name",
        ("priority", "is_builtin", "source"),
        ("settings", "app", "path"),
        {"priority": serializers.IntegerField(required=False)},
    ),
    "shield": Resource(
        "告警屏蔽",
        Shield,
        "description",
        ("category", "scope_type", "status", "begin_time", "end_time"),
        (
            "source",
            "content",
            "failure_time",
            "dimension_config",
            "cycle_config",
            "notice_config",
            "label",
            "is_quick",
            "end_policy",
        ),
        {
            "category": serializers.ChoiceField(choices=Shield.SHIELD_CATEGORY, required=False),
            "status": serializers.ChoiceField(
                choices=(ShieldStatus.SHIELDED, ShieldStatus.EXPIRED, ShieldStatus.REMOVED), required=False
            ),
        },
    ),
    "action": Resource(
        "处理套餐",
        ActionConfig,
        "name",
        ("plugin_id", "is_builtin"),
        ("desc", "execute_config", "app", "path"),
        {"plugin_id": serializers.CharField(required=False)},
    ),
}


class Scope(serializers.Serializer):
    bk_tenant_id = serializers.CharField(required=False, help_text="省略时查询当前环境全部租户")
    bk_biz_id = serializers.IntegerField(required=False, help_text="业务或负空间 ID")


class Page(Scope):
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)


class Listing(Page):
    id = serializers.IntegerField(min_value=1, required=False)
    keyword = serializers.CharField(required=False, allow_blank=True, help_text="名称或屏蔽原因包含匹配")
    is_enabled = serializers.BooleanField(required=False)


class Target(Scope):
    id = serializers.IntegerField(min_value=1)


class RelatedPage(Page):
    id = serializers.IntegerField(min_value=1)


def validate(serializer, params):
    unknown = params.keys() - serializer.fields.keys()
    if unknown:
        raise CustomException(message="不支持的参数：" + ", ".join(sorted(unknown)))
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def scoped(query, params, include_public=False):
    if include_public:
        # 用户态调用方已解析并鉴权当前租户的具体业务；用户组页面同时展示公共组。
        return query.filter(bk_biz_id__in=[0, params["bk_biz_id"]])
    tenant = params.get("bk_tenant_id")
    if settings.ENABLE_MULTI_TENANT_MODE and tenant and tenant != "__all__":
        spaces = SpaceApi.list_spaces(bk_tenant_id=tenant)
        query = query.filter(bk_biz_id__in=[space.bk_biz_id for space in spaces])
    if "bk_biz_id" in params:
        query = query.filter(bk_biz_id=params["bk_biz_id"])
    return query


def page_data(query, params):
    page, size = params["page"], params["page_size"]
    rows, total = paginate_queryset(query, page=page, page_size=size)
    return {"items": rows, "total": total, "page": page, "page_size": size}


def response(action, params, data):
    name = "alarm_config." + action
    return build_response(operation=name, func_name="admin." + name, bk_tenant_id=params.get("bk_tenant_id"), data=data)


def config_rows(spec, params, include_public=False):
    rows = scoped(spec.model.objects.all(), params, include_public)
    if spec.model is Shield:
        # 与 Shield.status 相同的状态定义，允许在分页前过滤。
        rows = rows.annotate(
            status=Case(
                When(is_enabled=False, then=Value(ShieldStatus.REMOVED)),
                When(end_time__lt=time_tools.now(), then=Value(ShieldStatus.EXPIRED)),
                default=Value(ShieldStatus.SHIELDED),
            )
        )
    return rows


def list_params(spec, **kwargs):
    serializer = Listing(**kwargs)
    serializer.fields.update(deepcopy(spec.filters))
    return serializer


def list_configs(kind, params, *, include_public=False):
    spec = RESOURCES[kind]
    p = validate(list_params(spec, data=params), params)
    query = config_rows(spec, p, include_public)
    for field in ("id", "is_enabled", *spec.filters):
        if field in p:
            query = query.filter(**{field: p[field]})
    if p.get("keyword"):
        query = query.filter(**{spec.title + "__icontains": p["keyword"]})
    rows = query.order_by("-id").values(*COMMON, spec.title, *spec.summary)
    return response(kind + "_list", p, page_data(rows, p))


def get_config(kind, params, *, include_public=False):
    spec = RESOURCES[kind]
    p = validate(Target(data=params), params)
    row = (
        config_rows(spec, p, include_public)
        .filter(id=p["id"])
        .values(*COMMON, spec.title, *spec.summary, *AUDIT, *spec.detail)
        .first()
    )
    if row is None:
        raise ResourceNotFound(message="当前查询范围内未找到" + spec.label)
    if kind == "action":
        row["execute_config"] = redact_config(row["execute_config"], "", [])
    return response(kind + "_detail", p, {"config": row})


def related(kind, params, *, include_public=False):
    p = validate(RelatedPage(data=params), params)
    parent_query = scoped(RESOURCES[kind].model.objects.all(), p, include_public).filter(id=p["id"])
    fields = ("id", "bk_biz_id", "duty_rules") if kind == "user_group" else ("id", "bk_biz_id")
    parent = parent_query.values(*fields).first()
    if parent is None:
        raise ResourceNotFound(message="当前查询范围内未找到" + RESOURCES[kind].label)
    if kind == "user_group":
        rules = DutyRule.objects.filter(id__in=parent["duty_rules"] or [], bk_biz_id__in=[0, parent["bk_biz_id"]])
        rows = (
            DutyArrange.objects.filter(
                Q(user_group_id=parent["id"]) | Q(duty_rule_id__in=rules.values("id"), user_group_id__isnull=True)
            )
            .order_by("order", "id")
            .values(
                "id",
                "user_group_id",
                "duty_rule_id",
                "work_time",
                "users",
                "duty_users",
                "group_type",
                "group_number",
                "need_rotation",
                "effective_time",
                "handoff_time",
                "duty_time",
                "order",
                "backups",
            )
        )
        action = "duty_arrange_list"
    elif kind == "assignment":
        rows = (
            AlertAssignRule.objects.filter(assign_group_id=parent["id"], bk_biz_id=parent["bk_biz_id"])
            .order_by("id")
            .values(
                "id",
                "bk_biz_id",
                "assign_group_id",
                "is_enabled",
                "user_groups",
                "user_type",
                "conditions",
                "actions",
                "alert_severity",
                "additional_tags",
                "event_source",
                "scenario",
            )
        )
        action = "assign_rule_list"
    else:
        strategies = scoped(StrategyModel.objects.all(), p)
        rows = (
            StrategyActionConfigRelation.objects.filter(config_id=parent["id"], strategy_id__in=strategies.values("id"))
            .order_by("strategy_id", "id")
            .values("id", "strategy_id", "relate_type", "signal", "user_groups", "user_type", "options", "is_enabled")
        )
        action = "strategy_binding_list"
    return response(action, p, page_data(rows, p))


def register(action, title, handler, serializer, example):
    KernelRPCRegistry.register_function(
        func_name="admin.alarm_config." + action,
        summary=title,
        description=title,
        handler=handler,
        params_schema={**AutoSchema().map_serializer(serializer), "additionalProperties": False},
        example_params=example,
    )


for key, resource in RESOURCES.items():
    register(
        key + "_list",
        "分页查询" + resource.label,
        partial(list_configs, key),
        list_params(resource),
        {"bk_biz_id": 2, "page": 1},
    )
    register(key + "_detail", "读取" + resource.label + "配置", partial(get_config, key), Target(), {"id": 1})

for key, action, label in (
    ("user_group", "duty_arrange_list", "用户组成员与轮班"),
    ("assignment", "assign_rule_list", "组内分派规则"),
    ("action", "strategy_binding_list", "套餐绑定的策略"),
):
    register(action, "分页查询" + label, partial(related, key), RelatedPage(), {"id": 1, "page": 1})
