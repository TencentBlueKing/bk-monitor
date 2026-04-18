"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
import logging
from datetime import UTC, datetime
from typing import Any, cast

from bk_monitor_base.strategy import delete_strategies, list_strategy, save_strategy
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from bkmonitor.models import StrategyModel
from bkmonitor.models.strategy import UserGroup
from bkmonitor.strategy.new_strategy import Strategy
from bkmonitor.utils.user import get_global_user
from bkmonitor.views import serializers
from constants.action import ActionPluginType, ActionSignal
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import SYSTEM_EVENT_RT_TABLE_ID
from core.drf_resource import Resource, api
from core.unit import load_unit
from monitor_web.commons.cc.utils import CmdbUtil
from monitor_web.models import CustomEventGroup
from monitor_web.shield.utils import ShieldDetectManager
from monitor_web.strategies.constant import DETECT_ALGORITHM_CHOICES
from monitor_web.strategies.resources.strategy import GetStrategyListV2Resource
from monitor_web.strategies.serializers import (
    handle_target,
    is_validate_target,
    validate_action_config,
    validate_agg_condition_msg,
    validate_algorithm_config_msg,
    validate_algorithm_msg,
    validate_no_data_config_msg,
    validate_recovery_config_msg,
    validate_trigger_config_msg,
)
from monitor_web.tasks import update_target_detail

logger = logging.getLogger(__name__)


class DeleteStrategyConfigResource(Resource):
    """
    删除监控策略
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id = serializers.IntegerField(required=False, label="策略ID")
        ids = serializers.ListField(required=False, label="策略ID列表")

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_biz_id = validated_request_data["bk_biz_id"]
        if "id" not in validated_request_data and "ids" not in validated_request_data:
            raise ValidationError("need id or ids")

        if "id" in validated_request_data:
            strategy_ids = [validated_request_data["id"]]
        else:
            strategy_ids = validated_request_data["ids"]

        # 删除相关联的屏蔽
        from bkmonitor.models import Shield

        shield_list = Shield.objects.filter(bk_biz_id=bk_biz_id, category="strategy")
        for item in shield_list:
            if item.dimension_config.get("strategy_id") in strategy_ids:
                item.delete()

        # 删除策略
        username = get_global_user() or "system"
        return delete_strategies(bk_biz_id, list(strategy_ids), operator=username)


class BackendStrategyConfigListResource(GetStrategyListV2Resource):
    """
    获取监控策略列表
    """

    def __init__(self):
        super().__init__()
        self.node_manager: CmdbUtil | None = None
        self.label_map: list[dict[str, Any]] = []
        self.shield_manager: ShieldDetectManager | None = None

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, default=0, label="业务ID")
        bk_cloud_id = serializers.IntegerField(required=False, label="云区域ID")
        order_by = serializers.CharField(required=False, default="-update_time", label="排序字段")
        scenario = serializers.CharField(required=False, label="二级标签")
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")
        notice_group_name = serializers.CharField(required=False, label="告警组名称")
        service_category = serializers.CharField(required=False, label="服务分类", allow_blank=True)
        task_id = serializers.IntegerField(required=False, label="任务ID")
        IP = serializers.IPAddressField(required=False, label="IP筛选")
        metric_id = serializers.CharField(required=False, label="指标ID")
        ids = serializers.ListField(required=False, label="ID列表")
        bk_event_group_id = serializers.IntegerField(required=False, label="事件分组ID")
        data_source_list = serializers.ListField(required=False, label="数据来源列表")
        conditions = serializers.ListField(label="搜索条件", required=False)
        only_using = serializers.IntegerField(required=False, label="仅统计在用的类型", default=0)

        def validate_data_source_list(self, value):
            try:
                return json.loads(value)
            except Exception as e:
                logger.exception(f"data_source_list参数错误, {e}")
                return []

    @staticmethod
    def _build_v2_conditions(validated_request_data: dict[str, Any]) -> list[dict[str, Any]]:
        """将 BackendStrategyConfigListResource 的旧查询参数转换为 v2 `conditions`。

        Notes:
            - v2 `conditions` 形如：`[{\"key\": \"xxx\", \"value\": [...]}, ...]`
            - 仅在值非空时追加条件，保持旧接口对空值“不过滤”的语义
            - `conditions.query`（用户确认）在新查询中仍是 `query` 字段
        """

        def _as_list(value: Any) -> list[Any]:
            if value is None:
                return []
            if isinstance(value, list):
                return [v for v in value if v not in (None, "")]
            # IPAddressField/IntegerField 等标量：包装成 list
            return [value]

        def _add(conditions: list[dict[str, Any]], key: str, value: Any) -> None:
            values = _as_list(value)
            if not values:
                return
            conditions.append({"key": key, "value": values})

        v2_conditions: list[dict[str, Any]] = []

        # 直接字段映射
        _add(v2_conditions, "strategy_id", validated_request_data.get("ids"))
        _add(v2_conditions, "metric_id", validated_request_data.get("metric_id"))
        _add(v2_conditions, "task_id", validated_request_data.get("task_id"))
        _add(v2_conditions, "user_group_name", validated_request_data.get("notice_group_name"))
        _add(v2_conditions, "service_category", validated_request_data.get("service_category"))
        _add(v2_conditions, "bk_event_group_id", validated_request_data.get("bk_event_group_id"))
        _add(v2_conditions, "data_source_list", validated_request_data.get("data_source_list"))
        _add(v2_conditions, "IP", validated_request_data.get("IP"))
        _add(v2_conditions, "bk_cloud_id", validated_request_data.get("bk_cloud_id"))

        # 条件：旧逻辑是 `conditions.query`
        raw_conditions = validated_request_data.get("conditions")
        query_value: str = ""
        if isinstance(raw_conditions, dict):
            query_value = str(raw_conditions.get("query", "") or "").strip()
        elif isinstance(raw_conditions, list):
            # 兼容部分调用方按 v2 风格传入：[{key: query, value: ...}]
            for cond in raw_conditions:
                if not isinstance(cond, dict):
                    continue
                if str(cond.get("key", "")).strip().lower() == "query":
                    v = cond.get("value", "")
                    if isinstance(v, list) and v:
                        query_value = str(v[0] or "").strip()
                    else:
                        query_value = str(v or "").strip()
                    break
        if query_value:
            _add(v2_conditions, "query", query_value)

        return v2_conditions

    def convert_v2_to_v1_strategy(self, strategy_config: dict[str, Any]) -> dict[str, Any]:
        """将v2策略配置转换为v1策略配置"""
        item_list = []
        for item in strategy_config["items"]:
            query_config = item["query_configs"][0]

            if (
                query_config["data_source_label"] == DataSourceLabel.BK_LOG_SEARCH
                and query_config["data_type_label"] == DataTypeLabel.LOG
            ):
                query_config["keywords_query_string"] = query_config["query_string"]
                del query_config["query_string"]
                query_config["agg_method"] = "COUNT"

            item_config = {
                "id": item["id"],
                "item_id": item["id"],
                "name": item["name"],
                "item_name": item["name"],
                "strategy_id": strategy_config["id"],
                "update_time": strategy_config["update_time"],
                "create_time": strategy_config["create_time"],
                "metric_id": query_config["metric_id"],
                "no_data_config": item["no_data_config"],
                "target": item["target"],
                "rt_query_config_id": query_config["id"],
                "data_source_label": query_config.pop("data_source_label"),
                "data_type_label": query_config.pop("data_type_label"),
                "algorithm_list": [
                    {
                        "id": algorithm["id"],
                        "algorithm_id": algorithm["id"],
                        "algorithm_type": algorithm["type"],
                        "algorithm_unit": algorithm["unit_prefix"],
                        "algorithm_config": algorithm["config"],
                        "trigger_config": strategy_config["detects"][0]["trigger_config"],
                        "recovery_config": strategy_config["detects"][0]["recovery_config"],
                        "level": algorithm["level"],
                    }
                    for algorithm in item["algorithms"]
                ],
                "labels": strategy_config["labels"],
            }

            # 查询配置
            rt_query_config = {
                "unit_conversion": 1,
                "extend_fields": {},
            }
            for field, value in query_config.items():
                if field in [
                    "index_set_id",
                    "time_field",
                    "values",
                    "custom_event_name",
                    "origin_config",
                    "intelligent_detect",
                ]:
                    rt_query_config["extend_fields"][field] = value
                else:
                    rt_query_config[field] = value

            rt_query_config["rt_query_config_id"] = query_config["id"]
            item_config["rt_query_config"] = rt_query_config

            item_list.append(item_config)

        # 处理动作适配逻辑 - 开始
        notice = strategy_config["notice"]

        anomaly_template = None
        recovery_template = None
        for template in notice["config"].get("template", []):
            if template["signal"] == ActionSignal.ABNORMAL:
                anomaly_template = template
            elif template["signal"] == ActionSignal.RECOVERED:
                recovery_template = template

        action = {
            "id": notice["id"],
            "action_id": notice["id"],
            "config": {
                "alarm_start_time": notice["options"].get("start_time", "00:00:00"),
                "alarm_end_time": notice["options"].get("end_time", "23:59:59"),
                "alarm_interval": notice["config"].get("notify_interval", 7200) // 60,
                "send_recovery_alarm": ActionSignal.RECOVERED in notice["signal"],
            },
            "action_type": ActionPluginType.NOTICE,
            "notice_template": {
                "anomaly_template": anomaly_template["message_tmpl"] if anomaly_template else "",
                "recovery_template": recovery_template["message_tmpl"] if recovery_template else "",
            },
            "notice_group_list": notice["user_groups"],
        }
        # 处理动作适配逻辑 - 结束

        result = {
            "id": strategy_config["id"],
            "strategy_id": strategy_config["id"],
            "name": strategy_config["name"],
            "strategy_name": strategy_config["name"],
            "bk_biz_id": strategy_config["bk_biz_id"],
            "scenario": strategy_config["scenario"],
            "is_enabled": strategy_config["is_enabled"],
            "is_invalid": strategy_config["is_invalid"],
            "invalid_type": strategy_config["invalid_type"],
            "update_time": strategy_config["update_time"],
            "update_user": strategy_config["update_user"],
            "create_time": strategy_config["create_time"],
            "create_user": strategy_config["create_user"],
            "action_list": [action],
            "item_list": item_list,
            "labels": strategy_config["labels"],
        }

        for item in result["item_list"]:
            item.pop("alias", None)
        return result

    def perform_request(self, validated_request_data: dict[str, Any]) -> list[dict[str, Any]]:  # pyright: ignore[reportIncompatibleMethodOverride]
        # 将查询条件转换为v2接口的查询条件
        bk_biz_id = validated_request_data.get("bk_biz_id")
        if not bk_biz_id:
            # NOTE: 不再支持多业务查询，原本当 bk_biz_id 为空时，会查询用户有权限的所有业务
            raise ValidationError("bk_biz_id is required")

        conditions = self._build_v2_conditions(validated_request_data)

        # 条件过滤，返回策略ID集合
        candidates = self.filter_by_conditions(bk_biz_id=bk_biz_id, conditions=conditions)

        # 分页计算
        offset, limit = 0, None
        page, page_size = validated_request_data.get("page"), validated_request_data.get("page_size")
        if page and page_size:
            offset = (page - 1) * page_size
            limit = page * page_size

        # 生成策略配置
        strategies_result = list_strategy(
            bk_biz_id=bk_biz_id,
            conditions=[{"key": "id", "values": list(candidates), "operator": "eq"}],
            order_by=validated_request_data["order_by"],
            offset=offset,
            limit=limit,
        )
        strategy_configs = strategies_result["data"]

        return [self.convert_v1_to_v2_strategy(strategy_config) for strategy_config in strategy_configs]


class BackendStrategyConfigResource(Resource):
    class RequestSerializer(serializers.Serializer):
        class ItemListSerializer(serializers.Serializer):
            class AlgorithmSerializers(serializers.Serializer):
                class TriggerConfigSerializers(serializers.Serializer):
                    count = serializers.IntegerField(required=True, label="触发次数")
                    check_window = serializers.IntegerField(required=True, label="检测周期")

                class RecoveryConfigSerializers(serializers.Serializer):
                    check_window = serializers.IntegerField(required=True, label="检测周期")

                trigger_config = TriggerConfigSerializers()
                algorithm_type = serializers.ChoiceField(
                    required=False, choices=DETECT_ALGORITHM_CHOICES, label="检测算法"
                )
                algorithm_unit = serializers.CharField(required=False, allow_blank=True, label="算法单位")
                recovery_config = RecoveryConfigSerializers()
                message_template = serializers.CharField(required=False, allow_blank=True, label="通知模板")
                algorithm_config = serializers.JSONField(required=False, label="检测算法配置")
                level = serializers.IntegerField(required=True, label="告警级别")

                def validate_algorithm_config(self, value):
                    return validate_algorithm_config_msg(value)

                def validate_trigger_config(self, value):
                    return validate_trigger_config_msg(value)

                def validate_recovery_config(self, value):
                    return validate_recovery_config_msg(value)

            class RtQueryConfigSerializers(serializers.Serializer):
                metric_field = serializers.CharField(required=False, label="监控指标别名")
                unit_conversion = serializers.FloatField(required=False, default=1.0, label="单位换算")
                unit = serializers.CharField(required=False, allow_blank=True, label="单位")
                extend_fields = serializers.JSONField(required=False, allow_null=True, label="扩展字段")
                agg_dimension = serializers.ListField(required=False, allow_empty=True, label="聚合维度")
                result_table_id = serializers.CharField(required=False, allow_blank=True, label="表名")
                agg_method = serializers.CharField(required=False, allow_blank=True, label="聚合算法")
                agg_interval = serializers.CharField(required=False, allow_blank=True, label="聚合周期")
                agg_condition = serializers.ListField(required=False, allow_empty=True, label="聚合条件")
                rule = serializers.CharField(required=False, allow_blank=True, label="组合方式")
                keywords = serializers.CharField(required=False, allow_blank=True, label="组合字段")
                keywords_query_string = serializers.CharField(required=False, allow_blank=True, label="关键字查询条件")
                bk_event_group_id = serializers.IntegerField(required=False, label="自定义事件分组ID")
                custom_event_id = serializers.IntegerField(required=False, label="自定义事件分组ID")

                def validate_extend_fields(self, value):
                    if not value:
                        return {}
                    return value

            id = serializers.IntegerField(required=False, label="item_id")
            name = serializers.CharField(required=True, label="监控指标别名")
            # 数据类型标签，例如：时序数据(time_series)，事件数据(event)，日志数据(log)
            data_type_label = serializers.CharField(required=True, label="数据类型标签")
            metric_id = serializers.CharField(required=True, label="指标标识")
            # 数据来源标签，例如：数据平台(bk_data)，监控采集器(bk_monitor_collector)
            data_source_label = serializers.CharField(required=True, label="数据来源标签")
            algorithm_list = AlgorithmSerializers(required=True, many=True, label="")
            no_data_config = serializers.DictField(required=True, label="无数据告警配置")
            rt_query_config = RtQueryConfigSerializers(required=True, allow_null=True, label="查询表")
            target = serializers.ListField(default=[[]], label="策略目标")
            result_table_id = serializers.CharField(required=False, label="表名（用于GSE进程事件默认创建）")

            def validate_no_data_config(self, value):
                return validate_no_data_config_msg(value)

            def validate_agg_condition(self, value):
                return validate_agg_condition_msg(value)

            def validate_algorithm_list(self, value):
                return validate_algorithm_msg(value)

        class ActionListSerializer(serializers.Serializer):
            class NoticeTemplateSerializer(serializers.Serializer):
                anomaly_template = serializers.CharField(required=False, allow_blank=True, label="告警发生通知模板")
                recovery_template = serializers.CharField(required=False, allow_blank=True, label="告警恢复通知模板")

            id = serializers.IntegerField(required=False, label="action_id")
            action_type = serializers.CharField(required=False, default="notice", label="触发动作")
            config = serializers.DictField(required=True, label="告警相关配置")
            notice_group_list = serializers.ListField(default=[], label="通知组ID列表")
            notice_template = NoticeTemplateSerializer()

            def validate_config(self, value):
                return validate_action_config(value)

        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        name = serializers.CharField(required=True, max_length=128, label="策略名称")
        scenario = serializers.CharField(required=True, label="监控场景")
        id = serializers.IntegerField(required=False, label="策略ID")
        source = serializers.CharField(required=False, label="策略配置来源")
        item_list = serializers.ListField(
            child=ItemListSerializer(required=True, label="监控算法配置"),
            min_length=1,
        )
        action_list = serializers.ListField(
            child=ActionListSerializer(required=True, label="触发动作"),
        )
        is_enabled = serializers.BooleanField(label="是否启用", default=True)

        def validate_target(self, value):
            is_validate_target(value)
            return handle_target(value)

        def validate_no_data_config(self, value):
            return validate_no_data_config_msg(value)

    @classmethod
    def convert_v1_to_v2_strategy(cls, old_strategy_config: dict[str, Any]) -> dict[str, Any]:
        config = copy.deepcopy(old_strategy_config)
        item_list = config.pop("item_list")
        action_list = config.pop("action_list")
        strategy_id = config.pop("id", 0)
        algorithm_list = item_list[0].pop("algorithm_list")

        item: dict = item_list[0]
        item.pop("strategy_id", None)
        item.pop("item_id", None)

        # 展开rt_query_config
        if "rt_query_config" in item:
            item["rt_query_config"].pop("id", None)
            item.update(item.pop("rt_query_config"))

        # 系统事件指标提取
        if (
            item["data_source_label"] == DataSourceLabel.BK_MONITOR_COLLECTOR
            and item["data_type_label"] == DataTypeLabel.EVENT
        ):
            item["result_table_id"] = SYSTEM_EVENT_RT_TABLE_ID
            item["metric_field"] = item["metric_id"].split(".")[-1]
            item["agg_condition"] = []
        item.pop("metric_id", None)

        # 补充缺失字段
        if "agg_condition" not in item:
            item["agg_condition"] = []

        # 算法字段名转换
        algorithm_field_mapping = {
            "algorithm_unit": "unit_prefix",
            "algorithm_type": "type",
            "algorithm_config": "config",
        }
        detect_configs = {}
        for algorithm in algorithm_list:
            algorithm.pop("strategy_id", None)
            algorithm.pop("item_id", None)
            for field in algorithm_field_mapping:
                algorithm[algorithm_field_mapping[field]] = algorithm.get(field, "")
            detect_configs[int(algorithm["level"])] = {
                "expression": "",
                "connector": "and",
                "level": int(algorithm["level"]),
                "trigger_config": algorithm["trigger_config"],
                "recovery_config": algorithm["recovery_config"],
            }

        # 动作配置字段转换
        if action_list:
            old_action = action_list[0]
        else:
            old_action = {}

        # 日志平台查询参数转换
        if "keywords_query_string" in item:
            item["query_string"] = item["keywords_query_string"]

        # 时间格式转换
        update_time = config.get("update_time")
        create_time = config.get("create_time")
        if isinstance(update_time, int):
            config["update_time"] = datetime.fromtimestamp(update_time, UTC)
        if isinstance(create_time, int):
            config["create_time"] = datetime.fromtimestamp(create_time, UTC)

        # 适配extend_fields为字符串的情况
        if isinstance(item.get("extend_fields"), str):
            item["extend_fields"] = {}

        # 适配extend_fields中的data_source_label为空的情况
        if item.get("extend_fields", {}).get("data_source_label") == "":
            item["extend_fields"]["data_source_label"] = item["data_source_label"]

        old_notice_config = old_action.get("config", {})

        signal = [ActionSignal.ABNORMAL, ActionSignal.NO_DATA]

        if old_notice_config.get("send_recovery_alarm"):
            signal.append(ActionSignal.RECOVERED)

        webhook_actions = []
        if not old_action:
            notice = {}
        else:
            # 兼容导入导出格式
            if old_action["notice_group_list"] and isinstance(old_action["notice_group_list"][0], dict):
                notice_group_ids = [group["id"] for group in old_action["notice_group_list"]]
            else:
                notice_group_ids = old_action["notice_group_list"]
                for group in UserGroup.objects.filter(id__in=notice_group_ids):
                    if not group.webhook_action_id:
                        continue
                    webhook_actions.append(
                        {
                            "config_id": group.webhook_action_id,
                            "signal": [
                                ActionSignal.ABNORMAL,
                                ActionSignal.NO_DATA,
                                ActionSignal.RECOVERED,
                                ActionSignal.CLOSED,
                            ],
                            "user_groups": notice_group_ids,
                            "options": {
                                "converge_config": {
                                    "is_enabled": False,
                                }
                            },
                        }
                    )

            notice = {
                "user_groups": notice_group_ids,
                "signal": signal,
                "options": {
                    "converge_config": {
                        "need_biz_converge": True,
                    },
                },
                "config": {
                    "notify_interval": int(old_notice_config.get("alarm_interval", 120)) * 60,
                    "interval_notify_mode": "standard",
                    "template": [
                        {
                            "signal": ActionSignal.ABNORMAL,
                            "message_tmpl": old_action["notice_template"].get("anomaly_template", ""),
                            "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}",
                        },
                        {
                            "signal": ActionSignal.RECOVERED,
                            "message_tmpl": old_action["notice_template"].get("recovery_template", ""),
                            "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}",
                        },
                        {
                            "signal": ActionSignal.CLOSED,
                            "message_tmpl": old_action["notice_template"].get("anomaly_template", ""),
                            "title_tmpl": "{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}",
                        },
                    ],
                },
            }

        for detect_config in detect_configs.values():
            detect_config["trigger_config"].update(
                {
                    "uptime": {
                        "time_ranges": [
                            {
                                "start": old_notice_config.get("alarm_start_time", "00:00")[:5],
                                "end": old_notice_config.get("alarm_end_time", "23:59")[:5],
                            }
                        ],
                        "calendars": [],
                        "active_calendars": [],
                    }
                }
            )

        return {
            "id": strategy_id,
            "type": "monitor",
            **config,
            "detects": list(detect_configs.values()),
            "items": [
                {
                    "algorithms": algorithm_list,
                    "query_configs": [{"alias": "a", **item, **item.get("extend_fields", {})}],
                    **item,
                }
            ],
            "notice": notice,
            "actions": webhook_actions,
        }

    def perform_request(self, validated_request_data):
        # 补全算法单位
        item_list = validated_request_data["item_list"]
        for item in item_list:
            if not item["rt_query_config"]:
                continue

            for algorithm in item["algorithm_list"]:
                if "algorithm_unit" in algorithm:
                    continue

                unit = load_unit(item["rt_query_config"].get("unit", ""))
                algorithm["algorithm_unit"] = unit.unit

        for item in validated_request_data["item_list"]:
            rt_query_config = item.get("rt_query_config", {})
            if item["data_source_label"] != DataSourceLabel.CUSTOM or item["data_type_label"] != DataTypeLabel.EVENT:
                continue

            if "result_table_id" in rt_query_config:
                continue

            event_group = CustomEventGroup.objects.get(
                bk_biz_id=validated_request_data["bk_biz_id"], bk_event_group_id=rt_query_config["bk_event_group_id"]
            )
            rt_query_config["result_table_id"] = event_group.table_id

        strategy_config = self.convert_v1_to_v2_strategy(validated_request_data)

        username = get_global_user() or "system"
        result = save_strategy(validated_request_data["bk_biz_id"], strategy_config, username)
        return {"id": result["id"]}


# 以下是只有前端在用，但是不确定是否是旧代码还是真的在用
class BulkEditStrategyResource(Resource):
    """
    批量修改接口
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        id_list = serializers.ListField(required=True, label="批量修改的策略ID列表")
        edit_data = serializers.DictField(required=True, label="批量修改的值")

        def validate_edit_data(self, value):
            if value.get("target"):
                is_validate_target(value.get("target"))
                value["target"] = handle_target(value.get("target"))
            return value

    @staticmethod
    def update_enabled(strategy: Strategy, edit_data):
        """
        更新策略启停状态
        """
        if "is_enabled" not in edit_data:
            return
        strategy.is_enabled = edit_data["is_enabled"]

    @staticmethod
    def update_notice_group(strategy: Strategy, edit_data):
        """
        更新告警组配置
        """
        if "notice_group_list" not in edit_data:
            return

        for action in strategy.actions:
            action.notice_group_ids = edit_data["notice_group_list"]

    @staticmethod
    def update_trigger(strategy: Strategy, edit_data):
        """
        更新触发条件
        """
        if "trigger_config" not in edit_data:
            return

        for detect in strategy.detects:
            detect.trigger_config = edit_data["trigger_config"]

    @staticmethod
    def update_notice_interval(strategy: Strategy, edit_data):
        """
        更新通知间隔
        """
        if "alarm_interval" not in edit_data:
            return

        for action in strategy.actions:
            action.config["alarm_interval"] = edit_data["alarm_interval"]

    @staticmethod
    def update_recovery_alarm(strategy: Strategy, edit_data):
        """
        更新恢复通知
        """
        if "send_recovery_alarm" not in edit_data:
            return

        for action in strategy.actions:
            action.config["send_recovery_alarm"] = edit_data["send_recovery_alarm"]

    @staticmethod
    def update_recovery_config(strategy: Strategy, edit_data):
        """
        更新告警恢复通知
        """
        if "recovery_config" not in edit_data:
            return

        for detect in strategy.detects:
            detect.recovery_config = edit_data["recovery_config"]

    @staticmethod
    def update_target(strategy: Strategy, edit_data):
        """
        更新监控目标
        """
        if "target" not in edit_data:
            return

        for item in strategy.items:
            item.target = edit_data["target"]

    @staticmethod
    def refresh_target_cache(strategies: list[StrategyModel], edit_data):
        """
        刷新监控目标缓存
        """

        if "target" not in edit_data or not strategies:
            return
        bk_biz_id = strategies[0].bk_biz_id
        strategy_ids = [strategy.pk for strategy in strategies]

        # 异步刷新监控目标缓存
        update_target_detail.delay(bk_biz_id, strategy_ids)

    @staticmethod
    def update_message_template(strategy: Strategy, edit_data):
        if "message_template" not in edit_data:
            return

        for action in strategy.actions:
            # `Strategy.actions` 的元素类型在类型系统里并不包含 notice_template，
            # 这里按运行期结构做兼容处理，避免静态类型检查报错。
            action_obj = cast(Any, action)
            notice_template = getattr(action_obj, "notice_template", None)
            if isinstance(notice_template, dict):
                notice_template["anomaly_template"] = edit_data["message_template"]

    @classmethod
    def update(cls, strategy: Strategy, edit_data):
        """
        更新配置
        :param strategy: 策略配置
        :param edit_data: 操作数据
        """
        cls.update_enabled(strategy, edit_data)
        cls.update_notice_group(strategy, edit_data)
        cls.update_notice_interval(strategy, edit_data)
        cls.update_recovery_alarm(strategy, edit_data)
        cls.update_recovery_config(strategy, edit_data)
        cls.update_trigger(strategy, edit_data)
        cls.update_target(strategy, edit_data)
        cls.update_message_template(strategy, edit_data)

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_biz_id = validated_request_data["bk_biz_id"]
        edit_data = validated_request_data["edit_data"]

        strategies = StrategyModel.objects.filter(bk_biz_id=bk_biz_id, id__in=validated_request_data["id_list"])

        for strategy in Strategy.from_models(strategies):
            self.update(strategy, edit_data)
            strategy.save()

        self.refresh_target_cache(list(strategies), edit_data)

        return validated_request_data["id_list"]


class GetIndexSetListResource(Resource):
    """
    获取索引集
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        index_set_id = serializers.IntegerField(default=-1, label="查询索引集")

    def index_filter(self, data):
        res = []
        count_list = []
        for index_set in data:
            temp_scenario_dict = {"id": index_set.get("scenario_id"), "name": index_set.get("scenario_name")}
            if temp_scenario_dict not in count_list:
                count_list.append({"id": index_set.get("scenario_id"), "name": index_set.get("scenario_name")})
            # 数据源
            scenario_id = index_set.get("scenario_id")
            scenario_name = index_set.get("scenario_name")
            # 索引集
            index_set_id = index_set.get("index_set_id")
            metric_field = index_set.get("index_set_name")
            default_time_field = index_set.get("time_field")
            # 其余
            storage_cluster_id = index_set.get("storage_cluster_id")

            # 临时的索引,索引集中的索引
            temp_metric_name = []
            temp_metric_id = []
            # 根据拆索引集获取索引
            for index in index_set.get("indices", []):
                temp_metric_id.append(str(index["result_table_id"]))
                temp_metric_name.append(index.get("result_table_name"))
                # 索引
                result_table_id = ",".join(temp_metric_id)
                # 拼接的注释
                metric_description = _("数据来源：日志平台")
                time_field = default_time_field

                data = {
                    # 索引集id
                    "index_set_id": index_set_id,
                    # 索引集名称
                    "name": metric_field,
                    "metric_field": metric_field,
                    "metric_field_name": metric_field,
                    # 索引
                    "result_table_id": result_table_id,
                    # 数据源id和名称
                    "scenario_id": scenario_id,
                    "scenario_name": scenario_name,
                    "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
                    "metric_description": metric_description,
                    "collect_interval": 1,
                    "id": None,
                    "data_type_label": "log",
                    "unit_conversion": 1.0,
                    "result_table_label": "log",
                    "default_trigger_config": {"count": 1, "check_window": 5},
                    "extend_fields": {
                        "index_set_id": index_set_id,
                        "scenario_id": scenario_id,
                        "scenario_name": scenario_name,
                        "storage_cluster_id": storage_cluster_id,
                        "time_field": time_field,
                    },
                    "result_table_name": "",
                    "default_condition": [],
                    "default_dimensions": [],
                    "related_name": "",
                    "collect_config_ids": [],
                    "unit": "",
                    "related_id": "",
                    "dimensions": [],
                    "collect_config": "",
                    "data_target": "",
                    "category_display": "",
                    "description": "",
                    "result_table_label_name": "",
                    "bk_biz_id": "",
                    "plugin_type": "",
                }
                res.append(data)

        return res, count_list

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        index_set_id = validated_request_data["index_set_id"]
        data = api.log_search.search_index_set(bk_biz_id=bk_biz_id)

        if index_set_id != -1:
            filter_data = []
            for i in data:
                if i.get("index_set_id") == index_set_id:
                    filter_data.append(i)
                    break
            data = filter_data
        metric_list, count_list = self.index_filter(data)
        return {"metric_list": metric_list, "count_list": count_list}
