from typing import Any, cast, final

from django.core.exceptions import ValidationError
from django.db import models
from typing_extensions import override

from bk_monitor_base.config.all import get_config
from bk_monitor_base.infras.constant import OLD_MONITOR_BACKEND_DB_NAME
from bk_monitor_base.infras.db_models.fields import TextJSONField
from bk_monitor_base.infras.db_models.manger import OldModelManager

from .constants import DataSourceLabel, DataTypeLabel, SourceApp, UserGroupType

# 策略模型是否使用旧模型
if get_config().domains.strategy.use_old_model:
    models_manager: models.Manager[Any] = OldModelManager(default_db_name=OLD_MONITOR_BACKEND_DB_NAME)
    managed = False
else:
    models_manager = models.Manager()
    managed = True


def _no_data_config() -> dict[str, Any]:
    """默认无数据配置"""
    return {"is_enabled": True, "continuous": 5, "agg_dimension": []}


def _default_target() -> list[list[dict[str, Any]]]:
    """默认监控目标"""
    return [[]]


@final
class ItemModel(models.Model):
    """
    监控项模型
    """

    strategy_id = models.IntegerField("关联策略ID", db_index=True)
    name = models.CharField("监控项名称", max_length=256)
    expression = models.TextField("计算公式")
    functions: list[dict[str, Any]] = models.JSONField("计算函数", default=list)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]
    origin_sql = models.TextField("原始查询语句")
    no_data_config: dict[str, Any] = models.JSONField("无数据配置", default=_no_data_config)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]
    target: list[list[dict[str, Any]]] = models.JSONField("监控目标", default=_default_target)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]
    meta: list[dict[str, Any]] = models.JSONField("查询配置元数据", default=list)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]
    metric_type = models.CharField("指标类型", max_length=32, default="", blank=True)
    time_delay = models.IntegerField("策略等待时间", default=0)

    objects = models_manager

    @final
    class Meta:
        verbose_name = "监控项配置V2"
        verbose_name_plural = "监控项配置V2"
        db_table = "alarm_item_v2"
        managed = managed


@final
class DetectModel(models.Model):
    """
    检测配置模型
    """

    strategy_id = models.IntegerField("关联策略ID", db_index=True)
    level = models.IntegerField(
        "告警级别",
        default=3,
        choices=(
            (1, "致命"),
            (2, "预警"),
            (3, "提醒"),
        ),
    )
    expression = models.TextField("计算公式", default="")
    trigger_config: dict[str, Any] = models.JSONField("触发条件配置", default=dict)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]
    recovery_config: dict[str, Any] = models.JSONField("恢复条件配置", default=dict)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]
    connector = models.CharField(
        "同级别算法连接符", choices=(("and", "AND"), ("or", "OR")), max_length=4, default="and"
    )

    objects = models_manager

    @final
    class Meta:
        verbose_name = "检测配置V2"
        verbose_name_plural = "检测配置V2"
        db_table = "alarm_detect_v2"
        managed = managed


@final
class AlgorithmModel(models.Model):
    """
    检测算法模型
    常用查询：
        1. 基于监控项ID
        2. 基于算法类型
    """

    @final
    class AlgorithmChoices:
        Threshold = "Threshold"
        NewSeries = "NewSeries"
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
        HostAnomalyDetection = "HostAnomalyDetection"

    AIOPS_ALGORITHMS = [
        AlgorithmChoices.IntelligentDetect,
        AlgorithmChoices.TimeSeriesForecasting,
        AlgorithmChoices.AbnormalCluster,
        AlgorithmChoices.MultivariateAnomalyDetection,
        AlgorithmChoices.HostAnomalyDetection,
    ]

    AUTHORIZED_SOURCE_ALGORITHMS = [
        AlgorithmChoices.MultivariateAnomalyDetection,
        AlgorithmChoices.HostAnomalyDetection,
    ]

    ALGORITHM_CHOICES = (
        (AlgorithmChoices.Threshold, "静态阈值算法"),
        (AlgorithmChoices.NewSeries, "新序列算法"),
        (AlgorithmChoices.SimpleRingRatio, "简易环比算法"),
        (AlgorithmChoices.AdvancedRingRatio, "高级环比算法"),
        (AlgorithmChoices.SimpleYearRound, "简易同比算法"),
        (AlgorithmChoices.AdvancedYearRound, "高级同比算法"),
        (AlgorithmChoices.PartialNodes, "部分节点数算法"),
        (AlgorithmChoices.OsRestart, "主机重启算法"),
        (AlgorithmChoices.ProcPort, "进程端口算法"),
        (AlgorithmChoices.PingUnreachable, "Ping不可达算法"),
        (AlgorithmChoices.YearRoundAmplitude, "同比振幅算法"),
        (AlgorithmChoices.YearRoundRange, "同比区间算法"),
        (AlgorithmChoices.RingRatioAmplitude, "环比振幅算法"),
        (AlgorithmChoices.IntelligentDetect, "智能异常检测算法"),
        (AlgorithmChoices.TimeSeriesForecasting, "时序预测算法"),
        (AlgorithmChoices.AbnormalCluster, "离群检测算法"),
        (AlgorithmChoices.MultivariateAnomalyDetection, "多指标异常检测算法"),
        (AlgorithmChoices.HostAnomalyDetection, "主机异常检测算法"),
    )

    strategy_id = models.IntegerField("关联策略ID", db_index=True)
    item_id = models.IntegerField("关联监控项ID", db_index=True)
    level = models.IntegerField(
        "告警级别",
        default=3,
        choices=((1, "致命"), (2, "预警"), (3, "提醒")),
    )
    type = models.CharField("算法类型", max_length=64, choices=ALGORITHM_CHOICES, db_index=True)
    unit_prefix = models.CharField("算法单位前缀", max_length=32, default="", blank=True)
    config: dict[str, Any] | list[Any] = models.JSONField("算法配置", default=dict)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]

    objects = models_manager

    @final
    class Meta:
        verbose_name = "检测算法配置V2"
        verbose_name_plural = "检测算法配置V2"
        db_table = "alarm_algorithm_v2"
        managed = managed


@final
class QueryConfigModel(models.Model):
    """
    查询配置基类
    """

    strategy_id = models.IntegerField("关联策略ID", db_index=True)
    item_id = models.IntegerField("关联监控项ID", db_index=True)
    alias = models.CharField("别名", max_length=12)
    data_source_label = models.CharField("数据来源标签", max_length=32)
    data_type_label = models.CharField("数据类型标签", max_length=32)
    metric_id = models.CharField("指标ID", max_length=128)
    config: dict[str, Any] = models.JSONField("查询配置", default=dict)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]

    objects = models_manager

    @final
    class Meta:
        verbose_name = "查询配置表V2"
        verbose_name_plural = "查询配置表V2"
        db_table = "alarm_query_config_v2"
        indexes = [models.Index(fields=["data_source_label", "data_type_label"])]
        managed = managed

    @classmethod
    def get_strategies_by_source_app(cls, source_app: str | None = None) -> set[int]:
        """根据source_app来源获取对应的策略ID

        Args:
            source_app: 来源app

        Returns:
            策略ID集合
        """
        queryset = cls.objects.all()

        if source_app == SourceApp.FTA:
            return set(
                queryset.filter(
                    models.Q(data_type_label=DataTypeLabel.ALERT) | models.Q(data_source_label=DataSourceLabel.BK_FTA)
                )
                .values_list("strategy_id", flat=True)
                .distinct()
            )

        return set(queryset.values_list("strategy_id", flat=True).distinct())


@final
class StrategyLabel(models.Model):
    """策略全局标签

    tag_name： /a/b/c/  - 3级标签 /a/b/
    全局标签：bk_biz_id: 0 , strategy_id: 0
    """

    label_name = models.CharField(max_length=128, verbose_name="策略名称")
    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0, blank=True, db_index=True)
    strategy_id = models.IntegerField(verbose_name="策略ID", default=0, blank=True)

    objects = models_manager

    @final
    class Meta:
        verbose_name = "策略标签"
        verbose_name_plural = "策略标签"
        db_table = "alarm_strategy_label"
        indexes = [models.Index(fields=["label_name", "strategy_id"])]
        managed = managed

    @classmethod
    def get_label_dict(cls, strategy_id: int | None = None) -> dict[int, list[str]]:
        label_dict: dict[int, list[str]] = {}
        queryset = cls.objects
        if strategy_id is not None:
            queryset = queryset.filter(strategy_id=strategy_id)
        for sid, label_name in queryset.values_list("strategy_id", "label_name"):
            label_dict.setdefault(sid, []).append(label_name.strip("/"))
        return label_dict


@final
class StrategyModel(models.Model):
    """
    策略表
    """

    @final
    class StrategyType:
        Monitor = "monitor"
        FTASolution = "fta"
        Dashboard = "dashboard"

        Choices = [(Monitor, "监控"), (FTASolution, "故障自愈"), (Dashboard, "仪表盘")]

    @final
    class InvalidType:
        NONE = ""
        INVALID_RELATED_STRATEGY = "invalid_related_strategy"
        DELETED_RELATED_STRATEGY = "deleted_related_strategy"
        INVALID_UNIT = "invalid_unit"
        INVALID_TARGET = "invalid_target"
        INVALID_METRIC = "invalid_metric"
        INVALID_BIZ = "invalid_biz"
        INVALID_DASHBOARD_PANEL = "invalid_dashboard_panel"

        Choices = [
            (NONE, NONE),
            (INVALID_RELATED_STRATEGY, "关联的策略已失效"),
            (DELETED_RELATED_STRATEGY, "关联的策略已删除"),
            (INVALID_UNIT, "指标和检测算法的单位类型不一致"),
            (INVALID_TARGET, "监控目标全部失效"),
            (INVALID_METRIC, "监控指标不存在"),
            (INVALID_BIZ, "策略所属业务不存在"),
            (INVALID_DASHBOARD_PANEL, "策略配置的仪表盘图表失效"),
        ]

    name = models.CharField("策略名称", max_length=128, db_index=True)
    bk_biz_id = models.IntegerField("业务ID", db_index=True)
    source = models.CharField("来源系统", default=SourceApp.MONITOR, max_length=32)
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
    # 自动算的是16位uuid，用户指定带固定前缀 PGK:
    priority_group_key = models.CharField("优先级分组", max_length=64, default=None, blank=True, null=True)

    objects = models_manager

    @final
    class Meta:
        verbose_name = "策略配置V2"
        verbose_name_plural = "策略配置V2"
        db_table = "alarm_strategy_v2"
        indexes = [models.Index(fields=["is_enabled", "bk_biz_id", "scenario"])]
        managed = managed

    @property
    def labels(self) -> list[str]:
        """获取策略标签"""
        return StrategyLabel.get_label_dict(self.pk).get(self.pk) or []


@final
class StrategyHistoryModel(models.Model):
    """
    策略历史表
    """

    strategy_id = models.IntegerField("关联策略ID", db_index=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)
    create_user = models.CharField("创建者", max_length=32)
    content: dict[str, Any] = models.JSONField("保存内容", default=dict)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]
    operate = models.CharField(
        "操作",
        choices=[("delete", "删除"), ("create", "创建"), ("update", "更新")],
        db_index=True,
        max_length=12,
    )
    status = models.BooleanField("操作状态", default=False)
    message = models.TextField("错误信息", default="", blank=True)

    objects = models_manager

    @final
    class Meta:
        verbose_name = "策略配置操作历史"
        verbose_name_plural = "策略配置操作历史"
        db_table = "alarm_strategy_history"
        ordering = ["-create_time"]
        managed = managed


@final
class NoticeTemplate(models.Model):
    """
    通知模板
    """

    anomaly_template = models.TextField(default="", verbose_name="异常通知模板")
    recovery_template = models.TextField(default="", verbose_name="恢复通知模板")

    action_id = models.IntegerField(verbose_name="关联动作ID", db_index=True)

    objects = models_manager

    @final
    class Meta:
        verbose_name = "通知模板配置"
        verbose_name_plural = "通知模板配置"
        db_table = "alarm_notice_template"
        managed = managed


@final
class ActionConfig(models.Model):
    """自愈套餐"""

    NOTICE_PLUGIN_ID = 1

    is_builtin = models.BooleanField("是否内置", default=False)
    name = models.CharField("套餐名称", max_length=128, null=False)
    desc = models.TextField("套餐描述", default="")
    bk_biz_id = models.CharField("业务ID", max_length=64, null=False)
    plugin_id = models.CharField("插件ID", max_length=64, null=False)
    # json字符串
    execute_config: dict[str, Any] = TextJSONField("执行任务参数配置")  # pyright: ignore[reportAssignmentType]

    app = models.CharField("所属应用", max_length=128, default="", blank=True, null=True)
    path = models.CharField("资源路径", max_length=128, default="", blank=True, null=True)
    hash = models.CharField("原始配置摘要", max_length=64, default="", blank=True, null=True)
    snippet = models.TextField("配置片段", default="", blank=True, null=True)

    is_enabled = models.BooleanField("是否启用", default=True)
    is_deleted = models.BooleanField("是否删除", default=False)
    create_user = models.CharField("创建人", max_length=32, default="", blank=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True, blank=True)
    update_user = models.CharField("最后修改人", max_length=32, default="", blank=True)
    update_time = models.DateTimeField("最后修改时间", auto_now=True, blank=True)

    objects = models_manager

    @final
    class Meta:
        verbose_name = "自愈套餐"
        verbose_name_plural = "自愈套餐"
        db_table = "action_config"
        ordering = ("-update_time", "-id")
        managed = managed


# @final
# class ActionNoticeMapping(models.Model):
#     """
#     通知动作和通知组的关系（多对多）

#     1. 一个通知动作，可以设置多个通知组
#     2. 一个通知组可以应用到多个通知动作
#     """

#     action_id = models.IntegerField(verbose_name="关联动作ID", db_index=True)
#     notice_group_id = models.IntegerField(verbose_name="关联通知组ID", db_index=True)

#     is_enabled = models.BooleanField("是否启用", default=True)
#     is_deleted = models.BooleanField("是否删除", default=False)
#     create_user = models.CharField("创建人", max_length=32, default="", blank=True)
#     create_time = models.DateTimeField("创建时间", auto_now_add=True, blank=True)
#     update_user = models.CharField("最后修改人", max_length=32, default="", blank=True)
#     update_time = models.DateTimeField("最后修改时间", auto_now=True, blank=True)

#     @final
#     class Meta:
#         db_table = "alarm_action_notice_group_mapping"
#         managed = False


@final
class StrategyActionConfigRelation(models.Model):
    """策略响应动作配置关联表"""

    @final
    class RelateType:
        NOTICE = "NOTICE"
        ACTION = "ACTION"

    RELATE_TYPE_CHOICES = (
        (RelateType.NOTICE, "通知"),
        (RelateType.ACTION, "处理动作"),
    )

    strategy_id = models.IntegerField("故障自愈的策略ID", null=False, db_index=True)
    config_id = models.IntegerField("响应动作配置ID", null=False, db_index=True)
    relate_type = models.CharField("关联类型", max_length=32, choices=RELATE_TYPE_CHOICES, default=RelateType.NOTICE)
    signal: list[str] = models.JSONField("触发信号", default=list)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]
    user_groups: list[int] = models.JSONField("用户组", default=list)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]
    user_type = models.CharField("人员类型", default=UserGroupType.MAIN, choices=UserGroupType.CHOICE, max_length=32)
    options: dict[str, Any] = models.JSONField("高级设置", default=dict)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]

    is_enabled = models.BooleanField("是否启用", default=True)
    is_deleted = models.BooleanField("是否删除", default=False)
    create_user = models.CharField("创建人", max_length=32, default="", blank=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True, blank=True)
    update_user = models.CharField("最后修改人", max_length=32, default="", blank=True)
    update_time = models.DateTimeField("最后修改时间", auto_now=True, blank=True)

    objects = models_manager

    @final
    class Meta:
        verbose_name = "策略响应动作配置关联表"
        verbose_name_plural = "策略响应动作配置关联表"
        db_table = "strategy_action_relation"
        managed = managed

    @property
    def validated_user_groups(self):
        return [group_id for group_id in self.user_groups if group_id]


# @final
# class AlgorithmChoiceConfig(models.Model):
#     """
#     算法类型配置表
#     algorithm：AlgorithmChoices和算法类型配置表是一对多关系
#     """

#     id = models.BigAutoField("id", primary_key=True)
#     alias = models.CharField("中文名称", max_length=64)
#     name = models.CharField("名称", max_length=64)
#     document = models.TextField("使用说明", null=True, blank=True)
#     description = models.TextField("描述", null=True, blank=True)
#     is_default = models.BooleanField("是否默认", default=False)
#     is_new_version = models.BooleanField("是否最新版本", default=True)
#     version_no = models.CharField(max_length=10, null=False, blank=True)
#     instruction = models.TextField("方案描述", null=True, blank=True)
#     variable_info = models.JSONField("参数变量", blank=True, null=True, default=dict)
#     ts_freq = models.IntegerField("数据频率", default=0)
#     algorithm = models.CharField("算法类型", max_length=64, choices=AlgorithmModel.ALGORITHM_CHOICES, db_index=True)
#     config: dict[str, Any] = models.JSONField("其他配置信息", blank=False, null=False, default=dict)

#     @final
#     class Meta:
#         verbose_name = "算法类型配置"
#         verbose_name_plural = "算法类型配置"
#         db_table = "algorithm_choice_config"
#         managed = False


@final
class UserGroup(models.Model):
    """告警处理组"""

    name = models.CharField(max_length=128, verbose_name="用户组名称")
    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0, blank=True, db_index=True)
    timezone = models.CharField(verbose_name="时区", default="Asia/Shanghai", max_length=32)

    desc = models.TextField(verbose_name="说明/备注")
    source = models.CharField(verbose_name="来源系统", default=SourceApp.MONITOR, max_length=32)
    need_duty = models.BooleanField(verbose_name="是否需要轮值", default=False)
    channels: list[str] = models.JSONField("告警通知渠道配置", default=list)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]

    # 机器人通知提醒人员 all 表示当前组的人员
    mention_list: list[dict[str, Any]] = models.JSONField("告警提醒人", default=list)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]

    # mention_type 0 代表是默认，1代表是用户改动过的
    mention_type = models.IntegerField("提醒类型", default=0)

    alert_notice: list[dict[str, Any]] = models.JSONField("告警通知配置", default=list)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]
    action_notice: list[dict[str, Any]] = models.JSONField("执行通知配置", default=list)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]
    duty_notice: dict[str, Any] = models.JSONField("轮值通知配置", default=dict)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]
    webhook_action_id = models.IntegerField("回调套餐ID", default=0)

    # 对应的轮值规则， need_duty为True的情况下必填
    duty_rules: list[int] = models.JSONField("轮值规则", default=list)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]

    app = models.CharField("所属应用", max_length=128, default="", blank=True, null=True)
    path = models.CharField("资源路径", max_length=128, default="", blank=True, null=True)
    hash = models.CharField("原始配置摘要", max_length=64, default="", blank=True, null=True)
    snippet = models.TextField("配置片段", default="", blank=True, null=True)

    is_enabled = models.BooleanField("是否启用", default=True)
    is_deleted = models.BooleanField("是否删除", default=False)
    create_user = models.CharField("创建人", max_length=32, default="", blank=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True, blank=True)
    update_user = models.CharField("最后修改人", max_length=32, default="", blank=True)
    update_time = models.DateTimeField("最后修改时间", auto_now=True, blank=True)

    objects = models_manager

    @final
    class Meta:
        verbose_name = "告警处理组配置"
        verbose_name_plural = "告警处理组配置"
        db_table = "user_group"
        indexes = [models.Index(fields=["bk_biz_id", "source"])]
        ordering = ("-update_time",)
        managed = managed


@final
class StrategyIssueConfigModel(models.Model):
    """策略 Issue 聚合配置

    对应表 bkmonitor_strategy_issue_config，字段与 bkmonitor.models.issue.StrategyIssueConfig 对齐。
    """

    VALID_CONDITION_METHODS = {"eq", "neq", "include", "exclude", "reg", "nreg"}

    strategy_id = models.IntegerField("策略 ID", unique=True, db_index=True)
    bk_biz_id = models.IntegerField("业务 ID", db_index=True)
    is_enabled = models.BooleanField("是否启用", default=True)
    is_deleted = models.BooleanField("是否删除", default=False)
    aggregate_dimensions: list[str] = models.JSONField("聚合维度", default=list, blank=True)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]
    conditions: list[dict[str, Any]] = models.JSONField("过滤条件", default=list, blank=True)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]
    alert_levels: list[int] = models.JSONField("生效告警级别", default=list, blank=True)  # pyright: ignore[reportUnknownVariableType,reportAssignmentType]
    create_user = models.CharField("创建人", max_length=32, default="", blank=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True, blank=True)
    update_user = models.CharField("最后修改人", max_length=32, default="", blank=True)
    update_time = models.DateTimeField("最后修改时间", auto_now=True, blank=True)

    objects = models_manager

    @classmethod
    def _validate_condition_item(cls, cond: Any, effective_dimensions: set[str] | None = None) -> None:
        """校验单条 condition 的结构与字段合法性。"""
        if not isinstance(cond, dict):
            raise ValidationError({"conditions": f"conditions 条目必须为 dict，当前为 {type(cond)}"})

        cond_dict = cast(dict[str, Any], cond)
        required_keys = {"key", "method", "value"}
        missing = required_keys - set(cond_dict.keys())
        if missing:
            raise ValidationError({"conditions": f"conditions 条目缺少字段: {sorted(missing)}"})

        key: Any = cond_dict.get("key")
        method: Any = cond_dict.get("method")
        value: Any = cond_dict.get("value")

        if not isinstance(key, str) or not key:
            raise ValidationError({"conditions": "conditions.key 必须为非空字符串"})
        if method not in cls.VALID_CONDITION_METHODS:
            raise ValidationError({"conditions": f"不支持的 method: {method}"})
        if value is None:
            raise ValidationError({"conditions": "conditions.value 不能为空"})
        if effective_dimensions is not None and key not in effective_dimensions:
            raise ValidationError({"conditions": f"conditions.key={key} 不在可用维度集合中"})

    @override
    def clean(self) -> None:
        if not self.alert_levels or not set(self.alert_levels).issubset({1, 2, 3}):
            raise ValidationError({"alert_levels": "alert_levels 必须为 [1,2,3] 的非空子集"})

        for cond in self.conditions:
            self._validate_condition_item(cond, set(self.aggregate_dimensions) if self.aggregate_dimensions else None)

    @final
    class Meta:
        verbose_name = "策略 Issue 聚合配置"
        verbose_name_plural = "策略 Issue 聚合配置"
        db_table = "bkmonitor_strategy_issue_config"
        managed = managed
