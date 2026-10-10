"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import arrow
from django.db.models import CharField, Count, Value
from django.utils import timezone

from apps.log_search.constants import (
    ExportErrorCode,
    ExportJobStatus,
    ExportPartStatus,
    ExportSearchType,
    ExportStage,
    ExportStatus,
    ExportType,
    IndexSetType,
)
from apps.log_search.export.models import ExportJob, ExportPart, ExportPlan
from apps.utils.drf import DataPageNumberPagination
from apps.utils.local import get_request_app_code, get_request_external_username


def load_export_progress(jobs):
    """批量加载任务进度，历史分页后调用，避免逐个查询分片。"""
    jobs = {job.pk: job for job in jobs}
    if not jobs:
        return
    for job in jobs.values():
        job.export_progress = {
            "job_status": job.status,
            "plan_version": job.plan_version,
            "planned_parts": None,
            "parts_total": 0,
            "parts_success": 0,
            "parts_failed": 0,
            "status_counts": dict.fromkeys((status for status, _ in ExportPartStatus.CHOICES), 0),
            "stage_counts": dict.fromkeys((ExportStage.DOWNLOAD_LOG, ExportStage.PACKAGE, ExportStage.UPLOAD), 0),
        }
    for plan in ExportPlan.objects.filter(job_id__in=jobs).values("job_id", "plan_version", "planned_parts"):
        job = jobs[plan["job_id"]]
        if plan["plan_version"] == job.plan_version:
            job.export_progress["planned_parts"] = plan["planned_parts"]
    counts = ExportPart.objects.filter(job_id__in=jobs).values("job_id", "status", "stage").annotate(count=Count("pk"))
    for row in counts:
        progress = jobs[row["job_id"]].export_progress
        status, stage, count = row["status"], row["stage"], row["count"]
        progress["status_counts"][status] = progress["status_counts"].get(status, 0) + count
        # 细分父片只保留状态计数，不计入有效分片总数；阶段只统计正在执行的分片。
        if status not in ExportPartStatus.NON_LEAF:
            progress["parts_total"] += count
        if status == ExportPartStatus.SUCCESS:
            progress["parts_success"] += count
        elif status == ExportPartStatus.FAILED:
            progress["parts_failed"] += count
        if status in ExportPartStatus.EXECUTING and stage in progress["stage_counts"]:
            progress["stage_counts"][stage] += count


def sharded_job_history_item(job):
    """把分片导出任务映射为旧导出历史的返回结构，供新旧链路合并的历史接口复用。"""
    if job.status == ExportJobStatus.SUCCESS:
        export_status = (
            ExportStatus.DOWNLOAD_EXPIRED
            if job.expires_at is not None and job.expires_at <= timezone.now()
            else ExportStatus.SUCCESS
        )
    elif job.status in (ExportJobStatus.FAILED, ExportJobStatus.CANCELED):
        export_status = ExportStatus.FAILED
    elif job.status == ExportJobStatus.FINALIZING:
        # 合并整包/生成清单，最接近旧链路的"打包"
        export_status = ExportStatus.EXPORT_PACKAGE
    elif job.status == ExportJobStatus.RUNNING:
        # 分片取数，对应旧链路的"取数"
        export_status = ExportStatus.DOWNLOAD_LOG
    elif job.status in (ExportJobStatus.PENDING, ExportJobStatus.PLANNING, ExportJobStatus.READY):
        # 尚未开始取数，置空让前端显示"未开始"
        export_status = None
    else:
        # 未知/空状态兜底为失败，避免前端永久显示进行中
        export_status = ExportStatus.FAILED

    index_set_type = job.index_set_type or IndexSetType.SINGLE.value
    if not hasattr(job, "export_progress"):
        load_export_progress([job])

    item = {
        "id": job.pk,
        "engine": "sharded",
        "progress": job.export_progress,
        "error_code": job.error_code,
        "search_dict": job.raw_params or job.search_params,
        "start_time": job.start_time,
        "end_time": job.end_time,
        "export_type": ExportType.ASYNC,
        "export_status": export_status,
        "error_msg": job.error_detail or (ExportErrorCode.label(job.error_code) if job.error_code else ""),
        "download_url": "",
        "export_pkg_name": "full.jsonl.gz" if job.merged_object_key else "",
        "export_pkg_size": max(round(job.merged_bytes / (1024 * 1024), 2), 0.01) if job.merged_bytes else None,
        "export_created_at": job.created_at,
        "export_created_by": job.created_by,
        "export_completed_at": job.completed_at,
        "exported_count": job.actual_total,
        "export_total_count": job.estimated_total,
        "download_count": 0,
        "download_able": export_status == ExportStatus.SUCCESS,
        # 一期不判数据保留期，重试由前端拿 search_dict 重新发起创建即可
        "retry_able": True,
        "index_set_type": index_set_type,
    }
    if index_set_type == IndexSetType.UNION.value:
        item["log_index_set_ids"] = job.index_set_ids
    elif index_set_type == IndexSetType.SINGLE.value:
        item["log_index_set_id"] = (job.index_set_ids or [None])[0]
    return item


def sharded_job_detail(job):
    """返回任务详情及全部分片的当前执行结果，包含细分父片。"""
    item = sharded_job_history_item(job)
    item.update(
        space_uid=job.space_uid,
        search_type=job.search_type,
        requested_parallelism=job.requested_parallelism,
        started_at=job.started_at,
        expires_at=job.expires_at,
        planning_enqueued_at=job.planning_enqueued_at,
        planning_started_at=job.planning_started_at,
        planning_attempts=job.planning_attempts,
        finalization_enqueued_at=job.finalization_enqueued_at,
        finalization_started_at=job.finalization_started_at,
        finalization_attempts=job.finalization_attempts,
    )
    parts = job.parts.order_by("plan_version", "part_no", "id").values(
        "id",
        "part_no",
        "plan_version",
        "parent_part_id",
        "start_time",
        "end_time",
        "oversized",
        "status",
        "stage",
        "attempts",
        "task_id",
        "estimated_rows",
        "actual_rows",
        "actual_bytes",
        "compressed_bytes",
        "checksum",
        "started_at",
        "finished_at",
        "updated_at",
        "error_code",
        "error_detail",
    )
    part_items = list(parts)
    for part in part_items:
        part["artifact_id"] = str(part["id"]) if part["status"] == ExportPartStatus.SUCCESS else None
    item["parts"] = part_items
    return item


def sharded_export_history_queryset(
    bk_biz_id,
    search_type=ExportSearchType.INDEX_SET,
    index_set_type=None,
    index_set_id=None,
    index_set_ids=None,
    table_id_conditions=None,
    created_by=None,
    start_time=None,
    end_time=None,
):
    """构建分片导出历史查询，供新旧链路合并分页。"""
    query_set = ExportJob.objects.filter(
        bk_biz_id=bk_biz_id, source_app_code=get_request_app_code(), search_type=search_type
    )
    # 索引集检索按固化的 index_set_type 直接 SQL 过滤（single/union），避免按 index_set_ids 长度在内存里过滤
    if index_set_type:
        query_set = query_set.filter(index_set_type=index_set_type)
    external_username = get_request_external_username()
    if external_username:
        query_set = query_set.filter(created_by=external_username)
    elif created_by:
        query_set = query_set.filter(created_by=created_by)

    if search_type == ExportSearchType.SCENE:
        if table_id_conditions:
            query_set = query_set.filter(search_params__table_id_conditions=table_id_conditions)
    elif index_set_ids:
        query_set = query_set.filter(index_set_ids=index_set_ids)
    elif index_set_id:
        query_set = query_set.filter(index_set_ids=[index_set_id])

    if start_time is not None:
        query_set = query_set.filter(created_at__gte=arrow.get(start_time / 1000).datetime)
    if end_time is not None:
        query_set = query_set.filter(created_at__lte=arrow.get(end_time / 1000).datetime)

    return query_set


def paginate_export_history(query_set, job_query_set, request, view):
    """合并新旧任务的轻量索引进行数据库分页，只加载当前页的完整任务。"""
    task_rows = (
        query_set.order_by()
        .annotate(history_engine=Value("legacy", output_field=CharField()))
        .values("id", "created_at", "history_engine")
    )
    job_rows = (
        job_query_set.order_by()
        .annotate(history_engine=Value("sharded", output_field=CharField()))
        .values("id", "created_at", "history_engine")
    )
    # 两个表的自增 ID 可能相同，来源作为排序兜底，且 UNION ALL 保留两条记录。
    rows = task_rows.union(job_rows, all=True).order_by("-created_at", "-id", "history_engine")
    pg = DataPageNumberPagination()
    pg.page_size = pg.PAGE_SIZE
    page_rows = pg.paginate_queryset(queryset=rows, request=request, view=view)
    tasks = query_set.in_bulk([row["id"] for row in page_rows if row["history_engine"] == "legacy"])
    jobs = job_query_set.in_bulk([row["id"] for row in page_rows if row["history_engine"] == "sharded"])
    load_export_progress(jobs.values())
    records = {"legacy": tasks, "sharded": jobs}
    history = [records[row["history_engine"]][row["id"]] for row in page_rows]
    return pg, history
