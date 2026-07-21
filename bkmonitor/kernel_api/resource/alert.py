"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# -*- coding: utf-8 -*-
import hashlib
import json
from copy import deepcopy
from typing import Any

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.documents import AlertDocument
from bkmonitor.models import ActionConfig, DutyRule, StrategyModel, UserGroup
from bkmonitor.strategy.new_strategy import Strategy, get_metric_id
from core.drf_resource import Resource, resource
from fta_web.alert.resources import AlertTopNResource as FtaAlertTopNResource
from fta_web.alert.resources import ListAlertTagsResource  # noqa
from fta_web.alert.resources import SearchAlertByEventResource, SearchAlertResource  # noqa
from fta_web.alert.resources import StrategySnapshotResource as FtaStrategySnapshotResource
from fta_web.alert_v2.resources import (
    AlertEventsResource as FtaAlertEventsResource,
    AlertEventTagDetailResource as FtaAlertEventTagDetailResource,
    AlertEventTSResource as FtaAlertEventTSResource,
    AlertHostTargetResource as FtaAlertHostTargetResource,
    AlertK8sTargetResource as FtaAlertK8sTargetResource,
    AlertLogRelationListResource as FtaAlertLogRelationListResource,
    AlertTracesResource as FtaAlertTracesResource,
)
from kernel_api.serializers.mixins import TimeSpanValidationPassThroughSerializer


class PassThroughSerializer(serializers.Serializer):
    """校验声明字段，同时透传底层 Resource 负责校验的业务参数。"""

    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        validated_data = super().to_internal_value(data)
        final_data = data.dict() if hasattr(data, "dict") else dict(data)
        final_data.update(validated_data)
        return final_data


class BusinessScopedSerializer(PassThroughSerializer):
    bk_biz_id = serializers.IntegerField(required=True, label="业务ID")


class AlertRelatedRequestSerializer(BusinessScopedSerializer):
    alert_id = serializers.CharField(required=True, label="告警ID")


class ConfirmedBusinessScopedSerializer(BusinessScopedSerializer):
    confirm = serializers.BooleanField(required=True, label="确认执行写操作")

    def validate_confirm(self, value: bool) -> bool:
        if not value:
            raise ValidationError("写操作必须由用户确认，请设置 confirm=true")
        return value


class ShieldNoticeConfigSerializer(serializers.Serializer):
    notice_time = serializers.IntegerField(required=True)
    notice_way = serializers.ListField(
        required=True,
        allow_empty=False,
        child=serializers.ChoiceField(choices=["weixin", "mail", "sms", "voice"]),
    )
    notice_receiver = serializers.ListField(required=True, allow_empty=False)

    def validate_notice_receiver(self, receivers):
        return normalize_shield_notice_config({"notice_receiver": receivers})["notice_receiver"]


class ActionExecuteConfigSerializer(serializers.Serializer):
    template_detail = serializers.JSONField(required=True)
    template_id = serializers.CharField(required=False, allow_blank=True)
    timeout = serializers.IntegerField(required=True, min_value=60, max_value=7 * 24 * 60 * 60)


def merge_nested_dict(current: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """递归合并字典；数组和标量按请求值完整替换。"""

    merged = deepcopy(current)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_nested_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def remove_confirm(validated_request_data: dict[str, Any]) -> dict[str, Any]:
    request_data = dict(validated_request_data)
    request_data.pop("confirm", None)
    return request_data


def ensure_strategy_ids_belong_to_biz(bk_biz_id: int, strategy_ids: list[int]) -> None:
    existing_ids = set(
        StrategyModel.objects.filter(bk_biz_id=bk_biz_id, id__in=strategy_ids).values_list("id", flat=True)
    )
    missing_ids = set(strategy_ids) - existing_ids
    if missing_ids:
        raise ValidationError({"ids": f"业务 {bk_biz_id} 下不存在策略: {sorted(missing_ids)}"})


def get_strategy_config_version(config: dict[str, Any]) -> str:
    version_data = dict(config)
    version_data.pop("config_version", None)
    serialized = json.dumps(
        version_data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def ensure_strategy_relations_belong_to_biz(bk_biz_id: int, request_data: dict[str, Any]) -> None:
    user_group_ids = set()
    action_config_ids = set()

    def add_ids(target: set[int], values: list[Any], field: str) -> None:
        if not isinstance(values, list | tuple | set):
            raise ValidationError({field: "必须为 ID 数组"})
        try:
            target.update(int(value) for value in values)
        except (TypeError, ValueError):
            raise ValidationError({field: "ID 必须为整数"})

    notice = request_data.get("notice") or {}
    if not isinstance(notice, dict):
        raise ValidationError({"notice": "必须为对象"})
    add_ids(user_group_ids, notice.get("user_groups") or [], "notice.user_groups")
    notice_options = notice.get("options") or {}
    if not isinstance(notice_options, dict):
        raise ValidationError({"notice.options": "必须为对象"})
    upgrade_config = notice_options.get("upgrade_config") or {}
    if not isinstance(upgrade_config, dict):
        raise ValidationError({"notice.options.upgrade_config": "必须为对象"})
    add_ids(
        user_group_ids,
        upgrade_config.get("user_groups") or [],
        "notice.options.upgrade_config.user_groups",
    )

    actions = request_data.get("actions") or []
    if not isinstance(actions, list):
        raise ValidationError({"actions": "必须为数组"})
    for action in actions:
        if not isinstance(action, dict):
            raise ValidationError({"actions": "每个处理套餐必须为对象"})
        add_ids(user_group_ids, action.get("user_groups") or [], "actions.user_groups")
        if action.get("config_id"):
            add_ids(action_config_ids, [action["config_id"]], "actions.config_id")

    if request_data.get("notice_group_list"):
        add_ids(user_group_ids, request_data["notice_group_list"], "notice_group_list")

    existing_user_group_ids = set(
        UserGroup.objects.filter(bk_biz_id=bk_biz_id, id__in=user_group_ids).values_list("id", flat=True)
    )
    missing_user_group_ids = user_group_ids - existing_user_group_ids
    if missing_user_group_ids:
        raise ValidationError({"user_groups": f"业务 {bk_biz_id} 下不存在告警组: {sorted(missing_user_group_ids)}"})

    existing_action_config_ids = set(
        ActionConfig.objects.filter(
            bk_biz_id__in=[0, bk_biz_id],
            id__in=action_config_ids,
        )
        .exclude(plugin_id=ActionConfig.NOTICE_PLUGIN_ID)
        .values_list("id", flat=True)
    )
    missing_action_config_ids = action_config_ids - existing_action_config_ids
    if missing_action_config_ids:
        raise ValidationError(
            {"action_configs": f"业务 {bk_biz_id} 下不存在处理套餐: {sorted(missing_action_config_ids)}"}
        )


def ensure_duty_rules_belong_to_biz(bk_biz_id: int, duty_rule_ids: list[int]) -> None:
    existing_ids = set(
        DutyRule.objects.filter(
            bk_biz_id__in=[0, bk_biz_id],
            id__in=duty_rule_ids,
        ).values_list("id", flat=True)
    )
    missing_ids = set(duty_rule_ids) - existing_ids
    if missing_ids:
        raise ValidationError({"duty_rules": f"业务 {bk_biz_id} 下不存在轮值规则: {sorted(missing_ids)}"})


def ensure_alert_belongs_to_biz(bk_biz_id: int, alert_id: str | int) -> AlertDocument:
    alert = AlertDocument.get(alert_id)
    alert_event = getattr(alert, "event", None)
    alert_biz_id = getattr(alert_event, "bk_biz_id", None)
    if str(alert_biz_id) != str(bk_biz_id):
        raise ValidationError({"alert_id": f"业务 {bk_biz_id} 下不存在告警: {alert_id}"})
    return alert


def ensure_shield_belongs_to_biz(bk_biz_id: int, shield_id: int) -> dict[str, Any]:
    shield = resource.shield.shield_detail.request(bk_biz_id=bk_biz_id, id=shield_id)
    if shield["bk_biz_id"] != bk_biz_id:
        raise ValidationError({"id": f"业务 {bk_biz_id} 下不存在屏蔽配置: {shield_id}"})
    return shield


def normalize_shield_notice_config(notice_config: dict[str, Any]) -> dict[str, Any]:
    normalized_config = dict(notice_config)
    normalized_receivers = []
    for receiver in normalized_config.get("notice_receiver") or []:
        if isinstance(receiver, str):
            receiver_type, separator, receiver_id = receiver.partition("#")
            if not separator:
                raise ValidationError({"notice_config.notice_receiver": f"无效的通知接收人: {receiver}"})
            normalized_receivers.append({"type": receiver_type, "id": receiver_id})
        elif isinstance(receiver, dict) and receiver.get("type") and receiver.get("id"):
            normalized_receivers.append(receiver)
        else:
            raise ValidationError({"notice_config.notice_receiver": "通知接收人必须包含 type 和 id"})
    normalized_config["notice_receiver"] = normalized_receivers
    return normalized_config


def normalize_strategy_metric_ids(
    request_data: dict[str, Any],
    current_config: dict[str, Any],
) -> None:
    """根据完整查询配置重算可推导的 metric_id，避免与 PromQL/物理指标字段不一致。"""

    metric_identity_fields = (
        "data_source_label",
        "data_type_label",
        "result_table_id",
        "index_set_id",
        "metric_field",
        "custom_event_name",
        "alert_name",
        "bkmonitor_strategy_id",
        "promql",
    )
    current_query_configs = {
        str(query_config.get("id")): query_config
        for item in current_config.get("items") or []
        for query_config in item.get("query_configs") or []
        if query_config.get("id")
    }
    for item in request_data.get("items") or []:
        query_configs = item.get("query_configs") if isinstance(item, dict) else None
        if not isinstance(query_configs, list) or not query_configs:
            raise ValidationError({"items.query_configs": "必须提供非空查询配置数组"})
        for query_config in query_configs:
            if not isinstance(query_config, dict):
                raise ValidationError({"items.query_configs": "查询配置必须为对象"})
            if not query_config.get("data_source_label") or not query_config.get("data_type_label"):
                raise ValidationError({"items.query_configs": "查询配置必须包含 data_source_label 和 data_type_label"})
            current_query_config = current_query_configs.get(str(query_config.get("id")))
            if current_query_config and all(
                query_config.get(field, "") == current_query_config.get(field, "") for field in metric_identity_fields
            ):
                query_config["metric_id"] = current_query_config.get("metric_id", "")
                continue
            metric_config = dict(query_config)
            metric_config.pop("metric_id", None)
            metric_id = get_metric_id(**metric_config)
            if metric_id:
                query_config["metric_id"] = metric_id


def build_strategy_from_simplified_request(request_data: dict[str, Any]) -> dict[str, Any]:
    """将 MCP 常用的单指标阈值配置转换为完整策略结构。"""

    required_fields = {"metric", "detect", "notice_group_ids"}
    missing_fields = required_fields - request_data.keys()
    if missing_fields:
        raise ValidationError(
            {
                "strategy": (
                    "请提供完整的 items/detects/notice，或提供简化字段 "
                    f"metric/detect/notice_group_ids；缺少: {sorted(missing_fields)}"
                )
            }
        )

    metric = dict(request_data.pop("metric"))
    detect = dict(request_data.pop("detect"))
    notice_group_ids = request_data.pop("notice_group_ids")
    action_config_ids = request_data.pop("action_config_ids", [])

    required_metric_fields = {"data_source_label", "data_type_label", "result_table_id", "metric_field"}
    missing_metric_fields = required_metric_fields - metric.keys()
    if missing_metric_fields:
        raise ValidationError({"metric": f"缺少字段: {sorted(missing_metric_fields)}"})

    required_detect_fields = {"level", "algorithm_type", "trigger_count", "check_window"}
    missing_detect_fields = required_detect_fields - detect.keys()
    if missing_detect_fields:
        raise ValidationError({"detect": f"缺少字段: {sorted(missing_detect_fields)}"})

    if not notice_group_ids:
        raise ValidationError({"notice_group_ids": "至少需要一个告警组"})

    algorithm_type = detect["algorithm_type"]
    algorithm_config = detect.get("config")
    if algorithm_config is None:
        if algorithm_type != "Threshold":
            raise ValidationError({"detect.config": f"{algorithm_type} 算法必须提供 config"})
        if "method" not in detect or "threshold" not in detect:
            raise ValidationError({"detect": "Threshold 算法必须提供 method 和 threshold"})
        algorithm_config = [[{"method": detect["method"], "threshold": detect["threshold"]}]]

    query_config = {
        "alias": metric.pop("alias", "a"),
        "functions": metric.pop("functions", []),
        "agg_method": metric.pop("agg_method", "AVG"),
        "agg_interval": metric.pop("agg_interval", 60),
        "agg_dimension": metric.pop("agg_dimension", []),
        "agg_condition": metric.pop("agg_condition", []),
        "unit": metric.pop("unit", ""),
        **metric,
    }
    item_name = query_config.pop("name", query_config.get("metric_field", request_data["name"]))
    level = detect["level"]
    check_window = detect["check_window"]

    request_data["items"] = [
        {
            "name": item_name,
            "expression": "",
            "origin_sql": "",
            "functions": [],
            "query_configs": [query_config],
            "algorithms": [
                {
                    "type": algorithm_type,
                    "level": level,
                    "config": algorithm_config,
                    "unit_prefix": detect.get("unit_prefix", ""),
                }
            ],
            "no_data_config": detect.get("no_data_config", {"is_enabled": False}),
            "target": detect.get("target", []),
        }
    ]
    request_data["detects"] = [
        {
            "level": level,
            "trigger_config": {
                "count": detect["trigger_count"],
                "check_window": check_window,
            },
            "recovery_config": {
                "check_window": detect.get("recovery_window", check_window),
            },
            "connector": "and",
        }
    ]
    request_data["notice"] = {
        "user_groups": notice_group_ids,
        "signal": ["abnormal", "recovered"],
        "options": {"converge_config": {"need_biz_converge": True}},
        "config": {
            "need_poll": True,
            "notify_interval": 3600,
            "interval_notify_mode": "standard",
            "template": [
                {"signal": "abnormal", "message_tmpl": "", "title_tmpl": ""},
                {"signal": "recovered", "message_tmpl": "", "title_tmpl": ""},
            ],
        },
    }
    request_data["actions"] = [
        {
            "config_id": action_config_id,
            "user_groups": notice_group_ids,
            "signal": ["abnormal"],
            "options": {"converge_config": {"is_enabled": True}},
        }
        for action_config_id in action_config_ids
    ]
    return request_data


class ListAlertResource(Resource):
    """告警列表查询接口 (用于 AI MCP 请求)"""

    RequestSerializer = TimeSpanValidationPassThroughSerializer

    def perform_request(self, validated_request_data):
        return SearchAlertResource().request(**validated_request_data)


class ListAlertTopNResource(Resource):
    """告警 TopN 查询接口 (用于 AI MCP 请求)"""

    RequestSerializer = TimeSpanValidationPassThroughSerializer

    def perform_request(self, validated_request_data):
        return FtaAlertTopNResource().request(**validated_request_data)


class ListStrategySnapshotResource(Resource):
    """告警策略快照查询接口 (用于 AI MCP 请求)

    bk_biz_id 仅用于 MCP 鉴权（中间件层校验），底层 StrategySnapshotResource 仅消费 id。
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=True, label="告警ID")

    def perform_request(self, validated_request_data):
        ensure_alert_belongs_to_biz(validated_request_data["bk_biz_id"], validated_request_data["id"])
        return FtaStrategySnapshotResource().request(id=validated_request_data["id"])


class AlertRelatedResource(Resource):
    """校验告警业务归属后调用关联查询 Resource。"""

    RequestSerializer = AlertRelatedRequestSerializer
    backend_resource_class = None

    def perform_request(self, validated_request_data):
        ensure_alert_belongs_to_biz(validated_request_data["bk_biz_id"], validated_request_data["alert_id"])
        request_data = dict(validated_request_data)
        request_data.pop("bk_biz_id")
        return self.backend_resource_class().request(**request_data)


class ListAlertEventsResource(AlertRelatedResource):
    backend_resource_class = FtaAlertEventsResource


class ListAlertEventTSResource(AlertRelatedResource):
    backend_resource_class = FtaAlertEventTSResource


class ListAlertEventTagDetailResource(AlertRelatedResource):
    backend_resource_class = FtaAlertEventTagDetailResource


class ListAlertK8sTargetResource(AlertRelatedResource):
    backend_resource_class = FtaAlertK8sTargetResource


class ListAlertHostTargetResource(AlertRelatedResource):
    backend_resource_class = FtaAlertHostTargetResource


class ListAlertTracesResource(AlertRelatedResource):
    backend_resource_class = FtaAlertTracesResource


class ListAlertLogRelationsResource(AlertRelatedResource):
    backend_resource_class = FtaAlertLogRelationListResource


class SearchAlarmStrategiesResource(Resource):
    """查询告警策略列表（用于 AI MCP 请求）。"""

    RequestSerializer = BusinessScopedSerializer

    def perform_request(self, validated_request_data):
        return resource.strategies.get_strategy_list_v2.request(**validated_request_data)


class GetAlarmStrategyResource(Resource):
    """通过策略 ID 或名称定位单个告警策略（用于 AI MCP 请求）。"""

    class RequestSerializer(BusinessScopedSerializer):
        class ConditionSerializer(serializers.Serializer):
            key = serializers.ChoiceField(choices=["strategy_id", "strategy_name"])
            value = serializers.ListField(
                allow_empty=False,
                child=serializers.CharField(),
            )

        conditions = serializers.ListField(
            required=True,
            allow_empty=False,
            child=ConditionSerializer(),
            label="策略定位条件",
        )
        with_user_group = serializers.BooleanField(required=False, default=True)
        with_user_group_detail = serializers.BooleanField(required=False, default=False)
        convert_dashboard = serializers.BooleanField(required=False, default=False)

    @staticmethod
    def _candidate(strategy: StrategyModel) -> dict[str, Any]:
        return {
            "id": strategy.id,
            "name": strategy.name,
            "bk_biz_id": strategy.bk_biz_id,
            "scenario": strategy.scenario,
            "is_enabled": strategy.is_enabled,
            "update_time": strategy.update_time,
        }

    def perform_request(self, validated_request_data):
        strategies = StrategyModel.objects.filter(bk_biz_id=validated_request_data["bk_biz_id"])
        for condition in validated_request_data["conditions"]:
            if condition["key"] == "strategy_id":
                strategy_ids = []
                for strategy_id in condition["value"]:
                    try:
                        strategy_ids.append(int(strategy_id))
                    except (TypeError, ValueError):
                        continue
                strategies = strategies.filter(id__in=strategy_ids)
            elif condition["key"] == "strategy_name":
                strategies = strategies.filter(name__in=condition["value"])

        total = strategies.count()
        if total == 1:
            strategy = Strategy.from_models([strategies.first()])[0]
            strategy.restore()
            config = strategy.to_dict(convert_dashboard=validated_request_data["convert_dashboard"])
            config_version = get_strategy_config_version(config)
            if validated_request_data["with_user_group"]:
                Strategy.fill_user_groups(
                    [config],
                    with_detail=validated_request_data["with_user_group_detail"],
                )
            config["config_version"] = config_version
            return config
        return {
            "total": total,
            "candidates": [self._candidate(strategy) for strategy in strategies.order_by("-update_time")[:10]],
        }


class CreateAlarmStrategyResource(Resource):
    """创建告警策略（用于 AI MCP 请求）。"""

    class RequestSerializer(ConfirmedBusinessScopedSerializer):
        name = serializers.CharField(required=True, label="策略名称")
        scenario = serializers.CharField(required=True, label="监控场景")
        metric = serializers.DictField(required=False, label="简化指标配置")
        detect = serializers.DictField(required=False, label="简化检测配置")
        notice_group_ids = serializers.ListField(
            required=False,
            child=serializers.IntegerField(),
            label="告警组ID列表",
        )
        action_config_ids = serializers.ListField(
            required=False,
            child=serializers.IntegerField(),
            label="处理套餐ID列表",
        )

    def perform_request(self, validated_request_data):
        request_data = remove_confirm(validated_request_data)
        if request_data.get("id"):
            raise ValidationError({"id": "create_alarm_strategy 不允许传入策略 ID"})

        complete_fields = {"items", "detects", "notice"}
        if not complete_fields.issubset(request_data):
            request_data = build_strategy_from_simplified_request(request_data)
        request_data.setdefault("actions", [])
        ensure_strategy_relations_belong_to_biz(request_data["bk_biz_id"], request_data)
        return resource.strategies.save_strategy_v2.request(**request_data)


class UpdateAlarmStrategyResource(Resource):
    """使用完整配置更新单个告警策略（用于 AI MCP 请求）。"""

    class RequestSerializer(ConfirmedBusinessScopedSerializer):
        id = serializers.IntegerField(required=True, label="策略ID")
        name = serializers.CharField(required=True, label="策略名称")
        type = serializers.CharField(required=True, label="策略类型")
        source = serializers.CharField(required=True, label="策略来源")
        scenario = serializers.CharField(required=True, label="监控场景")
        is_enabled = serializers.BooleanField(required=True, label="是否启用")
        is_invalid = serializers.BooleanField(required=True, label="是否失效")
        invalid_type = serializers.CharField(required=True, allow_blank=True, label="失效类型")
        items = serializers.ListField(
            required=True,
            allow_empty=False,
            child=serializers.DictField(),
            label="监控项完整配置",
        )
        detects = serializers.ListField(
            required=True,
            allow_empty=False,
            child=serializers.DictField(),
            label="检测规则完整配置",
        )
        notice = serializers.DictField(required=True, label="通知完整配置")
        actions = serializers.ListField(
            required=True,
            allow_empty=True,
            child=serializers.DictField(),
            label="处理套餐完整配置",
        )
        labels = serializers.ListField(
            required=True,
            allow_empty=True,
            child=serializers.CharField(),
            label="策略标签",
        )
        app = serializers.CharField(required=True, allow_blank=True, label="应用名称")
        path = serializers.CharField(required=True, allow_blank=True, label="配置路径")
        priority = serializers.IntegerField(required=True, allow_null=True, label="优先级")
        priority_group_key = serializers.CharField(
            required=True,
            allow_blank=True,
            label="优先级分组",
        )
        metric_type = serializers.CharField(required=True, allow_blank=True, label="指标类型")
        issue_config = serializers.JSONField(required=True, allow_null=True, label="故障聚合配置")
        update_time = serializers.CharField(required=True, label="读取策略时的更新时间")
        config_version = serializers.CharField(required=True, label="策略并发版本")

    def perform_request(self, validated_request_data):
        request_data = remove_confirm(validated_request_data)
        with transaction.atomic():
            try:
                current_strategy = StrategyModel.objects.select_for_update().get(
                    bk_biz_id=request_data["bk_biz_id"],
                    id=request_data["id"],
                )
            except StrategyModel.DoesNotExist:
                raise ValidationError({"id": f"业务 {request_data['bk_biz_id']} 下不存在策略: {request_data['id']}"})
            current_strategy_obj = Strategy.from_models([current_strategy])[0]
            current_strategy_obj.restore()
            current_config = current_strategy_obj.to_dict(convert_dashboard=False)
            if request_data["config_version"] != get_strategy_config_version(current_config):
                raise ValidationError(
                    {"config_version": "策略已被其他操作更新，请重新调用 get_alarm_strategy 后再修改"}
                )
            normalize_strategy_metric_ids(request_data, current_config)
            ensure_strategy_relations_belong_to_biz(request_data["bk_biz_id"], request_data)
            return resource.strategies.save_strategy_v2.request(**request_data)


class SearchAlarmShieldsResource(Resource):
    """查询告警屏蔽列表（用于 AI MCP 请求）。"""

    RequestSerializer = BusinessScopedSerializer

    def perform_request(self, validated_request_data):
        return resource.shield.shield_list.request(**validated_request_data)


class GetAlarmShieldResource(Resource):
    """查询单个告警屏蔽详情（用于 AI MCP 请求）。"""

    class RequestSerializer(BusinessScopedSerializer):
        id = serializers.IntegerField(required=True, label="屏蔽ID")

    def perform_request(self, validated_request_data):
        shield = ensure_shield_belongs_to_biz(validated_request_data["bk_biz_id"], validated_request_data["id"])
        if shield.get("notice_config"):
            shield["notice_config"] = normalize_shield_notice_config(shield["notice_config"])
        return shield


class CreateAlarmShieldResource(Resource):
    """创建告警屏蔽（用于 AI MCP 请求）。"""

    class RequestSerializer(ConfirmedBusinessScopedSerializer):
        category = serializers.ChoiceField(
            required=True,
            choices=["scope", "strategy", "alert", "dimension"],
            label="屏蔽类型",
        )
        begin_time = serializers.CharField(required=True, label="屏蔽开始时间")
        end_time = serializers.CharField(required=True, label="屏蔽结束时间")
        cycle_config = serializers.DictField(
            required=False,
            default={
                "type": 1,
                "begin_time": "",
                "end_time": "",
                "day_list": [],
                "week_list": [],
            },
            label="周期配置",
        )
        shield_notice = serializers.BooleanField(required=True, label="是否发送屏蔽通知")
        notice_config = ShieldNoticeConfigSerializer(required=False, label="屏蔽通知配置")
        dimension_config = serializers.DictField(required=True, label="屏蔽目标")

        def validate(self, attrs):
            if attrs["shield_notice"] and not attrs.get("notice_config"):
                raise ValidationError({"notice_config": "shield_notice=true 时必须提供通知配置"})
            category = attrs["category"]
            dimension_config = attrs["dimension_config"]
            if category == "scope":
                scope_type = dimension_config.get("scope_type")
                valid_scope_types = {"instance", "ip", "node", "biz", "dynamic_group"}
                if scope_type not in valid_scope_types:
                    raise ValidationError({"dimension_config.scope_type": "不支持的屏蔽范围类型"})
                target = dimension_config.get("target")
                if scope_type != "biz" and (not isinstance(target, list) or not target):
                    raise ValidationError({"dimension_config.target": "非业务范围屏蔽必须提供非空目标数组"})
                if scope_type == "ip":
                    for item in target:
                        if not isinstance(item, dict) or "ip" not in item or "bk_cloud_id" not in item:
                            raise ValidationError({"dimension_config.target": "IP 目标必须包含 ip 和 bk_cloud_id"})
                elif scope_type == "node":
                    for item in target:
                        if not isinstance(item, dict) or "bk_obj_id" not in item or "bk_inst_id" not in item:
                            raise ValidationError(
                                {"dimension_config.target": "节点目标必须包含 bk_obj_id 和 bk_inst_id"}
                            )
                elif scope_type == "dynamic_group":
                    for item in target:
                        if not isinstance(item, dict) or not str(item.get("dynamic_group_id", "")).strip():
                            raise ValidationError(
                                {"dimension_config.target": "动态分组目标必须包含非空 dynamic_group_id"}
                            )
                elif scope_type == "instance":
                    dimension_config["target"] = [
                        serializers.IntegerField(min_value=1).run_validation(item) for item in target
                    ]
            elif category == "dimension":
                conditions = dimension_config.get("dimension_conditions")
                if not isinstance(conditions, list) or not conditions:
                    raise ValidationError({"dimension_config.dimension_conditions": "维度屏蔽必须提供非空条件数组"})
            return attrs

    def perform_request(self, validated_request_data):
        request_data = remove_confirm(validated_request_data)
        shield_resource = resource.shield.add_shield
        if request_data["category"] == "strategy":
            strategy_ids = serializers.ListField(
                child=serializers.IntegerField(),
                allow_empty=False,
            ).run_validation(request_data["dimension_config"].get("id"))
            ensure_strategy_ids_belong_to_biz(request_data["bk_biz_id"], strategy_ids)
            request_data["dimension_config"]["id"] = strategy_ids
        elif request_data["category"] == "alert":
            alert_id = request_data["dimension_config"].get("alert_id")
            alert_ids = request_data["dimension_config"].get("alert_ids")
            if alert_id and alert_ids:
                raise ValidationError({"dimension_config": "alert_id 和 alert_ids 只能提供一个"})
            if alert_ids is not None and not isinstance(alert_ids, list):
                raise ValidationError({"dimension_config.alert_ids": "必须为告警 ID 数组"})
            if alert_ids:
                target_alert_ids = alert_ids
                shield_resource = resource.shield.bulk_add_alert_shield
            elif alert_id:
                target_alert_ids = [alert_id]
            else:
                raise ValidationError({"dimension_config": "alert_id 或 alert_ids 必须提供一个"})
            for target_alert_id in target_alert_ids:
                ensure_alert_belongs_to_biz(request_data["bk_biz_id"], target_alert_id)
        return shield_resource.request(**request_data)


class UpdateAlarmShieldResource(Resource):
    """编辑告警屏蔽（用于 AI MCP 请求）。"""

    class RequestSerializer(ConfirmedBusinessScopedSerializer):
        id = serializers.IntegerField(required=True, label="屏蔽ID")
        begin_time = serializers.CharField(required=True, label="屏蔽开始时间")
        end_time = serializers.CharField(required=True, label="屏蔽结束时间")
        cycle_config = serializers.DictField(required=True, label="周期配置")
        shield_notice = serializers.BooleanField(required=True, label="是否发送屏蔽通知")
        notice_config = ShieldNoticeConfigSerializer(required=False, label="屏蔽通知配置")
        description = serializers.CharField(required=False, allow_blank=True, label="屏蔽原因")
        level = serializers.ListField(required=False, child=serializers.IntegerField(), label="屏蔽等级")
        label = serializers.CharField(required=False, allow_blank=True, label="标签")

    def perform_request(self, validated_request_data):
        request_data = remove_confirm(validated_request_data)
        shield = ensure_shield_belongs_to_biz(request_data["bk_biz_id"], request_data["id"])
        request_data.setdefault("description", shield.get("description", ""))
        request_data["cycle_config"] = merge_nested_dict(
            shield.get("cycle_config") or {},
            request_data["cycle_config"],
        )
        if shield["category"] == "strategy":
            request_data.setdefault("level", shield["dimension_config"].get("level", []))
        if request_data.get("shield_notice"):
            request_data.setdefault("notice_config", shield.get("notice_config", {}))
            if not request_data["notice_config"]:
                raise ValidationError({"notice_config": "shield_notice=true 时必须提供通知配置"})
            request_data["notice_config"] = normalize_shield_notice_config(request_data["notice_config"])
        return resource.shield.edit_shield.request(**request_data)


class DisableAlarmShieldResource(Resource):
    """解除一个或多个告警屏蔽（用于 AI MCP 请求）。"""

    class RequestSerializer(ConfirmedBusinessScopedSerializer):
        id = serializers.ListField(
            required=True,
            allow_empty=False,
            child=serializers.IntegerField(),
            label="屏蔽ID列表",
        )

    def perform_request(self, validated_request_data):
        request_data = remove_confirm(validated_request_data)
        for shield_id in request_data["id"]:
            ensure_shield_belongs_to_biz(request_data["bk_biz_id"], shield_id)
        return resource.shield.disable_shield.request(**request_data)


class SearchNoticeGroupsResource(Resource):
    """查询业务下的告警组（用于 AI MCP 请求）。"""

    class RequestSerializer(BusinessScopedSerializer):
        with_detail = serializers.BooleanField(required=False, default=False, label="是否返回完整详情")

    def perform_request(self, validated_request_data):
        from kernel_api.views.v4.notice_group import SearchUserGroupDetailResource, SearchUserGroupResource

        request_data = dict(validated_request_data)
        with_detail = request_data.pop("with_detail")
        bk_biz_id = request_data["bk_biz_id"]
        request_data["bk_biz_ids"] = [request_data.pop("bk_biz_id")]
        groups = SearchUserGroupResource().request(**request_data)
        if not with_detail:
            return groups

        details = []
        for group in groups:
            detail = SearchUserGroupDetailResource().request(id=group["id"])
            if detail and detail["bk_biz_id"] == bk_biz_id:
                details.append(detail)
        return details


class UpdateNoticeGroupResource(Resource):
    """更新已有告警组（用于 AI MCP 请求）。"""

    class RequestSerializer(ConfirmedBusinessScopedSerializer):
        id = serializers.IntegerField(required=True, label="告警组ID")

    def perform_request(self, validated_request_data):
        from kernel_api.views.v4.notice_group import SaveUserGroupResource, SearchUserGroupDetailResource

        request_data = remove_confirm(validated_request_data)
        current_group = SearchUserGroupDetailResource().request(id=request_data["id"])
        if not current_group or current_group["bk_biz_id"] != request_data["bk_biz_id"]:
            raise ValidationError({"id": f"业务 {request_data['bk_biz_id']} 下不存在告警组: {request_data['id']}"})
        writable_fields = (
            "name",
            "timezone",
            "need_duty",
            "channels",
            "desc",
            "alert_notice",
            "action_notice",
            "duty_arranges",
            "duty_rules",
            "duty_notice",
            "path",
            "mention_list",
        )
        for field in writable_fields:
            if field not in request_data and field in current_group:
                request_data[field] = current_group[field]
        request_data.pop("mention_type", None)
        duty_rules = serializers.ListField(
            child=serializers.IntegerField(),
            allow_empty=True,
        ).run_validation(request_data.get("duty_rules") or [])
        ensure_duty_rules_belong_to_biz(request_data["bk_biz_id"], duty_rules)
        request_data["duty_rules"] = duty_rules
        return SaveUserGroupResource().request(**request_data)


class SearchActionConfigsResource(Resource):
    """查询业务下的处理套餐（用于 AI MCP 请求）。"""

    RequestSerializer = BusinessScopedSerializer

    def perform_request(self, validated_request_data):
        from kernel_api.views.v4.action_config import ListActionConfigResource

        return ListActionConfigResource().request(**validated_request_data)


class GetMCPActionConfigResource(Resource):
    """查询单个处理套餐详情（用于 AI MCP 请求）。"""

    class RequestSerializer(BusinessScopedSerializer):
        id = serializers.IntegerField(required=True, label="处理套餐ID")

    def perform_request(self, validated_request_data):
        from kernel_api.views.v4.action_config import GetActionConfigResource

        return GetActionConfigResource().request(**validated_request_data)


class UpdateMCPActionConfigResource(Resource):
    """更新已有处理套餐（用于 AI MCP 请求）。"""

    class RequestSerializer(ConfirmedBusinessScopedSerializer):
        id = serializers.IntegerField(required=True, label="处理套餐ID")
        name = serializers.CharField(required=True, label="处理套餐名称")
        desc = serializers.CharField(required=True, allow_blank=True, label="描述")
        execute_config = ActionExecuteConfigSerializer(required=True, label="完整执行配置")
        is_enabled = serializers.BooleanField(required=True, label="是否启用")

    def perform_request(self, validated_request_data):
        from kernel_api.views.v4.action_config import EditActionConfigResource, GetActionConfigResource

        request_data = remove_confirm(validated_request_data)
        current_config = GetActionConfigResource().request(id=request_data["id"], bk_biz_id=request_data["bk_biz_id"])
        if "plugin_id" in request_data and int(request_data["plugin_id"]) != int(current_config["plugin_id"]):
            raise ValidationError({"plugin_id": "处理套餐类型不允许修改"})
        request_data["plugin_id"] = current_config["plugin_id"]
        request_data["execute_config"] = merge_nested_dict(
            current_config["execute_config"],
            request_data["execute_config"],
        )
        return EditActionConfigResource().request(**request_data)
