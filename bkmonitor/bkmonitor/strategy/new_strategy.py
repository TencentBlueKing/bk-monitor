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
import abc
import copy
import json
import logging
import traceback
from collections import defaultdict
from datetime import datetime
from functools import partial, reduce
from itertools import chain, permutations
from typing import Dict, List, Type, Union

import arrow
import xxhash
from django.conf import settings
from django.db import transaction
from django.db.models import Model, QuerySet
from django.utils.translation import ugettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

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
from bkmonitor.utils.time_tools import strftime_local
from bkmonitor.utils.user import get_global_user
from constants.action import ActionPluginType, ActionSignal, AssignMode, UserGroupType
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import (
    DATALINK_SOURCE,
    HOST_SCENARIO,
    SERVICE_SCENARIO,
    SYSTEM_EVENT_RT_TABLE_ID,
    AdvanceConditionMethod,
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
            DataTypeLabel.TIME_SERIES: "{}.{}.{}".format(data_source_label, result_table_id, metric_field),
            DataTypeLabel.EVENT: "{}.{}".format(data_source_label, metric_field),
            DataTypeLabel.LOG: "{}.{}.{}".format(data_source_label, data_type_label, result_table_id),
            DataTypeLabel.ALERT: "{}.{}.{}".format(
                data_source_label, data_type_label, bkmonitor_strategy_id or metric_field
            ),
        },
        DataSourceLabel.PROMETHEUS: {DataTypeLabel.TIME_SERIES: promql[:125] + "..." if len(promql) > 128 else promql},
        DataSourceLabel.CUSTOM: {
            DataTypeLabel.EVENT: "{}.{}.{}.{}".format(
                data_source_label, data_type_label, result_table_id, custom_event_name
            ),
            DataTypeLabel.TIME_SERIES: "{}.{}.{}".format(data_source_label, result_table_id, metric_field),
        },
        DataSourceLabel.BK_LOG_SEARCH: {
            DataTypeLabel.LOG: "{}.index_set.{}".format(data_source_label, index_set_id),
            DataTypeLabel.TIME_SERIES: "{}.index_set.{}.{}".format(data_source_label, index_set_id, metric_field),
        },
        DataSourceLabel.BK_DATA: {
            DataTypeLabel.TIME_SERIES: "{}.{}.{}".format(data_source_label, result_table_id, metric_field),
        },
        DataSourceLabel.BK_FTA: {
            DataTypeLabel.ALERT: "{}.{}.{}".format(data_source_label, data_type_label, alert_name or metric_field),
            DataTypeLabel.EVENT: "{}.{}.{}".format(data_source_label, data_type_label, alert_name or metric_field),
        },
        DataSourceLabel.BK_APM: {
            DataTypeLabel.LOG: f"{data_source_label}.{data_type_label}.{result_table_id}",
            DataTypeLabel.TIME_SERIES: f"{data_source_label}.{result_table_id}.{metric_field}",
        },
    }
    return metric_id_map.get(data_source_label, {}).get(data_type_label, "")


def parse_metric_id(metric_id: str) -> Dict:
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
                    "result_table_id": ".".join(split_field_list[1:3]),
                    "metric_field": split_field_list[3],
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


class AbstractConfig(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def to_dict(self, *args, **kwargs) -> Dict:
        raise NotImplementedError

    @classmethod
    def delete_useless(cls, *args, **kwargs):
        return

    @classmethod
    def reuse_exists_records(
        cls, model: Type[Model], objs: List[Model], configs: List["AbstractConfig"], config_cls: Type["AbstractConfig"]
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
        config: Dict = None,
        notice_group_ids: List[int] = None,
        notice_template: Dict = None,
        id: int = 0,
        **kwargs,
    ):
        self.id = id
        self.strategy_id = strategy_id
        self.type = type
        self.config: Dict = config
        self.notice_group_ids: List[int] = notice_group_ids or []
        self.notice_template = notice_template or {"anomaly_template": "", "recovery_template": ""}

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "config": self.config,
            "notice_group_ids": self.notice_group_ids,
            "notice_template": self.notice_template,
        }

    @classmethod
    def delete_useless(cls, useless_action_ids: List[int]):
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
        actions: List["ActionModel"],
        notice_templates: Dict[int, NoticeTemplate],
        notice_group_ids: Dict[int, List[int]],
    ) -> List["Action"]:
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
            ],
        )
        options = OptionsSerializer()

    def __init__(
        self,
        strategy_id: int,
        config_id: int = 0,
        user_groups: List[int] = None,
        signal: List[str] = None,
        id: int = None,
        options: dict = None,
        config: dict = None,
        **kwargs,
    ):
        self.id = id
        self.strategy_id = strategy_id
        self.config_id: int = config_id
        self.user_groups: List[int] = user_groups or []
        self.user_type = kwargs.get("user_type", UserGroupType.MAIN)
        self.signal = list(signal or [])
        self.options: dict = options or {}
        self.config: dict = config or {}

    def to_dict(self) -> Dict:
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
    def convert_v1_to_v2(cls, config: Dict) -> Dict:
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
    def delete_useless(cls, relation_ids: List[int]):
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

    @classmethod
    def from_models(cls, relations: List["RelationModel"], action_configs: Dict[int, "ActionConfig"]):
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
        super(NoticeRelation, self).__init__(*args, **kwargs)

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

    def to_dict(self) -> Dict:
        data = super(NoticeRelation, self).to_dict()
        data["config"] = self.config
        return data

    @classmethod
    def delete_useless(cls, relation_ids: List[int]):
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

        return super(NoticeRelation, self).save()

    @classmethod
    def from_models(cls, relations: List["RelationModel"], action_configs: Dict[int, "ActionConfig"]):
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
        config: Union[Dict, List[List[Dict]]],
        level: int,
        unit_prefix: str = "",
        id: int = 0,
        **kwargs,
    ):
        self.id = id
        self.type = type
        self.config = config
        self.level = level
        self.unit_prefix = unit_prefix
        self.strategy_id = strategy_id
        self.item_id = item_id

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
    def from_models(cls, algorithms: List[AlgorithmModel]) -> List["Algorithm"]:
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
                required=False, choices=["recovery", "close"], label="告警恢复目标状态", default="recovery"
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
        level: Union[int, str],
        trigger_config: Dict,
        recovery_config: Dict,
        expression: str = "",
        connector: str = "and",
        id: int = 0,
        **kwargs,
    ):
        self.id = id
        self.level = int(level)
        self.expression = expression
        self.strategy_id = strategy_id
        self.trigger_config = trigger_config
        self.recovery_config = recovery_config
        self.connector = connector or "and"

    def to_dict(self) -> Dict:
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
    def from_models(cls, detects: List["DetectModel"]) -> List["Detect"]:
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
    agg_dimension: List[str]
    agg_condition: List[Dict]
    metric_field: str
    unit: str
    time_field: str
    custom_event_name: str
    origin_config: Dict
    intelligent_detect: Dict
    values: List[str]

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
        **kwargs,
    ):
        self.strategy_id = strategy_id
        self.item_id = item_id
        self.data_source_label = data_source_label
        self.data_type_label = data_type_label
        self.alias = alias
        self.id = id
        self.metric_id = metric_id or ""
        serializer_class = self.get_serializer_class(data_source_label, data_type_label)
        serializer = serializer_class(data=kwargs)
        serializer.is_valid(raise_exception=True)

        for field, value in serializer.validated_data.items():
            setattr(self, field, value)

    @classmethod
    def get_serializer_class(cls, data_source_label: str, data_type_label: str) -> Type[QueryConfigSerializer]:
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
    def from_models(cls, query_configs: List[QueryConfigModel]) -> List["QueryConfig"]:
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

            def validate(self, attrs: Dict):
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

    def __init__(
        self,
        strategy_id: int,
        name: str,
        no_data_config: Dict,
        target: List = None,
        expression: str = "",
        functions: List = None,
        origin_sql: str = "",
        id: int = 0,
        query_configs: List[Dict] = None,
        algorithms: List[Dict] = None,
        metric_type: str = "",
        **kwargs,
    ):
        self.functions = functions or []
        self.name = name
        self.no_data_config = no_data_config
        self.target: List[List[Dict]] = target or [[]]
        self.expression = expression
        self.origin_sql = origin_sql
        self.query_configs: List[QueryConfig] = [QueryConfig(strategy_id, id, **c) for c in query_configs or []]
        self.algorithms: List[Algorithm] = [Algorithm(strategy_id, id, **c) for c in algorithms or []]
        self.strategy_id = strategy_id
        self.id = id

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
    def delete_useless(cls, useless_item_ids: List[int]):
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
                item.save()
            else:
                item = self._create()
        except ItemModel.DoesNotExist:
            item = self._create()

        # 复用旧的记录
        model_configs = [
            (QueryConfigModel, QueryConfig, self.query_configs),
            (AlgorithmModel, Algorithm, self.algorithms),
        ]

        for model, config_cls, configs in model_configs:
            objs = model.objects.filter(strategy_id=self.strategy_id, item_id=self.id).only("id")
            self.reuse_exists_records(model, objs, configs, config_cls)

        # 保存子配置
        for obj in chain(self.algorithms, self.query_configs):
            obj.save()

        item.save()

    @classmethod
    def from_models(
        cls,
        items: List["ItemModel"],
        algorithms: Dict[int, List[AlgorithmModel]],
        query_configs: Dict[int, List[QueryConfigModel]],
    ) -> List["Item"]:
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
        items: List[Dict] = None,
        actions: List[Dict] = None,
        notice: Dict = None,
        detects: List[Dict] = None,
        is_enabled: bool = True,
        is_invalid: bool = False,
        invalid_type: str = StrategyModel.InvalidType.NONE,
        update_user: str = "",
        update_time: datetime = None,
        create_user: str = "",
        create_time: datetime = None,
        labels: List[str] = None,
        app: str = "",
        path: str = "",
        priority: int = 0,
        priority_group_key: str = None,
        metric_type: str = "",
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
        self.items: List[Item] = [Item(id, **item) for item in items or []]
        self.detects: List[Detect] = [Detect(id, **detect) for detect in detects or []]
        self.actions: List[ActionRelation] = [ActionRelation(id, **action) for action in actions or []]
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

        if isinstance(self.update_time, (int, str)):
            self.update_time = arrow.get(update_time).datetime

        if isinstance(self.create_time, (int, str)):
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

    def to_dict(self) -> Dict:
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

        return config

    @classmethod
    def fill_user_groups(cls, configs: List[Dict], with_detail=False):
        """
        显示告警组信息
        """
        strategy_ids = [config["id"] for config in configs]
        action_relations = RelationModel.objects.filter(strategy_id__in=strategy_ids)
        user_group_ids = []
        for action_relation in action_relations:
            user_group_ids.extend(action_relation.validated_user_groups)
        user_groups_slz = UserGroupSlz(UserGroup.objects.filter(id__in=user_group_ids), many=True).data
        if with_detail:
            user_groups_slz = UserGroupDetailSlz(UserGroup.objects.filter(id__in=user_group_ids), many=True).data
        user_groups = {group["id"]: dict(group) for group in user_groups_slz}
        for config in configs:
            for action in config["actions"] + [config["notice"]]:
                user_group_list = []
                for user_group_id in action["user_groups"]:
                    if user_group_id and user_group_id in user_groups:
                        user_group_list.append(user_groups[user_group_id])
                action["user_group_list"] = user_group_list

    def to_dict_v1(self, config_type: str = "frontend") -> Dict:
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
    def from_dict_v1(cls, config: Dict, config_type="frontend") -> "Strategy":
        """
        由旧策略配置JSON字典生成对象
        """
        config = copy.deepcopy(config)
        item_list = config.pop("item_list")
        action_list = config.pop("action_list")
        strategy_id = config.pop("id", 0)
        algorithm_list = item_list[0].pop("algorithm_list")

        item: Dict = item_list[0]
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
    def convert_v1_to_v2(cls, strategy_config: Dict) -> Dict:
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
    def convert_v2_to_v1(cls, strategy_config: Dict) -> Dict:
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
            priority_group_key=self.get_priority_group_key(self.bk_biz_id, self.items),
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
    def save(self, rollback=False):
        """
        保存策略配置
        """
        self.supplement_inst_target_dimension()

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
                strategy.priority_group_key = self.get_priority_group_key(self.bk_biz_id, self.items)
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

            self.reuse_exists_records(
                RelationModel,
                RelationModel.objects.filter(strategy_id=self.id, relate_type=RelationModel.RelateType.ACTION).only(
                    "id"
                ),
                self.actions,
                ActionRelation,
            )

            self.reuse_exists_records(
                RelationModel,
                RelationModel.objects.filter(strategy_id=self.id, relate_type=RelationModel.RelateType.NOTICE).only(
                    "id"
                ),
                [self.notice],
                NoticeRelation,
            )

            # 保存子配置
            for obj in chain(self.items, self.actions, self.detects, [self.notice]):
                obj.save()

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

        # 接入智能监控
        self.access_aiops()

    def access_aiops(self):
        """
        智能监控接入
        (目前仅支持监控时序、计算平台时序数据)

        - 监控时序数据(以监控管理员身份配置)
            1. 走kafka接入，配置好清洗规则，接入到计算平台
            2. 走dataflow，进行downsample操作，得到一张结果表，保存到metadata的bkdatastorage表中
            3. 走dataflow，根据策略配置的查询sql，创建好实时计算节点，在节点后配置好智能检测节点
        - 计算平台数据(根据用户身份配置)
            1. 直接走dataflow，根据策略配置的查询sql，创建好实时计算节点，在节点后配置好智能检测节点
        """
        # 未开启计算平台接入，则直接返回
        if not settings.IS_ACCESS_BK_DATA:
            return

        has_intelligent_algorithm = False
        for algorithm in chain(*(item.algorithms for item in self.items)):
            if algorithm.type in AlgorithmModel.AIOPS_ALGORITHMS:
                has_intelligent_algorithm = True
                break

        if not has_intelligent_algorithm:
            return

        # 判断数据来源
        for query_config in chain(*(item.query_configs for item in self.items)):
            if query_config.data_type_label != DataTypeLabel.TIME_SERIES:
                continue

            from monitor_web.tasks import access_aiops_by_strategy_id

            need_access = False

            if query_config.data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR:
                # 如果查询条件中存在特殊的方法，查询条件置为空
                for condition in query_config.agg_condition:
                    if condition["method"] in AdvanceConditionMethod:
                        raise Exception(_("智能检测算法不支持这些查询条件({})".format(AdvanceConditionMethod)))
                need_access = True

            elif query_config.data_source_label == DataSourceLabel.BK_DATA:
                # 1. 先授权给监控项目(以创建或更新策略的用户来请求一次授权)
                from bkmonitor.dataflow import auth

                auth.ensure_has_permission_with_rt_id(
                    bk_username=get_global_user() or settings.BK_DATA_PROJECT_MAINTAINER,
                    rt_id=query_config.result_table_id,
                    project_id=settings.BK_DATA_PROJECT_ID,
                )
                # 2. 然后再创建异常检测的dataflow
                need_access = True

            if need_access:
                intelligent_detect = getattr(query_config, "intelligent_detect", {})
                intelligent_detect["status"] = AccessStatus.PENDING
                intelligent_detect["retries"] = 0
                intelligent_detect["message"] = ""
                query_config.intelligent_detect = intelligent_detect
                query_config.save()

                if settings.ROLE == "web":
                    # 只有 web 运行模式下，才允许触发 celery 异步接入任务
                    access_aiops_by_strategy_id.delay(self.id)

    @classmethod
    def get_priority_group_key(cls, bk_biz_id: int, items: List[Item]):
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
    def delete_by_strategy_ids(cls, strategy_ids: List[int]):
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
    def from_models(cls, strategies: Union[List[StrategyModel], QuerySet]) -> List["Strategy"]:
        """
        数据模型转换为策略对象
        """
        strategy_ids = [s.id for s in strategies]

        # 当策略数量非常大时，直接全量查询避免
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

        items: Dict[int, List[ItemModel]] = defaultdict(list)
        for item in item_query:
            items[item.strategy_id].append(item)

        detects: Dict[int, List[DetectModel]] = defaultdict(list)
        for detect in detect_query:
            detects[detect.strategy_id].append(detect)

        algorithms: Dict[int, List[AlgorithmModel]] = defaultdict(list)
        for algorithm in algorithm_query:
            algorithms[algorithm.item_id].append(algorithm)

        query_configs: Dict[int, List[QueryConfigModel]] = defaultdict(list)
        for query_config in query_config_query:
            query_configs[query_config.item_id].append(query_config)

        labels: Dict[int, List[str]] = defaultdict(list)
        for label in label_query:
            labels[label.strategy_id].append(label.label_name.strip("/"))

        # 策略关联的自愈套餐及告警组配置
        action_config_ids = set()
        actions: Dict[int, List[RelationModel]] = defaultdict(list)
        notices: Dict[int, List[RelationModel]] = defaultdict(list)
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
        action_configs: Dict[int, ActionConfig] = {}
        for action_config in action_query:
            action_configs[action_config.id] = action_config

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
            )

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
