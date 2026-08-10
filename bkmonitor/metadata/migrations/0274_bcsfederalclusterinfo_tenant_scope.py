from django.db import migrations, models
from django.db.models import Count


DEFAULT_TENANT_ID = "system"


def backfill_tenant_and_deduplicate(apps, schema_editor):
    BCSClusterInfo = apps.get_model("metadata", "BCSClusterInfo")
    BcsFederalClusterInfo = apps.get_model("metadata", "BcsFederalClusterInfo")

    tenants_by_cluster_id = {}
    for cluster_id, bk_tenant_id in BCSClusterInfo.objects.values_list("cluster_id", "bk_tenant_id"):
        tenants_by_cluster_id.setdefault(cluster_id, set()).add(bk_tenant_id or DEFAULT_TENANT_ID)

    for record in BcsFederalClusterInfo.objects.all().iterator(chunk_size=1000):
        role_tenants = [
            tenants_by_cluster_id.get(record.fed_cluster_id, set()),
            tenants_by_cluster_id.get(record.sub_cluster_id, set()),
            tenants_by_cluster_id.get(record.host_cluster_id, set()),
        ]
        known_role_tenants = [tenants for tenants in role_tenants if tenants]
        common_tenants = set.intersection(*known_role_tenants) if known_role_tenants else set()
        if len(common_tenants) == 1:
            bk_tenant_id = common_tenants.pop()
        else:
            # 历史表没有租户字段，角色间无法唯一交叉确认时优先采用唯一的代理集群租户，
            # 再依次尝试子集群和 HOST；仍有歧义则保守落到 system。
            bk_tenant_id = next(
                (next(iter(tenants)) for tenants in role_tenants if len(tenants) == 1),
                DEFAULT_TENANT_ID,
            )
        if record.bk_tenant_id != bk_tenant_id:
            BcsFederalClusterInfo.objects.filter(pk=record.pk).update(bk_tenant_id=bk_tenant_id)

    duplicate_groups = (
        BcsFederalClusterInfo.objects.values("bk_tenant_id", "fed_cluster_id", "sub_cluster_id")
        .annotate(record_count=Count("id"))
        .filter(record_count__gt=1)
    )
    for group in duplicate_groups.iterator(chunk_size=1000):
        records = BcsFederalClusterInfo.objects.filter(
            bk_tenant_id=group["bk_tenant_id"],
            fed_cluster_id=group["fed_cluster_id"],
            sub_cluster_id=group["sub_cluster_id"],
        ).order_by("is_deleted", "-updated_at", "-id")
        canonical = records.first()
        if canonical is not None:
            records.exclude(pk=canonical.pk).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0273_pingserversubscriptionconfig_bk_biz_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="bcsfederalclusterinfo",
            name="bk_tenant_id",
            field=models.CharField(default=DEFAULT_TENANT_ID, max_length=256, verbose_name="租户ID"),
        ),
        migrations.RunPython(backfill_tenant_and_deduplicate, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="bcsfederalclusterinfo",
            constraint=models.UniqueConstraint(
                fields=("bk_tenant_id", "fed_cluster_id", "sub_cluster_id"),
                name="uniq_bcs_fed_tenant_cluster_sub",
            ),
        ),
        migrations.AddIndex(
            model_name="bcsfederalclusterinfo",
            index=models.Index(
                fields=["bk_tenant_id", "fed_cluster_id", "is_deleted"],
                name="idx_bcs_fed_tenant_fed_active",
            ),
        ),
        migrations.AddIndex(
            model_name="bcsfederalclusterinfo",
            index=models.Index(
                fields=["bk_tenant_id", "sub_cluster_id", "is_deleted"],
                name="idx_bcs_fed_tenant_sub_active",
            ),
        ),
    ]
