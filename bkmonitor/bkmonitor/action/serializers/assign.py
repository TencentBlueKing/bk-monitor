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
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.models import AlertAssignGroup, AlertAssignRule
from constants.action import GLOBAL_BIZ_ID, ActionPluginType, UserGroupType
from constants.alert import AlertAssignSeverity
from constants.strategy import DATALINK_SOURCE


class ConditionSerializer(serializers.Serializer):
    field = serializers.CharField(label="匹配字段")
    value = serializers.ListField(label="匹配值", child=serializers.CharField(allow_blank=True))
    method = serializers.ChoiceField(
        label="匹配方法", choices=["eq", "neq", "include", "exclude", "reg", "nreg", "issuperset"], default="eq"
    )
    condition = serializers.ChoiceField(label="复合条件", choices=["and", "or", ""], default="")


class TagSerializer(serializers.Serializer):
    key = serializers.CharField(label="字段", required=True)
    value = serializers.CharField(label="值", required=True)
    display_key = serializers.CharField(label="字段显示值", default="")
    display_value = serializers.CharField(label="字段值的显示值", default="")

    def validate(self, attrs):
        unsafe_chars = {"<", ">", "&", '"', "'", "`"}
        for value in attrs.values():
            value = set(value)
            if value & unsafe_chars:
                raise ValidationError(detail=_("不能包含特殊字符"))
        return attrs


class UpgradeConfigSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField(label="是否生效", required=False, default=False)
    user_groups = serializers.ListField(label="告警组", child=serializers.IntegerField(), required=False, default=[])
    upgrade_interval = serializers.IntegerField(label="升级时间", required=False, default=60)

    def to_internal_value(self, data):
        self.initial_data = data
        return super(UpgradeConfigSerializer, self).to_internal_value(data)

    def validate_user_groups(self, value):
        if self.initial_data.get("is_enabled") and not value:
            raise ValidationError(detail=_("请配置告警升级对应的告警通知组"))
        return value

    def validate_upgrade_interval(self, value):
        if self.initial_data.get("is_enabled") and not value:
            raise ValidationError(detail=_("请配置告警升级对应的告警升级时间"))
        return value


class UpgradeConfigField(serializers.JSONField):
    def run_validators(self, value):
        super(UpgradeConfigField, self).run_validators(value)
        if value:
            upgrade_slz = UpgradeConfigSerializer(data=value)
            upgrade_slz.is_valid(raise_exception=True)


class AssignActionSerializer(serializers.Serializer):
    action_type = serializers.ChoiceField(
        label="套餐类型", required=True, choices=[ActionPluginType.ITSM, ActionPluginType.NOTICE]
    )
    upgrade_config = UpgradeConfigField(label="套餐类型", required=False)
    action_id = serializers.IntegerField(label="套餐ID", required=False)
    is_enabled = serializers.BooleanField(label="是否生效", default=True)


class BaseAlertAssignRuleSlz(serializers.Serializer):
    id = serializers.IntegerField(label="主键ID", required=False)
    is_enabled = serializers.BooleanField(label="是否生效", required=False, default=False)
    user_groups = serializers.ListField(label="告警组", child=serializers.IntegerField(), required=True, allow_empty=False)
    conditions = serializers.ListField(label="分派条件", child=ConditionSerializer(), required=True, allow_empty=False)
    actions = serializers.ListField(label="分派动作", child=AssignActionSerializer(), required=False)
    alert_severity = serializers.ChoiceField(
        label="告警级别",
        default=AlertAssignSeverity.KEEP,
        choices=[
            AlertAssignSeverity.REMIND,
            AlertAssignSeverity.WARNING,
            AlertAssignSeverity.FATAL,
            AlertAssignSeverity.KEEP,
        ],
    )
    additional_tags = serializers.ListField(label="追加标签", child=TagSerializer(), required=False)


class AssignRuleSlz(serializers.ModelSerializer, BaseAlertAssignRuleSlz):
    bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
    assign_group_id = serializers.IntegerField(label="分派组ID", required=True)
    user_type = serializers.ChoiceField(label="通知人员类型", choices=UserGroupType.CHOICE, default=UserGroupType.MAIN)

    class Meta:
        model = AlertAssignRule
        fields = (
            "id",
            "bk_biz_id",
            "assign_group_id",
            "is_enabled",
            "user_groups",
            "conditions",
            "actions",
            "alert_severity",
            "additional_tags",
            "user_type",
        )

    def validate_actions(self, value):
        for action in value:
            if action["action_type"] != ActionPluginType.NOTICE:
                continue
            if not action.get("upgrade_config", {}).get("is_enabled"):
                continue
            if set(action["upgrade_config"]["user_groups"]) & set(self.initial_data.get("user_groups", [])):
                raise ValidationError(detail=_("通知升级的用户组不能包含第一次接收告警的用户组"))
        return value


class AssignGroupSlz(serializers.ModelSerializer):
    name = serializers.CharField(label="规则组名称", required=True)
    id = serializers.IntegerField(label="分组ID", required=False)
    bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
    priority = serializers.IntegerField(label="优先级", default=0)
    settings = serializers.JSONField(label="属性配置", default={}, required=False)

    class Meta:
        model = AlertAssignGroup
        fields = ("id", "name", "bk_biz_id", "priority", "settings", "source", "update_user", "update_time")

    def validate_priority(self, value):
        query_result = AlertAssignGroup.objects.filter(
            priority=value, bk_biz_id__in=[self.initial_data["bk_biz_id"], GLOBAL_BIZ_ID]
        )
        if self.instance:
            query_result = query_result.exclude(id=self.instance.id)
        if query_result.exists():
            raise ValidationError(detail=_("当前业务下已经存在优先级别为({})的分派规则组，请重新确认").format(value))
        return value

    def validate_name(self, value):
        if value.startswith("集成内置") or value.startswith("Datalink BuiltIn"):
            raise ValidationError(detail="Name starts with 'Datalink BuiltIn' and '集成内置' is forbidden")
        query_result = AlertAssignGroup.objects.filter(
            name=value, bk_biz_id__in=[self.initial_data["bk_biz_id"], GLOBAL_BIZ_ID]
        )
        if self.instance:
            query_result = query_result.exclude(id=self.instance.id)
        if query_result.exists():
            raise ValidationError(detail=_("当前业务下已经存在名称为({})的分派规则组，请重新确认").format(value))
        return value

    def validate(self, attrs):
        if self.instance and self.instance == DATALINK_SOURCE:
            # 数据链路内置策略无法修改
            raise ValidationError(detail="Edit datalink builtin rules is forbidden")
        return super(AssignGroupSlz, self).validate(attrs)

    def to_representation(self, instance):
        data = super(AssignGroupSlz, self).to_representation(instance)
        data["edit_allowed"] = False if instance.source == DATALINK_SOURCE else True
        return data


class BatchAssignRulesSlz(serializers.Serializer):
    assign_group_id = serializers.IntegerField(label="规则组ID", required=False, default=None)
    priority = serializers.IntegerField(label="优先级", required=False)
    bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
    group_name = serializers.CharField(label="规则组名称", required=False)
    rules = serializers.ListSerializer(label="规则列表", required=False, child=BaseAlertAssignRuleSlz(), default=[])

    def to_internal_value(self, data):
        self.initial_data = data
        internal_data = super(BatchAssignRulesSlz, self).to_internal_value(data)
        for rule in internal_data["rules"]:
            rule.update(
                {
                    "bk_biz_id": internal_data["bk_biz_id"],
                    "assign_group_id": internal_data["assign_group_id"],
                }
            )
        return internal_data

    def validate_priority(self, value):
        """
        优先级校验，同一个业务下的优先级别需要唯一
        """
        query_result = AlertAssignGroup.objects.filter(
            priority=value, bk_biz_id__in=[self.initial_data["bk_biz_id"], GLOBAL_BIZ_ID]
        )
        if self.initial_data.get("assign_group_id"):
            query_result = query_result.exclude(id=self.initial_data["assign_group_id"])
        if query_result.exists():
            raise ValidationError(detail=_("当前业务下已经存在优先级别为({})的分派规则组，请重新确认").format(value))
        return value

    def validate_name(self, value):
        """
        分派名称校验，同一个业务下的优先级别需要唯一
        """
        if value.startswith("集成内置") or value.startswith("Datalink BuiltIn"):
            raise ValidationError(detail="Name starts with 'Datalink BuiltIn' and '集成内置' is forbidden")

        query_result = AlertAssignGroup.objects.filter(
            name=value, bk_biz_id__in=[self.initial_data["bk_biz_id"], GLOBAL_BIZ_ID]
        )
        if self.initial_data.get("assign_group_id"):
            query_result = query_result.exclude(id=self.initial_data["assign_group_id"])
        if query_result.exists():
            raise ValidationError(detail=_("当前业务下已经存在名称为({})的分派规则组，请重新确认").format(value))
        return value

    def validate_rules(self, value):
        for rule in value:
            for action in rule.get("actions", []):
                if action["action_type"] != ActionPluginType.NOTICE:
                    continue
                if not action.get("upgrade_config", {}).get("is_enabled"):
                    continue
                if set(action["upgrade_config"]["user_groups"]) & set(rule.get("user_groups", [])):
                    raise ValidationError(detail=_("通知升级的用户组不能包含第一次接收告警的用户组"))
        return value


class BatchSaveAssignRulesSlz(BatchAssignRulesSlz):
    priority = serializers.IntegerField(label="优先级", required=True)
    name = serializers.CharField(label="规则组名称", required=True)

    def validate_group_name(self, value):
        return self.validate_name(value)

    def validate_assign_group_id(self, value):
        if value and AlertAssignGroup.objects.filter(id=value, source=DATALINK_SOURCE).exists():
            raise ValidationError(detail="Edit datalink builtin rules is forbidden")
        return value

    @staticmethod
    def save(validated_data):
        """
        保存分派告警组和规则
        """
        new_rules = []
        existed_rules = []
        group_id = validated_data.get("assign_group_id")
        if group_id:
            group = AlertAssignGroup.objects.get(id=group_id)
            group.name = validated_data["name"]
            group.priority = validated_data["priority"]
            group.hash = ""
            group.snippet = ""
            group.save()
        else:
            group = AlertAssignGroup.objects.create(
                name=validated_data["name"],
                priority=validated_data["priority"],
                bk_biz_id=validated_data["bk_biz_id"],
            )
            group_id = group.id

        for rule in validated_data["rules"]:
            rule_id = rule.pop("id", None)
            rule["assign_group_id"] = group_id
            rule["bk_biz_id"] = group.bk_biz_id
            if rule_id:
                existed_rules.append(rule_id)
                AlertAssignRule.objects.filter(id=rule_id, assign_group_id=group_id).update(**rule)
                continue
            new_rules.append(AlertAssignRule(**rule))
        aborted_rules = list(
            AlertAssignRule.objects.filter(assign_group_id=group_id)
            .exclude(id__in=existed_rules)
            .values_list("id", flat=True)
        )
        if aborted_rules:
            # 删除掉已有的废弃的规则
            AlertAssignRule.objects.filter(assign_group_id=group_id, id__in=aborted_rules).delete()

        AlertAssignRule.objects.bulk_create(new_rules)

        new_rules = AlertAssignRule.objects.filter(assign_group_id=group_id).values_list("id", flat=True)
        return {
            "bk_biz_id": validated_data["bk_biz_id"],
            "assign_group_id": group_id,
            "rules": list(new_rules),
            "aborted_rules": aborted_rules,
        }
