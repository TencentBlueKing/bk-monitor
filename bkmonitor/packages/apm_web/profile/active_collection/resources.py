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
from itertools import groupby, islice

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apm.models import ProfileDataSource
from apm_web.models import ActiveProfilingTask
from apm_web.profile.active_collection.constants import (
    BKMONITORBEAT_RELATIVE_PATH,
    BUILTIN_EVENT_GROUP_LABEL,
    BUILTIN_EVENT_GROUP_NAME,
    CANCEL_EXECUTION_SCRIPT,
    DEPLOYMENT_STATUS_DEPLOYING,
    DEPLOYMENT_STATUS_EXPIRED,
    DEPLOYMENT_STATUS_SUCCESS,
    EVENT_QUERY_BATCH_SIZE,
    EVENT_QUERY_MAX_SIZE,
    EXECUTION_DETAIL_HOST_COLUMNS,
    EXECUTION_LIST_TASK_COLUMNS,
    EXECUTION_QUERY_BATCH_SIZE,
    HOST_QUERY_COLUMNS,
    IMMEDIATE_COLLECT_SCRIPT,
    META_CONFIG,
    PROCESS_MATCH_SCRIPT,
    PROCESS_PREVIEW_COLUMNS,
    PROCESS_PREVIEW_MAX_HOSTS,
    SUCCEED_STATUSES,
    TASK_LIST_COLUMNS,
    TASK_STATUS_BY_ENABLED,
)
from apm_web.profile.active_collection import fixtures
from apm_web.profile.active_collection.handlers import (
    ActiveProfilingDeployMixin,
    ActiveProfilingEventHandler,
    ActiveProfilingEventQueryHandler,
    ActiveProfilingNodeManHandler,
    ActiveProfilingResultMixin,
)
from apm_web.profile.active_collection.serializers import (
    EnableRequestSerializer,
    EventListRequestSerializer,
    ExecutionCancelRequestSerializer,
    ExecutionDetailRequestSerializer,
    MetaConfigRequestSerializer,
    ProcessPreviewRequestSerializer,
    ResultDataTypesRequestSerializer,
    ResultExportRequestSerializer,
    ResultQueryRequestSerializer,
    TaskDeleteRequestSerializer,
    TaskEditRequestSerializer,
    TaskListRequestSerializer,
    TaskSubmitRequestSerializer,
    TaskSwitchRequestSerializer,
    TopKRequestSerializer,
)
from apm_web.profile.constants import DEFAULT_EXPORT_FORMAT
from apm_web.profile.diagrams import get_diagrammer
from apm_web.profile.diagrams.tree_converter import TreeConverter
from apm_web.profile.doris.converter import DorisProfileConverter
from apm_web.profile.resources import QueryServicesDetailResource
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.user import get_request_username
from constants.apm import BUILTIN_PROFILING_APP_NAME
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import Resource, api, resource
from core.errors.api import BKAPIError
from monitor_web.constants import ETL_CONFIG

logger = logging.getLogger("apm")


class ActiveProfilingMetaConfigResource(Resource):
    """获取表单默认值、请求枚举，以及当前业务是否已开通"""

    RequestSerializer = MetaConfigRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return {**META_CONFIG, "enabled": True}

        return {**META_CONFIG, "enabled": self._is_enabled(validated_request_data["bk_biz_id"])}

    @staticmethod
    def _is_enabled(bk_biz_id):
        """内置 Profiling 数据源已有 DataID 即视为已开通，事件分组由 enable 一起创建"""
        profile = ProfileDataSource.objects.filter(bk_biz_id=bk_biz_id, app_name=BUILTIN_PROFILING_APP_NAME).first()
        return profile is not None and profile.bk_data_id != -1


class EnableActiveCollectionResource(Resource):
    """按业务幂等创建 Event DataID、Profiling DataID 及存储资源"""

    RequestSerializer = EnableRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return

        bk_biz_id = validated_request_data["bk_biz_id"]
        operator = get_request_username()
        self._enable_profiling_datasource(bk_biz_id)
        self._enable_event_datasource(bk_biz_id, operator)

    def _enable_profiling_datasource(self, bk_biz_id):
        """开通业务的 Profiling 数据源，只建数据源不建应用，重复调用由 apply_datasource 内部短路"""
        ProfileDataSource.apply_datasource(bk_biz_id=bk_biz_id, app_name=BUILTIN_PROFILING_APP_NAME, option=True)

    def _enable_event_datasource(self, bk_biz_id, operator):
        """开通业务的事件分组，不写 monitor_web 自定义事件表"""
        if api.metadata.single_query_event_group(bk_biz_id=bk_biz_id, event_group_name=BUILTIN_EVENT_GROUP_NAME):
            return

        api.metadata.create_event_group(
            operator=operator,
            bk_data_id=self._get_or_create_event_data_id(bk_biz_id, operator),
            bk_biz_id=bk_biz_id,
            event_group_name=BUILTIN_EVENT_GROUP_NAME,
            label=BUILTIN_EVENT_GROUP_LABEL,
            data_label=BUILTIN_EVENT_GROUP_NAME,
        )

    def _get_or_create_event_data_id(self, bk_biz_id, operator):
        """DataID 与事件分组分两次调用创建，先复用上一次可能已创建成功的 DataID"""
        data_name = f"{bk_biz_id}_{BUILTIN_EVENT_GROUP_NAME}"
        try:
            return api.metadata.get_data_id(data_name=data_name, with_rt_info=False)["bk_data_id"]
        except BKAPIError:
            pass

        return api.metadata.create_data_id(
            bk_biz_id=bk_biz_id,
            data_name=data_name,
            data_description="主动 Profiling 内置资源，请勿删除",
            etl_config=ETL_CONFIG.CUSTOM_EVENT,
            operator=operator,
            type_label=DataTypeLabel.EVENT,
            source_label=DataSourceLabel.CUSTOM,
            option={"inject_local_time": True},
        )["bk_data_id"]


class PreviewProcessesResource(Resource):
    """预览命令行匹配进程"""

    RequestSerializer = ProcessPreviewRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.PROCESS_PREVIEW

        nodes = validated_request_data["target_config"]["nodes"]
        if len(nodes) > PROCESS_PREVIEW_MAX_HOSTS:
            raise ValueError(_("预览主机数不能超过 {} 台").format(PROCESS_PREVIEW_MAX_HOSTS))

        beat_path = os.path.join(settings.LINUX_GSE_AGENT_PATH, BKMONITORBEAT_RELATIVE_PATH)
        task_result = resource.commons.fast_execute_script(
            bk_biz_id=validated_request_data["bk_biz_id"],
            host_list=[{"bk_host_id": node["bk_host_id"]} for node in nodes],
            script_content=PROCESS_MATCH_SCRIPT.format(beat_path=beat_path),
            script_param=self._build_selector_param(validated_request_data["process_selector"]),
            account_alias=settings.LINUX_JOB_EXECUTE_ACCOUNT,
        )
        return {
            "columns": PROCESS_PREVIEW_COLUMNS,
            "data": self._matched_processes(task_result["success"]) + self._failed_hosts(task_result["failed"]),
        }

    def _build_selector_param(self, process_selector):
        """选择器展开 config 后以 base64 传给脚本，base64 字符集不含 shell 元字符"""
        payload = json.dumps({"process_selector": {"type": process_selector["type"], **process_selector["config"]}})
        return base64.b64encode(payload.encode("utf-8")).decode("utf-8")

    def _matched_processes(self, success_hosts):
        """退出码为 0 时 stdout 是单个 JSON 对象；匹配不到进程的主机也返回一行，只有 bk_host_id 与 ip"""
        rows = []
        for host in success_hosts:
            processes = json.loads(host["log_content"])["processes"]
            if not processes:
                rows.append({"bk_host_id": host["bk_host_id"], "ip": host["ip"]})
            rows.extend({"bk_host_id": host["bk_host_id"], "ip": host["ip"], **process} for process in processes)
        return rows

    def _failed_hosts(self, failed_hosts):
        """退出码非 0 时 bkmonitorbeat 的错误文本就在 stdout，作业平台把它放进 errmsg"""
        return [
            {"bk_host_id": host["bk_host_id"], "ip": host["ip"], "err_msg": host["errmsg"]} for host in failed_hosts
        ]


class ListTasksResource(Resource):
    """查询指定时间/周期计划"""

    RequestSerializer = TaskListRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.TASK_LIST

        page = validated_request_data["page"]
        page_size = validated_request_data["page_size"]
        # 同一时间写入的计划靠 id 兜底定序，避免翻页时行序抖动
        queryset = ActiveProfilingTask.objects.filter(bk_biz_id=validated_request_data["bk_biz_id"]).order_by(
            "-update_time", "-id"
        )
        offset = (page - 1) * page_size
        return {
            "columns": TASK_LIST_COLUMNS,
            "data": [self._serialize_task(task) for task in queryset[offset : offset + page_size]],
            "page": page,
            "page_size": page_size,
            "total": queryset.count(),
        }

    def _serialize_task(self, task):
        config = {field: getattr(task, field) for field in ActiveProfilingTask.CONFIG_FIELDS}
        return {
            "task_id": task.id,
            "task_status": TASK_STATUS_BY_ENABLED[task.is_enabled],
            "deployment_status": self._display_deployment_status(task),
            "creator": task.create_user,
            "updated_at": int(task.update_time.timestamp() * 1000),
            **config,
        }

    @staticmethod
    def _display_deployment_status(task):
        """计划时间已过时列表显示已过期，不写库，定时清理仍按库里的成功状态拆除配置"""
        if task.deployment_status != DEPLOYMENT_STATUS_SUCCESS:
            return task.deployment_status
        schedule = task.schedule
        if schedule["type"] == "once_at":
            last_run_at = schedule["execute_at"]
        elif schedule["type"] == "cron":
            last_run_at = schedule.get("effective_end_at")
        else:
            last_run_at = None
        if last_run_at is not None and last_run_at < int(time.time() * 1000):
            return DEPLOYMENT_STATUS_EXPIRED
        return task.deployment_status


class SubmitTaskResource(ActiveProfilingDeployMixin, Resource):
    """统一提交立即、指定时间或周期采集"""

    RequestSerializer = TaskSubmitRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return

        if validated_request_data["schedule"]["type"] == "immediate":
            self._execute_immediately(validated_request_data)
            return

        handler = ActiveProfilingNodeManHandler(validated_request_data["bk_biz_id"])
        task = ActiveProfilingTask.create_task(validated_request_data["bk_biz_id"], validated_request_data)
        handler.deploy(task)

    def _execute_immediately(self, validated_request_data):
        """立即执行不落计划表：逐台主机下发作业，受理即返回，终态由 CLI 上报的 finished Event 表达"""
        bk_biz_id = validated_request_data["bk_biz_id"]
        bk_tenant_id = get_request_tenant_id()
        creator = get_request_username()
        profile_data_id = self._get_profile_data_id(bk_biz_id)
        event_handler = ActiveProfilingEventHandler(bk_tenant_id, creator, validated_request_data)
        script_content = self._build_cli_script(IMMEDIATE_COLLECT_SCRIPT)

        for bk_host_id, cli_config, event_config in self._build_host_configs(
            validated_request_data, bk_tenant_id, creator, event_handler.event_data_id, profile_data_id
        ):
            try:
                job = self._execute_cli_job(bk_biz_id, bk_host_id, script_content, cli_config)
            except Exception as error:  # pylint: disable=broad-except
                logger.exception(
                    "[ActiveProfiling] immediate job submit failed, bk_biz_id->[%s], bk_host_id->[%s]",
                    bk_biz_id,
                    bk_host_id,
                )
                event_handler.report_failed_finished(bk_host_id, event_config, error)
                continue

            event_handler.report_started(bk_host_id, event_config, job)


class EditTaskResource(Resource):
    """编辑计划"""

    RequestSerializer = TaskEditRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return

        task = ActiveProfilingTask.get_task(validated_request_data["bk_biz_id"], validated_request_data["task_id"])
        handler = ActiveProfilingNodeManHandler(validated_request_data["bk_biz_id"])
        task.update_config(validated_request_data)
        handler.deploy(task)


class DeleteTaskResource(Resource):
    """删除计划"""

    RequestSerializer = TaskDeleteRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return

        task = ActiveProfilingTask.get_task(validated_request_data["bk_biz_id"], validated_request_data["task_id"])
        if task.is_enabled:
            raise ValueError(_("删除前请先停用计划"))

        if not ActiveProfilingNodeManHandler(validated_request_data["bk_biz_id"]).uninstall(task):
            raise ValueError(_("节点管理卸载失败，请稍后重试"))
        task.delete()


class SwitchTaskResource(Resource):
    """启停计划"""

    RequestSerializer = TaskSwitchRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return

        task = ActiveProfilingTask.get_task(validated_request_data["bk_biz_id"], validated_request_data["task_id"])
        handler = ActiveProfilingNodeManHandler(validated_request_data["bk_biz_id"])
        task.is_enabled = validated_request_data["enabled"]
        task.deployment_status = DEPLOYMENT_STATUS_DEPLOYING
        task.save()
        handler.switch(task)


class QueryHostsResource(Resource):
    """查询已采数据主机"""

    RequestSerializer = EventListRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.HOST_QUERY

        filters = validated_request_data.get("filters", {})
        status = filters.get("status")
        # unknown 取决于有没有 finished，ES 筛不出来，只能全量配对
        if status == "unknown":
            raise ValueError(_("暂不支持按 unknown 状态筛选"))

        # TODO: 二期查询 MySQL 主机执行表，筛选、排序与分页直接在 SQL 中完成，unknown 也可以筛选
        handler = ActiveProfilingEventQueryHandler(validated_request_data["bk_biz_id"])
        queryset = self._build_queryset(handler, validated_request_data, filters)
        offset = validated_request_data["offset"]
        end = offset + validated_request_data["limit"]
        # 每行通常只有 started/finished 两条，多取一条确认最后一行已经完整；重复上报或内存筛选导致不够时再按批续读
        events = handler.iter_events(queryset, end * 2 + 1, EVENT_QUERY_BATCH_SIZE)
        rows = (
            self._build_row(handler, key, host_events)
            for key, host_events in groupby(events, key=handler.host_execution_key)
        )
        if status == "running":
            rows = (row for row in rows if row["status"] == "running")
        return {"columns": HOST_QUERY_COLUMNS, "data": list(islice(rows, offset, end))}

    def _build_queryset(self, handler, validated_request_data, filters):
        """筛选全部下推 ES：终态再按 status 维度筛选，outdate 是过期的成功类终态；
        running 要看有没有 finished，不能按 status 筛，只收窄 scheduled_at"""
        filter_dict = {
            **handler.build_execution_filter(validated_request_data),
            **handler.build_host_filter(validated_request_data),
        }
        status = filters.get("status")
        if status == "outdate":
            filter_dict["status"] = list(SUCCEED_STATUSES)
        elif status and status != "running":
            filter_dict["status"] = status
        return handler.build_list_queryset(validated_request_data, filter_dict)

    def _build_row(self, handler, key, events):
        schedule_type, scheduled_at, task_id, __ = key
        row, dimensions, __ = handler.resolve_host(events)
        task = {"name": dimensions["task_name"], "schedule_type": schedule_type}
        if task_id:
            task = {"task_id": int(task_id), **task}
        # 列表不展示执行信息
        del row["message"]
        row.update(
            task=task,
            collection_method=dimensions["collection_method"],
            collection_type=dimensions["collection_type"],
            creator=dimensions["creator"],
            scheduled_at=int(scheduled_at),
        )
        return row


class ListExecutionsResource(Resource):
    """查询任务历史列表：按执行汇总全部主机，一次执行一行"""

    RequestSerializer = EventListRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.EXECUTION_LIST

        status = validated_request_data.get("filters", {}).get("status")
        # 执行状态由全部主机聚合，unknown 主机取决于有没有 finished，ES 筛不出来
        if status == "unknown":
            raise ValueError(_("暂不支持按 unknown 状态筛选"))

        # TODO: 二期查询 MySQL 执行表，主机/进程筛选改为关联主机执行表，状态筛选与分页直接在 SQL 中完成，不再分两段查询
        handler = ActiveProfilingEventQueryHandler(validated_request_data["bk_biz_id"])
        host_filter = handler.build_host_filter(validated_request_data)
        if host_filter:
            data = self._query_host_matched_rows(handler, validated_request_data, status, host_filter)
        else:
            data = self._scan_rows(handler, validated_request_data, status)
        return {"task_columns": EXECUTION_LIST_TASK_COLUMNS, "data": data}

    def _scan_rows(self, handler, validated_request_data, status):
        """筛选都是执行级维度时一次扫描，同一执行的 Event 相邻，边读边按执行汇总，执行状态在内存中筛选"""
        offset = validated_request_data["offset"]
        end = offset + validated_request_data["limit"]
        execution_filter = handler.build_execution_filter(validated_request_data)
        queryset = handler.build_list_queryset(validated_request_data, execution_filter)
        rows = (
            self._build_row(handler, key, events)
            for key, events in groupby(self._iter_events(handler, queryset, end), key=handler.execution_key)
        )
        if status:
            rows = (row for row in rows if row["execution_status"] == status)
        return list(islice(rows, offset, end))

    def _query_host_matched_rows(self, handler, validated_request_data, status, host_filter):
        """主机/进程只决定选中哪些执行，不改变执行的汇总结果：先按主机筛出命中的执行，再回查这些执行的全部主机"""
        offset = validated_request_data["offset"]
        end = offset + validated_request_data["limit"]
        execution_filter = handler.build_execution_filter(validated_request_data)
        queryset = handler.build_list_queryset(validated_request_data, {**execution_filter, **host_filter})
        keys = (key for key, __ in groupby(self._iter_events(handler, queryset, end), key=handler.execution_key))
        if not status:
            # 每个命中的执行就是一行，offset 之前的执行不用回查
            return self._query_execution_rows(
                handler, validated_request_data, execution_filter, list(islice(keys, offset, end))
            )

        # 状态要回查全部主机汇总后才知道，每轮只回查还缺的行数个执行，不够时接着上一轮继续找命中的执行
        rows = []
        while len(rows) < end:
            chunk = list(islice(keys, end - len(rows)))
            if not chunk:
                break
            rows.extend(
                row
                for row in self._query_execution_rows(handler, validated_request_data, execution_filter, chunk)
                if row["execution_status"] == status
            )
        return rows[offset:end]

    def _query_execution_rows(self, handler, validated_request_data, execution_filter, keys):
        """按 scheduled_at 回查执行的全部主机；同一毫秒可能有别的执行，按执行键精确保留"""
        if not keys:
            return []
        filter_dict = {**execution_filter, "scheduled_at": list(dict.fromkeys(key[1] for key in keys))}
        events = handler.query_events(
            handler.build_list_queryset(validated_request_data, filter_dict), 0, EVENT_QUERY_MAX_SIZE
        )
        if len(events) >= EVENT_QUERY_MAX_SIZE:
            raise ValueError(_("当前页执行的主机过多，超出查询上限"))
        selected_keys = set(keys)
        return [
            self._build_row(handler, key, execution_events)
            for key, execution_events in groupby(events, key=handler.execution_key)
            if key in selected_keys
        ]

    def _iter_events(self, handler, queryset, needed_rows):
        # 每行至少一台主机，通常有 started/finished 两条，翻页较深时首批按行数估算
        return handler.iter_events(
            queryset, max(EXECUTION_QUERY_BATCH_SIZE, needed_rows * 2 + 1), EXECUTION_QUERY_BATCH_SIZE
        )

    def _build_row(self, handler, key, events):
        schedule_type, scheduled_at, task_id = key
        hosts = []
        for __, host_events in groupby(events, key=handler.host_execution_key):
            host, dimensions, __ = handler.resolve_host(host_events)
            hosts.append(host)
        row = {"task_id": int(task_id)} if task_id else {}
        row.update(
            task_name=dimensions["task_name"],
            schedule_type=schedule_type,
            scheduled_at=int(scheduled_at),
            collection_method=dimensions["collection_method"],
            collection_type=dimensions["collection_type"],
            creator=dimensions["creator"],
            **handler.summarize_execution(hosts),
            target_count=len(hosts),
            hosts=[{"bk_host_id": host["bk_host_id"], "ip": host["ip"]} for host in hosts],
        )
        return row


class QueryTopKResource(Resource):
    """查询两个列表搜索框的候选值"""

    RequestSerializer = TopKRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.topk(validated_request_data["field"])

        return ActiveProfilingEventQueryHandler(validated_request_data["bk_biz_id"]).query_topk(validated_request_data)


class ExecutionDetailResource(Resource):
    """查询单次执行详情及全部主机"""

    RequestSerializer = ExecutionDetailRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.execution_detail(validated_request_data)

        schedule_type = validated_request_data["schedule_type"]
        scheduled_at = validated_request_data["scheduled_at"]
        handler = ActiveProfilingEventQueryHandler(validated_request_data["bk_biz_id"])

        hosts, configs = [], []
        for host, dimensions, config in handler.query_execution_hosts(validated_request_data):
            hosts.append(host)
            configs.append(config)
        if not hosts:
            raise ValueError(_("执行记录不存在"))

        detail = {"host_columns": EXECUTION_DETAIL_HOST_COLUMNS}
        if "task_id" in validated_request_data:
            detail["task_id"] = validated_request_data["task_id"]
        detail.update(
            task_name=dimensions["task_name"],
            schedule_type=schedule_type,
            scheduled_at=scheduled_at,
            collection_method=dimensions["collection_method"],
            collection_type=dimensions["collection_type"],
            creator=dimensions["creator"],
            **handler.summarize_execution(hosts),
            total_hosts=len(hosts),
            config=self._merge_config(configs),
            hosts=hosts,
        )
        return detail

    @staticmethod
    def _merge_config(configs):
        """每条 Event 的 target_config.nodes 只含当机一项，按主机拼回完整配置；其余配置同一次执行内一致"""
        config = dict(configs[0])
        config["target_config"] = {
            **config["target_config"],
            "nodes": [host_config["target_config"]["nodes"][0] for host_config in configs],
        }
        return config


class CancelExecutionResource(ActiveProfilingDeployMixin, Resource):
    """取消执行：逐台主机下发 CLI 取消命令，作业受理即返回，终态由原采集端上报的 cancelled finished 表达"""

    RequestSerializer = ExecutionCancelRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return

        bk_biz_id = validated_request_data["bk_biz_id"]
        hosts = {host["bk_host_id"]: host for host in validated_request_data["hosts"]}
        execution_key = self._build_execution_key(validated_request_data)
        script_content = self._build_cli_script(CANCEL_EXECUTION_SCRIPT)

        failed_ips = []
        for bk_host_id in self._get_running_host_ids(validated_request_data, hosts):
            try:
                self._execute_cli_job(
                    bk_biz_id, bk_host_id, script_content, {**execution_key, "bk_host_id": bk_host_id}
                )
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    "[ActiveProfiling] cancel job submit failed, bk_biz_id->[%s], bk_host_id->[%s]",
                    bk_biz_id,
                    bk_host_id,
                )
                failed_ips.append(hosts[bk_host_id]["ip"])

        if failed_ips:
            raise ValueError(_("以下主机的取消命令下发失败，请重试：{}").format("、".join(failed_ips)))

    def _build_execution_key(self, validated_request_data):
        """CLI 按与采集端相同的执行键定位运行目录"""
        return {
            "bk_tenant_id": get_request_tenant_id(),
            "bk_biz_id": validated_request_data["bk_biz_id"],
            **ActiveProfilingEventQueryHandler.execution_filter(validated_request_data),
        }

    def _get_running_host_ids(self, validated_request_data, hosts):
        """按 Event 聚合请求主机在该次执行中的状态：不属于该次执行的主机报错，已结束或 unknown 的主机无需取消"""
        handler = ActiveProfilingEventQueryHandler(validated_request_data["bk_biz_id"])
        statuses = {
            host["bk_host_id"]: host["status"]
            for host, __, __ in handler.query_execution_hosts(validated_request_data, list(hosts))
        }

        outside_ips = [host["ip"] for bk_host_id, host in hosts.items() if bk_host_id not in statuses]
        if outside_ips:
            raise ValueError(_("以下主机不属于该次执行：{}").format("、".join(outside_ips)))
        return [bk_host_id for bk_host_id in hosts if statuses[bk_host_id] == "running"]


class QueryResultsResource(ActiveProfilingResultMixin, Resource):
    """查看 Profiling 结果：取数、转换与绘图复用现有 Profiling 检索"""

    RequestSerializer = ResultQueryRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.result_query(validated_request_data["diagram_types"])

        tree_converter = self._convert_samples(validated_request_data, TreeConverter())
        if tree_converter is None or tree_converter.empty():
            return {}

        result = {}
        for diagram_type in validated_request_data["diagram_types"]:
            result.update(get_diagrammer(diagram_type).draw(tree_converter, sort="-total"))
        result.update(tree_converter.get_sample_type())
        return result


class QueryResultDataTypesResource(ActiveProfilingResultMixin, Resource):
    """查询单次采集包含的采样类型：类型筛选与命名复用 Profiling 检索的服务详情"""

    RequestSerializer = ResultDataTypesRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return {"data_types": fixtures.RESULT_DATA_TYPES}

        data_types = QueryServicesDetailResource.to_data_types(self._query_sample_types(validated_request_data))
        return {"data_types": [{"key": data_type["key"], "name": data_type["name"]} for data_type in data_types]}


class ExportResultsResource(ActiveProfilingResultMixin, Resource):
    """导出 Profiling 结果：样本查询与 results/query 共用，pprof 打包复用 Profiling 检索导出"""

    RequestSerializer = ResultExportRequestSerializer

    def perform_request(self, validated_request_data):
        if validated_request_data.get("is_mock"):
            return fixtures.export_response()

        from apm_web.profile.views import ProfileQueryViewSet

        # 没有样本时传 None，由检索导出统一报“未查询到有效数据”
        return ProfileQueryViewSet.build_export_response(
            self._convert_samples(validated_request_data, DorisProfileConverter()),
            BUILTIN_PROFILING_APP_NAME,
            validated_request_data["data_type"],
            DEFAULT_EXPORT_FORMAT,
        )
