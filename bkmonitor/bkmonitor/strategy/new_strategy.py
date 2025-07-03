"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
import copy
import json
import logging
import traceback
from collections import defaultdict
from datetime import datetime
from functools import partial, reduce
from itertools import chain, permutations
from typing import Any

import arrow
import xxhash
from django.conf import settings
from django.db import transaction
from django.db.models import Model, QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bk_dataview.api import get_grafana_panel_query
from bkm_space.utils import bk_biz_id_to_space_uid
from bkmonitor.action.serializers import (
    ConvergeConfigSlz,
    NoiseReduceConfigSlz,
    NotifyActionConfigSlz,
    UpgradeConfigSlz,
    UserGroupDetailSlz,
    UserGroupSlz,
)
from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.data_source import load_data_source
from bkmonitor.data_source.unify_query.functions import add_expression_functions
from bkmonitor.dataflow.constant import AccessStatus
from bkmonitor.middlewares.source import get_source_app_code
from bkmonitor.models import Action as ActionModel
from bkmonitor.models import ActionConfig, ActionNoticeMapping, NoticeTemplate
from bkmonitor.models import StrategyActionConfigRelation as RelationModel
from bkmonitor.models import UserGroup
from bkmonitor.models.strategy import (
    AlgorithmModel,
    DetectModel,
    ItemModel,
    QueryConfigModel,
    StrategyHistoryModel,
    StrategyLabel,
    StrategyModel,
    AlgorithmChoiceConfig,
)
from bkmonitor.strategy.expression import parse_expression
from bkmonitor.strategy.serializers import (
    AbnormalClusterSerializer,
    AdvancedRingRatioSerializer,
    AdvancedYearRoundSerializer,
    BkApmTimeSeriesSerializer,
    BkApmTraceSerializer,
    BkDataTimeSeriesSerializer,
    BkFtaAlertSerializer,
    BkFtaEventSerializer,
    BkLogSearchLogSerializer,
    BkLogSearchTimeSeriesSerializer,
    BkMonitorAlertSerializer,
    BkMonitorEventSerializer,
    BkMonitorLogSerializer,
    BkMonitorTimeSeriesSerializer,
    CustomEventSerializer,
    CustomTimeSeriesSerializer,
    GrafanaTimeSeriesSerializer,
    HostAnomalyDetectionSerializer,
    IntelligentDetectSerializer,
    MultivariateAnomalyDetectionSerializer,
    PrometheusTimeSeriesSerializer,
    QueryConfigSerializer,
    RingRatioAmplitudeSerializer,
    SimpleRingRatioSerializer,
    SimpleYearRoundSerializer,
    ThresholdSerializer,
    TimeSeriesForecastingSerializer,
    YearRoundAmplitudeSerializer,
    YearRoundRangeSerializer,
)
from bkmonitor.utils.time_tools import parse_time_compare_abbreviation, strftime_local
from bkmonitor.utils.user import get_global_user
from constants.action import ActionPluginType, ActionSignal, AssignMode, UserGroupType
from constants.aiops import SDKDetectStatus
from constants.data_source import DataSourceLabel, DataTypeLabel, DATA_SOURCE_LABEL_ALIAS
from constants.strategy import (
    DATALINK_SOURCE,
    HOST_SCENARIO,
    SERVICE_SCENARIO,
    SYSTEM_EVENT_RT_TABLE_ID,
    SYSTEM_PROC_PORT_METRIC_ID,
    DataTarget,
    TargetFieldType,
)
from core.drf_resource import api
from core.errors.strategy import CreateStrategyError, StrategyNotExist

logger = logging.getLogger(__name__)


def get_metric_id(
    data_source_label,
    data_type_label,
    result_table_id="",
    index_set_id="",
    metric_field="",
    custom_event_name="",
    alert_name="",
    bkmonitor_strategy_id="",
    promql="",
    **kwargs,
):
    """
    生成metric_id
    """
    metric_id_map = {
        DataSourceLabel.BK_MONITOR_COLLECTOR: {
            DataTypeLabel.TIME_SERIES: f"{data_source_label}.{result_table_id}.{metric_field}",
            DataTypeLabel.EVENT: f"{data_source_label}.{metric_field}",
            DataTypeLabel.LOG: f"{data_source_label}.{data_type_label}.{result_table_id}",
            DataTypeLabel.ALERT: f"{data_source_label}.{data_type_label}.{bkmonitor_strategy_id or metric_field}",
        },
        DataSourceLabel.PROMETHEUS: {DataTypeLabel.TIME_SERIES: promql[:125] + "..." if len(promql) > 128 else promql},
        DataSourceLabel.CUSTOM: {
            DataTypeLabel.EVENT: "{}.{}.{}.{}".format(
                data_source_label, data_type_label, result_table_id, custom_event_name or "__INDEX__"
            ),
            DataTypeLabel.TIME_SERIES: f"{data_source_label}.{result_table_id}.{metric_field}",
        },
        DataSourceLabel.BK_LOG_SEARCH: {
            DataTypeLabel.LOG: f"{data_source_label}.index_set.{index_set_id}",
            DataTypeLabel.TIME_SERIES: f"{data_source_label}.index_set.{index_set_id}.{metric_field}",
        },
        DataSourceLabel.BK_DATA: {
            DataTypeLabel.TIME_SERIES: f"{data_source_label}.{result_table_id}.{metric_field}",
        },
        DataSourceLabel.BK_FTA: {
            DataTypeLabel.ALERT: f"{data_source_label}.{data_type_label}.{alert_name or metric_field}",
            DataTypeLabel.EVENT: f"{data_source_label}.{data_type_label}.{alert_name or metric_field}",
        },
        DataSourceLabel.BK_APM: {
            DataTypeLabel.LOG: f"{data_source_label}.{data_type_label}.{result_table_id}",
            DataTypeLabel.TIME_SERIES: f"{data_source_label}.{result_table_id}.{metric_field}",
        },
    }
    # 特殊事件: 进程端口
    if kwargs.get("metric_id") == SYSTEM_PROC_PORT_METRIC_ID:
        return SYSTEM_PROC_PORT_METRIC_ID
    return metric_id_map.get(data_source_label, {}).get(data_type_label, "")


def parse_metric_id(metric_id: str) -> dict:
    """
    解析指标ID
    """
    split_field_list = metric_id.split(".")
    data_source_label = split_field_list[0]
    info = {"data_source_label": data_source_label}

    if data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR:
        if split_field_list[1] == DataTypeLabel.LOG:
            info.update({"data_type_label": DataTypeLabel.LOG, "result_table_id": split_field_list[2]})
        elif len(split_field_list) == 2:
            # 系统事件指标
            info.update(
                {
                    "data_type_label": DataTypeLabel.EVENT,
                    "result_table_id": SYSTEM_EVENT_RT_TABLE_ID,
                    "metric_field": split_field_list[1],
                }
            )
        elif split_field_list[1] == DataTypeLabel.ALERT:
            # 告警类型指标
            info.update(
                {
                    "data_type_label": DataTypeLabel.ALERT,
                    "metric_field": split_field_list[2],
                }
            )
        elif len(split_field_list) in [3, 4]:
            # 系统时序型指标 & 插件采集指标
            info.update(
                {
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "result_table_id": ".".join(split_field_list[1:-1]),
                    "metric_field": split_field_list[-1],
                }
            )
        else:
            return {}
    elif data_source_label == DataSourceLabel.CUSTOM:
        # 自定义事件指标
        if split_field_list[1] == DataTypeLabel.EVENT:
            info.update(
                {
                    "data_type_label": DataTypeLabel.EVENT,
                    "result_table_id": split_field_list[2],
                    "metric_field": split_field_list[3],
                }
            )
        # 自定义时序型指标
        else:
            info.update(
                {
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "result_table_id": ".".join(split_field_list[1:-1]),
                    "metric_field": split_field_list[-1],
                }
            )
    elif data_source_label == DataSourceLabel.BK_LOG_SEARCH:
        if len(split_field_list) == 3:
            info.update({"data_type_label": DataTypeLabel.LOG, "index_set_id": split_field_list[2]})
        else:
            info.update(
                {
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "index_set_id": split_field_list[2],
                    "metric_field": ".".join(split_field_list[3:]),
                }
            )
    elif data_source_label == DataSourceLabel.BK_DATA:
        info.update(
            {
                "data_type_label": DataTypeLabel.TIME_SERIES,
                "result_table_id": split_field_list[1],
                "metric_field": split_field_list[2],
            }
        )
    elif data_source_label == DataSourceLabel.BK_FTA:
        info.update(
            {
                "data_type_label": split_field_list[1],
                "metric_field": ".".join(split_field_list[2:]),
            }
        )
    elif data_source_label == DataSourceLabel.BK_APM:
        if split_field_list[1] == DataTypeLabel.LOG:
            info.update(
                {
                    "data_type_label": DataTypeLabel.LOG,
                    "result_table_id": split_field_list[2],
                }
            )
        else:
            info.update(
                {
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "result_table_id": split_field_list[1],
                    "metric_field": split_field_list[2],
                }
            )

    else:
        return {}

    return info


def has_instance_attr(obj, attr):
    """检查是否有指定的实例变量，并排除方法和@property"""
    if attr in obj.__dict__:
        return True

    if hasattr(obj.__class__, attr):
        attr_value = getattr(obj.__class__, attr)
        if isinstance(attr_value, property):
            return False
        if callable(attr_value):
            return False
    return False


class AbstractConfig(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def to_dict(self, *args, **kwargs) -> dict:
        raise NotImplementedError

    @classmethod
    def delete_useless(cls, *args, **kwargs):
        return

    @classmethod
    def reuse_exists_records(
        cls, model: type[Model], objs: list[Model], configs: list["AbstractConfig"], config_cls: type["AbstractConfig"]
    ):
        """
        重用存量的数据库记录，删除多余的记录
        :param model: 模型
        :param objs: 数据库记录
        :param configs: 配置对象
        :param config_cls: 配置处理类
        """
        for config, obj in zip(configs, objs):
            config.id = obj.id
        # fmt: off
        for config in configs[len(objs):]:
            config.id = 0
        if objs[len(configs):]:
            obj_ids = [obj.id for obj in objs[len(configs):]]
            model.objects.filter(id__in=obj_ids).delete()
            config_cls.delete_useless(obj_ids)
        # fmt: on

    @staticmethod
    def _get_username():
        try:
            from blueapps.utils import get_request

            username = get_request().user.username
        except IndexError:
            username = "system"
        return username

    @abc.abstractmethod
    def save(self):
        raise NotImplementedError

    def __setattr__(self, key, value):
        super().__setattr__(key, value)
        if getattr(self, "instance", None):
            if has_instance_attr(self.instance, key):
                setattr(self.instance, key, value)


class Action(AbstractConfig):
    """
    动作配置
    """

    class Serializer(serializers.Serializer):
        id = serializers.IntegerField(required=False)
        type = serializers.CharField()
        config = serializers.DictField()
        notice_group_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)
        notice_template = serializers.DictField(required=False, allow_null=True)

    def __init__(
        self,
        strategy_id: int,
        type: str,
        config: dict = None,
        notice_group_ids: list[int] = None,
        notice_template: dict = None,
        id: int = 0,
        instance: ActionModel = None,
        **kwargs,
    ):
        self.id = id
        self.strategy_id = strategy_id
        self.type = type
        self.config: dict = config
        self.notice_group_ids: list[int] = notice_group_ids or []
        self.notice_template = notice_template or {"anomaly_template": "", "recovery_template": ""}
        self.instance = instance

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "config": self.config,
            "notice_group_ids": self.notice_group_ids,
            "notice_template": self.notice_template,
        }

    @classmethod
    def delete_useless(cls, useless_action_ids: list[int]):
        """
        删除策略下多余的Action记录
        """
        ActionNoticeMapping.objects.filter(action_id__in=useless_action_ids).delete()
        NoticeTemplate.objects.filter(action_id__in=useless_action_ids).delete()

    def _create(self):
        """
        新建Action记录
        """
        action = ActionModel.objects.create(action_type=self.type, config=self.config, strategy_id=self.strategy_id)
        self.id = action.id

        action_notices = []
        for notice_group_id in self.notice_group_ids:
            action_notices.append(ActionNoticeMapping(action_id=self.id, notice_group_id=notice_group_id))
        ActionNoticeMapping.objects.bulk_create(action_notices)

        NoticeTemplate.objects.create(
            action_id=self.id,
            anomaly_template=self.notice_template.get("anomaly_template", ""),
            recovery_template=self.notice_template.get("recovery_template", ""),
        )

    def save(self):
        """
        根据配置新建或更新Action记录
        """
        try:
            if self.id > 0:
                action = ActionModel.objects.get(id=self.id, strategy_id=self.strategy_id)
            else:
                self._create()
                return
        except ActionModel.DoesNotExist:
            self._create()
            return
        else:
            action.action_type = self.type
            action.config = self.config
            action.save()

        action_notices = ActionNoticeMapping.objects.filter(action_id=self.id)
        exists_notice_group_ids = {notice_group.notice_group_id for notice_group in action_notices}
        current_notice_group_ids = set(self.notice_group_ids)

        # 删除多余的关联记录
        delete_notice_group_ids = exists_notice_group_ids - current_notice_group_ids
        if delete_notice_group_ids:
            ActionNoticeMapping.objects.filter(action_id=self.id, notice_group_id__in=delete_notice_group_ids).delete()

        # 新增关联记录
        new_notice_group_ids = current_notice_group_ids - exists_notice_group_ids
        if new_notice_group_ids:
            ActionNoticeMapping.objects.bulk_create(
                [
                    ActionNoticeMapping(action_id=self.id, notice_group_id=notice_group_id)
                    for notice_group_id in new_notice_group_ids
                ]
            )

        # 更新通知模板
        NoticeTemplate.objects.filter(action_id=self.id).update(
            anomaly_template=self.notice_template.get("anomaly_template", ""),
            recovery_template=self.notice_template.get("recovery_template", ""),
        )

    @classmethod
    def from_models(
        cls,
        actions: list["ActionModel"],
        notice_templates: dict[int, NoticeTemplate],
        notice_group_ids: dict[int, list[int]],
    ) -> list["Action"]:
        """
        数据模型转换为监控项对象
        """

        return [
            Action(
                strategy_id=action.strategy_id,
                id=action.id,
                type=action.action_type,
                config=action.config,
                notice_group_ids=notice_group_ids[action.id],
                notice_template={
                    "anomaly_template": notice_templates[action.id].anomaly_template,
                    "recovery_template": notice_templates[action.id].recovery_template,
                },
                instance=action,
            )
            for action in actions
        ]


class BaseActionRelation(AbstractConfig):
    """
    动作关联关系的基类
    """

    # 关联类型，目前支持 通知 和 处理动作
    RELATE_TYPE = ""

    class Serializer(serializers.Serializer):
        class OptionsSerializer(serializers.Serializer):
            converge_config = ConvergeConfigSlz()
            noise_reduce_config = NoiseReduceConfigSlz(label="降噪配置", default={})
            assign_mode = serializers.ListField(
                label="分派模式",
                required=False,
                child=serializers.ChoiceField(allow_null=False, choices=AssignMode.ASSIGN_MODE_CHOICE),
            )
            upgrade_config = UpgradeConfigSlz(label="升级配置", default={})
            exclude_notice_ways = serializers.JSONField(label="排除的通知方式", default={})
            start_time = serializers.CharField(label="生效开始时间", default="00:00:00")
            end_time = serializers.CharField(label="生效结束时间", default="23:59:59")
            chart_image_enabled = serializers.BooleanField(label="是否附带图片", default=True)

        config_id = serializers.IntegerField(required=False, label="套餐ID")
        user_groups = serializers.ListField(required=False, child=serializers.IntegerField(), label="通知组ID列表")
        signal = serializers.MultipleChoiceField(
            required=True,
            allow_empty=True,
            choices=[
                ActionSignal.ABNORMAL,
                ActionSignal.RECOVERED,
                ActionSignal.CLOSED,
                ActionSignal.ACK,
                ActionSignal.NO_DATA,
                ActionSignal.EXECUTE,
                ActionSignal.EXECUTE_SUCCESS,
                ActionSignal.EXECUTE_FAILED,
                ActionSignal.INCIDENT,
            ],
        )
        options = OptionsSerializer()

    def __init__(
        self,
        strategy_id: int,
        config_id: int = 0,
        user_groups: list[int] = None,
        signal: list[str] = None,
        id: int = None,
        options: dict = None,
        config: dict = None,
        instance: RelationModel = None,
        **kwargs,
    ):
        self.id = id
        self.strategy_id = strategy_id
        self.config_id: int = config_id
        self.user_groups: list[int] = user_groups or []
        self.user_type = kwargs.get("user_type", UserGroupType.MAIN)
        self.signal = list(signal or [])
        self.options: dict = options or {}
        self.config: dict = config or {}
        self.instance = instance

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "config_id": self.config_id,
            "user_groups": self.user_groups,
            "user_type": self.user_type,
            "signal": self.signal,
            "options": self.options,
            "relate_type": self.RELATE_TYPE,
            "config": self.config,
        }

    @classmethod
    def convert_v1_to_v2(cls, config: dict) -> dict:
        """
        将v1版本的配置转换为v2版本的配置
        """
        return {
            "id": config["id"],
            "name": config["name"],
            "desc": config.get("message", ""),
            "duty_arranges": [
                {
                    "user_group_id": config["id"],
                    "need_rotation": False,
                    "duty_time": [],
                    "effective_time": None,
                    "handoff_time": {},
                    "users": config["notice_receiver"],
                    "duty_users": [],
                    "backups": [],
                    "order": 0,
                }
            ],
            # 老版本导出通知配置会丢失企业微信机器人配置
            "alert_notice": [
                {
                    "time_range": "00:00:00--23:59:59",
                    "notify_config": [
                        {"type": notice_way, "level": int(level)} for level, notice_way in config["notice_way"].items()
                    ],
                }
            ],
            "action_notice": [
                {
                    "time_range": "00:00:00--23:59:59",
                    "notify_config": [
                        {"type": ["mail"], "phase": 3},
                        {"type": ["mail"], "phase": 2},
                        {"type": ["mail"], "phase": 1},
                    ],
                }
            ],
            "need_duty": False,
        }

    @classmethod
    def delete_useless(cls, relation_ids: list[int]):
        """
        删除策略下多余的Action关联记录
        """
        RelationModel.objects.filter(id__in=relation_ids).delete()

    def _create(self):
        """
        新建Action记录
        """
        new_relation = RelationModel.objects.create(
            strategy_id=self.strategy_id,
            config_id=self.config_id,
            relate_type=self.RELATE_TYPE,
            signal=self.signal,
            user_groups=self.user_groups,
            options=self.options,
        )
        self.id = new_relation.id

    def save(self):
        """
        根据配置新建或更新关联记录
        """
        try:
            action_relation = RelationModel.objects.get(id=self.id, strategy_id=self.strategy_id)
        except RelationModel.DoesNotExist:
            self._create()
            return
        save_fields = self.to_dict()
        for key, value in save_fields.items():
            setattr(action_relation, key, value)
        action_relation.save()

    def bulk_save(self, relations: dict[int, list[RelationModel]], action_configs: dict[int, ActionConfig] = None):
        """
        根据配置新建或更新关联记录,循环结束后批量创建或更新
        """
        action_relations = relations.get(self.strategy_id, [])
        username = get_global_user() or "unknown"
        for action_relation in action_relations:
            if self.id == action_relation.id:
                action_relation.config_id = self.config_id
                action_relation.user_groups = self.user_groups
                action_relation.user_type = self.user_type
                action_relation.signal = self.signal
                action_relation.options = self.options
                action_relation.relate_type = self.RELATE_TYPE
                action_relation.update_user = username
                action_relation.update_time = timezone.now()

                return {
                    "update_data": [
                        {
                            "cls": RelationModel,
                            "keys": [
                                "config_id",
                                "user_groups",
                                "user_type",
                                "signal",
                                "options",
                                "relate_type",
                                "update_user",
                                "update_time",
                            ],
                            "objs": [action_relation],
                        }
                    ]
                }
        else:
            new_relation = RelationModel(
                strategy_id=self.strategy_id,
                config_id=self.config_id,
                relate_type=self.RELATE_TYPE,
                signal=self.signal,
                user_groups=self.user_groups,
                options=self.options,
                create_user=username,
                create_time=timezone.now(),
            )

            return {"create_data": [{"cls": RelationModel, "objs": [new_relation]}]}

    @classmethod
    def from_models(cls, relations: list["RelationModel"], action_configs: dict[int, "ActionConfig"]):
        """
        数据模型转换为监控项对象
        """

        results = []
        for relation in relations:
            if relation.config_id not in action_configs:
                config = {}
            else:
                config_obj = action_configs[relation.config_id]
                config = {
                    "id": config_obj.id,
                    "name": config_obj.name,
                    "desc": config_obj.desc,
                    "bk_biz_id": config_obj.bk_biz_id,
                    "plugin_id": config_obj.plugin_id,
                    "execute_config": config_obj.execute_config,
                }
            results.append(
                cls(
                    strategy_id=relation.strategy_id,
                    id=relation.id,
                    user_groups=relation.validated_user_groups,
                    user_type=relation.user_type,
                    signal=relation.signal,
                    config_id=relation.config_id,
                    config=config,
                    options=relation.options,
                    instance=relation,
                )
            )

        return results


class NoticeRelation(BaseActionRelation):
    """
    通知套餐关联关系
    """

    RELATE_TYPE = RelationModel.RelateType.NOTICE

    class Serializer(BaseActionRelation.Serializer):
        config = NotifyActionConfigSlz()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if ActionSignal.ABNORMAL in self.signal and ActionSignal.NO_DATA not in self.signal:
            # 如果用户配置了异常通知，那么无数据通知也会默认打开
            self.signal.append(ActionSignal.NO_DATA)
        elif ActionSignal.ABNORMAL not in self.signal and ActionSignal.NO_DATA in self.signal:
            self.signal.remove(ActionSignal.NO_DATA)

        self.options.setdefault("assign_mode", [AssignMode.ONLY_NOTICE, AssignMode.BY_RULE])

        # 降噪配置
        self.options.setdefault("noise_reduce_config", {})
        noise_reduce_config = self.options["noise_reduce_config"]
        if noise_reduce_config.get("is_enabled", False):
            # 默认后台设置降噪的时间窗口
            noise_reduce_config["timedelta"] = settings.NOISE_REDUCE_TIMEDELTA
        # 通知是否携带图片
        self.options.setdefault("chart_image_enabled", True)
        self.options.setdefault("converge_config", {})
        converge_config = self.options["converge_config"]
        converge_config["is_enabled"] = True
        converge_config["timedelta"] = 60
        converge_config["count"] = 1
        # 通知默认防御维度
        converge_config["condition"] = [
            {"dimension": "strategy_id", "value": ["self"]},
            {"dimension": "dimensions", "value": ["self"]},
            {"dimension": "alert_level", "value": ["self"]},
            {"dimension": "signal", "value": ["self"]},
            {"dimension": "bk_biz_id", "value": ["self"]},
            {"dimension": "notice_receiver", "value": ["self"]},
            {"dimension": "notice_way", "value": ["self"]},
        ]
        # 防御方式：超出后汇总
        converge_config["converge_func"] = "collect"

        # 二级收敛配置
        if not converge_config.get("need_biz_converge", True):
            converge_config.pop("sub_converge_config", None)
        else:
            converge_config["sub_converge_config"] = {
                "timedelta": 60,
                "count": 2,
                "condition": [
                    {"dimension": "bk_biz_id", "value": ["self"]},
                    {"dimension": "notice_receiver", "value": ["self"]},
                    {"dimension": "notice_way", "value": ["self"]},
                    {"dimension": "alert_level", "value": ["self"]},
                    {"dimension": "signal", "value": ["self"]},
                ],
                "converge_func": "collect_alarm",
            }

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["config"] = self.config
        return data

    @classmethod
    def delete_useless(cls, relation_ids: list[int]):
        """
        删除策略下多余的Action关联记录
        """
        relations = RelationModel.objects.filter(id__in=relation_ids)
        config_ids = relations.values_list("config_id", flat=True)
        relations.delete()
        ActionConfig.objects.filter(id__in=list(config_ids)).delete()

    def save(self):
        """
        根据配置新建或更新关联记录
        """
        action_config = ActionConfig()

        try:
            action_relation = RelationModel.objects.get(id=self.id, strategy_id=self.strategy_id)
        except RelationModel.DoesNotExist:
            pass
        else:
            action_config = ActionConfig.objects.filter(id=action_relation.config_id).first()

        action_config.name = _("告警通知")
        action_config.desc = _("通知套餐，策略ID: {}").format(self.strategy_id)
        action_config.bk_biz_id = 0
        action_config.plugin_id = ActionConfig.NOTICE_PLUGIN_ID
        action_config.execute_config = {"template_detail": self.config}
        action_config.save()

        self.config_id = action_config.id

        return super().save()

    def bulk_save(self, relations: dict[int, list[RelationModel]], action_configs: dict[int, ActionConfig]):
        """
        根据配置新建或更新关联记录,循环结束后批量创建或更新
        """
        action_relations = relations.get(self.strategy_id, [])
        create_or_update_datas = {"create_data": [], "update_data": []}
        username = get_global_user() or "unknown"
        for action_relation in action_relations:
            if self.id == action_relation.id:
                config_id = action_relation.config_id
                action_config = action_configs.get(config_id)
                if action_config:
                    action_config.name = _("告警通知")
                    action_config.desc = _("通知套餐，策略ID: {}").format(self.strategy_id)
                    action_config.bk_biz_id = 0
                    action_config.plugin_id = ActionConfig.NOTICE_PLUGIN_ID
                    action_config.execute_config = {"template_detail": self.config}
                    action_config.update_user = username
                    action_config.update_time = timezone.now()
                    create_or_update_datas["update_data"].append(
                        {
                            "cls": ActionConfig,
                            "keys": [
                                "name",
                                "desc",
                                "bk_biz_id",
                                "plugin_id",
                                "execute_config",
                                "update_user",
                                "update_time",
                            ],
                            "objs": [action_config],
                        }
                    )
                    break
        else:
            action_config = ActionConfig(
                name=_("告警通知"),
                desc=_("通知套餐，策略ID: {}").format(self.strategy_id),
                bk_biz_id=0,
                plugin_id=ActionConfig.NOTICE_PLUGIN_ID,
                execute_config={"template_detail": self.config},
                create_user=username,
                create_time=timezone.now(),
            )
            create_or_update_datas["create_data"].append({"cls": ActionConfig, "objs": [action_config]})

        parent_data = super().bulk_save(relations)
        create_or_update_datas["create_data"].extend(parent_data.get("create_data", []))
        create_or_update_datas["update_data"].extend(parent_data.get("update_data", []))

        return create_or_update_datas

    @classmethod
    def from_models(cls, relations: list["RelationModel"], action_configs: dict[int, "ActionConfig"]):
        """
        数据模型转换为监控项对象
        """

        results = []
        for relation in relations:
            if relation.config_id not in action_configs:
                config = {}
            else:
                config_obj = action_configs[relation.config_id]
                config = config_obj.execute_config["template_detail"]

            results.append(
                cls(
                    strategy_id=relation.strategy_id,
                    id=relation.id,
                    user_type=relation.user_type,
                    user_groups=relation.validated_user_groups,
                    signal=relation.signal,
                    config_id=relation.config_id,
                    config=config,
                    options=relation.options,
                    instance=relation,
                )
            )

        return results


class ActionRelation(BaseActionRelation):
    """
    处理套餐关联关系
    """

    RELATE_TYPE = RelationModel.RelateType.ACTION

    class Serializer(BaseActionRelation.Serializer):
        class OptionsSerializer(serializers.Serializer):
            converge_config = ConvergeConfigSlz()
            skip_delay = serializers.IntegerField(required=False, default=0)

            def validate_converge_config(self, data):
                # 默认防御维度
                data["condition"] = [
                    {"dimension": "action_info", "value": ["self"]},
                ]
                return data

        options = OptionsSerializer()


class Algorithm(AbstractConfig):
    """
    检测算法
    """

    class Serializer(serializers.Serializer):
        AlgorithmSerializers = {
            "Threshold": partial(ThresholdSerializer, allow_empty=True),
            "SimpleRingRatio": SimpleRingRatioSerializer,
            "AdvancedRingRatio": AdvancedRingRatioSerializer,
            "SimpleYearRound": SimpleYearRoundSerializer,
            "AdvancedYearRound": AdvancedYearRoundSerializer,
            "OsRestart": None,
            "ProcPort": None,
            "PingUnreachable": None,
            "YearRoundAmplitude": YearRoundAmplitudeSerializer,
            "YearRoundRange": YearRoundRangeSerializer,
            "RingRatioAmplitude": RingRatioAmplitudeSerializer,
            "IntelligentDetect": IntelligentDetectSerializer,
            "TimeSeriesForecasting": TimeSeriesForecastingSerializer,
            "AbnormalCluster": AbnormalClusterSerializer,
            "MultivariateAnomalyDetection": MultivariateAnomalyDetectionSerializer,
            "HostAnomalyDetection": HostAnomalyDetectionSerializer,
            "PartialNodes": None,
            "": None,
        }

        id = serializers.IntegerField(required=False)
        type = serializers.ChoiceField(allow_blank=True, choices=AlgorithmModel.ALGORITHM_CHOICES)
        level = serializers.IntegerField()
        unit_prefix = serializers.CharField(allow_blank=True, default="")
        config = serializers.JSONField()

        def validate(self, attrs):
            """
            校验算法配置详情
            """
            if attrs["type"] not in self.AlgorithmSerializers:
                raise ValidationError(_("不存在的检测算法{}").format(attrs["type"]))

            serializer_class = self.AlgorithmSerializers[attrs["type"]]
            if not serializer_class:
                return attrs

            serializer = serializer_class(data=attrs["config"])
            serializer.is_valid(raise_exception=True)
            attrs["config"] = serializer.validated_data
            return attrs

    def __init__(
        self,
        strategy_id: int,
        item_id: int,
        type: str,
        config: dict | list[list[dict]],
        level: int,
        unit_prefix: str = "",
        id: int = 0,
        instance: AlgorithmModel = None,
        **kwargs,
    ):
        self.id = id
        self.type = type
        self.config = config
        self.level = level
        self.unit_prefix = unit_prefix
        self.strategy_id = strategy_id
        self.item_id = item_id
        self.instance = instance

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "level": self.level,
            "config": self.config,
            "unit_prefix": self.unit_prefix,
        }

    def _create(self):
        algorithm = AlgorithmModel.objects.create(
            type=self.type,
            config=self.config,
            unit_prefix=self.unit_prefix,
            strategy_id=self.strategy_id,
            item_id=self.item_id,
            level=self.level,
        )
        self.id = algorithm.id

    def save(self):
        try:
            if self.id > 0:
                algorithm: AlgorithmModel = AlgorithmModel.objects.get(
                    id=self.id, strategy_id=self.strategy_id, item_id=self.item_id
                )
            else:
                self._create()
                return
        except AlgorithmModel.DoesNotExist:
            self._create()
        else:
            algorithm.type = self.type
            algorithm.config = self.config
            algorithm.unit_prefix = self.unit_prefix
            algorithm.level = self.level
            algorithm.save()

    @classmethod
    def from_models(cls, algorithms: list[AlgorithmModel]) -> list["Algorithm"]:
        """
        根据数据模型生成算法配置对象
        """
        return [
            Algorithm(
                id=algorithm.id,
                strategy_id=algorithm.strategy_id,
                item_id=algorithm.item_id,
                type=algorithm.type,
                config=algorithm.config,
                level=algorithm.level,
                unit_prefix=algorithm.unit_prefix,
                instance=algorithm,
            )
            for algorithm in algorithms
        ]


class Detect(AbstractConfig):
    """
    检测配置
    """

    class Serializer(serializers.Serializer):
        class TriggerConfig(serializers.Serializer):
            class Uptime(serializers.Serializer):
                class TimeRange(serializers.Serializer):
                    start = serializers.CharField(label="开始时间")
                    end = serializers.CharField(label="结束时间")

                time_ranges = TimeRange(label="生效时间范围", default=[], many=True, allow_empty=True)
                calendars = serializers.ListField(
                    label="不生效日历列表", allow_empty=True, default=[], child=serializers.IntegerField()
                )

            count = serializers.IntegerField()
            check_window = serializers.IntegerField()
            uptime = Uptime(required=False)

        class RecoveryConfig(serializers.Serializer):
            check_window = serializers.IntegerField()
            status_setter = serializers.ChoiceField(
                required=False,
                choices=["recovery", "close", "recovery-nodata"],
                label="告警恢复目标状态",
                default="recovery",
            )

        id = serializers.IntegerField(required=False)
        level = serializers.IntegerField()
        expression = serializers.CharField(allow_blank=True, default="")
        trigger_config = TriggerConfig()
        recovery_config = RecoveryConfig()
        connector = serializers.CharField(allow_blank=True, default="")

        def validate_expression(self, value):
            if not value:
                return value
            try:
                parse_expression(value)
            except Exception as e:
                raise ValidationError(e)
            return value

    def __init__(
        self,
        strategy_id: int,
        level: int | str,
        trigger_config: dict,
        recovery_config: dict,
        expression: str = "",
        connector: str = "and",
        id: int = 0,
        instance: DetectModel = None,
        **kwargs,
    ):
        self.id = id
        self.level = int(level)
        self.expression = expression
        self.strategy_id = strategy_id
        self.trigger_config = trigger_config
        self.recovery_config = recovery_config
        self.connector = connector or "and"
        self.instance = instance

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "level": self.level,
            "expression": self.expression,
            "trigger_config": self.trigger_config,
            "recovery_config": self.recovery_config,
            "connector": self.connector,
        }

    def _create(self):
        detect = DetectModel.objects.create(
            strategy_id=self.strategy_id,
            level=self.level,
            expression=self.expression,
            trigger_config=self.trigger_config,
            recovery_config=self.recovery_config,
            connector=self.connector,
        )
        self.id = detect.id

    def save(self):
        try:
            if self.id > 0:
                detect: DetectModel = DetectModel.objects.get(id=self.id, strategy_id=self.strategy_id)
            else:
                self._create()
                return
        except DetectModel.DoesNotExist:
            self._create()
        else:
            detect.level = self.level
            detect.trigger_config = self.trigger_config
            detect.recovery_config = self.recovery_config
            detect.expression = self.expression
            detect.connector = self.connector
            detect.save()

    @classmethod
    def from_models(cls, detects: list["DetectModel"]) -> list["Detect"]:
        """
        数据模型转换为监控项对象
        """
        return [
            Detect(
                id=detect.id,
                strategy_id=detect.strategy_id,
                level=detect.level,
                expression=detect.expression,
                trigger_config=detect.trigger_config,
                recovery_config=detect.recovery_config,
                connector=detect.connector,
                instance=detect,
            )
            for detect in detects
        ]


class QueryConfig(AbstractConfig):
    """
    查询配置
    """

    index_set_id: int
    result_table_id: str
    data_label: str
    promql: str
    agg_method: str
    agg_interval: int
    agg_dimension: list[str]
    agg_condition: list[dict]
    metric_field: str
    unit: str
    time_field: str
    custom_event_name: str
    origin_config: dict
    intelligent_detect: dict
    values: list[str]

    # grafana图表来源
    dashboard_uid: str
    panel_id: int
    ref_id: str
    variables: dict[str, list[str]]
    snapshot_config: dict[str, Any]

    QueryConfigSerializerMapping = {
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES): BkMonitorTimeSeriesSerializer,
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG): BkMonitorLogSerializer,
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.EVENT): BkMonitorEventSerializer,
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.TIME_SERIES): BkLogSearchTimeSeriesSerializer,
        (DataSourceLabel.BK_LOG_SEARCH, DataTypeLabel.LOG): BkLogSearchLogSerializer,
        (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES): CustomTimeSeriesSerializer,
        (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT): CustomEventSerializer,
        (DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES): BkDataTimeSeriesSerializer,
        (DataSourceLabel.BK_FTA, DataTypeLabel.EVENT): BkFtaEventSerializer,
        (DataSourceLabel.BK_FTA, DataTypeLabel.ALERT): BkFtaAlertSerializer,
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.ALERT): BkMonitorAlertSerializer,
        (DataSourceLabel.BK_APM, DataTypeLabel.TIME_SERIES): BkApmTimeSeriesSerializer,
        (DataSourceLabel.BK_APM, DataTypeLabel.LOG): BkApmTraceSerializer,
        (DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES): PrometheusTimeSeriesSerializer,
        (DataSourceLabel.DASHBOARD, DataTypeLabel.TIME_SERIES): GrafanaTimeSeriesSerializer,
    }

    def __init__(
        self,
        strategy_id: int,
        item_id: int,
        data_source_label: str,
        data_type_label: str,
        alias: str,
        id: int = 0,
        metric_id: str = "",
        instance: QueryConfigModel = None,
        **kwargs,
    ):
        self.strategy_id = strategy_id
        self.item_id = item_id
        self.data_source_label = data_source_label
        self.data_type_label = data_type_label
        self.alias = alias
        self.id = id
        self.metric_id = metric_id or ""
        self.instance = instance
        serializer_class = self.get_serializer_class(data_source_label, data_type_label)
        serializer = serializer_class(data=kwargs)
        serializer.is_valid(raise_exception=True)

        for field, value in serializer.validated_data.items():
            setattr(self, field, value)

    @classmethod
    def get_serializer_class(cls, data_source_label: str, data_type_label: str) -> type[QueryConfigSerializer]:
        return cls.QueryConfigSerializerMapping[(data_source_label, data_type_label)]

    def get_metric_id(self):
        return get_metric_id(
            data_source_label=self.data_source_label,
            data_type_label=self.data_type_label,
            result_table_id=getattr(self, "result_table_id", ""),
            index_set_id=getattr(self, "index_set_id", ""),
            metric_field=getattr(self, "metric_field", ""),
            custom_event_name=getattr(self, "custom_event_name", ""),
            alert_name=getattr(self, "alert_name", ""),
            bkmonitor_strategy_id=getattr(self, "bkmonitor_strategy_id", ""),
            promql=getattr(self, "promql", ""),
        )

    def to_dict(self):
        # 自动生成metric_id
        if not self.metric_id:
            self.metric_id = self.get_metric_id()

        result = {
            "data_source_label": self.data_source_label,
            "data_type_label": self.data_type_label,
            "alias": self.alias,
            "metric_id": self.metric_id,
            "id": self.id,
        }

        for field in self.get_serializer_class(self.data_source_label, self.data_type_label)().get_config_field_names():
            if not hasattr(self, field):
                continue

            value = getattr(self, field)

            # 监控条件的值默认转换为字符串
            if field == "agg_condition":
                for condition in value:
                    if not isinstance(condition["value"], list):
                        condition["value"] = [condition["value"]]

            result[field] = value
        return result

    def _create(self):
        serializer = self.get_serializer_class(self.data_source_label, self.data_type_label)(data=self.to_dict())
        serializer.is_valid(raise_exception=True)
        obj = QueryConfigModel.objects.create(
            strategy_id=self.strategy_id,
            item_id=self.item_id,
            data_source_label=self.data_source_label,
            data_type_label=self.data_type_label,
            metric_id=self.metric_id,
            alias=self.alias,
            config=serializer.validated_data,
        )
        self.id = obj.id

    def save(self):
        self._clean_empty_dimension()
        self.supplement_adv_condition_dimension()

        try:
            if self.id > 0:
                query_config: QueryConfigModel = QueryConfigModel.objects.get(
                    id=self.id, item_id=self.item_id, strategy_id=self.strategy_id
                )
            else:
                self._create()
                return
        except QueryConfigModel.DoesNotExist:
            self._create()
            return

        serializer = self.get_serializer_class(self.data_source_label, self.data_type_label)(data=self.to_dict())
        serializer.is_valid(raise_exception=True)
        data = {
            "alias": self.alias,
            "data_source_label": self.data_source_label,
            "data_type_label": self.data_type_label,
            "metric_id": self.metric_id,
            "config": serializer.validated_data,
        }
        for field, value in data.items():
            setattr(query_config, field, value)
        query_config.save()

    @classmethod
    def from_models(cls, query_configs: list[QueryConfigModel]) -> list["QueryConfig"]:
        """
        根据数据模型获取查询配置对象
        """
        records = []
        for query_config in query_configs:
            record = QueryConfig(
                id=query_config.id,
                strategy_id=query_config.strategy_id,
                item_id=query_config.item_id,
                alias=query_config.alias,
                data_source_label=query_config.data_source_label,
                data_type_label=query_config.data_type_label,
                metric_id=query_config.metric_id,
                instance=query_config,
                **query_config.config,
            )

            records.append(record)
        return records

    def supplement_adv_condition_dimension(self):
        """
        高级条件补全维度
        """
        if not hasattr(self, "agg_dimension"):
            return
        data_source = load_data_source(self.data_source_label, self.data_type_label)
        has_advance_method = False
        dimensions = set()
        for condition in self.agg_condition:
            if condition["method"] in data_source.ADVANCE_CONDITION_METHOD:
                has_advance_method = True
            # 数值型字段，不需要进行聚合分组
            if condition["method"] in ["gt", "gte", "lt", "lte", "eq", "neq"]:
                continue
            dimensions.add(condition["key"])

        if has_advance_method:
            self.agg_dimension = list(set(self.agg_dimension) | dimensions)

    def _clean_empty_dimension(self):
        """
        清理空维度
        """
        if not hasattr(self, "agg_dimension"):
            return

        self.agg_dimension = [dimension for dimension in self.agg_dimension if dimension]


class Item(AbstractConfig):
    """
    监控项配置
    """

    class Serializer(serializers.Serializer):
        class TargetSerializer(serializers.Serializer):
            field = serializers.CharField()
            value = serializers.ListField(child=serializers.DictField(), allow_empty=False)
            method = serializers.CharField()

            def validate(self, attrs: dict):
                attrs["value"] = [v for v in attrs["value"] if v]
                return attrs

        class FunctionSerializer(serializers.Serializer):
            class FunctionParamsSerializer(serializers.Serializer):
                id = serializers.CharField()
                value = serializers.CharField()

            id = serializers.CharField()
            params = serializers.ListField(child=serializers.DictField(), allow_empty=True)

        id = serializers.IntegerField(default=0)
        name = serializers.CharField()
        expression = serializers.CharField(allow_blank=True, default="")
        functions = serializers.ListField(allow_empty=True, default=[], child=FunctionSerializer())
        origin_sql = serializers.CharField(allow_blank=True, default="")
        target = serializers.ListField(
            allow_empty=True, child=serializers.ListField(child=TargetSerializer(), allow_empty=True)
        )
        no_data_config = serializers.DictField()

        query_configs = serializers.ListField(allow_empty=False)
        algorithms = Algorithm.Serializer(many=True)
        metric_type = serializers.CharField(allow_blank=True, default="")
        # 目前只允许后台修改
        # time_delay = serializers.IntegerField(default=0)

    def __init__(
        self,
        strategy_id: int,
        name: str,
        no_data_config: dict,
        target: list = None,
        expression: str = "",
        functions: list = None,
        origin_sql: str = "",
        id: int = 0,
        query_configs: list[dict] = None,
        algorithms: list[dict] = None,
        metric_type: str = "",
        instance: ItemModel = None,
        time_delay: int = None,
        **kwargs,
    ):
        self.functions = functions or []
        self.name = name
        self.no_data_config = no_data_config
        self.target: list[list[dict]] = target or [[]]
        self.expression = expression
        self.origin_sql = origin_sql
        self.query_configs: list[QueryConfig] = [QueryConfig(strategy_id, id, **c) for c in query_configs or []]
        self.algorithms: list[Algorithm] = [Algorithm(strategy_id, id, **c) for c in algorithms or []]
        self.strategy_id = strategy_id
        self.id = id
        self.instance = instance
        self.time_delay = time_delay or 0

        if metric_type:
            self.metric_type = metric_type
        else:
            self.metric_type = self.query_configs[0].data_type_label if self.query_configs else ""

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        self._id = value
        for obj in chain(self.query_configs, self.algorithms):
            obj.item_id = value

    @property
    def strategy_id(self):
        return self._strategy_id

    @strategy_id.setter
    def strategy_id(self, value):
        self._strategy_id = value
        for obj in chain(self.query_configs, self.algorithms):
            obj.strategy_id = value

    @property
    def public_dimensions(self):
        # 公共维度
        return list(
            reduce(
                lambda x, y: x & y,
                [set(getattr(query_config, "agg_dimension", [])) for query_config in self.query_configs],
            )
        )

    def to_dict(self):
        if self.metric_type:
            metric_type = self.metric_type
        else:
            metric_type = self.query_configs[0].data_type_label
        return {
            "id": self.id,
            "name": self.name,
            "no_data_config": self.no_data_config,
            "target": self.target,
            "expression": self.expression,
            "functions": self.functions,
            "origin_sql": self.origin_sql,
            "query_configs": [query_config.to_dict() for query_config in self.query_configs],
            "algorithms": [algorithm.to_dict() for algorithm in self.algorithms],
            "metric_type": metric_type,
            "time_delay": self.time_delay,
        }

    def to_unify_query_config(self):
        """
        生成统一查询配置
        """
        # 查询配置生成
        query_list = []
        for query_config in self.query_configs:
            # 查询条件格式转换
            conditions = {"field_list": [], "condition_list": []}
            for condition in query_config.agg_condition:
                if conditions["field_list"]:
                    conditions["condition_list"].append(condition.get("condition", "and"))

                value = condition["value"] if isinstance(condition["value"], list) else [condition["value"]]
                conditions["field_list"].append(
                    {"field_name": condition["key"], "value": value, "op": condition["method"]}
                )
            query = {
                "table_id": query_config.result_table_id,
                "field_name": query_config.metric_field,
                "aggregate_method_list": [{"method": query_config.agg_method, "args_list": []}],
                "reference_name": query_config.alias,
                "dimensions": query_config.agg_dimension,
                "driver": "influxdb",
                "time_field": getattr(query_config, "time_field", "time"),
                "conditions": conditions,
            }

            query["keep_columns"] = ["_time", query["reference_name"], *query_config.agg_dimension]
            if query_config.agg_interval:
                query["interval"] = f"{query_config.agg_interval}s"
            query_list.append(query)

        return {
            "query_list": query_list,
            "metric_merge": add_expression_functions(self.expression, self.functions),
            "join_on": self.public_dimensions,
            "order_by": ["-time"],
            "keep_columns": ["_result", "_time", *[query["reference_name"] for query in query_list]],
        }

    @classmethod
    def delete_useless(cls, useless_item_ids: list[int]):
        """
        删除策略下多余的Item记录
        """
        AlgorithmModel.objects.filter(item_id__in=useless_item_ids).delete()
        QueryConfigModel.objects.filter(item_id__in=useless_item_ids).delete()

    def _create(self):
        data = self.to_dict()
        data.pop("id", None)
        data.pop("query_configs", None)
        data.pop("algorithms", None)
        data["name"] = data.get("name", "")[:256]
        item = ItemModel.objects.create(strategy_id=self.strategy_id, **data)
        self.id = item.id
        return item

    def save_algorithms(self):
        self.reuse_exists_records(
            AlgorithmModel,
            AlgorithmModel.objects.filter(strategy_id=self.strategy_id, item_id=self.id).only("id"),
            self.algorithms,
            Algorithm,
        )

        for algo in self.algorithms:
            algo.save()

    def save_query_configs(self):
        self.reuse_exists_records(
            QueryConfigModel,
            QueryConfigModel.objects.filter(strategy_id=self.strategy_id, item_id=self.id).only("id"),
            self.query_configs,
            QueryConfig,
        )

        for query_config in self.query_configs:
            query_config.save()

    def save(self):
        try:
            if self.id > 0:
                item: ItemModel = ItemModel.objects.get(id=self.id, strategy_id=self.strategy_id)
                item.name = self.name
                item.no_data_config = self.no_data_config
                item.target = self.target
                item.expression = self.expression
                item.functions = self.functions
                item.origin_sql = self.origin_sql
                item.metric_type = self.metric_type
                item.time_delay = self.time_delay if self.time_delay else item.time_delay
                item.save()
            else:
                item = self._create()
        except ItemModel.DoesNotExist:
            item = self._create()

        # 复用旧的记录
        self.save_algorithms()
        self.save_query_configs()

        item.save()

    @classmethod
    def from_models(
        cls,
        items: list["ItemModel"],
        algorithms: dict[int, list[AlgorithmModel]],
        query_configs: dict[int, list[QueryConfigModel]],
    ) -> list["Item"]:
        """
        数据模型转换为监控项对象
        """
        records = []
        for item in items:
            record = Item(
                id=item.id,
                strategy_id=item.strategy_id,
                name=item.name,
                expression=item.expression,
                functions=item.functions,
                origin_sql=item.origin_sql,
                no_data_config=item.no_data_config,
                target=item.target,
                metric_type=item.metric_type,
                instance=item,
                time_delay=item.time_delay,
            )
            record.algorithms = Algorithm.from_models(algorithms[item.id])
            record.query_configs = QueryConfig.from_models(query_configs[item.id])
            records.append(record)

        return records


class Strategy(AbstractConfig):
    """
    策略 数据结构
    """

    version = "v2"

    ExtendFields = [
        "index_set_id",
        "time_field",
        "values",
        "custom_event_name",
        "origin_config",
        "intelligent_detect",
    ]

    class Serializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        id = serializers.IntegerField(required=False)
        name = serializers.CharField()
        type = serializers.CharField(default=StrategyModel.StrategyType.Monitor)
        source = serializers.CharField(default=get_source_app_code)
        scenario = serializers.CharField()
        is_enabled = serializers.BooleanField(default=True)
        is_invalid = serializers.BooleanField(default=False)
        invalid_type = serializers.CharField(default=StrategyModel.InvalidType.NONE, allow_blank=True)

        items = serializers.ListField(child=Item.Serializer(), allow_empty=False)
        detects = serializers.ListField(child=Detect.Serializer(), allow_empty=False)
        actions = serializers.ListField(child=ActionRelation.Serializer(), allow_empty=True)
        notice = NoticeRelation.Serializer()
        labels = serializers.ListField(allow_empty=True, default=[], child=serializers.CharField())
        app = serializers.CharField(allow_blank=True, default="")
        path = serializers.CharField(allow_blank=True, default="")
        priority = serializers.IntegerField(min_value=0, required=False, default=None, max_value=10000, allow_null=True)
        metric_type = serializers.CharField(allow_blank=True, default="")

        def validate(self, attrs):
            name = attrs.get("name")
            is_builtin_name = name.startswith("集成内置") or name.startswith("Datalink BuiltIn")
            if attrs.get("source") != DATALINK_SOURCE and is_builtin_name:
                raise ValidationError(detail="Name starts with 'Datalink BuiltIn' and '集成内置' is forbidden")
            return attrs

    def __init__(
        self,
        bk_biz_id: int,
        name: str,
        scenario: str,
        source: str = settings.APP_CODE,
        type: str = StrategyModel.StrategyType.Monitor,
        id: int = 0,
        items: list[dict] = None,
        actions: list[dict] = None,
        notice: dict = None,
        detects: list[dict] = None,
        is_enabled: bool = True,
        is_invalid: bool = False,
        invalid_type: str = StrategyModel.InvalidType.NONE,
        update_user: str = "",
        update_time: datetime = None,
        create_user: str = "",
        create_time: datetime = None,
        labels: list[str] = None,
        app: str = "",
        path: str = "",
        priority: int = None,
        priority_group_key: str = None,
        metric_type: str = "",
        instance: StrategyModel = None,
        **kwargs,
    ):
        """
        :param id: 策略ID
        :param name: 策略名称
        :param source: 来源应用
        :param scenario: 监控对象类型
        """
        self.bk_biz_id = bk_biz_id
        self.name = name
        self.source = source
        self.scenario = scenario
        self.type = type
        self.items: list[Item] = [Item(id, **item) for item in items or []]
        self.detects: list[Detect] = [Detect(id, **detect) for detect in detects or []]
        self.actions: list[ActionRelation] = [ActionRelation(id, **action) for action in actions or []]
        self.notice: NoticeRelation = NoticeRelation(id, **(notice or {}))
        self.is_enabled = is_enabled
        self.is_invalid = is_invalid
        self.invalid_type = invalid_type
        self.id = id
        self.update_user = update_user
        self.update_time = update_time or arrow.utcnow().datetime
        self.create_user = create_user
        self.create_time = create_time or arrow.utcnow().datetime
        self.labels = labels or []
        self.app = app or ""
        self.path = path or ""
        self.priority = priority
        self.priority_group_key = priority_group_key or ""
        self.instance = instance

        if isinstance(self.update_time, int | str):
            self.update_time = arrow.get(update_time).datetime

        if isinstance(self.create_time, int | str):
            self.create_time = arrow.get(create_time).datetime

        for item in self.items:
            item.metric_type = metric_type

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        self._id = value
        for obj in chain(self.actions, self.items, self.detects, [self.notice]):
            obj.strategy_id = value

    def _get_dashboard_panel_query_config(self, query_config: QueryConfig) -> dict:
        """
        获取Grafana图表查询配置
        """
        panel_query = get_grafana_panel_query(
            self.bk_biz_id, query_config.dashboard_uid, query_config.panel_id, query_config.ref_id
        )
        if not panel_query:
            raise ValidationError(_("无法获取到Grafana图表查询配置"))

        try:
            converted_config = grafana_panel_to_config(panel_query, query_config.variables)
        except (ValidationError, ValueError):
            raise ValidationError(_("Grafana图表查询配置转换失败"))

        return converted_config

    def to_dict(self, convert_dashboard: bool = True) -> dict:
        """
        转换为JSON字典
        """
        if self.priority is None:
            priority_group_key = ""
        else:
            if self.priority_group_key:
                priority_group_key = self.priority_group_key
            else:
                priority_group_key = self.get_priority_group_key(self.bk_biz_id, self.items)

        config = {
            "id": self.id,
            "version": self.version,
            "bk_biz_id": self.bk_biz_id,
            "name": self.name,
            "source": self.source,
            "scenario": self.scenario,
            "type": self.type,
            "items": [item.to_dict() for item in self.items],
            "detects": [detect.to_dict() for detect in self.detects],
            "actions": [action.to_dict() for action in self.actions],
            "notice": self.notice.to_dict(),
            "is_enabled": self.is_enabled,
            "is_invalid": self.is_invalid,
            "invalid_type": self.invalid_type,
            "update_time": strftime_local(self.update_time),
            "update_user": self.update_user,
            "create_time": strftime_local(self.create_time),
            "create_user": self.create_user,
            "labels": self.labels,
            "app": self.app,
            "path": self.path,
            "priority": self.priority,
            "priority_group_key": priority_group_key,
            "edit_allowed": self.source != DATALINK_SOURCE,
        }

        config["metric_type"] = config["items"][0]["metric_type"] if config["items"] else ""

        for item in config["items"]:
            if item["expression"]:
                continue
            item["expression"] = " + ".join([query_config["alias"] for query_config in item["query_configs"]])

        # grafana来源策略适配
        query_config = self.items[0].query_configs[0]
        if query_config.data_source_label == DataSourceLabel.DASHBOARD and convert_dashboard:
            config["from_dashboard"] = {
                "dashboard_uid": query_config.dashboard_uid,
                "panel_id": query_config.panel_id,
                "ref_id": query_config.ref_id,
                "valid": True,
                "message": "",
            }

            try:
                converted_config = self._get_dashboard_panel_query_config(query_config)
            except ValidationError as e:
                config["is_invalid"] = True
                config["invalid_type"] = StrategyModel.InvalidType.INVALID_DASHBOARD_PANEL
                config["from_dashboard"]["valid"] = False
                config["from_dashboard"]["message"] = str(e.detail[0])

                # 使用快照配置
                converted_config = query_config.snapshot_config

            item = config["items"][0]
            item["query_configs"] = converted_config["query_configs"]
            item["expression"] = converted_config["expression"]
            item["functions"] = converted_config["functions"]
            item["target"] = converted_config["target"]

            # 重新生成 metric_id 字段
            for query_config in item["query_configs"]:
                qc = QueryConfig(strategy_id=self.id, item_id=item["id"], **query_config)
                query_config["metric_id"] = qc.get_metric_id()

        return config

    @classmethod
    def fill_user_groups(cls, configs: list[dict], with_detail=False):
        """
        显示告警组信息
        """
        strategy_ids = [config["id"] for config in configs]
        action_relations = RelationModel.objects.filter(strategy_id__in=strategy_ids)
        user_group_ids = []
        for action_relation in action_relations:
            user_group_ids.extend(action_relation.validated_user_groups)
        if with_detail:
            user_groups_slz = UserGroupDetailSlz(UserGroup.objects.filter(id__in=user_group_ids), many=True).data
        else:
            user_groups_slz = UserGroupSlz(UserGroup.objects.filter(id__in=user_group_ids), many=True).data
        user_groups = {group["id"]: dict(group) for group in user_groups_slz}

        for config in configs:
            for action in config["actions"] + [config["notice"]]:
                user_group_list = []
                for user_group_id in action["user_groups"]:
                    if user_group_id and user_group_id in user_groups:
                        user_group_list.append(user_groups[user_group_id])
                action["user_group_list"] = user_group_list

    def to_dict_v1(self, config_type: str = "frontend") -> dict:
        """
        TODO 转换为旧版策略JSON字典
        """
        item_list = []
        for item in self.items:
            query_config = item.query_configs[0].to_dict()

            if (
                item.query_configs[0].data_source_label == DataSourceLabel.BK_LOG_SEARCH
                and item.query_configs[0].data_type_label == DataTypeLabel.LOG
            ):
                query_config["keywords_query_string"] = query_config["query_string"]
                del query_config["query_string"]
                query_config["agg_method"] = "COUNT"

            item_config = {
                "id": item.id,
                "item_id": item.id,
                "name": item.name,
                "item_name": item.name,
                "strategy_id": self.id,
                "update_time": self.update_time,
                "create_time": self.create_time,
                "metric_id": item.query_configs[0].metric_id,
                "no_data_config": item.no_data_config,
                "target": item.target,
                "rt_query_config_id": query_config["id"],
                "data_source_label": query_config.pop("data_source_label"),
                "data_type_label": query_config.pop("data_type_label"),
                "algorithm_list": [
                    {
                        "id": algorithm.id,
                        "algorithm_id": algorithm.id,
                        "algorithm_type": algorithm.type,
                        "algorithm_unit": algorithm.unit_prefix,
                        "algorithm_config": algorithm.config,
                        "trigger_config": self.detects[0].trigger_config,
                        "recovery_config": self.detects[0].recovery_config,
                        "level": algorithm.level,
                    }
                    for algorithm in item.algorithms
                ],
                "labels": self.labels,
            }

            # 查询配置
            rt_query_config = {
                "unit_conversion": 1,
                "extend_fields": {},
            }
            for field, value in query_config.items():
                if field in self.ExtendFields:
                    rt_query_config["extend_fields"][field] = value
                else:
                    rt_query_config[field] = value

            # frontend和backend两种格式
            if config_type == "frontend":
                rt_query_config.pop("id", None)
                item_config.update(rt_query_config)
            else:
                rt_query_config["rt_query_config_id"] = query_config["id"]
                item_config["rt_query_config"] = rt_query_config

            item_list.append(item_config)

        # 处理动作适配逻辑 - 开始
        notice = self.notice

        anomaly_template = None
        recovery_template = None
        for template in notice.config.get("template"):
            if template["signal"] == ActionSignal.ABNORMAL:
                anomaly_template = template
            elif template["signal"] == ActionSignal.RECOVERED:
                recovery_template = template

        action = {
            "id": notice.id,
            "action_id": notice.id,
            "config": {
                "alarm_start_time": notice.options.get("start_time", "00:00:00"),
                "alarm_end_time": notice.options.get("end_time", "23:59:59"),
                "alarm_interval": notice.config.get("notify_interval", 7200) // 60,
                "send_recovery_alarm": ActionSignal.RECOVERED in notice.signal,
            },
            "action_type": ActionPluginType.NOTICE,
            "notice_template": {
                "anomaly_template": anomaly_template["message_tmpl"] if anomaly_template else "",
                "recovery_template": recovery_template["message_tmpl"] if recovery_template else "",
            },
            "notice_group_list": notice.user_groups,
        }
        # 处理动作适配逻辑 - 结束

        result = {
            "id": self.id,
            "strategy_id": self.id,
            "name": self.name,
            "strategy_name": self.name,
            "bk_biz_id": self.bk_biz_id,
            "scenario": self.scenario,
            "is_enabled": self.is_enabled,
            "is_invalid": self.is_invalid,
            "invalid_type": self.invalid_type,
            "update_time": self.update_time,
            "update_user": self.update_user,
            "create_time": self.create_time,
            "create_user": self.create_user,
            "action_list": [action],
            "item_list": item_list,
            "labels": self.labels,
        }

        for item in result["item_list"]:
            item.pop("alias", None)
        return result

    def convert(self):
        """
        特殊逻辑转换
        """
        from bkmonitor.strategy.convert import Convertors

        for convertor in Convertors:
            convertor.convert(self)

    def restore(self):
        """
        特殊逻辑重置
        """
        from bkmonitor.strategy.convert import Convertors

        for convertor in Convertors:
            convertor.restore(self)

    @classmethod
    def from_dict_v1(cls, config: dict, config_type="frontend") -> "Strategy":
        """
        由旧策略配置JSON字典生成对象
        """
        config = copy.deepcopy(config)
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
            old_action = None

        # 日志平台查询参数转换
        if "keywords_query_string" in item:
            item["query_string"] = item["keywords_query_string"]

        # 时间格式转换
        update_time = config.get("update_time")
        create_time = config.get("create_time")
        if isinstance(update_time, int):
            config["update_time"] = datetime.utcfromtimestamp(update_time)
        if isinstance(create_time, int):
            config["create_time"] = datetime.utcfromtimestamp(create_time)

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
                    }
                }
            )

        return Strategy(
            **{
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
        )

    @classmethod
    def convert_v1_to_v2(cls, strategy_config: dict) -> dict:
        """
        旧版策略配置转新版策略
        """
        if not strategy_config or strategy_config.get("version") == "v2":
            return strategy_config

        # query_md5转换
        item_query_md5 = {}
        for item in strategy_config["item_list"]:
            if "query_md5" in item:
                item_query_md5[item["id"]] = item["query_md5"]

        strategy_obj = Strategy.from_dict_v1(strategy_config)
        new_strategy_config = strategy_obj.to_dict()

        # 旧版通知组转换
        if strategy_config.get("action_list"):
            old_action = strategy_config["action_list"][0]
            if old_action["notice_group_list"] and isinstance(old_action["notice_group_list"][0], dict):
                user_group_list = [
                    NoticeRelation.convert_v1_to_v2(notice_group) for notice_group in old_action["notice_group_list"]
                ]
                new_strategy_config["notice"]["user_group_list"] = user_group_list

        # query_md5适配
        for item in new_strategy_config["items"]:
            if item["id"] in item_query_md5:
                item["query_md5"] = item_query_md5[item["id"]]

        return new_strategy_config

    @classmethod
    def convert_v2_to_v1(cls, strategy_config: dict) -> dict:
        """
        新版策略配置转旧版策略
        """
        if not strategy_config or strategy_config.get("version") != "v2":
            return strategy_config

        strategy = Strategy(**strategy_config)
        return strategy.to_dict_v1()

    def _create(self):
        strategy = StrategyModel.objects.create(
            name=self.name,
            scenario=self.scenario,
            source=self.source,
            bk_biz_id=self.bk_biz_id,
            type=self.type,
            is_enabled=self.is_enabled,
            is_invalid=self.is_invalid,
            invalid_type=self.invalid_type,
            create_user=self._get_username(),
            update_user=self._get_username(),
            priority=self.priority,
            priority_group_key=self.get_priority_group_key(self.bk_biz_id, self.items) if self.priority else "",
        )
        self.id = strategy.id

    def save_labels(self):
        """
        保存策略标签
        """
        labels = [f"/{label.strip('/')}/" for label in self.labels]

        # 校验标签长度
        for label in labels:
            if len(label) > 128:
                raise ValidationError(_("标签长度超长，请调整后重试"))

        # 如果某个标签是另一个标签的父标签，则抛弃该标签
        redundant_labels = set()
        for label1, label2 in permutations(labels, 2):
            if label1 == label2:
                continue

            if label1.startswith(label2):
                redundant_labels.add(label2)
            elif label2.startswith(label1):
                redundant_labels.add(label1)
        self.labels = [label for label in labels if label not in redundant_labels]

        # 清理旧标签
        StrategyLabel.objects.filter(bk_biz_id=self.bk_biz_id, strategy_id=self.id).delete()

        # 批量创建新标签
        StrategyLabel.objects.bulk_create(
            StrategyLabel(label_name=label, strategy_id=self.id, bk_biz_id=self.bk_biz_id) for label in self.labels
        )

    @transaction.atomic
    def save_actions(self):
        """保存actions配置."""
        self.reuse_exists_records(
            RelationModel,
            RelationModel.objects.filter(strategy_id=self.id, relate_type=RelationModel.RelateType.ACTION).only("id"),
            self.actions,
            ActionRelation,
        )

        # 保存子配置
        for action in self.actions:
            action.save()

    @transaction.atomic
    def save_notice(self, rollback=False):
        """保存actions配置."""
        self.reuse_exists_records(
            RelationModel,
            RelationModel.objects.filter(strategy_id=self.id, relate_type=RelationModel.RelateType.NOTICE).only("id"),
            [self.notice],
            NoticeRelation,
        )

        # 保存子配置
        self.notice.save()

    @transaction.atomic
    def bulk_save_notice(self, relations, action_configs):
        """保存actions配置,循环结束后批量创建或更新."""
        self.reuse_exists_records(
            RelationModel,
            relations.get(self.id),
            [self.notice],
            NoticeRelation,
        )

        # 保存子配置
        create_or_update_datas = self.notice.bulk_save(relations, action_configs)

        return create_or_update_datas

    @transaction.atomic
    def save(self, rollback=False):
        """
        保存策略配置
        """
        # grafana策略标记
        if self.items[0].query_configs[0].data_source_label == DataSourceLabel.DASHBOARD:
            self.type = StrategyModel.StrategyType.Dashboard

            # 补充快照信息
            if not self.items[0].query_configs[0].snapshot_config:
                converted_config = self._get_dashboard_panel_query_config(self.items[0].query_configs[0])
                self.items[0].query_configs[0].snapshot_config = converted_config

        self.supplement_inst_target_dimension()
        need_access_aiops, algorithm_name = self.check_aiops_access()

        if not rollback:
            history = StrategyHistoryModel.objects.create(
                create_user=self._get_username(),
                strategy_id=self.id,
                operate="create" if self.id == 0 else "update",
                content=self.to_dict(),
            )

            # 重名检测
            if StrategyModel.objects.filter(bk_biz_id=self.bk_biz_id, name=self.name).exclude(id=self.id).exists():
                history.message = _("策略名称({})不能重复").format(self.name)
                history.save()
                raise CreateStrategyError(history.message)
        else:
            history = None

        old_strategy = None
        try:
            if self.id > 0:
                strategy = StrategyModel.objects.get(id=self.id, bk_biz_id=self.bk_biz_id)

                # 记录原始配置
                old_strategy = Strategy.from_models([strategy])[0]

                strategy.name = self.name
                strategy.scenario = self.scenario
                strategy.source = self.source
                strategy.type = self.type
                strategy.is_enabled = self.is_enabled
                strategy.is_invalid = self.is_invalid
                strategy.invalid_type = self.invalid_type
                strategy.update_user = self._get_username()
                strategy.priority = self.priority
                strategy.priority_group_key = (
                    self.get_priority_group_key(self.bk_biz_id, self.items) if self.priority else ""
                )
                strategy.save()
            else:
                self._create()

            # 复用当前存在的记录
            model_configs = [
                (ItemModel, Item, self.items),
                (DetectModel, Detect, self.detects),
            ]
            for model, config_cls, configs in model_configs:
                objs = model.objects.filter(strategy_id=self.id).only("id")
                self.reuse_exists_records(model, objs, configs, config_cls)

            # 保存子配置
            for obj in chain(self.items, self.detects):
                obj.save()

            # 复用旧ID地保存actions和notice
            self.save_actions()
            self.save_notice()

            # 保存策略标签
            self.save_labels()

            if history and history.strategy_id == 0:
                history.strategy_id = self.id
                history.save()
        except StrategyModel.DoesNotExist:
            if history:
                history.message = _("策略({})不存在").format(self.id)
                history.save()
            raise StrategyNotExist()
        except Exception as e:
            # 回滚失败直接报错
            if rollback:
                raise e

            # 清空或回滚配置
            if history.operate == "create":
                self.delete()
            elif old_strategy:
                try:
                    old_strategy.save(rollback=True)
                except Exception as rollback_exception:
                    logger.error(f"策略({self.id})回滚失败")
                    logger.exception(rollback_exception)

            # 记录错误信息
            history.message = traceback.format_exc()
            history.save()
            raise e

        history.status = True
        history.save()

        if need_access_aiops:
            self.access_aiops(algorithm_name)

    def check_aiops_access(self):
        """
        检查智能监控接入配置
        (目前仅支持监控时序、计算平台时序数据)
        """
        from bkmonitor.models import AlgorithmModel

        # 1. 未开启计算平台接入，则直接返回
        if not settings.IS_ACCESS_BK_DATA:
            return False, ""

        # 2. 获取配置的智能检测算法(AIOPS)
        intelligent_algorithm = None
        algorithm_plan_id = None
        for algorithm in chain(*(item.algorithms for item in self.items)):
            if algorithm.type in AlgorithmModel.AIOPS_ALGORITHMS:
                intelligent_algorithm = algorithm.type
                algorithm_plan_id = algorithm.config.get("plan_id", 0)
                break

        # 3. 未找到配置的智能检测算法(AIOPS)，则直接返回
        if not intelligent_algorithm:
            return False, ""

        # 4. 遍历每个监控项的查询配置，以判断数据来源并执行相应处理逻辑
        need_access = False
        for item in self.items:
            for query_config in item.query_configs:
                need_access = need_access or self.check_aiops_query_config(
                    query_config, intelligent_algorithm, algorithm_plan_id
                )
                if getattr(query_config, "intelligent_detect", {}).get("use_sdk", False):
                    item.time_delay = 60

        return need_access, intelligent_algorithm

    def check_aiops_query_config(
        self, query_config: QueryConfig, algorithm_name: str = None, algorithm_plan_id: int = None
    ):
        # 4.1 如果数据类型不是时序数据，则跳过不处理
        if query_config.data_type_label not in (DataTypeLabel.TIME_SERIES, DataTypeLabel.LOG, DataTypeLabel.EVENT):
            return False

        # 4.2 标记是否需要接入智能检测算法，默认False表示不接入
        need_access = False
        # 4.3.1 目前result_table_id为空的指标，不在计算平台或者无法接入计算平台
        if getattr(query_config, "result_table_id", None):
            # 4.3.2 如果数据来源是监控采集器或者计算平台的结果表，则不支持一些特殊过滤条件
            if query_config.data_source_label not in (DataSourceLabel.BK_MONITOR_COLLECTOR, DataSourceLabel.BK_DATA):
                data_source_label_name = DATA_SOURCE_LABEL_ALIAS.get(
                    query_config.data_source_label, query_config.data_source_label
                )

                plan = AlgorithmChoiceConfig.objects.filter(id=algorithm_plan_id).first()
                if not plan:
                    raise ValidationError(_("未找到当前智能算法的方案配置，请联系系统管理员"))

                unsupported_algorithms = [
                    "log_patterns_anomaly_detection_with_dimensions",
                    "general_anomaly_detection_for_crash_failure_metric",
                ]
                if plan.name in unsupported_algorithms:
                    raise ValidationError(_(f"{plan.alias}算法不支持数据来源: {data_source_label_name}"))

            if query_config.data_source_label in (DataSourceLabel.BK_MONITOR_COLLECTOR, DataSourceLabel.BK_DATA):
                need_access = True

        # 4.4 如果不需要走bkbase接入流程或者配置使用SDK进行检测，则更新query_config中关于使用sdk的配置
        intelligent_detect = getattr(query_config, "intelligent_detect", {})
        default_switch = (
            True
            if (
                algorithm_plan_id == settings.BK_DATA_PLAN_ID_INTELLIGENT_DETECTION
                or algorithm_name
                in (
                    AlgorithmModel.AlgorithmChoices.AbnormalCluster,
                    AlgorithmModel.AlgorithmChoices.TimeSeriesForecasting,
                )
            )
            else False
        )
        # 如果已经配置了使用SDK，则不再走bkbase接入的方式，默认使用SDK的方式进行检测
        if (
            intelligent_detect.get("use_sdk", default_switch)
            and algorithm_name != AlgorithmModel.AlgorithmChoices.HostAnomalyDetection
        ):
            # 不保留原来的配置（主要是为了清理dataflow的配置，后续dataflow的任务会统一清理）
            intelligent_detect = {"use_sdk": True}
            if algorithm_name == AlgorithmModel.AlgorithmChoices.AbnormalCluster:
                # 离群检测不需要历史依赖，因此如果使用SDK，默认可以直接进行检测
                intelligent_detect["status"] = SDKDetectStatus.READY
            else:
                intelligent_detect["status"] = SDKDetectStatus.PREPARING
            need_access = False

        query_config.intelligent_detect = intelligent_detect

        return need_access

    def access_aiops(self, algorithm_name: str):
        """执行实际AIOPS接入逻辑

        :param algorithm_name: 算法名称

        - 监控时序数据(以监控管理员身份配置)
            1. 走kafka接入，配置好清洗规则，接入到计算平台
            2. 走dataflow，进行downsample操作，得到一张结果表，保存到metadata的bkdatastorage表中
            3. 走dataflow，根据策略配置的查询sql，创建好实时计算节点，在节点后配置好智能检测节点
        - 计算平台数据(根据用户身份配置)
            1. 直接走dataflow，根据策略配置的查询sql，创建好实时计算节点，在节点后配置好智能检测节点
        """
        for query_config in chain(*(item.query_configs for item in self.items)):
            self.access_algorithm_by_query_config(query_config, algorithm_name)

    def access_algorithm_by_query_config(self, query_config: QueryConfig, algorithm_name: str):
        """根据查询配置把算法对应的后台任务接入到bkbase中.

        :param query_config: 查询配置
        :param algorithm_name: 算法名称
        """
        from monitor_web.tasks import get_aiops_access_func

        if query_config.data_type_label != DataTypeLabel.TIME_SERIES:
            return

        # 如果数据来源是计算平台，则需要先进行授权给监控项目，再标记需要接入智能检测算法
        if query_config.data_source_label == DataSourceLabel.BK_DATA:
            # 授权给监控项目(以创建或更新策略的用户来请求一次授权)
            if algorithm_name in (
                set(AlgorithmModel.AIOPS_ALGORITHMS) - set(AlgorithmModel.AUTHORIZED_SOURCE_ALGORITHMS)
            ):
                # 主机异常检测使用业务主机观测场景的flow，因此不需要授权
                from bkmonitor.dataflow import auth

                auth.ensure_has_permission_with_rt_id(
                    bk_username=get_global_user() or settings.BK_DATA_PROJECT_MAINTAINER,
                    rt_id=query_config.result_table_id,
                    project_id=settings.BK_DATA_PROJECT_ID,
                )

        # 接入智能检测算法
        intelligent_detect = getattr(query_config, "intelligent_detect", {})
        # 如果已经配置了使用SDK，则不再走bkbase接入的方式
        if not intelligent_detect.get("use_sdk", False):
            # 4.3.1 标记当前查询配置需要接入智能检测算法，并保存算法接入状态为等待中，及重试接入次数为0
            intelligent_detect["status"] = AccessStatus.PENDING
            intelligent_detect["retries"] = 0
            intelligent_detect["message"] = ""
            intelligent_detect["task_id"] = None

            # 4.3.2 仅在web运行模式下，异步接入智能检测算法
            if settings.ROLE == "web":
                access_func = get_aiops_access_func(algorithm_name)
                task = access_func.delay(self.id)
                intelligent_detect["task_id"] = task.id

        query_config.intelligent_detect = intelligent_detect
        query_config.save()

    @classmethod
    def get_priority_group_key(cls, bk_biz_id: int, items: list[Item]):
        """
        获取优先级分组key
        """
        query_config_fields = [
            "functions",
            "metric_field",
            "agg_dimension",
            "agg_interval",
            "agg_method",
            "bkmonitor_strategy_id",
            "custom_event_name",
            "result_table_id",
            "index_set_id",
            "alert_name",
            "keywords_query_string",
        ]

        query = []
        for item in items:
            query_config = item.query_configs[0]

            item_query = {
                "bk_biz_id": bk_biz_id,
                "data_source_label": query_config.data_source_label,
                "data_type_label": query_config.data_type_label,
                "expression": item.expression,
                "functions": item.functions,
                "query_configs": [],
            }

            for query_config in item.query_configs:
                new_query_config = {}

                for field in query_config_fields:
                    new_query_config[field] = getattr(query_config, field, None)

                # 聚合维度排序
                if new_query_config["agg_dimension"]:
                    new_query_config["agg_dimension"] = sorted(new_query_config["agg_dimension"])

                # promql需要去除条件
                if getattr(query_config, "promql", None):
                    try:
                        origin_config = api.unify_query.promql_to_struct(promql=query_config.promql)["data"]
                        for _query in origin_config["query_list"]:
                            _query["conditions"] = {"field_list": [], "condition_list": []}
                        origin_config["space_uid"] = bk_biz_id_to_space_uid(bk_biz_id)
                        promql = api.unify_query.struct_to_promql(origin_config)["promql"]
                        new_query_config["promql"] = promql
                    except Exception as e:
                        logger.error(f"promql转换失败：{query_config.promql}, {e}")
                        new_query_config["promql"] = query_config.promql

                item_query["query_configs"].append(new_query_config)
            query.append(item_query)

        content = json.dumps(query, sort_keys=True)
        return xxhash.xxh64(content).hexdigest()

    def supplement_inst_target_dimension(self):
        """
        静态目标补全静态维度
        """
        if is_ipv6_biz(self.bk_biz_id):
            host_dimensions = {"bk_host_id"}
        else:
            host_dimensions = {"bk_target_ip", "bk_target_cloud_id"}

        for item in self.items:
            if not item.target or not item.target[0]:
                return

            target = item.target[0][0]
            if target["field"] not in [TargetFieldType.host_target_ip, TargetFieldType.host_ip]:
                return

            for query_config in item.query_configs:
                if (
                    query_config.data_source_label != DataSourceLabel.BK_MONITOR_COLLECTOR
                    or query_config.data_type_label != DataTypeLabel.TIME_SERIES
                ):
                    continue
                query_config.agg_dimension = list(set(query_config.agg_dimension) | host_dimensions)

    def delete(self):
        if id == 0:
            return

        StrategyModel.objects.filter(id=self.id).delete()
        RelationModel.objects.filter(strategy_id=self.id).delete()
        DetectModel.objects.filter(strategy_id=self.id).delete()
        ItemModel.objects.filter(strategy_id=self.id).delete()
        AlgorithmModel.objects.filter(strategy_id=self.id).delete()
        QueryConfigModel.objects.filter(strategy_id=self.id).delete()
        StrategyLabel.objects.filter(strategy_id=self.id).delete()

    @classmethod
    def delete_by_strategy_ids(cls, strategy_ids: list[int]):
        """
        批量删除策略
        """
        histories = []
        for strategy_id in strategy_ids:
            histories.append(
                StrategyHistoryModel(
                    create_user=cls._get_username(),
                    strategy_id=strategy_id,
                    operate="delete",
                )
            )
        StrategyHistoryModel.objects.bulk_create(histories, batch_size=100)

        StrategyModel.objects.filter(id__in=strategy_ids).delete()
        RelationModel.objects.filter(strategy_id__in=strategy_ids).delete()
        DetectModel.objects.filter(strategy_id__in=strategy_ids).delete()
        ItemModel.objects.filter(strategy_id__in=strategy_ids).delete()
        AlgorithmModel.objects.filter(strategy_id__in=strategy_ids).delete()
        QueryConfigModel.objects.filter(strategy_id__in=strategy_ids).delete()
        StrategyLabel.objects.filter(strategy_id__in=strategy_ids).delete()

    @classmethod
    def from_models(cls, strategies: list[StrategyModel] | QuerySet) -> list["Strategy"]:
        """
        数据模型转换为策略对象

        :param strategies: 策略模型列表或QuerySet，包含要转换为策略对象的数据模型。
        :return: List["Strategy"]策略对象列表
        """
        # 提取所有策略的ID
        strategy_ids = [s.id for s in strategies]

        # 当接收到大量策略模型时，为了避免查询数据库时带来的巨大开销，采用全量查询的方式。
        if len(strategy_ids) > 500:
            item_query = ItemModel.objects.all()
            detect_query = DetectModel.objects.all()
            algorithm_query = AlgorithmModel.objects.all()
            query_config_query = QueryConfigModel.objects.all()
            label_query = StrategyLabel.objects.all()
            related_query = RelationModel.objects.all()
        else:
            item_query = ItemModel.objects.filter(strategy_id__in=strategy_ids)
            detect_query = DetectModel.objects.filter(strategy_id__in=strategy_ids)
            algorithm_query = AlgorithmModel.objects.filter(strategy_id__in=strategy_ids)
            query_config_query = QueryConfigModel.objects.filter(strategy_id__in=strategy_ids)
            label_query = StrategyLabel.objects.filter(strategy_id__in=strategy_ids)
            related_query = RelationModel.objects.filter(strategy_id__in=strategy_ids)

        # 将查询结果整理为字典，便于后续根据策略ID快速查找
        # {strategy_id: [strategy_model]}
        items: dict[int, list[ItemModel]] = defaultdict(list)
        for item in item_query:
            items[item.strategy_id].append(item)

        detects: dict[int, list[DetectModel]] = defaultdict(list)
        for detect in detect_query:
            detects[detect.strategy_id].append(detect)

        algorithms: dict[int, list[AlgorithmModel]] = defaultdict(list)
        for algorithm in algorithm_query:
            algorithms[algorithm.item_id].append(algorithm)

        query_configs: dict[int, list[QueryConfigModel]] = defaultdict(list)
        for query_config in query_config_query:
            query_configs[query_config.item_id].append(query_config)

        labels: dict[int, list[str]] = defaultdict(list)
        for label in label_query:
            labels[label.strategy_id].append(label.label_name.strip("/"))

        # 策略关联的自愈套餐及告警组配置
        action_config_ids = set()
        actions: dict[int, list[RelationModel]] = defaultdict(list)
        notices: dict[int, list[RelationModel]] = defaultdict(list)
        for action in related_query:
            if action.relate_type == RelationModel.RelateType.NOTICE:
                notices[action.strategy_id].append(action)
            else:
                actions[action.strategy_id].append(action)
            action_config_ids.add(action.config_id)

        # 查询关联自愈套餐
        action_config_ids = list(action_config_ids)
        if len(action_config_ids) > 500:
            action_query = ActionConfig.objects.all()
        else:
            action_query = ActionConfig.objects.filter(id__in=action_config_ids)
        action_configs: dict[int, ActionConfig] = {}
        for action_config in action_query:
            action_configs[action_config.id] = action_config

        # 根据查询和处理结果，创建策略对象
        records = []
        for strategy in strategies:
            record = Strategy(
                bk_biz_id=strategy.bk_biz_id,
                id=strategy.id,
                name=strategy.name,
                scenario=strategy.scenario,
                is_enabled=strategy.is_enabled,
                is_invalid=strategy.is_invalid,
                invalid_type=strategy.invalid_type,
                source=strategy.source,
                type=strategy.type,
                update_time=strategy.update_time,
                update_user=strategy.update_user,
                create_user=strategy.create_user,
                create_time=strategy.create_time,
                labels=labels.get(strategy.id, []),
                app=strategy.app,
                path=strategy.path,
                priority=strategy.priority,
                priority_group_key=strategy.priority_group_key,
                instance=strategy,
            )

            # 为策略对象的items、actions、detects和notice属性赋值
            record.items = Item.from_models(items[strategy.id], algorithms, query_configs)
            record.actions = ActionRelation.from_models(actions[strategy.id], action_configs)
            record.detects = Detect.from_models(detects[strategy.id])

            record_notices = NoticeRelation.from_models(notices[strategy.id], action_configs)
            if record_notices:
                record.notice = record_notices[0]
            else:
                record.notice = NoticeRelation(strategy_id=strategy.id)

            records.append(record)

        return records

    @property
    def target_type(self):
        """
        监控目标类型
        """
        if not self.items or not self.items[0].query_configs:
            return DataTarget.NONE_TARGET

        query_config = self.items[0].query_configs[0]
        if self.scenario in HOST_SCENARIO and query_config.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR:
            return DataTarget.HOST_TARGET
        elif (
            self.scenario in SERVICE_SCENARIO and query_config.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
        ):
            return DataTarget.SERVICE_TARGET

        return DataTarget.NONE_TARGET

    @property
    def public_dimensions(self):
        # 公共维度
        return list(reduce(lambda x, y: x & y, [set(item.public_dimensions) for item in self.items]))

    def is_composite(self) -> bool:
        """
        当前策略是否为关联告警策略
        :return: bool
        """
        for item in self.items:
            for query_config in item.query_configs:
                if query_config.data_type_label == DataTypeLabel.ALERT:
                    return True
        return False


def _render_grafana_variable_str(variables: dict[str, list[str]], value: str, mode: str = "") -> str | list:
    """
    字符串渲染grafana变量
    mode: promql, list
    """
    for variable_key, variable in variables.items():
        # 变量预处理
        if mode == "promql":
            variable_value = "|".join(variable)
        else:
            variable_value = ",".join(variable)

        # 如果值和变量相等，直接返回变量
        if value.strip() == variable_key and mode == "list":
            return variable

        value = value.replace(variable_key, variable_value)
    return value


def _render_grafana_variable(
    variables: dict[str, list[str]], value: str | list | dict, mode: str = ""
) -> str | list | dict:
    """
    递归渲染grafana变量
    $x, ${x}, {{x}}, ${x:y}
    mode: regex
    """
    if not value:
        return value

    if isinstance(value, list):
        new_values = []
        for v in value:
            if isinstance(v, dict):
                new_values.append(_render_grafana_variable(variables, v, mode))
            elif isinstance(v, str):
                new_value = _render_grafana_variable_str(variables, v, mode or "promql")

                # 如果是list模式，且变量值是list，则展开
                if isinstance(new_value, list):
                    new_values.extend(new_value)
                else:
                    new_values.append(new_value)
            else:
                new_values.append(v)
        value = new_values
    elif isinstance(value, dict):
        new_value = {}
        for k, v in value.items():
            new_value[k] = _render_grafana_variable(variables, v, mode)
        value = new_value
    elif isinstance(value, str):
        value = _render_grafana_variable_str(variables, value, mode)

    return value


def grafana_panel_to_config(panel_query: dict, variables: dict[str, list[str]]) -> dict[str, Any]:
    """
    将grafana的panel信息转换为监控策略配置格式
    variables: {"xxx": {"text": "xxx", "value": "xxx"}, "yyy": [{"text": "yyy", "value": "yyy"}]}
    """
    # 数据源检查，目前仅支持bkmonitor-timeseries-datasource
    if panel_query.get("datasource") and panel_query["datasource"]["type"] not in ["bkmonitor-timeseries-datasource"]:
        raise ValueError(f"not support datasource {panel_query['datasource']}")

    # todo: 配置预处理
    expression = "a"
    functions = []
    if panel_query.get("mode") == "code":
        promql = panel_query.get("source")
        step = panel_query.get("step")

        # 判断 promql 不能为空
        if not promql:
            raise ValidationError("promql cannot be empty")

        # 周期解析
        if step:
            interval = abs(parse_time_compare_abbreviation(step))
        else:
            interval = 60

        target = [[]]
        raw_query_configs = [
            {
                "data_source_label": DataSourceLabel.PROMETHEUS,
                "data_type_label": DataTypeLabel.TIME_SERIES,
                "agg_interval": interval,
                "promql": promql,
                "refId": "a",
            }
        ]
    else:
        # 字段映射
        raw_query_configs = []
        for query_config in panel_query.get("query_configs", []):
            # 周期解析
            interval = query_config.get("interval", 60)
            if not interval or interval == "auto":
                interval = 60
            elif query_config.get("interval_unit") == "m":
                interval *= 60

            raw_query_configs.append(
                {
                    "data_source_label": query_config["data_source_label"],
                    "data_type_label": query_config["data_type_label"],
                    "functions": query_config.get("functions", []),
                    "agg_dimension": query_config.get("group_by", []),
                    "agg_interval": interval,
                    "agg_method": query_config.get("method", "avg"),
                    "agg_condition": query_config.get("where", []),
                    "metric_field": query_config.get("metric_field", ""),
                    "result_table_id": query_config.get("result_table_id", ""),
                    "index_set_id": query_config.get("index_set_id", ""),
                    "data_label": query_config.get("data_label", ""),
                    "time_field": query_config.get("time_field", ""),
                    "refId": query_config["refId"],
                }
            )

        # 监控目标解析
        target = None
        if panel_query.get("host"):
            hosts = []
            for host in panel_query["host"]:
                ip, bk_cloud_id = host.split("|")
                hosts.append({"ip": ip, "bk_cloud_id": bk_cloud_id})
            target = {"field": TargetFieldType.host_ip, "method": "eq", "value": hosts}
        elif panel_query.get("module"):
            modules = [{"bk_obj_id": "module", "bk_inst_id": module["value"]} for module in panel_query["module"]]
            target = {"field": TargetFieldType.host_topo, "method": "eq", "value": modules}
        elif panel_query.get("cluster"):
            sets = [{"bk_obj_id": "set", "bk_inst_id": cluster["value"]} for cluster in panel_query["cluster"]]
            target = {"field": TargetFieldType.host_topo, "method": "eq", "value": sets}

        if target:
            target = [[target]]
        else:
            target = [[]]

        # 当存在表达式时，使用第一个表达式，否则生成一个or表达式
        expressions = panel_query.get("expressionList", [])
        if expressions and expressions[0].get("expression"):
            expression = expressions[0].get("expression", "")
            functions = expressions[0].get("functions", [])
        elif raw_query_configs:
            expression = " or ".join(q["refId"] for q in raw_query_configs)
            functions = []
        else:
            return

    # 配置格式化及参数渲染
    query_configs = []
    for raw_query_config in raw_query_configs:
        alias = raw_query_config["refId"]
        data_source_label = raw_query_config["data_source_label"]
        data_type_label = raw_query_config["data_type_label"]
        serializer_class = QueryConfig.get_serializer_class(data_source_label, data_type_label)
        serializer = serializer_class(data=raw_query_config)
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        query_config = {
            "alias": alias,
            "data_source_label": data_source_label,
            "data_type_label": data_type_label,
            **serializer.validated_data,
        }

        # 渲染变量，只有特定字段支持变量渲染,维度，条件，周期，函数，promql
        fields = ["agg_dimension", "agg_condition", "promql", "functions"]
        for field in fields:
            if field not in query_config:
                continue

            # 根据字段，设置渲染模式
            mode = ""
            if field == "agg_condition":
                mode = "list"
            elif field == "promql":
                mode = "promql"

            query_config[field] = _render_grafana_variable(variables, query_config[field], mode)

        query_configs.append(query_config)

    return {
        "expression": expression,
        "functions": functions,
        "query_configs": query_configs,
        "target": target,
    }
