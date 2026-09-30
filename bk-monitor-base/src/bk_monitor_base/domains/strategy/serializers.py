from typing import Any, cast, final

from jinja2.exceptions import TemplateSyntaxError
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.fields import empty
from typing_extensions import override

from bk_monitor_base.infras.constant import NOISE_REDUCE_TIMEDELTA
from bk_monitor_base.infras.template import jinja2_environment

from .constants import (
    ALL_CONVERGE_DIMENSION,
    CONVERGE_FUNCTION,
    ActionSignal,
    IntervalNotifyMode,
    VisualType,
    VoiceNoticeMode,
)

YEAR_ROUND_ALLOWED_METHODS = {
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "eq": "==",
}

THRESHOLD_ALLOWED_METHODS = {
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "eq": "==",
    "neq": "!=",
}


@final
class AdvancedYearRoundSerializer(serializers.Serializer):
    """
    高级同比算法serializer
    """

    floor = serializers.FloatField(required=True, allow_null=True, min_value=0)
    floor_interval = serializers.IntegerField(required=True, allow_null=True, min_value=1)
    ceil = serializers.FloatField(required=True, allow_null=True, min_value=0)
    ceil_interval = serializers.IntegerField(required=True, allow_null=True, min_value=1)
    # 新增历史数据获取类型: 均值或顺时值
    fetch_type = serializers.CharField(default="avg")

    @override
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        floor = attrs["floor"]
        floor_interval = attrs["floor_interval"]
        ceil = attrs["ceil"]
        ceil_interval = attrs["ceil_interval"]
        # 校验历史数据获取类型
        fetch_type = attrs["fetch_type"]
        if fetch_type not in ["avg", "last"]:
            raise serializers.ValidationError("fetch_type 必须是 avg 或 last")

        floor_configured = all([floor, floor_interval])
        ceil_configured = all([ceil, ceil_interval])
        if not floor_configured:
            attrs["floor"] = None
            attrs["floor_interval"] = None
        if not ceil_configured:
            attrs["ceil"] = None
            attrs["ceil_interval"] = None
        if not any([ceil_configured, floor_configured]):
            raise serializers.ValidationError("floor 和 ceil 至少需要配置一个")
        return attrs


class AdvancedRingRatioSerializer(AdvancedYearRoundSerializer):
    """
    高级环比算法serializer,复用高级同比算法serializer
    """


@final
class RingRatioAmplitudeSerializer(serializers.Serializer):
    """
    环比振幅算法serializer
    """

    ratio = serializers.FloatField(required=True)
    shock = serializers.FloatField(required=True)
    threshold = serializers.FloatField(required=True)


@final
class SimpleRingRatioSerializer(serializers.Serializer):
    """
    简单环比算法serializer
    """

    floor = serializers.FloatField(required=True, allow_null=True, min_value=0)
    ceil = serializers.FloatField(required=True, allow_null=True, min_value=0)

    @override
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        floor = attrs["floor"]
        ceil = attrs["ceil"]
        if not any([floor, ceil]):
            raise serializers.ValidationError("floor 和 ceil 至少需要配置一个")
        return attrs


@final
class SimpleYearRoundSerializer(SimpleRingRatioSerializer):
    """
    简单同比算法serializer
    """


@final
class ThresholdSerializer(serializers.ListSerializer):
    """
    静态阈值算法serializer
    """

    @final
    class AndSerializer(serializers.ListSerializer):
        @final
        class UnitSerializer(serializers.Serializer):
            threshold = serializers.FloatField(required=True)
            method = serializers.ChoiceField(required=True, choices=list(THRESHOLD_ALLOWED_METHODS.keys()))

        child = UnitSerializer()

    child = AndSerializer(allow_empty=False)


@final
class NewSeriesSerializer(serializers.Serializer):
    """新序列算法serializer"""

    effective_delay = serializers.IntegerField(label="生效延迟", required=False, default=86400)
    max_series = serializers.IntegerField(label="最大序列数", required=False, default=100000)
    detect_range = serializers.IntegerField(label="检测范围", required=True)


@final
class AIServiceControlMixin(serializers.Serializer):
    """
    AI服务控制参数Mixin
    用于管理与AI服务相关的通用控制参数（如灰度、服务选择等）

    这些参数不属于算法配置本身，而是用于控制API调用行为
    所有需要调用AI服务的算法序列化器都应该继承此Mixin
    """

    service_name = serializers.CharField(
        label="service环境选择", required=False, default="default", help_text="指定AI服务的环境名称，用于多环境部署场景"
    )
    grey_to_bkfara = serializers.BooleanField(
        label="是否迁移到bkfara", required=False, default=False, help_text="是否使用新的bkfara服务，用于灰度发布控制"
    )


@final
class IntelligentDetectSerializer(AIServiceControlMixin, serializers.Serializer):
    """
    智能异常检测算法serializer
    """

    args = serializers.DictField(required=True)
    plan_id = serializers.IntegerField(required=True)
    visual_type = serializers.ChoiceField(
        default=VisualType.NONE, choices=[VisualType.NONE, VisualType.SCORE, VisualType.BOUNDARY]
    )


@final
class TimeSeriesForecastingSerializer(serializers.Serializer):
    """
    时序预测算法serializer
    """

    @final
    class BoundType:
        # 上界
        UPPER = "upper"
        # 下界
        LOWER = "lower"
        # 预测值
        MIDDLE = "middle"

    args = serializers.DictField(required=True, label="算法参数")
    plan_id = serializers.IntegerField(required=True, label="方案ID")
    thresholds = ThresholdSerializer(required=True, label="阈值配置")
    bound_type = serializers.ChoiceField(
        default=BoundType.MIDDLE, choices=[BoundType.UPPER, BoundType.LOWER, BoundType.MIDDLE]
    )
    duration = serializers.IntegerField(required=True, label="预测时长(s)", min_value=0)
    visual_type = serializers.ChoiceField(default=VisualType.FORECASTING, choices=[VisualType.FORECASTING])


@final
class AbnormalClusterSerializer(serializers.Serializer):
    """
    离群检测检测算法
    """

    args = serializers.DictField(default=dict)
    plan_id = serializers.IntegerField(required=True)
    group = serializers.ListSerializer(allow_empty=True, child=serializers.CharField(), default=list)
    visual_type = serializers.ChoiceField(default=VisualType.NONE, choices=[VisualType.NONE])


@final
class YearRoundAmplitudeSerializer(serializers.Serializer):
    """
    同比振幅算法
    """

    ratio = serializers.FloatField(required=True)
    shock = serializers.FloatField(required=True)
    days = serializers.IntegerField(required=True, min_value=1)
    method = serializers.ChoiceField(required=True, choices=list(YEAR_ROUND_ALLOWED_METHODS.keys()))


@final
class YearRoundRangeSerializer(serializers.Serializer):
    """
    同比区间算法
    """

    ratio = serializers.FloatField(required=True)
    shock = serializers.FloatField(required=True)
    days = serializers.IntegerField(required=True, min_value=1)
    method = serializers.ChoiceField(required=True, choices=list(YEAR_ROUND_ALLOWED_METHODS.keys()))


@final
class MultivariateAnomalyDetectionSerializer(serializers.Serializer):
    """
    智能AI多指标异常检测算法
    目前只有host场景，无需传入指标值，由数据平台算法的智能指标组成
    """

    @final
    class MetricListSerializer(serializers.ListSerializer):
        @final
        class MetricSerializer(serializers.Serializer):
            metric_id = serializers.CharField(required=True, label="指标ID")
            name = serializers.CharField(required=True, label="指标中文名")
            unit = serializers.CharField(required=True, label="单位")
            metric_name = serializers.CharField(required=True, label="指标英文名")

        child = MetricSerializer()

    scene_id = serializers.CharField(required=True, label="场景")
    metrics = MetricListSerializer(allow_empty=True, label="指标数据")


@final
class HostAnomalyDetectionSerializer(MultivariateAnomalyDetectionSerializer):
    """
    智能AI主机异常检测算法
    目前只有host场景，无需传入指标值，由数据平台算法的智能指标组成
    """

    levels = serializers.ListField(required=True, label="告警级别列表")
    sensitivity = serializers.IntegerField(required=True, label="告警敏感度")


@final
class QueryConfigSerializer(serializers.Serializer):
    """
    查询配置序列化器基类
    """

    functions = serializers.ListField(label="计算函数", default=[])
    intelligent_detect = serializers.DictField(label="智能监控配置", required=False)

    def get_config_field_names(self) -> list[str]:
        """获取配置字段名"""

        return list(self.fields.keys())  # pyright: ignore[reportUnknownArgumentType]


@final
class TimeSeriesQueryConfigSerializer(QueryConfigSerializer):
    result_table_id = serializers.CharField(required=False, label="结果表", allow_blank=True)
    data_label = serializers.CharField(required=False, label="db标识", allow_blank=True)
    agg_method = serializers.CharField(label="聚合方法")
    agg_interval = serializers.IntegerField(label="聚合周期", min_value=0)
    agg_dimension = serializers.ListField(label="聚合维度", allow_empty=True)
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())
    metric_field = serializers.CharField(label="指标")
    unit = serializers.CharField(label="单位", allow_blank=True, default="")


@final
class BkMonitorTimeSeriesSerializer(TimeSeriesQueryConfigSerializer):
    origin_config = serializers.DictField(label="原始配置", required=False)
    values = serializers.ListField(required=False)


@final
class BkMonitorLogSerializer(QueryConfigSerializer):
    result_table_id = serializers.CharField(label="结果表")
    agg_method = serializers.CharField(label="聚合方法")
    agg_interval = serializers.IntegerField(label="聚合周期", min_value=0)
    agg_dimension = serializers.ListField(allow_empty=True)
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())


@final
class BkMonitorEventSerializer(QueryConfigSerializer):
    result_table_id = serializers.CharField(label="结果表")
    metric_field = serializers.CharField(label="指标")
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())


@final
class BkLogSearchTimeSeriesSerializer(TimeSeriesQueryConfigSerializer):
    query_string = serializers.CharField(label="查询语句", required=False)
    index_set_id = serializers.IntegerField(label="索引集ID")
    result_table_id = serializers.CharField(label="索引", allow_blank=True)
    time_field = serializers.CharField(label="时间字段", default="dtEventTimeStamp", allow_blank=True, allow_null=True)

    @override
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs.get("time_field"):
            attrs["time_field"] = "dtEventTimeStamp"
        return attrs


@final
class BkLogSearchLogSerializer(QueryConfigSerializer):
    query_string = serializers.CharField(label="查询语句")
    result_table_id = serializers.CharField(label="索引", allow_blank=True)
    index_set_id = serializers.IntegerField(label="索引集ID")
    agg_interval = serializers.IntegerField(label="聚合周期", min_value=0)
    agg_dimension = serializers.ListField(label="聚合维度", allow_empty=True)
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())
    time_field = serializers.CharField(label="时间字段", default="dtEventTimeStamp", allow_blank=True, allow_null=True)

    @override
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs.get("time_field"):
            attrs["time_field"] = "dtEventTimeStamp"
        return attrs


@final
class CustomEventSerializer(QueryConfigSerializer):
    result_table_id = serializers.CharField(required=False, label="结果表", allow_blank=True)
    data_label = serializers.CharField(required=False, label="db标识", allow_blank=True)
    agg_method = serializers.CharField(label="聚合方法", default="COUNT")
    agg_interval = serializers.IntegerField(label="聚合周期", min_value=0)
    agg_dimension = serializers.ListField(allow_empty=True)
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())
    custom_event_name = serializers.CharField(label="事件名", required=False, allow_blank=True)
    query_string = serializers.CharField(label="查询语句", required=False)


class CustomTimeSeriesSerializer(BkMonitorTimeSeriesSerializer):
    pass


@final
class BkDataTimeSeriesSerializer(QueryConfigSerializer):
    result_table_id = serializers.CharField(label="结果表")
    agg_method = serializers.CharField(label="聚合方法")
    agg_interval = serializers.IntegerField(label="聚合周期", min_value=0)
    agg_dimension = serializers.ListField(label="聚合维度", allow_empty=True)
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())
    metric_field = serializers.CharField(label="指标")
    unit = serializers.CharField(label="单位", allow_blank=True, default="")
    values = serializers.ListField(required=False)
    time_field = serializers.CharField(label="时间字段", default="dtEventTimeStamp", allow_blank=True, allow_null=True)
    extend_fields = serializers.DictField(label="拓展字段", required=False)

    @override
    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs.get("time_field"):
            attrs["time_field"] = "dtEventTimeStamp"
        return attrs


@final
class BkFtaEventSerializer(QueryConfigSerializer):
    alert_name = serializers.CharField(label="告警名称")
    agg_dimension = serializers.ListField(allow_empty=True)
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())
    agg_method = serializers.CharField(label="聚合方法")
    agg_interval = serializers.IntegerField(label="聚合周期", min_value=0)


@final
class BkFtaAlertSerializer(QueryConfigSerializer):
    alert_name = serializers.CharField(label="告警名称")
    agg_dimension = serializers.ListField(allow_empty=True)
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())


@final
class BkMonitorAlertSerializer(QueryConfigSerializer):
    bkmonitor_strategy_id = serializers.IntegerField(label="监控策略ID")
    agg_dimension = serializers.ListField(allow_empty=True)
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())


@final
class PrometheusTimeSeriesSerializer(QueryConfigSerializer):
    promql = serializers.CharField(label="查询表达式")
    agg_interval = serializers.IntegerField(label="聚合周期", min_value=0)


@final
class NoticeGroupSerializer(serializers.Serializer):
    @final
    class NoticeReceiverSerializer(serializers.Serializer):
        id = serializers.CharField(required=True, label="通知对象ID")
        type = serializers.ChoiceField(
            required=True, choices=(("user", "用户"), ("group", "用户组")), label="通知对象类别"
        )

    bk_biz_id = serializers.IntegerField(required=False, default=0, label="业务ID")
    name = serializers.CharField(required=True, max_length=128, label="通知组名称")
    notice_receiver = NoticeReceiverSerializer(required=True, many=True, label="通知对象")
    message = serializers.CharField(required=False, allow_blank=True, label="说明")
    notice_way = serializers.DictField(required=True, label="各级别对应的通知方式")
    wxwork_group = serializers.DictField(required=False, default={})
    webhook_url = serializers.CharField(required=False, allow_blank=True, default="", label="回调地址")
    id = serializers.IntegerField(required=False, label="修改对应的通知组ID列表")

    @override
    def validate_notice_way(self, value: dict[str, Any]) -> dict[str, Any]:
        if any(value.values()):
            return value
        raise serializers.ValidationError("通知方式至少开启一项")


@final
class ConvergeConfigDetailSlz(serializers.Serializer):
    """套餐收敛详情"""

    @final
    class ConditionSlz(serializers.Serializer):
        """套餐收敛"""

        DIMENSION_CHOICE = [(key, value) for key, value in ALL_CONVERGE_DIMENSION.items()]

        dimension = serializers.ChoiceField(help_text="收敛时间窗口", required=True, choices=DIMENSION_CHOICE)
        value = serializers.ListField(child=serializers.CharField(), required=True)

    CONVERGE_FUNCTION_CHOICES: list[tuple[str, str]] = [(key, value) for key, value in CONVERGE_FUNCTION.items()]

    is_enabled = serializers.BooleanField(label="是否启用防御", default=True)
    converge_func = serializers.ChoiceField(
        help_text="收敛函数", choices=CONVERGE_FUNCTION_CHOICES, default="skip_when_exceed"
    )
    timedelta = serializers.IntegerField(required=False, help_text="收敛时间窗口", default=60, min_value=0)
    count = serializers.IntegerField(required=False, help_text="收敛数量", default=1, min_value=1)
    condition = serializers.ListField(
        required=False,
        child=ConditionSlz(),
        help_text="收敛条件",
        default=[
            {"dimension": "strategy_id", "value": ["self"]},
        ],
    )


@final
class ConvergeConfigSlz(ConvergeConfigDetailSlz):
    """
    一级收敛：包含二级收敛的内容
    二级收敛的优先级 > 一级收敛
    """

    sub_converge_config = ConvergeConfigDetailSlz(required=False)
    need_biz_converge = serializers.BooleanField(required=False, default=True, help_text="是否需要业务汇总")


@final
class NoiseReduceConfigSlz(serializers.Serializer):
    """
    降噪收敛配置
    """

    is_enabled = serializers.BooleanField(required=False, default=False, help_text="是否开启降噪")
    dimensions = serializers.ListField(child=serializers.CharField(), help_text="降噪的对比维度", required=False)
    count = serializers.IntegerField(help_text="降噪阈值", allow_null=True, required=False)
    unit = serializers.CharField(default="percent")
    timedelta = serializers.IntegerField(default=NOISE_REDUCE_TIMEDELTA, help_text="降噪时间窗口, 单位（min）")

    @override
    def run_validation(self, data: Any = empty) -> Any:
        """
        根据is_enable进行参数是否必填校验
        """
        is_empty_value, _data = self.validate_empty_values(data)  # pyright: ignore[reportUnknownVariableType]
        if is_empty_value:
            return _data  # pyright: ignore[reportUnknownVariableType]
        _data = cast(dict[str, Any], _data)
        if is_empty_value:
            return _data
        if _data.get("is_enabled") and not (_data.get("dimensions") and _data.get("count")):
            raise ValidationError(detail="已开启降噪，请填写正确的维度信息和降噪阈值")
        return super().run_validation(_data)  # pyright: ignore[reportArgumentType,reportUnknownVariableType]


@final
class UpgradeConfigSlz(serializers.Serializer):
    is_enabled = serializers.BooleanField(help_text="是否开启", default=False)
    upgrade_interval = serializers.IntegerField(help_text="升级间隔", default=24 * 60)
    user_groups = serializers.ListField(child=serializers.IntegerField(), default=[])

    @override
    def run_validation(self, data: Any = empty) -> Any:
        """
        根据is_enable进行参数是否必填校验
        """
        is_empty_value, _data = self.validate_empty_values(data)  # pyright: ignore[reportUnknownVariableType]
        _data = cast(dict[str, Any], _data)
        if is_empty_value:
            return _data
        if _data.get("is_enabled") and not (_data.get("upgrade_interval") and _data.get("user_groups")):
            raise ValidationError(detail="已开启通知升级配置，请填写正确的升级时间间隔和升级通知组成员")
        return super().run_validation(_data)  # pyright: ignore[reportArgumentType,reportUnknownVariableType]


@final
class PollModeConfig(serializers.Serializer):
    need_poll = serializers.BooleanField(required=False, default=True)
    notify_interval = serializers.IntegerField(required=False, min_value=60, default=60 * 60)
    interval_notify_mode = serializers.ChoiceField(
        required=False,
        default=IntervalNotifyMode.STANDARD,
        choices=IntervalNotifyMode.CHOICES,
    )


@final
class TemplateSerializer(serializers.Serializer):
    signal = serializers.ChoiceField(label="触发信号", required=True, choices=ActionSignal.ACTION_SIGNAL_CHOICE)
    message_tmpl = serializers.CharField(required=False, allow_blank=True, default="")
    title_tmpl = serializers.CharField(required=False, allow_blank=True, default="")

    @staticmethod
    def validate_title_tmpl(value: str) -> str:
        try:
            jinja2_environment(autoescape=False, escape_func=None).from_string(value).render({})
        except TemplateSyntaxError:
            raise serializers.ValidationError("通知自定义标题格式不正确，请重新确认") from None
        return value

    @staticmethod
    def validate_message_tmpl(value: str) -> str:
        try:
            jinja2_environment(autoescape=False, escape_func=None).from_string(value).render({})
        except TemplateSyntaxError:
            raise serializers.ValidationError("通知自定义内容格式不正确，请重新确认") from None
        return value


@final
class NotifyActionConfigSlz(PollModeConfig):
    """通知动作配置序列化器"""

    template = TemplateSerializer(label="通知模板配置", many=True)
    # 多通知组对应多个语音接收组，默认并行通知，设置serial则合并接收组后通知一次
    voice_notice = serializers.ChoiceField(
        label="语音通知模式",
        required=False,
        default=VoiceNoticeMode.PARALLEL,
        choices=[(VoiceNoticeMode.PARALLEL, "PARALLEL"), (VoiceNoticeMode.SERIAL, "SERIAL")],
    )
