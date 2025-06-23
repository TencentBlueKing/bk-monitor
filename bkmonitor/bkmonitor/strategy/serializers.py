"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext as _
from rest_framework import serializers

from bkmonitor.dataflow.constant import VisualType
from core.errors.alarm_backends.detect import (
    InvalidAdvancedRingRatioConfig,
    InvalidAdvancedYearRoundConfig,
    InvalidSimpleRingRatioConfig,
    InvalidSimpleYearRoundConfig,
)

allowed_threshold_method = {
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "eq": "==",
    "neq": "!=",
}

allowed_method = {
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "eq": "==",
}


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

    def validate(self, attrs):
        floor = attrs["floor"]
        floor_interval = attrs["floor_interval"]
        ceil = attrs["ceil"]
        ceil_interval = attrs["ceil_interval"]
        # 校验历史数据获取类型
        fetch_type = attrs["fetch_type"]
        if fetch_type not in ["avg", "last"]:
            raise InvalidAdvancedYearRoundConfig(config=attrs)

        floor_configured = all([floor, floor_interval])
        ceil_configured = all([ceil, ceil_interval])
        if not floor_configured:
            attrs["floor"] = None
            attrs["floor_interval"] = None
        if not ceil_configured:
            attrs["ceil"] = None
            attrs["ceil_interval"] = None
        if not any([ceil_configured, floor_configured]):
            raise InvalidAdvancedYearRoundConfig(config=attrs)
        return attrs


class AdvancedRingRatioSerializer(AdvancedYearRoundSerializer):
    """
    高级环比算法serializer,复用高级同比算法serializer
    """

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except InvalidAdvancedYearRoundConfig:
            raise InvalidAdvancedRingRatioConfig(config=attrs)


class RingRatioAmplitudeSerializer(serializers.Serializer):
    """
    环比振幅算法serializer
    """

    ratio = serializers.FloatField(required=True)
    shock = serializers.FloatField(required=True)
    threshold = serializers.FloatField(required=True)


class SimpleRingRatioSerializer(serializers.Serializer):
    """
    简单环比算法serializer
    """

    floor = serializers.FloatField(required=True, allow_null=True, min_value=0)
    ceil = serializers.FloatField(required=True, allow_null=True, min_value=0)

    def validate(self, attrs):
        floor = attrs["floor"]
        ceil = attrs["ceil"]
        if not any([floor, ceil]):
            raise InvalidSimpleRingRatioConfig(config=attrs)
        return attrs


class SimpleYearRoundSerializer(SimpleRingRatioSerializer):
    """
    简单同比算法serializer
    """

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except InvalidSimpleRingRatioConfig:
            raise InvalidSimpleYearRoundConfig(config=attrs)


class ThresholdSerializer(serializers.ListSerializer):
    """
    静态阈值算法serializer
    """

    class AndSerializer(serializers.ListSerializer):
        class UnitSerializer(serializers.Serializer):
            threshold = serializers.FloatField(required=True)
            method = serializers.ChoiceField(required=True, choices=list(allowed_threshold_method.keys()))

        child = UnitSerializer()

    child = AndSerializer(allow_empty=False)


class IntelligentDetectSerializer(serializers.Serializer):
    """
    智能异常检测算法serializer
    """

    args = serializers.DictField(required=True)
    plan_id = serializers.IntegerField(required=True)
    visual_type = serializers.ChoiceField(
        default=VisualType.NONE, choices=[VisualType.NONE, VisualType.SCORE, VisualType.BOUNDARY]
    )
    service_name = serializers.CharField(label="service环境选择", required=False, default="default")


class TimeSeriesForecastingSerializer(serializers.Serializer):
    """
    时序预测算法serializer
    """

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


class AbnormalClusterSerializer(serializers.Serializer):
    """
    离群检测检测算法serializer
    """

    args = serializers.DictField(default=dict)
    plan_id = serializers.IntegerField(required=True)
    group = serializers.ListSerializer(allow_empty=True, child=serializers.CharField(), default=list)
    visual_type = serializers.ChoiceField(default=VisualType.NONE, choices=[VisualType.NONE])


class YearRoundAmplitudeSerializer(serializers.Serializer):
    """
    同比振幅算法
    """

    ratio = serializers.FloatField(required=True)
    shock = serializers.FloatField(required=True)
    days = serializers.IntegerField(required=True, min_value=1)
    method = serializers.ChoiceField(required=True, choices=list(allowed_method.keys()))


# 同比区间serializer与同比振幅算法配置格式一致
YearRoundRangeSerializer = YearRoundAmplitudeSerializer


class MultivariateAnomalyDetectionSerializer(serializers.Serializer):
    """
    智能AI多指标异常检测算法
    目前只有host场景，无需传入指标值，由数据平台算法的智能指标组成
    """

    class MetricListSerializer(serializers.ListSerializer):
        class MetricSerializer(serializers.Serializer):
            metric_id = serializers.CharField(required=True, label="指标ID")
            name = serializers.CharField(required=True, label="指标中文名")
            unit = serializers.CharField(required=True, label="单位")
            metric_name = serializers.CharField(required=True, label="指标英文名")

        child = MetricSerializer()

    scene_id = serializers.CharField(required=True, label="场景")
    metrics = MetricListSerializer(allow_empty=True, label="指标数据")


class HostAnomalyDetectionSerializer(MultivariateAnomalyDetectionSerializer):
    """
    智能AI主机异常检测算法
    目前只有host场景，无需传入指标值，由数据平台算法的智能指标组成
    """

    levels = serializers.ListField(required=True, label="告警级别列表")
    sensitivity = serializers.IntegerField(required=True, label="告警敏感度")


class QueryConfigSerializer(serializers.Serializer):
    """
    查询配置序列化器基类
    """

    functions = serializers.ListField(label="计算函数", default=[])
    intelligent_detect = serializers.DictField(label="智能监控配置", required=False)

    _config_field_names = None

    @classmethod
    def get_config_field_names(cls):
        if cls._config_field_names is None:
            cls._config_field_names = list(cls().fields.keys())
        return cls._config_field_names


class TimeSeriesQueryConfigSerializer(QueryConfigSerializer):
    result_table_id = serializers.CharField(required=False, label="结果表", allow_blank=True)
    data_label = serializers.CharField(required=False, label="db标识", allow_blank=True)
    agg_method = serializers.CharField(label="聚合方法")
    agg_interval = serializers.IntegerField(label="聚合周期", min_value=0)
    agg_dimension = serializers.ListField(
        label="聚合维度",
        allow_empty=True,
    )
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())
    metric_field = serializers.CharField(label="指标")
    unit = serializers.CharField(label="单位", allow_blank=True, default="")


class BkMonitorTimeSeriesSerializer(TimeSeriesQueryConfigSerializer):
    origin_config = serializers.DictField(label="原始配置", required=False)
    values = serializers.ListField(required=False)


class BkMonitorLogSerializer(QueryConfigSerializer):
    result_table_id = serializers.CharField(label="结果表")
    agg_method = serializers.CharField(label="聚合方法")
    agg_interval = serializers.IntegerField(label="聚合周期", min_value=0)
    agg_dimension = serializers.ListField(allow_empty=True)
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())


class BkMonitorEventSerializer(QueryConfigSerializer):
    result_table_id = serializers.CharField(label="结果表")
    metric_field = serializers.CharField(label="指标")
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())


class BkLogSearchTimeSeriesSerializer(TimeSeriesQueryConfigSerializer):
    query_string = serializers.CharField(label="查询语句", required=False)
    index_set_id = serializers.IntegerField(label="索引集ID")
    result_table_id = serializers.CharField(label="索引", allow_blank=True)
    time_field = serializers.CharField(label="时间字段", default="dtEventTimeStamp", allow_blank=True, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("time_field"):
            attrs["time_field"] = "dtEventTimeStamp"
        return attrs


class BkLogSearchLogSerializer(QueryConfigSerializer):
    query_string = serializers.CharField(label="查询语句")
    result_table_id = serializers.CharField(label="索引", allow_blank=True)
    index_set_id = serializers.IntegerField(label="索引集ID")
    agg_interval = serializers.IntegerField(label="聚合周期", min_value=0)
    agg_dimension = serializers.ListField(
        label="聚合维度",
        allow_empty=True,
    )
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())
    time_field = serializers.CharField(label="时间字段", default="dtEventTimeStamp", allow_blank=True, allow_null=True)

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("time_field"):
            attrs["time_field"] = "dtEventTimeStamp"
        return attrs


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

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("time_field"):
            attrs["time_field"] = "dtEventTimeStamp"
        return attrs


class BkFtaEventSerializer(QueryConfigSerializer):
    alert_name = serializers.CharField(label="告警名称")
    agg_dimension = serializers.ListField(allow_empty=True)
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())
    agg_method = serializers.CharField(label="聚合方法")
    agg_interval = serializers.IntegerField(label="聚合周期", min_value=0)


class BkFtaAlertSerializer(QueryConfigSerializer):
    alert_name = serializers.CharField(label="告警名称")
    agg_dimension = serializers.ListField(allow_empty=True)
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())


class BkMonitorAlertSerializer(QueryConfigSerializer):
    bkmonitor_strategy_id = serializers.IntegerField(label="监控策略ID")
    agg_dimension = serializers.ListField(allow_empty=True)
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())


class BkApmTimeSeriesSerializer(TimeSeriesForecastingSerializer):
    result_table_id = serializers.CharField(label="索引", allow_blank=True)


class BkApmTraceSerializer(QueryConfigSerializer):
    query_string = serializers.CharField(label="查询语句")
    result_table_id = serializers.CharField(label="索引", allow_blank=True)
    agg_interval = serializers.IntegerField(label="聚合周期", min_value=0)
    agg_dimension = serializers.ListField(
        label="聚合维度",
        allow_empty=True,
    )
    agg_condition = serializers.ListField(label="查询条件", allow_empty=True, child=serializers.DictField())
    metric_field = serializers.CharField(label="指标")
    time_field = serializers.CharField(label="时间字段", default="dtEventTimeStamp", allow_blank=True, allow_null=True)


class PrometheusTimeSeriesSerializer(QueryConfigSerializer):
    promql = serializers.CharField(label="查询表达式")
    agg_interval = serializers.IntegerField(label="聚合周期", min_value=0)


class GrafanaTimeSeriesSerializer(QueryConfigSerializer):
    dashboard_uid = serializers.CharField(label="dashboard uid")
    panel_id = serializers.IntegerField(label="panel id")
    ref_id = serializers.CharField(label="ref id")
    variables = serializers.DictField(label="变量", default={})
    snapshot_config = serializers.JSONField(label="快照配置", default={})


class NoticeGroupSerializer(serializers.Serializer):
    class NoticeReceiverSerializer(serializers.Serializer):
        id = serializers.CharField(required=True, label="通知对象ID")
        type = serializers.ChoiceField(
            required=True, choices=(("user", _("用户")), ("group", _("用户组"))), label="通知对象类别"
        )

    bk_biz_id = serializers.IntegerField(required=False, default=0, label="业务ID")
    name = serializers.CharField(required=True, max_length=128, label="通知组名称")
    notice_receiver = NoticeReceiverSerializer(required=True, many=True, label="通知对象")
    message = serializers.CharField(required=False, allow_blank=True, label="说明")
    notice_way = serializers.DictField(required=True, label="各级别对应的通知方式")
    wxwork_group = serializers.DictField(required=False, default={})
    webhook_url = serializers.CharField(required=False, allow_blank=True, default="", label="回调地址")
    id = serializers.IntegerField(required=False, label="修改对应的通知组ID列表")

    def validate_notice_way(self, value):
        if any(value.values()):
            return value
        raise serializers.ValidationError(_("通知方式至少开启一项"))
