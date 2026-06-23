from django.core.management import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.api import OverseasMigrateApi
from apps.log_clustering.handlers.dataflow.constants import ActionEnum
from apps.log_clustering.handlers.dataflow.dataflow_handler import DataFlowHandler
from apps.log_clustering.models import ClusteringConfig
from apps.utils.local import activate_request
from apps.utils.thread import generate_request


def parse_str_int_list(value):
    """解析逗号分隔的整数列表。"""
    if not value:
        return []
    try:
        return [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as error:
        raise CommandError(f"解析失败: {value!r}, 请输入逗号分隔的数字") from error


class Command(BaseCommand):
    """日志聚类 Flow 和模型配置迁移指令。"""

    help = "迁移日志聚类 Flow ID，并在预测 Flow 迁移时更新模型配置、创建在线 CI、重启 Flow"

    flow_id_fields = (
        "pre_treat_flow_id",
        "after_treat_flow_id",
        "predict_flow_id",
        "log_count_aggregation_flow_id",
    )

    def add_arguments(self, parser):
        scope_group = parser.add_mutually_exclusive_group(required=True)
        scope_group.add_argument(
            "-b",
            "--bk_biz_id",
            type=str,
            help="迁移指定业务下的聚类配置，支持逗号分隔多个，如 1,2,3",
        )
        scope_group.add_argument(
            "--flow_id",
            "--flow_ids",
            dest="flow_ids",
            type=str,
            help="迁移指定 Flow ID，支持逗号分隔多个，如 1000,1001",
        )
        scope_group.add_argument("--all", action="store_true", help="迁移全部聚类配置")
        parser.add_argument(
            "--skip-create-ci",
            action="store_true",
            help="预测 Flow 迁移时跳过在线 CI 创建，仅更新模型实例配置并重启 Flow",
        )
        parser.add_argument(
            "--dry-run",
            dest="dry_run",
            action="store_true",
            default=False,
            help="仅打印待迁移的 Flow ID 映射，不修改数据或迁移模型配置",
        )

    def handle(self, *args, **options):
        bk_biz_ids = parse_str_int_list(options["bk_biz_id"])
        flow_ids = parse_str_int_list(options["flow_ids"])
        dry_run = options["dry_run"]

        if options["bk_biz_id"] is not None and not bk_biz_ids:
            raise CommandError("参数 -b/--bk_biz_id 不能为空")
        if options["flow_ids"] is not None and not flow_ids:
            raise CommandError("参数 --flow_id 不能为空/0")

        activate_request(generate_request("admin"))
        result = OverseasMigrateApi.get_migration_mapping_info()
        mapping = result.get("flow_mapping_info", {}) if isinstance(result, dict) else {}
        if not isinstance(mapping, dict) or not mapping:
            raise CommandError("flow_mapping_info 为空或格式错误，终止处理")

        configs = ClusteringConfig.objects.all().order_by("id")
        if bk_biz_ids:
            configs = configs.filter(bk_biz_id__in=bk_biz_ids)
        elif flow_ids:
            configs = configs.filter(
                Q(after_treat_flow_id__in=flow_ids)
                | Q(pre_treat_flow_id__in=flow_ids)
                | Q(predict_flow_id__in=flow_ids)
                | Q(log_count_aggregation_flow_id__in=flow_ids)
            )

        configs = list(configs)
        if not configs:
            self.stdout.write(self.style.WARNING("指定范围内未找到日志聚类配置"))
            return

        flow_handler = DataFlowHandler()
        for config in configs:
            flow_handler._use_biz_config(config.bk_biz_id)
            flow_id_updates = {}
            for field in self.flow_id_fields:
                old_flow_id = getattr(config, field)
                if old_flow_id is None or (flow_ids and old_flow_id not in flow_ids):
                    continue
                if str(old_flow_id) not in mapping:
                    continue

                try:
                    new_flow_id = int(mapping[str(old_flow_id)])
                except (TypeError, ValueError):
                    self.stdout.write(
                        self.style.WARNING(
                            f"index_set_id={config.index_set_id}: {field} {old_flow_id} 新 Flow ID 无效，跳过"
                        )
                    )
                    continue

                if new_flow_id == old_flow_id:
                    continue

                flow_id_updates[field] = (old_flow_id, new_flow_id)
                self.stdout.write(f"index_set_id={config.index_set_id}: {field} {old_flow_id} -> {new_flow_id}")

            if not flow_id_updates:
                continue
            if dry_run:
                continue

            try:
                for field, (_, new_flow_id) in flow_id_updates.items():
                    setattr(config, field, new_flow_id)

                # 只有预测 Flow 发生迁移时，才需要迁移模型配置和创建在线 CI。
                if "predict_flow_id" in flow_id_updates:
                    self.migrate_model_config(config, options["skip_create_ci"], flow_handler)

                # 外部资源迁移成功后，先保存 Flow ID 映射；重启失败时可按新映射手动补偿。
                update_fields = list(flow_id_updates)
                with transaction.atomic():
                    config.save(update_fields=update_fields)

                # 只重启本次映射发生变化的新 Flow，不经过异步任务的缓存判断。
                changed_flow_ids = list(dict.fromkeys(new_flow_id for _, new_flow_id in flow_id_updates.values()))
                online_flow_ids = {config.predict_flow_id, config.log_count_aggregation_flow_id}
                for changed_flow_id in changed_flow_ids:
                    kwargs = {"bk_biz_id": config.bk_biz_id} if changed_flow_id in online_flow_ids else {}
                    flow_handler.operator_flow(
                        flow_id=changed_flow_id,
                        action=ActionEnum.RESTART,
                        **kwargs,
                    )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"迁移成功: index_set_id={config.index_set_id}, 重启 flow_ids={changed_flow_ids}"
                    )
                )
            except Exception as error:
                self.stderr.write(
                    self.style.ERROR(
                        f"迁移失败: index_set_id={config.index_set_id}, 请检查 Flow ID 映射保存状态并按需补偿重启, 错误: {error}"
                    )
                )

        if dry_run:
            self.stdout.write(self.style.SUCCESS("dry-run 完成，未修改任何数据"))
            return

        self.stdout.write(self.style.SUCCESS("迁移执行完成"))

    def migrate_model_config(self, config, skip_create_ci, handler):
        if not config.predict_flow_id:
            return None

        result_table_id = config.predict_flow["clustering_predict"]["result_table_id"]
        model_config = handler.get_serving_data_processing_id_config(
            result_table_id=result_table_id,
            bk_biz_id=config.bk_biz_id,
        )
        model_instance_id = model_config["id"]
        handler.update_model_instance(
            model_instance_id=model_instance_id,
            bk_biz_id=config.bk_biz_id,
        )

        if skip_create_ci:
            return None

        online_task = handler.create_online_task(index_set_id=config.index_set_id)
        ci_id = online_task["ci_id"]
        config.online_task_id = ci_id
        config.save(update_fields=["online_task_id"])
        self.stdout.write(f"online_task 创建成功并已保存: index_set_id={config.index_set_id}, ci_id={ci_id}")
        return ci_id
