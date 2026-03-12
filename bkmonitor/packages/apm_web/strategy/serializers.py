"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from bk_monitor_base.strategy import THRESHOLD_ALLOWED_METHODS
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apm_web.models import StrategyInstance, StrategyTemplate
from apm_web.strategy.helper import get_user_groups, simplify_conditions

from . import constants


class DetectSerializer(serializers.Serializer):
    class DefaultDetectConfigSerializer(serializers.Serializer):
        recovery_check_window = serializers.IntegerField(label=_("恢复检查窗口"), min_value=1, default=5)
        trigger_check_window = serializers.IntegerField(label=_("触发检查窗口"), min_value=1)
        trigger_count = serializers.IntegerField(label=_("触发次数"), min_value=1)

    type = serializers.CharField(label=_("类型"), default=constants.DEFAULT_DETECT_TYPE)
    config = serializers.DictField(label=_("判断条件配置"), default={})
    connector = serializers.ChoiceField(
        label=_("同级别告警连接关系"),
        choices=constants.DetectConnector.choices(),
        default=constants.DetectConnector.AND.value,
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["type"] == constants.DEFAULT_DETECT_TYPE:
            s = self.DefaultDetectConfigSerializer(data=attrs["config"])
            s.is_valid(raise_exception=True)
            attrs["config"] = s.validated_data
        return super().validate(attrs)


class UserGroupSerializer(serializers.Serializer):
    id = serializers.IntegerField(label=_("用户组 ID"), min_value=1)
    name = serializers.CharField(label=_("用户组名称"))


class AlgorithmSerializer(serializers.Serializer):
    class ThresholdAlgorithmConfigSerializer(serializers.Serializer):
        method = serializers.ChoiceField(label=_("检测方法"), choices=list(THRESHOLD_ALLOWED_METHODS.keys()))
        threshold = serializers.FloatField(label=_("阈值"))

    class YearRoundAndRingRatioAlgorithmConfigSerializer(serializers.Serializer):
        method = serializers.ChoiceField(
            label=_("检测方法"), choices=constants.AlgorithmYearRoundAndRingRatioMethod.choices()
        )
        ceil = serializers.FloatField(label=_("上升"))
        floor = serializers.FloatField(label=_("下降"))

    TYPE_SERIALIZER_MAP = {
        constants.AlgorithmType.THRESHOLD.value: ThresholdAlgorithmConfigSerializer,
        constants.AlgorithmType.YEAR_ROUND_AND_RING_RATIO.value: YearRoundAndRingRatioAlgorithmConfigSerializer,
    }

    level = serializers.ChoiceField(label=_("级别"), choices=constants.ThresholdLevel.choices())
    type = serializers.ChoiceField(
        label=_("检测算法类型"),
        choices=constants.AlgorithmType.choices(),
        default=constants.AlgorithmType.THRESHOLD.value,
    )
    config = serializers.DictField(label=_("检测算法配置"), default={})
    unit_prefix = serializers.CharField(label=_("单位前缀"), default="", allow_blank=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        s = self.TYPE_SERIALIZER_MAP[attrs["type"]](data=attrs["config"])
        s.is_valid(raise_exception=True)
        attrs["config"] = s.validated_data
        return super().validate(attrs)


class AlgorithmListSerializer(serializers.Serializer):
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        algorithms: list[dict[str, Any]] | None = attrs.get("algorithms")
        if not algorithms:
            return super().validate(attrs)
        level_type_set: set[tuple[str, str]] = set()
        for algorithm in algorithms:
            level_type = (algorithm["level"], algorithm["type"])
            if level_type not in level_type_set:
                level_type_set.add(level_type)
            else:
                raise serializers.ValidationError(
                    _("「{}」级别「{}」算法至多选一次").format(
                        constants.ThresholdLevel.from_value(algorithm["level"]).label,
                        constants.AlgorithmType.from_value(algorithm["type"]).label,
                    )
                )
        return super().validate(attrs)


class BaseAppStrategyTemplateRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
    app_name = serializers.CharField(label=_("应用名称"), max_length=50)


class BaseServiceStrategyTemplateRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    service_name = serializers.CharField(label=_("服务名称"))


class BaseEditDataSerializer(AlgorithmListSerializer):
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs.get("is_enabled") is False:
            if attrs.get("is_auto_apply"):
                raise serializers.ValidationError(_("策略模板禁用时，不允许配置自动下发"))
            attrs["is_auto_apply"] = False
        user_group_list: list[dict[str, int | str]] | None = attrs.pop("user_group_list", None)
        if user_group_list is not None:
            user_groups = get_user_groups([user_group_dict["id"] for user_group_dict in user_group_list])
            not_exist_names = [
                user_group_dict["name"]
                for user_group_dict in user_group_list
                if user_group_dict["id"] not in user_groups
            ]
            if not_exist_names:
                raise serializers.ValidationError(
                    _("不存在名称为 {names} 的告警组").format(names=", ".join(not_exist_names))
                )
            attrs["user_group_ids"] = [user_group_dict["id"] for user_group_dict in user_group_list]
        return super().validate(attrs)


class StrategyTemplatePreviewRequestSerializer(BaseServiceStrategyTemplateRequestSerializer):
    strategy_template_id = serializers.IntegerField(label=_("策略模板 ID"), min_value=1)


class StrategyTemplateDetailRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    pass


class StrategyTemplateApplyRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    class GlobalConfigSerializer(serializers.Serializer):
        detect = DetectSerializer(label=_("判断条件"), required=False)
        user_group_list = serializers.ListField(label=_("用户组列表"), child=UserGroupSerializer(), required=False)

    class ExtraConfigSerializer(GlobalConfigSerializer, AlgorithmListSerializer):
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

    is_reuse_instance_config = serializers.BooleanField(label=_("是否复用已有策略配置"), default=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        # 校验 strategy_template_ids 是否有效
        strategy_templates: list[dict[str, Any]] = list(
            StrategyTemplate.objects.filter(
                bk_biz_id=attrs["bk_biz_id"],
                app_name=attrs["app_name"],
                id__in=attrs["strategy_template_ids"],
                is_enabled=True,
            ).values("id", "root_id")
        )
        if len(strategy_templates) != len(set(attrs["strategy_template_ids"])):
            raise serializers.ValidationError(_("数据异常，部分策略模板不存在或已禁用"))
        # 不允许存在同源的模板
        root_template_ids: set[int] = set()
        for strategy_template in strategy_templates:
            root_template_id = (
                strategy_template["id"]
                if strategy_template["root_id"] == constants.DEFAULT_ROOT_ID
                else strategy_template["root_id"]
            )
            if root_template_id in root_template_ids:
                raise serializers.ValidationError(_("下发模板时，不允许存在同源的模板"))
            root_template_ids.add(root_template_id)
        return super().validate(attrs)


class StrategyTemplateUnapplyResponseSerializer(BaseAppStrategyTemplateRequestSerializer):
    service_names = serializers.ListField(label=_("服务名称列表"), child=serializers.CharField())
    strategy_template_ids = serializers.ListField(
        label=_("策略模板 ID 列表"), child=serializers.IntegerField(min_value=1)
    )


class StrategyTemplateCheckRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    # TODO 默认值暂时改为 true 以供联调
    is_check_diff = serializers.BooleanField(label=_("是否检查变更"), default=True)
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

        def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
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
            return super().validate(attrs)

    conditions = serializers.ListField(label=_("查询条件"), child=ConditionSerializer(), default=[], allow_empty=True)
    page = serializers.IntegerField(label=_("页码"), min_value=1, default=1)
    page_size = serializers.IntegerField(label=_("分页大小"), min_value=1, default=50)
    order_by = serializers.ListField(
        label=_("排序字段"),
        child=serializers.ChoiceField(choices=["update_time", "-update_time", "create_time", "-create_time"]),
        default=["-update_time"],
        allow_empty=True,
    )
    simple = serializers.BooleanField(label=_("是否仅返回概要信息"), default=False)


class BaseStrategyTemplateUpdateSerializer(BaseEditDataSerializer):
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
    pass


class StrategyTemplateCloneRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    source_id = serializers.IntegerField(label=_("源策略模板 ID"), min_value=1)
    edit_data = BaseStrategyTemplateUpdateSerializer(label=_("克隆模板编辑数据"))


class StrategyTemplateBatchPartialUpdateRequestSerializer(BaseAppStrategyTemplateRequestSerializer):
    EDITABLE_FIELDS: list[str] = [
        "user_group_ids",
        "detect",
        "algorithms",
        "is_enabled",
        "is_auto_apply",
        "update_user",
        "update_time",
    ]

    class EditDataSerializer(BaseEditDataSerializer):
        user_group_list = serializers.ListField(
            label=_("用户组列表"), child=UserGroupSerializer(), required=False, allow_empty=False
        )
        detect = DetectSerializer(label=_("判断条件"), required=False)
        algorithms = serializers.ListField(
            label=_("检测算法列表"), child=AlgorithmSerializer(), required=False, allow_empty=False
        )
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
    system = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
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

    def get_applied_service_names(self, obj: StrategyTemplate) -> list[str]:
        return self._applied_service_names_by_id.get(obj.pk, [])

    @staticmethod
    def get_system(obj: StrategyTemplate):
        return {"value": obj.system, "alias": constants.StrategyTemplateSystem.from_value(obj.system).label}

    @staticmethod
    def get_category(obj: StrategyTemplate):
        return {"value": obj.category, "alias": constants.StrategyTemplateCategory.from_value(obj.category).label}


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

    @staticmethod
    def validate_auto_apply(strategy_template_objs: list[StrategyTemplate] | None, data: dict[str, Any]):
        """限制同源模板间只能有一个自动下发模板

        :param strategy_template_objs: 要更新的策略模板对象列表，为None表示创建新模板
        :param data: 数据字典
        """
        if not data.get("is_auto_apply"):
            return

        base_qs: QuerySet[StrategyTemplate] = StrategyTemplate.objects.filter(
            bk_biz_id=data["bk_biz_id"], app_name=data["app_name"]
        )
        if strategy_template_objs is None:
            other_same_origin_qs: QuerySet[StrategyTemplate] = StrategyTemplate.filter_same_origin_templates(
                qs=base_qs, ids=[], root_ids=[data["root_id"]]
            )
        else:
            tmpl_ids: list[int] = []
            root_ids: list[int] = []
            root_tmpl_id_tmpl_names: dict[int, list[str]] = defaultdict(list)
            for tmpl_obj in strategy_template_objs:
                tmpl_ids.append(tmpl_obj.pk)
                root_ids.append(tmpl_obj.root_id)
                # 获取根模板的 ID
                root_tmpl_id = tmpl_obj.root_id if tmpl_obj.root_id != constants.DEFAULT_ROOT_ID else tmpl_obj.pk
                root_tmpl_id_tmpl_names[root_tmpl_id].append(tmpl_obj.name)

            same_origin_tmpl_names_str: list[str] = []
            for tmpl_names in root_tmpl_id_tmpl_names.values():
                if len(tmpl_names) > 1:
                    same_origin_tmpl_names_str.append("[" + "、".join(tmpl_names) + "]")
            if same_origin_tmpl_names_str:
                raise serializers.ValidationError(
                    _("同类别的模板不能同时启用「自动下发」：{}").format(", ".join(same_origin_tmpl_names_str))
                )

            other_same_origin_qs: QuerySet[StrategyTemplate] = StrategyTemplate.filter_same_origin_templates(
                qs=base_qs, ids=tmpl_ids, root_ids=root_ids
            ).exclude(id__in=tmpl_ids)

        if other_same_origin_qs.filter(is_auto_apply=True).exists():
            raise serializers.ValidationError(_("同类别的模板间只允许设置一个自动下发"))

    @staticmethod
    def _validate_name(qs: QuerySet[StrategyTemplate], data: dict[str, Any]) -> None:
        if qs.filter(bk_biz_id=data["bk_biz_id"], app_name=data["app_name"], name=data["name"]).exists():
            raise serializers.ValidationError(_("同一应用下策略模板名称不能重复"))

    @staticmethod
    def _validate_context(data: dict[str, Any]) -> None:
        conditions: Any = data.get("context", {}).get("CONDITIONS")
        if conditions and isinstance(conditions, list):
            simplified_conditions = simplify_conditions(conditions)
            data["context"]["CONDITIONS"] = simplified_conditions

    @classmethod
    def set_auto_apply(
        cls, data: dict[str, Any], instance: StrategyTemplate, auto_applied_at: datetime.datetime | None = None
    ):
        """设置自动下发相关字段"""
        is_to_be_auto_applied: bool = data.get("is_auto_apply") and not instance.is_auto_apply
        if is_to_be_auto_applied:
            data["auto_applied_at"] = auto_applied_at or timezone.now()

    def update(self, instance: StrategyTemplate, validated_data: dict[str, Any]) -> StrategyTemplate:
        self._validate_context(validated_data)
        self._validate_name(StrategyTemplate.origin_objects.exclude(pk=instance.pk), validated_data)
        self.validate_auto_apply([instance], validated_data)
        self.set_auto_apply(validated_data, instance)
        return super().update(instance, validated_data)

    def create(self, validated_data: dict[str, Any]) -> StrategyTemplate:
        self._validate_context(validated_data)
        self._validate_name(StrategyTemplate.origin_objects.all(), validated_data)
        self.validate_auto_apply(None, validated_data)
        instance: StrategyTemplate = super().create(validated_data)
        if instance.is_auto_apply:
            StrategyTemplate.objects.filter(id=instance.pk).update(auto_applied_at=instance.create_time)
        return instance


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
            "detect",
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
        fields = ["id", "name", "system", "category", "monitor_type", "code", "type"]
