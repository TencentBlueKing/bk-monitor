from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("metadata", "0276_custom_format_datalink")]

    operations = [
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
                    ("databus_labels", "Databus 标签注入配置"),
                    ("enable_custom_format_v4_data_link", "是否开启自定义格式 V4 数据链路"),
                    ("custom_format_v4_data_link", "自定义格式 V4 数据链路配置"),
                    ("binding_bcs_cluster_id", "绑定BCS集群ID"),
                ],
                max_length=128,
                verbose_name="option名称",
            ),
        ),
    ]
