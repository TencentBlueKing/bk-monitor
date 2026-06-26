# Generated manually for graph relation automatic SurrealDB restore marker

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0268_graph_relation_child_component_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="graphrelationbindingconfig",
            name="surrealdb_auto_restore",
            field=models.BooleanField(default=False, verbose_name="SurrealDB自动恢复写入"),
        ),
    ]
