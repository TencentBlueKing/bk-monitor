from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0275_bcsfederalclusterinfo_tenant_scope"),
    ]

    operations = [
        migrations.AddField(
            model_name="surrealdbbindingconfig",
            name="materialized_view_definition_hash",
            field=models.CharField(default="", max_length=64, verbose_name="物化视图定义哈希"),
        ),
        migrations.AddField(
            model_name="surrealdbbindingconfig",
            name="materialized_view_last_apply_time",
            field=models.DateTimeField(blank=True, null=True, verbose_name="物化视图最近下发时间"),
        ),
        migrations.AddField(
            model_name="surrealdbbindingconfig",
            name="materialized_view_last_error",
            field=models.TextField(blank=True, default="", verbose_name="物化视图最近错误"),
        ),
        migrations.AddField(
            model_name="surrealdbbindingconfig",
            name="materialized_view_status",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="物化视图状态"),
        ),
        migrations.AddField(
            model_name="surrealdbbindingconfig",
            name="materialized_view_relation_names",
            field=models.JSONField(default=list, verbose_name="物化视图关系名称"),
        ),
    ]
