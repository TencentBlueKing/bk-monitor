"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re

import pytz
from celery.schedules import ParseException, crontab
from rest_framework import serializers

from apm_web.profile.active_collection.constants import (
    COLLECTOR_MAX_DURATION_SEC,
    COLLECTION_METHOD_CHOICES,
    COLLECTION_TYPE_CHOICES,
    COLLECTION_TYPES_BY_METHOD,
    DIAGRAM_TYPE_CHOICES,
    EXECUTION_STATUS_CHOICES,
    TOPK_FIELDS,
    PLANNED_SCHEDULE_TYPE_CHOICES,
    PROCESS_SELECTOR_MAX_HOST_PIDS,
    PROCESS_SELECTOR_MAX_PID_PATH_LENGTH,
    PROCESS_SELECTOR_MAX_PID_PATHS,
    PROCESS_SELECTOR_MAX_PIDS,
    PROCESS_SELECTOR_MAX_TEXT_LENGTH,
    PROCESS_SELECTOR_SEPARATOR,
    PROCESS_SELECTOR_TYPE_CHOICES,
    SCHEDULE_TYPE_CHOICES,
    STACK_UNWIND_CHOICES,
)


class IsMockSerializer(serializers.Serializer):
    is_mock = serializers.BooleanField(label="是否返回 mock", required=False, default=False)


class MetaConfigRequestSerializer(IsMockSerializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")


class TargetConfigSerializer(serializers.Serializer):
    class NodeSerializer(serializers.Serializer):
        bk_host_id = serializers.IntegerField(label="主机 ID")

    node_type = serializers.CharField(label="节点类型")
    nodes = serializers.ListField(label="目标节点", child=NodeSerializer(), allow_empty=False)


class ResourceGuardConfigSerializer(serializers.Serializer):
    auto_stop_on_resource_pressure = serializers.BooleanField(label="资源压力自动停止")
    max_disk_usage = serializers.IntegerField(label="采集临时文件最大占用(MB)", min_value=0)
    min_mem_level = serializers.IntegerField(label="可用内存停止阈值(MB)", min_value=0)


class BaseScheduleSerializer(serializers.Serializer):
    timezone = serializers.CharField(label="时区")

    def validate_timezone(self, value):
        try:
            pytz.timezone(value)
        except pytz.exceptions.UnknownTimeZoneError:
            raise serializers.ValidationError("timezone is invalid")
        return value


class ScheduleSerializer(serializers.Serializer):
    class ImmediateScheduleSerializer(BaseScheduleSerializer):
        type = serializers.ChoiceField(label="调度类型", choices=(("immediate", "immediate"),))
        execute_at = serializers.IntegerField(label="执行时间")

    class OnceAtScheduleSerializer(BaseScheduleSerializer):
        type = serializers.ChoiceField(label="调度类型", choices=(("once_at", "once_at"),))
        execute_at = serializers.IntegerField(label="执行时间")

    class CronScheduleSerializer(BaseScheduleSerializer):
        type = serializers.ChoiceField(label="调度类型", choices=(("cron", "cron"),))
        cron_expression = serializers.CharField(label="Cron 表达式")
        effective_start_at = serializers.IntegerField(label="生效开始时间", required=False)
        effective_end_at = serializers.IntegerField(label="生效结束时间", required=False)

        def validate_cron_expression(self, value):
            fields = value.split()
            if len(fields) != 5:
                raise serializers.ValidationError("cron_expression must contain exactly 5 fields")

            minute, hour, day_of_month, month_of_year, day_of_week = fields
            try:
                crontab(
                    minute=minute,
                    hour=hour,
                    day_of_week=day_of_week,
                    day_of_month=day_of_month,
                    month_of_year=month_of_year,
                )
            except (ParseException, ValueError):
                raise serializers.ValidationError("cron_expression is invalid")
            return value

        def validate(self, attrs):
            start_at = attrs.get("effective_start_at")
            end_at = attrs.get("effective_end_at")
            if start_at is not None and end_at is not None and end_at < start_at:
                raise serializers.ValidationError("结束时间不能早于开始时间")
            return attrs

    TYPE_SERIALIZER_MAP = {
        "immediate": ImmediateScheduleSerializer,
        "once_at": OnceAtScheduleSerializer,
        "cron": CronScheduleSerializer,
    }

    type = serializers.ChoiceField(label="调度类型", choices=SCHEDULE_TYPE_CHOICES)

    def to_internal_value(self, data):
        ret = super().to_internal_value(data)
        serializer = self.TYPE_SERIALIZER_MAP[ret["type"]](data=data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


class PlannedScheduleSerializer(ScheduleSerializer):
    TYPE_SERIALIZER_MAP = {
        "once_at": ScheduleSerializer.OnceAtScheduleSerializer,
        "cron": ScheduleSerializer.CronScheduleSerializer,
    }

    type = serializers.ChoiceField(label="调度类型", choices=PLANNED_SCHEDULE_TYPE_CHOICES)


def _split_selector_values(value):
    """按分号拆分 pid_path / pids，去掉首尾空白与空项；采集端按同样的规则拆分"""
    return [item.strip() for item in value.split(PROCESS_SELECTOR_SEPARATOR) if item.strip()]


class HostPidSerializer(serializers.Serializer):
    bk_host_id = serializers.IntegerField(label="主机 ID")
    pid = serializers.IntegerField(label="进程 PID", min_value=1)


class ProcessSelectorSerializer(serializers.Serializer):
    class CommandMatchConfigSerializer(serializers.Serializer):
        match_pattern = serializers.CharField(label="命令行包含", max_length=PROCESS_SELECTOR_MAX_TEXT_LENGTH)
        exclude_pattern = serializers.CharField(
            label="排除正则", required=False, allow_blank=True, max_length=PROCESS_SELECTOR_MAX_TEXT_LENGTH
        )

        def validate_exclude_pattern(self, value):
            # 采集端按 Go RE2 校验，两边语法集不等价，这里只粗筛明显写错的表达式，
            # lookahead、反向引用等仍由 bkmonitorbeat 拒绝
            try:
                re.compile(value)
            except re.error:
                raise serializers.ValidationError("exclude_pattern is invalid")
            return value

    class PidFileConfigSerializer(serializers.Serializer):
        """采集目标由 PID 文件内容决定，提交与预览都只传路径，多个路径用分号分隔"""

        pid_path = serializers.CharField(label="PID 文件路径", max_length=PROCESS_SELECTOR_MAX_PID_PATH_LENGTH)

        def validate_pid_path(self, value):
            pid_paths = _split_selector_values(value)
            if not pid_paths:
                raise serializers.ValidationError("pid_path 不能为空")
            if len(pid_paths) > PROCESS_SELECTOR_MAX_PID_PATHS:
                raise serializers.ValidationError(f"pid_path 最多 {PROCESS_SELECTOR_MAX_PID_PATHS} 个路径")
            if any(len(pid_path) > PROCESS_SELECTOR_MAX_TEXT_LENGTH for pid_path in pid_paths):
                raise serializers.ValidationError(f"单个路径不能超过 {PROCESS_SELECTOR_MAX_TEXT_LENGTH} 个字符")
            return value

    class PidConfigSerializer(serializers.Serializer):
        """PID 列表下发到每台目标主机，提交与预览都用分号分隔"""

        pids = serializers.CharField(label="进程 PID")

        def validate_pids(self, value):
            pids = _split_selector_values(value)
            if not pids:
                raise serializers.ValidationError("pids 不能为空")
            if len(pids) > PROCESS_SELECTOR_MAX_PIDS:
                raise serializers.ValidationError(f"pids 最多 {PROCESS_SELECTOR_MAX_PIDS} 个")
            # 采集端按 ASCII 十进制解析，全角数字等也要在这里拒绝
            if not all(pid.isascii() and pid.isdigit() and int(pid) > 0 for pid in pids):
                raise serializers.ValidationError("pids 必须是正整数")
            return value

    class CommandConfigSerializer(CommandMatchConfigSerializer):
        enable_dynamic_collection = serializers.BooleanField(label="动态采集")
        host_pids = serializers.ListField(
            label="勾选的进程",
            child=HostPidSerializer(),
            required=False,
            max_length=PROCESS_SELECTOR_MAX_HOST_PIDS,
        )

        def validate(self, attrs):
            # 动态采集每次重新匹配，只按勾选的进程采集时才需要 host_pids，两者互斥
            if attrs["enable_dynamic_collection"]:
                if "host_pids" in attrs:
                    raise serializers.ValidationError("动态采集不能传 host_pids")
            elif not attrs.get("host_pids"):
                raise serializers.ValidationError("关闭动态采集时必须传 host_pids")
            return attrs

    CONFIG_SERIALIZER_MAP = {
        "command": CommandConfigSerializer,
        "pid_file": PidFileConfigSerializer,
        "pid": PidConfigSerializer,
    }

    type = serializers.ChoiceField(label="进程选择类型", choices=PROCESS_SELECTOR_TYPE_CHOICES)
    config = serializers.DictField(label="选择器配置")

    def to_internal_value(self, data):
        ret = super().to_internal_value(data)
        serializer = self.CONFIG_SERIALIZER_MAP[ret["type"]](data=ret["config"])
        serializer.is_valid(raise_exception=True)
        return {"type": ret["type"], "config": serializer.validated_data}


class PreviewProcessSelectorSerializer(ProcessSelectorSerializer):
    """预览只带匹配条件，没有动态采集开关和 host_pids"""

    CONFIG_SERIALIZER_MAP = {
        "command": ProcessSelectorSerializer.CommandMatchConfigSerializer,
        "pid_file": ProcessSelectorSerializer.PidFileConfigSerializer,
        "pid": ProcessSelectorSerializer.PidConfigSerializer,
    }


class NativeCpuCollectorConfigSerializer(serializers.Serializer):
    duration_sec = serializers.IntegerField(label="采集时长(秒)", min_value=1, max_value=COLLECTOR_MAX_DURATION_SEC)
    frequency_hz = serializers.IntegerField(label="采样频率", min_value=1)
    stack_unwind = serializers.ChoiceField(label="栈回溯方式", choices=STACK_UNWIND_CHOICES)


class GoCpuCollectorConfigSerializer(serializers.Serializer):
    ip_address = serializers.CharField(label="pprof 地址")
    port = serializers.IntegerField(label="pprof 端口", min_value=1)
    duration_sec = serializers.IntegerField(label="采集时长(秒)", min_value=1, max_value=COLLECTOR_MAX_DURATION_SEC)


class GoHeapCollectorConfigSerializer(serializers.Serializer):
    ip_address = serializers.CharField(label="pprof 地址")
    port = serializers.IntegerField(label="pprof 端口", min_value=1)


class JavaCollectorConfigSerializer(serializers.Serializer):
    duration_sec = serializers.IntegerField(label="采集时长(秒)", min_value=1, max_value=COLLECTOR_MAX_DURATION_SEC)


class TopKRequestSerializer(IsMockSerializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    start_time = serializers.IntegerField(label="查询开始时间")
    end_time = serializers.IntegerField(label="查询结束时间")
    field = serializers.ChoiceField(label="候选字段", choices=[(field, field) for field in TOPK_FIELDS])
    limit = serializers.IntegerField(label="返回数量", min_value=1, default=20)

    def validate(self, attrs):
        if attrs["start_time"] > attrs["end_time"]:
            raise serializers.ValidationError("start_time 不能大于 end_time")
        return attrs


class EventListFiltersSerializer(serializers.Serializer):
    ips = serializers.ListField(label="IP 筛选", child=serializers.CharField(), required=False)
    task_name = serializers.CharField(label="任务名称关键词", required=False, allow_blank=True)
    process_names = serializers.ListField(label="进程名筛选", child=serializers.CharField(), required=False)
    process_pids = serializers.ListField(label="PID 筛选", child=serializers.CharField(), required=False)
    schedule_types = serializers.ListField(
        label="执行方式筛选",
        child=serializers.ChoiceField(choices=SCHEDULE_TYPE_CHOICES),
        required=False,
    )
    collection_methods = serializers.ListField(
        label="采集方式筛选",
        child=serializers.ChoiceField(choices=COLLECTION_METHOD_CHOICES),
        required=False,
    )
    collection_types = serializers.ListField(
        label="采集类型筛选",
        child=serializers.ChoiceField(choices=COLLECTION_TYPE_CHOICES),
        required=False,
    )
    status = serializers.ChoiceField(
        label="执行状态",
        choices=EXECUTION_STATUS_CHOICES,
        required=False,
        allow_blank=True,
    )


class CancelHostSerializer(serializers.Serializer):
    bk_host_id = serializers.IntegerField(label="主机 ID")
    ip = serializers.CharField(label="主机 IP")


class EnableRequestSerializer(IsMockSerializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")


class ProcessPreviewRequestSerializer(IsMockSerializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    target_config = TargetConfigSerializer(label="目标主机配置")
    process_selector = PreviewProcessSelectorSerializer(label="进程选择器")


class TaskListRequestSerializer(IsMockSerializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    page = serializers.IntegerField(label="页码", min_value=1, default=1)
    page_size = serializers.IntegerField(label="每页数量", min_value=1, default=20)


class TaskSubmitRequestSerializer(IsMockSerializer):
    COLLECTOR_CONFIG_SERIALIZER_MAP = {
        "native_cpu": NativeCpuCollectorConfigSerializer,
        "go_cpu": GoCpuCollectorConfigSerializer,
        "go_heap": GoHeapCollectorConfigSerializer,
        "java_cpu": JavaCollectorConfigSerializer,
        "java_allocation": JavaCollectorConfigSerializer,
    }

    bk_biz_id = serializers.IntegerField(label="业务 ID")
    name = serializers.CharField(label="任务名称", max_length=128)
    collection_method = serializers.ChoiceField(label="采集方式", choices=COLLECTION_METHOD_CHOICES)
    collection_type = serializers.ChoiceField(label="采集类型", choices=COLLECTION_TYPE_CHOICES)
    target_config = TargetConfigSerializer(label="目标主机配置")
    process_selector = ProcessSelectorSerializer(label="进程选择器", required=False)
    schedule = ScheduleSerializer(label="调度配置")
    collector_config = serializers.DictField(label="采集参数")
    resource_guard_config = ResourceGuardConfigSerializer(label="资源保护参数")

    def validate(self, attrs):
        collection_method = attrs["collection_method"]
        collection_type = attrs["collection_type"]
        if collection_type not in COLLECTION_TYPES_BY_METHOD[collection_method]:
            raise serializers.ValidationError("采集类型与采集方式不匹配")

        collector_serializer = self.COLLECTOR_CONFIG_SERIALIZER_MAP[collection_type](data=attrs["collector_config"])
        collector_serializer.is_valid(raise_exception=True)
        attrs["collector_config"] = collector_serializer.validated_data

        process_selector = attrs.get("process_selector")
        if collection_method == "golang":
            if process_selector is not None:
                raise serializers.ValidationError("Golang 不传 process_selector")
        elif process_selector is None:
            raise serializers.ValidationError("Perf/Java 必须传 process_selector")

        # 选择器原样下发到全部目标主机，勾选的进程只能来自这些主机
        if process_selector and "host_pids" in process_selector["config"]:
            pid_host_ids = {item["bk_host_id"] for item in process_selector["config"]["host_pids"]}
            if not pid_host_ids <= {node["bk_host_id"] for node in attrs["target_config"]["nodes"]}:
                raise serializers.ValidationError("host_pids 中的主机必须属于 target_config")

        return attrs


class PlannedTaskSubmitRequestSerializer(TaskSubmitRequestSerializer):
    schedule = PlannedScheduleSerializer(label="调度配置")


class TaskEditRequestSerializer(PlannedTaskSubmitRequestSerializer):
    task_id = serializers.IntegerField(label="任务 ID")


class TaskDeleteRequestSerializer(IsMockSerializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    task_id = serializers.IntegerField(label="任务 ID")


class TaskSwitchRequestSerializer(IsMockSerializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    task_id = serializers.IntegerField(label="任务 ID")
    enabled = serializers.BooleanField(label="是否启用")


class EventListRequestSerializer(IsMockSerializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    start_time = serializers.IntegerField(label="查询开始时间")
    end_time = serializers.IntegerField(label="查询结束时间")
    filters = EventListFiltersSerializer(label="筛选条件", required=False)
    offset = serializers.IntegerField(label="滚动偏移", min_value=0, default=0)
    limit = serializers.IntegerField(label="每页数量", min_value=1, default=20)

    def validate(self, attrs):
        if attrs["start_time"] > attrs["end_time"]:
            raise serializers.ValidationError("start_time 不能大于 end_time")
        return attrs


class ExecutionDetailRequestSerializer(IsMockSerializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    schedule_type = serializers.ChoiceField(label="执行方式", choices=SCHEDULE_TYPE_CHOICES)
    scheduled_at = serializers.IntegerField(label="执行计划时间")
    task_id = serializers.IntegerField(label="任务 ID", required=False)

    def validate(self, attrs):
        if attrs["schedule_type"] == "immediate":
            if "task_id" in attrs:
                raise serializers.ValidationError("immediate 不传 task_id")
        elif "task_id" not in attrs:
            raise serializers.ValidationError("once_at/cron 必须传 task_id")
        return attrs


class ExecutionCancelRequestSerializer(ExecutionDetailRequestSerializer):
    hosts = serializers.ListField(label="待取消主机", child=CancelHostSerializer(), allow_empty=False)


class ResultDataTypesRequestSerializer(IsMockSerializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    scheduled_at = serializers.IntegerField(label="执行计划时间")
    bk_host_id = serializers.IntegerField(label="主机 ID")
    task_id = serializers.IntegerField(label="任务 ID", required=False)
    started_at = serializers.IntegerField(label="主机执行开始时间")
    finished_at = serializers.IntegerField(label="主机执行结束时间")

    def validate(self, attrs):
        if attrs["finished_at"] < attrs["started_at"]:
            raise serializers.ValidationError("finished_at 不能早于 started_at")
        return attrs


class ResultExportRequestSerializer(ResultDataTypesRequestSerializer):
    data_type = serializers.CharField(label="采样类型")


class ResultQueryRequestSerializer(ResultExportRequestSerializer):
    diagram_types = serializers.ListField(
        label="图表类型",
        child=serializers.ChoiceField(choices=DIAGRAM_TYPE_CHOICES),
        allow_empty=False,
    )
