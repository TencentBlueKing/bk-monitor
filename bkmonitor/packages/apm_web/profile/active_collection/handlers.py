"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import json
import logging
import os
import time
from collections import Counter
from itertools import groupby

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apm.models import ProfileDataSource
from apm_web.models import ActiveProfilingTask
from apm_web.profile.active_collection.constants import (
    ACTIVE_PROFILE_CONFIG_TEMPLATE_NAME,
    ACTIVE_PROFILE_SUBSCRIPTION_STEP_ID,
    ACTIVE_PROFILING_FINISHED_EVENT,
    ACTIVE_PROFILING_STARTED_EVENT,
    BKMONITORBEAT_MAIN_CONF_RELATIVE_PATH,
    BKMONITORBEAT_RELATIVE_PATH,
    BUILTIN_EVENT_GROUP_NAME,
    BUILTIN_PROFILE_SERVICE_NAME,
    DEPLOYMENT_STATUS_FAILED,
    DEPLOYMENT_STATUS_SUCCESS,
    EVENT_CONTENT_SCHEMA_VERSION,
    EVENT_ERROR_MESSAGE_MAX_LENGTH,
    EVENT_QUERY_MAX_SIZE,
    EXECUTION_UNKNOWN_GRACE_SEC,
    RUNNING_EXECUTION_WINDOW_MS,
    SUCCEED_STATUSES,
)
from apm_web.profile.constants import NORMAL_SERVICE_MAX_QUERY_SIZE
from apm_web.profile.doris.querier import APIType
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.utils.custom_report_tools import custom_report_tool
from bkmonitor.utils.request import get_request_tenant_id
from constants.apm import BUILTIN_PROFILING_APP_NAME
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api
from monitor_web.data_explorer.event.resources import EventTopKResource

logger = logging.getLogger("apm")


class ActiveProfilingDeployMixin:
    """作业平台（立即执行、取消）与节点管理（计划下发）共用：取业务开通的 DataID，按主机生成单机执行配置，逐台下发 CLI 作业"""

    def _get_event_group(self, bk_biz_id):
        """enable 开通的事件分组，返回里同时带上报用的 bk_data_id 和 token"""
        event_groups = api.metadata.single_query_event_group(
            bk_biz_id=bk_biz_id, event_group_name=BUILTIN_EVENT_GROUP_NAME
        )
        if not event_groups:
            raise ValueError(_("业务未开通主动 Profiling，请先开通"))
        return event_groups[0]

    def _get_profile_datasource(self, bk_biz_id):
        """enable 开通的 Profiling 数据源，bk_data_id 仍为 -1 说明链路没建成"""
        profile_datasource = ProfileDataSource.objects.filter(
            bk_biz_id=bk_biz_id, app_name=BUILTIN_PROFILING_APP_NAME
        ).first()
        if not profile_datasource or profile_datasource.bk_data_id == -1:
            raise ValueError(_("业务未开通主动 Profiling，请先开通"))
        return profile_datasource

    def _get_profile_data_id(self, bk_biz_id):
        return self._get_profile_datasource(bk_biz_id).bk_data_id

    def _build_host_configs(self, validated_request_data, bk_tenant_id, creator, event_data_id, profile_data_id):
        """逐主机生成下发给采集端的单机配置与写入 Event 的配置快照。
        每台目标主机收到同一份展开 config 后的扁平选择器，host_pids 由采集端按本机 bk_host_id 取用；
        Event 快照保持页面提交的 {type, config} 结构"""
        shared_config = {
            "schedule": validated_request_data["schedule"],
            "collector_config": validated_request_data["collector_config"],
            "resource_guard_config": validated_request_data["resource_guard_config"],
        }
        shared_cli_config = {
            **shared_config,
            "bk_tenant_id": bk_tenant_id,
            "bk_biz_id": validated_request_data["bk_biz_id"],
            "name": validated_request_data["name"],
            "creator": creator,
            "collection_method": validated_request_data["collection_method"],
            "collection_type": validated_request_data["collection_type"],
            "event_data_id": event_data_id,
            "profile_data_id": profile_data_id,
            "profile_app_name": BUILTIN_PROFILING_APP_NAME,
            "profile_service_name": BUILTIN_PROFILE_SERVICE_NAME,
        }
        # Golang 不传 process_selector
        process_selector = validated_request_data.get("process_selector")

        for node in validated_request_data["target_config"]["nodes"]:
            bk_host_id = node["bk_host_id"]
            cli_config = {**shared_cli_config, "bk_host_id": bk_host_id}
            event_config = {
                **shared_config,
                "target_config": {
                    "node_type": validated_request_data["target_config"]["node_type"],
                    "nodes": [{"bk_host_id": bk_host_id}],
                },
            }
            if process_selector:
                cli_config["process_selector"] = {"type": process_selector["type"], **process_selector["config"]}
                event_config["process_selector"] = process_selector
            yield bk_host_id, cli_config, event_config

    def _build_cli_script(self, script_template):
        return self._encode(
            script_template.format(
                beat_path=os.path.join(settings.LINUX_GSE_AGENT_PATH, BKMONITORBEAT_RELATIVE_PATH),
                main_conf=os.path.join(settings.LINUX_GSE_AGENT_PATH, BKMONITORBEAT_MAIN_CONF_RELATIVE_PATH),
            )
        )

    def _execute_cli_job(self, bk_biz_id, bk_host_id, script_content, payload):
        """单台主机一个作业，下发失败由调用方按各自的失败策略处理"""
        return api.job.fast_execute_script(
            bk_scope_type="biz",
            bk_scope_id=bk_biz_id,
            script_content=script_content,
            # 作业平台要求脚本参数本身 base64 传输，内层 base64 才是脚本读到的 $1
            script_param=self._encode(self._encode(json.dumps(payload))),
            target_server={"host_id_list": [bk_host_id]},
            account_alias=settings.LINUX_JOB_EXECUTE_ACCOUNT,
        )

    def _encode(self, text):
        return base64.b64encode(text.encode("utf-8")).decode("utf-8")


class ActiveProfilingResultMixin(ActiveProfilingDeployMixin):
    """查看与导出 Profiling 结果共用：定位键与起止时间由前端从主机执行行传入，取数复用现有 Profiling 检索"""

    def _locate_samples(self, validated_request_data):
        """单次采集的样本按 scheduled_at + bk_host_id 定位，计划任务再匹配 task_id，返回 Profiling 检索的查询参数"""
        bk_biz_id = validated_request_data["bk_biz_id"]
        filter_labels = {
            "scheduled_at": str(validated_request_data["scheduled_at"]),
            "bk_host_id": str(validated_request_data["bk_host_id"]),
        }
        if "task_id" in validated_request_data:
            filter_labels["task_id"] = str(validated_request_data["task_id"])
        # 查询窗取该主机的实际起止，两端各放宽一个运行窗口容忍上报端时钟偏差
        return {
            "bk_biz_id": bk_biz_id,
            "app_name": BUILTIN_PROFILING_APP_NAME,
            "service_name": BUILTIN_PROFILE_SERVICE_NAME,
            "start": validated_request_data["started_at"] - RUNNING_EXECUTION_WINDOW_MS,
            "end": validated_request_data["finished_at"] + RUNNING_EXECUTION_WINDOW_MS,
            "result_table_id": self._get_profile_datasource(bk_biz_id).result_table_id,
            "filter_labels": filter_labels,
        }

    def _convert_samples(self, validated_request_data, converter):
        """按单次采集定位样本，用调用方的转换器转换；没有样本时返回 None"""
        from apm_web.profile.views import ProfileQueryViewSet

        query_params = self._locate_samples(validated_request_data)
        samples = ProfileQueryViewSet.query(
            **query_params,
            sample_type=validated_request_data["data_type"],
            # 多取一行判断是否超限，超限时报错而不是截断
            extra_params={"limit": {"offset": 0, "rows": NORMAL_SERVICE_MAX_QUERY_SIZE + 1}},
        )

        if not samples or not samples.get("list"):
            return None
        if len(samples["list"]) > NORMAL_SERVICE_MAX_QUERY_SIZE:
            raise ValueError(_("该次采集的调用栈超过 {} 条，无法完整查看或导出").format(NORMAL_SERVICE_MAX_QUERY_SIZE))
        converter.convert(
            samples, agg_interval=ProfileQueryViewSet.get_agg_interval(query_params["start"], query_params["end"])
        )
        return converter

    def _query_sample_types(self, validated_request_data):
        """按单次采集定位样本，返回其中出现过的 sample_type，按名称排序"""
        from apm_web.profile.views import ProfileQueryViewSet

        rows = ProfileQueryViewSet.query(
            **self._locate_samples(validated_request_data),
            api_type=APIType.SELECT_COUNT,
            dimension_fields="sample_type",
            extra_params={"metric_fields": "count(*)"},
        ).get("list", [])
        return sorted(rows, key=lambda row: row["sample_type"])


class ActiveProfilingEventHandler(ActiveProfilingDeployMixin):
    """立即执行中由 SaaS 上报的 Event：作业受理后的 started，以及作业没下发成功时补发的 finished"""

    def __init__(self, bk_tenant_id, creator, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        self.event_group = self._get_event_group(bk_biz_id)
        self.host_ips = self._get_host_ips(
            bk_biz_id, [node["bk_host_id"] for node in validated_request_data["target_config"]["nodes"]]
        )
        # 自定义事件的 dimension 只接受标量字符串
        self.base_dimension = {
            "bk_tenant_id": bk_tenant_id,
            "bk_biz_id": str(bk_biz_id),
            "task_name": validated_request_data["name"],
            "creator": creator,
            "schedule_type": "immediate",
            "scheduled_at": str(validated_request_data["schedule"]["execute_at"]),
            "collection_method": validated_request_data["collection_method"],
            "collection_type": validated_request_data["collection_type"],
        }

    @property
    def event_data_id(self):
        return self.event_group["bk_data_id"]

    def report_started(self, bk_host_id, event_config, job):
        # TODO: 二期性能优化时入库 MySQL，现在上报 Event 相当于入库 ES
        now = int(time.time() * 1000)
        content = {
            "started_at": now,
            "job": {"job_instance_id": job["job_instance_id"], "step_instance_id": job["step_instance_id"]},
            "config": event_config,
        }
        self._send(self._build_event(ACTIVE_PROFILING_STARTED_EVENT, "running", now, bk_host_id, content))

    def report_failed_finished(self, bk_host_id, event_config, error):
        """作业没有下发成功就不会有 CLI finished，由 SaaS 补一条失败终态"""
        # TODO: 二期性能优化时入库 MySQL，现在上报 Event 相当于入库 ES
        now = int(time.time() * 1000)
        content = {
            "started_at": now,
            "finished_at": now,
            "execution_duration_ms": 0,
            "config": event_config,
            "processes": [],
            "message": str(error)[:EVENT_ERROR_MESSAGE_MAX_LENGTH],
        }
        self._send(self._build_event(ACTIVE_PROFILING_FINISHED_EVENT, "failed", now, bk_host_id, content))

    def _get_host_ips(self, bk_biz_id, bk_host_ids):
        """Event target 取执行时内网 IP；查不到或 CMDB 异常时留空，不阻塞下发"""
        try:
            hosts = api.cmdb.get_host_by_id(bk_biz_id=bk_biz_id, bk_host_ids=bk_host_ids)
        except Exception:  # pylint: disable=broad-except
            logger.exception("[ActiveProfiling] query host ip failed, bk_biz_id->[%s]", bk_biz_id)
            return {}
        return {host.bk_host_id: host.bk_host_innerip or host.bk_host_innerip_v6 for host in hosts}

    def _build_event(self, event_name, status, timestamp, bk_host_id, content):
        return {
            "event_name": event_name,
            "target": self.host_ips.get(bk_host_id, ""),
            "timestamp": timestamp,
            "dimension": {**self.base_dimension, "bk_host_id": str(bk_host_id), "status": status},
            "event": {"content": json.dumps({"schema_version": EVENT_CONTENT_SCHEMA_VERSION, **content})},
        }

    def _send(self, event):
        """发送失败只记日志，不影响后续主机下发"""
        try:
            custom_report_tool(self.event_data_id).send_data_by_http([event], self.event_group["token"], parallel=False)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "[ActiveProfiling] report %s failed, dimension->[%s]", event["event_name"], event["dimension"]
            )


class ActiveProfilingNodeManHandler(ActiveProfilingDeployMixin):
    """计划任务经节点管理下发：一个计划一个订阅，覆盖计划的全部目标主机，每台主机只渲染自己那份单机配置"""

    def __init__(self, bk_biz_id):
        self.bk_biz_id = bk_biz_id
        self.bk_tenant_id = get_request_tenant_id()
        # 构造时就取 DataID，业务未开通时调用方还没落库就会报错
        self.event_data_id = self._get_event_group(bk_biz_id)["bk_data_id"]
        self.profile_data_id = self._get_profile_data_id(bk_biz_id)

    def deploy(self, task):
        """按计划当前配置创建或更新订阅，返回是否成功"""
        return self._call(task, self._deploy, task)

    def switch(self, task, success_status=DEPLOYMENT_STATUS_SUCCESS):
        """启用执行 START、停用执行 STOP，官方插件只增删该订阅在各主机上的配置文件；返回是否成功"""
        if not task.subscription_id:
            # 订阅没建成过，按当前启停状态补一次完整下发
            return self.deploy(task)
        return self._call(
            task,
            self._run_action,
            task.subscription_id,
            "START" if task.is_enabled else "STOP",
            success_status=success_status,
        )

    def uninstall(self, task):
        """移除各主机上的配置文件并删除订阅，返回是否成功"""
        if not task.subscription_id:
            return True
        return self._call(task, self._run_action, task.subscription_id, "UNINSTALL_AND_DELETE")

    def _call(self, task, operation, *args, success_status=DEPLOYMENT_STATUS_SUCCESS):
        """节点管理调用失败只记日志，按结果回写本次操作计划的部署状态"""
        try:
            operation(*args)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "[ActiveProfiling] nodeman %s failed, bk_biz_id->[%s], task_id->[%s]",
                operation.__name__,
                self.bk_biz_id,
                task.id,
            )
            succeed = False
        else:
            succeed = True
        task.deployment_status = success_status if succeed else DEPLOYMENT_STATUS_FAILED
        task.save()
        return succeed

    def _deploy(self, task):
        params = self._build_subscription_params(task)
        if task.subscription_id:
            api.node_man.update_subscription(
                bk_tenant_id=self.bk_tenant_id, subscription_id=task.subscription_id, **params
            )
            return

        result = api.node_man.create_subscription(bk_tenant_id=self.bk_tenant_id, **params)
        # 订阅建好先落库，后续调用失败也不会丢失订阅 ID
        task.subscription_id = result["subscription_id"]
        task.save()
        if task.is_enabled:
            api.node_man.switch_subscription(
                bk_tenant_id=self.bk_tenant_id, subscription_id=task.subscription_id, action="enable"
            )

    def _run_action(self, subscription_id, action):
        # 巡检开关跟着启停走，停用后节点管理的巡检不会再把配置补回主机
        api.node_man.switch_subscription(
            bk_tenant_id=self.bk_tenant_id,
            subscription_id=subscription_id,
            action="enable" if action == "START" else "disable",
        )
        api.node_man.run_subscription(
            bk_tenant_id=self.bk_tenant_id,
            subscription_id=subscription_id,
            actions={ACTIVE_PROFILE_SUBSCRIPTION_STEP_ID: action},
        )

    def _build_subscription_params(self, task):
        config = {field: getattr(task, field) for field in ActiveProfilingTask.CONFIG_FIELDS}
        # 模板按 cmdb_instance.host.bk_host_id 的字符串形式取当前主机的 task 列表
        host_tasks = {
            str(bk_host_id): [{**cli_config, "task_id": task.id}]
            for bk_host_id, cli_config, __ in self._build_host_configs(
                {**config, "bk_biz_id": self.bk_biz_id},
                self.bk_tenant_id,
                task.create_user,
                self.event_data_id,
                self.profile_data_id,
            )
        }
        return {
            "scope": {
                "bk_biz_id": self.bk_biz_id,
                "object_type": "HOST",
                "node_type": "INSTANCE",
                "nodes": task.target_config["nodes"],
            },
            "steps": [
                {
                    "id": ACTIVE_PROFILE_SUBSCRIPTION_STEP_ID,
                    "type": "PLUGIN",
                    "config": {
                        "plugin_name": "bkmonitorbeat",
                        # TODO: 测试包写死 0.0.4，正式发布前改回 latest
                        "plugin_version": "0.0.4",
                        "config_templates": [{"name": ACTIVE_PROFILE_CONFIG_TEMPLATE_NAME, "version": "latest"}],
                    },
                    "params": {"context": {"host_tasks": host_tasks}},
                }
            ],
            # 停用中的计划只更新订阅内容，等启用时再由 START 下发到主机
            "run_immediately": task.is_enabled,
        }


class ActiveProfilingEventQueryHandler:
    """一期执行数据都由 Event 聚合：已采数据、执行详情等接口按同一口径把 started/finished 配成主机执行"""

    def __init__(self, bk_biz_id):
        self.bk_biz_id = bk_biz_id
        self.now = int(time.time() * 1000)
        self.retention_ms = self._get_retention_ms()
        self.event_table_id = self._get_event_table_id()

    def build_queryset(self, start_time, end_time, filter_dict):
        q = (
            self._build_query_config(filter_dict)
            # 同一执行、同一主机执行的 Event 各自相邻，重复上报时最新一条在前；排序字段不会自动补 dimensions. 前缀
            .order_by(
                "-dimensions.scheduled_at",
                "dimensions.schedule_type",
                "dimensions.task_id",
                "dimensions.bk_host_id",
                "event_name",
                "-time",
            )
        )
        return self._build_unify_queryset(start_time, end_time).add_query(q)

    def _build_query_config(self, filter_dict):
        return (
            QueryConfigBuilder((DataTypeLabel.EVENT, DataSourceLabel.CUSTOM))
            .table(self.event_table_id)
            .filter(
                bk_tenant_id=get_request_tenant_id(),
                bk_biz_id=self.bk_biz_id,
                event_name=[ACTIVE_PROFILING_STARTED_EVENT, ACTIVE_PROFILING_FINISHED_EVENT],
                **filter_dict,
            )
        )

    def _build_unify_queryset(self, start_time, end_time):
        return UnifyQuerySet().scope(self.bk_biz_id).time_align(False).start_time(start_time).end_time(end_time)

    def build_list_queryset(self, validated_request_data, filter_dict):
        """两个列表的行按 scheduled_at 选取，窗口末尾执行的 finished 可能晚于 end_time 上报"""
        return self.build_queryset(
            validated_request_data["start_time"],
            validated_request_data["end_time"] + RUNNING_EXECUTION_WINDOW_MS,
            filter_dict,
        )

    def build_execution_filter(self, validated_request_data):
        """两个列表共用的执行级筛选，任务名、执行方式、采集方式与类型在同一次执行内一致。
        dimension 都是 keyword，scheduled_at 按字典序比较，13 位毫秒时间戳的字典序与数值序一致"""
        filters = validated_request_data.get("filters", {})
        optional_filters = {
            "task_name__include": filters.get("task_name"),
            "schedule_type": filters.get("schedule_types"),
            "collection_method": filters.get("collection_methods"),
            "collection_type": filters.get("collection_types"),
        }
        filter_dict = {key: value for key, value in optional_filters.items() if value}

        # TODO: 二期执行表与主机执行表持久化状态后直接按状态筛选，不再按 scheduled_at 推算
        # running 只会出现在最近一个运行窗口内；过期按 scheduled_at 判定，与行状态同一口径
        lower, upper = validated_request_data["start_time"], validated_request_data["end_time"]
        status = filters.get("status")
        expire_before = self.now - self.retention_ms
        if status == "running":
            lower = max(lower, self.now - RUNNING_EXECUTION_WINDOW_MS)
        elif status == "outdate":
            upper = min(upper, expire_before - 1)
        elif status in SUCCEED_STATUSES:
            lower = max(lower, expire_before)
        filter_dict.update(scheduled_at__gte=lower, scheduled_at__lte=upper)
        return filter_dict

    @staticmethod
    def build_host_filter(validated_request_data):
        """两个列表共用的主机级筛选：执行时 IP、进程名和 PID 都按包含匹配，同一筛选项的多个值命中任一即可"""
        filters = validated_request_data.get("filters", {})
        filter_dict = {"target__include": filters["ips"]} if filters.get("ips") else {}
        # 采集端以逗号拼接多个进程，并把进程名里的逗号归一化为 _；查询词同样归一化，不会跨进程命中
        for field in ("process_names", "process_pids"):
            if filters.get(field):
                filter_dict[f"{field}__include"] = [value.replace(",", "_") for value in filters[field]]
        return filter_dict

    def query_events(self, queryset, offset, size):
        return list(queryset.offset(offset).limit(size))

    def iter_events(self, queryset, first_size, batch_size):
        """从头分批读取，调用方凑够行数后停止迭代，后面的批次不会查询"""
        # TODO: 二期在 MySQL 中直接按 offset + limit 分页，不再从头扫描 Event
        size = min(EVENT_QUERY_MAX_SIZE, first_size)
        offset = 0
        while True:
            events = self.query_events(queryset, offset, size)
            yield from events
            if len(events) < size:
                return
            offset += size
            if offset >= EVENT_QUERY_MAX_SIZE:
                raise ValueError(_("时间范围内的执行记录过多，请缩小时间范围或增加筛选条件"))
            size = min(batch_size, EVENT_QUERY_MAX_SIZE - offset)

    @staticmethod
    def execution_filter(validated_request_data):
        """执行定位键，立即执行不带 task_id"""
        filter_dict = {
            "schedule_type": validated_request_data["schedule_type"],
            "scheduled_at": validated_request_data["scheduled_at"],
        }
        if "task_id" in validated_request_data:
            filter_dict["task_id"] = validated_request_data["task_id"]
        return filter_dict

    def query_execution_hosts(self, validated_request_data, bk_host_ids=None):
        """按执行定位键查该次执行的 Event，逐台主机返回主机执行行、维度和本机配置快照"""
        # TODO: 二期改查 MySQL 主机执行表，执行详情与取消校验都经由这里
        scheduled_at = validated_request_data["scheduled_at"]
        filter_dict = self.execution_filter(validated_request_data)
        if bk_host_ids is not None:
            filter_dict["bk_host_id"] = bk_host_ids
        # finished 可能在执行后很久才上报（如 once_at 配置晚到），窗口放到当前；两端各放宽一个运行窗口容忍上报端时钟偏差
        queryset = self.build_queryset(
            scheduled_at - RUNNING_EXECUTION_WINDOW_MS, self.now + RUNNING_EXECUTION_WINDOW_MS, filter_dict
        )
        events = self.query_events(queryset, 0, EVENT_QUERY_MAX_SIZE)
        if len(events) >= EVENT_QUERY_MAX_SIZE:
            raise ValueError(_("该次执行的主机过多，超出查询上限"))
        return [self.resolve_host(host_events) for __, host_events in groupby(events, key=self.host_execution_key)]

    @staticmethod
    def execution_key(event):
        dimensions = event["dimensions"]
        return dimensions["schedule_type"], dimensions["scheduled_at"], dimensions.get("task_id")

    @staticmethod
    def host_execution_key(event):
        dimensions = event["dimensions"]
        return (
            dimensions["schedule_type"],
            dimensions["scheduled_at"],
            dimensions.get("task_id"),
            dimensions["bk_host_id"],
        )

    def resolve_host(self, events):
        """重复上报时排在前面的是最新一条；finished 决定终态，只有 started 时按超时派生 running/unknown。
        返回主机执行行、维度和本机配置快照"""
        # TODO: 二期由 BMW 合并 started/finished，并按 expire_at 持久化 unknown/outdate，查询时不再派生
        latest_events = {}
        for event in events:
            latest_events.setdefault(event["event_name"], event)
        finished = latest_events.get(ACTIVE_PROFILING_FINISHED_EVENT)
        event = finished or latest_events[ACTIVE_PROFILING_STARTED_EVENT]
        dimensions = event["dimensions"]
        content = json.loads(event["event"]["content"])

        host = {
            "bk_host_id": int(dimensions["bk_host_id"]),
            "ip": event["target"],
            "processes": [],
            "status": "",
            "message": "",
            "started_at": content["started_at"],
            "finished_at": None,
            "duration_ms": None,
        }
        if finished:
            status = dimensions["status"]
            if status in SUCCEED_STATUSES and int(dimensions["scheduled_at"]) + self.retention_ms < self.now:
                status = "outdate"
            host.update(
                # 旧版采集端没拿到进程时会省略 processes 字段，这类事件在 Event 保留期内仍会查到
                processes=content.get("processes", []),
                status=status,
                message=content["message"],
                finished_at=content["finished_at"],
                duration_ms=content["execution_duration_ms"],
            )
        else:
            # Go Heap 没有 duration_sec，采集时长按 0 秒计算
            duration_sec = content["config"]["collector_config"].get("duration_sec", 0)
            unknown_at = content["started_at"] + (duration_sec + EXECUTION_UNKNOWN_GRACE_SEC) * 1000
            host["status"] = "running" if self.now <= unknown_at else "unknown"
        return host, dimensions, content["config"]

    def summarize_execution(self, hosts):
        """按执行下全部主机汇总外层状态、状态计数与起止时间"""
        # TODO: 二期由 BMW 写入主机执行时在同一事务内重算，直接读取 MySQL 执行表
        statuses = [host["status"] for host in hosts]
        execution_status = self._aggregate_status(statuses)
        started_at = min(host["started_at"] for host in hosts)
        # unknown 主机没有结束时间，外层取已结束主机中最晚的一台
        finished_ats = [host["finished_at"] for host in hosts if host["finished_at"] is not None]
        finished_at = max(finished_ats) if finished_ats and execution_status != "running" else None
        return {
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": None if finished_at is None else finished_at - started_at,
            "execution_status": execution_status,
            "status_summary": dict(Counter(statuses)),
        }

    @staticmethod
    def _aggregate_status(statuses):
        """仍有主机 running 时保持 running；状态都相同时沿用；有成功主机的混合为 partial_succeed；
        没有成功主机但成功结果已过期时为 outdate；其余混合为 failed"""
        distinct_statuses = set(statuses)
        if "running" in distinct_statuses:
            return "running"
        if len(distinct_statuses) == 1:
            return statuses[0]
        if distinct_statuses & set(SUCCEED_STATUSES):
            return "partial_succeed"
        if "outdate" in distinct_statuses:
            return "outdate"
        return "failed"

    def query_topk(self, validated_request_data):
        """搜索框候选值，与两个列表一样按 scheduled_at 选取，按事件数倒序取前 limit 个。
        进程维度是逗号拼接的多个进程，PID 按位置配上进程名用于展示，点选后按 PID 筛选"""
        # TODO: 二期对 MySQL 主机执行表与进程表 GROUP BY 计数，不再拆分逗号拼接的维度
        field = validated_request_data["field"]
        limit = validated_request_data["limit"]
        candidates = Counter()
        if field == "process_names":
            for (names,), count in self._query_process_groups(validated_request_data, ["process_names"]):
                # 没有匹配到进程时维度是空串；同一次采集的同名进程只计一次
                for name in dict.fromkeys(filter(None, names.split(","))):
                    candidates[name, name] += count
        elif field == "process_pids":
            for (names, pids), count in self._query_process_groups(
                validated_request_data, ["process_names", "process_pids"]
            ):
                if pids:
                    for name, pid in zip(names.split(","), pids.split(",")):
                        candidates[pid, f"{name}:{pid}"] += count
        else:
            for (value,), count in self._query_group_counts(validated_request_data, [field], limit):
                if value:
                    candidates[value, value] += count
        return [
            {"value": value, "alias": alias, "count": count} for (value, alias), count in candidates.most_common(limit)
        ]

    def _query_process_groups(self, validated_request_data, fields):
        """进程维度几乎每次采集都不同，要取全时间范围的取值组合才能拆开计数；组合超过查询上限时报错而不是截断"""
        groups = self._query_group_counts(validated_request_data, fields, EVENT_QUERY_MAX_SIZE)
        if len(groups) >= EVENT_QUERY_MAX_SIZE:
            raise ValueError(_("时间范围内的进程组合过多，请缩小时间范围"))
        return groups

    def _query_group_counts(self, validated_request_data, fields, limit):
        """按字段分组统计事件数，按事件数倒序返回 (各字段取值, 事件数)。
        复用事件检索 TopK 的分组计数；它只按计数字段分组，其余字段先在查询配置上分组，取值按位置对应"""
        *group_fields, count_field = fields
        q = (
            self._build_query_config(self.build_execution_filter(validated_request_data))
            .time_field("time")
            .group_by(*group_fields)
        )
        queryset = (
            self._build_unify_queryset(
                validated_request_data["start_time"],
                validated_request_data["end_time"] + RUNNING_EXECUTION_WINDOW_MS,
            )
            .time_agg(False)
            .instant()
        )
        return [
            (tuple(row[field] for field in fields), row["_result_"])
            for row in EventTopKResource.query_topk(queryset, [q], count_field, limit)
        ]

    def _get_retention_ms(self):
        """成功结果超过内置 Profiling 数据源的保留期（天）即为 outdate"""
        profile_datasource = ProfileDataSource.objects.filter(
            bk_biz_id=self.bk_biz_id, app_name=BUILTIN_PROFILING_APP_NAME
        ).first()
        if not profile_datasource or profile_datasource.bk_data_id == -1:
            raise ValueError(_("业务未开通主动 Profiling，请先开通"))
        return profile_datasource.retention * 24 * 3600 * 1000

    def _get_event_table_id(self):
        event_groups = api.metadata.single_query_event_group(
            bk_biz_id=self.bk_biz_id, event_group_name=BUILTIN_EVENT_GROUP_NAME
        )
        if not event_groups:
            raise ValueError(_("业务未开通主动 Profiling，请先开通"))
        return event_groups[0]["table_id"]
