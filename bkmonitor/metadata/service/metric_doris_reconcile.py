"""推进独立 RT 的 BKBase 下发、DorisJob 和查询路由。每一步提交后可单独恢复。"""

import logging
from contextlib import ExitStack, closing
from datetime import datetime, timezone

from django.db import transaction
from django.utils import timezone as django_timezone

from metadata.config import DATABASE_CONNECTION_NAME
from metadata.models import BkBaseResultTable, DorisStorage, ResultTable, Space, StorageClusterRecord
from metadata.models.data_link import DataBusConfig, DorisJobConfig, MetricDorisPipeline
from metadata.models.data_link.metric_options import MetricAggregateOption, metric_fields
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.service import doris_job
from metadata.service.doris_job_config import render_configs, save_configs
from metadata.service.metric_aggregate import create_aggregate_table, qualified, successful_cutover
from metadata.service.metric_doris import (
    AGGREGATE,
    binding_for,
    declare,
    get_source_option,
    options_for,
    physical_ref,
    sync_fields,
)

logger = logging.getLogger("metadata")


def component_ready(component):
    if component.status == "Ok":
        return True
    status = component.component_status
    if status:
        component.status = status
        component.save(update_fields=["status"])
    return status == "Ok"


def published_source(pipeline, storage):
    source = DorisStorage.get_by_table_id(storage.bk_tenant_id, pipeline.source.table_id)
    if source.storage_cluster_id != storage.storage_cluster_id:
        return None  # 源可能仍在准备同一目标集群上的物理表。
    if not source.bkbase_table_id or not source.physical_tables.get("main"):
        return None
    output = pipeline.source.metricdorispipeline.data_link
    return output_binding(output, source.bkbase_table_id)


def output_binding(link, bkbase_table_id):
    from metadata.models.data_link import ResultTableConfig

    output = ResultTableConfig.objects.get(
        data_link_name=link.pk, bk_tenant_id=link.bk_tenant_id, bkbase_table_id=bkbase_table_id
    )
    return binding_for(output)


def ensure_running(pipeline, storage, binding):
    """复用现有 draft -> pending -> ready 流程。drop 完成后原记录成为可编辑草稿。"""
    source = published_source(pipeline, storage)
    if source is None or not component_ready(source):
        return None
    tenant = storage.bk_tenant_id
    option = MetricAggregateOption.model_validate(options_for(pipeline.result_table)[AGGREGATE])
    config = {
        "cluster_id": storage.storage_cluster_id,
        "database": physical_ref(binding)["database"],
        "name": pipeline.output.name,
        "interval_minutes": option.interval_minutes,
        "template_key": option.template_key,
        "sources": {"raw": physical_ref(source)},
        "targets": {"aggregate": physical_ref(binding)},
        "params": {**pipeline.layout, "lookback_minutes": option.lookback_minutes},
    }
    jobs = DorisJobConfig.objects.filter(data_link_id=pipeline.data_link_id, cluster_id=storage.storage_cluster_id)
    job = jobs.filter(name=pipeline.output.name).first()
    if job and job.reconcile_status in ("failed", "verifying"):
        raise ValueError(f"DorisJob {job.pk}: {job.reconcile_status} {job.status_reason}")
    if job and job.reconcile_status == "pending":
        return None
    if job is None or job.reconcile_status == "draft":
        (pk,) = save_configs(tenant, pipeline.data_link_id, config, job_id=job.pk if job else None)
        doris_job.request_action(tenant, pk, "create")
        return None
    (desired,) = render_configs(config)
    if job.template_inputs != desired["template_inputs"] or job.interval_minutes != option.interval_minutes:
        doris_job.request_action(tenant, job.pk, "drop")
        return None
    with closing(doris_job.connect(job)) as conn, conn.cursor() as cur:
        remote = doris_job.remote_job(cur, job.name)
    if not remote or int(remote["Id"]) != job.remote_id:
        raise ValueError(f"DorisJob {job.pk} 与绑定的 FE Job ID 不符")
    if remote["Status"] == "PAUSED":
        doris_job.request_action(tenant, job.pk, "resume")
        return None
    if remote["Status"] != "RUNNING":
        raise ValueError(f"DorisJob {job.pk}: {remote['Status']}")
    return job


def pause_jobs(pipeline, *, include_current):
    jobs = pipeline.data_link.doris_jobs.all()
    if not include_current:
        jobs = jobs.exclude(name=pipeline.output.name)
    done = True
    for job in jobs:
        if job.reconcile_status in ("failed", "verifying"):
            raise ValueError(f"DorisJob {job.pk}: {job.reconcile_status} {job.status_reason}")
        if job.reconcile_status == "pending":
            if job.pending_action in ("create", "resume"):
                doris_job.request_action(pipeline.data_link.bk_tenant_id, job.pk, "cancel")
            done = False
            continue
        if job.remote_id is None:
            continue
        with closing(doris_job.connect(job)) as conn, conn.cursor() as cur:
            remote = doris_job.remote_job(cur, job.name)
        if remote and int(remote["Id"]) == job.remote_id and remote["Status"] == "PAUSED":
            continue
        doris_job.request_action(pipeline.data_link.bk_tenant_id, job.pk, "pause")
        done = False
    return done


def sync_retention(cursor, target, days):
    table = qualified(target)
    cursor.execute(f"SHOW CREATE TABLE {table}")
    ddl = cursor.fetchone()["Create Table"]
    if f'"dynamic_partition.start" = "-{int(days)}"' not in ddl:
        cursor.execute(f'ALTER TABLE {table} SET ("dynamic_partition.start" = "-{int(days)}")')


def publish_storage(pipeline, storage, binding, cutover, labels):
    rt, output = pipeline.result_table, pipeline.output
    rotated = bool(storage.bkbase_table_id and storage.bkbase_table_id != output.bkbase_table_id)
    record, _ = StorageClusterRecord.switch_current_cluster(
        table_id=rt.table_id,
        bk_tenant_id=rt.bk_tenant_id,
        target_cluster_id=storage.storage_cluster_id,
        target_storage_type="doris",
        creator=rt.last_modify_user or rt.creator,
        switch_time=cutover,
        force_new_segment=rotated,
    )
    for entry in (storage, record):
        entry.bkbase_table_id = output.bkbase_table_id
        entry.physical_tables = binding.physical_tables
        entry.save(update_fields=["bkbase_table_id", "physical_tables"])
    storage.table_type = (
        DorisStorage.DUPLICATE_TABLE_TYPE if pipeline.source_id is None else DorisStorage.PRIMARY_TABLE_TYPE
    )
    storage.save(update_fields=["table_type", "storage_cluster_id"])
    sync_fields(rt, metric_fields(labels, aggregate=pipeline.source_id is not None))
    defaults = {
        "bkbase_rt_name": output.name,
        "bkbase_table_id": output.bkbase_table_id,
        "storage_cluster_id": storage.storage_cluster_id,
        "status": "Ok",
    }
    if pipeline.source_id is None:
        defaults["bkbase_data_name"] = DataBusConfig.objects.get(data_link_name=pipeline.data_link_id).source_name
    BkBaseResultTable.objects.filter(data_link_name=pipeline.data_link_id, bk_tenant_id=rt.bk_tenant_id).update(
        **defaults
    )


def refresh_routes(rt):
    client = SpaceTableIDRedis()
    args = {"bk_tenant_id": rt.bk_tenant_id, "table_id_list": [rt.table_id], "is_publish": True}
    client.push_table_id_detail(**args)
    client.push_data_label_table_ids(**args)
    if rt.bk_biz_id:
        space = Space.objects.get_space_info_by_biz_id(rt.bk_biz_id)
        client.push_space_table_ids(
            space["space_type"], space["space_id"], is_publish=True, bk_tenant_id=rt.bk_tenant_id
        )


def find_cutover(cur, job, storage, pipeline):
    # tasks() 返回 FE 本地时间字符串，解析时使用对应集群时区。
    link, rt = pipeline.data_link, pipeline.result_table
    with ExitStack() as resources:
        old_job = None
        old_cursor = cur
        cur.execute("SET time_zone = @@system_time_zone")
        if storage.bkbase_table_id:
            old_binding = output_binding(link, storage.bkbase_table_id)
            old_job = link.doris_jobs.get(name=old_binding.bkbase_result_table_name)
            if old_job.cluster_id != job.cluster_id:
                old_conn = resources.enter_context(closing(doris_job.connect(old_job)))
                old_cursor = resources.enter_context(old_conn.cursor())
                old_cursor.execute("SET time_zone = @@system_time_zone")
            # 在停用期间修改分组后重新启用，也要让旧代先补齐最后一个窗口。
            if old_job.reconcile_status == "ready":
                remote = doris_job.remote_job(old_cursor, old_job.name)
                if remote and int(remote["Id"]) == old_job.remote_id and remote["Status"] == "PAUSED":
                    doris_job.request_action(rt.bk_tenant_id, old_job.pk, "resume")
                    return None
        return successful_cutover(
            cur, job, old_job, pipeline.output.create_time.timestamp(), previous_cursor=old_cursor
        )


def advance(pipeline):
    rt, link = pipeline.result_table, pipeline.data_link
    raw = pipeline.source_id is None
    if pipeline.phase == "plan":
        options = options_for(rt)
        declare(rt, options, delay=False)
        return "apply" if rt.is_enable and options else "stop"
    if pipeline.phase == "stop":
        if raw:
            link.delete_data_link()
        elif not pause_jobs(pipeline, include_current=True):
            return "stop"
        BkBaseResultTable.objects.filter(data_link_name=link.pk).update(status="Terminating")
        return "routes"
    if pipeline.phase == "routes":
        refresh_routes(rt)
        return "retire" if not raw and rt.is_enable and AGGREGATE in options_for(rt) else ""
    if pipeline.phase == "retire":
        return "" if pause_jobs(pipeline, include_current=False) else "retire"

    binding = binding_for(pipeline.output)
    target = physical_ref(binding)
    storage = rt.get_storage("doris")
    storage.storage_cluster_id = pipeline.layout["cluster_id"]
    labels = get_source_option(rt).labels if raw else pipeline.layout["labels"]
    if pipeline.phase == "apply":
        if not raw:
            with (
                closing(doris_job.connect_cluster(rt.bk_tenant_id, storage.storage_cluster_id)) as conn,
                conn.cursor() as cur,
            ):
                create_aggregate_table(cur, target, labels, storage)
        link.apply_data_link(data_source=rt.get_related_datasource(), table_id=rt.table_id)
        return "wait"

    if not component_ready(pipeline.output) or not component_ready(binding):
        return "wait"
    if raw and not component_ready(DataBusConfig.objects.get(data_link_name=link.pk)):
        return "wait"
    cutover = django_timezone.now()
    if not raw:
        job = ensure_running(pipeline, storage, binding)
        if job is None:
            return "wait"
    with closing(doris_job.connect_cluster(rt.bk_tenant_id, storage.storage_cluster_id)) as conn, conn.cursor() as cur:
        if not raw and storage.bkbase_table_id != pipeline.output.bkbase_table_id:
            boundary = find_cutover(cur, job, storage, pipeline)
            if boundary is None:
                return "wait"
            cutover = datetime.fromtimestamp(boundary, tz=timezone.utc)
        sync_retention(cur, target, storage.expire_days)
    publish_storage(pipeline, storage, binding, cutover, labels)
    if raw:
        # 明细维度变化后，各汇总独立重读来源声明。已经停用的目标由其自身的状态决定。
        rt.metric_aggregates.update(phase="plan")
    return "routes"


def reconcile_pipeline(rt_pk):
    # 与 ResultTable.modify 使用相同的 RT 行和锁顺序。跨步骤提交，使路由发布失败可重试。
    while True:
        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            rt = ResultTable.objects.select_for_update().get(pk=rt_pk)
            pipeline = MetricDorisPipeline.objects.select_related("data_link", "output").filter(result_table=rt).first()
            if not pipeline or not pipeline.phase:
                return
            previous = pipeline.phase
            try:
                with transaction.atomic(using=DATABASE_CONNECTION_NAME):
                    following = advance(pipeline)
            except Exception as exc:
                pipeline.status_reason = str(exc)
                pipeline.save(update_fields=["status_reason"])
                logger.exception(
                    "指标 Doris 链路处理失败 tenant=%s table=%s phase=%s", rt.bk_tenant_id, rt.table_id, previous
                )
                return
            pipeline.phase, pipeline.status_reason = following, ""
            pipeline.save(update_fields=["phase", "status_reason"])
        if not following or following == previous:
            return


def reconcile_pending_pipelines():
    # 慢 Binding / 故障 FE 的网络等待留给独立 RT 任务，避免阻塞其他 Job 的分钟扫描。
    from metadata.task.datalink import reconcile_metric_doris_rt

    for rt_pk in MetricDorisPipeline.objects.exclude(phase="").values_list("pk", flat=True).iterator():
        try:
            reconcile_metric_doris_rt.delay(rt_pk)
        except Exception:
            logger.exception("投递指标 Doris RT %s 失败", rt_pk)
