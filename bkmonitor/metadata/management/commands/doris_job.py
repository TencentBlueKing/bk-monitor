"""管理与 DataLink 关联的 Doris 定时任务。"""

import json
from contextlib import closing
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from metadata.config import DATABASE_CONNECTION_NAME
from metadata.models.data_link import DorisJobConfig
from metadata.service.doris_job import connect, remote_job, request_action
from metadata.service.doris_job_config import adopt_job, render_configs, replace_relations, save_configs


class Command(BaseCommand):
    help = "管理 DorisJob 草稿和异步变更。使用 doris_job <action> --help 查看参数。"

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)
        actions = parser.add_subparsers(dest="action", required=True)
        for action in ("preview", "save", "relations"):
            cmd = actions.add_parser(action)
            cmd.add_argument("--config", required=True, type=Path, help="JSON 配置文件")
            if action == "save":
                cmd.add_argument("--link", required=True)
                cmd.add_argument("--id", type=int, help="待更新的草稿 ID")
            if action == "relations":
                cmd.add_argument("--id", required=True, type=int)
        listing = actions.add_parser("list")
        listing.add_argument("--link")
        listing.add_argument("--result-table", type=int)
        listing.add_argument("--doris-binding", type=int)
        listing.add_argument("--direction", choices=("source", "target"))
        for action in (
            "show",
            "status",
            "tasks",
            "create",
            "pause",
            "resume",
            "drop",
            "retry",
            "cancel",
            "detach",
            "adopt",
        ):
            cmd = actions.add_parser(action)
            cmd.add_argument("--id", required=True, type=int)
            if action == "tasks":
                cmd.add_argument("--page", type=int, default=1)
                cmd.add_argument("--page-size", type=int, default=20)
            if action == "adopt":
                cmd.add_argument("--remote-id", required=True, type=int)

    def handle(self, *args, **options):
        action = options["action"]
        tenant = options["tenant"]
        jobs = DorisJobConfig.objects.filter(data_link__bk_tenant_id=tenant)
        job_id = options.get("id")
        if action in ("preview", "save", "relations"):
            config = json.loads(options["config"].read_text())
        if action == "preview":
            result = render_configs(config)
        elif action == "save":
            result = save_configs(tenant, options["link"], config, job_id)
        elif action == "list":
            if options["link"]:
                jobs = jobs.filter(data_link_id=options["link"])
            filters = {
                f"table_relations__{key}": options[key]
                for key in ("result_table", "doris_binding", "direction")
                if options[key] is not None
            }
            result = list(jobs.filter(**filters).distinct().values("id", "name", "data_link_id", "reconcile_status"))
        elif action == "show":
            result = jobs.values().get(pk=job_id)
            result["relations"] = list(
                jobs.get(pk=job_id).table_relations.values(
                    "direction", "result_table_id", "doris_binding_id", "database", "table"
                )
            )
        elif action in ("status", "tasks"):
            job = jobs.get(pk=job_id)
            if not job.remote_id:
                raise CommandError("该配置尚未绑定远端 Job")
            if action == "status":
                with closing(connect(job)) as connection, connection.cursor() as cursor:
                    result = remote_job(cursor, job.name)
                if result is None or int(result["Id"]) != job.remote_id:
                    raise CommandError("远端绑定的 Job 不存在")
            else:
                from kernel_api.rpc.functions.admin.doris_jobs import query_jobs

                result = query_jobs(
                    {
                        "bk_tenant_id": tenant,
                        "cluster_id": job.cluster_id,
                        "job_type": "insert",
                        "job_id": job.remote_id,
                        "job_name": job.name,
                        "page": options["page"],
                        "page_size": options["page_size"],
                    },
                    tasks=True,
                )["data"]
        elif action in ("detach", "relations"):
            with transaction.atomic(using=DATABASE_CONNECTION_NAME):
                job = jobs.select_for_update().get(pk=job_id)
                if job.reconcile_status == "pending":
                    raise CommandError("请等待或撤销当前动作")
                if action == "detach":
                    job.delete()
                else:
                    replace_relations(job, config["sources"], config["targets"])
            result = {"id": job_id}
        elif action == "adopt":
            adopt_job(tenant, job_id, options["remote_id"])
            result = {"id": job_id, "status": "ready"}
        else:
            job = request_action(tenant, job_id, action)
            result = {"id": job.pk, "status": job.reconcile_status, "action": job.pending_action}
        return json.dumps(result, ensure_ascii=False, default=str, indent=2)
