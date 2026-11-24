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
    ACTIVE_PROFILING_ES_FALLBACK_MAX_HOST_TERMS,
    ACTIVE_PROFILING_ES_QUERY_BATCH_SIZE,
    ACTIVE_PROFILING_ES_QUERY_MAX_SIZE,
    ACTIVE_PROFILING_FINISHED_EVENT,
    ACTIVE_PROFILING_PARSING_MS,
    ACTIVE_PROFILING_PLANNED_SCHEDULE_TYPES,
    ACTIVE_PROFILING_PROCESS_TOPK_RECENT_ROWS,
    ACTIVE_PROFILING_RUNNING_WINDOW_MS,
    ACTIVE_PROFILING_STARTED_EVENT,
    ACTIVE_PROFILING_SUCCEED_STATUSES,
    ACTIVE_PROFILING_UNKNOWN_GRACE_SEC,
)
from apm.core.handlers.profile.active_profiling import (
    PROCESS_CANDIDATE_PATTERN,
    STARTED_HOST_STATUSES,
    build_cancelled_message,
)
from apm.models import ProfileDataSource
from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder, UnifyQuerySet
from bkmonitor.utils.request import get_request_tenant_id
from constants.apm import BUILTIN_EVENT_GROUP_NAME, BUILTIN_PROFILING_APP_NAME
from constants.data_source import DataSourceLabel, DataTypeLabel
from metadata.models import EventGroup


class ActiveProfilingEventQueryHandler:
    """按 Event ES 聚合的查询，source=es 时使用，保留一期的查询能力：
    已采数据、任务历史、执行详情按同一口径把 started/finished 配成主机执行，outdate、unknown 等都在查询时派生。
    MySQL 查询在预计算落后时用两个列表取落后区间内的计划执行，params 带上 overrides，
    把 SaaS 只写进 MySQL 的信息覆盖到 Event 配出的行上：
    - hosts：{主机执行键: {"finished_at": ..., "cancelled_by": ...}}，SaaS 受理的取消：采集端的 finished 还没上报时覆盖为 cancelled，
      取消人只有 SaaS 记录，finished 已上报为 cancelled 时也带上
    - task_names：{执行键: 任务名}，改名只改执行表
    覆盖后状态与任务名会变，这两项不下推 ES，在内存中按覆盖后的值筛选"""

    def __init__(self, bk_biz_id):
        self.bk_biz_id = bk_biz_id
        self.now = int(time.time() * 1000)
        self.retention_ms = self._get_retention_ms()
        self.event_table_id = self._get_event_table_id()

    def query_hosts(self, params):
        """已采数据：一台主机的一次执行一行，返回本页的行与筛选后的总行数"""
        statuses = params.get("filters", {}).get("status") or []
        # unknown 取决于有没有 finished，ES 筛不出来，只能全量配对
        if "unknown" in statuses:
            raise ValueError(_("暂不支持按 unknown 状态筛选"))

        offset = params["offset"]
        end = offset + params["limit"]
        # 每行通常只有 started/finished 两条，多取一条确认最后一行已经完整；重复上报或内存筛选导致不够时再按批续读
        events = self._iter_events(
            self._build_hosts_queryset(params, statuses), end * 2 + 1, ACTIVE_PROFILING_ES_QUERY_BATCH_SIZE
        )
        overrides = self._get_overrides(params)
        rows = (
            self._build_host_row(key, host_events, overrides)
            for key, host_events in self._iter_matched_hosts(events, self._build_process_matcher(params))
        )
        # running 要看有没有 finished，成功类要排除还在解析中的行，多选时下推的条件只是各状态的并集，
        # 都要配对后在内存中按行状态筛选
        row_filter = self._build_row_filter(
            params, statuses, lambda row: row["status"], lambda row: row["task"]["name"]
        )
        if row_filter:
            rows = filter(row_filter, rows)
        return self._paginate(rows, offset, end)

    def list_executions(self, params):
        """任务历史：按执行汇总全部主机，一次执行一行，返回本页的行与筛选后的总行数"""
        statuses = params.get("filters", {}).get("status") or []
        # 执行状态由全部主机聚合，unknown 主机取决于有没有 finished，ES 筛不出来
        if "unknown" in statuses:
            raise ValueError(_("暂不支持按 unknown 状态筛选"))

        row_filter = self._build_row_filter(
            params, statuses, lambda row: row["execution_status"], lambda row: row["task_name"]
        )
        host_filter = self._build_host_filter(params)
        if host_filter:
            return self._query_host_matched_executions(params, row_filter, host_filter)
        return self._scan_executions(params, row_filter)

    @staticmethod
    def _get_overrides(params):
        overrides = params.get("overrides") or {}
        return {"hosts": overrides.get("hosts") or {}, "task_names": overrides.get("task_names") or {}}

    def _build_row_filter(self, params, statuses, get_status, get_task_name):
        """配对后在内存中筛选的条件：状态都在内存中筛；任务名有覆盖时不下推，也在内存中按覆盖后的名称包含匹配"""
        task_name = params.get("filters", {}).get("task_name") if self._get_overrides(params)["task_names"] else None
        if not statuses and not task_name:
            return None
        return lambda row: (
            (not statuses or get_status(row) in statuses) and (not task_name or task_name in get_task_name(row))
        )

    def _override_host(self, host, key, overrides):
        """SaaS 已受理取消、采集端的 finished 还没上报时，Event 配出的还是 running/unknown，以 MySQL 的取消为准；
        已有 finished 时以 Event 为准，与预计算的覆盖顺序一致。最终为 cancelled 时执行信息带上 SaaS 记录的取消人"""
        override = overrides["hosts"].get(self._normalize_host_execution_key(key))
        if not override:
            return
        if host["status"] in STARTED_HOST_STATUSES:
            host.update(status="cancelled", finished_at=override["finished_at"])
        if host["status"] == "cancelled":
            host["message"] = build_cancelled_message(override["cancelled_by"])

    @staticmethod
    def _override_task_name(key, dimensions, overrides):
        schedule_type, scheduled_at, task_id = key[:3]
        return overrides["task_names"].get(
            (schedule_type, int(scheduled_at), int(task_id or 0)), dimensions["task_name"]
        )

    def query_topk(self, params):
        """搜索框候选值，与两个列表一样按 scheduled_at 选取，按主机执行数倒序取前 limit 个，与 MySQL 查询同一口径"""
        if params.get("keyword"):
            raise ValueError(_("暂不支持按关键字搜索候选"))
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

    def _build_hosts_queryset(self, params, statuses):
        """筛选全部下推 ES：终态再按 status 维度筛选，outdate 是过期的成功类终态，多选取各状态的并集；
        running 要看有没有 finished，不能按 status 筛，只收窄 scheduled_at"""
        filter_dict = {**self._build_execution_filter(params), **self._build_host_filter(params)}
        # 有取消覆盖时 running 的 Event 可能展示为 cancelled，状态不下推
        if statuses and "running" not in statuses and not self._get_overrides(params)["hosts"]:
            dimension_statuses = []
            for status in statuses:
                dimension_statuses.extend(ACTIVE_PROFILING_SUCCEED_STATUSES if status == "outdate" else [status])
            filter_dict["status"] = list(dict.fromkeys(dimension_statuses))
        return self._build_list_queryset(params, filter_dict)

    def _build_host_row(self, key, events, overrides):
        schedule_type, scheduled_at, task_id, __ = key
        row, dimensions, __ = self._resolve_host(events)
        self._override_host(row, key, overrides)
        task = {"name": self._override_task_name(key, dimensions, overrides), "schedule_type": schedule_type}
        if task_id:
            task = {"task_id": int(task_id), **task}
        # 只有取消的行带执行信息，只有失败的行带失败类型，与 MySQL 查询的口径一致
        if row["status"] != "cancelled":
            del row["message"]
        if row["status"] != "failed":
            del row["error_type"]
        row.update(
            status=self._display_host_status(row),
            task=task,
            collection_method=dimensions["collection_method"],
            collection_type=dimensions["collection_type"],
            creator=dimensions["creator"],
            scheduled_at=int(scheduled_at),
        )
        return row

    def _scan_executions(self, params, row_filter):
        """筛选都是执行级维度时一次扫描，同一执行的 Event 相邻，边读边按执行汇总，执行状态在内存中筛选"""
        offset = params["offset"]
        end = offset + params["limit"]
        queryset = self._build_list_queryset(params, self._build_execution_filter(params))
        overrides = self._get_overrides(params)
        rows = (
            self._build_execution_row(key, events, overrides)
            for key, events in groupby(self._iter_execution_events(queryset, end), key=self._execution_key)
        )
        if row_filter:
            rows = filter(row_filter, rows)
        return self._paginate(rows, offset, end)

    def _query_host_matched_executions(self, params, row_filter, host_filter):
        """主机/进程只决定选中哪些执行，不改变执行的汇总结果：先按主机筛出命中的执行，再回查这些执行的全部主机"""
        offset = params["offset"]
        end = offset + params["limit"]
        execution_filter = self._build_execution_filter(params)
        queryset = self._build_list_queryset(params, {**execution_filter, **host_filter})
        matcher = self._build_process_matcher(params)
        keys = (
            key
            for key, events in groupby(self._iter_execution_events(queryset, end), key=self._execution_key)
            if matcher is None or any(True for __ in self._iter_matched_hosts(events, matcher))
        )
        if not row_filter:
            # 每个命中的执行就是一行，offset 之前的执行不用回查，总数即命中的执行数
            page = self._paginate(keys, offset, end)
            return {**page, "data": self._query_execution_rows(params, execution_filter, page["data"])}

        # 状态（及覆盖后的任务名）要回查全部主机汇总后才知道，每轮只回查还缺的行数个执行，
        # 不够时接着上一轮继续找命中的执行
        rows = []
        while len(rows) < end:
            chunk = list(islice(keys, end - len(rows)))
            if not chunk:
                # 命中的执行已全部回查过
                return {"data": rows[offset:], "total": len(rows)}
            rows.extend(self._query_filtered_rows(params, execution_filter, chunk, row_filter))
        return {
            "data": rows[offset:],
            "total": self._count_filtered_executions(params, execution_filter, keys, row_filter, len(rows)),
        }

    def _query_filtered_rows(self, params, execution_filter, keys, row_filter):
        return list(filter(row_filter, self._query_execution_rows(params, execution_filter, keys)))

    def _count_filtered_executions(self, params, execution_filter, keys, row_filter, counted):
        """本页之后命中的执行再回查一次统计总数；剩余的执行过多或超出查询上限时不再回查，总数未知"""
        try:
            remaining = list(islice(keys, ACTIVE_PROFILING_ES_FALLBACK_MAX_HOST_TERMS + 1))
            if len(remaining) > ACTIVE_PROFILING_ES_FALLBACK_MAX_HOST_TERMS:
                return None
            return counted + len(self._query_filtered_rows(params, execution_filter, remaining, row_filter))
        except ValueError:
            return None

    @staticmethod
    def _paginate(rows, offset, end):
        """rows 惰性产出筛选后的行：取到本页末尾后接着读完，得到总行数；
        读到查询上限还没读完时总数未知，返回 None，本页的行不受影响"""
        head = list(islice(rows, end))
        total = len(head)
        if total == end:
            try:
                total += sum(1 for __ in rows)
            except ValueError:
                total = None
        return {"data": head[offset:], "total": total}

    def _iter_matched_hosts(self, events, matcher):
        """按主机执行分组；带 进程名:PID 精确条件时只保留同一进程两者都相等的主机执行"""
        for key, host_events in groupby(events, key=self._host_execution_key):
            host_events = list(host_events)
            if matcher is None or matcher(host_events):
                yield key, host_events

    @staticmethod
    def _build_process_matcher(params):
        """PID 候选的 进程名:PID 要按同一进程精确匹配：维度里进程名与 PID 分开拼接，下推只能按 PID 包含匹配，
        复用该 PID 的其他进程、包含该数字的其他 PID 也会命中，配对后再按 finished 里成对的 processes 筛一遍，
        与 MySQL 查询同一口径。没有这类条件时返回 None，下推的条件已经精确"""
        exact_processes, plain_pids = set(), []
        for value in params.get("filters", {}).get("process_pids") or []:
            process = PROCESS_CANDIDATE_PATTERN.fullmatch(value)
            if process:
                # 候选可能来自维度（进程名里的逗号已归一化为 _），两边都归一化后比较
                exact_processes.add((process["process_name"].replace(",", "_"), process["pid"]))
            else:
                plain_pids.append(value.replace(",", "_"))
        if not exact_processes:
            return None

        def match(host_events):
            # 重复上报时最新一条在前；进程信息只在 finished 里
            finished = next(
                (event for event in host_events if event["event_name"] == ACTIVE_PROFILING_FINISHED_EVENT), None
            )
            if finished is None:
                return False
            # 同一筛选项的多个值命中任一即可：直接输入的 PID 仍按包含匹配
            process_pids = finished["dimensions"].get("process_pids", "")
            if any(pid in process_pids for pid in plain_pids):
                return True
            processes = json.loads(finished["event"]["content"]).get("processes", [])
            return any(
                (process["process_name"].replace(",", "_"), str(process["pid"])) in exact_processes
                for process in processes
            )

        return match

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
        overrides = self._get_overrides(params)
        return [
            self._build_execution_row(key, execution_events, overrides)
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

    def _build_execution_row(self, key, events, overrides):
        schedule_type, scheduled_at, task_id = key
        hosts = []
        for host_key, host_events in groupby(events, key=self._host_execution_key):
            host, dimensions, __ = self._resolve_host(host_events)
            # 先覆盖再汇总，执行状态与状态计数按覆盖后的主机计
            self._override_host(host, host_key, overrides)
            hosts.append(host)
        row = {"task_id": int(task_id)} if task_id else {}
        row.update(
            task_name=self._override_task_name(key, dimensions, overrides),
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

    def _build_query_config(
        self, filter_dict, event_names=(ACTIVE_PROFILING_STARTED_EVENT, ACTIVE_PROFILING_FINISHED_EVENT)
    ):
        return (
            QueryConfigBuilder((DataTypeLabel.EVENT, DataSourceLabel.CUSTOM))
            .table(self.event_table_id)
            .filter(
                bk_tenant_id=get_request_tenant_id(),
                bk_biz_id=self.bk_biz_id,
                event_name=list(event_names),
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
        """两个列表共用的执行级筛选，任务 ID、任务名、执行方式、采集方式与类型在同一次执行内一致。
        dimension 都是 keyword，scheduled_at 按字典序比较，13 位毫秒时间戳的字典序与数值序一致"""
        filters = params.get("filters", {})
        optional_filters = {
            # 有任务名覆盖时按覆盖后的名称在内存中筛，见 _build_row_filter
            "task_name__include": None if self._get_overrides(params)["task_names"] else filters.get("task_name"),
            "schedule_type": filters.get("schedule_types"),
            "collection_method": filters.get("collection_methods"),
            "collection_type": filters.get("collection_types"),
        }
        filter_dict = {key: value for key, value in optional_filters.items() if value}
        if filters.get("task_id"):
            # 任务 ID 是计划 ID，只匹配计划执行：立即执行 Event 的 task_id 是执行行自己的 id，与计划 ID 不在同一取值空间；
            # 从计划点立即执行的关联只记在执行表，Event 里没有
            schedule_types = [
                schedule_type
                for schedule_type in ACTIVE_PROFILING_PLANNED_SCHEDULE_TYPES
                if schedule_type in (filters.get("schedule_types") or ACTIVE_PROFILING_PLANNED_SCHEDULE_TYPES)
            ]
            if not schedule_types:
                raise ValueError(_("暂不支持按计划筛选立即执行"))
            filter_dict.update(task_id=str(filters["task_id"]), schedule_type=schedule_types)

        lower, upper = self._build_scheduled_at_range(params, filters.get("status") or [])
        filter_dict.update(scheduled_at__gte=lower, scheduled_at__lte=upper)
        return filter_dict

    def _build_scheduled_at_range(self, params, statuses):
        """running 只会出现在最近一个运行窗口内；过期按 scheduled_at 判定，与行状态同一口径。
        多选时取各状态时间范围的并集，范围内不属于所选状态的行由调用方在内存中筛掉"""
        start_time, end_time = params["start_time"], params["end_time"]
        if not statuses:
            return start_time, end_time
        expire_before = self.now - self.retention_ms
        ranges = []
        for status in statuses:
            lower, upper = start_time, end_time
            if status == "running":
                lower = max(lower, self.now - ACTIVE_PROFILING_RUNNING_WINDOW_MS)
            elif status == "outdate":
                upper = min(upper, expire_before - 1)
            elif status in ACTIVE_PROFILING_SUCCEED_STATUSES:
                lower = max(lower, expire_before)
            ranges.append((lower, upper))
        # 某个状态的范围为空（lower > upper）时不参与并集，全部为空时保留空范围，查不到数据
        valid_ranges = [(lower, upper) for lower, upper in ranges if lower <= upper] or ranges[:1]
        return min(lower for lower, __ in valid_ranges), max(upper for __, upper in valid_ranges)

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
                # 维度里进程名与 PID 分开拼接，无法按同一进程配对，PID 候选的 进程名:PID 先按 PID 下推，
                # 配对后再由 _build_process_matcher 按同一进程精确筛选
                process = PROCESS_CANDIDATE_PATTERN.fullmatch(value)
                pids.append(process["pid"] if process else value.replace(",", "_"))
            filter_dict["process_pids__include"] = pids
        return filter_dict

    def _query_events(self, queryset, offset, size):
        return list(queryset.offset(offset).limit(size))

    def _iter_events(self, queryset, first_size, batch_size):
        """从头分批读取，调用方凑够行数后停止迭代，后面的批次不会查询；
        续读的批次逐次翻倍，凑够本页后还要读完才能统计总行数，避免请求次数随数据量线性增长"""
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
            batch_size *= 2

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

    def resolve_hosts(self, keys):
        """按主机执行键批量回查 Event，返回 {主机执行键: 主机执行行}，供 MySQL 查询校正预计算没按时写入的主机行。
        键为 (schedule_type, scheduled_at, task_id, bk_host_id)，改造前上报的立即执行没有 task_id，记为 0；
        状态保留原始终态，不派生 outdate，由调用方按自己的口径派生"""
        keys = set(keys)
        if not keys:
            return {}
        scheduled_ats = sorted({key[1] for key in keys})
        bk_host_ids = sorted({key[3] for key in keys})
        # dimension 都是 keyword；只按 scheduled_at 与主机筛选，执行方式与任务 ID 在内存中按执行键精确匹配
        filter_dict = {"scheduled_at": [str(scheduled_at) for scheduled_at in scheduled_ats]}
        # 主机多时不按主机下推，避免查询条件过长
        if len(bk_host_ids) <= ACTIVE_PROFILING_ES_FALLBACK_MAX_HOST_TERMS:
            filter_dict["bk_host_id"] = [str(bk_host_id) for bk_host_id in bk_host_ids]
        # finished 可能在执行后很久才上报，窗口放到当前；两端各放宽一个运行窗口容忍上报端时钟偏差
        queryset = self._build_queryset(
            scheduled_ats[0] - ACTIVE_PROFILING_RUNNING_WINDOW_MS,
            self.now + ACTIVE_PROFILING_RUNNING_WINDOW_MS,
            filter_dict,
        )
        events = self._query_events(queryset, 0, ACTIVE_PROFILING_ES_QUERY_MAX_SIZE)
        groups = [
            (self._normalize_host_execution_key(key), list(host_events))
            for key, host_events in groupby(events, key=self._host_execution_key)
        ]
        if len(events) >= ACTIVE_PROFILING_ES_QUERY_MAX_SIZE:
            # 读满上限时最后一组可能不完整，不用它校正
            groups = groups[:-1]
        return {key: self._resolve_latest_host(host_events)[0] for key, host_events in groups if key in keys}

    def query_latest_planned_execution(self, reported_after, reported_before):
        """业务在 Event ES 里计划时间最晚的一次计划执行，只看 [reported_after, reported_before] 内上报的 Event；
        返回执行键 (schedule_type, scheduled_at, task_id)，没有计划执行时返回 None"""
        queryset = self._build_queryset(
            reported_after, reported_before, {"schedule_type": list(ACTIVE_PROFILING_PLANNED_SCHEDULE_TYPES)}
        )
        # 按 scheduled_at 倒序，第一条即计划时间最晚的执行
        events = self._query_events(queryset, 0, 1)
        if not events:
            return None
        schedule_type, scheduled_at, task_id = self._execution_key(events[0])
        return schedule_type, int(scheduled_at), int(task_id or 0)

    @staticmethod
    def _normalize_host_execution_key(key):
        """Event 维度都是字符串，转为与执行表一致的类型"""
        schedule_type, scheduled_at, task_id, bk_host_id = key
        return schedule_type, int(scheduled_at), int(task_id or 0), int(bk_host_id)

    def _resolve_host(self, events):
        """主机执行行在 Event 原始状态的基础上，成功类终态按 scheduled_at 超过保留期派生为 outdate"""
        host, dimensions, config = self._resolve_latest_host(events)
        if (
            host["status"] in ACTIVE_PROFILING_SUCCEED_STATUSES
            and int(dimensions["scheduled_at"]) + self.retention_ms < self.now
        ):
            host["status"] = "outdate"
        return host, dimensions, config

    def _resolve_latest_host(self, events):
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
            # 成功的 finished 不带执行信息，取消的原始信息是英文
            message = content["message"]
            if status == "succeed":
                message = _("采集成功")
            elif status == "cancelled":
                message = build_cancelled_message()
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
        """按字段分组统计主机执行数，按主机执行数倒序返回 (各字段取值, 主机执行数)。
        每次主机执行有一条 started，只数 started，与 MySQL 按主机执行计数同一口径；
        作业下发失败的立即执行只补发 finished，不计入，计数只用于排序，按可接受处理。
        与事件检索 TopK 的分组计数口径一致：只按计数字段分组计数，其余字段先在查询配置上分组，取值按位置对应"""
        *group_fields, count_field = fields
        alias = "a"
        q = (
            self._build_query_config(self._build_execution_filter(params), [ACTIVE_PROFILING_STARTED_EVENT])
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
