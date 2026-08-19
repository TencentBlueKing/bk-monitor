# Generated manually for custom-format DataSource/DataLink support.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0275_bcsfederalclusterinfo_tenant_scope"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChannelBindingConfig",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("namespace", models.CharField(default="bkmonitor", max_length=64, verbose_name="命名空间")),
                ("create_time", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("last_modify_time", models.DateTimeField(auto_now=True, verbose_name="最后更新时间")),
                ("status", models.CharField(max_length=64, verbose_name="状态")),
                ("data_link_name", models.CharField(blank=True, max_length=64, verbose_name="数据链路名称")),
                ("bk_biz_id", models.BigIntegerField(verbose_name="业务ID")),
                (
                    "bk_tenant_id",
                    models.CharField(default="system", max_length=256, null=True, verbose_name="租户ID"),
                ),
                ("name", models.CharField(db_index=True, max_length=64, verbose_name="通道绑定名称")),
                ("bkbase_result_table_name", models.CharField(max_length=255, verbose_name="BKBase结果表名称")),
                ("channel_name", models.CharField(max_length=255, verbose_name="Inner KafkaChannel名称")),
            ],
            options={
                "verbose_name": "结果表通道绑定配置",
                "verbose_name_plural": "结果表通道绑定配置",
                "unique_together": {("bk_tenant_id", "namespace", "name")},
            },
        ),
        migrations.AddField(
            model_name="databusconfig",
            name="source_kind",
            field=models.CharField(default="DataId", max_length=64, verbose_name="源资源类型"),
        ),
        migrations.AddField(
            model_name="databusconfig",
            name="source_name",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="源资源名称"),
        ),
        migrations.AddField(
            model_name="databusconfig",
            name="role",
            field=models.CharField(blank=True, default="main", max_length=32, verbose_name="Databus角色"),
        ),
        migrations.AlterField(
            model_name="bkbaseresulttable",
            name="bkbase_data_name",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=128,
                null=True,
                verbose_name="计算平台数据源名称",
            ),
        ),
        migrations.AlterField(
            model_name="datalink",
            name="data_link_strategy",
            field=models.CharField(
                choices=[
                    ("bk_standard_v2_event", "标准自定义事件链路"),
                    ("bk_standard_v2_time_series", "标准单指标单表时序数据链路"),
                    ("bk_exporter_time_series", "采集插件时序数据链路"),
                    ("bk_standard_time_series", "STANDARD采集插件时序数据链路"),
                    ("bcs_federal_proxy_time_series", "联邦代理时序数据链路"),
                    ("bcs_federal_subset_time_series", "联邦子集时序数据链路"),
                    ("basereport_time_series_v1", "主机基础采集时序数据链路"),
                    ("graph_relation_time_series", "图关系时序数据链路"),
                    ("base_event_v1", "基础事件链路"),
                    ("system_proc_perf", "系统进程性能链路"),
                    ("system_proc_port", "系统进程端口链路"),
                    ("bk_log", "日志链路"),
                    ("custom_format_vm", "自定义格式 VM 链路"),
                    ("custom_format_es", "自定义格式 Elasticsearch 链路"),
                    ("custom_format_doris", "自定义格式 Doris 链路"),
                ],
                max_length=255,
                verbose_name="链路策略",
            ),
        ),
        migrations.AlterField(
            model_name="resulttableoption",
            name="name",
            field=models.CharField(
                choices=[
                    ("cmdb_level_config", "cmdb_level_config"),
                    ("es_unique_field_list", "es_unique_field_list"),
                    ("group_info_alias", "group_info_alias"),
                    ("dimension_values", "dimension_values"),
                    ("segmented_query_enable", "分段查询开关"),
                    ("is_split_measurement", "是否为单指标单表"),
                    ("enable_field_black_list", "是否开启指标黑名单"),
                    ("is_virtual_table", "是否为虚拟结果表"),
                    ("enable_data_link_component_reuse", "是否开启DataLink组件复用"),
                    ("graph_relation_v4_data_link", "Graph Relation V4 数据链路配置"),
                    ("enable_custom_format_v4_data_link", "是否开启自定义格式 V4 数据链路"),
                    ("custom_format_v4_data_link", "自定义格式 V4 数据链路配置"),
                    ("binding_bcs_cluster_id", "绑定BCS集群ID"),
                ],
                max_length=128,
                verbose_name="option名称",
            ),
        ),
    ]
