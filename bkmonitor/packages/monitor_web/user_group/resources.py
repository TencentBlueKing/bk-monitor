from collections import defaultdict
from datetime import datetime, timedelta

import pytz
from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.action.duty_manage import DutyRuleManager
from bkmonitor.action.serializers import (
    DutyPlanSlz,
    DutyRuleDetailSlz,
    PreviewSerializer,
)
from bkmonitor.models import DutyRule, DutyRuleSnap, DutyArrange
from bkmonitor.utils import time_tools
from common.log import logger
from constants.action import BKCHAT_TRIGGER_TYPE_MAPPING
from core.drf_resource import Resource
from core.drf_resource.management.root import resource, api
from bkmonitor.utils.common_utils import count_md5


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
            notice_way = BKCHAT_TRIGGER_TYPE_MAPPING.get(group["trigger_type"], group["trigger_type"])
            group["id"] = f"{notice_way}|{group['id']}"
            group["name"] = f"{group['name']}({group['trigger_name']})"
        return groups


class DutyPlanUserTranslaterResource(Resource):
    def __init__(self, context=None):
        self.all_group_users = defaultdict(dict)
        self.user_list = {}
        super().__init__(context)

    def get_all_plan_users(self, duty_plans):
        """
        转换用户组的显示名称
        """
        all_members = []
        for duty_plan in duty_plans:
            all_members.extend([user["id"] for user in duty_plan["users"] if user["type"] == "user"])
        try:
            self.user_list = {
                user["username"]: user["display_name"]
                for user in api.bk_login.get_all_user(
                    page_size=500, fields="username,display_name", exact_lookups=",".join(sorted(set(all_members)))
                )["results"]
            }
        except Exception as error:
            logger.info(f"query list users error {str(error)}")

        self.all_group_users = DutyPlanSlz.get_all_recievers()

    def translate_user_display(self, duty_plan):
        """对轮值用户进行翻译"""
        return DutyPlanSlz.translate_user_display(duty_plan["users"], self.all_group_users, self.user_list)


class PreviewUserGroupPlanResource(DutyPlanUserTranslaterResource):
    """
    预览某个组的排班情况
    """

    def validate_request_data(self, request_data):
        """
        校验请求数据
        """
        request_data["resource_type"] = "user_group"
        preview_slz = PreviewSerializer(data=request_data)
        preview_slz.is_valid(raise_exception=True)
        request_data = preview_slz.validated_data
        user_group = request_data.pop("instance", None)
        if request_data["source_type"] == PreviewSerializer.SourceType.DB:
            # 如果从DB获取配置，通过DB获取信息
            duty_rule_ids = user_group.duty_rules
        else:
            duty_rule_ids = request_data["config"]["duty_rules"]
        if not duty_rule_ids:
            raise ValidationError(detail="duty_rules is empty")
        duty_rules = DutyRuleDetailSlz(instance=DutyRule.objects.filter(id__in=duty_rule_ids), many=True).data
        request_data["duty_rules"] = duty_rules
        request_data["duty_rule_ids"] = duty_rule_ids
        request_data["user_group"] = user_group
        return request_data

    def perform_request(self, validated_request_data):
        """
        预览逻辑实现
        """
        # 告警组的预览生成，需要包含已有的未有的
        if not validated_request_data.get("begin_time"):
            # 如果没有带begin_time， 直接用当前时间
            begin_datetime = datetime.now(tz=pytz.timezone(validated_request_data["timezone"]))
            begin_time = time_tools.datetime2str(begin_datetime)
        else:
            begin_time = validated_request_data["begin_time"]
            begin_datetime = time_tools.str2datetime(begin_time)
            begin_time = time_tools.datetime2str(begin_datetime)
        preview_end_time = time_tools.datetime2str(begin_datetime + timedelta(days=validated_request_data["days"]))
        user_group = validated_request_data["user_group"]
        duty_plans = defaultdict(list)
        origin_duty_plans = user_group.duty_plans if user_group else []
        for duty_rule in validated_request_data["duty_rules"]:
            # step1 找到当前规则的最后一次plan_time
            if not user_group:
                # 如果不是通过内部保存内容预览，直接生成
                # 通过该方法，刷新 duty_rule.duty_arranges 的生效时间（begin_time）
                # 问题： 按周排班， 此时刷新的生效时间不是当前， 而是下一周起始时间。当前到下周内无排班计划
                # 1. 先拿当周排班计划
                plans = []
                _manager = DutyRuleManager.refresh_duty_rule_from_any_begin_time(duty_rule, begin_time)
                if _manager:
                    plans = _manager.get_last_duty_plans()

                duty_plans[duty_rule["id"]] = plans
                # 2. 再拿未来排班计划
                # 基于刷新后的生效时间，获取轮值计划预览
                duty_manager = DutyRuleManager(duty_rule=duty_rule, begin_time=begin_time, end_time=preview_end_time)
                duty_plans[duty_rule["id"]] += duty_manager.get_duty_plan()
                continue

            # 获取那些未排班时间与预览时间有重叠的快照
            snaps = DutyRuleSnap.objects.filter(
                Q(end_time__gte=begin_time) | Q(end_time__isnull=True) | Q(end_time=""),
                next_plan_time__lte=preview_end_time,
                user_group_id=user_group.id,
                duty_rule_id=duty_rule["id"],
            )

            # 完成预览时间段内未完成的排班
            # 注意 get_duty_plan 返回的计划没有精确限制开始和结束的时间
            for snap in snaps:
                duty_manager = DutyRuleManager(
                    duty_rule=snap.rule_snap,
                    begin_time=snap.next_plan_time,
                    end_time=preview_end_time,
                    snap_end_time=snap.end_time,
                    last_user_index=snap.next_user_index,
                )
                duty_plans[duty_rule["id"]].extend(duty_manager.get_duty_plan())

        for duty_plan in origin_duty_plans:
            duty_plans[duty_plan.duty_rule_id].append(
                {
                    "users": duty_plan.users,
                    "id": duty_plan.id,
                    "user_index": duty_plan.user_index,
                    "order": duty_plan.order,
                    "work_times": duty_plan.work_times,
                }
            )
        all_duty_plans = []
        for _, plans in duty_plans.items():
            all_duty_plans.extend(plans)
        self.get_all_plan_users(all_duty_plans)
        response_plans = []
        for rule_id in validated_request_data["duty_rule_ids"]:
            rule_duty_plans = duty_plans.get(rule_id, [])
            for duty_plan in rule_duty_plans:
                duty_plan["users"] = self.translate_user_display(duty_plan)
            response_plans.append({"rule_id": rule_id, "duty_plans": rule_duty_plans})
        return response_plans


class PreviewDutyRulePlanResource(DutyPlanUserTranslaterResource):
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
        if preview_data["source_type"] == PreviewSerializer.SourceType.DB:
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
        begin_time = validated_data["begin_time"]
        begin_datetime = time_tools.str2datetime(begin_time)
        validated_data["begin_time"] = time_tools.datetime2str(begin_datetime)

        return validated_data

    def perform_request(self, validated_request_data):
        DutyRuleManager.refresh_duty_rule_from_any_begin_time(
            validated_request_data, validated_request_data["begin_time"]
        )
        duty_manager = DutyRuleManager(
            duty_rule=validated_request_data,
            begin_time=validated_request_data["begin_time"],
            days=validated_request_data["days"],
        )
        duty_plans = duty_manager.get_duty_plan()
        self.get_all_plan_users(duty_plans)
        for duty_plan in duty_plans:
            duty_plan["users"] = self.translate_user_display(duty_plan)
        return duty_plans


class UserGroupBulkUpdateResource(Resource):
    """
    批量更新告警组
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ids = []
        self.bk_biz_id = None
        self.edit_data = None

    class RequestSerializer(serializers.Serializer):
        ids = serializers.ListField(child=serializers.IntegerField())
        bk_biz_id = serializers.IntegerField()
        edit_data = serializers.DictField()

    def perform_request(self, validated_data):
        self.ids = validated_data["ids"]
        self.bk_biz_id = validated_data["bk_biz_id"]
        self.edit_data = validated_data["edit_data"]

        if not self.ids:
            return []

        append_keys = self.edit_data.get("append_keys", [])
        if append_keys:
            is_partial = True
        else:
            is_partial = False
            self.edit_data.pop("append_keys", None)
            append_keys = self.edit_data.keys()

        for key in append_keys:
            method = getattr(self, f"update_{key}", None)
            if method:
                method(partial=is_partial)
        return self.ids

    def update_users(self, partial):
        """
        批量更新直接通知人员
        """
        arranges = DutyArrange.objects.filter(user_group_id__in=self.ids)
        searched_user_group_ids = set()
        for arrange in arranges:
            if partial:
                arrange.users.extend(self.get_users_by_id())
            else:
                arrange.users = self.get_users_by_id()
            if not arrange.duty_rule_id:
                searched_user_group_ids.add(arrange.user_group_id)

            # 从新计算hash值
            hash_data = {
                "duty_users": arrange.duty_users,
                "users": arrange.users,
                "duty_time": arrange.duty_time,
                "group_type": arrange.group_type,
                "group_number": arrange.group_number,
            }
            arrange.hash = count_md5(hash_data)

        if len(searched_user_group_ids) != len(self.ids):
            raise ValidationError(
                f"配置了轮值的告警组不支持修改直接通知对象，告警组ID：{set(self.ids) - searched_user_group_ids}"
            )

        DutyArrange.objects.bulk_update(arranges, ["users", "hash"])

    def get_users_by_id(self) -> list[dict]:
        """
        :return  [ // 直接通知的用户，或者某个组
               {
                   "display_name": "hjt@testlocal.com",
                   "logo": "",
                   "id": "hjt@testlocal.com",
                   "type": "user"
               },
               {
                   "display_name": "运维人员",
                   "logo": "",
                   "id": "bk_biz_maintainer",
                   "type": "group",
                   "members": [
                       {
                           "id": "admin",
                           "display_name": "管理员"
                       },
                       {
                           "id": "study1_ex",
                           "display_name": "study1_ex"
                       }
                   ]
               }
           ]
        """

        receivers = []
        for rec in resource.notice_group.get_receiver(bk_biz_id=self.bk_biz_id):
            if "children" in rec:
                receivers.extend(rec["children"])
            else:
                receivers.append(rec)

        user_ids = set(self.edit_data["users"])
        result = []

        def build_user_info(users, is_receivers):
            for item in users:
                _id = item["id"] if is_receivers else item["username"]
                if _id in user_ids:
                    user = {
                        "id": _id,
                        "logo": item.get("logo", ""),
                        "display_name": item["display_name"],
                        "type": item["type"] if is_receivers else "user",
                    }
                    if "members" in item:
                        user["members"] = item["members"]
                    result.append(user)
                    user_ids.remove(_id)
                    if not user_ids:
                        break

        build_user_info(receivers, True)

        if not user_ids:
            return result

        # 查询剩余的用户信息
        user_list = api.bk_login.get_all_user(fields="username,display_name", exact_lookups=",".join(user_ids))[
            "results"
        ]
        build_user_info(user_list, False)

        if not user_ids:
            return result

        raise ValidationError(f"用户{user_ids} 不存在")
