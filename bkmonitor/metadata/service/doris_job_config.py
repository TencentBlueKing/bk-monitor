"""受信任的 metadata 管理入口使用的 Job 草稿和组件关系。"""

import re
from contextlib import closing

import sqlparse
from django.db import transaction

from metadata.config import DATABASE_CONNECTION_NAME
from metadata.models.data_link import (
    DataLink,
    DorisJobConfig,
    DorisJobTableRelation,
    ResultTableConfig,
    DorisStorageBindingConfig,
)
from metadata.models.storage import ClusterInfo
from metadata.service.doris_job import connect, remote_job


def quote_identifier(value):
    return "`" + value.replace("`", "``") + "`"


def render_configs(config):
    """自由 SQL、分钟汇总或按目标展开的窗口投影，最终均生成受管 INSERT。"""
    if not config.get("template_key"):
        return [config]
    if config["template_key"] == "sum_without":
        from metadata.service.metric_aggregate import render_sum_without

        return [render_sum_without(config)]
    if config["template_key"] != "window_projection":
        raise ValueError("未知 DorisJob 模板")
    params = config["params"]
    minutes = int(params["lookback_minutes"])
    if minutes <= 0 or not params["columns"]:
        raise ValueError("窗口分钟数必须为正数，并指定投影列")
    columns = ", ".join(quote_identifier(column) for column in params["columns"])
    time_column = quote_identifier(params["time_column"])
    outputs = []
    for slot, target in config["targets"].items():
        source_slot = target["source"]
        source = config["sources"][source_slot]
        src = f"{quote_identifier(source['database'])}.{quote_identifier(source['table'])}"
        dst = f"{quote_identifier(target['database'])}.{quote_identifier(target['table'])}"
        outputs.append(
            {
                **config,
                "name": f"{config['name']}_{slot}",
                "sources": {source_slot: source},
                "targets": {slot: target},
                "insert_sql": f"INSERT INTO {dst} ({columns}) SELECT {columns} FROM {src} "
                f"WHERE {time_column} >= DATE_SUB(NOW(), INTERVAL {minutes} MINUTE) AND {time_column} < NOW()",
                "template_inputs": {"sources": {source_slot: source}, "targets": {slot: target}, "params": params},
            }
        )
    if not outputs:
        raise ValueError("模板需要目标表")
    return outputs


def replace_relations(job, sources, targets):
    tenant = job.data_link.bk_tenant_id
    relations = []
    for direction, refs in (("source", sources), ("target", targets)):
        for ref in refs.values():
            fields = {"database": ref.get("database", job.database), "table": ref.get("table", "")}
            fields["component_kind"] = ref.get("kind", "")
            if fields["component_kind"] == "ResultTable":
                fields["result_table"] = ResultTableConfig.objects.get(pk=ref["id"], bk_tenant_id=tenant)
            elif ref.get("kind") == "DorisBinding":
                fields["doris_binding"] = DorisStorageBindingConfig.objects.get(pk=ref["id"], bk_tenant_id=tenant)
            elif fields["component_kind"] or not fields["table"]:
                raise ValueError("需要 ResultTable、DorisBinding 或物理表名")
            relations.append(DorisJobTableRelation(job=job, direction=direction, **fields))
    job.table_relations.all().delete()
    DorisJobTableRelation.objects.bulk_create(relations)


@transaction.atomic(using=DATABASE_CONNECTION_NAME)
def save_configs(tenant, link_name, config, job_id=None):
    link = DataLink.objects.get(pk=link_name, bk_tenant_id=tenant)
    definitions = render_configs(config)
    if job_id is not None and len(definitions) != 1:
        raise ValueError("编辑草稿时请选择单个输出")
    saved = []
    for definition in definitions:
        if job_id is None:
            job = DorisJobConfig(data_link=link)
        else:
            job = DorisJobConfig.objects.select_for_update().get(pk=job_id, data_link=link)
            if job.reconcile_status != "draft":
                raise ValueError("仅草稿可编辑")
        cluster = ClusterInfo.objects.get(
            cluster_id=definition["cluster_id"], bk_tenant_id=tenant, cluster_type=ClusterInfo.TYPE_DORIS
        )
        job.cluster_id = cluster.pk
        job.name = definition["name"]
        job.database = definition["database"]
        job.interval_minutes = int(definition["interval_minutes"])
        job.insert_sql = definition["insert_sql"].strip()
        statements = sqlparse.parse(job.insert_sql)
        if job.interval_minutes < 1 or len(statements) != 1 or statements[0].get_type() != "INSERT":
            raise ValueError("需要正整数周期和单条 INSERT")
        job.template_key = definition.get("template_key", "")
        job.template_inputs = definition.get("template_inputs", {}) if job.template_key else {}
        job.save()
        replace_relations(job, definition.get("sources", {}), definition.get("targets", {}))
        saved.append(job.pk)
    return saved


@transaction.atomic(using=DATABASE_CONNECTION_NAME)
def adopt_job(tenant, job_id, remote_id, *, relations=None):
    """将远端定义与管理员确认的上下游在同一事务中接管。"""
    job = DorisJobConfig.objects.select_for_update().get(pk=job_id, data_link__bk_tenant_id=tenant)
    if job.remote_id is not None or job.reconcile_status not in ("draft", "failed"):
        raise ValueError("请选择未绑定的草稿或失败配置")
    if relations is None and job.table_relations.exists():
        raise ValueError("草稿已有上下游，请通过 --config 提供远端 SQL 对应的 sources 和 targets")
    if relations is not None and not all(isinstance(relations.get(key), dict) for key in ("sources", "targets")):
        raise ValueError("接管配置需要同时指定 sources 和 targets，无关联时使用空对象")
    with closing(connect(job)) as connection, connection.cursor() as cursor:
        remote = remote_job(cursor, job.name)
    if not remote or int(remote["Id"]) != remote_id:
        raise ValueError("远端 Job 名称与指定 ID 不匹配")
    schedule = re.fullmatch(r"EVERY (\d+) MINUTE(?: STARTS [\d: -]+)?", remote["RecurringStrategy"] or "", re.I)
    if remote["ExecuteType"] != "RECURRING" or not schedule:
        raise ValueError("仅支持无截止时间的周期分钟 INSERT")
    if relations is not None:
        replace_relations(job, relations["sources"], relations["targets"])
    job.interval_minutes = int(schedule[1])
    job.insert_sql = remote["ExecuteSql"]
    job.template_key = job.pending_action = job.status_reason = ""
    job.template_inputs = {}
    job.remote_id = remote_id
    job.reconcile_status = "ready"
    job.save()
