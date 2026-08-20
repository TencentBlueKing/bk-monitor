import json

from django.core.management.base import BaseCommand, CommandError

from metadata import models
from metadata.service.federation_data_link import FederationReconcilePlan, reconcile_federation_data_links


class Command(BaseCommand):
    help = "按当前 BcsFederalClusterInfo 全量收敛联邦 Proxy/Subset 数据链路"

    def add_arguments(self, parser):
        parser.add_argument("--tenant-id", dest="bk_tenant_id")
        parser.add_argument("--all-tenants", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        bk_tenant_id = options.get("bk_tenant_id")
        all_tenants = options.get("all_tenants")
        if bool(bk_tenant_id) == bool(all_tenants):
            raise CommandError("请且仅请指定 --tenant-id 或 --all-tenants")

        if all_tenants:
            tenant_ids = sorted(set(models.BcsFederalClusterInfo.objects.values_list("bk_tenant_id", flat=True)))
        else:
            tenant_ids = [bk_tenant_id]

        for tenant_id in tenant_ids:
            active_records = models.BcsFederalClusterInfo.objects.filter(
                bk_tenant_id=tenant_id,
                is_deleted=False,
            )
            deleted_records = models.BcsFederalClusterInfo.objects.filter(
                bk_tenant_id=tenant_id,
                is_deleted=True,
            )
            active_proxy_ids = set(active_records.values_list("fed_cluster_id", flat=True))
            active_sub_ids = set(active_records.values_list("sub_cluster_id", flat=True))
            plan = FederationReconcilePlan(
                active_proxy_cluster_ids=sorted(active_proxy_ids),
                active_sub_cluster_ids=sorted(active_sub_ids),
                removed_proxy_cluster_ids=sorted(
                    set(deleted_records.values_list("fed_cluster_id", flat=True)) - active_proxy_ids
                ),
                removed_sub_cluster_ids=sorted(
                    set(deleted_records.values_list("sub_cluster_id", flat=True)) - active_sub_ids
                ),
            ).normalized()
            self.stdout.write(
                json.dumps(
                    {
                        "bk_tenant_id": tenant_id,
                        "active_proxy_cluster_ids": plan.active_proxy_cluster_ids,
                        "active_sub_cluster_ids": plan.active_sub_cluster_ids,
                        "removed_proxy_cluster_ids": plan.removed_proxy_cluster_ids,
                        "removed_sub_cluster_ids": plan.removed_sub_cluster_ids,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            if not options.get("dry_run"):
                reconcile_federation_data_links(bk_tenant_id=tenant_id, plan=plan)
