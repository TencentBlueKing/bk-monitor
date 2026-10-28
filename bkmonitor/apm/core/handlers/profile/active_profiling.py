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
import re
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from itertools import islice

from django.conf import settings
from django.db import router, transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apm.constants import (
    ACTIVE_PROFILING_BEAT_MAIN_CONF_RELATIVE_PATH,
    ACTIVE_PROFILING_BEAT_RELATIVE_PATH,
    ACTIVE_PROFILING_CANCEL_SCRIPT,
    ACTIVE_PROFILING_CONFIG_TEMPLATE_NAME,
    ACTIVE_PROFILING_DEPLOYMENT_EXPIRED,
    ACTIVE_PROFILING_DEPLOYMENT_FAILED,
    ACTIVE_PROFILING_DEPLOYMENT_SUCCESS,
    ACTIVE_PROFILING_ERROR_TYPE_DISPATCH_FAILED,
    ACTIVE_PROFILING_EXPIRED_TASK_STOP_DELAY_MS,
    ACTIVE_PROFILING_IMMEDIATE_SCRIPT,
    ACTIVE_PROFILING_PARSING_MS,
    ACTIVE_PROFILING_PLUGIN_VERSION,
    ACTIVE_PROFILING_PROCESS_TOPK_RECENT_ROWS,
    ACTIVE_PROFILING_PROFILE_SERVICE_NAME,
    ACTIVE_PROFILING_SUBSCRIPTION_STEP_ID,
    ACTIVE_PROFILING_SUCCEED_STATUSES,
    ACTIVE_PROFILING_UNKNOWN_GRACE_SEC,
)
from apm.core.discover.precalculation.consul_handler import ConsulKafkaInfo
from apm.models import ActiveProfilingExecution, ActiveProfilingHostExecution, ActiveProfilingTask, ProfileDataSource
from bkmonitor.utils.request import get_request_tenant_id, get_request_username
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id, set_local_tenant_id
from constants.apm import BUILTIN_EVENT_GROUP_NAME, BUILTIN_PROFILING_APP_NAME
from core.drf_resource import api
from metadata.models import ClusterInfo, DataSource, EventGroup, KafkaTopicInfo
from metadata.utils import consul_tools

logger = logging.getLogger("apm")

# BMW 预计算按此前缀读取，路径与 value 结构变更需同步 BMW
CONSUL_PATH_PREFIX = f"{settings.APP_CODE}_{settings.PLATFORM}_{settings.ENVIRONMENT}/active_profiling/data_id/"

# 只有 started 或还没有 Event 的主机行，其余状态说明已有 finished
STARTED_HOST_STATUSES = ("running", "unknown")

# PID 候选的值是 进程名:PID；进程名里可能有冒号，PID 取最后一个冒号之后的数字
PROCESS_CANDIDATE_PATTERN = re.compile(r"(?P<process_name>.+):(?P<pid>\d+)")


class ActiveProfilingConsulHandler:
    """把主动 Profiling 事件分组 DataID 的 Kafka 信息同步到 Consul，供 BMW 预计算消费"""

    @classmethod
    def refresh(cls, bk_biz_id):
        """刷新单个业务，不清理其他 key"""
        cls._put_values([bk_biz_id])

    @classmethod
    def check_update(cls):
        """全量对账：刷新全部开通业务，并删除已失效 DataID 的 key"""
        # event_group_name 没有索引，先从开通时创建的 Profiling 数据源取业务，再按 bk_biz_id 查事件分组
        bk_biz_ids = list(
            ProfileDataSource.objects.filter(app_name=BUILTIN_PROFILING_APP_NAME).values_list("bk_biz_id", flat=True)
        )
        valid_data_ids = cls._put_values(bk_biz_ids)
        cls._delete_stale_keys(valid_data_ids)
        logger.info("[ActiveProfilingConsul] check update finished, valid data_ids->[%s]", len(valid_data_ids))

    @classmethod
    def _put_values(cls, bk_biz_ids):
        """写入业务事件分组的 Consul 配置，返回仍有效的 DataID；单个 DataID 失败时跳过并保留 Consul 旧值"""
        event_groups = list(
            EventGroup.objects.filter(
                bk_biz_id__in=bk_biz_ids, event_group_name=BUILTIN_EVENT_GROUP_NAME, is_delete=False, is_enable=True
            ).values("bk_tenant_id", "bk_biz_id", "bk_data_id")
        )
        data_ids = [event_group["bk_data_id"] for event_group in event_groups]
        mq_cluster_ids = dict(
            DataSource.objects.filter(bk_data_id__in=data_ids, is_enable=True).values_list(
                "bk_data_id", "mq_cluster_id"
            )
        )
        topics = dict(
            KafkaTopicInfo.objects.filter(bk_data_id__in=list(mq_cluster_ids)).values_list("bk_data_id", "topic")
        )
        clusters = {
            cluster.cluster_id: cluster
            for cluster in ClusterInfo.objects.filter(cluster_id__in=set(mq_cluster_ids.values()))
        }

        hash_consul = consul_tools.HashConsul()
        valid_data_ids = set()
        for event_group in event_groups:
            bk_data_id = event_group["bk_data_id"]
            if bk_data_id not in mq_cluster_ids:
                continue
            valid_data_ids.add(bk_data_id)

            try:
                cluster = clusters[mq_cluster_ids[bk_data_id]]
                kafka_info = ConsulKafkaInfo(
                    host=f"{cluster.domain_name}:{cluster.port}",
                    username=cluster.username,
                    password=cluster.password,
                    topic=topics[bk_data_id],
                )
                hash_consul.put(
                    key=f"{CONSUL_PATH_PREFIX}{bk_data_id}",
                    value={**event_group, "kafka_info": asdict(kafka_info)},
                    bk_data_id=bk_data_id,
                )
            except Exception:  # pylint: disable=broad-except
                logger.exception("[ActiveProfilingConsul] put consul config failed, data_id->[%s]", bk_data_id)

        return valid_data_ids

    @classmethod
    def _delete_stale_keys(cls, valid_data_ids):
        hash_consul = consul_tools.HashConsul()
        valid_keys = {f"{CONSUL_PATH_PREFIX}{bk_data_id}" for bk_data_id in valid_data_ids}
        _, keys = hash_consul.list_keys(CONSUL_PATH_PREFIX)
        for key in keys or []:
            if key not in valid_keys:
                hash_consul.delete(key)


class ActiveProfilingExecutionQueryHandler:
    """读取预计算物化的执行表与主机执行表；outdate 不落库，按 Profiling 保留期在查询时由成功类终态派生"""

    def __init__(self, bk_biz_id):
        self.bk_biz_id = bk_biz_id
        self.bk_tenant_id = get_request_tenant_id(peaceful=True) or bk_biz_id_to_bk_tenant_id(bk_biz_id)
        now = int(time.time() * 1000)
        # 计划时间早于该时刻的成功类终态已过保留期
        self.expire_before = now - self._get_retention_ms()
        # 结束时间晚于该时刻的成功类主机执行，Profiling 数据还在解析入库
        self.parsing_after = now - ACTIVE_PROFILING_PARSING_MS

    def query_hosts(self, params):
        """已采数据：一台主机的一次执行一行，按计划时间倒序分页"""
        filters = params.get("filters", {})
        queryset = ActiveProfilingHostExecution.objects.filter(
            self._build_host_q(filters),
            bk_biz_id=self.bk_biz_id,
            scheduled_at__gte=params["start_time"],
            scheduled_at__lte=params["end_time"],
        )
        execution_filter = self._build_execution_filter(filters)
        if execution_filter:
            queryset = queryset.filter(execution_id__in=self._execution_queryset(params, execution_filter).values("id"))
        if filters.get("status"):
            queryset = queryset.filter(self._build_host_status_q(filters["status"]))

        offset = params["offset"]
        # scheduled_at 不唯一（同一执行的主机、整点触发的多个计划都在同一毫秒），offset 分页要排到唯一，否则翻页会重复或漏行；
        # 三列同向倒序且与索引列顺序一致，MySQL 才能沿索引倒着读到本页即停，不用对整个时间范围排序
        hosts = list(
            queryset.order_by("-scheduled_at", "-execution_id", "-bk_host_id")[offset : offset + params["limit"]]
        )
        executions = ActiveProfilingExecution.objects.in_bulk({host.execution_id for host in hosts})
        return [self._build_host_row(host, executions[host.execution_id]) for host in hosts]

    def list_executions(self, params):
        """任务历史：一次执行一行；主机/进程条件只决定选中哪些执行，汇总仍按该执行的全部主机"""
        filters = params.get("filters", {})
        queryset = self._execution_queryset(params, self._build_execution_filter(filters))
        host_q = self._build_host_q(filters)
        if host_q:
            queryset = queryset.filter(
                id__in=ActiveProfilingHostExecution.objects.filter(
                    host_q,
                    bk_biz_id=self.bk_biz_id,
                    scheduled_at__gte=params["start_time"],
                    scheduled_at__lte=params["end_time"],
                ).values("execution_id")
            )
        if filters.get("status"):
            queryset = queryset.filter(self._build_status_q("execution_status", filters["status"]))

        offset = params["offset"]
        # 同理补上 task_id 并同向倒序，同一业务内 task_id + scheduled_at 唯一
        executions = list(queryset.order_by("-scheduled_at", "-task_id")[offset : offset + params["limit"]])
        hosts_by_execution = defaultdict(list)
        for host in (
            ActiveProfilingHostExecution.objects.filter(execution_id__in=[execution.id for execution in executions])
            .order_by("bk_host_id")
            .values("execution_id", "bk_host_id", "ip")
        ):
            hosts_by_execution[host.pop("execution_id")].append(host)
        return [
            {
                **self._build_execution_fields(execution),
                "target_count": execution.target_count,
                "hosts": hosts_by_execution[execution.id],
            }
            for execution in executions
        ]

    def query_topk(self, params):
        """搜索框候选值，按计划时间范围选取；计数只用于排序，统一按主机执行数计，进程候选按最近出现排序"""
        field = params["field"]
        limit = params["limit"]
        hosts = ActiveProfilingHostExecution.objects.filter(
            bk_biz_id=self.bk_biz_id, scheduled_at__gte=params["start_time"], scheduled_at__lte=params["end_time"]
        )
        if field == "target":
            rows = hosts.exclude(ip="").values_list("ip").annotate(count=Count("id")).order_by("-count")[:limit]
            return [{"value": ip, "alias": ip, "count": count} for ip, count in rows]
        if field in ("process_names", "process_pids"):
            return self._query_recent_processes(hosts, field, limit)

        # 执行级字段在同一次执行内一致，按执行的主机数累加
        rows = (
            self._execution_queryset(params, {})
            .exclude(**{field: ""})
            .values_list(field)
            .annotate(count=Sum("target_count"))
            .order_by("-count")[:limit]
        )
        return [{"value": value, "alias": value, "count": count} for value, count in rows]

    def query_execution_detail(self, params):
        """单次执行及其全部主机，按执行定位键查找"""
        execution = ActiveProfilingExecution.get_execution(
            self.bk_tenant_id, self.bk_biz_id, params["scheduled_at"], params.get("task_id")
        )

        fields = self._build_execution_fields(execution)
        hosts = [
            {
                "bk_host_id": host.bk_host_id,
                "ip": host.ip,
                "processes": host.processes,
                "status": self._display_host_status(host),
                "error_type": host.error_type,
                "message": self._display_host_message(host),
                "started_at": host.started_at,
                "finished_at": host.finished_at,
                "duration_ms": fields["duration_ms"],
            }
            for host in ActiveProfilingHostExecution.objects.filter(execution_id=execution.id).order_by("bk_host_id")
        ]
        return {
            **fields,
            "total_hosts": len(hosts),
            "config": execution.config,
            "hosts": hosts,
        }

    def _query_recent_processes(self, hosts, field, limit):
        """进程候选按最近出现排序，只读最近的有限行，不对整个时间范围分组计数；
        PID 几乎每次采集都变，全量分组的组数接近主机执行数"""
        # 只按 scheduled_at 排序，MySQL 可沿 (bk_biz_id, scheduled_at, ...) 索引倒序读到上限即停，不用对整个时间范围排序
        rows = (
            hosts.exclude(**{field: ""})
            .order_by("-scheduled_at")
            .values_list("process_names" if field == "process_names" else "processes", flat=True)[
                :ACTIVE_PROFILING_PROCESS_TOPK_RECENT_ROWS
            ]
        )
        candidates = Counter()
        for row in rows:
            candidates.update(self._split_process_candidates(field, row))
        return [{"value": value, "alias": value, "count": count} for value, count in islice(candidates.items(), limit)]

    @staticmethod
    def _split_process_candidates(field, row):
        """进程名候选拆开逗号拼接的进程名，同一次采集的同名进程只计一次，点选后按进程名筛选；
        PID 候选取 processes 中的原始进程名，显示与取值都是 进程名:PID，点选后按同一进程的进程名与 PID 精确匹配"""
        if field == "process_names":
            return list(dict.fromkeys(filter(None, row.split(","))))
        return [f"{process['process_name']}:{process['pid']}" for process in row]

    def _execution_queryset(self, params, execution_filter):
        return ActiveProfilingExecution.objects.filter(
            bk_tenant_id=self.bk_tenant_id,
            bk_biz_id=self.bk_biz_id,
            scheduled_at__gte=params["start_time"],
            scheduled_at__lte=params["end_time"],
            **execution_filter,
        )

    @staticmethod
    def _build_execution_filter(filters):
        """执行级筛选：任务名包含匹配，执行方式、采集方式与类型多选"""
        optional_filters = {
            "task_name__contains": filters.get("task_name"),
            "schedule_type__in": filters.get("schedule_types"),
            "collection_method__in": filters.get("collection_methods"),
            "collection_type__in": filters.get("collection_types"),
        }
        return {key: value for key, value in optional_filters.items() if value}

    @staticmethod
    def _build_host_q(filters):
        """主机级筛选：IP、进程名、PID 都按包含匹配，同一筛选项的多个值命中任一即可，不同筛选项同时满足；
        PID 候选的 进程名:PID 按同一进程精确匹配"""
        q = Q()
        for field, column in (("ips", "ip"), ("process_names", "process_names"), ("process_pids", "process_pids")):
            values = filters.get(field)
            if not values:
                continue
            field_q = Q()
            for value in values:
                process = PROCESS_CANDIDATE_PATTERN.fullmatch(value) if field == "process_pids" else None
                if process:
                    # processes 保留原始进程名，同一元素里进程名与 PID 都相等才命中，不会命中复用该 PID 的其他进程
                    field_q |= Q(
                        processes__contains=[{"process_name": process["process_name"], "pid": int(process["pid"])}]
                    )
                    continue
                # 进程名与 PID 以逗号拼接、进程名里的逗号已归一化为 _，查询词同样归一化，不会跨进程命中
                field_q |= Q(**{f"{column}__contains": value if field == "ips" else value.replace(",", "_")})
            q &= field_q
        return q

    def _build_status_q(self, field, status):
        """outdate 是过期的成功类终态；按成功类状态筛选时排除已过期的"""
        if status == "outdate":
            return Q(**{f"{field}__in": ACTIVE_PROFILING_SUCCEED_STATUSES, "scheduled_at__lt": self.expire_before})
        if status in ACTIVE_PROFILING_SUCCEED_STATUSES:
            return Q(**{field: status, "scheduled_at__gte": self.expire_before})
        return Q(**{field: status})

    def _build_host_status_q(self, status):
        """主机行按成功类状态筛选时，还要排除仍在解析中的"""
        q = self._build_status_q("status", status)
        if status in ACTIVE_PROFILING_SUCCEED_STATUSES:
            q &= Q(finished_at__lte=self.parsing_after)
        return q

    def _display_status(self, status, scheduled_at):
        if status in ACTIVE_PROFILING_SUCCEED_STATUSES and scheduled_at < self.expire_before:
            return "outdate"
        return status

    def _display_host_status(self, host):
        """主机行展示的状态：成功类结束后 Profiling 数据还在解析入库时显示 parsing，执行汇总仍按原状态"""
        status = self._display_status(host.status, host.scheduled_at)
        if status in ACTIVE_PROFILING_SUCCEED_STATUSES and host.finished_at > self.parsing_after:
            return "parsing"
        return status

    @staticmethod
    def _display_host_message(host):
        """执行详情主机行的执行信息：成功的不带原因，unknown 是没收到终态"""
        if host.status == "succeed":
            return _("采集成功")
        if host.status == "unknown":
            return _("请检查agent状态及版本信息，若持续异常请联系管理员")
        return host.message

    def _build_execution_fields(self, execution):
        """执行行的展示字段；立即执行不返回 task_id，与一期协议一致"""
        fields = {"task_id": execution.task_id} if execution.schedule_type != "immediate" else {}
        status_summary = execution.status_summary
        if execution.scheduled_at < self.expire_before:
            # 同一执行的全部主机计划时间相同，成功类计数一起合并为 outdate
            status_summary = {
                status: count
                for status, count in status_summary.items()
                if status not in ACTIVE_PROFILING_SUCCEED_STATUSES
            }
            expired_count = sum(execution.status_summary.get(status, 0) for status in ACTIVE_PROFILING_SUCCEED_STATUSES)
            if expired_count:
                status_summary["outdate"] = expired_count
        fields.update(
            task_name=execution.task_name,
            schedule_type=execution.schedule_type,
            scheduled_at=execution.scheduled_at,
            collection_method=execution.collection_method,
            collection_type=execution.collection_type,
            creator=execution.creator,
            started_at=execution.started_at,
            finished_at=execution.finished_at,
            duration_ms=self._get_duration_ms(execution),
            execution_status=self._display_status(execution.execution_status, execution.scheduled_at),
            status_summary=status_summary,
        )
        return fields

    def _build_host_row(self, host, execution):
        task = {"name": execution.task_name, "schedule_type": execution.schedule_type}
        if execution.schedule_type != "immediate":
            task = {"task_id": execution.task_id, **task}
        return {
            "bk_host_id": host.bk_host_id,
            "ip": host.ip,
            "processes": host.processes,
            "status": self._display_host_status(host),
            "started_at": host.started_at,
            "finished_at": host.finished_at,
            "duration_ms": self._get_duration_ms(execution),
            "task": task,
            "collection_method": execution.collection_method,
            "collection_type": execution.collection_type,
            "creator": execution.creator,
            "scheduled_at": host.scheduled_at,
        }

    @staticmethod
    def _get_duration_ms(execution):
        """采集时长取本次执行配置的时长；Go Heap 是即时快照，没有 duration_sec"""
        duration_sec = execution.config["collector_config"].get("duration_sec")
        return None if duration_sec is None else duration_sec * 1000

    def _get_retention_ms(self):
        """成功结果超过内置 Profiling 数据源的保留期（天）即为 outdate"""
        profile_datasource = ProfileDataSource.objects.filter(
            bk_biz_id=self.bk_biz_id, app_name=BUILTIN_PROFILING_APP_NAME
        ).first()
        if not profile_datasource or profile_datasource.bk_data_id == -1:
            raise ValueError(_("业务未开通主动 Profiling，请先开通"))
        return profile_datasource.retention * 24 * 3600 * 1000


class ActiveProfilingDeployMixin:
    """作业平台（立即执行、取消）与节点管理（计划下发）共用：取业务开通的 DataID，按主机生成单机执行配置，逐台下发 CLI 作业"""

    def _get_event_group(self, bk_biz_id):
        """enable 开通的事件分组，采集端按它的 bk_data_id 上报 Event"""
        event_group = EventGroup.objects.filter(
            bk_biz_id=bk_biz_id, event_group_name=BUILTIN_EVENT_GROUP_NAME, is_delete=False
        ).first()
        if event_group is None:
            raise ValueError(_("业务未开通主动 Profiling，请先开通"))
        return event_group

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

    def _get_host_ips(self, bk_biz_id, bk_host_ids):
        """执行时内网 IP；查不到或 CMDB 异常时留空，不阻塞下发"""
        try:
            hosts = api.cmdb.get_host_by_id(bk_biz_id=bk_biz_id, bk_host_ids=bk_host_ids)
        except Exception:  # pylint: disable=broad-except
            logger.exception("[ActiveProfiling] query host ip failed, bk_biz_id->[%s]", bk_biz_id)
            return {}
        return {host.bk_host_id: host.bk_host_innerip or host.bk_host_innerip_v6 for host in hosts}

    @staticmethod
    def _build_target_hosts(bk_host_ids, host_ips):
        """本次执行全部目标主机的快照，计划执行随 Event 上报，没上报 Event 的主机靠它补出来"""
        return [{"bk_host_id": bk_host_id, "ip": host_ips.get(bk_host_id, "")} for bk_host_id in bk_host_ids]

    def _build_host_configs(self, validated_data, bk_tenant_id, creator, task_id, event_data_id, profile_data_id):
        """逐主机生成下发给采集端的单机配置。
        每台目标主机收到同一份展开 config 后的扁平选择器，host_pids 由采集端按本机 bk_host_id 取用"""
        shared_cli_config = {
            "schedule": validated_data["schedule"],
            "collector_config": validated_data["collector_config"],
            "resource_guard_config": validated_data["resource_guard_config"],
            "task_id": task_id,
            "bk_tenant_id": bk_tenant_id,
            "bk_biz_id": validated_data["bk_biz_id"],
            "name": validated_data["name"],
            "creator": creator,
            "collection_method": validated_data["collection_method"],
            "collection_type": validated_data["collection_type"],
            "event_data_id": event_data_id,
            "profile_data_id": profile_data_id,
            "profile_app_name": BUILTIN_PROFILING_APP_NAME,
            "profile_service_name": ACTIVE_PROFILING_PROFILE_SERVICE_NAME,
        }
        # Golang 不传 process_selector
        process_selector = validated_data.get("process_selector")
        if process_selector:
            shared_cli_config["process_selector"] = {"type": process_selector["type"], **process_selector["config"]}

        for node in validated_data["target_config"]["nodes"]:
            yield node["bk_host_id"], {**shared_cli_config, "bk_host_id": node["bk_host_id"]}

    def _build_cli_script(self, script_template):
        return self._encode(
            script_template.format(
                beat_path=os.path.join(settings.LINUX_GSE_AGENT_PATH, ACTIVE_PROFILING_BEAT_RELATIVE_PATH),
                main_conf=os.path.join(settings.LINUX_GSE_AGENT_PATH, ACTIVE_PROFILING_BEAT_MAIN_CONF_RELATIVE_PATH),
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


class ActiveProfilingNodeManHandler(ActiveProfilingDeployMixin):
    """计划任务经节点管理下发：一个计划一个订阅，覆盖计划的全部目标主机，每台主机只渲染自己那份单机配置"""

    def __init__(self, bk_biz_id):
        self.bk_biz_id = bk_biz_id
        self.bk_tenant_id = get_request_tenant_id()
        # 构造时就取 DataID，业务未开通时调用方还没落库就会报错
        self.event_data_id = self._get_event_group(bk_biz_id).bk_data_id
        self.profile_data_id = self._get_profile_data_id(bk_biz_id)

    @classmethod
    def stop_expired_tasks(cls):
        """最后一次执行过去 1 天的计划走手动停用的同一流程；没设生效结束时间的 cron 一直有效"""
        expire_before = int(time.time() * 1000) - ACTIVE_PROFILING_EXPIRED_TASK_STOP_DELAY_MS
        tasks_by_biz = defaultdict(list)
        # 停用失败的计划保持部署失败状态，第二天再试；订阅没建成的计划主机上没有配置
        for task in ActiveProfilingTask.objects.filter(
            Q(is_enabled=True) | Q(deployment_status=ACTIVE_PROFILING_DEPLOYMENT_FAILED)
        ).exclude(subscription_id=0):
            schedule = task.schedule
            last_run_at = schedule["execute_at"] if schedule["type"] == "once_at" else schedule.get("effective_end_at")
            if last_run_at is not None and last_run_at < expire_before:
                tasks_by_biz[task.bk_biz_id].append(task)

        for bk_biz_id, tasks in tasks_by_biz.items():
            try:
                set_local_tenant_id(bk_biz_id_to_bk_tenant_id(bk_biz_id))
                handler = cls(bk_biz_id)
            except Exception:  # pylint: disable=broad-except
                logger.exception("[ActiveProfiling] stop expired tasks init failed, bk_biz_id->[%s]", bk_biz_id)
                continue
            for task in tasks:
                # 停用状态随节点管理结果一次写回；成功记为已过期，失败仍是 failed，下一次任务再试
                task.is_enabled = False
                handler.switch(task, ACTIVE_PROFILING_DEPLOYMENT_EXPIRED)

    def deploy(self, task):
        """按计划当前配置创建或更新订阅，返回是否成功"""
        return self._call(task, self._deploy, task)

    def switch(self, task, success_status=ACTIVE_PROFILING_DEPLOYMENT_SUCCESS):
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

    def _call(self, task, operation, *args, success_status=ACTIVE_PROFILING_DEPLOYMENT_SUCCESS):
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
        task.deployment_status = success_status if succeed else ACTIVE_PROFILING_DEPLOYMENT_FAILED
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
            actions={ACTIVE_PROFILING_SUBSCRIPTION_STEP_ID: action},
        )

    def _build_subscription_params(self, task):
        config = {field: getattr(task, field) for field in ActiveProfilingTask.CONFIG_FIELDS}
        bk_host_ids = [node["bk_host_id"] for node in task.target_config["nodes"]]
        # 全部主机共用一份快照，放进公共上下文由模板渲染进每个 task，不随 host_tasks 按主机重复
        target_hosts = self._build_target_hosts(bk_host_ids, self._get_host_ips(self.bk_biz_id, bk_host_ids))
        # 模板按 cmdb_instance.host.bk_host_id 的字符串形式取当前主机的 task 列表
        host_tasks = {
            str(bk_host_id): [cli_config]
            for bk_host_id, cli_config in self._build_host_configs(
                {**config, "bk_biz_id": self.bk_biz_id},
                self.bk_tenant_id,
                task.create_user,
                task.id,
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
                    "id": ACTIVE_PROFILING_SUBSCRIPTION_STEP_ID,
                    "type": "PLUGIN",
                    "config": {
                        "plugin_name": "bkmonitorbeat",
                        "plugin_version": ACTIVE_PROFILING_PLUGIN_VERSION,
                        "config_templates": [{"name": ACTIVE_PROFILING_CONFIG_TEMPLATE_NAME, "version": "latest"}],
                    },
                    "params": {"context": {"host_tasks": host_tasks, "target_hosts": target_hosts}},
                }
            ],
            # 停用中的计划只更新订阅内容，等启用时再由 START 下发到主机
            "run_immediately": task.is_enabled,
        }


class ActiveProfilingExecutionWriter:
    """SaaS 对执行表与主机执行表的写入：立即执行建行、作业受理或下发失败时更新主机行、取消时写入 cancelled。
    这些写入没有对应的 Event，event_time 取写入时刻，采集端之后上报的 finished 更新，经 BMW 覆盖；
    BMW 同时写同一执行，主机行按条件更新，执行行锁住后按该执行的全部主机行重算"""

    def __init__(self, execution):
        self.execution = execution
        self.database = router.db_for_write(ActiveProfilingExecution)

    @classmethod
    def create_immediate(cls, bk_tenant_id, creator, validated_data, target_hosts):
        """同一事务内建执行行与全部目标主机的占位行，执行行的 id 即本次立即执行的 task_id"""
        scheduled_at = validated_data["schedule"]["execute_at"]
        unknown_at = cls._unknown_at(scheduled_at, validated_data["collector_config"])
        database = router.db_for_write(ActiveProfilingExecution)
        with transaction.atomic(using=database):
            execution = ActiveProfilingExecution.objects.using(database).create(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=validated_data["bk_biz_id"],
                schedule_type="immediate",
                scheduled_at=scheduled_at,
                task_name=validated_data["name"],
                creator=creator,
                collection_method=validated_data["collection_method"],
                collection_type=validated_data["collection_type"],
                execution_status="running",
                status_summary={"running": len(target_hosts)},
                target_count=len(target_hosts),
                config=cls._build_config(validated_data),
            )
            execution.task_id = execution.id
            execution.save(using=database, update_fields=["task_id"])
            ActiveProfilingHostExecution.objects.using(database).bulk_create(
                ActiveProfilingHostExecution(
                    execution_id=execution.id,
                    bk_biz_id=execution.bk_biz_id,
                    scheduled_at=scheduled_at,
                    bk_host_id=host["bk_host_id"],
                    ip=host["ip"],
                    status="running",
                    event_time=0,
                    unknown_at=unknown_at,
                )
                for host in target_hosts
            )
        return cls(execution)

    def write_started(self, bk_host_id, started_at):
        """作业受理：只覆盖还没有终态、且没有更新 Event 的主机行"""
        self._update_hosts(
            Q(bk_host_id=bk_host_id, status__in=STARTED_HOST_STATUSES, event_time__lt=started_at),
            status="running",
            started_at=started_at,
            event_time=started_at,
            unknown_at=self._unknown_at(started_at, self.execution.config["collector_config"]),
        )

    def write_dispatch_failed(self, bk_host_id, failed_at, message):
        """作业下发失败：这台主机不会再有采集端的 finished，直接写失败终态；已有更新的终态时跳过"""
        self._update_hosts(
            Q(bk_host_id=bk_host_id) & (Q(status__in=STARTED_HOST_STATUSES) | Q(event_time__lt=failed_at)),
            status="failed",
            started_at=failed_at,
            finished_at=failed_at,
            error_type=ACTIVE_PROFILING_ERROR_TYPE_DISPATCH_FAILED,
            message=message,
            event_time=failed_at,
            unknown_at=None,
        )

    def cancel_hosts(self, bk_host_ids, finished_at):
        """只改仍为 running 的主机行，event_time 不变，之后上报的真实 finished 一定比它新，会覆盖这次写入"""
        self._update_hosts(
            Q(bk_host_id__in=bk_host_ids, status="running"),
            status="cancelled",
            finished_at=finished_at,
            unknown_at=None,
        )

    def _update_hosts(self, host_q, **fields):
        """锁住执行行后再按条件更新主机行并重算汇总，与同一执行的其他写入串行"""
        with transaction.atomic(using=self.database):
            execution = (
                ActiveProfilingExecution.objects.using(self.database).select_for_update().get(id=self.execution.id)
            )
            hosts = ActiveProfilingHostExecution.objects.using(self.database).filter(host_q, execution_id=execution.id)
            if hosts.update(**fields, updated_at=timezone.now()):
                self._recalculate(execution)

    def _recalculate(self, execution):
        """按该执行的全部主机行重算汇总字段，不按内存中的旧状态计算"""
        hosts = list(
            ActiveProfilingHostExecution.objects.using(self.database)
            .filter(execution_id=execution.id)
            .values_list("status", "started_at", "finished_at")
        )
        statuses = [status for status, __, __ in hosts]
        started_ats = [started_at for __, started_at, __ in hosts if started_at is not None]
        finished_ats = [finished_at for __, __, finished_at in hosts if finished_at is not None]
        execution.execution_status = self._aggregate_status(statuses)
        execution.status_summary = dict(Counter(statuses))
        execution.target_count = len(hosts)
        execution.started_at = min(started_ats) if started_ats else None
        execution.finished_at = max(finished_ats) if finished_ats and execution.execution_status != "running" else None
        execution.save(
            using=self.database,
            update_fields=[
                "execution_status",
                "status_summary",
                "target_count",
                "started_at",
                "finished_at",
                "updated_at",
            ],
        )

    @staticmethod
    def _aggregate_status(statuses):
        """仍有主机 running 时保持 running；状态都相同时沿用；有成功主机的混合为 partial_succeed；其余混合为 failed"""
        distinct_statuses = set(statuses)
        if "running" in distinct_statuses:
            return "running"
        if len(distinct_statuses) == 1:
            return statuses[0]
        if distinct_statuses & set(ACTIVE_PROFILING_SUCCEED_STATUSES):
            return "partial_succeed"
        return "failed"

    @staticmethod
    def _unknown_at(started_at, collector_config):
        # Go Heap 没有 duration_sec，采集时长按 0 秒计算
        return started_at + (collector_config.get("duration_sec", 0) + ACTIVE_PROFILING_UNKNOWN_GRACE_SEC) * 1000

    @staticmethod
    def _build_config(validated_data):
        """提交的完整配置，target_config.nodes 含全部目标主机，结构与 Event 中的配置快照一致"""
        config = {
            "schedule": validated_data["schedule"],
            "collector_config": validated_data["collector_config"],
            "resource_guard_config": validated_data["resource_guard_config"],
            "target_config": validated_data["target_config"],
        }
        if validated_data.get("process_selector"):
            config["process_selector"] = validated_data["process_selector"]
        return config


class ActiveProfilingImmediateHandler(ActiveProfilingDeployMixin):
    """立即执行：先建执行行与全部目标主机的占位行，再逐台主机下发作业，受理即返回，
    终态由 CLI 上报的 finished 经 BMW 落库"""

    def __init__(self, bk_biz_id):
        self.bk_biz_id = bk_biz_id
        self.bk_tenant_id = get_request_tenant_id()
        self.creator = get_request_username()

    def execute(self, validated_data):
        # 业务未开通时在建行前报错
        profile_data_id = self._get_profile_data_id(self.bk_biz_id)
        event_data_id = self._get_event_group(self.bk_biz_id).bk_data_id
        bk_host_ids = [node["bk_host_id"] for node in validated_data["target_config"]["nodes"]]
        target_hosts = self._build_target_hosts(bk_host_ids, self._get_host_ips(self.bk_biz_id, bk_host_ids))
        writer = ActiveProfilingExecutionWriter.create_immediate(
            self.bk_tenant_id, self.creator, validated_data, target_hosts
        )
        script_content = self._build_cli_script(ACTIVE_PROFILING_IMMEDIATE_SCRIPT)

        for bk_host_id, cli_config in self._build_host_configs(
            validated_data, self.bk_tenant_id, self.creator, writer.execution.task_id, event_data_id, profile_data_id
        ):
            try:
                self._execute_cli_job(self.bk_biz_id, bk_host_id, script_content, cli_config)
            except Exception as error:  # pylint: disable=broad-except
                logger.exception(
                    "[ActiveProfiling] immediate job submit failed, bk_biz_id->[%s], bk_host_id->[%s]",
                    self.bk_biz_id,
                    bk_host_id,
                )
                self._write(writer.write_dispatch_failed, bk_host_id, int(time.time() * 1000), str(error))
                continue

            self._write(writer.write_started, bk_host_id, int(time.time() * 1000))

    def _write(self, operation, bk_host_id, *args):
        """写库失败只记日志：已受理的主机由采集端上报的 finished 经 BMW 补上终态，
        下发失败的主机保留占位行，按时间转为 unknown"""
        try:
            operation(bk_host_id, *args)
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "[ActiveProfiling] %s failed, bk_biz_id->[%s], bk_host_id->[%s]",
                operation.__name__,
                self.bk_biz_id,
                bk_host_id,
            )


class ActiveProfilingCancelHandler(ActiveProfilingDeployMixin):
    """取消执行：逐台主机下发 CLI 取消命令，受理后把主机行写为 cancelled，真实终态以原采集端之后上报的 finished 为准"""

    def __init__(self, bk_biz_id):
        self.bk_biz_id = bk_biz_id
        self.bk_tenant_id = get_request_tenant_id()

    def cancel(self, validated_data):
        execution = ActiveProfilingExecution.get_execution(
            self.bk_tenant_id, self.bk_biz_id, validated_data["scheduled_at"], validated_data.get("task_id")
        )
        hosts = {host["bk_host_id"]: host for host in validated_data["hosts"]}
        host_rows = self._get_host_rows(execution, hosts)
        # CLI 按与采集端相同的执行键定位运行目录
        execution_key = {
            "bk_tenant_id": execution.bk_tenant_id,
            "bk_biz_id": execution.bk_biz_id,
            "task_id": execution.task_id,
            "schedule_type": execution.schedule_type,
            "scheduled_at": execution.scheduled_at,
        }
        script_content = self._build_cli_script(ACTIVE_PROFILING_CANCEL_SCRIPT)

        cancelled_host_ids, failed_ips = [], []
        for bk_host_id, host in hosts.items():
            # 已结束或 unknown 的主机无需取消
            if host_rows[bk_host_id].status != "running":
                continue
            try:
                self._execute_cli_job(
                    self.bk_biz_id, bk_host_id, script_content, {**execution_key, "bk_host_id": bk_host_id}
                )
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    "[ActiveProfiling] cancel job submit failed, bk_biz_id->[%s], bk_host_id->[%s]",
                    self.bk_biz_id,
                    bk_host_id,
                )
                # 占位行从没上报过 Event，没有证据表明它在采集，下发失败也写 cancelled，之后真跑起来由真实 finished 覆盖
                if host_rows[bk_host_id].event_time:
                    failed_ips.append(host["ip"])
                    continue
            cancelled_host_ids.append(bk_host_id)

        self._write_cancelled(execution, cancelled_host_ids)
        if failed_ips:
            raise ValueError(_("以下主机的取消命令下发失败，请重试：{}").format("、".join(failed_ips)))

    @staticmethod
    def _get_host_rows(execution, hosts):
        """请求主机在该次执行中的主机行，不属于该次执行的主机报错"""
        host_rows = {
            row.bk_host_id: row
            for row in ActiveProfilingHostExecution.objects.filter(
                execution_id=execution.id, bk_host_id__in=list(hosts)
            )
        }
        outside_ips = [host["ip"] for bk_host_id, host in hosts.items() if bk_host_id not in host_rows]
        if outside_ips:
            raise ValueError(_("以下主机不属于该次执行：{}").format("、".join(outside_ips)))
        return host_rows

    def _write_cancelled(self, execution, bk_host_ids):
        """写库失败只记日志：取消命令已受理，真实终态由采集端上报的 finished 经 BMW 落库"""
        if not bk_host_ids:
            return
        try:
            ActiveProfilingExecutionWriter(execution).cancel_hosts(bk_host_ids, int(time.time() * 1000))
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "[ActiveProfiling] write cancelled failed, bk_biz_id->[%s], execution_id->[%s]",
                self.bk_biz_id,
                execution.id,
            )
