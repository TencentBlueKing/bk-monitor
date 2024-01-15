# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from collections import defaultdict
from datetime import datetime
from typing import Dict

from django.utils.functional import cached_property
from django.utils.translation import ugettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import empty

from bkmonitor.action.serializers import AlertSerializer, ExecutionSerializer
from bkmonitor.action.utils import (
    get_user_group_assign_rules,
    get_user_group_strategies,
    validate_time_range,
)
from bkmonitor.models import (
    AlertAssignRule,
    DutyArrange,
    DutyArrangeSnap,
    DutyPlan,
    StrategyActionConfigRelation,
    UserGroup,
)
from common.log import logger
from constants.action import NoticeChannel
from constants.common import IsoWeekDay, MonthDay, RotationType
from core.drf_resource import api, resource


class DateTimeField(serializers.CharField):
    def run_validators(self, value):
        super(DateTimeField, self).run_validators(value)
        if value:
            try:
                datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                raise ValidationError(detail=_("当前输入非日期时间格式，请按格式[年-月-日 时:分:秒]填写"))


class HandOffSettingsSerializer(serializers.Serializer):
    rotation_type = serializers.ChoiceField(required=True, choices=RotationType.ROTATION_TYPE_CHOICE)
    date = serializers.IntegerField(required=False, label="交接日期")
    time = serializers.CharField(required=True, label="时间点")

    def to_internal_value(self, data):
        self.initial_data = data
        return super(HandOffSettingsSerializer, self).to_internal_value(data)

    def validate_date(self, value):
        if self.initial_data.get("rotation_type") == RotationType.WEEKLY and value not in set(
            IsoWeekDay.WEEK_DAY_RANGE
        ):
            raise ValidationError(detail=_("当前轮值类型为每周，选择的日期格式必须为星期一至星期日（1-7）"))
        if self.initial_data.get("rotation_type") == RotationType.MONTHLY and value not in set(
            MonthDay.MONTH_DAY_RANGE
        ):
            raise ValidationError(detail=_("当前轮值类型为每月，选择的日期格式必须为1-31之间"))
        return value

    def validate_time(self, value):
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError:
            raise ValidationError(detail=_("设置的交接时间不正确, 正确格式为00:00--23:59"))
        return value


class HandOffField(serializers.JSONField):
    def run_validators(self, value):
        super(HandOffField, self).run_validators(value)
        if value:
            handoff_slz = HandOffSettingsSerializer(data=value)
            handoff_slz.is_valid(raise_exception=True)


class UserSerializer(serializers.Serializer):
    id = serializers.CharField(required=True, label="通知对象ID")
    type = serializers.ChoiceField(required=True, choices=(("user", _("用户")), ("group", _("用户组"))), label="通知对象类别")


class ExcludeSettingsSerializer(serializers.Serializer):
    date = serializers.CharField(required=True, label="排除日期")
    time = serializers.CharField(required=True, label="时间段")

    def validate_time(self, value):
        if validate_time_range(value) is False:
            raise ValidationError(detail=_("设置的排除时间范围不正确, 正确格式为00:00--23:59"))
        return value

    def validate_date(self, value):
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise ValidationError(detail=_("删除代班日期格式不正确，请按照[年-月-日]填写"))
        return value


class DutyTimeSerializer(serializers.Serializer):
    work_type = serializers.ChoiceField(required=True, label="工作类型", choices=RotationType.ROTATION_TYPE_CHOICE)
    work_days = serializers.ListField(required=False, label="工作日期", child=serializers.IntegerField())
    work_time = serializers.CharField(required=True, label="工作时间")

    def to_internal_value(self, data):
        self.initial_data = data
        return super(DutyTimeSerializer, self).to_internal_value(data)

    def validate_work_days(self, value):
        value_set = set(value)
        if (
            self.initial_data.get("work_type") == RotationType.WEEKLY
            and value_set.intersection(set(IsoWeekDay.WEEK_DAY_RANGE)) != value_set
        ):
            raise ValidationError(detail=_("当前轮值类型为每周，选择的日期格式必须为星期一至星期日（1-7）"))

        if (
            self.initial_data.get("work_type") == RotationType.MONTHLY
            and value_set.intersection(set(MonthDay.MONTH_DAY_RANGE)) != value_set
        ):
            raise ValidationError(detail=_("当前轮值类型为每月，选择的日期格式必须为1-31之间"))
        return value

    def validate_work_time(self, value):
        if validate_time_range(value) is False:
            raise ValidationError(detail=_("设置的时间范围不正确, 正确格式为00:00--23:59"))
        return value


class BackupSerializer(serializers.Serializer):
    users = serializers.ListField(required=True, child=UserSerializer())
    begin_time = DateTimeField(label="配置生效时间", required=True)
    end_time = DateTimeField(label="配置生效时间", required=True)
    duty_time = DutyTimeSerializer(label="工作时间段", required=True)
    exclude_settings = serializers.ListField(label="被删除的代班", child=ExcludeSettingsSerializer())


class DutyBaseInfoSlz(serializers.ModelSerializer):
    def __init__(self, instance=None, data=empty, **kwargs):
        self.user_list = kwargs.pop("user_list", {})
        super(DutyBaseInfoSlz, self).__init__(instance, data, **kwargs)

    def __new__(cls, *args, **kwargs):
        duty_instances = args[0] if args else kwargs.get("instance", [])
        duty_instances = duty_instances or []
        if isinstance(duty_instances, (DutyPlan, DutyArrange)):
            duty_instances = [duty_instances]
        all_members = cls.get_all_members(duty_instances)
        if all_members:
            try:
                user_list = api.bk_login.get_all_user(
                    page_size=500, fields="username,display_name", exact_lookups=",".join(set(all_members))
                )["results"]
                kwargs["user_list"] = {user["username"]: user["display_name"] for user in user_list}
            except BaseException as error:
                logger.exception("query list users error %s" % str(error))
        return super(DutyBaseInfoSlz, cls).__new__(cls, *args, **kwargs)

    @classmethod
    def get_all_members(cls, instances):
        raise NotImplementedError("position NotImplementedError")

    @staticmethod
    def get_all_recievers() -> Dict[str, Dict[str, Dict]]:
        """
        获取用户组具体的用户
        """
        receivers: Dict[str, Dict[str, Dict]] = defaultdict(dict)
        for item in resource.notice_group.get_receiver():
            receiver_type = item["id"]
            for receiver in item["children"]:
                receivers[receiver_type][receiver["id"]] = receiver
        return receivers

    @staticmethod
    def translate_user_display(display_users, all_users, user_list):
        """
        前端用户信息转换
        """
        return_users = []
        all_users_id = []
        for user in display_users:
            user_type_id = "{}--{}".format(user["type"], user["id"])
            if user_type_id in all_users_id:
                continue
            all_users_id.append(user_type_id)
            user_info = all_users[user["type"]].get(
                user["id"],
                {
                    "id": user["id"],
                    "display_name": user["id"],
                    "type": user["type"],
                },
            )
            if user["type"] == "user":
                user_info["display_name"] = user_list.get(user["id"], user["id"])

            return_users.append(user_info)
        return return_users

    @cached_property
    def all_users(self) -> Dict[str, Dict[str, Dict]]:
        """
        接收人信息
        """
        return self.get_all_recievers()

    def users_representation(self, users):
        return self.translate_user_display(users, self.all_users, self.user_list)


class DutyArrangeSlz(DutyBaseInfoSlz):
    id = serializers.IntegerField(required=False)
    user_group_id = serializers.IntegerField(required=False)
    need_rotation = serializers.BooleanField(required=False, default=False)

    users = serializers.ListField(required=False, child=UserSerializer())
    duty_users = serializers.ListField(required=False, child=serializers.ListField(child=UserSerializer()))

    # 配置生效时间
    effective_time = serializers.DateTimeField(label="配置生效时间", required=False, allow_null=True)
    # handoff_time: {"date": 1, "time": "10:00"  } 根据rotation_type进行切换
    handoff_time = HandOffField(label="轮班交接时间安排", required=False)
    # duty_time: [{"work_type": "daily|month|week", "work_days":[1,2,3], "work_time"}]
    duty_time = serializers.ListField(label="轮班时间安排", required=False, child=DutyTimeSerializer())
    order = serializers.IntegerField(label="轮班组的顺序", default=0, required=False)
    """ backups: [{users:[],"begin_time":"2021-03-21 00:00",
    "end_time":"2021-03-25 00:00",
    "work_time": "10:00--18:00"
   "exclude_days": ["2021-03-21"]}]"""
    backups = serializers.ListField(label="备份安排", child=BackupSerializer(), required=False)

    class Meta:
        model = DutyArrange
        fields = (
            "id",
            "user_group_id",
            "need_rotation",
            "duty_time",
            "effective_time",
            "handoff_time",
            "users",
            "duty_users",
            "backups",
            "order",
        )

    @classmethod
    def get_all_members(cls, duty_arranges):
        all_members = []
        for duty_arrange in duty_arranges:
            all_members.extend([user["id"] for user in duty_arrange.users if user["type"] == "user"])
            all_members.extend(
                [user["id"] for users in duty_arrange.duty_users for user in users if user["type"] == "user"]
            )
        return all_members

    def to_representation(self, instance):
        data = super(DutyArrangeSlz, self).to_representation(instance)
        data["users"] = self.users_representation(data["users"])
        data["duty_users"] = self.duty_users_representation(data.get("duty_users", []))
        return data

    def duty_users_representation(self, duty_users):
        duty_users = [self.users_representation(users) for users in duty_users]
        return duty_users

    def to_internal_value(self, data):
        self.initial_data = data
        ret = super(DutyArrangeSlz, self).to_internal_value(data)
        return ret

    def validate_need_rotation(self, value):
        if value and not self.initial_data.get("handoff_time"):
            raise ValidationError(detail=_("需要交接的情况下，交接轮值方式与交接时间不能为空"))
        return value


class DutyPlanSlz(DutyBaseInfoSlz):
    class Meta:
        model = DutyPlan
        fields = (
            "id",
            "user_group_id",
            "duty_arrange_id",
            "duty_time",
            "begin_time",
            "end_time",
            "users",
            "order",
        )

    @classmethod
    def get_all_members(cls, duty_plans):
        all_members = []
        for duty_plan in duty_plans:
            all_members.extend([user["id"] for user in duty_plan.users if user["type"] == "user"])
        return all_members

    def to_representation(self, instance):
        data = super(DutyPlanSlz, self).to_representation(instance)
        data["is_active"] = instance.is_active_plan()
        data["users"] = self.users_representation(data["users"])
        return data


class UserGroupSlz(serializers.ModelSerializer):
    name = serializers.CharField(required=True)
    bk_biz_id = serializers.IntegerField(required=True)
    need_duty = serializers.BooleanField(required=False, default=False)
    channels = serializers.ListField(
        child=serializers.ChoiceField(choices=NoticeChannel.NOTICE_CHANNEL_CHOICE),
        required=False,
        default=NoticeChannel.DEFAULT_CHANNELS,
    )
    mention_list = serializers.ListField(child=UserSerializer(), required=False)
    desc = serializers.CharField(required=False, default="", allow_blank=True)

    class Meta:
        model = UserGroup
        fields = (
            "id",
            "name",
            "bk_biz_id",
            "need_duty",
            "channels",
            "desc",
            "update_user",
            "update_time",
            "create_user",
            "create_time",
            "mention_list",
            "mention_type",
            "app",
        )

    def __init__(self, instance=None, data=empty, **kwargs):
        self.group_user_mappings = kwargs.pop("group_user_mappings", {})
        self.strategy_count_of_given_type = kwargs.pop("strategy_count_of_given_type", {})
        self.strategy_count_of_all = kwargs.pop("strategy_count_of_all", {})
        self.rule_count = kwargs.pop("rule_count", {})
        super(UserGroupSlz, self).__init__(instance=instance, data=data, **kwargs)

    def __new__(cls, *args, **kwargs):
        request = kwargs.get("context", {}).get("request")
        if kwargs.get("many", False):
            # 带排除详细信息的接口不获取策略相关内容
            groups = args[0] if args else kwargs.get("instance", [])
            user_group_instance_mapping = {user_group.id: user_group for user_group in groups}
            user_group_ids = list(user_group_instance_mapping.keys())
            duty_plans = DutyPlan.objects.filter(user_group_id__in=user_group_ids, is_active=True).order_by("order")
            group_users_data = DutyPlanSlz(instance=duty_plans, many=True).data
            duty_arranges = DutyArrange.objects.filter(user_group_id__in=user_group_ids).order_by("order")
            group_users_without_duty = DutyArrangeSlz(instance=duty_arranges, many=True).data
            group_user_mappings = defaultdict(list)
            for item in group_users_data:
                group = user_group_instance_mapping.get(item["user_group_id"])
                if group.need_duty and item["is_active"]:
                    # 如果当前是轮值且当前轮值在生效中
                    for user in item["users"]:
                        if user in group_user_mappings[group.id]:
                            continue
                        group_user_mappings[group.id].append(user)
            for item in group_users_without_duty:
                group = user_group_instance_mapping.get(item["user_group_id"])
                if group.need_duty:
                    continue
                if not group_user_mappings[group.id]:
                    # 如果当前不轮值，直接返回第一组的信息
                    group_user_mappings[group.id].extend(item["users"])
            kwargs["group_user_mappings"] = group_user_mappings
            if not (request and request.query_params.get("exclude_detail_info", "0") != "0"):
                kwargs["strategy_count_of_all"] = get_user_group_strategies(user_group_ids)
                kwargs["rule_count"] = get_user_group_assign_rules(user_group_ids)
                kwargs["strategy_count_of_given_type"] = kwargs["strategy_count_of_all"]

        return super(UserGroupSlz, cls).__new__(cls, *args, **kwargs)

    def to_representation(self, instance):
        data = super(UserGroupSlz, self).to_representation(instance)
        data["users"] = self.group_user_mappings.get(instance.id, [])
        data["channels"] = data.get("channels") or NoticeChannel.DEFAULT_CHANNELS
        data["strategy_count"] = len(set(self.strategy_count_of_given_type.get(instance.id, [])))
        data["rules_count"] = len(set(self.rule_count.get(instance.id, [])))
        data["delete_allowed"] = (
            len(set(self.strategy_count_of_all.get(instance.id, []))) == 0
            and len(set(self.rule_count.get(instance.id, []))) == 0
        )
        data["edit_allowed"] = instance.bk_biz_id != 0
        data["config_source"] = "YAML" if instance.app else "UI"
        if data["mention_type"] == 0 and not data["mention_list"] and NoticeChannel.WX_BOT in data["channels"]:
            data["mention_list"] = [{"type": "group", "id": "all"}]
        return data


class UserGroupDetailSlz(UserGroupSlz):
    name = serializers.CharField(label="告警组名称", required=True)
    bk_biz_id = serializers.IntegerField(required=True)
    need_duty = serializers.BooleanField(required=False, default=False)
    desc = serializers.CharField(required=False, default="", allow_blank=True)
    duty_arranges = serializers.ListField(child=DutyArrangeSlz())
    alert_notice = serializers.ListField(child=AlertSerializer())
    action_notice = serializers.ListField(child=ExecutionSerializer())
    path = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = UserGroup
        fields = (
            "id",
            "name",
            "bk_biz_id",
            "desc",
            "update_user",
            "update_time",
            "create_user",
            "create_time",
            "duty_arranges",
            "alert_notice",
            "action_notice",
            "need_duty",
            "path",
            "channels",
            "mention_list",
            "mention_type",
        )

    def validate_name(self, value):
        if len(value) > 128:
            raise ValidationError(detail=_("告警组名称长度不能超过128，请重新确认"))
        query_result = UserGroup.objects.filter(bk_biz_id=self.initial_data["bk_biz_id"], name=value)
        if self.instance:
            query_result = query_result.exclude(id=self.instance.id)
        if query_result.exists():
            raise ValidationError(detail=_("当前告警组名称已经存在，请重新确认"))
        return value

    def validate_need_duty(self, value):
        """
        是否需要轮值的需求验证
        """

        if value and self.initial_data.get("channels") and NoticeChannel.USER not in self.initial_data.get("channels"):
            # 如果通知到人的开关没有打开，不允许轮值
            raise ValidationError(detail=_("当前告警组已启用轮值，必须要开启内部通知渠道"))
        return value

    def __init__(self, instance=None, data=empty, **kwargs):
        self.duty_arranges_mapping = kwargs.pop("duty_arranges_mapping", {})
        super(UserGroupDetailSlz, self).__init__(instance=instance, data=data, **kwargs)

    def __new__(cls, *args, **kwargs):
        if kwargs.get("many", False):
            groups = args[0] if args else kwargs.get("instance", [])
            user_group_ids = [user_group.id for user_group in groups]
            duty_arranges = DutyArrangeSlz(
                instance=DutyArrange.objects.filter(user_group_id__in=user_group_ids).order_by("order"), many=True
            ).data
            duty_arranges_mapping = defaultdict(list)
            for item in duty_arranges:
                duty_arranges_mapping[item["user_group_id"]].append(item)
            kwargs["duty_arranges_mapping"] = duty_arranges_mapping
        return super(UserGroupDetailSlz, cls).__new__(cls, *args, **kwargs)

    def to_representation(self, instance: UserGroup):
        data = super(UserGroupDetailSlz, self).to_representation(instance)
        if self.duty_arranges_mapping:
            data["duty_arranges"] = self.duty_arranges_mapping.get(instance.id, [])
        else:
            data["duty_arranges"] = DutyArrangeSlz(instance.duty_arranges, many=True).data

        # 以下部分为了兼容历史数据
        data["duty_plans"] = DutyPlanSlz(instance.duty_plans, many=True).data
        data["strategy_count"] = len(
            set(
                StrategyActionConfigRelation.objects.filter(user_groups__contains=instance.id).values_list(
                    "strategy_id", flat=True
                )
            )
        )
        data["rule_count"] = len(
            set(AlertAssignRule.objects.filter(user_groups__contains=instance.id).values_list("id", flat=True))
        )
        data["delete_allowed"] = data["strategy_count"] == 0 and data["rule_count"] == 0
        data["edit_allowed"] = instance.bk_biz_id != 0

        data["mention_list"] = self.mention_users_representation(data["mention_list"])
        return data

    def mention_users_representation(self, users):
        """
        提醒用户进行翻译
        """
        user_ids = [user["id"] for user in users if user["type"] == "user"]
        try:
            user_list = api.bk_login.get_all_user(
                page_size=500, fields="username,display_name", exact_lookups=",".join(set(user_ids))
            )["results"]
            user_list = {user["username"]: user["display_name"] for user in user_list}
        except Exception as error:
            # 有异常打印日志，默认为空，不做翻译
            logger.exception("query list users error %s" % str(error))
            user_list = {}
        all_users = DutyBaseInfoSlz.get_all_recievers()
        return DutyBaseInfoSlz.translate_user_display(users, all_users, user_list)

    def update(self, instance, validated_data):
        validated_data["hash"] = ""
        validated_data["snippet"] = ""
        validated_data["mention_type"] = 1
        return super(UserGroupDetailSlz, self).update(instance, validated_data)

    def save(self, **kwargs):
        """
        拆分为两个部分
        """
        duty_arranges = self.validated_data.pop("duty_arranges")
        self.validated_data["hash"] = ""
        self.validated_data["snippet"] = ""
        # 只要编辑过，这里都默认是1
        self.validated_data["mention_type"] = 1
        super(UserGroupDetailSlz, self).save(**kwargs)
        for index, duty_arrange in enumerate(duty_arranges):
            # 根据排序给出顺序表
            duty_arrange["order"] = index + 1

        existed_duty = {duty_arrange["id"]: duty_arrange for duty_arrange in duty_arranges if duty_arrange.get("id")}
        existed_duty_instances = {
            duty.id: duty
            for duty in DutyArrange.objects.filter(id__in=list(existed_duty.keys()), user_group_id=self.instance.id)
        }
        existed_duty = {
            duty_id: duty_arrange for duty_id, duty_arrange in existed_duty.items() if duty_id in existed_duty_instances
        }

        new_duty_arranges = [
            duty_arrange
            for duty_arrange in duty_arranges
            if not duty_arrange.get("id") or duty_arrange["id"] not in existed_duty
        ]

        # 针对DB已有的数据进行快照和计划的改变
        self.manage_duty_snap_and_plan(existed_duty)

        for duty_id, duty_data in existed_duty.items():
            duty = existed_duty_instances[duty_id]
            for attr, value in duty_data.items():
                setattr(duty, attr, value)
            duty.save()

        duty_arrange_instances = []
        for duty_arrange in new_duty_arranges:
            duty_arrange["user_group_id"] = self.instance.id
            duty_arrange_instances.append(DutyArrange(**duty_arrange))
        if duty_arrange_instances:
            DutyArrange.objects.bulk_create(duty_arrange_instances)

        return self.instance

    def manage_duty_snap_and_plan(self, existed_duty):
        # 删除不存在的
        DutyArrange.objects.filter(user_group_id=self.instance.id).exclude(id__in=list(existed_duty.keys())).delete()
        DutyArrangeSnap.objects.filter(user_group_id=self.instance.id, is_active=True).exclude(
            duty_arrange_id__in=list(existed_duty.keys())
        ).update(is_active=False)
        DutyPlan.objects.filter(user_group_id=self.instance.id, is_active=True).exclude(
            duty_arrange_id__in=list(existed_duty.keys())
        ).update(is_active=False)

        # 更改顺序之后，直接更新plan的信息
        new_duty_plans = []
        old_duty_plans = []
        for duty_plan in DutyPlan.objects.filter(
            user_group_id=self.instance.id, is_active=True, duty_arrange_id__in=list(existed_duty.keys())
        ):
            old_duty_plans.append(duty_plan.id)
            duty_plan.id = None
            duty_plan.order = existed_duty[duty_plan.duty_arrange_id]["order"]
            new_duty_plans.append(duty_plan)

        DutyPlan.objects.bulk_create(new_duty_plans)
        DutyPlan.objects.filter(id__in=old_duty_plans).delete()
