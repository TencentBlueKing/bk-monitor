# Generated manually for GraphDataBusConfig proxy migration state

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0268_graph_relation_child_component_names"),
    ]

    operations = [
        migrations.CreateModel(
            name="GraphDataBusConfig",
            fields=[],
            options={
                "verbose_name": "图关联数据总线配置",
                "verbose_name_plural": "图关联数据总线配置",
                "proxy": True,
                "indexes": [],
            },
            bases=("metadata.databusconfig",),
        ),
    ]
