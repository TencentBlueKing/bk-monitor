# Rebuilt on the latest metadata migration graph.

import bkmonitor.utils.db.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0273_pingserversubscriptionconfig_bk_biz_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeatureFlag",
            fields=[
                ("flag_id", models.AutoField(primary_key=True, serialize=False, verbose_name="特性开关ID")),
                (
                    "flag_name",
                    models.CharField(db_index=True, max_length=128, unique=True, verbose_name="特性开关名称"),
                ),
                ("description", models.CharField(blank=True, default="", max_length=512, verbose_name="描述")),
                ("config", bkmonitor.utils.db.fields.JsonField(default=dict, verbose_name="配置信息")),
                ("is_enabled", models.BooleanField(db_index=True, default=True, verbose_name="是否启用")),
                ("creator", models.CharField(default="system", max_length=32, verbose_name="创建者")),
                ("updater", models.CharField(default="system", max_length=32, verbose_name="变更人")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={
                "verbose_name": "特性开关",
                "verbose_name_plural": "特性开关",
                "db_table": "metadata_featureflag",
                "ordering": ["-updated_at"],
            },
        ),
    ]
