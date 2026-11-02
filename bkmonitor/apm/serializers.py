"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rest_framework import serializers
from django.utils.translation import gettext as _

from apm.constants import (
    ACTIVE_PROFILING_QUERY_SOURCES,
    ACTIVE_PROFILING_STATUSES,
    ACTIVE_PROFILING_TOPK_FIELDS,
    QueryMode,
)
from constants.apm import OperatorGroupRelation
from constants.otel_query import EnabledStatisticsDimension, StatisticsProperty


class FilterSerializer(serializers.Serializer):
    class OptionsSerializer(serializers.Serializer):
        is_wildcard = serializers.BooleanField(label="是否使用通配符", default=False)
        group_relation = serializers.ChoiceField(
            label="分组关系", choices=OperatorGroupRelation.choices(), default=OperatorGroupRelation.OR
        )

    key = serializers.CharField(label="查询键")
    operator = serializers.CharField(label="操作符")
    value = serializers.ListSerializer(label="查询值", child=serializers.CharField(allow_blank=True), allow_empty=True)
    options = OptionsSerializer(label="操作符选项", default={})


class BaseTraceRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    app_name = serializers.CharField(label="应用名称")
    is_mock = serializers.BooleanField(label="是否使用mock数据", required=False, default=False)


class BaseTraceFilterSerializer(serializers.Serializer):
    filters = serializers.ListSerializer(label="查询条件", child=FilterSerializer(), default=[])
    query_string = serializers.CharField(label="查询字符串", allow_blank=True)
    mode = serializers.ChoiceField(label="查询视角", choices=QueryMode.choices())
    start_time = serializers.IntegerField(label="开始时间")
    end_time = serializers.IntegerField(label="结束时间")


class TraceFieldsTopkRequestSerializer(BaseTraceRequestSerializer, BaseTraceFilterSerializer):
    fields = serializers.ListField(child=serializers.CharField(), label="查询字段列表")
    limit = serializers.IntegerField(label="数量限制", required=False, default=5)


class TraceStatisticsFieldSerializer(serializers.Serializer):
    field_type = serializers.ChoiceField(label="字段类型", choices=EnabledStatisticsDimension.choices())
    field_name = serializers.CharField(label="字段名称")
    values = serializers.ListField(label="查询过滤条件值列表", required=False, allow_empty=True, default=[])


class TraceFieldStatisticsInfoRequestSerializer(BaseTraceRequestSerializer, BaseTraceFilterSerializer):
    field = TraceStatisticsFieldSerializer(label="字段")
    exclude_property = serializers.ListSerializer(
        label="排除属性", child=serializers.ChoiceField(choices=StatisticsProperty.choices()), default=[]
    )


class TraceFieldStatisticsGraphRequestSerializer(BaseTraceRequestSerializer, BaseTraceFilterSerializer):
    field = TraceStatisticsFieldSerializer(label="字段")
    query_method = serializers.CharField(label="查询方法", required=False)
    time_alignment = serializers.BooleanField(label="是否对齐时间", required=False, default=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        time_alignment: bool = attrs.get("time_alignment", False)
        attrs["query_method"] = ("query_reference", "query_data")[time_alignment]
        field = attrs["field"]
        if not EnabledStatisticsDimension.from_value(field["field_type"]).is_numeric():
            return attrs
        if len(field["values"]) < 4:
            raise ValueError(_("数值类型查询条件不足"))
        return attrs


class ActiveProfilingTimeRangeSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    start_time = serializers.IntegerField(label="计划时间起点")
    end_time = serializers.IntegerField(label="计划时间终点")

    def validate(self, attrs):
        if attrs["start_time"] > attrs["end_time"]:
            raise serializers.ValidationError("start_time 不能大于 end_time")
        return attrs


class ActiveProfilingListFiltersSerializer(serializers.Serializer):
    ips = serializers.ListField(label="IP 筛选", child=serializers.CharField(), required=False)
    task_id = serializers.IntegerField(label="任务 ID", min_value=1, required=False)
    task_name = serializers.CharField(label="任务名称关键词", required=False, allow_blank=True)
    process_names = serializers.ListField(label="进程名筛选", child=serializers.CharField(), required=False)
    process_pids = serializers.ListField(label="PID 筛选", child=serializers.CharField(), required=False)
    schedule_types = serializers.ListField(label="执行方式筛选", child=serializers.CharField(), required=False)
    collection_methods = serializers.ListField(label="采集方式筛选", child=serializers.CharField(), required=False)
    collection_types = serializers.ListField(label="采集类型筛选", child=serializers.CharField(), required=False)
    status = serializers.ChoiceField(
        label="执行状态", choices=ACTIVE_PROFILING_STATUSES, required=False, allow_blank=True
    )


class ActiveProfilingQuerySourceSerializer(serializers.Serializer):
    source = serializers.ChoiceField(label="查询数据源", choices=ACTIVE_PROFILING_QUERY_SOURCES, default="mysql")


class ActiveProfilingListRequestSerializer(ActiveProfilingTimeRangeSerializer, ActiveProfilingQuerySourceSerializer):
    filters = ActiveProfilingListFiltersSerializer(label="筛选条件", required=False)
    offset = serializers.IntegerField(label="滚动偏移", min_value=0, default=0)
    limit = serializers.IntegerField(label="每页数量", min_value=1, default=20)


class ActiveProfilingTopKRequestSerializer(ActiveProfilingTimeRangeSerializer, ActiveProfilingQuerySourceSerializer):
    field = serializers.ChoiceField(label="候选字段", choices=ACTIVE_PROFILING_TOPK_FIELDS)
    limit = serializers.IntegerField(label="返回数量", min_value=1, default=20)
    keyword = serializers.CharField(label="候选关键字", required=False, allow_blank=True)


class ActiveProfilingExecutionKeySerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    # 前端不给立即执行传 task_id，按立即执行与计划时间定位
    task_id = serializers.IntegerField(label="任务 ID", required=False)
    scheduled_at = serializers.IntegerField(label="执行计划时间")


class ActiveProfilingExecutionDetailRequestSerializer(
    ActiveProfilingExecutionKeySerializer, ActiveProfilingQuerySourceSerializer
):
    pass


class ActiveProfilingExecutionCancelRequestSerializer(ActiveProfilingExecutionKeySerializer):
    class HostSerializer(serializers.Serializer):
        bk_host_id = serializers.IntegerField(label="主机 ID")
        ip = serializers.CharField(label="主机 IP")

    hosts = serializers.ListField(label="待取消主机", child=HostSerializer(), allow_empty=False)


class ActiveProfilingExecutionRenameRequestSerializer(ActiveProfilingExecutionKeySerializer):
    task_name = serializers.CharField(label="任务名称", max_length=128)


class ActiveProfilingTaskListRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    page = serializers.IntegerField(label="页码", min_value=1, default=1)
    page_size = serializers.IntegerField(label="每页数量", min_value=1, default=20)


class ActiveProfilingTaskSubmitRequestSerializer(serializers.Serializer):
    """配置由 SaaS 按前端协议校验后转发，这里只校验结构"""

    bk_biz_id = serializers.IntegerField(label="业务 ID")
    name = serializers.CharField(label="任务名称", max_length=128)
    collection_method = serializers.CharField(label="采集方式")
    collection_type = serializers.CharField(label="采集类型")
    target_config = serializers.DictField(label="目标主机配置")
    # Golang 不传 process_selector
    process_selector = serializers.DictField(label="进程选择器", required=False)
    schedule = serializers.DictField(label="调度配置")
    collector_config = serializers.DictField(label="采集参数")
    resource_guard_config = serializers.DictField(label="资源保护参数")


class ActiveProfilingTaskEditRequestSerializer(ActiveProfilingTaskSubmitRequestSerializer):
    task_id = serializers.IntegerField(label="任务 ID")


class ActiveProfilingTaskRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    task_id = serializers.IntegerField(label="任务 ID")


class ActiveProfilingTaskSwitchRequestSerializer(ActiveProfilingTaskRequestSerializer):
    enabled = serializers.BooleanField(label="是否启用")
