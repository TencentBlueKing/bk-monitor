"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import time
from collections import Counter
from itertools import groupby, islice

from django.utils.translation import gettext_lazy as _

from apm.constants import (
    ACTIVE_PROFILING_ES_EXECUTION_BATCH_SIZE,
    ACTIVE_PROFILING_ES_QUERY_BATCH_SIZE,
    ACTIVE_PROFILING_ES_QUERY_MAX_SIZE,
    ACTIVE_PROFILING_FINISHED_EVENT,
    ACTIVE_PROFILING_PARSING_MS,
    ACTIVE_PROFILING_PROCESS_TOPK_RECENT_ROWS,
    ACTIVE_PROFILING_RUNNING_WINDOW_MS,
    ACTIVE_PROFILING_STARTED_EVENT,
    ACTIVE_PROFILING_SUCCEED_STATUSES,
    ACTIVE_PROFILING_UNKNOWN_GRACE_SEC,
)
from apm.core.handlers.profile.active_profiling import PROCESS_CANDIDATE_PATTERN
from apm.models import ProfileDataSource
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.utils.request import get_request_tenant_id
from constants.apm import BUILTIN_EVENT_GROUP_NAME, BUILTIN_PROFILING_APP_NAME
from constants.data_source import DataSourceLabel, DataTypeLabel
from metadata.models import EventGroup


class ActiveProfilingEventQueryHandler:
    """按 Event ES 聚合的查询，source=es 时使用，保留一期的查询能力：
    已采数据、任务历史、执行详情按同一口径把 started/finished 配成主机执行，outdate、unknown 等都在查询时派生"""

    def __init__(self, bk_biz_id):
        self.bk_biz_id = bk_biz_id
        self.now = int(time.time() * 1000)
        self.retention_ms = self._get_retention_ms()
        self.event_table_id = self._get_event_table_id()

    def query_hosts(self, params):
        """已采数据：一台主机的一次执行一行"""
        status = params.get("filters", {}).get("status")
        # unknown 取决于有没有 finished，ES 筛不出来，只能全量配对
        if status == "unknown":
            raise ValueError(_("暂不支持按 unknown 状态筛选"))

        offset = params["offset"]
        end = offset + params["limit"]
        # 每行通常只有 started/finished 两条，多取一条确认最后一行已经完整；重复上报或内存筛选导致不够时再按批续读
        events = self._iter_events(
            self._build_hosts_queryset(params, status), end * 2 + 1, ACTIVE_PROFILING_ES_QUERY_BATCH_SIZE
        )
        rows = (
            self._build_host_row(key, host_events) for key, host_events in groupby(events, key=self._host_execution_key)
        )
        # running 要看有没有 finished，成功类要排除还在解析中的行，都只能配对后在内存中筛选
        if status in ("running", *ACTIVE_PROFILING_SUCCEED_STATUSES):
            rows = (row for row in rows if row["status"] == status)
        return list(islice(rows, offset, end))

    def list_executions(self, params):
        """任务历史：按执行汇总全部主机，一次执行一行"""
        status = params.get("filters", {}).get("status")
        # 执行状态由全部主机聚合，unknown 主机取决于有没有 finished，ES 筛不出来
        if status == "unknown":
            raise ValueError(_("暂不支持按 unknown 状态筛选"))

        host_filter = self._build_host_filter(params)
        if host_filter:
            return self._query_host_matched_executions(params, status, host_filter)
        return self._scan_executions(params, status)

    def query_topk(self, params):
        """搜索框候选值，与两个列表一样按 scheduled_at 选取，按事件数倒序取前 limit 个"""
        field = params["field"]
        limit = params["limit"]
        if field in ("process_names", "process_pids"):
            return self._query_recent_processes(params, field, limit)
        return [
            {"value": value, "alias": value, "count": count}
            for (value,), count in self._query_group_counts(params, [field], limit)
            if value
        ]

    def query_execution_detail(self, params):
        """单次执行及其全部主机；前端不给立即执行传 task_id，没有 task_id 时按立即执行定位"""
        hosts, configs = [], []
        for host, dimensions, config in self._query_execution_hosts(params):
            hosts.append(host)
            configs.append(config)
        if not hosts:
            raise ValueError(_("执行记录不存在"))

        detail = {"task_id": params["task_id"]} if "task_id" in params else {}
        detail.update(
            task_name=dimensions["task_name"],
            schedule_type=dimensions["schedule_type"],
            scheduled_at=params["scheduled_at"],
            collection_method=dimensions["collection_method"],
            collection_type=dimensions["collection_type"],
            creator=dimensions["creator"],
            **self._summarize_execution(hosts),
            total_hosts=len(hosts),
            config=self._merge_config(configs),
            hosts=[{**host, "status": self._display_host_status(host)} for host in hosts],
        )
        return detail

    def _build_hosts_queryset(self, params, status):
        """筛选全部下推 ES：终态再按 status 维度筛选，outdate 是过期的成功类终态；
        running 要看有没有 finished，不能按 status 筛，只收窄 scheduled_at"""
        filter_dict = {**self._build_execution_filter(params), **self._build_host_filter(params)}
        if status == "outdate":
            filter_dict["status"] = list(ACTIVE_PROFILING_SUCCEED_STATUSES)
        elif status and status != "running":
            filter_dict["status"] = status
        return self._build_list_queryset(params, filter_dict)

    def _build_host_row(self, key, events):
        schedule_type, scheduled_at, task_id, __ = key
        row, dimensions, __ = self._resolve_host(events)
        task = {"name": dimensions["task_name"], "schedule_type": schedule_type}
        if task_id:
            task = {"task_id": int(task_id), **task}
        # 列表不展示执行信息
        del row["error_type"], row["message"]
        row.update(
            status=self._display_host_status(row),
            task=task,
            collection_method=dimensions["collection_method"],
            collection_type=dimensions["collection_type"],
            creator=dimensions["creator"],
            scheduled_at=int(scheduled_at),
        )
        return row

    def _scan_executions(self, params, status):
        """筛选都是执行级维度时一次扫描，同一执行的 Event 相邻，边读边按执行汇总，执行状态在内存中筛选"""
        offset = params["offset"]
        end = offset + params["limit"]
        queryset = self._build_list_queryset(params, self._build_execution_filter(params))
        rows = (
            self._build_execution_row(key, events)
            for key, events in groupby(self._iter_execution_events(queryset, end), key=self._execution_key)
        )
        if status:
            rows = (row for row in rows if row["execution_status"] == status)
        return list(islice(rows, offset, end))

    def _query_host_matched_executions(self, params, status, host_filter):
        """主机/进程只决定选中哪些执行，不改变执行的汇总结果：先按主机筛出命中的执行，再回查这些执行的全部主机"""
        offset = params["offset"]
        end = offset + params["limit"]
        execution_filter = self._build_execution_filter(params)
        queryset = self._build_list_queryset(params, {**execution_filter, **host_filter})
        keys = (key for key, __ in groupby(self._iter_execution_events(queryset, end), key=self._execution_key))
        if not status:
            # 每个命中的执行就是一行，offset 之前的执行不用回查
            return self._query_execution_rows(params, execution_filter, list(islice(keys, offset, end)))

        # 状态要回查全部主机汇总后才知道，每轮只回查还缺的行数个执行，不够时接着上一轮继续找命中的执行
        rows = []
        while len(rows) < end:
            chunk = list(islice(keys, end - len(rows)))
            if not chunk:
                break
            rows.extend(
                row
                for row in self._query_execution_rows(params, execution_filter, chunk)
                if row["execution_status"] == status
            )
        return rows[offset:end]

    def _query_execution_rows(self, params, execution_filter, keys):
        """按 scheduled_at 回查执行的全部主机；同一毫秒可能有别的执行，按执行键精确保留"""
        if not keys:
            return []
        filter_dict = {**execution_filter, "scheduled_at": list(dict.fromkeys(key[1] for key in keys))}
        events = self._query_events(
            self._build_list_queryset(params, filter_dict), 0, ACTIVE_PROFILING_ES_QUERY_MAX_SIZE
        )
        if len(events) >= ACTIVE_PROFILING_ES_QUERY_MAX_SIZE:
            raise ValueError(_("当前页执行的主机过多，超出查询上限"))
        selected_keys = set(keys)
        return [
            self._build_execution_row(key, execution_events)
            for key, execution_events in groupby(events, key=self._execution_key)
            if key in selected_keys
        ]

    def _iter_execution_events(self, queryset, needed_rows):
        # 每行至少一台主机，通常有 started/finished 两条，翻页较深时首批按行数估算
        return self._iter_events(
            queryset,
            max(ACTIVE_PROFILING_ES_EXECUTION_BATCH_SIZE, needed_rows * 2 + 1),
            ACTIVE_PROFILING_ES_EXECUTION_BATCH_SIZE,
        )

    def _build_execution_row(self, key, events):
        schedule_type, scheduled_at, task_id = key
        hosts = []
        for __, host_events in groupby(events, key=self._host_execution_key):
            host, dimensions, __ = self._resolve_host(host_events)
            hosts.append(host)
        row = {"task_id": int(task_id)} if task_id else {}
        row.update(
            task_name=dimensions["task_name"],
            schedule_type=schedule_type,
            scheduled_at=int(scheduled_at),
            collection_method=dimensions["collection_method"],
            collection_type=dimensions["collection_type"],
            creator=dimensions["creator"],
            **self._summarize_execution(hosts),
            target_count=len(hosts),
            hosts=[{"bk_host_id": host["bk_host_id"], "ip": host["ip"]} for host in hosts],
        )
        return row

    @staticmethod
    def _merge_config(configs):
        """每条 Event 的 target_config.nodes 只含当机一项，按主机拼回完整配置；其余配置同一次执行内一致"""
        config = dict(configs[0])
        config["target_config"] = {
            **config["target_config"],
            "nodes": [host_config["target_config"]["nodes"][0] for host_config in configs],
        }
        return config

    def _build_queryset(self, start_time, end_time, filter_dict):
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

    def _build_list_queryset(self, params, filter_dict):
        """两个列表的行按 scheduled_at 选取，窗口末尾执行的 finished 可能晚于 end_time 上报"""
        return self._build_queryset(
            params["start_time"], params["end_time"] + ACTIVE_PROFILING_RUNNING_WINDOW_MS, filter_dict
        )

    def _build_execution_filter(self, params):
        """两个列表共用的执行级筛选，任务名、执行方式、采集方式与类型在同一次执行内一致。
        dimension 都是 keyword，scheduled_at 按字典序比较，13 位毫秒时间戳的字典序与数值序一致"""
        filters = params.get("filters", {})
        optional_filters = {
            "task_name__include": filters.get("task_name"),
            "schedule_type": filters.get("schedule_types"),
            "collection_method": filters.get("collection_methods"),
            "collection_type": filters.get("collection_types"),
        }
        filter_dict = {key: value for key, value in optional_filters.items() if value}

        # running 只会出现在最近一个运行窗口内；过期按 scheduled_at 判定，与行状态同一口径
        lower, upper = params["start_time"], params["end_time"]
        status = filters.get("status")
        expire_before = self.now - self.retention_ms
        if status == "running":
            lower = max(lower, self.now - ACTIVE_PROFILING_RUNNING_WINDOW_MS)
        elif status == "outdate":
            upper = min(upper, expire_before - 1)
        elif status in ACTIVE_PROFILING_SUCCEED_STATUSES:
            lower = max(lower, expire_before)
        filter_dict.update(scheduled_at__gte=lower, scheduled_at__lte=upper)
        return filter_dict

    @staticmethod
    def _build_host_filter(params):
        """两个列表共用的主机级筛选：执行时 IP、进程名和 PID 都按包含匹配，同一筛选项的多个值命中任一即可"""
        filters = params.get("filters", {})
        filter_dict = {"target__include": filters["ips"]} if filters.get("ips") else {}
        # 采集端以逗号拼接多个进程，并把进程名里的逗号归一化为 _；查询词同样归一化，不会跨进程命中
        if filters.get("process_names"):
            filter_dict["process_names__include"] = [value.replace(",", "_") for value in filters["process_names"]]
        if filters.get("process_pids"):
            pids = []
            for value in filters["process_pids"]:
                # 维度里进程名与 PID 分开拼接，无法按同一进程配对，PID 候选的 进程名:PID 只按 PID 匹配
                process = PROCESS_CANDIDATE_PATTERN.fullmatch(value)
                pids.append(process["pid"] if process else value.replace(",", "_"))
            filter_dict["process_pids__include"] = pids
        return filter_dict

    def _query_events(self, queryset, offset, size):
        return list(queryset.offset(offset).limit(size))

    def _iter_events(self, queryset, first_size, batch_size):
        """从头分批读取，调用方凑够行数后停止迭代，后面的批次不会查询"""
        size = min(ACTIVE_PROFILING_ES_QUERY_MAX_SIZE, first_size)
        offset = 0
        while True:
            events = self._query_events(queryset, offset, size)
            yield from events
            if len(events) < size:
                return
            offset += size
            if offset >= ACTIVE_PROFILING_ES_QUERY_MAX_SIZE:
                raise ValueError(_("时间范围内的执行记录过多，请缩小时间范围或增加筛选条件"))
            size = min(batch_size, ACTIVE_PROFILING_ES_QUERY_MAX_SIZE - offset)

    def _query_execution_hosts(self, params):
        """按执行定位键查该次执行的 Event，逐台主机返回主机执行行、维度和本机配置快照"""
        scheduled_at = params["scheduled_at"]
        filter_dict = {"scheduled_at": scheduled_at}
        if "task_id" in params:
            filter_dict["task_id"] = params["task_id"]
        else:
            filter_dict["schedule_type"] = "immediate"
        # finished 可能在执行后很久才上报（如 once_at 配置晚到），窗口放到当前；两端各放宽一个运行窗口容忍上报端时钟偏差
        queryset = self._build_queryset(
            scheduled_at - ACTIVE_PROFILING_RUNNING_WINDOW_MS,
            self.now + ACTIVE_PROFILING_RUNNING_WINDOW_MS,
            filter_dict,
        )
        events = self._query_events(queryset, 0, ACTIVE_PROFILING_ES_QUERY_MAX_SIZE)
        if len(events) >= ACTIVE_PROFILING_ES_QUERY_MAX_SIZE:
            raise ValueError(_("该次执行的主机过多，超出查询上限"))
        return [self._resolve_host(host_events) for __, host_events in groupby(events, key=self._host_execution_key)]

    @staticmethod
    def _execution_key(event):
        dimensions = event["dimensions"]
        return dimensions["schedule_type"], dimensions["scheduled_at"], dimensions.get("task_id")

    @staticmethod
    def _host_execution_key(event):
        dimensions = event["dimensions"]
        return (
            dimensions["schedule_type"],
            dimensions["scheduled_at"],
            dimensions.get("task_id"),
            dimensions["bk_host_id"],
        )

    def _resolve_host(self, events):
        """重复上报时排在前面的是最新一条；finished 决定终态，只有 started 时按超时派生 running/unknown。
        返回主机执行行、维度和本机配置快照"""
        latest_events = {}
        for event in events:
            latest_events.setdefault(event["event_name"], event)
        finished = latest_events.get(ACTIVE_PROFILING_FINISHED_EVENT)
        event = finished or latest_events[ACTIVE_PROFILING_STARTED_EVENT]
        dimensions = event["dimensions"]
        content = json.loads(event["event"]["content"])
        # 采集时长取本次执行配置的时长；Go Heap 是即时快照，没有 duration_sec
        duration_sec = content["config"]["collector_config"].get("duration_sec")

        host = {
            "bk_host_id": int(dimensions["bk_host_id"]),
            "ip": event["target"],
            "processes": [],
            "status": "",
            "error_type": "",
            "message": "",
            "started_at": content["started_at"],
            "finished_at": None,
            "duration_ms": None if duration_sec is None else duration_sec * 1000,
        }
        if finished:
            status = dimensions["status"]
            # 成功的 finished 不带执行信息
            message = _("采集成功") if status == "succeed" else content["message"]
            if (
                status in ACTIVE_PROFILING_SUCCEED_STATUSES
                and int(dimensions["scheduled_at"]) + self.retention_ms < self.now
            ):
                status = "outdate"
            host.update(
                # 旧版采集端没拿到进程时会省略 processes 字段，这类事件在 Event 保留期内仍会查到
                processes=content.get("processes", []),
                status=status,
                # 旧版采集端不上报 error_type，前端直接显示原始 message
                error_type=content.get("error_type", ""),
                message=message,
                finished_at=content["finished_at"],
            )
        else:
            # Go Heap 判定 unknown 时采集时长按 0 秒计算
            unknown_at = content["started_at"] + ((duration_sec or 0) + ACTIVE_PROFILING_UNKNOWN_GRACE_SEC) * 1000
            if self.now <= unknown_at:
                host["status"] = "running"
            else:
                host.update(status="unknown", message=_("请检查agent状态及版本信息，若持续异常请联系管理员"))
        return host, dimensions, content["config"]

    def _display_host_status(self, host):
        """主机行展示的状态：成功类结束后 Profiling 数据还在解析入库时显示 parsing，执行汇总仍按原状态"""
        if (
            host["status"] in ACTIVE_PROFILING_SUCCEED_STATUSES
            and self.now < host["finished_at"] + ACTIVE_PROFILING_PARSING_MS
        ):
            return "parsing"
        return host["status"]

    def _summarize_execution(self, hosts):
        """按执行下全部主机汇总外层状态、状态计数与起止时间"""
        statuses = [host["status"] for host in hosts]
        execution_status = self._aggregate_status(statuses)
        started_at = min(host["started_at"] for host in hosts)
        # unknown 主机没有结束时间，外层取已结束主机中最晚的一台
        finished_ats = [host["finished_at"] for host in hosts if host["finished_at"] is not None]
        finished_at = max(finished_ats) if finished_ats and execution_status != "running" else None
        return {
            "started_at": started_at,
            "finished_at": finished_at,
            # 同一执行的全部主机配置相同
            "duration_ms": hosts[0]["duration_ms"],
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
        if distinct_statuses & set(ACTIVE_PROFILING_SUCCEED_STATUSES):
            return "partial_succeed"
        if "outdate" in distinct_statuses:
            return "outdate"
        return "failed"

    def _query_recent_processes(self, params, field, limit):
        """进程候选按最近出现排序，只读最近的有限条 Event，不对整个时间范围分组计数"""
        queryset = self._build_list_queryset(params, self._build_execution_filter(params))
        candidates = Counter()
        for event in self._query_events(queryset, 0, ACTIVE_PROFILING_PROCESS_TOPK_RECENT_ROWS):
            # started 与作业下发失败补发的 finished 没有进程维度
            names = event["dimensions"].get("process_names", "").split(",")
            if field == "process_names":
                # 同一次采集的同名进程只计一次
                candidates.update(dict.fromkeys(filter(None, names)).keys())
            else:
                pids = event["dimensions"].get("process_pids", "").split(",")
                candidates.update(f"{name}:{pid}" for name, pid in zip(names, pids) if pid)
        return [{"value": value, "alias": value, "count": count} for value, count in islice(candidates.items(), limit)]

    def _query_group_counts(self, params, fields, limit):
        """按字段分组统计事件数，按事件数倒序返回 (各字段取值, 事件数)。
        与事件检索 TopK 的分组计数口径一致：只按计数字段分组计数，其余字段先在查询配置上分组，取值按位置对应"""
        *group_fields, count_field = fields
        alias = "a"
        q = (
            self._build_query_config(self._build_execution_filter(params))
            .time_field("time")
            .group_by(*group_fields)
            .metric(field=count_field, method="COUNT", alias=alias)
            .group_by(count_field)
            .order_by("_value desc")
        )
        queryset = (
            self._build_unify_queryset(params["start_time"], params["end_time"] + ACTIVE_PROFILING_RUNNING_WINDOW_MS)
            .time_agg(False)
            .instant()
            .add_query(q)
        )
        queryset.expression(alias)
        return [(tuple(row[field] for field in fields), row["_result_"]) for row in queryset.limit(limit)]

    def _get_retention_ms(self):
        """成功结果超过内置 Profiling 数据源的保留期（天）即为 outdate"""
        profile_datasource = ProfileDataSource.objects.filter(
            bk_biz_id=self.bk_biz_id, app_name=BUILTIN_PROFILING_APP_NAME
        ).first()
        if not profile_datasource or profile_datasource.bk_data_id == -1:
            raise ValueError(_("业务未开通主动 Profiling，请先开通"))
        return profile_datasource.retention * 24 * 3600 * 1000

    def _get_event_table_id(self):
        event_group = EventGroup.objects.filter(
            bk_biz_id=self.bk_biz_id, event_group_name=BUILTIN_EVENT_GROUP_NAME, is_delete=False
        ).first()
        if event_group is None:
            raise ValueError(_("业务未开通主动 Profiling，请先开通"))
        return event_group.table_id
