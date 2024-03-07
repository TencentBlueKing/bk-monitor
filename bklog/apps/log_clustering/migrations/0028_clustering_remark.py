import hashlib
import json

from django.db import migrations, models
from django.db.models import Q


def convert_groups_to_groups_hash(groups: dict) -> str:
    """
    对 groups 字段进行 hash
    """
    sorted_groups = sorted(groups.items(), key=lambda x: x[0])
    return hashlib.md5(json.dumps(sorted_groups).encode("utf-8")).hexdigest()


def insert_data_to_clusteringremark(apps, schema_editor):
    AiopsSignatureAndPattern = apps.get_model('log_clustering', 'AiopsSignatureAndPattern')
    ClusteringRemark = apps.get_model('log_clustering', 'ClusteringRemark')
    ClusteringConfig = apps.get_model('log_clustering', 'ClusteringConfig')

    groups = {}
    group_hash = convert_groups_to_groups_hash(groups)

    clustering_remarks = {}
    # 所有的signature_and_pattern都需要插入到clustering_remark中
    for pattern in AiopsSignatureAndPattern.objects.exclude(remark=[], owners=[]).all():
        clustering_config = ClusteringConfig.objects.filter(
            Q(model_id=pattern.model_id) | Q(model_output_rt=pattern.model_id)
        ).first()
        if not clustering_config:
            continue

        if pattern.signature not in clustering_remarks:
            clustering_remarks[pattern.signature] = ClusteringRemark(
                bk_biz_id=clustering_config.bk_biz_id,
                signature=pattern.signature,
                origin_pattern="",
                groups=groups,
                group_hash=group_hash,
                remark=pattern.remark,
                owners=pattern.owners,
            )
        else:
            # 如果有多个签名相同的记录，合并之
            clustering_remarks[pattern.signature].owners += list(
                set(clustering_remarks[pattern.signature].owners + pattern.owners)
            )
            clustering_remarks[pattern.signature].remark += pattern.remark

    ClusteringRemark.objects.bulk_create(list(clustering_remarks.values()))


class Migration(migrations.Migration):
    dependencies = [
        ('log_clustering', '0027_auto_20240306_1125'),
    ]

    operations = [
        migrations.RunPython(insert_data_to_clusteringremark),
    ]
