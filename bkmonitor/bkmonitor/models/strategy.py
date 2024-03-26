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
from datetime import datetime

import pytz
from django.contrib import admin
from django.db import models
from django.db.models import Model, Q
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _lazy

from bkmonitor.middlewares.source import get_source_app_code
from bkmonitor.utils import time_tools
from bkmonitor.utils.model_manager import AbstractRecordModel
from bkmonitor.utils.range.period import TimeMatchByDay
from bkmonitor.utils.request import get_source_app
from constants.action import NoticeWay
from constants.common import DutyGroupType, SourceApp
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import resource

__all__ = [
    "StrategyModel",
    "ItemModel",
    "DetectModel",
    "AlgorithmModel",
    "QueryConfigModel",
    "StrategyLabel",
    "StrategyHistoryModel",
    "StrategyModelAdmin",
    "StrategyHistoryModelAdmin",
    "ItemModelAdmin",
    "DetectModelAdmin",
    "AlgorithmModelAdmin",
    "QueryConfigModelAdmin",
    "MetricMappingConfigModel",
    "DutyPlan",
    "DutyArrange",
    "UserGroup",
    "DutyRule",
    "DutyRuleSnap",
    "DutyRuleRelation",
    "DutyPlanSendRecord",
    "DutyArrangeSnap",
    "DefaultStrategyBizAccessModel",
]


def default_target():
    return [[]]


def no_data_config():
    return {"is_enabled": True, "continuous": 5, "agg_dimension": []}


def default_work_days():
    return []


class ItemModelAdmin(admin.ModelAdmin):
    """
    监控项表展示
    """

    list_display = ("id", "strategy_id", "name", "expression", "no_data_config")
    search_fields = ("expression", "name", "origin_sql")


class ItemModel(Model):
    """
    监控项模型
    """

    strategy_id = models.IntegerField("关联策略ID", db_index=True)
    name = models.CharField("监控项名称", max_length=256)
    expression = models.TextField("计算公式")
    functions = models.JSONField("计算函数", default=list)
    origin_sql = models.TextField("原始查询语句")
    no_data_config = models.JSONField("无数据配置", default=no_data_config)
    target = models.JSONField("监控目标", default=default_target)
    meta = models.JSONField("查询配置元数据", default=list)
    metric_type = models.CharField("指标类型", max_length=32, default="", blank=True)

    class Meta:
        verbose_name = "监控项配置V2"
        verbose_name_plural = "监控项配置V2"
        db_table = "alarm_item_v2"


class DetectModelAdmin(admin.ModelAdmin):
    """
    配置表展示
    """

    list_display = ("strategy_id", "level", "connector", "expression", "trigger_config", "recovery_config")
    search_fields = ("expression",)
    list_filter = ("level", "connector")


class DetectModel(Model):
    """
    检测配置模型
    """

    strategy_id = models.IntegerField("关联策略ID", db_index=True)
    level = models.IntegerField(
        "告警级别",
        default=3,
        choices=(
            (1, _lazy("致命")),
            (2, _lazy("预警")),
            (3, _lazy("提醒")),
        ),
    )
    expression = models.TextField("计算公式", default="")
    trigger_config = models.JSONField("触发条件配置", default=dict)
    recovery_config = models.JSONField("恢复条件配置", default=dict)
    connector = models.CharField("同级别算法连接符", choices=(("and", "AND"), ("or", "OR")), max_length=4, default="and")

    class Meta:
        verbose_name = "检测配置V2"
        verbose_name_plural = "检测配置V2"
        db_table = "alarm_detect_v2"


class AlgorithmModelAdmin(admin.ModelAdmin):
    """
    算法配置表展示
    """

    list_display = ("strategy_id", "item_id", "level", "type", "unit_prefix")
    search_fields = ("unit_prefix",)
    list_filter = ("level", "type")


class AlgorithmModel(Model):
    """
    检测算法模型
    常用查询：
        1. 基于监控项ID
        2. 基于算法类型
    """

    class AlgorithmChoices(object):
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
        TimeSeriesForecasting = "TimeSeriesForecasting"
        AbnormalCluster = "AbnormalCluster"
        MultivariateAnomalyDetection = "MultivariateAnomalyDetection"

    AIOPS_ALGORITHMS = [
        AlgorithmChoices.IntelligentDetect,
        AlgorithmChoices.TimeSeriesForecasting,
        AlgorithmChoices.AbnormalCluster,
        AlgorithmChoices.MultivariateAnomalyDetection,
    ]

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
        (AlgorithmChoices.TimeSeriesForecasting, _lazy("时序预测算法")),
        (AlgorithmChoices.AbnormalCluster, _lazy("离群检测算法")),
        (AlgorithmChoices.MultivariateAnomalyDetection, _lazy("多指标异常检测算法")),
    )

    strategy_id = models.IntegerField("关联策略ID", db_index=True)
    item_id = models.IntegerField("关联监控项ID", db_index=True)
    level = models.IntegerField(
        "告警级别",
        default=3,
        choices=(
            (1, _lazy("致命")),
            (2, _lazy("预警")),
            (3, _lazy("提醒")),
        ),
    )
    type = models.CharField("算法类型", max_length=64, choices=ALGORITHM_CHOICES, db_index=True)
    unit_prefix = models.CharField("算法单位前缀", max_length=32, default="", blank=True)
    config = models.JSONField("算法配置", default=dict)

    class Meta:
        verbose_name = "检测算法配置V2"
        verbose_name_plural = "检测算法配置V2"
        db_table = "alarm_algorithm_v2"


class QueryConfigModelAdmin(admin.ModelAdmin):
    """
    查询配置表展示
    """

    list_display = ("strategy_id", "item_id", "alias", "metric_id", "data_source_label", "data_type_label")
    search_fields = ("metric_id", "alias")
    list_filter = ("data_source_label", "data_type_label")


class QueryConfigModel(Model):
    """
    查询配置基类
    """

    strategy_id = models.IntegerField("关联策略ID", db_index=True)
    item_id = models.IntegerField("关联监控项ID", db_index=True)
    alias = models.CharField("别名", max_length=12)
    data_source_label = models.CharField("数据来源标签", max_length=32)
    data_type_label = models.CharField("数据类型标签", max_length=32)
    metric_id = models.CharField("指标ID", max_length=128)
    config = models.JSONField("查询配置", default=dict)

    class Meta:
        verbose_name = "查询配置表V2"
        verbose_name_plural = "查询配置表V2"
        db_table = "alarm_query_config_v2"
        index_together = [
            ("data_source_label", "data_type_label"),
        ]

    def to_obj(self):
        from bkmonitor.strategy.new_strategy import QueryConfig

        return QueryConfig.from_models([self])[0]

    @classmethod
    def get_strategies_by_source_app(cls, source_app=None):
        """
        根据source_app来源获取对应的策略ID
        :param source_app:来源app
        :return:
        """
        source_app = source_app or get_source_app()
        queryset = cls.objects.all()

        if source_app == SourceApp.FTA:
            return set(
                queryset.filter(Q(data_type_label=DataTypeLabel.ALERT) | Q(data_source_label=DataSourceLabel.BK_FTA))
                .values_list("strategy_id", flat=True)
                .distinct()
            )

        return set(queryset.values_list("strategy_id", flat=True).distinct())


class StrategyLabel(Model):
    """
    策略全局标签
    tag_name： /a/b/c/  - 3级标签 /a/b/
    全局标签：bk_biz_id: 0 , strategy_id: 0
    """

    label_name = models.CharField(max_length=128, verbose_name="策略名称")
    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0, blank=True, db_index=True)
    strategy_id = models.IntegerField(verbose_name="策略ID", default=0, blank=True)

    class Meta:
        verbose_name = "策略标签"
        verbose_name_plural = "策略标签"
        db_table = "alarm_strategy_label"
        index_together = (("label_name", "strategy_id"),)

    @classmethod
    def get_label_dict(cls, strategy_id=None):
        # global mem_cache
        label_dict = {}
        queryset = cls.objects
        if strategy_id is not None:
            queryset = queryset.filter(strategy_id=strategy_id)
        for strategy_id, label_name in queryset.values_list("strategy_id", "label_name"):
            label_dict.setdefault(strategy_id, []).append(label_name.strip("/"))
        return label_dict

    @classmethod
    def save_strategy_label(cls, bk_biz_id, strategy_id, labels):
        resource.strategies.delete_strategy_label(strategy_id=strategy_id)
        for label in labels:
            resource.strategies.strategy_label(label_name=label, strategy_id=strategy_id, bk_biz_id=bk_biz_id)


class StrategyModelAdmin(admin.ModelAdmin):
    """
    策略表展示
    """

    list_display = ("id", "name", "bk_biz_id", "scenario", "source", "type", "is_enabled")
    search_fields = ("name", "create_user", "bk_biz_id", "update_user")
    list_filter = ("source", "scenario", "type", "is_enabled")


class StrategyModel(Model):
    """
    策略表
    """

    class StrategyType:
        Monitor = "monitor"
        FTASolution = "fta"

        Choices = ((Monitor, _lazy("监控")), (FTASolution, _lazy("故障自愈")))

    class InvalidType:
        NONE = ""
        INVALID_RELATED_STRATEGY = "invalid_related_strategy"
        DELETED_RELATED_STRATEGY = "deleted_related_strategy"
        INVALID_UNIT = "invalid_unit"
        INVALID_TARGET = "invalid_target"
        INVALID_METRIC = "invalid_metric"
        INVALID_BIZ = "invalid_biz"

        Choices = [
            (NONE, NONE),
            (INVALID_RELATED_STRATEGY, _lazy("关联的策略已失效")),
            (DELETED_RELATED_STRATEGY, _lazy("关联的策略已删除")),
            (INVALID_UNIT, _lazy("指标和检测算法的单位类型不一致")),
            (INVALID_TARGET, _lazy("监控目标全部失效")),
            (INVALID_METRIC, _lazy("监控指标不存在")),
            (INVALID_BIZ, _lazy("策略所属业务不存在")),
        ]

    name = models.CharField("策略名称", max_length=128, db_index=True)
    bk_biz_id = models.IntegerField("业务ID", db_index=True)
    source = models.CharField("来源系统", default=get_source_app_code, max_length=32)
    scenario = models.CharField("监控场景", max_length=32)
    type = models.CharField(
        "策略类型",
        max_length=12,
        db_index=True,
        choices=StrategyType.Choices,
    )
    is_enabled = models.BooleanField("是否启用", default=True)
    is_invalid = models.BooleanField("是否失效", default=False)
    invalid_type = models.CharField(
        "失效类型", max_length=32, blank=True, default=InvalidType.NONE, choices=InvalidType.Choices
    )
    create_user = models.CharField("创建人", max_length=32, default="")
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    update_user = models.CharField("最后修改人", max_length=32, default="")
    update_time = models.DateTimeField("最后修改时间", auto_now=True)

    app = models.CharField("所属应用", max_length=128, default="", blank=True, null=True)
    path = models.CharField("资源路径", max_length=128, default="", blank=True, null=True)
    hash = models.CharField("原始配置摘要", max_length=64, default="", blank=True, null=True)
    snippet = models.TextField("配置片段", default="", blank=True, null=True)

    priority = models.IntegerField("优先级", null=True)
    # 在配置优先级的情况下，去除条件，根据查询配置生成优先级分组key
    priority_group_key = models.CharField("优先级分组", max_length=64, default=None, blank=True, null=True)

    class Meta:
        verbose_name = "策略配置V2"
        verbose_name_plural = "策略配置V2"
        db_table = "alarm_strategy_v2"
        index_together = (("is_enabled", "bk_biz_id", "scenario"),)

    @property
    def labels(self):
        # global mem_cache
        # labels = mem_cache.get(self.id)
        # if labels is None:
        labels = StrategyLabel.get_label_dict(self.id).get(self.id)
        return labels or []

    @property
    def target_type(self):
        from constants.strategy import DataTarget
        from monitor_web.models import DataTargetMapping

        data_target_map = dict(
            [(DataTarget.HOST_TARGET, "HOST"), (DataTarget.SERVICE_TARGET, "SERVICE"), (DataTarget.NONE_TARGET, None)]
        )
        result_table_label = self.scenario
        item_instance = QueryConfigModel.objects.filter(strategy_id=self.id).first()
        target_type = DataTargetMapping().get_data_target(
            result_table_label, item_instance.data_source_label, item_instance.data_type_label
        )
        return data_target_map[target_type]


class StrategyHistoryModel(Model):
    """
    策略历史表
    """

    strategy_id = models.IntegerField("关联策略ID", db_index=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)
    create_user = models.CharField("创建者", max_length=32)
    content = models.JSONField("保存内容", default=dict)
    operate = models.CharField(
        "操作",
        choices=(
            ("delete", _lazy("删除")),
            ("create", _lazy("创建")),
            ("update", _lazy("更新")),
        ),
        db_index=True,
        max_length=12,
    )
    status = models.BooleanField("操作状态", default=False)
    message = models.TextField("错误信息", default="", blank=True)

    class Meta:
        verbose_name = "策略配置操作历史"
        verbose_name_plural = "策略配置操作历史"
        db_table = "alarm_strategy_history"
        ordering = ("-create_time",)


class StrategyHistoryModelAdmin(admin.ModelAdmin):
    """
    策略历史表展示
    """

    list_display = ("operate", "strategy_id", "create_user", "status", "create_time")
    search_fields = ("strategy_id", "create_user")
    list_filter = ("operate", "status")


class UserGroup(AbstractRecordModel):
    """
    告警处理组
    """

    name = models.CharField(max_length=128, verbose_name="用户组名称")
    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0, blank=True, db_index=True)
    timezone = models.CharField(verbose_name="时区", default="Asia/Shanghai", max_length=32)

    desc = models.TextField(verbose_name="说明/备注")
    source = models.CharField(verbose_name="来源系统", default=get_source_app_code, max_length=32)
    need_duty = models.BooleanField(verbose_name="是否需要轮值", default=False)
    channels = models.JSONField("告警通知渠道配置", default=list)

    # 机器人通知提醒人员 all 表示当前组的人员
    mention_list = models.JSONField("告警提醒人", default=list)

    # mention_type 0 代表是默认，1代表是用户改动过的
    mention_type = models.IntegerField("提醒类型", default=0)

    alert_notice = models.JSONField("告警通知配置", default=list)
    action_notice = models.JSONField("执行通知配置", default=list)
    duty_notice = models.JSONField("轮值通知配置", default=dict)
    webhook_action_id = models.IntegerField("回调套餐ID", default=0)

    # 对应的轮值规则， need_duty为True的情况下必填
    duty_rules = models.JSONField("轮值规则", default=list)

    app = models.CharField("所属应用", max_length=128, default="", blank=True, null=True)
    path = models.CharField("资源路径", max_length=128, default="", blank=True, null=True)
    hash = models.CharField("原始配置摘要", max_length=64, default="", blank=True, null=True)
    snippet = models.TextField("配置片段", default="", blank=True, null=True)

    class Meta:
        verbose_name = "告警处理组配置"
        verbose_name_plural = "告警处理组配置"
        db_table = "user_group"
        index_together = (("bk_biz_id", "source"),)
        ordering = ("-update_time",)

    @cached_property
    def duty_arranges(self):
        return DutyArrange.objects.filter(user_group_id=self.id).order_by("order")

    @cached_property
    def duty_plans(self):
        """
        轮值安排
        """
        valid_plans = []
        for plan in DutyPlan.objects.filter(user_group_id=self.id, is_effective=1).order_by("id"):
            valid_work_times = [
                work_time for work_time in plan.work_times if f'{work_time["start_time"]}:00' < plan.finished_time
            ]
            if valid_work_times:
                plan.work_times = valid_work_times
                plan.start_time = min([work_time["start_time"] for work_time in plan.work_times])
                work_finished_time = max([work_time["end_time"] for work_time in plan.work_times])
                # plan的结束时间，以工作时间和当前排班结束时间的最小值为准
                plan_finish_time = plan.finished_time[:-3]
                plan.finished_time = min(work_finished_time, plan_finish_time)
                valid_plans.append(plan)
        return valid_plans

    @staticmethod
    def translate_notice_ways(notify_config):
        """
        做通知方式的数据结构切换
        """
        if notify_config.get("notice_ways"):
            # 已经存在的数据，表示为新版本接口存储
            return notify_config
        # 不存在的话为老数据
        notify_config["notice_ways"] = []
        for notice_way in set(notify_config["type"]):
            # 历史数据存在多个相同type的key的情况
            notice_way_config = {"name": notice_way}
            if NoticeWay.WX_BOT == notice_way:
                notice_way_config["receivers"] = notify_config["chatid"].split(",")
            notify_config["notice_ways"].append(notice_way_config)
        return notify_config

    @staticmethod
    def clean_notice_ways(notify_config, notice_way="weixin", replace_way="rtx"):
        """
        指定通知方式清理
        """
        translated_config = UserGroup.translate_notice_ways(notify_config)
        old_ways = {n["name"] for n in translated_config["notice_ways"]}
        if not old_ways:
            return notify_config

        if notice_way in old_ways:
            if replace_way:
                old_ways.add(replace_way)
            old_ways.remove(notice_way)
        # 不存在的话为老数据
        notify_config["notice_ways"] = []
        for notice_way in old_ways:
            # 历史数据存在多个相同type的key的情况
            notice_way_config = {"name": notice_way}
            if NoticeWay.WX_BOT == notice_way:
                notice_way_config["receivers"] = notify_config["chatid"].split(",")
            notify_config["notice_ways"].append(notice_way_config)
        notify_config["type"] = list(old_ways)
        return notify_config

    @property
    def tz_info(self):
        """
        用户组时区信息
        """
        try:
            return pytz.timezone(self.timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            return pytz.timezone("Asia/Shanghai")


class DutyRule(AbstractRecordModel):
    """
    轮值规则
    """

    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0, blank=True, db_index=True)
    name = models.CharField("轮值规则名称", max_length=128)
    enabled = models.BooleanField("是否开启", default=False)
    category = models.CharField(
        "轮值类型",
        choices=(
            ("regular", _lazy("常规值班")),
            ("handoff", _lazy("交替轮值")),
        ),
        default="regular",
        max_length=64,
    )
    labels = models.JSONField("标签", default=list)

    # 配置生效时间, 有时区控制，所以存为charfield
    effective_time = models.CharField("配置生效时间", max_length=32, null=True, db_index=True)
    end_time = models.CharField("配置截止时间", null=True, max_length=32, blank=True, db_index=True)
    hash = models.CharField("原始配置摘要", max_length=64, default="", blank=True, null=True)

    app = models.CharField("所属应用", max_length=128, default="", blank=True, null=True)
    path = models.CharField("资源路径", max_length=128, default="", blank=True, null=True)
    code_hash = models.CharField("配置摘要(ascode)", max_length=64, default="", blank=True, null=True)
    snippet = models.TextField("配置片段", default="", blank=True, null=True)

    class Meta:
        verbose_name = "轮值规则"
        verbose_name_plural = "轮值规则"
        db_table = "duty_rule"
        ordering = ["-update_time"]


class DutyRuleSnap(Model):
    """
    告警规则快照
    """

    duty_rule_id = models.IntegerField("轮值组ID", null=False, db_index=True)
    user_group_id = models.IntegerField("用户组ID", null=False, db_index=True)
    first_effective_time = models.CharField("首次生效时间", null=True, max_length=32)
    next_plan_time = models.CharField("下一次生效时间", null=True, max_length=32)
    end_time = models.CharField("结束时间", null=True, max_length=32)
    next_user_index = models.IntegerField("下一次轮岗用户组", default=0)
    rule_snap = models.JSONField(verbose_name="当前快照的配置内容", default=dict)
    enabled = models.BooleanField("是否生效状态", default=False)

    class Meta:
        verbose_name = "轮值规则快照"
        verbose_name_plural = "轮值规则快照"
        db_table = "duty_rule_snap"


class DutyRuleRelation(models.Model):
    """
    轮值用户组关系表
    """

    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0, blank=True, db_index=True)
    user_group_id = models.IntegerField("用户组ID", db_index=True)
    duty_rule_id = models.IntegerField("规则ID", db_index=True)
    order = models.IntegerField("规则的顺序", default=0)

    class Meta:
        verbose_name = "用户组轮值关系表"
        verbose_name_plural = "用户组轮值关系表"
        db_table = "duty_rule_relation"


class DutyPlanSendRecord(models.Model):
    """
    用户组轮值排班发送计划
    """

    user_group_id = models.IntegerField("用户组ID", db_index=True)
    last_send_time = models.IntegerField("最后发送时间戳", default=0)
    notice_config = models.JSONField("发送通知配置信息(留作记录)", default=dict)

    class Meta:
        verbose_name = "用户组排班计划发送表"
        verbose_name_plural = "用户组排班计划发送表"
        db_table = "duty_plan_send_record"
        ordering = ["-id"]


class DutyArrange(AbstractRecordModel):
    """
    轮班配置
    """

    user_group_id = models.IntegerField("关联的告警组", null=True, db_index=True)
    duty_rule_id = models.IntegerField("轮值规则ID", null=True, db_index=True)
    # 时间范围
    work_time = models.CharField("工作时间段", default="always", max_length=128)
    users = models.JSONField(verbose_name="告警处理值班人员", default=dict)

    # 轮值用户组， 当group_type为auto的时候，仅支持第一个列表
    duty_users = models.JSONField(verbose_name="轮班用户", default=dict)
    # 用户分组类型
    group_type = models.CharField(
        "分组类型",
        choices=DutyGroupType.CHOICE,
        default="specified",
        max_length=64,
    )

    group_number = models.IntegerField("每班人数", default=0)

    # 是否需要交接
    need_rotation = models.BooleanField("是否轮班", default=False)

    # 配置生效时间
    effective_time = models.DateTimeField("配置生效时间", null=True, db_index=True)
    # handoff_time: {"date": 1, "time": "10:00"  } 根据rotation_type进行切换
    handoff_time = models.JSONField(verbose_name="轮班交接时间安排", default=dict)
    # 工作时间段 duty_time: [{"work_type": "daily|month|week|work_day|weekend|custom", "work_days":[1,2,3],
    # "work_time_type":"time_range| datetime_range","work_time":""}]
    duty_time = models.JSONField(verbose_name="轮班时间安排", default=dict)
    order = models.IntegerField("轮班组的顺序", default=0)
    """ backups: [{users:[],"begin_time":"2021-03-21 00:00",
    "end_time":"2021-03-25 00:00",
    "work_time": "10:00--18:00"
   "exclude_days": ["2021-03-21"]}]"""
    backups = models.JSONField(verbose_name="备份安排", default=dict)

    hash = models.CharField("原始配置摘要", max_length=64, default="", blank=True, null=True)

    class Meta:
        verbose_name = "告警组时间安排"
        verbose_name_plural = "告警组时间安排"
        db_table = "duty_arrange"

    @classmethod
    def bulk_create(cls, duty_arranges, instance):
        """
        批量创建轮值项
        """
        for index, duty_arrange in enumerate(duty_arranges):
            # 根据排序给出顺序表
            duty_arrange["order"] = index + 1

        duty_arranges = {duty_arrange["hash"]: duty_arrange for duty_arrange in duty_arranges}
        existed_duty_queryset = DutyArrange.objects.all()
        instance_id_key = "duty_rule_id"
        if isinstance(instance, UserGroup):
            # 如果关联关系是用户组，则过滤告警组相关的内容
            existed_duty_queryset = existed_duty_queryset.filter(user_group_id=instance.id)
            instance_id_key = "user_group_id"
        elif isinstance(instance, DutyRule):
            # 如果关联关系是轮值规则， 则过滤轮值规则内容
            existed_duty_queryset = existed_duty_queryset.filter(duty_rule_id=instance.id)
        else:
            # 如果不是这两种类型的其中一种，直接返回，否则后面是危险的删除操作，会删掉所有的轮值记录
            return

        existed_duty_instances = {duty.hash: duty for duty in existed_duty_queryset}

        existed_duty = {
            duty_hash: duty_arrange
            for duty_hash, duty_arrange in duty_arranges.items()
            if duty_hash in existed_duty_instances
        }

        # 如果hash不在更新列表中的，直接删除
        deleted_duty_ids = [duty.id for duty in existed_duty_queryset if duty.hash not in existed_duty]

        new_duty_arranges = [
            duty_arrange for duty_hash, duty_arrange in duty_arranges.items() if duty_hash not in existed_duty
        ]

        # delete old duty arranges
        cls.objects.filter(id__in=deleted_duty_ids).delete()

        # update old duty arranges
        for duty_hash, duty_data in existed_duty.items():
            duty = existed_duty_instances[duty_hash]
            for attr, value in duty_data.items():
                setattr(duty, attr, value)
            duty.save()

        # create new duty arranges
        duty_arrange_instances = []
        for duty_arrange in new_duty_arranges:
            duty_arrange[instance_id_key] = instance.id
            duty_arrange_instances.append(cls(**duty_arrange))
        if duty_arrange_instances:
            cls.objects.bulk_create(duty_arrange_instances)


class MetricMappingConfigModel(Model):
    """
    指标映射配置表
    """

    config_field = models.CharField("配置名称", max_length=128, db_index=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    mapping_detail = models.JSONField("映射信息", default=dict)
    mapping_range = models.JSONField("映射范围", default=list)
    range_type = models.CharField("数据范围类型", max_length=128, default="kubernetes")
    bk_biz_id = models.IntegerField("业务ID")

    class Meta:
        verbose_name = "指标映射配置"
        verbose_name_plural = "指标映射配置"
        db_table = "metric_mapping_config"


class DutyArrangeSnap(Model):
    """
    轮值安排快照
    """

    user_group_id = models.IntegerField("告警组ID", null=False, db_index=True)
    duty_arrange_id = models.IntegerField("轮值组ID", null=False, db_index=True)
    next_plan_time = models.DateTimeField("配置生效时间", null=True)
    first_effective_time = models.DateTimeField("配置生效时间", null=True)
    duty_snap = models.JSONField(verbose_name="当前快照的配置内容", default=dict)
    is_active = models.BooleanField("是否生效状态", default=False)

    class Meta:
        verbose_name = "告警组时间安排快照"
        verbose_name_plural = "告警组时间安排快照"
        db_table = "duty_arrange_snap"


class DutyPlan(Model):
    """
    轮班计划表
    """

    id = models.BigAutoField("主键", primary_key=True)
    user_group_id = models.IntegerField("关联的告警组", null=False, db_index=True)
    duty_rule_id = models.IntegerField("关联的告警信息", null=True, db_index=True)
    duty_arrange_id = models.IntegerField("轮值组ID", null=True, db_index=True)
    order = models.IntegerField("轮班组的顺序")
    user_index = models.IntegerField("轮班用户的分组", default=0)

    is_active = models.BooleanField("是否生效状态（已废弃）", default=False)

    # 是否有效，替换原来的is_active字段，这样可以设置索引
    is_effective = models.IntegerField("是否有效", default=0, db_index=True)
    start_time = models.CharField("当前轮班生效开始时间", null=False, max_length=32, default="1970-01-01 00:00:00")
    finished_time = models.CharField("当前轮班生效结束时间", null=True, max_length=32)

    users = models.JSONField(verbose_name="当前告警处理值班人员", default=dict)
    work_times = models.JSONField("工作时间段", default=list)
    timezone = models.CharField("时区", default="Asia/Shanghai", max_length=64)

    # 存UTC时间，根据用户组配置的时区进行调整
    begin_time = models.DateTimeField("当前轮班生效开始时间", null=True)
    end_time = models.DateTimeField("当前轮班生效结束时间", null=True)

    # 最近一次排班计划的起始时间点，记录时间戳, 为0的话表示从来没有发送过
    last_send_time = models.IntegerField("最近一次发送通知时间", default=0)

    # duty_time: [{"work_type": "daily|month|week", "work_days":[1,2,3], "work_time"}]
    duty_time = models.JSONField(verbose_name="轮班时间安排", default=dict)

    def is_active_plan(self, data_time=None):
        """
        当前排班是否命中
        """
        # 结束时间没有的话，认为一直有效a
        try:
            tz_info = pytz.timezone(self.timezone)
        except Exception:
            # 当有异常的时候，默认用中国时区，怕用户乱填
            tz_info = pytz.timezone("Asia/Shanghai")

        data_time = data_time or time_tools.datetime2str(datetime.now(tz=tz_info))
        finished_time = self.finished_time or "3000-01-01 00:00:00"

        if finished_time < self.start_time or not self.start_time <= data_time <= finished_time:
            # 如果当前时间不满足区间条件，则直接
            return False

        for work_time in self.work_times:
            start_time = f'{work_time["start_time"]}:00'
            end_time = f'{work_time["end_time"]}:59'
            if start_time <= data_time <= end_time:
                # 当满足区间条件的时候
                return True
        return False

    def get_valid_backup_users(self, data_time=None):
        """
        获取有效的备份人信息
        :param data_time: 当前时间
        :return backup_users: 返回备份人员信息
        """

        data_time = TimeMatchByDay.convert_datetime_to_arrow(data_time or datetime.now())
        try:
            duty_arrange = DutyArrange.objects.get(id=self.duty_arrange_id)
        except DutyArrange.DoesNotExist:
            return []

        backup_users = []
        for backup in duty_arrange.backups:
            if not self.is_time_match(backup["work_time"], backup["begin_time"], backup["end_time"], data_time):
                # 工作时间段不匹配，忽略
                continue
            for exclude_setting in backup.get("exclude_settings", []):
                # 处于排除时间段内，直接去掉
                exclude_date = exclude_setting["date"]
                work_time = exclude_setting["work_time"]
                begin_time = "{} 00:00:00".format(exclude_date)
                end_time = "{} 23:59:59".format(exclude_date)
                if self.is_time_match(work_time, begin_time, end_time, data_time):
                    # 在排除时间段内，直接排除
                    break
            else:
                backup_users.extend(backup["users"])
        return backup_users


class DefaultStrategyBizAccessModel(Model):
    """
    默认策略业务接入表
    """

    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    create_user = models.CharField("创建者", max_length=32)
    bk_biz_id = models.IntegerField("业务ID", null=False, blank=False, db_index=True)
    version = models.CharField("版本", max_length=32, null=False, blank=False)
    access_type = models.CharField(
        "接入类型",
        max_length=32,
        null=False,
        blank=False,
        choices=(
            ("os", "os"),
            ("gse", "gse"),
            ("k8s", "k8s"),
        ),
    )

    class Meta:
        verbose_name = "默认策略业务接入"
        verbose_name_plural = "默认策略业务接入"
        db_table = "alarm_strategy_biz_access"
        unique_together = ("bk_biz_id", "access_type", "version")
