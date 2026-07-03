# Generated manually for graph relation rebuilt child component names

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0267_graph_relation_binding_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="graphrelationbindingconfig",
            name="vm_storage_binding_name",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="VM存储绑定名称"),
        ),
        migrations.AddField(
            model_name="graphrelationbindingconfig",
            name="vm_databus_name",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="VM清洗任务名称"),
        ),
        migrations.AddField(
            model_name="graphrelationbindingconfig",
            name="surrealdb_binding_name",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="SurrealDB绑定名称"),
        ),
        migrations.AddField(
            model_name="graphrelationbindingconfig",
            name="graph_databus_name",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="图清洗任务名称"),
        ),
    ]
