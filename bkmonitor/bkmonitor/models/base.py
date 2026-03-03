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
import random
import time
from typing import Any

import pytz
from bkcrypto.contrib.django.fields import SymmetricTextField
from django.conf import settings
from django.db import models
from django.db.transaction import atomic
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from bkmonitor.middlewares.source import get_source_app_code
from bkmonitor.utils import event_target, time_tools
from bkmonitor.utils.cache import InstanceCache
from bkmonitor.utils.db.fields import (
    EventStatusField,
    JsonField,
    ReadWithUnderscoreField,
)
from bkmonitor.utils.model_manager import AbstractRecordModel, Model
from constants.common import DEFAULT_TENANT_ID
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.report import StaffChoice
from constants.shield import ShieldStatus, ShieldType
from core.drf_resource import api

# nodata dimension tag
NO_DATA_TAG_DIMENSION = "__NO_DATA_DIMENSION__"

mem_cache = InstanceCache()


# hotfix: 指标名描述统一
class DescriptionAdapterField(models.CharField):
    description = "指标名描述统一"

    def from_db_value(self, value, expression, connection):
        return {_("接收字节流量"): _("网卡入流量"), _("发送字节流量"): _("网卡出流量")}.get(value, value)


#
# 监控指标相关模型
#
class SnapshotHostIndex(Model):
    CATEGORY_CHOICES = (
        ("cpu", "CPU"),
        ("net", _lazy("网络")),
        ("mem", _lazy("内存")),
        ("disk", _lazy("磁盘")),
        ("process", _lazy("进程")),
        ("system_env", _lazy("系统")),
    )

    category = models.CharField(max_length=32, verbose_name="category")
    item = ReadWithUnderscoreField(max_length=32, verbose_name="item")
    type = models.CharField(max_length=32, verbose_name="type")
    result_table_id = models.CharField(max_length=128, verbose_name="result table id")
    description = DescriptionAdapterField(max_length=50, verbose_name="description")
    dimension_field = models.CharField(max_length=1024, verbose_name="dimension field")
    conversion = models.FloatField(verbose_name="conversion")
    conversion_unit = models.CharField(max_length=32, verbose_name="conversion unit")
    metric = ReadWithUnderscoreField(blank=True, max_length=128, null=True, verbose_name="metric")
    is_linux = models.BooleanField(default=True, verbose_name="is liunx metric")
    is_windows = models.BooleanField(default=True, verbose_name="is windows metric")
    is_aix = models.BooleanField(default=True, verbose_name="is aix metric")

    class Meta:
        db_table = "app_snapshot_host_index"

    @property
    def desc(self):
        return _lazy(self.description.strip())

    @property
    def unit_display(self):
        return _lazy(self.conversion_unit)

    @property
    def dummy_category(self):
        return self.category

    def get_category_display(self):
        for category_info in SnapshotHostIndex.CATEGORY_CHOICES:
            if self.category == category_info[0]:
                return _lazy(category_info[1])
        return self.category

    @property
    def table_dimensions(self):
        default_dimension = ["bk_cloud_id", "bk_target_ip"]
        if self.dimension_field:
            default_dimension.extend(self.dimension_field.split(","))
        return list(set(default_dimension))


class BaseAlarm(Model):
    alarm_type = models.IntegerField(blank=True, default=0, verbose_name="告警标识")
    title = models.CharField(blank=True, default="", max_length=256, verbose_name="基础告警名称")
    description = models.CharField(blank=True, default="", max_length=256, verbose_name="基础告警描述")
    is_enable = models.BooleanField(default=True, null=True, verbose_name="是否启用")
    dimensions = JsonField(default=list, verbose_name="维度")

    class Meta:
        db_table = "dict_base_alarm"

    @property
    def category(self):
        return "base_alarm"

    @property
    def dummy_category(self):
        return self.category

    @property
    def real_id(self):
        return self.alarm_type

    @property
    def result_table_id(self):
        return _lazy("基础")

    @property
    def item(self):
        return self.title

    @property
    def desc(self):
        return _lazy(self.description)


class ResultTableQueryConfig(AbstractRecordModel):
    class Meta:
        abstract = True


class ResultTableSQLConfig(ResultTableQueryConfig):
    result_table_id = models.CharField(max_length=256, verbose_name="结果表")

    agg_method = models.CharField(max_length=64, verbose_name="聚合方法")
    agg_interval = models.PositiveIntegerField("聚合周期", default=60)
    agg_dimension = JsonField(verbose_name="聚合维度")
    agg_condition = JsonField(verbose_name="聚合条件")

    metric_field = models.CharField(max_length=256, verbose_name="字段")
    unit = models.CharField(max_length=32, default="", verbose_name="单位")
    unit_conversion = models.FloatField(default=1.0, verbose_name="单位转换")

    extend_fields = JsonField(verbose_name="扩展字段")

    class Meta:
        verbose_name = "SQL类结果表查询配置"
        verbose_name_plural = "SQL类结果表查询配置"
        db_table = "alarm_rt_sql_config"


class ResultTableDSLConfig(ResultTableQueryConfig):
    result_table_id = models.CharField(max_length=256, verbose_name="结果表")

    agg_method = models.CharField(max_length=64, verbose_name="聚合方法")
    agg_interval = models.PositiveIntegerField("聚合周期", default=60)
    agg_dimension = JsonField(verbose_name="聚合维度")
    agg_condition = JsonField(verbose_name="监控条件")
    # 优先使用keywords_query_string，没有则使用rule和keywords两个字段来生成
    keywords_query_string = models.TextField(verbose_name="关键字查询条件")
    rule = models.CharField(max_length=256, verbose_name="组合方式")
    keywords = JsonField(verbose_name="组合字段")

    extend_fields = JsonField(verbose_name="扩展字段")

    class Meta:
        verbose_name = "DSL类结果表查询配置"
        verbose_name_plural = "DSL类结果表查询配置"
        db_table = "alarm_rt_dsl_config"


class CustomEventQueryConfig(AbstractRecordModel):
    bk_event_group_id = models.IntegerField(verbose_name="自定义事件分组ID")
    custom_event_id = models.IntegerField(verbose_name="自定义事件ID")
    agg_dimension = JsonField(verbose_name="聚合维度")
    agg_condition = JsonField(verbose_name="监控条件")
    agg_method = models.CharField(max_length=64, verbose_name="聚合方法", default="count")
    agg_interval = models.PositiveIntegerField("聚合周期", default=60)
    extend_fields = JsonField(verbose_name="扩展字段")
    result_table_id = models.CharField(max_length=256, verbose_name="结果表", default="")

    class Meta:
        verbose_name = "自定义事件查询配置"
        verbose_name_plural = "自定义事件查询配置"
        db_table = "alarm_custom_event_group_config"


class BaseAlarmQueryConfig(AbstractRecordModel):
    agg_condition = JsonField(verbose_name="过滤条件", default=list)

    class Meta:
        verbose_name = "系统事件查询配置"
        verbose_name_plural = verbose_name
        db_table = "alarm_base_alarm_config"


class Item(AbstractRecordModel):
    """
    监控项定义

    扩展：多指标计算问题
    """

    name = models.CharField(max_length=256, verbose_name="监控项名称")
    # 指标id，时序类：使用表名 + 字段名，事件类：使用事件类型标识
    metric_id = models.CharField(max_length=128, default="", verbose_name="指标ID")
    # 数据来源标签，例如：计算平台(bk_data)，监控采集器(bk_monitor_collector)
    data_source_label = models.CharField(verbose_name="数据来源标签", max_length=255)
    # 数据类型标签，例如：时序数据(time_series)，事件数据(event)，日志数据(log)
    data_type_label = models.CharField(verbose_name="数据类型标签", max_length=255)

    rt_query_config_id = models.IntegerField(verbose_name="查询配置ID")

    no_data_config = JsonField(blank=True, default="", verbose_name="无数据配置")

    strategy_id = models.IntegerField(verbose_name="关联策略ID", db_index=True)

    target = JsonField(default=[[]], verbose_name="监控目标")

    class Meta:
        verbose_name = "策略监控项配置"
        verbose_name_plural = "策略监控项配置"
        db_table = "alarm_item"
        index_together = (("data_type_label", "data_source_label"),)

    @classmethod
    def get_query_config_model(cls, data_source_label, data_type_label):
        if data_type_label == DataTypeLabel.TIME_SERIES:
            return ResultTableSQLConfig
        elif data_type_label == DataTypeLabel.LOG:
            return ResultTableDSLConfig
        elif data_type_label == DataTypeLabel.EVENT and data_source_label == DataSourceLabel.CUSTOM:
            return CustomEventQueryConfig
        elif data_type_label == DataTypeLabel.EVENT and data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR:
            return BaseAlarmQueryConfig

    @property
    def data_target_type(self):
        return


class Strategy(AbstractRecordModel):
    """
    策略表
    """

    name = models.CharField(max_length=128, verbose_name="策略名称", db_index=True)
    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0, blank=True, db_index=True)
    source = models.CharField(verbose_name="来源系统", default=get_source_app_code, max_length=32)

    # 主机、服务、拨测、设备、网络、自定义
    scenario = models.CharField(max_length=64, verbose_name="监控场景", db_index=True)
    # 节点、实例/主机
    target = JsonField(blank=True, default="", verbose_name="监控目标")

    class Meta:
        verbose_name = "策略配置"
        verbose_name_plural = "策略配置"
        db_table = "alarm_strategy"
        index_together = (("bk_biz_id", "source"),)

    @property
    def labels(self):
        from .strategy import StrategyLabel

        labels = StrategyLabel.get_label_dict(self.id).get(self.id)
        return labels or []


class DetectAlgorithm(AbstractRecordModel):
    """
    检测算法

    config：
        不同的算法有不同的配置内容
    """

    class AlgorithmChoices:
        Threshold = "Threshold"
        SimpleRingRatio = "SimpleRingRatio"
        AdvancedRingRatio = "AdvancedRingRatio"
        SimpleYearRound = "SimpleYearRound"
        AdvancedYearRound = "AdvancedYearRound"
        PartialNodes = "PartialNodes"
        OsRestart = "OsRestart"
        ProcPort = "ProcPort"
        PingUnreachable = "PingUnreachable"
        YearRoundAmplitude = "YearRoundAmplitude"
        YearRoundRange = "YearRoundRange"
        RingRatioAmplitude = "RingRatioAmplitude"
        IntelligentDetect = "IntelligentDetect"
        HostAnomalyDetection = "HostAnomalyDetection"

    ALGORITHM_CHOICES = (
        (AlgorithmChoices.Threshold, _lazy("静态阈值算法")),
        (AlgorithmChoices.SimpleRingRatio, _lazy("简易环比算法")),
        (AlgorithmChoices.AdvancedRingRatio, _lazy("高级环比算法")),
        (AlgorithmChoices.SimpleYearRound, _lazy("简易同比算法")),
        (AlgorithmChoices.AdvancedYearRound, _lazy("高级同比算法")),
        (AlgorithmChoices.PartialNodes, _lazy("部分节点数算法")),
        (AlgorithmChoices.OsRestart, _lazy("主机重启算法")),
        (AlgorithmChoices.ProcPort, _lazy("进程端口算法")),
        (AlgorithmChoices.PingUnreachable, _lazy("Ping不可达算法")),
        (AlgorithmChoices.YearRoundAmplitude, _lazy("同比振幅算法")),
        (AlgorithmChoices.YearRoundRange, _lazy("同比区间算法")),
        (AlgorithmChoices.RingRatioAmplitude, _lazy("环比振幅算法")),
        (AlgorithmChoices.IntelligentDetect, _lazy("智能异常检测算法")),
        (AlgorithmChoices.HostAnomalyDetection, _lazy("主机异常检测算法")),
    )

    algorithm_type = models.CharField(max_length=128, choices=ALGORITHM_CHOICES, verbose_name="算法类型")
    algorithm_unit = models.CharField(max_length=32, verbose_name="算法单位", default="", blank=True)
    algorithm_config = JsonField(verbose_name="算法配置")
    trigger_config = JsonField(verbose_name="触发条件配置")
    recovery_config = JsonField(verbose_name="恢复条件配置")
    message_template = models.TextField(verbose_name="算法描述模板配置")

    level = models.IntegerField(blank=True, default=3, verbose_name="监控等级")
    item_id = models.IntegerField(verbose_name="关联监控项ID", db_index=True)
    strategy_id = models.IntegerField(verbose_name="关联策略ID", db_index=True)

    class Meta:
        verbose_name = "检测算法配置"
        verbose_name_plural = "检测算法配置"
        db_table = "alarm_detect_algorithm"


class Action(AbstractRecordModel):
    """
    动作

    action_type类型：通知、自愈/工单、推送给第三方service/access/event/config.py

    config配置：
        1. 通知类
            - start_time: 通知开始时间
            - end_time: 通知结束时间
            - alert_interval: 通知间隔
            - send_recovery_alarm: 是否发送恢复告警

    """

    action_type = models.CharField(verbose_name="动作类型", max_length=256)
    config = JsonField(verbose_name="动作配置")

    strategy_id = models.IntegerField(verbose_name="关联策略ID", db_index=True)

    class Meta:
        verbose_name = "动作配置"
        verbose_name_plural = "动作配置"
        db_table = "alarm_action"


class NoticeTemplate(AbstractRecordModel):
    """
    通知模板
    """

    anomaly_template = models.TextField(default="", verbose_name="异常通知模板")
    recovery_template = models.TextField(default="", verbose_name="恢复通知模板")

    action_id = models.IntegerField(verbose_name="关联动作ID", db_index=True)

    class Meta:
        verbose_name = "通知模板配置"
        verbose_name_plural = "通知模板配置"
        db_table = "alarm_notice_template"


class NoticeGroup(AbstractRecordModel):
    """
    通知组
    """

    name = models.CharField(max_length=128, verbose_name="通知组名称")
    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0, blank=True, db_index=True)

    # ['user#admin', 'group#bk_biz_tester', 'user#2', 'user3#']
    notice_receiver = JsonField(verbose_name="通知对象")
    # {1: ['mail', 'phone'], 2: [], 3: []}
    notice_way = JsonField(verbose_name="通知方式")
    webhook_url = models.CharField(verbose_name="回调地址", default="", max_length=1024)
    wxwork_group = JsonField(verbose_name="企业微信群", default={})

    message = models.TextField(verbose_name="说明/备注")
    source = models.CharField(verbose_name="来源系统", default=get_source_app_code, max_length=32)

    class Meta:
        verbose_name = "通知组配置"
        verbose_name_plural = "通知组配置"
        db_table = "alarm_notice_group"
        index_together = (("bk_biz_id", "source"),)

    @property
    def related_strategy(self):
        from .strategy import StrategyModel

        action_ids = (
            ActionNoticeMapping.objects.filter(notice_group_id=self.id).values_list("action_id", flat=True).distinct()
        )
        strategy_ids = Action.objects.filter(id__in=action_ids).values_list("strategy_id", flat=True).distinct()
        return StrategyModel.objects.filter(id__in=strategy_ids).count()

    @property
    def delete_allowed(self):
        return self.related_strategy == 0


class ActionNoticeMapping(AbstractRecordModel):
    """
    通知动作和通知组的关系（多对多）

    1. 一个通知动作，可以设置多个通知组
    2. 一个通知组可以应用到多个通知动作
    """

    action_id = models.IntegerField(verbose_name="关联动作ID", db_index=True)
    notice_group_id = models.IntegerField(verbose_name="关联通知组ID", db_index=True)

    class Meta:
        db_table = "alarm_action_notice_group_mapping"


class AnomalyRecord(Model):
    """
    异常记录表

    1. 经过检测算法判定后，生成异常记录
    2. 其它系统接入的异常记录
    """

    anomaly_id = models.CharField(verbose_name="异常ID", db_index=True, unique=True, max_length=255)
    source_time = models.DateTimeField(verbose_name="异常时间", db_index=True)
    create_time = models.DateTimeField(verbose_name="创建时间", auto_now_add=True, db_index=True)
    strategy_id = models.IntegerField(verbose_name="关联策略ID", db_index=True)
    origin_alarm = JsonField(verbose_name="原始的异常内容")
    count = models.IntegerField(verbose_name="异常汇总数量", default=1)
    event_id = models.CharField(verbose_name="关联事件ID", max_length=255, blank=True, default="", db_index=True)

    class Meta:
        verbose_name = "异常"
        verbose_name_plural = "异常"
        db_table = "alarm_anomaly_record"

    @property
    def anomaly_data(self):
        return self.origin_alarm["data"]


class Event(Model):
    """
    事件（已废弃）

    经过检测范围匹配，收敛等判断后，生成事件
    """

    class TargetKeyGenerator:
        Host = event_target.HostKeyGenerator
        ServiceInstance = event_target.ServiceInstanceKeyGenerator
        Topo = event_target.TopoKeyGenerator

    EVENT_LEVEL_FATAL = 1
    EVENT_LEVEL_WARNING = 2
    EVENT_LEVEL_REMIND = 3

    EVENT_LEVEL = (
        (EVENT_LEVEL_FATAL, _lazy("致命")),
        (EVENT_LEVEL_WARNING, _lazy("预警")),
        (EVENT_LEVEL_REMIND, _lazy("提醒")),
    )

    EVENT_LEVEL_COLOR = (
        (EVENT_LEVEL_FATAL, "#EA3636"),
        (EVENT_LEVEL_WARNING, "#FF9C01"),
        (EVENT_LEVEL_REMIND, "#FFDE3A"),
    )

    DEFAULT_END_TIME = datetime.datetime(1980, 1, 1, 8, tzinfo=pytz.UTC)

    class EventStatus:
        CLOSED = "CLOSED"  # 已关闭，对应数据表 10
        RECOVERED = "RECOVERED"  # 已恢复，对应数据表 20
        ABNORMAL = "ABNORMAL"  # 异常事件，对应数据表 30

    EVENT_STATUS = (
        (EventStatus.RECOVERED, _lazy("已修复")),
        (EventStatus.ABNORMAL, _lazy("异常中")),
        (EventStatus.CLOSED, _lazy("已关闭")),
    )
    create_time = models.DateTimeField(verbose_name="创建时间", auto_now_add=True)
    event_id = models.CharField(verbose_name="事件ID", db_index=True, unique=True, max_length=255)
    begin_time = models.DateTimeField(verbose_name="事件产生时间")
    # 恢复、关闭 都是结束
    end_time = models.DateTimeField(verbose_name="事件结束时间", default=DEFAULT_END_TIME)
    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0, blank=True)
    strategy_id = models.IntegerField(verbose_name="关联策略ID")
    origin_alarm = JsonField(verbose_name="原始的异常内容", default=None)
    origin_config = JsonField(verbose_name="告警策略原始配置", default=None)
    level = models.IntegerField(verbose_name="级别", choices=EVENT_LEVEL, default=0)
    status = EventStatusField(
        verbose_name="状态", choices=EVENT_STATUS, default=EventStatus.ABNORMAL
    )  # 异常中、已恢复、已失效
    is_ack = models.BooleanField(verbose_name="是否确认", default=False)
    p_event_id = models.CharField(
        verbose_name="父事件ID", default="", blank=True, max_length=255
    )  # 保留字段，给事件关联用
    is_shielded = models.BooleanField(verbose_name="是否处于屏蔽状态", default=False)
    shield_type = models.CharField(verbose_name="屏蔽类型", default="", blank=True, max_length=16)

    target_key = models.CharField(verbose_name="目标标识符", default="", blank=True, max_length=128)
    notify_status = models.IntegerField(verbose_name="通知状态", default=0)

    class Meta:
        verbose_name = "事件"
        verbose_name_plural = "事件"
        db_table = "alarm_event"
        index_together = (
            ("level", "end_time", "bk_biz_id", "status", "strategy_id", "notify_status"),
            ("end_time", "bk_biz_id", "status", "strategy_id", "notify_status"),
            ("target_key", "status", "end_time", "bk_biz_id", "level", "strategy_id"),
            ("notify_status", "status", "end_time", "bk_biz_id", "level", "strategy_id"),
        )

    def origin_strategy(self):
        return self.origin_config

    @cached_property
    def latest_anomaly_record(self):
        """
        获取最新的异常点
        :rtype: AnomalyRecord
        """
        try:
            return AnomalyRecord.objects.filter(event_id=self.event_id).latest("source_time")
        except AnomalyRecord.DoesNotExist:
            return None

    @cached_property
    def duration(self):
        """
        持续时间
        :rtype: datetime.timedelta
        """
        interval = self.origin_strategy["items"][0]["query_configs"][0].get("agg_interval", 60)

        if self.latest_anomaly_record:
            return self.latest_anomaly_record.source_time - self.begin_time + datetime.timedelta(seconds=interval)
        else:
            return datetime.timedelta(seconds=interval)

    @cached_property
    def anomaly_message(self):
        try:
            if self.latest_anomaly_record and str(self.level) in self.latest_anomaly_record.origin_alarm["anomaly"]:
                message = self.latest_anomaly_record.origin_alarm["anomaly"][str(self.level)]["anomaly_message"]
            else:
                message = self.origin_alarm["anomaly"][str(self.level)]["anomaly_message"]
        except KeyError:
            return "anomaly_message not found in {}".format(self.origin_alarm["anomaly"])
        return message

    @cached_property
    def level_name(self):
        """
        级别名称
        :rtype: str
        """
        for level_pair in self.EVENT_LEVEL:
            if level_pair[0] == self.level:
                return str(level_pair[1])
        return ""

    @cached_property
    def level_color(self):
        """
        级别名称
        :rtype: str
        """
        for level_pair in self.EVENT_LEVEL_COLOR:
            if level_pair[0] == self.level:
                return level_pair[1]
        return "#000000"

    @cached_property
    def is_no_data(self):
        return NO_DATA_TAG_DIMENSION in self.origin_alarm["data"]["dimensions"]


class EventAction(Model):
    """
    事件操作记录

    1. 事件产生
    2. 事件确认
    3. 事件恢复
    4. 事件关闭
    """

    class Operate:
        ACK = "ACK"
        ANOMALY_NOTICE = "ANOMALY_NOTICE"
        RECOVERY_NOTICE = "RECOVERY_NOTICE"
        CLOSE_NOTICE = "CLOSE_NOTICE"

        ANOMALY_PUSH = "ANOMALY_PUSH"
        RECOVERY_PUSH = "RECOVERY_PUSH"
        CLOSE_PUSH = "CLOSE_PUSH"

        CREATE = "CREATE"
        CONVERGE = "CONVERGE"
        RECOVER = "RECOVER"
        CLOSE = "CLOSE"
        CREATE_ORDER = "CREATE_ORDER"
        MESSAGE_QUEUE = "MESSAGE_QUEUE"

    OPERATE = (
        (Operate.ACK, _lazy("告警确认")),
        (Operate.ANOMALY_NOTICE, _lazy("告警通知")),
        (Operate.RECOVERY_NOTICE, _lazy("恢复通知")),
        (Operate.CREATE, _lazy("触发告警")),
        (Operate.CONVERGE, _lazy("告警收敛")),
        (Operate.RECOVER, _lazy("告警恢复")),
        (Operate.CLOSE, _lazy("告警关闭")),
        (Operate.CREATE_ORDER, _lazy("生成工单")),
        (Operate.MESSAGE_QUEUE, _lazy("消息队列")),
    )

    MESSAGE_QUEUE_OPERATE_TYPE_MAPPING = {
        "anomaly": Operate.ANOMALY_PUSH,
        "recovery": Operate.RECOVERY_PUSH,
        "close": Operate.CLOSE_PUSH,
    }

    ACTION_TYPE_MAPPING = {
        "notice": {
            "anomaly": Operate.ANOMALY_NOTICE,
            "recovery": Operate.RECOVERY_NOTICE,
            "close": Operate.CLOSE_NOTICE,
        },
    }

    class Status:
        RUNNING = "RUNNING"
        SUCCESS = "SUCCESS"
        PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
        FAILED = "FAILED"
        SHIELDED = "SHIELDED"

    STATUS = (
        (Status.RUNNING, _lazy("运行中")),
        (Status.SUCCESS, _lazy("成功")),
        (Status.PARTIAL_SUCCESS, _lazy("部分成功")),
        (Status.FAILED, _lazy("失败")),
        (Status.SHIELDED, _lazy("屏蔽")),
    )

    create_time = models.DateTimeField(verbose_name="操作时间", auto_now_add=True)
    username = models.CharField(verbose_name="操作人", max_length=32, default="", blank=True, db_index=True)
    # 产生、确认、恢复、关闭、生成工单、发送通知、自愈处理
    operate = models.CharField(verbose_name="操作", choices=OPERATE, max_length=32)
    message = models.TextField(verbose_name="事件确认评论", default="")
    extend_info = JsonField(verbose_name="拓展信息", default={})
    status = models.CharField(max_length=32, verbose_name="操作状态", choices=STATUS)
    event_id = models.CharField(verbose_name="关联事件ID", db_index=True, max_length=255)

    class Meta:
        verbose_name = "事件动作日志"
        verbose_name_plural = "事件动作日志"
        db_table = "alarm_event_action"
        index_together = (("create_time", "operate"),)

    @property
    def shield_log(self):
        """
        屏蔽的信息会记录在extend_info["shield"]中
        :return: {
            "type": "saas_config",
            "detail": {}
        }
        """
        if self.status != self.Status.SHIELDED:
            return {}

        if isinstance(self.extend_info.get("shield"), str):
            # 兼容旧版字段
            data = {"type": ShieldType.SAAS_CONFIG, "detail": self.extend_info["shield"]}
        else:
            data = self.extend_info.get("shield", {})

        return data

    @cached_property
    def event(self):
        events = Event.objects.filter(event_id=self.event_id)
        if events:
            return events[0]


class EventStats(Model):
    """
    事件统计表(TODO)
    """

    class Meta:
        db_table = "alarm_event_stats"

    pass


class Alert(Model):
    """
    告警通知表
    """

    # alert_id = models.AutoField(verbose_name='告警ID')
    ALERT_STATUS = (
        ("RUNNING", _lazy("通知中")),
        ("SUCCESS", _lazy("通知成功")),
        ("FAILED", _lazy("通知失败")),
    )

    method = models.CharField(verbose_name="通知方式", max_length=32)
    username = models.CharField(verbose_name="通知接收人", max_length=32, db_index=True)
    role = models.CharField(verbose_name="通知接收人角色", max_length=32, default="", blank=True)
    create_time = models.DateTimeField(verbose_name="通知时间", auto_now_add=True, db_index=True)

    status = models.CharField(verbose_name="状态", choices=ALERT_STATUS, max_length=32)  # 1.已通知 2.已屏蔽 3.通知失败
    message = models.TextField(verbose_name="(失败|屏蔽)原因")
    action_id = models.IntegerField(verbose_name="动作ID", db_index=True)
    event_id = models.CharField(verbose_name="关联事件ID", db_index=True, max_length=255)
    alert_collect_id = models.IntegerField(verbose_name="汇总ID", db_index=True)

    class Meta:
        verbose_name = "通知动作"
        verbose_name_plural = "通知动作"
        db_table = "alarm_alert"


class AlertCollect(Model):
    """
    告警通知汇总
    """

    COLLECT_TYPE = (
        ("DIMENSION", _lazy("同维度汇总")),
        ("STRATEGY", _lazy("同策略汇总")),
        ("MULTI_STRATEGY", _lazy("同业务汇总")),
    )

    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0, blank=True, db_index=True)
    collect_key = models.TextField(verbose_name="汇总key")
    collect_type = models.CharField(verbose_name="汇总类型", choices=COLLECT_TYPE, default="DIMENSION", max_length=32)
    message = models.CharField(verbose_name="汇总原因", max_length=512)
    collect_time = models.DateTimeField(verbose_name="汇总时间", auto_now_add=True)
    extend_info = JsonField(verbose_name="其他信息", default={})

    class Meta:
        verbose_name = "汇总记录"
        verbose_name_plural = "汇总记录"
        db_table = "alarm_alert_collect"


class Shield(AbstractRecordModel):
    """
    告警屏蔽表
    """

    SHIELD_CATEGORY = (
        ("scope", _lazy("范围屏蔽")),
        ("strategy", _lazy("策略屏蔽")),
        ("event", _lazy("事件屏蔽")),
        ("alert", _lazy("告警屏蔽")),
        ("dimension", _lazy("维度屏蔽")),
    )

    SCOPE_TYPE = (
        ("instance", _lazy("实例")),
        ("ip", "IP"),
        ("node", _lazy("节点")),
        ("biz", _lazy("业务")),
        ("dynamic_group", _lazy("动态分组")),
    )

    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0, blank=True, db_index=True)
    category = models.CharField(verbose_name="屏蔽类型", choices=SHIELD_CATEGORY, max_length=32)
    scope_type = models.CharField(verbose_name="屏蔽范围类型", choices=SCOPE_TYPE, max_length=32)
    content = models.TextField(verbose_name="屏蔽内容快照")

    begin_time = models.DateTimeField(verbose_name="屏蔽开始时间")
    end_time = models.DateTimeField(verbose_name="屏蔽结束时间")
    failure_time = models.DateTimeField(verbose_name="屏蔽失效时间")

    dimension_config: dict[str, Any] = JsonField(verbose_name="屏蔽维度")  # type: ignore
    cycle_config = JsonField(verbose_name="屏蔽周期")
    notice_config = JsonField(verbose_name="通知配置")

    description = models.TextField(verbose_name="屏蔽原因")

    is_quick = models.BooleanField(verbose_name="是否是快捷屏蔽", default=False)
    source = models.CharField(verbose_name="来源系统", default=get_source_app_code, max_length=32)
    label = models.CharField(verbose_name="标签", max_length=255, default="", blank=True, db_index=True)

    class Meta:
        verbose_name = "屏蔽配置"
        verbose_name_plural = "屏蔽配置"
        db_table = "alarm_shield"
        index_together = (("bk_biz_id", "source"), ("begin_time", "bk_biz_id"))

    @property
    def status(self):
        if not self.is_enabled:
            return ShieldStatus.REMOVED

        if time_tools.now() > self.end_time:
            return ShieldStatus.EXPIRED

        return ShieldStatus.SHIELDED


class CacheNode(Model):
    """
    后台缓存节点
    """

    CACHE_TYPE = (
        ("RedisCache", _("单例")),
        ("SentinelRedisCache", "sentinel"),
    )
    cluster_name = models.CharField(verbose_name="集群名称", max_length=128, default="default")
    cache_type = models.CharField(verbose_name="节点类型", choices=CACHE_TYPE, max_length=32)
    host = models.CharField(verbose_name="host", max_length=128)
    port = models.IntegerField(verbose_name="port")
    password = SymmetricTextField("密码", default="")
    connection_kwargs = JsonField("额外连接信息")
    is_enable = models.BooleanField("是否启用", default=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    is_default = models.BooleanField("默认节点", default=False)
    node_alias = models.CharField(verbose_name="节点别名", max_length=128, default="")

    class Meta:
        verbose_name = "后台缓存节点"
        verbose_name_plural = "后台缓存节点"
        db_table = "alarm_cachenode"

    @classmethod
    def refresh_from_settings(cls):
        node = cls.default_node()
        connection_kwargs = {
            "master_name": getattr(settings, "REDIS_MASTER_NAME", "mymaster"),
            "sentinel_password": getattr(settings, "REDIS_SENTINEL_PASS", ""),
        }
        node.__dict__.update(
            dict(
                cache_type=settings.CACHE_BACKEND_TYPE,
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWD,
                connection_kwargs=connection_kwargs if settings.CACHE_BACKEND_TYPE == "SentinelRedisCache" else {},
            )
        )
        node.save()

    @classmethod
    def default_node(cls):
        from alarm_backends.core.cluster import get_cluster

        global mem_cache

        cluster_name = get_cluster().name

        connection_kwargs = {
            "master_name": getattr(settings, "REDIS_MASTER_NAME", "mymaster"),
            "sentinel_password": getattr(settings, "REDIS_SENTINEL_PASS", ""),
        }
        # 在首次部署阶段，可能存在并发情况，由于没有唯一性约束，可能会导致重复默认记录
        default_node_count = mem_cache.get("default_node_count")
        if not default_node_count:
            # 获取当前db实际情况
            default_node_count = cls.objects.filter(is_default=True, cluster_name=cluster_name).count()
            if default_node_count > 0:
                mem_cache.set("default_node_count", default_node_count)
            else:
                # 新部署或首次升级该版本，稍微随机等待一下
                time.sleep(random.random())

        try:
            node, is_new_node = cls.objects.get_or_create(
                is_default=True,
                cluster_name=cluster_name,
                defaults=dict(
                    cache_type=settings.CACHE_BACKEND_TYPE,
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    password=settings.REDIS_PASSWD,
                    connection_kwargs=connection_kwargs if settings.CACHE_BACKEND_TYPE == "SentinelRedisCache" else {},
                ),
            )
        except cls.MultipleObjectsReturned:
            # 如果存在多个默认节点，则该次创建必然不是新节点
            is_new_node = False
            node = False

        nodes = cls.objects.filter(is_default=True, cluster_name=cluster_name)
        if len(nodes) > 1:
            # 如果存在多个默认节点，则删除多余的默认节点
            cls.objects.filter(is_default=True, cluster_name=cluster_name).exclude(id=nodes[0].id).delete()
            # 如果节点不是第一个节点，则其必然不是新节点
            if is_new_node and node:
                is_new_node = node.id == nodes[0].id

        # 只有新节点才需要创建路由
        if is_new_node or CacheRouter.objects.filter(cluster_name=cluster_name).count() == 0:
            CacheRouter.add_router(node)
        return node

    def __str__(self):
        node_id = f"[{self.node_alias}]{self.cache_type}-{self.host}:{self.port}"
        if self.cache_type == "SentinelRedisCache":
            node_id += f"-{self.connection_kwargs.get('master_name')}"
        return node_id


class CacheRouter(Model):
    """
    缓存路由
    100: nodeA
    200: nodeB
    1000: nodeC
    2000: nodeA
    inf: nodeC (默认记录，当开启cache集群化时自动创建这条记录)
    =====
    0-99： nodeA
    100-199： NodeB
    200->999: nodeC
    1000->1999: NodeA
    2000->inf: nodeC
    """

    cluster_name = models.CharField(verbose_name="集群名称", max_length=128, default="default")
    node = models.ForeignKey(CacheNode, verbose_name="缓存节点", related_name="routers", on_delete=models.CASCADE)
    strategy_score = models.IntegerField("策略id路由分组", db_index=True)

    class Meta:
        verbose_name = "后台缓存路由"
        verbose_name_plural = "后台缓存路由"
        db_table = "alarm_cacherouter"

    @classmethod
    def list_router(cls):
        from alarm_backends.core.cluster import get_cluster

        cluster_name = get_cluster().name
        query = cls.objects.filter(cluster_name=cluster_name).order_by("strategy_score")
        routers = list(query.values("id", "strategy_score", "node_id"))
        for router in routers:
            router["node_name"] = CacheNode.objects.get(id=router["node_id"]).node_alias
        return routers

    @classmethod
    def add_router(cls, node, score_floor=0, score_ceil=2**20):
        from alarm_backends.core.cluster import get_cluster

        cluster_name = get_cluster().name
        query = cls.objects.filter(cluster_name=cluster_name)

        # print(f"先找到{score_floor}以下的区间和找到{score_ceil}以上的区间")
        floor_lower_router = query.filter(strategy_score__lt=score_floor).order_by("-strategy_score").first()
        floor_upper_router = query.filter(strategy_score__gte=score_floor).order_by("strategy_score").first()
        if not floor_lower_router and not floor_upper_router:
            cls.objects.create(node=node, strategy_score=score_ceil + 1, cluster_name=cluster_name)
            return
        # floor_lower_score = floor_lower_router.strategy_score if floor_lower_router else 0
        # print(f"分割{floor_lower_score}-{score_floor}和{score_floor}-{floor_upper_router.strategy_score}")
        cls.objects.get_or_create(node=floor_upper_router.node, strategy_score=score_floor, cluster_name=cluster_name)
        if floor_upper_router.node.id == node.id:
            # print(f"0-{score_floor}和{score_floor}-{floor_upper_router.strategy_score}区间指向相同的集群，合并区间")
            query.filter(strategy_score=score_floor).delete()

        # print(f"清理{score_floor} 和 {score_ceil} 之间的区间")
        query.filter(strategy_score__gt=score_floor, strategy_score__lte=score_ceil + 1).delete()

        # print(f"基于{score_ceil} 创建新区间")

        ceil_upper_router = query.filter(strategy_score__gte=score_floor).order_by("strategy_score").first()
        if ceil_upper_router and ceil_upper_router.node.id == node.id:
            # print(f"{score_ceil}-{ceil_upper_router.strategy_score}和{score_floor}-{score_ceil}指向相同集群，合并区间")
            return
        cls.objects.create(node=node, strategy_score=score_ceil + 1, cluster_name=cluster_name)
        cls.optimize_router()

    @classmethod
    def optimize_router(cls):
        from alarm_backends.core.cluster import get_cluster

        cluster_name = get_cluster().name
        # 优化表记录，相邻区间指向相同的集群的记录将合并
        with atomic(getattr(settings, "BACKEND_DATABASE_NAME", "monitor_api")):
            to_be_remove = []
            routers = cls.objects.filter(cluster_name=cluster_name).order_by("-strategy_score")
            now_router = tuple()
            for router in routers:
                if not now_router:
                    now_router = (router.strategy_score, router.node.id)
                    continue
                if router.node.id == now_router[1]:
                    to_be_remove.append(router.id)
                else:
                    now_router = (router.strategy_score, router.node.id)
            # print(to_be_remove)
            cls.objects.filter(cluster_name=cluster_name, id__in=to_be_remove).delete()


class ReportItems(AbstractRecordModel):
    """
    订阅报表
    """

    bk_tenant_id = models.CharField(verbose_name="租户ID", max_length=128, default=DEFAULT_TENANT_ID)
    mail_title = models.CharField(verbose_name="邮件标题", max_length=512)
    channels = models.JSONField(verbose_name="订阅渠道", default=list)
    receivers = models.JSONField(verbose_name="接收者", default=dict)
    managers = models.JSONField(verbose_name="管理员", default=dict)
    frequency = models.JSONField(verbose_name="发送频率", default=dict)
    last_send_time = models.DateTimeField(verbose_name="发送时间", null=True)
    is_link_enabled = models.BooleanField(verbose_name="是否发送链接", default=True)

    class Channel:
        # 订阅渠道
        EMAIL = "email"
        WXBOT = "wxbot"
        USER = "user"

        CHANNEL_DICT = {EMAIL: _lazy("外部邮件"), WXBOT: _lazy("企业微信机器人"), USER: _lazy("内部用户")}

    class HourFrequencyTime:
        HALF_HOUR = {"minutes": ["00", "30"]}
        HOUR = {"minutes": ["00"]}
        HOUR_2 = {"hours": ["00", "02", "04", "06", "08", "10", "12", "14", "16", "18", "20", "22"]}
        HOUR_6 = {"hours": ["00", "06", "12", "18"]}
        HOUR_12 = {"hours": ["09", "21"]}

        TIME_CONFIG = {"0.5": HALF_HOUR, "1": HOUR, "2": HOUR_2, "6": HOUR_6, "12": HOUR_12}

    @property
    def format_managers(self):
        """
        获取所有管理员
        """
        managers = []
        groups_data = api.monitor.group_list()
        for manager in self.managers:
            if manager["type"] == StaffChoice.user and manager.get("id"):
                managers.append(manager["id"])
            elif manager["type"] == StaffChoice.group and manager.get("id") in groups_data:
                managers.extend(groups_data[manager["id"]])
            else:
                continue
        return list(set(managers))


class ReportContents(Model):
    """
    报表内容
    """

    bk_tenant_id = models.CharField(verbose_name="租户ID", max_length=128, default=DEFAULT_TENANT_ID)
    report_item = models.IntegerField(verbose_name="订阅报表ID", db_index=True)
    content_title = models.CharField(verbose_name="内容标题", max_length=512)
    content_details = models.TextField(verbose_name="内容说明", max_length=512)
    row_pictures_num = models.IntegerField(verbose_name="一行几幅图", default=0)
    graphs = models.JSONField(verbose_name="图表Panels信息", default=dict)
    width = models.IntegerField(verbose_name="单图宽度", null=True, blank=True)
    height = models.IntegerField(verbose_name="单图高度", null=True, blank=True)


class ReportStatus(Model):
    """
    报表发送状态
    """

    bk_tenant_id = models.CharField(verbose_name="租户ID", max_length=128, default=DEFAULT_TENANT_ID)
    report_item = models.IntegerField(verbose_name="订阅报表ID", db_index=True)
    mail_title = models.CharField(verbose_name="邮件标题", max_length=512)
    create_time = models.DateTimeField(verbose_name="发送时间", db_index=True)
    details = models.JSONField(verbose_name="发送详情", default=dict)
    is_success = models.BooleanField(verbose_name="是否成功", default=False)
