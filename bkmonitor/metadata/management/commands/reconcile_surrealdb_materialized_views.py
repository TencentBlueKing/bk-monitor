"""Force-reconcile SurrealDB materialized-view definitions."""

from collections.abc import Mapping
from typing import cast

from django.core.management import BaseCommand, CommandError

from core.drf_resource import api
from metadata.models.data_link.constants import DataLinkKind, DataLinkResourceStatus
from metadata.models.data_link.data_link_configs import SurrealDBBindingConfig
from metadata.service.surrealdb_materialized_view import SurrealDBRemoteConfig
from metadata.task.bkbase import reconcile_surrealdb_materialized_view


class Command(BaseCommand):
    help = "强制重新下发 SurrealDB 物化视图的 Event、Index 和 serving table"

    def add_arguments(self, parser):
        parser.add_argument("--bk_tenant_id", type=str, required=True, help="租户ID")
        parser.add_argument("--namespace", type=str, required=True, help="BKBase namespace")
        parser.add_argument("--binding_name", type=str, help="只重建指定的 SurrealDBBinding")

    def handle(self, *args, **options):
        bk_tenant_id = options["bk_tenant_id"]
        namespace = options["namespace"]
        binding_name = options.get("binding_name")

        raw_remote_configs: object = api.bkdata.list_data_link(
            bk_tenant_id=bk_tenant_id,
            namespace=namespace,
            kind=DataLinkKind.get_choice_value(DataLinkKind.SURREALDBBINDING.value),
        )
        if not isinstance(raw_remote_configs, list):
            raise CommandError("BKBase 返回的 SurrealDBBinding 列表格式无效")

        remote_configs_by_name: dict[str, SurrealDBRemoteConfig] = {}
        for raw_config in raw_remote_configs:
            if not isinstance(raw_config, Mapping):
                continue
            metadata = raw_config.get("metadata")
            if not isinstance(metadata, Mapping):
                continue
            name = metadata.get("name")
            if isinstance(name, str) and name:
                remote_configs_by_name[name] = cast(SurrealDBRemoteConfig, raw_config)
        bindings = SurrealDBBindingConfig.objects.filter(bk_tenant_id=bk_tenant_id, namespace=namespace)
        if binding_name:
            bindings = bindings.filter(name=binding_name)

        binding_count = bindings.count()
        if not binding_count:
            raise CommandError("未找到匹配的 SurrealDBBinding")

        failed = 0
        for binding in bindings.order_by("pk"):
            remote_config = remote_configs_by_name.get(binding.name)
            if remote_config is None:
                failed += 1
                self.stderr.write(self.style.ERROR(f"{binding.name}: BKBase 中不存在对应的远端配置"))
                continue

            reconcile_surrealdb_materialized_view.run(binding.pk, remote_config, force=True)
            binding.refresh_from_db()
            if binding.materialized_view_status != DataLinkResourceStatus.OK.value:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"{binding.name}: 重建失败: {binding.materialized_view_last_error or 'unknown error'}"
                    )
                )
                continue
            self.stdout.write(self.style.SUCCESS(f"{binding.name}: 已强制重新下发物化视图定义"))

        if failed:
            raise CommandError(f"{failed}/{binding_count} 个 SurrealDBBinding 重建失败")
