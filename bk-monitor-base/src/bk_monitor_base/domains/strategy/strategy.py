"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
import json
import logging
import traceback
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import datetime
from functools import partial, reduce
from itertools import chain, permutations
from typing import Any, ClassVar, Self, cast, final

import arrow
import xxhash
from django.db import OperationalError, ProgrammingError, transaction
from django.db.models import Model, QuerySet
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from typing_extensions import override

from bk_monitor_base.config.all import get_config
from bk_monitor_base.domains.space.cache import bk_biz_id_to_bk_tenant_id, bk_biz_id_to_space_uid
from bk_monitor_base.domains.strategy.errors import CreateStrategyError, StrategyNotExistError
from bk_monitor_base.infras.constant import NOISE_REDUCE_TIMEDELTA
from bk_monitor_base.infras.third_party_api.bkdata import api as bkdata_api
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.infras.third_party_api.unify_query import api as unify_query_api
from bk_monitor_base.infras.time import strftime_local

from .constants import (
    CUSTOM_PRIORITY_GROUP_PREFIX,
    DATA_SOURCE_LABEL_ALIAS,
    DATALINK_SOURCE,
    HOST_SCENARIO,
    SERVICE_SCENARIO,
    SYSTEM_EVENT_RT_TABLE_ID,
    SYSTEM_PROC_PORT_METRIC_ID,
    AccessStatus,
    ActionSignal,
    AssignMode,
    DataSourceLabel,
    DataTarget,
    DataTypeLabel,
    IntelligentDetectAlgorithms,
    SDKDetectStatus,
    SourceApp,
    TargetFieldType,
    UserGroupType,
)
from .expression import parse_expression
from .functions import add_expression_functions
from .models import (
    ActionConfig,
    AlgorithmModel,
    DetectModel,
    ItemModel,
    QueryConfigModel,
    StrategyActionConfigRelation,
    StrategyHistoryModel,
    StrategyIssueConfigModel,
    StrategyLabel,
    StrategyModel,
)
from .serializers import (
    AbnormalClusterSerializer,
    AdvancedRingRatioSerializer,
    AdvancedYearRoundSerializer,
    BkDataTimeSeriesSerializer,
    BkFtaAlertSerializer,
    BkFtaEventSerializer,
    BkLogSearchLogSerializer,
    BkLogSearchTimeSeriesSerializer,
    BkMonitorAlertSerializer,
    BkMonitorEventSerializer,
    BkMonitorLogSerializer,
    BkMonitorTimeSeriesSerializer,
    ConvergeConfigSlz,
    CustomEventSerializer,
    CustomTimeSeriesSerializer,
    HostAnomalyDetectionSerializer,
    IntelligentDetectSerializer,
    MultivariateAnomalyDetectionSerializer,
    NewSeriesSerializer,
    NoiseReduceConfigSlz,
    NotifyActionConfigSlz,
    PrometheusTimeSeriesSerializer,
    QueryConfigSerializer,
    RingRatioAmplitudeSerializer,
    SimpleRingRatioSerializer,
    SimpleYearRoundSerializer,
    ThresholdSerializer,
    TimeSeriesForecastingSerializer,
    UpgradeConfigSlz,
    YearRoundAmplitudeSerializer,
    YearRoundRangeSerializer,
)

logger = logging.getLogger(__name__)

_RELATED_QUERY_CHUNK_SIZE = 500

_TABLE_NOT_EXIST_PATTERNS = (
    "doesn't exist",  # MySQL 1146
    "does not exist",  # PostgreSQL: relation "xxx" does not exist
    "no such table",  # SQLite
)


def _is_table_not_exist_error(exc: OperationalError | ProgrammingError) -> bool:
    """判断数据库异常是否为"表不存在"（兼容 MySQL / PostgreSQL / SQLite）。"""
    msg = str(exc).lower()
    return any(pattern in msg for pattern in _TABLE_NOT_EXIST_PATTERNS)


def _iter_models_by_strategy_ids(
    model: Any, strategy_ids: list[int], *, chunk_size: int = _RELATED_QUERY_CHUNK_SIZE
) -> Iterable[Any]:
    """按 strategy_id 分批读取关联模型，避免大批量策略触发全表加载。

    Args:
        model: 含有 `strategy_id` 字段的 Django 模型类。
        strategy_ids: 本次需要加载的策略 ID 列表。
        chunk_size: 单次 `IN` 查询的 ID 数量。

    Yields:
        Django 模型实例。
    """
    for index in range(0, len(strategy_ids), chunk_size):
        chunk = strategy_ids[index : index + chunk_size]
        if not chunk:
            continue
        yield from model.objects.filter(strategy_id__in=chunk).iterator(chunk_size=chunk_size)


def _iter_models_by_ids(
    model: Any, ids: Iterable[int], *, chunk_size: int = _RELATED_QUERY_CHUNK_SIZE
) -> Iterable[Any]:
    """按主键分批读取模型，避免因 ID 过多退化为全表扫描。

    Args:
        model: Django 模型类。
        ids: 本次需要加载的主键集合。
        chunk_size: 单次 `IN` 查询的 ID 数量。

    Yields:
        Django 模型实例。
    """
    id_list = list(ids)
    for index in range(0, len(id_list), chunk_size):
        chunk = id_list[index : index + chunk_size]
        if not chunk:
            continue
        yield from model.objects.filter(id__in=chunk).iterator(chunk_size=chunk_size)


def get_metric_id(
    data_source_label: str,
    data_type_label: str,
    result_table_id: str = "",
    index_set_id: str = "",
    metric_field: str = "",
    custom_event_name: str = "",
    alert_name: str = "",
    bkmonitor_strategy_id: str = "",
    promql: str = "",
    **kwargs: Any,
) -> str:
    """生成metric_id"""
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


def parse_metric_id(metric_id: str) -> dict[str, Any]:
    """解析指标ID"""
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


def has_instance_attr(obj: Any, attr: str) -> bool:
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
    def to_dict(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def delete_useless(cls, *args: Any, **kwargs: Any) -> None:  # pyright: ignore[reportUnusedParameter]
        return

    @classmethod
    def reuse_exists_records(
        cls, model: type[Model], objs: list[Any], configs: list[Any], config_cls: type["AbstractConfig"]
    ):
        """
        重用存量的数据库记录，删除多余的记录
        :param model: 模型
        :param objs: 数据库记录
        :param configs: 配置对象
        :param config_cls: 配置处理类
        """
        for config, obj in zip(configs, objs, strict=False):
            config.id = obj.pk
        for config in configs[len(objs) :]:
            config.id = 0
        if objs[len(configs) :]:
            obj_ids = [obj.pk for obj in objs[len(configs) :]]
            model.objects.filter(id__in=obj_ids).delete()
            config_cls.delete_useless(obj_ids)

    @abc.abstractmethod
    def save(self) -> Any:
        raise NotImplementedError

    @override
    def __setattr__(self, key: str, value: Any) -> None:
        super().__setattr__(key, value)
        instance = getattr(self, "instance", None)
        if instance and has_instance_attr(instance, key):
            setattr(instance, key, value)


@final
class BaseActionRelation(AbstractConfig):
    """
    动作关联关系的基类
    """

    # 关联类型，目前支持 通知 和 处理动作
    RELATE_TYPE: str = ""

    @final
    class Serializer(serializers.Serializer):
        @final
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
        user_groups: list[int] | None = None,
        signal: list[str] | None = None,
        id: int | None = None,  # noqa: A002
        options: dict[str, Any] | None = None,
        config: dict[str, Any] | None = None,
        instance: StrategyActionConfigRelation | None = None,
        **kwargs: Any,
    ):
        self.id = id
        self.strategy_id = strategy_id
        self.config_id: int = config_id
        self.user_groups: list[int] = user_groups or []
        self.user_type = kwargs.get("user_type", UserGroupType.MAIN)
        self.signal = list(signal or [])
        self.options: dict[str, Any] = options or {}
        self.config: dict[str, Any] = config or {}
        self.instance = instance

    @override
    def to_dict(self) -> dict[str, Any]:
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

    @override
    @classmethod
    def delete_useless(cls, relation_ids: list[int]):
        """
        删除策略下多余的Action关联记录
        """
        StrategyActionConfigRelation.objects.filter(id__in=relation_ids).delete()

    def _create(self):
        """
        新建Action记录
        """
        new_relation = StrategyActionConfigRelation.objects.create(
            strategy_id=self.strategy_id,
            config_id=self.config_id,
            relate_type=self.RELATE_TYPE,
            signal=self.signal,
            user_groups=self.user_groups,
            options=self.options,
        )
        self.id = new_relation.pk

    @override
    def save(self):
        """
        根据配置新建或更新关联记录
        """
        try:
            action_relation = StrategyActionConfigRelation.objects.get(id=self.id, strategy_id=self.strategy_id)
        except StrategyActionConfigRelation.DoesNotExist:
            self._create()
            return
        save_fields = self.to_dict()
        for key, value in save_fields.items():
            setattr(action_relation, key, value)
        action_relation.save()

    def bulk_save(
        self,
        relations: dict[int, list[StrategyActionConfigRelation]],
        action_configs: dict[int, ActionConfig] | None = None,  # pyright: ignore[reportUnusedParameter]
        operator: str = "",
    ):
        """
        根据配置新建或更新关联记录,循环结束后批量创建或更新
        """
        action_relations = relations.get(self.strategy_id, [])
        username = operator or "unknown"
        for action_relation in action_relations:
            if self.id == action_relation.pk:
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
                            "cls": StrategyActionConfigRelation,
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
            new_relation = StrategyActionConfigRelation(
                strategy_id=self.strategy_id,
                config_id=self.config_id,
                relate_type=self.RELATE_TYPE,
                signal=self.signal,
                user_groups=self.user_groups,
                options=self.options,
                create_user=username,
                create_time=timezone.now(),
            )

            return {"create_data": [{"cls": StrategyActionConfigRelation, "objs": [new_relation]}]}

    @classmethod
    def from_models(
        cls, relations: list["StrategyActionConfigRelation"], action_configs: dict[int, "ActionConfig"]
    ) -> list[Self]:
        """
        数据模型转换为监控项对象
        """

        results: list[Self] = []
        for relation in relations:
            if relation.config_id not in action_configs:
                config = {}
            else:
                config_obj = action_configs[relation.config_id]
                config = {
                    "id": config_obj.pk,
                    "name": config_obj.name,
                    "desc": config_obj.desc,
                    "bk_biz_id": config_obj.bk_biz_id,
                    "plugin_id": config_obj.plugin_id,
                    "execute_config": config_obj.execute_config,
                }
            results.append(
                cls(
                    strategy_id=relation.strategy_id,
                    id=relation.pk,
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


@final
class NoticeRelation(BaseActionRelation):
    """
    通知套餐关联关系
    """

    RELATE_TYPE = StrategyActionConfigRelation.RelateType.NOTICE

    @final
    class Serializer(BaseActionRelation.Serializer):
        config = NotifyActionConfigSlz()

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        if ActionSignal.ABNORMAL in self.signal and ActionSignal.NO_DATA not in self.signal:
            # 如果用户配置了异常通知，那么无数据通知也会默认打开
            self.signal.append(ActionSignal.NO_DATA)
        elif ActionSignal.ABNORMAL not in self.signal and ActionSignal.NO_DATA in self.signal:
            self.signal.remove(ActionSignal.NO_DATA)

        self.options.setdefault("assign_mode", [AssignMode.ONLY_NOTICE, AssignMode.BY_RULE])

        # 降噪配置
        self.options.setdefault("noise_reduce_config", {})
        noise_reduce_config: dict[str, Any] = self.options["noise_reduce_config"]
        if noise_reduce_config.get("is_enabled", False):
            # 默认后台设置降噪的时间窗口
            noise_reduce_config["timedelta"] = NOISE_REDUCE_TIMEDELTA
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

    @override
    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["config"] = self.config
        return data

    @override
    @classmethod
    def delete_useless(cls, relation_ids: list[int]):
        """
        删除策略下多余的Action关联记录
        """
        relations = StrategyActionConfigRelation.objects.filter(id__in=relation_ids)
        config_ids = relations.values_list("config_id", flat=True)
        relations.delete()
        ActionConfig.objects.filter(id__in=list(config_ids)).delete()

    @override
    def save(self, operator: str = ""):
        """
        根据配置新建或更新关联记录
        """
        action_config: ActionConfig | None = None

        try:
            action_relation = StrategyActionConfigRelation.objects.get(id=self.id, strategy_id=self.strategy_id)
        except StrategyActionConfigRelation.DoesNotExist:
            pass
        else:
            action_config = ActionConfig.objects.get(id=action_relation.config_id)

        if action_config is None:
            # 通过 objects 管理器创建新实例，确保使用正确的数据库
            action_config = ActionConfig.objects.create(
                name="告警通知",
                desc=f"通知套餐，策略ID: {self.strategy_id}",
                bk_biz_id="0",
                plugin_id=str(ActionConfig.NOTICE_PLUGIN_ID),
                execute_config={"template_detail": self.config},
                update_user=operator,
                update_time=timezone.now(),
            )
        else:
            action_config.name = "告警通知"
            action_config.desc = f"通知套餐，策略ID: {self.strategy_id}"
            action_config.bk_biz_id = "0"
            action_config.plugin_id = str(ActionConfig.NOTICE_PLUGIN_ID)
            action_config.execute_config = {"template_detail": self.config}
            action_config.update_user = operator
            action_config.update_time = timezone.now()
            action_config.save()

        self.config_id = action_config.pk

        return super().save()

    @override
    def bulk_save(
        self,
        relations: dict[int, list[StrategyActionConfigRelation]],
        action_configs: dict[int, ActionConfig] | None = None,
        operator: str = "",
    ):
        """
        根据配置新建或更新关联记录,循环结束后批量创建或更新
        """
        action_configs = action_configs or {}
        action_relations = relations.get(self.strategy_id, [])
        create_or_update_datas: dict[str, list[dict[str, Any]]] = {"create_data": [], "update_data": []}
        username = operator or "unknown"
        for action_relation in action_relations:
            if self.id == action_relation.pk:
                config_id = action_relation.config_id
                action_config = action_configs.get(config_id)
                if action_config:
                    action_config.name = _("告警通知")
                    action_config.desc = _("通知套餐，策略ID: {}").format(self.strategy_id)
                    action_config.bk_biz_id = "0"
                    action_config.plugin_id = str(ActionConfig.NOTICE_PLUGIN_ID)
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

    @override
    @classmethod
    def from_models(
        cls, relations: list["StrategyActionConfigRelation"], action_configs: dict[int, "ActionConfig"] | None = None
    ) -> list[BaseActionRelation]:
        """
        数据模型转换为监控项对象
        """

        action_configs = action_configs or {}
        results: list[BaseActionRelation] = []
        for relation in relations:
            if relation.config_id not in action_configs:
                config = {}
            else:
                config_obj = action_configs[relation.config_id]
                execute_config = config_obj.execute_config
                config = execute_config["template_detail"]

            results.append(
                cls(
                    strategy_id=relation.strategy_id,
                    id=relation.pk,
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


@final
class ActionRelation(BaseActionRelation):
    """
    处理套餐关联关系
    """

    RELATE_TYPE = StrategyActionConfigRelation.RelateType.ACTION

    @final
    class Serializer(BaseActionRelation.Serializer):
        @final
        class ActionRelationOptionsSerializer(serializers.Serializer):
            converge_config = ConvergeConfigSlz()
            skip_delay = serializers.IntegerField(required=False, default=0)

            def validate_converge_config(self, data: dict[str, Any]) -> dict[str, Any]:
                # 默认防御维度
                data["condition"] = [
                    {"dimension": "action_info", "value": ["self"]},
                ]
                return data

        options = ActionRelationOptionsSerializer()


@final
class Algorithm(AbstractConfig):
    """
    检测算法
    """

    @final
    class Serializer(serializers.Serializer):
        AlgorithmSerializers = {
            "Threshold": partial(ThresholdSerializer, allow_empty=True),
            "NewSeries": NewSeriesSerializer,
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

        @override
        def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
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
        type: str,  # noqa: A002
        config: dict[str, Any] | list[list[dict[str, Any]]],
        level: int,
        unit_prefix: str = "",
        id: int = 0,  # noqa: A002
        instance: AlgorithmModel | None = None,
        **kwargs: Any,
    ):
        self.id = id
        self.type = type
        self.config = config
        self.level = level
        self.unit_prefix = unit_prefix
        self.strategy_id = strategy_id
        self.item_id = item_id
        self.instance = instance

    @override
    def to_dict(self) -> dict[str, Any]:
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
        self.id = algorithm.pk

    @override
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
                id=algorithm.pk,
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


@final
class Detect(AbstractConfig):
    """
    检测配置
    """

    @final
    class Serializer(serializers.Serializer):
        @final
        class TriggerConfig(serializers.Serializer):
            @final
            class Uptime(serializers.Serializer):
                @final
                class TimeRange(serializers.Serializer):
                    start = serializers.CharField(label="开始时间")
                    end = serializers.CharField(label="结束时间")

                time_ranges = TimeRange(label="生效时间范围", default=[], many=True, allow_empty=True)
                calendars = serializers.ListField(
                    label="不生效日历列表", allow_empty=True, default=[], child=serializers.IntegerField()
                )
                active_calendars = serializers.ListField(
                    label="生效日历列表", allow_empty=True, default=[], child=serializers.IntegerField()
                )

            count = serializers.IntegerField()
            check_window = serializers.IntegerField()
            uptime = Uptime(required=False)

        @final
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

        def validate_expression(self, value: Any) -> Any:
            if not value:
                return value
            try:
                parse_expression(value)
            except Exception as e:
                raise ValidationError(str(e)) from e
            return value

    def __init__(
        self,
        strategy_id: int,
        level: int | str,
        trigger_config: dict[str, Any],
        recovery_config: dict[str, Any],
        expression: str = "",
        connector: str = "and",
        id: int = 0,  # noqa: A002
        instance: DetectModel | None = None,
        **kwargs: Any,
    ):
        self.id = id
        self.level = int(level)
        self.expression = expression
        self.strategy_id = strategy_id
        self.trigger_config = trigger_config
        self.recovery_config = recovery_config
        self.connector = connector or "and"
        self.instance = instance

    @override
    def to_dict(self) -> dict[str, Any]:
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
        self.id = detect.pk

    @override
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
                id=detect.pk,
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


@final
class QueryConfig(AbstractConfig):
    """
    查询配置
    """

    index_set_id: int  # pyright: ignore[reportUninitializedInstanceVariable]
    result_table_id: str  # pyright: ignore[reportUninitializedInstanceVariable]
    data_label: str  # pyright: ignore[reportUninitializedInstanceVariable]
    promql: str  # pyright: ignore[reportUninitializedInstanceVariable]
    agg_method: str  # pyright: ignore[reportUninitializedInstanceVariable]
    agg_interval: int  # pyright: ignore[reportUninitializedInstanceVariable]
    agg_dimension: list[str]  # pyright: ignore[reportUninitializedInstanceVariable]
    agg_condition: list[dict[str, Any]]  # pyright: ignore[reportUninitializedInstanceVariable]
    metric_field: str  # pyright: ignore[reportUninitializedInstanceVariable]
    unit: str  # pyright: ignore[reportUninitializedInstanceVariable]
    time_field: str  # pyright: ignore[reportUninitializedInstanceVariable]
    custom_event_name: str  # pyright: ignore[reportUninitializedInstanceVariable]
    origin_config: dict[str, Any]  # pyright: ignore[reportUninitializedInstanceVariable]
    intelligent_detect: dict[str, Any]  # pyright: ignore[reportUninitializedInstanceVariable]
    values: list[str]  # pyright: ignore[reportUninitializedInstanceVariable]

    QueryConfigSerializerMapping: ClassVar[dict[tuple[str, str], type[QueryConfigSerializer]]] = {
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
        (DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES): PrometheusTimeSeriesSerializer,
    }

    def __init__(
        self,
        strategy_id: int,
        item_id: int,
        data_source_label: str,
        data_type_label: str,
        alias: str,
        id: int = 0,  # noqa: A002
        metric_id: str = "",
        instance: QueryConfigModel | None = None,
        **kwargs: Any,
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

        validated_data = cast(dict[str, Any], serializer.validated_data)
        for field, value in validated_data.items():
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

    @override
    def to_dict(self) -> dict[str, Any]:
        # 自动生成metric_id
        if not self.metric_id:
            self.metric_id = self.get_metric_id()

        result: dict[str, Any] = {
            "data_source_label": self.data_source_label,
            "data_type_label": self.data_type_label,
            "alias": self.alias,
            "metric_id": self.metric_id,
            "id": self.id,
        }

        slz: QueryConfigSerializer = cast(
            QueryConfigSerializer,
            self.get_serializer_class(data_source_label=self.data_source_label, data_type_label=self.data_type_label)(),
        )
        for field in slz.get_config_field_names():
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
        self.id = obj.pk

    @override
    def save(self, instance: "Item | None" = None):
        self._clean_empty_dimension()
        self.supplement_adv_condition_dimension(instance)

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
        data: dict[str, Any] = {
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
        records: list[QueryConfig] = []
        for query_config in query_configs:
            record = QueryConfig(
                id=query_config.pk,
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

    def supplement_adv_condition_dimension(self, instance: "Item | None" = None):
        """
        高级条件补全维度
        """
        if not hasattr(self, "agg_dimension"):
            return
        if instance is not None:
            # 多指标时，不进行维度补充
            if len(instance.query_configs) > 1:
                return
        has_advance_method = False
        dimensions: set[str] = set()
        for condition in self.agg_condition:
            if condition["method"] in ["reg", "nreg", "include", "exclude"]:
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


@final
class Item(AbstractConfig):
    """
    监控项配置
    """

    _id: int
    _strategy_id: int
    _query_output_config: dict[str, Any] | None = None

    @final
    class Serializer(serializers.Serializer):
        @final
        class TargetSerializer(serializers.Serializer):
            field = serializers.CharField()
            value = serializers.ListField(child=serializers.DictField(), allow_empty=False)
            method = serializers.CharField()

            @override
            def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
                attrs["value"] = [v for v in attrs["value"] if v]
                return attrs

        @final
        class FunctionSerializer(serializers.Serializer):
            @final
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
        no_data_config: dict[str, Any],
        target: list[list[dict[str, Any]]] | None = None,
        expression: str = "",
        functions: list[dict[str, Any]] | None = None,
        origin_sql: str = "",
        id: int = 0,  # noqa: A002
        query_configs: list[dict[str, Any]] | None = None,
        algorithms: list[dict[str, Any]] | None = None,
        metric_type: str = "",
        instance: ItemModel | None = None,
        time_delay: int | None = None,
        **kwargs: Any,
    ):
        self.functions = functions or []
        self.name = name
        self.no_data_config = no_data_config
        self.target: list[list[dict[str, Any]]] = target or [[]]
        self.expression = expression
        self.origin_sql = origin_sql
        self.query_configs: list[QueryConfig] = [QueryConfig(strategy_id, id, **c) for c in query_configs or []]
        self.algorithms: list[Algorithm] = [Algorithm(strategy_id, id, **c) for c in algorithms or []]
        self.strategy_id = strategy_id
        self._strategy_id = strategy_id
        self.id = id
        self._id = id
        self.instance = instance
        self.time_delay = time_delay or 0

        if metric_type:
            self.metric_type = metric_type
        else:
            self.metric_type = self.query_configs[0].data_type_label if self.query_configs else ""

    @property
    def id(self) -> int:
        return self._id

    @id.setter
    def id(self, value: int):
        self._id = value
        for obj in chain(self.query_configs, self.algorithms):
            obj.item_id = value

    @property
    def strategy_id(self) -> int:
        return self._strategy_id

    @strategy_id.setter
    def strategy_id(self, value: int):
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

    @override
    def to_dict(self) -> dict[str, Any]:
        if self.metric_type:
            metric_type = self.metric_type
        else:
            metric_type = self.query_configs[0].data_type_label
        data = {
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
        if isinstance(self._query_output_config, dict):
            data["query_output_config"] = self._query_output_config
        return data

    def to_unify_query_config(self) -> dict[str, Any]:
        """
        生成统一查询配置
        """
        # 查询配置生成
        query_list: list[dict[str, Any]] = []
        for query_config in self.query_configs:
            # 查询条件格式转换
            conditions: dict[str, Any] = {"field_list": [], "condition_list": []}
            for condition in query_config.agg_condition:
                if conditions["field_list"]:
                    conditions["condition_list"].append(condition.get("condition", "and"))

                value: list[Any] = (
                    cast(list[Any], condition["value"])
                    if isinstance(condition["value"], list)
                    else [condition["value"]]
                )
                conditions["field_list"].append(
                    {"field_name": condition["key"], "value": value, "op": condition["method"]}
                )
            query: dict[str, Any] = {
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

    @override
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
        data.pop("query_output_config", None)
        data["name"] = data.get("name", "")[:256]
        item = ItemModel.objects.create(strategy_id=self.strategy_id, **data)
        self.id = item.pk
        return item

    def save_algorithms(self):
        self.reuse_exists_records(
            AlgorithmModel,
            list(AlgorithmModel.objects.filter(strategy_id=self.strategy_id, item_id=self.id).only("id")),
            self.algorithms,
            Algorithm,
        )

        for algo in self.algorithms:
            algo.save()

    def save_query_configs(self):
        self.reuse_exists_records(
            QueryConfigModel,
            list(QueryConfigModel.objects.filter(strategy_id=self.strategy_id, item_id=self.id).only("id")),
            self.query_configs,
            QueryConfig,
        )

        for query_config in self.query_configs:
            query_config.save(self)

    @override
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
    ) -> list[Self]:
        """
        数据模型转换为监控项对象
        """
        records: list[Self] = []
        for item in items:
            # meta 的历史默认值是 []；仅从对象元数据中恢复受管的命名输出配置。
            query_output_config: dict[str, Any] | None = None
            if isinstance(item.meta, dict):
                item_meta = cast(dict[str, Any], item.meta)
                raw_query_output_config: Any = item_meta.get("query_output_config")
                if isinstance(raw_query_output_config, dict):
                    query_output_config = cast(dict[str, Any], raw_query_output_config)
            record = cls(
                id=item.pk,
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
            record._query_output_config = query_output_config
            record.algorithms = Algorithm.from_models(algorithms[item.pk])
            record.query_configs = QueryConfig.from_models(query_configs[item.pk])
            records.append(record)

        return records


class _Empty:
    """用于区分"字段未传"与"显式传 None"的 sentinel 对象。"""


ISSUE_CONFIG_EMPTY = _Empty()


@final
class IssueConfig:
    """Issues 聚合配置，挂在 Strategy 对象上，与 ActionRelation 并列。

    生命周期完全由 Strategy.save() / Strategy.delete() 驱动。
    校验逻辑（跨模型约束 + 字段级合法性）内聚在 validate() 方法中。
    """

    VALID_CONDITION_METHODS = {"eq", "neq", "include", "exclude", "reg", "nreg"}

    @final
    class Serializer(serializers.Serializer):
        is_enabled = serializers.BooleanField(default=True)
        aggregate_dimensions = serializers.ListField(child=serializers.CharField(), default=list)
        conditions = serializers.ListField(default=list)
        alert_levels = serializers.ListField(child=serializers.IntegerField(), default=list)

    def __init__(self, strategy_id: int = 0, bk_biz_id: int = 0, **kwargs: Any):
        self.strategy_id = strategy_id
        self.bk_biz_id = bk_biz_id
        self.is_enabled: bool = kwargs.get("is_enabled", True)
        self.aggregate_dimensions: list[str] = kwargs.get("aggregate_dimensions", [])
        self.conditions: list[dict[str, Any]] = kwargs.get("conditions", [])
        self.alert_levels: list[int] = kwargs.get("alert_levels", [])

    @classmethod
    def from_model(cls, config_model: StrategyIssueConfigModel) -> "IssueConfig":
        """从 ORM 模型构建领域对象。"""
        return cls(
            strategy_id=config_model.strategy_id,
            bk_biz_id=config_model.bk_biz_id,
            is_enabled=config_model.is_enabled,
            aggregate_dimensions=config_model.aggregate_dimensions,
            conditions=config_model.conditions,
            alert_levels=config_model.alert_levels,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_enabled": self.is_enabled,
            "aggregate_dimensions": self.aggregate_dimensions,
            "conditions": self.conditions,
            "alert_levels": self.alert_levels,
        }

    def validate(self, strategy: "Strategy") -> None:
        """校验 issue_config 的跨模型约束 + 字段级合法性。

        - alert_levels 必须为 [1,2,3] 的非空子集
        - aggregate_dimensions 必须是策略 public_dimensions 的子集
        - conditions.key 必须属于生效维度集合；method 必须合法；必填字段完整

        直接从 strategy.public_dimensions 计算，不依赖 strategy.id 或缓存，
        新建策略（id=0）也能正确校验。
        """
        if not self.alert_levels or not set(self.alert_levels).issubset({1, 2, 3}):
            raise ValidationError(detail=_("alert_levels 必须为 [1,2,3] 的非空子集"))

        public_dims = set(strategy.public_dimensions)

        if self.aggregate_dimensions:
            invalid = set(self.aggregate_dimensions) - public_dims
            if invalid:
                raise ValidationError(
                    detail=_(
                        "aggregate_dimensions 包含策略公共维度之外的字段: {invalid}，当前策略 public_dimensions 为: {public_dims}"
                    ).format(invalid=invalid, public_dims=public_dims)
                )

        effective_dims = set(self.aggregate_dimensions) if self.aggregate_dimensions else public_dims
        for cond in self.conditions:
            self._validate_condition_item(cond, effective_dims)

    @classmethod
    def _validate_condition_item(cls, cond: Any, effective_dimensions: set[str]) -> None:
        """校验单条 condition 的结构与字段合法性。"""
        if not isinstance(cond, dict):
            raise ValidationError(detail=f"conditions 条目必须为 dict，当前为 {type(cond)}")

        cond_dict = cast(dict[str, Any], cond)
        required_keys = {"key", "method", "value"}
        missing = required_keys - set(cond_dict.keys())
        if missing:
            raise ValidationError(detail=f"conditions 条目缺少字段: {sorted(missing)}")

        key: Any = cond_dict.get("key")
        method: Any = cond_dict.get("method")
        value: Any = cond_dict.get("value")

        if not isinstance(key, str) or not key:
            raise ValidationError(detail="conditions.key 必须为非空字符串")
        if method not in cls.VALID_CONDITION_METHODS:
            raise ValidationError(detail=f"不支持的 method: {method}")
        if value is None:
            raise ValidationError(detail="conditions.value 不能为空")
        if key not in effective_dimensions:
            raise ValidationError(detail=f"conditions.key={key} 不在可用维度集合中")

    def save(self, strategy_id: int, bk_biz_id: int) -> None:
        """创建或更新 StrategyIssueConfigModel（软删除恢复 + upsert）。"""
        defaults: dict[str, Any] = {
            "bk_biz_id": bk_biz_id,
            "is_enabled": self.is_enabled,
            "is_deleted": False,
            "aggregate_dimensions": self.aggregate_dimensions,
            "conditions": self.conditions,
            "alert_levels": self.alert_levels,
        }
        temp = StrategyIssueConfigModel(strategy_id=strategy_id, **defaults)
        temp.full_clean(validate_unique=False)

        StrategyIssueConfigModel.objects.update_or_create(
            strategy_id=strategy_id,
            defaults=defaults,
        )

    @staticmethod
    def delete(strategy_id: int) -> None:
        """软删除指定策略的 issue_config 记录。"""
        StrategyIssueConfigModel.objects.filter(strategy_id=strategy_id, is_deleted=False).update(
            is_deleted=True, is_enabled=False, update_time=timezone.now()
        )

    @staticmethod
    def delete_by_strategy_ids(strategy_ids: list[int]) -> None:
        """批量软删除 issue_config 记录。"""
        StrategyIssueConfigModel.objects.filter(strategy_id__in=strategy_ids, is_deleted=False).update(
            is_deleted=True, is_enabled=False, update_time=timezone.now()
        )


@final
class Strategy(AbstractConfig):
    """
    策略 数据结构
    """

    _id: int

    version = "v2"

    ExtendFields = ["index_set_id", "time_field", "values", "custom_event_name", "origin_config", "intelligent_detect"]

    @final
    class Serializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        id = serializers.IntegerField(required=False)
        name = serializers.CharField()
        type = serializers.CharField(default=StrategyModel.StrategyType.Monitor)
        source = serializers.CharField(default=SourceApp.MONITOR)
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
        priority_group_key = serializers.CharField(allow_blank=True, default="", max_length=60)
        metric_type = serializers.CharField(allow_blank=True, default="")
        # required=False + 无 default：字段缺失时不写入 validated_data，与显式 null 天然区分
        issue_config = IssueConfig.Serializer(required=False, allow_null=True)

        def validate_priority_group_key(self, value: str) -> str:
            if value.startswith(CUSTOM_PRIORITY_GROUP_PREFIX):
                return value
            return ""

        @override
        def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
            name = attrs.get("name", "")
            is_builtin_name = name.startswith("集成内置") or name.startswith("Datalink BuiltIn")
            if attrs.get("source") != DATALINK_SOURCE and is_builtin_name:
                raise ValidationError(detail="Name starts with 'Datalink BuiltIn' and '集成内置' is forbidden")
            return attrs

    def __init__(
        self,
        bk_biz_id: int,
        name: str,
        scenario: str,
        source: str | None = None,
        type: str = StrategyModel.StrategyType.Monitor,  # noqa: A002
        id: int = 0,  # noqa: A002
        items: list[dict[str, Any]] | None = None,
        actions: list[dict[str, Any]] | None = None,
        notice: dict[str, Any] | None = None,
        detects: list[dict[str, Any]] | None = None,
        is_enabled: bool = True,
        is_invalid: bool = False,
        invalid_type: str = StrategyModel.InvalidType.NONE,
        update_user: str = "",
        update_time: datetime | None = None,
        create_user: str = "",
        create_time: datetime | None = None,
        labels: list[str] | None = None,
        app: str | None = None,
        path: str | None = None,
        priority: int | None = None,
        priority_group_key: str | None = None,
        metric_type: str = "",
        instance: StrategyModel | None = None,
        issue_config: dict[str, Any] | None | _Empty = ISSUE_CONFIG_EMPTY,
        **kwargs: Any,
    ):
        """
        :param id: 策略ID
        :param name: 策略名称
        :param source: 来源应用
        :param scenario: 监控对象类型
        """
        self.bk_biz_id = bk_biz_id
        self.name = name
        self.source = source or get_config().blueking.app_code
        self.scenario = scenario
        self.type = type
        self.items: list[Item] = [Item(id, **item) for item in items or []]
        self.detects: list[Detect] = [Detect(id, **detect) for detect in detects or []]
        self.actions: list[ActionRelation] = [ActionRelation(id, **action) for action in actions or []]
        self.notice: NoticeRelation = NoticeRelation(id, **(notice or {}))
        self.is_enabled = is_enabled
        self.is_invalid = is_invalid
        self.invalid_type = invalid_type
        self._id = id
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
        # ISSUE_CONFIG_EMPTY（sentinel）= 字段未传，不操作已有配置
        # None = 显式传 null，删除已有配置
        # dict = 显式传值，upsert 配置
        self._issue_config_in_request: bool = not isinstance(issue_config, _Empty)
        self.issue_config: IssueConfig | None = IssueConfig(**issue_config) if isinstance(issue_config, dict) else None

        if isinstance(self.update_time, int | str):
            self.update_time = arrow.get(self.update_time).datetime

        if isinstance(self.create_time, int | str):
            self.create_time = arrow.get(self.create_time).datetime

        for item in self.items:
            item.metric_type = metric_type

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value: int):
        self._id = value
        for obj in chain(self.actions, self.items, self.detects, [self.notice]):
            obj.strategy_id = value

    @override
    def to_dict(self) -> dict[str, Any]:
        """
        转换为JSON字典
        """
        if self.priority is None:
            priority_group_key = ""
        else:
            if self.priority_group_key:
                priority_group_key = self.priority_group_key
            else:
                # 自动生成优先级分组key
                priority_group_key = self.get_priority_group_key(self.bk_biz_id, self.items)

        config: dict[str, Any] = {
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
        config["issue_config"] = self.issue_config.to_dict() if self.issue_config else None

        for item in config["items"]:
            if item["expression"]:
                continue
            item["expression"] = " + ".join([query_config["alias"] for query_config in item["query_configs"]])

        return config

    def _create(self, operator: str):
        strategy = StrategyModel.objects.create(
            name=self.name,
            scenario=self.scenario,
            source=self.source,
            bk_biz_id=self.bk_biz_id,
            type=self.type,
            is_enabled=self.is_enabled,
            is_invalid=self.is_invalid,
            invalid_type=self.invalid_type,
            create_user=operator,
            update_user=operator,
            priority=self.priority,
            priority_group_key=self.get_priority_group_key(self.bk_biz_id, self.items, self.priority_group_key)
            if self.priority is not None
            else "",
        )
        self.id = strategy.pk

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
        redundant_labels: set[str] = set()
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

    def save_issue_config(self) -> None:
        """持久化 issue_config。仅当 _issue_config_in_request=True 时由 save() 调用。

        - issue_config 非 None：validate + upsert StrategyIssueConfigModel
        - issue_config 为 None（显式传 null）：删除已有 StrategyIssueConfig（关闭 Issues 功能）
        """
        if self.issue_config is not None:
            self.issue_config.validate(self)
            self.issue_config.save(self.id, self.bk_biz_id)
        else:
            IssueConfig.delete(self.id)

    @transaction.atomic
    def save_actions(self):
        """保存actions配置."""
        self.reuse_exists_records(
            StrategyActionConfigRelation,
            list(
                StrategyActionConfigRelation.objects.filter(
                    strategy_id=self.id, relate_type=StrategyActionConfigRelation.RelateType.ACTION
                ).only("id")
            ),
            self.actions,
            ActionRelation,
        )

        # 保存子配置
        for action in self.actions:
            action.save()

    @transaction.atomic
    def save_notice(self, operator: str = ""):
        """保存actions配置."""
        self.reuse_exists_records(
            StrategyActionConfigRelation,
            list(
                StrategyActionConfigRelation.objects.filter(
                    strategy_id=self.id, relate_type=StrategyActionConfigRelation.RelateType.NOTICE
                ).only("id")
            ),
            [self.notice],
            NoticeRelation,
        )

        # 保存子配置
        self.notice.save(operator)

    @transaction.atomic
    def bulk_save_notice(
        self,
        relations: dict[int, list[StrategyActionConfigRelation]],
        action_configs: dict[int, ActionConfig] | None = None,
        operator: str = "",
    ):
        """保存actions配置,循环结束后批量创建或更新."""
        self.reuse_exists_records(
            StrategyActionConfigRelation,
            relations.get(self.id, []),
            [self.notice],
            NoticeRelation,
        )

        # 保存子配置
        create_or_update_datas = self.notice.bulk_save(relations, action_configs, operator)

        return create_or_update_datas

    @override
    @transaction.atomic
    def save(self, rollback: bool = False, operator: str = "", aiops_access_func: Callable[[int], str] | None = None):
        """保存策略配置

        Args:
            rollback: 是否回滚
            operator: 操作人
            aiops_access_func: 智能检测接入函数，输入策略ID，返回异步任务ID
        """
        self.supplement_inst_target_dimension()
        need_access_aiops, algorithm_name = self.check_aiops_access()

        if not rollback:
            history = StrategyHistoryModel.objects.create(
                create_user=operator,
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
                strategy.update_user = operator
                strategy.priority = self.priority
                strategy.priority_group_key = (
                    self.get_priority_group_key(self.bk_biz_id, self.items, self.priority_group_key)
                    if self.priority is not None
                    else ""
                )
                strategy.save()
            else:
                self._create(operator)

            # 复用当前存在的记录
            model_configs = [
                (ItemModel, Item, self.items),
                (DetectModel, Detect, self.detects),
            ]
            for model, config_cls, configs in model_configs:
                objs = model.objects.filter(strategy_id=self.id).only("id")
                self.reuse_exists_records(model, list(objs), configs, config_cls)

            # 保存子配置
            for obj in chain(self.items, self.detects):
                obj.save()

            # 复用旧ID地保存actions和notice
            self.save_actions()
            self.save_notice(operator=operator)

            # 保存策略标签
            self.save_labels()

            # 保存 issue_config（仅当请求体中携带该字段时执行）
            if self._issue_config_in_request:
                self.save_issue_config()

            if history and history.strategy_id == 0:
                history.strategy_id = self.id
                history.save()
        except StrategyModel.DoesNotExist:
            if history:
                history.message = _("策略({})不存在").format(self.id)
                history.save()
            raise StrategyNotExistError() from None
        except Exception as e:
            # 回滚失败直接报错
            if rollback:
                raise e

            if history:
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

        if history:
            history.status = True
            history.save()

        if need_access_aiops:
            self.access_aiops(algorithm_name=algorithm_name, aiops_access_func=aiops_access_func)

    def check_aiops_access(self):
        """
        检查智能监控接入配置
        (目前仅支持监控时序、计算平台时序数据)
        """

        # 1. 未开启计算平台接入，则直接返回
        if not get_config().blueking.bkbase.enabled:
            return False, ""

        # 2. 获取配置的智能检测算法(AIOPS)
        intelligent_algorithm = None
        algorithm_plan_id: int | None = None
        for algorithm in chain(*(item.algorithms for item in self.items)):
            if algorithm.type in AlgorithmModel.AIOPS_ALGORITHMS:
                intelligent_algorithm = algorithm.type
                algorithm_config = cast(dict[str, Any], algorithm.config)
                algorithm_plan_id = algorithm_config.get("plan_id", 0)
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
        self, query_config: QueryConfig, algorithm_name: str | None = None, algorithm_plan_id: int | None = None
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

                plan = IntelligentDetectAlgorithms.get(algorithm_plan_id or 0)
                if not plan:
                    raise ValidationError(_("未找到当前智能算法的方案配置，请联系系统管理员"))

                unsupported_algorithms = [
                    "log_patterns_anomaly_detection_with_dimensions",
                    "general_anomaly_detection_for_crash_failure_metric",
                ]
                if plan["name"] in unsupported_algorithms:
                    raise ValidationError(_(f"{plan['alias']}算法不支持数据来源: {data_source_label_name}"))

            if query_config.data_source_label in (DataSourceLabel.BK_MONITOR_COLLECTOR, DataSourceLabel.BK_DATA):
                need_access = True

        # 4.4 如果不需要走bkbase接入流程或者配置使用SDK进行检测，则更新query_config中关于使用sdk的配置
        intelligent_detect: dict[str, Any] = getattr(query_config, "intelligent_detect", {})
        default_switch = (
            True
            if (
                algorithm_plan_id == get_config().blueking.bkbase.intelligent_detect_plan_id
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

    def access_aiops(self, algorithm_name: str, aiops_access_func: Callable[[int], str] | None = None):
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
            self.access_algorithm_by_query_config(query_config, algorithm_name, aiops_access_func)

    def access_algorithm_by_query_config(
        self,
        query_config: QueryConfig,
        algorithm_name: str,
        aiops_access_func: Callable[[int], str] | None = None,
    ):
        """根据查询配置把算法对应的后台任务接入到bkbase中.

        :param query_config: 查询配置
        :param algorithm_name: 算法名称
        """

        if query_config.data_type_label != DataTypeLabel.TIME_SERIES:
            return

        # 如果数据来源是计算平台，则需要先进行授权给监控项目，再标记需要接入智能检测算法
        if query_config.data_source_label == DataSourceLabel.BK_DATA:
            # 授权给监控项目(以创建或更新策略的用户来请求一次授权)
            # 主机异常检测使用业务主机观测场景的flow，因此不需要授权
            if algorithm_name in (
                set(AlgorithmModel.AIOPS_ALGORITHMS) - set(AlgorithmModel.AUTHORIZED_SOURCE_ALGORITHMS)
            ):
                # 检查是否已经授权
                try:
                    has_permission = bkdata_api.auth_projects_data_check(
                        bk_tenant_id=bk_biz_id_to_bk_tenant_id(self.bk_biz_id),
                        project_id=get_config().blueking.bkbase.project_id,
                        result_table_id=query_config.result_table_id,
                    )
                except BkApiError:
                    has_permission = False

                # 如果未授权，则进行授权
                if not has_permission:
                    bkdata_api.auth_result_table(
                        bk_tenant_id=bk_biz_id_to_bk_tenant_id(self.bk_biz_id),
                        project_id=get_config().blueking.bkbase.project_id,
                        object_id=query_config.result_table_id,
                        bk_biz_id=self.bk_biz_id,
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
            if aiops_access_func:
                intelligent_detect["task_id"] = aiops_access_func(self.id)

        query_config.intelligent_detect = intelligent_detect
        query_config.save()

    @classmethod
    def get_priority_group_key(cls, bk_biz_id: int, items: list[Item], priority_group_key: str = ""):
        """
        获取优先级分组key
        """
        if priority_group_key:
            # 指定优先级分组key的场景，需要判定是自动算的还是用户指定的
            # 自动算的是16位uuid，用户指定带固定前缀 PGK:
            if priority_group_key.startswith(CUSTOM_PRIORITY_GROUP_PREFIX):
                return priority_group_key

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

            item_query: dict[str, Any] = {
                "bk_biz_id": bk_biz_id,
                "data_source_label": query_config.data_source_label,
                "data_type_label": query_config.data_type_label,
                "expression": item.expression,
                "functions": item.functions,
                "query_configs": [],
            }

            for query_config in item.query_configs:
                new_query_config: dict[str, Any] = {}

                for field in query_config_fields:
                    new_query_config[field] = getattr(query_config, field, None)

                # 聚合维度排序
                if new_query_config["agg_dimension"]:
                    new_query_config["agg_dimension"] = sorted(new_query_config["agg_dimension"])

                # promql需要去除条件
                if getattr(query_config, "promql", None):
                    bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
                    try:
                        origin_config = unify_query_api.promql_to_struct(
                            bk_tenant_id=bk_tenant_id, promql=query_config.promql
                        )
                        query_list: list[dict[str, Any]] = origin_config.pop("query_list")
                        for _query in query_list:
                            _query["conditions"] = {"field_list": [], "condition_list": []}
                        promql = unify_query_api.struct_to_promql(
                            bk_tenant_id=bk_tenant_id,
                            params={
                                "space_uid": bk_biz_id_to_space_uid(bk_biz_id),
                                "query_list": query_list,
                                "metric_merge": origin_config.pop("metric_merge", None),
                                "order_by": origin_config.pop("order_by", None),
                                "step": origin_config.pop("step", None),
                            },
                        )
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
        if str(self.bk_biz_id) in {str(biz) for biz in get_config().common.ipv6_support_biz_list}:
            host_dimensions = {"bk_host_id"}
        else:
            host_dimensions = {"bk_target_ip", "bk_target_cloud_id"}

        for item in self.items:
            if not item.target or not item.target[0]:
                return

            target: dict[str, Any] = item.target[0][0]
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
        StrategyActionConfigRelation.objects.filter(strategy_id=self.id).delete()
        DetectModel.objects.filter(strategy_id=self.id).delete()
        ItemModel.objects.filter(strategy_id=self.id).delete()
        AlgorithmModel.objects.filter(strategy_id=self.id).delete()
        QueryConfigModel.objects.filter(strategy_id=self.id).delete()
        StrategyLabel.objects.filter(strategy_id=self.id).delete()
        try:
            IssueConfig.delete(self.id)
        except (ProgrammingError, OperationalError) as exc:
            if _is_table_not_exist_error(exc):
                logger.debug("delete issue_config skipped (table not exist), strategy_id=%s", self.id)
            else:
                raise

    @classmethod
    def delete_by_strategy_ids(cls, strategy_ids: list[int], operator: str):
        """
        批量删除策略
        """
        histories: list[StrategyHistoryModel] = []
        for strategy_id in strategy_ids:
            histories.append(
                StrategyHistoryModel(
                    create_user=operator,
                    strategy_id=strategy_id,
                    operate="delete",
                )
            )
        StrategyHistoryModel.objects.bulk_create(histories, batch_size=100)

        StrategyModel.objects.filter(id__in=strategy_ids).delete()
        StrategyActionConfigRelation.objects.filter(strategy_id__in=strategy_ids).delete()
        DetectModel.objects.filter(strategy_id__in=strategy_ids).delete()
        ItemModel.objects.filter(strategy_id__in=strategy_ids).delete()
        AlgorithmModel.objects.filter(strategy_id__in=strategy_ids).delete()
        QueryConfigModel.objects.filter(strategy_id__in=strategy_ids).delete()
        StrategyLabel.objects.filter(strategy_id__in=strategy_ids).delete()
        try:
            IssueConfig.delete_by_strategy_ids(strategy_ids)
        except (ProgrammingError, OperationalError) as exc:
            if _is_table_not_exist_error(exc):
                logger.debug("bulk delete issue_config skipped (table not exist)")
            else:
                raise

    @classmethod
    def from_models(cls, strategies: list[StrategyModel] | QuerySet[StrategyModel]) -> list["Strategy"]:
        """
        数据模型转换为策略对象

        :param strategies: 策略模型列表或QuerySet，包含要转换为策略对象的数据模型。
        :return: List["Strategy"]策略对象列表
        """
        # 提取所有策略的ID
        strategy_models = list(strategies)
        strategy_ids: list[int] = [s.pk for s in strategy_models]
        if not strategy_ids:
            return []

        item_query = _iter_models_by_strategy_ids(ItemModel, strategy_ids)
        detect_query = _iter_models_by_strategy_ids(DetectModel, strategy_ids)
        algorithm_query = _iter_models_by_strategy_ids(AlgorithmModel, strategy_ids)
        query_config_query = _iter_models_by_strategy_ids(QueryConfigModel, strategy_ids)
        label_query = _iter_models_by_strategy_ids(StrategyLabel, strategy_ids)
        related_query = _iter_models_by_strategy_ids(StrategyActionConfigRelation, strategy_ids)

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
        action_config_ids: set[int] = set()
        actions: dict[int, list[StrategyActionConfigRelation]] = defaultdict(list)
        notices: dict[int, list[StrategyActionConfigRelation]] = defaultdict(list)
        for action in related_query:
            if action.relate_type == StrategyActionConfigRelation.RelateType.NOTICE:
                notices[action.strategy_id].append(action)
            else:
                actions[action.strategy_id].append(action)
            action_config_ids.add(action.config_id)

        # 查询关联自愈套餐
        action_query = _iter_models_by_ids(ActionConfig, action_config_ids)
        action_configs: dict[int, ActionConfig] = {}
        for action_config in action_query:
            action_configs[action_config.pk] = action_config

        # 根据查询和处理结果，创建策略对象
        records: list[Strategy] = []
        for strategy in strategy_models:
            record = Strategy(
                bk_biz_id=strategy.bk_biz_id,
                id=strategy.pk,
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
                labels=labels.get(strategy.pk, []),
                app=strategy.app,
                path=strategy.path,
                priority=strategy.priority,
                priority_group_key=strategy.priority_group_key,
                instance=strategy,
            )

            # 为策略对象的items、actions、detects和notice属性赋值
            record.items = Item.from_models(items[strategy.pk], algorithms, query_configs)
            record.actions = ActionRelation.from_models(actions[strategy.pk], action_configs)
            record.detects = Detect.from_models(detects[strategy.pk])

            record_notices = NoticeRelation.from_models(notices[strategy.pk], action_configs)
            if record_notices:
                record.notice = cast(NoticeRelation, record_notices[0])
            else:
                record.notice = NoticeRelation(strategy_id=strategy.pk)

            records.append(record)

        # 批量加载 StrategyIssueConfig（避免 N+1），兼容表不存在（未迁移环境）
        issue_configs: dict[int, IssueConfig] = {}
        try:
            chunk_size = 500
            for i in range(0, len(strategy_ids), chunk_size):
                chunk = strategy_ids[i : i + chunk_size]
                for c in StrategyIssueConfigModel.objects.filter(strategy_id__in=chunk, is_deleted=False):
                    issue_configs[c.strategy_id] = IssueConfig.from_model(c)
        except (ProgrammingError, OperationalError) as exc:
            if _is_table_not_exist_error(exc):
                logger.debug("load issue_config skipped (table not exist)")
            else:
                raise
        for record in records:
            record.issue_config = issue_configs.get(record.id)

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
