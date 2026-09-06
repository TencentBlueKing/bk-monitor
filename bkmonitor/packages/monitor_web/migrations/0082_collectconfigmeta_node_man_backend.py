from django.db import migrations, models


def preserve_existing_v3_collections(apps, schema_editor):
    collect_config_model = apps.get_model("monitor_web", "CollectConfigMeta")
    binding_model = apps.get_model("monitor_web", "NodeManIntegrationBinding")
    database_alias = schema_editor.connection.alias
    resource_keys = (
        binding_model.objects.using(database_alias)
        .filter(resource_type="COLLECT_CONFIG")
        .values_list("resource_key", flat=True)
    )
    v3_config_ids = []
    for resource_key in resource_keys.iterator(chunk_size=1000):
        try:
            v3_config_ids.append(int(resource_key))
        except (TypeError, ValueError):
            continue
        if len(v3_config_ids) == 1000:
            collect_config_model.objects.using(database_alias).filter(pk__in=v3_config_ids).update(
                node_man_backend="v3"
            )
            v3_config_ids.clear()
    if v3_config_ids:
        collect_config_model.objects.using(database_alias).filter(pk__in=v3_config_ids).update(node_man_backend="v3")


class Migration(migrations.Migration):
    dependencies = [("monitor_web", "0081_nodeman_collection_policy")]

    operations = [
        migrations.AddField(
            model_name="collectconfigmeta",
            name="node_man_backend",
            field=models.CharField(
                choices=[("v2", "NodeMan V2"), ("v3", "NodeMan V3")],
                default="v2",
                max_length=8,
                verbose_name="NodeMan 执行后端",
            ),
        ),
        migrations.RunPython(preserve_existing_v3_collections, migrations.RunPython.noop),
    ]
