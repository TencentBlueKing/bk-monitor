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

import arrow
import pytz
from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import empty

from bkmonitor.action.duty_manage import GroupDutyRuleManager
from bkmonitor.action.serializers import AlertSerializer, ExecutionSerializer
from bkmonitor.action.utils import (
    get_duty_rule_user_groups,
    get_user_group_assign_rules,
    get_user_group_strategies,
    validate_datetime_range,
    validate_time_range,
)
from bkmonitor.models import (
    AlertAssignRule,
    DutyArrange,
    DutyPlan,
    DutyRule,
    DutyRuleRelation,
    DutyRuleSnap,
    StrategyActionConfigRelation,
    UserGroup,
)
from bkmonitor.utils import time_tools
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.request import get_request
from common.log import logger
from constants.action import NoticeChannel
from constants.common import (
    DutyGroupType,
    IsoWeekDay,
    MonthDay,
    RotationType,
    WorkTimeType,
)
from core.drf_resource import api, resource
from core.drf_resource.exceptions import CustomException
from core.errors.user_group import DutyRuleNameExist, UserGroupNameExist


class DateTimeField(serializers.CharField):
    def run_validators(self, value):
        super().run_validators(value)
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
        return super().to_internal_value(data)

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
        super().run_validators(value)
        if value:
            handoff_slz = HandOffSettingsSerializer(data=value)
            handoff_slz.is_valid(raise_exception=True)


class UserSerializer(serializers.Serializer):
    id = serializers.CharField(required=True, label="通知对象ID")
    type = serializers.ChoiceField(
        required=True, choices=(("user", _("用户")), ("group", _("用户组"))), label="通知对象类别"
    )


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
    is_custom = serializers.BooleanField(label="是否自定义", required=False, default=False)
    work_type = serializers.ChoiceField(required=True, label="工作类型", choices=RotationType.ROTATION_TYPE_CHOICE)
    work_days = serializers.ListField(required=False, label="工作日期", child=serializers.IntegerField())
    work_date_range = serializers.ListField(required=False, label="工作日期范围", child=serializers.CharField())
    work_time_type = serializers.ChoiceField(
        required=False, default=WorkTimeType.TIME_RANGE, choices=WorkTimeType.WORK_TYME_TYPE_CHOICE
    )
    work_time = serializers.ListField(child=serializers.CharField(), required=True, label="工作时间")
    period_settings = serializers.DictField(label="周期分配", required=False)

    def to_internal_value(self, data):
        self.initial_data = data
        return super().to_internal_value(data)

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
        """
        校验工作时间
        """
        if not value:
            return value
        for work_time in value:
            if self.initial_data.get("work_time_type") == WorkTimeType.DATETIME_RANGE:
                if not validate_datetime_range(work_time):
                    raise ValidationError(detail=_("设置的时间范围不正确, 正确格式为01 00:00--01 23:59"))
            elif not validate_time_range(work_time):
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
        super().__init__(instance, data, **kwargs)

    def __new__(cls, *args, **kwargs):
        duty_instances = args[0] if args else kwargs.get("instance", [])
        duty_instances = duty_instances or []
        if isinstance(duty_instances, DutyPlan | DutyArrange):
            duty_instances = [duty_instances]
        all_members = cls.get_all_members(duty_instances)
        if not all_members:
            return super().__new__(cls, *args, **kwargs)

        # 新增 notice_user_detail 标记，获取用户中文名
        request = get_request(peaceful=True)
        need_username = getattr(request, "notice_user_detail", None)
        if need_username:
            try:
                user_list = api.bk_login.get_all_user(
                    page_size=500, fields="username,display_name", exact_lookups=",".join(sorted(set(all_members)))
                )["results"]
                kwargs["user_list"] = {user["username"]: user["display_name"] for user in user_list}
            except BaseException as error:
                logger.info(f"query list users error {str(error)}")
        return super().__new__(cls, *args, **kwargs)

    @classmethod
    def get_all_members(cls, instances):
        raise NotImplementedError("position NotImplementedError")

    @staticmethod
    def get_all_recievers() -> dict[str, dict[str, dict]]:
        """
        获取用户组具体的用户
        """
        receivers: dict[str, dict[str, dict]] = defaultdict(dict)
        try:
            for item in resource.notice_group.get_receiver():
                receiver_type = item["id"]
                for receiver in item["children"]:
                    receivers[receiver_type][receiver["id"]] = receiver
        except Exception:
            pass
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
    def all_users(self) -> dict[str, dict[str, dict]]:
        """
        接收人信息
        """
        return self.get_all_recievers()

    def users_representation(self, users):
        return self.translate_user_display(users, self.all_users, self.user_list)


class DutyArrangeSlz(DutyBaseInfoSlz):
    id = serializers.IntegerField(required=False, read_only=True)
    user_group_id = serializers.IntegerField(required=False, allow_null=True)
    duty_rule_id = serializers.IntegerField(required=False, allow_null=True)
    need_rotation = serializers.BooleanField(required=False, default=False)

    users = serializers.ListField(required=False, child=UserSerializer())
    duty_users = serializers.ListField(required=False, child=serializers.ListField(child=UserSerializer()))

    group_type = serializers.ChoiceField(choices=DutyGroupType.CHOICE, default=DutyGroupType.SPECIFIED)
    group_number = serializers.IntegerField(required=False)

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
    hash = serializers.CharField(label="原始配置摘要", max_length=64, default="", allow_blank=True)

    class Meta:
        model = DutyArrange
        fields = (
            "id",
            "user_group_id",
            "duty_rule_id",
            "need_rotation",
            "duty_time",
            "effective_time",
            "handoff_time",
            "users",
            "duty_users",
            "backups",
            "order",
            "hash",
            "group_type",
            "group_number",
        )

    @classmethod
    def get_all_members(cls, duty_arranges):
        """
        获取所有成员的用户ID
        """
        all_members = []
        for duty_arrange in duty_arranges:
            all_members.extend([user["id"] for user in duty_arrange.users if user["type"] == "user"])
            all_members.extend(
                [user["id"] for users in duty_arrange.duty_users for user in users if user["type"] == "user"]
            )
        return all_members

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["users"] = self.users_representation(data["users"])
        data["duty_users"] = self.duty_users_representation(data.get("duty_users", []))
        return data

    def duty_users_representation(self, duty_users):
        duty_users = [self.users_representation(users) for users in duty_users]
        return duty_users

    def to_internal_value(self, data):
        self.initial_data = data
        ret = super().to_internal_value(data)
        ret = self.calc_hash(ret)
        return ret

    @staticmethod
    def calc_hash(internal_data):
        hash_data = {
            "duty_users": internal_data.get("duty_users", []),
            "users": internal_data.get("users", []),
            "duty_time": internal_data.get("duty_time", []),
            "group_type": internal_data.get("group_type", DutyGroupType.SPECIFIED),
            "group_number": internal_data.get("group_number", 0),
        }
        internal_data["hash"] = count_md5(hash_data)

        return internal_data

    def validate_need_rotation(self, value):
        if value and not self.initial_data.get("handoff_time"):
            raise ValidationError(detail=_("需要交接的情况下，交接轮值方式与交接时间不能为空"))
        return value

    def validate_group_type(self, value):
        if value == DutyGroupType.AUTO and not self.initial_data.get("group_number"):
            raise ValidationError(detail=_("当前轮值为自动分组，请设置每个班次对应的人数"))
        return value


class DutyPlanSlz(DutyBaseInfoSlz):
    class Meta:
        model = DutyPlan
        fields = (
            "id",
            "user_group_id",
            "duty_rule_id",
            "duty_time",
            "start_time",
            "finished_time",
            "work_times",
            "users",
            "order",
            "last_send_time",
        )

    @classmethod
    def get_all_members(cls, duty_plans):
        all_members = []
        for duty_plan in duty_plans:
            all_members.extend([user["id"] for user in duty_plan.users if user["type"] == "user"])
        return all_members

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["is_active"] = instance.is_active_plan()
        data["users"] = self.users_representation(data["users"])
        return data


class DutySwitchSlz(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
    enabled = serializers.BooleanField(label="是否开启", required=True)
    ids = serializers.ListField(label="启停的ID", allow_empty=False, required=True)


class DutyRuleSlz(serializers.ModelSerializer):
    bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
    name = serializers.CharField(label="轮值规则名称", required=True)
    labels = serializers.ListField(label="轮值规则标签", required=False, default=list)
    enabled = serializers.BooleanField(label="是否开启", default=False)
    effective_time = DateTimeField(label="规则生效时间", required=True)
    end_time = DateTimeField(label="规则结束时间", required=False, allow_blank=True)
    category = serializers.ChoiceField(
        label="类型",
        choices=(
            ("regular", "常规值班"),
            ("handoff", "交替轮值"),
        ),
        default="regular",
    )

    class Meta:
        model = DutyRule
        fields = (
            "id",
            "bk_biz_id",
            "name",
            "labels",
            "effective_time",
            "end_time",
            "category",
            "enabled",
            "create_time",
            "create_user",
            "update_time",
            "update_user",
        )

    def __init__(self, instance=None, data=empty, **kwargs):
        self.rule_group_dict = kwargs.pop("rule_group_dict", {})
        super().__init__(instance, data, **kwargs)

    def __new__(cls, *args, **kwargs):
        if kwargs.get("many", False):
            all_rules = args[0] if args else kwargs.get("instance", [])
            rule_group_dict = get_duty_rule_user_groups(list(all_rules.values_list("id", flat=True)))
            kwargs["rule_group_dict"] = rule_group_dict
        return super().__new__(cls, *args, **kwargs)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["user_groups"] = list(set(self.rule_group_dict.get(instance.id, [])))
        data["user_groups_count"] = len(data["user_groups"])
        data["delete_allowed"] = data["user_groups_count"] == 0
        data["edit_allowed"] = instance.bk_biz_id != 0
        return data

    def validate_name(self, value):
        if len(value) > 128:
            raise ValidationError(detail=_("轮值规则名称长度不能超过128个字符，请重新确认"))
        query_result = DutyRule.objects.filter(bk_biz_id=self.initial_data["bk_biz_id"], name=value)
        if self.instance:
            query_result = query_result.exclude(id=self.instance.id)
        if query_result.exists():
            raise DutyRuleNameExist()
        return value


class DutyRuleDetailSlz(DutyRuleSlz):
    duty_arranges = serializers.ListField(child=DutyArrangeSlz(), required=False, default=list)

    class Meta:
        model = DutyRule
        fields = (
            "id",
            "bk_biz_id",
            "name",
            "labels",
            "effective_time",
            "end_time",
            "category",
            "enabled",
            "hash",
            "duty_arranges",
            "create_time",
            "create_user",
            "update_time",
            "update_user",
            "code_hash",
            "app",
            "path",
            "snippet",
        )

    def save(self, **kwargs):
        duty_arranges = self.validated_data.pop("duty_arranges", [])
        super().save(**kwargs)

        DutyArrange.bulk_create(duty_arranges, self.instance)

        if self.instance.enabled:
            # 快照和计划管理，以便预览能看到即时变化
            user_groups = UserGroup.objects.filter(duty_rules__contains=self.instance.id).only(
                "id", "bk_biz_id", "duty_rules", "duty_notice", "timezone"
            )
            for user_group in user_groups:
                group_duty_manager = GroupDutyRuleManager(user_group, [self.data])
                try:
                    group_duty_manager.manage_duty_rule_snap(time_tools.datetime_today().strftime("%Y-%m-%d %H:%M:%S"))
                except Exception:  # noqa
                    continue
        else:
            # 如果是关闭了当前的规则, 则已有的排班计划都需要关闭掉
            # TODO 和产品确认下，是否要一个调整时间
            DutyRuleSnap.objects.filter(duty_rule_id=self.instance.id).update(enabled=False)
            DutyPlan.objects.filter(duty_rule_id=self.instance.id).update(is_effective=False)

        return self.instance

    def to_internal_value(self, data):
        ret = super().to_internal_value(data)
        ret = self.calc_hash(ret)
        return ret

    @staticmethod
    def calc_hash(internal_data):
        """
        计算关键字hash
        """
        hash_data = {
            "effective_time": internal_data.get("effective_time", ""),
            "end_time": internal_data.get("end_time", ""),
            "duty_arranges": [d["hash"] for d in internal_data.get("duty_arranges")],
        }
        internal_data["hash"] = count_md5(hash_data)
        return internal_data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["user_groups"] = list(
            set(DutyRuleRelation.objects.filter(duty_rule_id=instance.id).values_list("user_group_id", flat=True))
        )
        data["user_groups_count"] = len(data["user_groups"])
        data["delete_allowed"] = data["user_groups_count"] == 0
        data["edit_allowed"] = instance.bk_biz_id != 0
        # 将对应的duty_arranges加上
        data["duty_arranges"] = DutyArrangeSlz(
            instance=DutyArrange.objects.filter(duty_rule_id=instance.id), many=True
        ).data
        return data


class PreviewSerializer(serializers.Serializer):
    class SourceType:
        DB = "DB"
        API = "API"

        choices = [DB, API]

    bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
    id = serializers.IntegerField(required=False, label="规则组ID")
    begin_time = DateTimeField(required=False, label="预览生效开始时间", default="")
    days = serializers.IntegerField(required=False, label="预览天数", default=30)
    timezone = serializers.CharField(required=False, default="Asia/Shanghai")
    resource_type = serializers.ChoiceField(
        required=False, choices=["user_group", "duty_rule"], default="duty_rule", label="资源类型"
    )
    source_type = serializers.ChoiceField(required=False, choices=SourceType.choices, default=SourceType.API)
    config = serializers.DictField(required=False, label="配置信息", default=None)

    def to_internal_value(self, data):
        """
        参数转换
        """
        self.initial_data = data
        internal_data = super().to_internal_value(data)
        # 数据返回增加对应的存储记录
        internal_data["instance"] = self.get_instance(internal_data) if internal_data.get("id") else None
        # 如果是预览的话，可以随便设置一个名字
        return internal_data

    def validate_config(self, value):
        """
        对应的配置信息校验和丰富
        """
        if isinstance(value, dict):
            value["name"] = "[demo] for preview"
        if self.initial_data.get(
            "source_type", self.SourceType.API
        ) == self.SourceType.API and not self.initial_data.get("config"):
            # 如果数据来源是API，并且不带配置信息返回错误
            raise ValidationError(detail="params config is required when resource type is API")
        return value

    def validate_source_type(self, value):
        if value == self.SourceType.DB and not self.initial_data.get("id"):
            raise ValidationError(detail="field(id) is required when preview config is from DB")
        return value

    def get_instance(self, internal_data):
        """
        获取预览的DB对象
        """
        instance_model = DutyRule
        if internal_data["resource_type"] == "user_group":
            instance_model = UserGroup
        if internal_data["source_type"] == self.SourceType.DB and not internal_data.get("id"):
            raise CustomException("field(id) is required where source-type is db or default")

        try:
            instance = instance_model.objects.get(id=internal_data["id"], bk_biz_id=internal_data["bk_biz_id"])
        except (DutyRule.DoesNotExist, UserGroup.DoesNotExist):
            raise CustomException(f"resource({internal_data['resource_type']}) not existed")
        return instance


class UserGroupSlz(serializers.ModelSerializer):
    name = serializers.CharField(required=True)
    bk_biz_id = serializers.IntegerField(required=True)
    need_duty = serializers.BooleanField(required=False, default=False)
    timezone = serializers.CharField(required=False, default="Asia/Shanghai")
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
            "timezone",
            "update_user",
            "update_time",
            "create_user",
            "create_time",
            "duty_rules",
            "mention_list",
            "mention_type",
            "app",
        )

    def __init__(self, instance=None, data=empty, **kwargs):
        self.group_user_mappings = kwargs.pop("group_user_mappings", {})
        self.strategy_count_of_given_type = kwargs.pop("strategy_count_of_given_type", {})
        self.strategy_count_of_all = kwargs.pop("strategy_count_of_all", {})
        self.rule_count = kwargs.pop("rule_count", {})
        super().__init__(instance=instance, data=data, **kwargs)

    def __new__(cls, *args, **kwargs):
        request = kwargs.get("context", {}).get("request")
        if kwargs.get("many", False):
            # 带排除详细信息的接口不获取策略相关内容
            groups = list(args[0] if args else kwargs.get("instance", []))
            group_user_mappings = defaultdict(list)
            cls.get_group_duty_users(groups, group_user_mappings)
            cls.get_group_users_without_duty(groups, group_user_mappings)
            kwargs["group_user_mappings"] = group_user_mappings
            if not (request and request.query_params.get("exclude_detail_info", "0") != "0"):
                user_group_ids = [group.id for group in groups]
                kwargs["strategy_count_of_all"] = get_user_group_strategies(user_group_ids)
                kwargs["rule_count"] = get_user_group_assign_rules(user_group_ids)
                kwargs["strategy_count_of_given_type"] = kwargs["strategy_count_of_all"]

        return super().__new__(cls, *args, **kwargs)

    @staticmethod
    def get_group_users_without_duty(groups, group_user_mappings):
        """
        获取没有轮值的用户信息
        """
        user_group_ids = [group.id for group in groups]
        user_group_instance_mapping = {group.id: group for group in groups}
        duty_arranges = DutyArrange.objects.filter(user_group_id__in=user_group_ids).order_by("order")
        group_users_without_duty = DutyArrangeSlz(instance=duty_arranges, many=True).data
        for item in group_users_without_duty:
            group = user_group_instance_mapping.get(item["user_group_id"])
            if group.need_duty:
                continue
            if not group_user_mappings[group.id]:
                # 如果当前不轮值，直接返回第一组的信息
                group_user_mappings[group.id].extend(item["users"])

    @staticmethod
    def get_group_duty_users(groups, group_user_mappings):
        """
        获取轮值用户组的用户列表
        """
        # 参考 DutyPlan.is_active_plan, 提前过滤部分未激活的计划
        # 由于目前计划创建时，timezone 固定为默认值 "Asia/Shanghai"，所以为了使用索引，不使用 timezone 对当前时间进行转换
        # 以后考虑将 start_time 和 finished_time 存为 UTC 时间，避免转换
        user_group_ids = [group.id for group in groups]
        now = arrow.now("Asia/Shanghai").format("YYYY-MM-DD HH:mm:ss")
        duty_plans = DutyPlan.objects.filter(
            Q(finished_time__gte=now) | Q(finished_time__isnull=True),
            start_time__lte=now,
            user_group_id__in=user_group_ids,
            is_effective=1,
        )

        group_rule_users = defaultdict(list)
        for plan in DutyPlanSlz(instance=duty_plans, many=True).data:
            group_rule_users[f"{plan['user_group_id']}-{plan['duty_rule_id']}"].append(plan)

        for group in groups:
            if not group.need_duty:
                continue
            for duty_rule_id in group.duty_rules:
                rule_plans = group_rule_users.get(f"{group.id}-{duty_rule_id}", [])
                if not rule_plans:
                    # 如果没有获取到plan, 继续
                    continue
                users = []
                for plan in rule_plans:
                    if not plan["is_active"]:
                        # 如果当前plan未激活，直接返回
                        continue
                    for user in plan["users"]:
                        if user not in users:
                            users.append(user)
                if users:
                    # 命中到规则对应的用户，终止轮值规则的循环
                    group_user_mappings[group.id] = users
                    break

    def to_representation(self, instance):
        data = super().to_representation(instance)
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


class PlanNoticeSerializer(serializers.Serializer):
    """
    预览计划通知参数
    """

    enabled = serializers.BooleanField(required=False, default=True)
    chat_ids = serializers.ListSerializer(child=serializers.CharField(max_length=32, min_length=32), required=True)
    days = serializers.IntegerField(label="发送预览天数", required=True)
    type = serializers.ChoiceField(
        label="通知周期类型", choices=RotationType.ROTATION_TYPE_CHOICE, default=RotationType.WEEKLY
    )
    date = serializers.IntegerField(label="发送日期", required=False)
    time = serializers.CharField(label="发送时间点", required=True)


class PersonalNoticeSerializer(serializers.Serializer):
    """
    个人值班通知
    """

    enabled = serializers.BooleanField(required=False, default=True)
    hours_ago = serializers.IntegerField(label="发送日期", required=True)

    duty_rules = serializers.ListSerializer(label="指定的规则", child=serializers.IntegerField(), default=list)


class DutyNoticeSerializer(serializers.Serializer):
    """
    轮值排班计划通知配置
    """

    plan_notice = PlanNoticeSerializer(label="告警组排班计划", required=False)
    personal_notice = PersonalNoticeSerializer(label="个人排班通知", required=False)


class UserGroupDetailSlz(UserGroupSlz):
    """
    告警组
    """

    name = serializers.CharField(label="告警组名称", required=True)
    bk_biz_id = serializers.IntegerField(required=True)
    need_duty = serializers.BooleanField(required=False, default=False)
    desc = serializers.CharField(required=False, default="", allow_blank=True)
    # duty_arranges和duty_rules二者选其一
    duty_arranges = serializers.ListField(child=DutyArrangeSlz(), required=False, default=list)
    duty_rules = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    alert_notice = serializers.ListField(child=AlertSerializer())
    action_notice = serializers.ListField(child=ExecutionSerializer())
    duty_notice = DutyNoticeSerializer(label="工作计划通知", required=False)
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
            "duty_rules",
            "alert_notice",
            "action_notice",
            "duty_notice",
            "need_duty",
            "path",
            "channels",
            "mention_list",
            "mention_type",
            "timezone",
        )

    def validate_name(self, value):
        if len(value) > 128:
            raise ValidationError(detail=_("告警组名称长度不能超过128，请重新确认"))
        query_result = UserGroup.objects.filter(bk_biz_id=self.initial_data["bk_biz_id"], name=value)
        if self.instance:
            query_result = query_result.exclude(id=self.instance.id)
        if query_result.exists():
            raise UserGroupNameExist()
        return value

    def validate_need_duty(self, value):
        """
        是否需要轮值的需求验证
        """

        if value and self.initial_data.get("channels") and NoticeChannel.USER not in self.initial_data.get("channels"):
            # 如果通知到人的开关没有打开，不允许轮值
            raise ValidationError(detail=_("当前告警组已启用轮值，必须要开启内部通知渠道"))
        if value and not self.initial_data.get("duty_rules"):
            # 如果启动轮值, 必须要关联轮值规则
            raise ValidationError(detail=_("当前告警组已启用轮值，关联的轮值规则不能为空"))
        return value

    def validate_timezone(self, value):
        try:
            pytz.timezone(value)
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValidationError(detail="timezone is invalid")
        return value

    def __init__(self, instance=None, data=empty, **kwargs):
        self.duty_arranges_mapping = kwargs.pop("duty_arranges_mapping", {})
        self.duty_rules_mapping = kwargs.pop("duty_rules", {})
        super().__init__(instance=instance, data=data, **kwargs)

    def __new__(cls, *args, **kwargs):
        if kwargs.get("many", False):
            groups = args[0] if args else kwargs.get("instance", [])
            user_group_ids = [user_group.id for user_group in groups]
            duty_rule_ids = []
            for user_group in groups:
                if not user_group.duty_rules:
                    continue
                duty_rule_ids.extend(user_group.duty_rules)

            duty_arranges = DutyArrangeSlz(
                instance=DutyArrange.objects.filter(user_group_id__in=user_group_ids).order_by("order"), many=True
            ).data
            duty_arranges_mapping = defaultdict(list)
            if duty_rule_ids:
                # 获取对应的规则ID信息，用来做展示
                duty_rules = DutyRule.objects.filter(id__in=duty_rule_ids)
                kwargs["duty_rules"] = {
                    rule_data["id"]: rule_data for rule_data in DutyRuleDetailSlz(instance=duty_rules, many=True).data
                }

            for item in duty_arranges:
                duty_arranges_mapping[item["user_group_id"]].append(item)
            kwargs["duty_arranges_mapping"] = duty_arranges_mapping
        return super().__new__(cls, *args, **kwargs)

    def to_representation(self, instance: UserGroup):
        data = super().to_representation(instance)
        if self.duty_arranges_mapping:
            data["duty_arranges"] = self.duty_arranges_mapping.get(instance.id, [])
        else:
            data["duty_arranges"] = DutyArrangeSlz(instance.duty_arranges, many=True).data

        # 将对应的规则信息加入到告警组详情中，方便用户用来展示
        data["duty_rules_info"] = []
        for rule_id in data["duty_rules"]:
            if rule_id in self.duty_rules_mapping:
                data["duty_rules_info"].append(self.duty_rules_mapping[rule_id])

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
                page_size=500, fields="username,display_name", exact_lookups=",".join(sorted(set(user_ids)))
            )["results"]
            user_list = {user["username"]: user["display_name"] for user in user_list}
        except Exception as error:
            # 有异常打印日志，默认为空，不做翻译
            logger.exception(f"query list users error {str(error)}")
            user_list = {}
        all_users = DutyBaseInfoSlz.get_all_recievers()
        return DutyBaseInfoSlz.translate_user_display(users, all_users, user_list)

    def update(self, instance, validated_data):
        validated_data["hash"] = ""
        validated_data["snippet"] = ""
        validated_data["mention_type"] = 1
        return super().update(instance, validated_data)

    def save(self, **kwargs):
        """
        拆分为三个部分部分
        """
        duty_arranges = self.validated_data.pop("duty_arranges")
        self.validated_data["hash"] = ""
        self.validated_data["snippet"] = ""
        # 只要编辑过，这里都默认是1
        self.validated_data["mention_type"] = 1

        # step 1 save user group
        super().save(**kwargs)

        # step 3 save duty arranges and delete old relation
        if duty_arranges:
            DutyArrange.bulk_create(duty_arranges, self.instance)

        # step 3 save duty arranges and delete old relation
        self.save_duty_rule_relations()

        self.manage_duty_snap_and_plan()

        return self.instance

    def save_duty_rule_relations(self):
        # step 1: delete old relations
        DutyRuleRelation.objects.filter(user_group_id=self.instance.id).delete()
        if not self.instance.duty_rules:
            return
        # step 1: create new relations
        rules = [
            DutyRuleRelation(
                user_group_id=self.instance.id, duty_rule_id=rule_id, order=index, bk_biz_id=self.instance.bk_biz_id
            )
            for index, rule_id in enumerate(self.instance.duty_rules)
        ]
        DutyRuleRelation.objects.bulk_create(rules)

    def manage_duty_snap_and_plan(self):
        """
        调整duty_snap 和 排班计划
        """
        # TODO 需要改造的

        duty_rules = DutyRuleDetailSlz(
            instance=DutyRule.objects.filter(id__in=self.instance.duty_rules), many=True
        ).data

        group_duty_manager = GroupDutyRuleManager(self.instance, duty_rules)
        group_duty_manager.manage_duty_rule_snap(time_tools.datetime_today().strftime("%Y-%m-%d %H:%M:%S"))
        # 删除掉已经解除绑定的相关的snap和排班信息
        DutyRuleSnap.objects.filter(user_group_id=self.instance.id).exclude(
            duty_rule_id__in=self.instance.duty_rules
        ).delete()

        # 在数据量特别大情况下，会判断是否能够快速删除
        # 如果不能快速删除，则采用批量删除的形式，这也是主要耗时的原因之一
        # 故参考 https://stackoverflow.com/a/36935536/24637892,
        # 使用 queryset._raw_delete(using=queryset.db) 私有api来加速这个删除的过程
        delete_buty_plan_query = DutyPlan.objects.filter(user_group_id=self.instance.id).exclude(
            duty_rule_id__in=self.instance.duty_rules
        )
        delete_buty_plan_query._raw_delete(delete_buty_plan_query.db)
