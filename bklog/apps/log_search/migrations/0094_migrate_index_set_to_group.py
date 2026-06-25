from django.db import migrations


def migrate_index_set_to_group(apps, schema_editor):
    LogIndexSet = apps.get_model("log_search", "LogIndexSet")
    LogIndexSetData = apps.get_model("log_search", "LogIndexSetData")
    CollectorConfig = apps.get_model("log_databus", "CollectorConfig")

    # result_table_id -> collector index_set_id
    rt_id_to_index_set_id = dict(
        CollectorConfig.objects.filter(table_id__isnull=False, index_set_id__isnull=False)
        .exclude(table_id="")
        .values_list("table_id", "index_set_id")
    )

    index_sets = LogIndexSet.objects.filter(
        scenario_id="log",
        collector_config_id__isnull=True,
        is_group=False,
    )

    for index_set in index_sets.iterator(chunk_size=500):
        to_create = []
        index_data_qs = LogIndexSetData.objects.filter(index_set_id=index_set.index_set_id, type="result_table")
        for index_data in index_data_qs.iterator(chunk_size=500):
            mapped_index_set_id = rt_id_to_index_set_id.get(index_data.result_table_id)
            if not mapped_index_set_id:
                continue

            to_create.append(
                LogIndexSetData(
                    index_set_id=index_set.index_set_id,
                    result_table_id=str(mapped_index_set_id),
                    scenario_id=index_data.scenario_id,
                    bk_biz_id=index_data.bk_biz_id,
                    type="index_set",
                    apply_status="normal",
                )
            )

        if to_create:
            LogIndexSetData.objects.bulk_create(to_create, batch_size=500)
            index_set.is_group = True
            index_set.save(update_fields=["is_group"])


class Migration(migrations.Migration):
    dependencies = [
        ("log_databus", "0049_collectorconfig_storage_cluster_type"),
        ("log_search", "0093_logindexset_is_platform_index_and_more"),
    ]

    operations = [
        migrations.RunPython(migrate_index_set_to_group, migrations.RunPython.noop),
    ]
