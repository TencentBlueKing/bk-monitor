"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any
from collections.abc import Iterable
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from django.utils.functional import cached_property

from bkmonitor.models import UserGroup, AlgorithmModel
from bkmonitor.strategy.serializers import allowed_threshold_method

from . import constants
from apm_web.models import StrategyTemplate, StrategyInstance


def get_user_groups(user_group_ids: Iterable[int]) -> dict[int, dict[str, int | str]]:
    return {
        user_group["id"]: user_group
        for user_group in UserGroup.objects.filter(id__in=user_group_ids).values("id", "name")
    }


class DetectSerializer(serializers.Serializer):
    class DefaultDetectConfigSerializer(serializers.Serializer):
        recovery_check_window = serializers.IntegerField(label=_("恢复检查窗口"), min_value=1, default=5)
        trigger_check_window = serializers.IntegerField(label=_("触发检查窗口"), min_value=1)
        trigger_count = serializers.IntegerField(label=_("触发次数"), min_value=1)

    type = serializers.CharField(label=_("类型"), default=constants.DEFAULT_DETECT_TYPE)
    config = serializers.DictField(label=_("判断条件配置"), default={})

    def validate(self, attrs: dict) -> dict:
        if attrs["type"] == constants.DEFAULT_DETECT_TYPE:
            s = self.DefaultDetectConfigSerializer(data=attrs["config"])
            s.is_valid(raise_exception=True)
            attrs["config"] = s.validated_data
        return attrs


class UserGroupSerializer(serializers.Serializer):
    id = serializers.IntegerField(label=_("用户组 ID"), min_value=1)
    name = serializers.CharField(label=_("用户组名称"))


class AlgorithmSerializer(serializers.Serializer):
    class ThresholdAlgorithmConfigSerializer(serializers.Serializer):
        method = serializers.ChoiceField(label=_("检测方法"), choices=allowed_threshold_method)
        threshold = serializers.FloatField(label=_("阈值"))

    level = serializers.ChoiceField(label=_("级别"), choices=constants.ThresholdLevel.choices())
    type = serializers.ChoiceField(
        label=_("检测算法类型"),
        choices=AlgorithmModel.ALGORITHM_CHOICES,
        default=AlgorithmModel.AlgorithmChoices.Threshold,
    )
    config = serializers.DictField(label=_("检测算法配置"), default={})

    def validate(self, attrs: dict) -> dict:
        if attrs["type"] == AlgorithmModel.AlgorithmChoices.Threshold:
            s = self.ThresholdAlgorithmConfigSerializer(data=attrs["config"])
            s.is_valid(raise_exception=True)
            attrs["config"] = s.validated_data
        return attrs


class BaseAppStrategyTemplateRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
    app_name = serializers.CharField(label=_("应用名称"), max_length=50)
    is_mock = serializers.BooleanField(label=_("是否为 mock 数据"), default=True)


class BaseServiceStrategyTemplateRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    service_name = serializers.CharField(label=_("服务名称"))


class StrategyTemplatePreviewRequestSerializer(BaseServiceStrategyTemplateRequestSerializer):
    strategy_template_id = serializers.IntegerField(label=_("策略模板 ID"), min_value=1)


class StrategyTemplateDetailRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    pass


class StrategyTemplateApplyRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    class GlobalConfigSerializer(serializers.Serializer):
        detect = DetectSerializer(label=_("判断条件"), required=False)
        user_group_list = serializers.ListField(label=_("用户组列表"), child=UserGroupSerializer(), required=False)

    class ExtraConfigSerializer(GlobalConfigSerializer):
        strategy_template_id = serializers.IntegerField(label=_("策略模板 ID"), min_value=1)
        service_name = serializers.CharField(label=_("服务名称"))
        context = serializers.DictField(label=_("查询模板的变量上下文"), required=False)
        algorithms = serializers.ListField(label=_("检测算法列表"), child=AlgorithmSerializer(), required=False)

    service_names = serializers.ListField(label=_("服务名称列表"), child=serializers.CharField())
    strategy_template_ids = serializers.ListField(
        label=_("策略模板 ID 列表"), child=serializers.IntegerField(min_value=1)
    )
    extra_configs = serializers.ListField(
        label=_("额外编辑的配置"), child=ExtraConfigSerializer(), default=[], allow_empty=True
    )
    global_config = GlobalConfigSerializer(label=_("批量修改的配置"), default={})


class StrategyTemplateCheckRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    service_names = serializers.ListField(
        label=_("服务名称列表"), child=serializers.CharField(), default=[], allow_empty=True
    )
    strategy_template_ids = serializers.ListField(
        label=_("策略模板 ID 列表"), child=serializers.IntegerField(min_value=1), default=[], allow_empty=True
    )


class StrategyTemplateSearchRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    class ConditionSerializer(serializers.Serializer):
        FIELD_TYPE_VALIDATION_RULES = [
            {
                "type": str,
                "type_alias": _("字符串"),
                "fields": {"query", "type", "name", "system", "update_user", "applied_service_name"},
            },
            {
                "type": bool,
                "type_alias": _("布尔值"),
                "fields": {"is_enabled", "is_auto_apply"},
            },
            {
                "type": int,
                "type_alias": _("整数"),
                "fields": {"user_group_id"},
            },
        ]
        key = serializers.ChoiceField(
            label=_("查询字段"),
            choices=[
                "query",
                "type",
                "name",
                "user_group_id",
                "system",
                "update_user",
                "applied_service_name",
                "is_enabled",
                "is_auto_apply",
            ],
        )
        value = serializers.ListField(label=_("字段值"), child=serializers.JSONField())

        def validate(self, attrs: dict) -> dict:
            error_message: str = _("查询字段为 {key} 时，字段值类型必须为 {value_type}")
            for rule in self.FIELD_TYPE_VALIDATION_RULES:
                if attrs["key"] not in rule["fields"]:
                    continue
                for v in attrs["value"]:
                    if not isinstance(v, rule["type"]):
                        raise serializers.ValidationError(
                            error_message.format(key=attrs["key"], value_type=rule["type_alias"])
                        )
                break
            return attrs

    conditions = serializers.ListField(label=_("查询条件"), child=ConditionSerializer(), default=[], allow_empty=True)
    page = serializers.IntegerField(label=_("页码"), min_value=1, default=1)
    page_size = serializers.IntegerField(label=_("分页大小"), min_value=1, default=50)
    simple = serializers.BooleanField(label=_("是否仅返回概要信息"), default=False)


class BaseStrategyTemplateUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(label=_("策略模板名称"))
    algorithms = serializers.ListField(label=_("检测算法列表"), child=AlgorithmSerializer())
    detect = DetectSerializer(label=_("判断条件"))
    user_group_list = serializers.ListField(label=_("用户组列表"), child=UserGroupSerializer())
    context = serializers.DictField(label=_("查询模板的变量上下文"), default={})
    is_enabled = serializers.BooleanField(label=_("是否启用"), default=True)
    is_auto_apply = serializers.BooleanField(label=_("是否自动下发"), default=False)


class StrategyTemplateUpdateRequestSerializer(
    BaseStrategyTemplateUpdateSerializer, BaseAppStrategyTemplateRequestSerializer
):
    def validate(self, attrs: dict) -> dict:
        if not attrs["is_enabled"] and attrs["is_auto_apply"]:
            raise serializers.ValidationError(_("策略模板禁用时，不允许配置自动下发"))

        user_group_list: list[dict[str, int | str]] = attrs["user_group_list"]
        user_groups = get_user_groups([user_group["id"] for user_group in user_group_list])
        not_exist_names = [user_group["name"] for user_group in user_group_list if user_group["id"] not in user_groups]
        if not_exist_names:
            raise serializers.ValidationError(
                _("不存在名称为 {names} 的告警组").format(names=", ".join(not_exist_names))
            )
        return attrs


class StrategyTemplateCloneRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    source_id = serializers.IntegerField(label=_("源策略模板 ID"), min_value=1)
    edit_data = BaseStrategyTemplateUpdateSerializer(label=_("克隆模板编辑数据"))


class StrategyTemplateBatchPartialUpdateRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    class EditDataSerializer(serializers.Serializer):
        user_group_list = serializers.ListField(label=_("用户组列表"), child=UserGroupSerializer(), required=False)
        algorithms = serializers.ListField(label=_("检测算法列表"), child=AlgorithmSerializer(), required=False)
        is_enabled = serializers.BooleanField(label=_("是否启用"), required=False)
        is_auto_apply = serializers.BooleanField(label=_("是否自动下发"), required=False)

    ids = serializers.ListField(label=_("策略模板 ID 列表"), child=serializers.IntegerField(min_value=1))
    edit_data = EditDataSerializer(label=_("批量编辑数据"))


class StrategyTemplateCompareRequestSerializer(BaseServiceStrategyTemplateRequestSerializer):
    strategy_template_id = serializers.IntegerField(label=_("策略模板 ID"), min_value=1)


class StrategyTemplateAlertsRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    ids = serializers.ListField(label=_("策略模板 ID 列表"), child=serializers.IntegerField(min_value=1))
    need_strategies = serializers.BooleanField(label=_("是否需要策略列表"), default=False)


class StrategyTemplateDeleteRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    pass


class StrategyTemplateOptionValuesRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    fields = serializers.ListField(
        label=_("字段列表"),
        child=serializers.ChoiceField(
            choices=["system", "update_user", "applied_service_name", "user_group_id", "is_enabled", "is_auto_apply"]
        ),
        default=[],
        allow_empty=True,
    )


class StrategyTemplateBaseModelSerializer(serializers.ModelSerializer):
    user_group_list = serializers.SerializerMethodField()
    applied_service_names = serializers.SerializerMethodField()

    class Meta:
        model = StrategyTemplate
        fields = "__all__"

    @cached_property
    def _strategy_template_objs(self) -> Iterable[StrategyTemplate]:
        if isinstance(self.instance, Iterable):
            return self.instance
        elif self.instance is None:
            return []
        return [self.instance]

    @cached_property
    def _user_groups(self) -> dict[int, dict[str, int | str]]:
        user_group_ids = set(
            user_group_id for obj in self._strategy_template_objs for user_group_id in obj.user_group_ids
        )
        return get_user_groups(user_group_ids)

    @cached_property
    def _strategy_instances(self) -> list[dict[str, int | str]]:
        strategy_template_ids = set(obj.pk for obj in self._strategy_template_objs)
        return list(
            StrategyInstance.objects.filter(strategy_template_id__in=strategy_template_ids).values(
                "strategy_template_id", "service_name"
            )
        )

    @cached_property
    def _applied_service_names_by_id(self) -> dict[int, list[str]]:
        applied_service_names_by_id = {}
        for instance in self._strategy_instances:
            applied_service_names_by_id.setdefault(instance["strategy_template_id"], []).append(
                instance["service_name"]
            )
        return applied_service_names_by_id

    def get_user_group_list(self, obj: StrategyTemplate) -> list[dict[str, int | str]]:
        return [
            self._user_groups[user_group_id]
            for user_group_id in obj.user_group_ids
            if user_group_id in self._user_groups
        ]

    def get_applied_service_names(self, obj) -> list[str]:
        return self._applied_service_names_by_id.get(obj.pk, [])


class StrategyTemplateModelSerializer(StrategyTemplateBaseModelSerializer):
    class Meta:
        model = StrategyTemplate
        fields = [
            "id",
            "code",
            "name",
            "type",
            "is_enabled",
            "is_auto_apply",
            "system",
            "category",
            "detect",
            "algorithms",
            "user_group_list",
            "query_template",
            "context",
            "applied_service_names",
        ]

    def update(self, instance: StrategyTemplate, validated_data: dict[str, Any]) -> StrategyTemplate:
        validated_data["user_group_ids"] = [user_group["id"] for user_group in validated_data.pop("user_group_list")]
        return super().update(instance, validated_data)


class StrategyTemplateSearchModelSerializer(StrategyTemplateBaseModelSerializer):
    class Meta:
        model = StrategyTemplate
        fields = [
            "id",
            "name",
            "system",
            "category",
            "monitor_type",
            "type",
            "is_enabled",
            "is_auto_apply",
            "algorithms",
            "user_group_list",
            "applied_service_names",
            "create_user",
            "create_time",
            "update_user",
            "update_time",
        ]


class StrategyTemplateSimpleSearchModelSerializer(StrategyTemplateBaseModelSerializer):
    class Meta:
        model = StrategyTemplate
        fields = [
            "id",
            "name",
            "system",
            "category",
            "monitor_type",
        ]
