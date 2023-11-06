# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime, timedelta

import pytz
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.action.duty_manage import DutyRuleManager
from bkmonitor.action.serializers import DutyRuleDetailSlz, PreviewSerializer
from bkmonitor.models import DutyRule, DutyRuleSnap
from bkmonitor.utils import time_tools
from constants.action import BKCHAT_TRIGGER_TYPE_MAPPING
from core.drf_resource import Resource, api


class GetBkchatGroupResource(Resource):
    """
    获取对应业务下的bkchat告警组列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        """
        返回示例：
        """
        groups = api.bkchat.get_notice_group_detail(biz_id=validated_request_data["bk_biz_id"])
        for group in groups:
            notice_way = BKCHAT_TRIGGER_TYPE_MAPPING.get(group['trigger_type'], group['trigger_type'])
            group["id"] = f"{notice_way}|{group['id']}"
            group["name"] = f"{group['name']}({group['trigger_name']})"
        return groups


class PreviewUserGroupPlanResource(Resource):
    # 预览某个组的排班情况

    def validate_request_data(self, request_data):
        """
        校验请求数据
        """
        request_data["resource_type"] = "user_group"
        preview_slz = PreviewSerializer(data=request_data)
        preview_slz.is_valid(raise_exception=True)
        request_data = preview_slz.validated_data
        user_group = request_data.pop("instance", None)
        if user_group:
            duty_rules = user_group.duty_rules
        else:
            duty_rules = request_data["config"]["duty_rules"]
        if not duty_rules:
            raise ValidationError(detail="duty_rules is empty")
        duty_rules = DutyRuleDetailSlz(instance=DutyRule.objects.filter(id__in=duty_rules), many=True).data
        request_data["duty_rules"] = duty_rules
        request_data["user_group"] = user_group
        return request_data

    def perform_request(self, validated_request_data):
        # 告警组的预览生成，需要包含已有的未有的
        if not validated_request_data.get("begin_time"):
            # 如果没有带begin_time， 直接用当前时间
            begin_datetime = datetime.now(tz=pytz.timezone(validated_request_data["timezone"]))
            begin_time = time_tools.datetime2str(begin_datetime)
        else:
            begin_time = validated_request_data["begin_time"]
            begin_datetime = time_tools.str2datetime(begin_time)
        end_time = time_tools.datetime2str(begin_datetime + timedelta(days=validated_request_data["days"]))
        user_group = validated_request_data["user_group"]
        duty_plans = defaultdict(list)
        origin_duty_plans = user_group.duty_plans if user_group else []
        for duty_rule in validated_request_data["duty_rules"]:
            # step1 找到当前规则的最后一次plan_time
            effective_time = begin_time
            if not user_group:
                duty_manager = DutyRuleManager(
                    duty_rule=duty_rule,
                    begin_time=effective_time,
                    end_time=end_time,
                )
                duty_plans[duty_rule["id"]] = duty_manager.get_duty_plan()
                continue
            if DutyRuleSnap.objects.filter(
                next_plan_time__gte=end_time, user_group_id=user_group.id, duty_rule_id=duty_rule["id"]
            ).exists():
                # 如果当前规则已经排到了结束时间，忽略
                continue
            # 找到最近一个排班过的
            latest_snap = (
                DutyRuleSnap.objects.filter(
                    next_plan_time__lt=end_time, user_group_id=user_group.id, duty_rule_id=duty_rule["id"]
                )
                .order_by("next_plan_time")
                .first()
            )
            if latest_snap:
                # 如果最后一个存在，则开始生效时间为最后一次的排班时间，生成这段时间内的即可
                effective_time = latest_snap.next_plan_time
            duty_manager = DutyRuleManager(
                duty_rule=duty_rule,
                begin_time=effective_time,
                end_time=end_time,
            )
            duty_plans[duty_rule["id"]] = duty_manager.get_duty_plan()

        for duty_plan in origin_duty_plans:
            if duty_plan.duty_rule_id in duty_plans:
                duty_plans[duty_plan.duty_rule_id].append(
                    {"users": duty_plan.users, "work_times": duty_plan.work_times}
                )
        response_plans = []
        for rule in validated_request_data["duty_rules"]:
            response_plans.append({"rule_id": rule["id"], "duty_plans": duty_plans.get(rule["id"], [])})
        return response_plans


class PreviewDutyRulePlanResource(Resource):
    """
    预览轮值排班计划
    """

    def validate_request_data(self, preview_data):
        """
        校验请求数据
        """
        preview_slz = PreviewSerializer(data=preview_data)
        preview_slz.is_valid(raise_exception=True)
        preview_data = preview_slz.validated_data
        duty_rule = preview_data.pop("instance", None)
        if duty_rule:
            # 如果预览内置对应的规则，直接返回DB数据
            validated_data = DutyRuleDetailSlz(instance=duty_rule).data
        else:
            preview_data["config"]["bk_biz_id"] = preview_data["bk_biz_id"]
            request_slz = DutyRuleDetailSlz(data=preview_data["config"])
            request_slz.is_valid(raise_exception=True)
            validated_data = request_slz.validated_data
        validated_data["timezone"] = preview_data["timezone"]
        validated_data["days"] = preview_data["days"]
        validated_data["begin_time"] = preview_data["begin_time"] or validated_data["effective_time"]

        return validated_data

    def perform_request(self, validated_request_data):
        duty_manager = DutyRuleManager(
            duty_rule=validated_request_data,
            begin_time=validated_request_data["begin_time"],
            days=validated_request_data["days"],
        )
        return duty_manager.get_duty_plan()
