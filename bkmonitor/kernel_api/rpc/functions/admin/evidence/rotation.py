from django.db.models import Q
from rest_framework import serializers

from bkmonitor.models import DutyArrange, DutyPlan, DutyRule, UserGroup
from calendars.models import CalendarItemModel, CalendarModel
from .common import BusinessPage, TenantPage, business_scope, db_page, query


class Rules(BusinessPage):
    name = serializers.CharField(required=False)
    rule_id = serializers.IntegerField(min_value=1, required=False)


class Arranges(BusinessPage):
    rule_id = serializers.IntegerField(min_value=1)


class Plans(BusinessPage):
    user_group_id = serializers.IntegerField(min_value=1)
    at = serializers.DateTimeField(
        input_formats=["%Y-%m-%d %H:%M:%S"], required=False, help_text="排班所在时区的本地时间"
    )


class Calendars(TenantPage):
    name = serializers.CharField(required=False)


class Items(TenantPage):
    calendar_id = serializers.IntegerField(min_value=1)


def rule_scope(p):
    business_scope(p)
    return DutyRule.objects.filter(bk_biz_id__in=[0, p["bk_biz_id"]])


@query("rotation.rule_list", "业务及平台公共轮值规则", Rules)
def rules(p):
    rows = rule_scope(p)
    if "rule_id" in p:
        rows = rows.filter(id=p["rule_id"])
    if "name" in p:
        rows = rows.filter(name__icontains=p["name"])
    return db_page(
        rows.order_by("id").values(
            "id",
            "name",
            "bk_biz_id",
            "category",
            "enabled",
            "effective_time",
            "end_time",
            "labels",
            "update_user",
            "update_time",
        ),
        p,
    )


@query("rotation.arrange_list", "轮值规则的班次与人员配置", Arranges, {"rule_id": 1})
def arranges(p):
    rows = DutyArrange.objects.filter(duty_rule_id__in=rule_scope(p).filter(id=p["rule_id"]).values("id"))
    return db_page(
        rows.order_by("order", "id").values(
            "id",
            "duty_rule_id",
            "order",
            "users",
            "duty_users",
            "group_type",
            "duty_time",
            "work_time",
            "handoff_time",
            "backups",
        ),
        p,
    )


@query("rotation.plan_list", "用户组已生成的值班计划", Plans, {"user_group_id": 1})
def plans(p):
    business_scope(p)
    groups = UserGroup.objects.filter(bk_biz_id=p["bk_biz_id"], id=p["user_group_id"])
    rows = DutyPlan.objects.filter(user_group_id__in=groups.values("id"), is_effective=1)
    at = p["at"].strftime("%Y-%m-%d %H:%M:%S") if p.get("at") else None
    if at:
        rows = rows.filter(
            Q(finished_time__gte=at) | Q(finished_time__isnull=True) | Q(finished_time=""), start_time__lte=at
        )
    page, total = db_page(rows.order_by("-start_time", "-id"), p)
    fields = (
        "id",
        "user_group_id",
        "duty_rule_id",
        "duty_arrange_id",
        "start_time",
        "finished_time",
        "timezone",
        "users",
        "work_times",
    )
    return [{**{k: getattr(row, k) for k in fields}, "on_duty": row.is_active_plan(at)} for row in page], total


@query("rotation.calendar_list", "租户日历", Calendars)
def calendars(p):
    rows = CalendarModel.objects.filter(bk_tenant_id=p["bk_tenant_id"])
    if "name" in p:
        rows = rows.filter(name__icontains=p["name"])
    return db_page(rows.order_by("id").values("id", "name", "classify", "update_user", "update_time"), p)


@query("rotation.calendar_item_list", "日历事项及重复规则", Items, {"calendar_id": 1})
def items(p):
    rows = CalendarItemModel.objects.filter(bk_tenant_id=p["bk_tenant_id"], calendar_id=p["calendar_id"])
    return db_page(
        rows.order_by("start_time", "id").values(
            "id",
            "name",
            "calendar_id",
            "parent_id",
            "start_time",
            "end_time",
            "repeat",
            "time_zone",
            "update_user",
            "update_time",
        ),
        p,
    )
