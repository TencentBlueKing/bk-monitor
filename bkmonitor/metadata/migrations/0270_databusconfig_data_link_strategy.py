# Generated manually for Databus graph rebuild strategy marker

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0269_graph_databus_proxy"),
    ]

    operations = [
        migrations.AddField(
            model_name="databusconfig",
            name="data_link_strategy",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="数据链路策略标记"),
        ),
    ]
