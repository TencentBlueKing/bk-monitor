"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from django.utils.translation import gettext as _

from rest_framework import serializers
from apm_web.handlers import metric_group
from apm_web.metric.constants import ProcessorHookType
from apm_web.serializers import ComponentInstanceIdDynamicField
from bkmonitor.data_source import conditions_to_q, filter_dict_to_conditions, q_to_dict
from constants.apm import MetricTemporality, CallSide


__all__ = [
    "CalculateByRangeRequestSerializer",
    "GetFieldOptionValuesRequestSerializer",
    "QueryDimensionsByLimitRequestSerializer",
    "DynamicUnifyQueryRequestSerializer",
]


class MetricFilterMergeSerializer(serializers.Serializer):
    filter_dict = serializers.DictField(label="过滤条件", required=False, default={})
    where = serializers.ListField(label="过滤条件", required=False, default=[], child=serializers.DictField())

    def validate(self, attrs):
        # 合并查询条件
        attrs["filter_dict"] = q_to_dict(
            conditions_to_q(filter_dict_to_conditions(attrs.get("filter_dict") or {}, attrs.get("where") or []))
        )
        return attrs


class MetricGroupOptionsSerializer(serializers.Serializer):
    class TrpcSerializer(serializers.Serializer):
        kind = serializers.ChoiceField(label="调用类型", choices=CallSide.choices(), required=True)
        temporality = serializers.ChoiceField(label="时间性", required=True, choices=MetricTemporality.choices())

    trpc = TrpcSerializer(label="tRPC 配置", required=False)


class MetricGroupByLimitSerializer(MetricFilterMergeSerializer):
    limit = serializers.IntegerField(label="查询数量", default=10, required=False)
    method = serializers.ChoiceField(
        label="计算类型",
        required=False,
        default=metric_group.CalculationType.TOP_N.value,
        choices=[metric_group.CalculationType.TOP_N.value, metric_group.CalculationType.BOTTOM_N.value],
    )
    metric_group_name = serializers.ChoiceField(label="指标组", required=True, choices=metric_group.GroupEnum.choices())
    metric_cal_type = serializers.ChoiceField(
        label="指标计算类型", required=True, choices=metric_group.CalculationType.choices()
    )
    options = MetricGroupOptionsSerializer(label="配置", required=False, default={})
    enabled = serializers.BooleanField(label="是否可用", required=False, default=True)


class DynamicUnifyQueryRequestSerializer(serializers.Serializer):
    class ProcessorSerializer(serializers.Serializer):
        hook = serializers.ChoiceField(label="处理器钩子", required=True, choices=ProcessorHookType.choices())
        name = serializers.CharField(label="处理器名称", required=True)
        options = serializers.DictField(label="处理器参数", required=False, default={})

    app_name = serializers.CharField(label="应用名称")
    service_name = serializers.CharField(label="服务名称", default=False)
    unify_query_param = serializers.DictField(label="unify-query参数")
    bk_biz_id = serializers.IntegerField(label="业务ID")
    start_time = serializers.IntegerField(label="开始时间")
    end_time = serializers.IntegerField(label="结束时间")
    component_instance_id = ComponentInstanceIdDynamicField(required=False, label="组件实例id(组件页面下有效)")
    unit = serializers.CharField(label="图表单位(多指标计算时手动返回)", default=False)
    fill_bar = serializers.BooleanField(label="是否需要补充柱子(用于特殊配置的场景 仅影响 interval)", required=False)
    processors = serializers.ListField(label="处理器列表", child=ProcessorSerializer(), required=False, default=[])
    alias_prefix = serializers.ChoiceField(label="动态主被调当前值", choices=CallSide.choices(), required=False)
    alias_suffix = serializers.CharField(label="动态 alias 后缀", required=False)
    extra_filter_dict = serializers.DictField(label="额外查询条件", required=False, default={})
    group_by_limit = MetricGroupByLimitSerializer(label="聚合排序", required=False)

    # 预处理参数
    hook_processors = serializers.DictField(label="每个 hook 对应的处理器列表", required=False, default={})

    def validate(self, attrs):
        hook_processors: dict[str, Any] = {}
        for processor in attrs.get("processors") or []:
            hook_processors.setdefault(processor["hook"], []).append(processor)

        attrs["hook_processors"] = hook_processors
        return attrs


class GetFieldOptionValuesRequestSerializer(MetricFilterMergeSerializer):
    bk_biz_id = serializers.IntegerField(label="业务ID")
    app_name = serializers.CharField(label="应用名称")
    start_time = serializers.IntegerField(label="开始时间", required=False)
    end_time = serializers.IntegerField(label="结束时间", required=False)
    limit = serializers.IntegerField(label="查询数量", default=10000, required=False)
    field = serializers.CharField(label="字段")
    metric_field = serializers.CharField(label="指标")


class CalculateByRangeRequestSerializer(MetricFilterMergeSerializer):
    ZERO_TIME_SHIFT: str = "0s"

    bk_biz_id = serializers.IntegerField(label="业务ID")
    app_name = serializers.CharField(label="应用名称")
    metric_group_name = serializers.ChoiceField(label="指标组", required=True, choices=metric_group.GroupEnum.choices())
    metric_cal_type = serializers.ChoiceField(
        label="指标计算类型", required=True, choices=metric_group.CalculationType.choices()
    )

    baseline = serializers.CharField(label="对比基准", required=False, default=ZERO_TIME_SHIFT)
    time_shifts = serializers.ListSerializer(
        label="时间偏移", required=False, default=[], child=serializers.CharField()
    )
    group_by = serializers.ListSerializer(label="聚合字段", required=False, default=[], child=serializers.CharField())
    options = MetricGroupOptionsSerializer(label="配置", required=False, default={})
    start_time = serializers.IntegerField(label="开始时间", required=False)
    end_time = serializers.IntegerField(label="结束时间", required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        attrs["time_shifts"] = list(set(attrs["time_shifts"]))
        if self.ZERO_TIME_SHIFT not in attrs["time_shifts"]:
            attrs["time_shifts"].append(self.ZERO_TIME_SHIFT)

        # 当前时间不计入对比次数
        if len(attrs["time_shifts"]) > 3:
            raise ValueError(_("最多支持两次时间对比"))

        return attrs


class QueryDimensionsByLimitRequestSerializer(MetricFilterMergeSerializer):
    bk_biz_id = serializers.IntegerField(label="业务ID")
    app_name = serializers.CharField(label="应用名称")
    limit = serializers.IntegerField(label="查询数量", default=10, required=False)
    filter_dict = serializers.DictField(label="过滤条件", required=False, default={})
    where = serializers.ListField(label="过滤条件", required=False, default=[], child=serializers.DictField())
    group_by = serializers.ListSerializer(label="聚合字段", required=False, default=[], child=serializers.CharField())
    method = serializers.ChoiceField(
        label="计算类型",
        required=False,
        default=metric_group.CalculationType.TOP_N.value,
        choices=[metric_group.CalculationType.TOP_N.value, metric_group.CalculationType.BOTTOM_N.value],
    )
    metric_group_name = serializers.ChoiceField(label="指标组", required=True, choices=metric_group.GroupEnum.choices())
    metric_cal_type = serializers.ChoiceField(
        label="指标计算类型", required=True, choices=metric_group.CalculationType.choices()
    )
    time_shift = serializers.CharField(label="时间偏移", required=False)
    start_time = serializers.IntegerField(label="开始时间", required=False)
    end_time = serializers.IntegerField(label="结束时间", required=False)
    options = MetricGroupOptionsSerializer(label="配置", required=False, default={})
    with_filter_dict = serializers.BooleanField(label="是否提供过滤条件", required=False, default=False)
