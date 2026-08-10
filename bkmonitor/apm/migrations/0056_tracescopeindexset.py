from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("apm", "0055_add_datasource_backup_link_info"),
    ]

    operations = [
        migrations.CreateModel(
            name="TraceScopeIndexSet",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_enabled", models.BooleanField(default=True, verbose_name="是否启用")),
                ("is_deleted", models.BooleanField(default=False, verbose_name="是否删除")),
                ("create_user", models.CharField(blank=True, default="", max_length=32, verbose_name="创建人")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("update_user", models.CharField(blank=True, default="", max_length=32, verbose_name="最后修改人")),
                ("update_time", models.DateTimeField(auto_now=True, verbose_name="最后修改时间")),
                ("bk_biz_id", models.IntegerField(verbose_name="业务 ID")),
                ("index_set_id", models.IntegerField(db_index=True, verbose_name="索引集 ID")),
                ("bk_tenant_id", models.CharField(default="system", max_length=64, verbose_name="租户 ID")),
            ],
            options={
                "unique_together": {("bk_tenant_id", "bk_biz_id")},
            },
        ),
    ]
