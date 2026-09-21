from unittest.mock import Mock

from bk_monitor_base.domains.metric_plugin.define import (
    JOB_PLUGIN_BUILT_IN_DIMENSIONS,
    MetricPlugin,
    MetricPluginMetricField,
    MetricPluginMetricGroup,
    MetricPluginParams,
    MetricPluginStatus,
    VersionTuple,
)
from bk_monitor_base.domains.metric_plugin.manager.job.datalink import CustomSQLPluginDataLinker


def _create_sql_plugin() -> MetricPlugin:
    return MetricPlugin(
        bk_tenant_id="test_tenant",
        bk_biz_id=2,
        id="sql_plugin",
        type="job_mysql",
        name="SQL插件",
        description_md="SQL插件",
        version=VersionTuple(1, 0),
        status=MetricPluginStatus.DEBUG,
        created_by="admin",
        updated_by="admin",
        define={"sql_content": []},
        params=[
            MetricPluginParams(
                name="host_dimensions",
                type="host",
                mode="dms_insert",
                default={
                    "cw_object_model_id": "cw_object_model_id",
                    "cw_object_model_inst_id": "cw_object_model_inst_id",
                },
            ),
            MetricPluginParams(
                name="empty_dimensions",
                type="host",
                mode="dms_insert",
            ),
        ],
        metrics=[
            MetricPluginMetricGroup(
                table_name="sql1",
                fields=[
                    MetricPluginMetricField(
                        name="custom_dim",
                        type="string",
                        monitor_type="dimension",
                        unit="none",
                        description="自定义维度",
                        is_active=True,
                    ),
                    MetricPluginMetricField(
                        name="metric1_alias",
                        type="double",
                        monitor_type="metric",
                        unit="none",
                        description="metric1_alias",
                        is_active=True,
                    ),
                ],
            )
        ],
    )


def test_get_time_series_metrics_injects_job_labels_and_dms_default_keys():
    plugin = _create_sql_plugin()
    linker = CustomSQLPluginDataLinker(plugin, plugin_model=Mock())

    metric_info_list = linker._get_time_series_metrics()

    assert len(metric_info_list) == 1
    tag_fields = {tag["field_name"] for tag in metric_info_list[0]["tag_list"]}
    built_in_dimension_fields = {dimension.field_name for dimension in JOB_PLUGIN_BUILT_IN_DIMENSIONS}

    assert "custom_dim" in tag_fields
    assert built_in_dimension_fields <= tag_fields
    assert "cw_object_model_id" in tag_fields
    assert "cw_object_model_inst_id" in tag_fields
    assert "empty_dimensions" in tag_fields
    assert "bk_host_id" not in tag_fields
    assert "bk_agent_id" not in tag_fields


def test_auto_discovery_excluded_dimension_names_include_job_labels_and_dms_fields():
    plugin = _create_sql_plugin()
    linker = CustomSQLPluginDataLinker(plugin, plugin_model=Mock())

    excluded_fields = linker._get_auto_discovery_excluded_dimension_names()
    built_in_dimension_fields = {dimension.field_name for dimension in JOB_PLUGIN_BUILT_IN_DIMENSIONS}

    assert built_in_dimension_fields <= excluded_fields
    assert "cw_object_model_id" in excluded_fields
    assert "cw_object_model_inst_id" in excluded_fields
    assert "empty_dimensions" in excluded_fields
    assert "custom_dim" not in excluded_fields


def test_get_time_series_metrics_deduplicates_builtin_and_ignores_inactive_dimensions():
    plugin = _create_sql_plugin()
    plugin.metrics[0].fields.insert(
        0,
        MetricPluginMetricField(
            name="bk_target_ip",
            type="string",
            monitor_type="dimension",
            unit="none",
            description="用户已声明的目标IP",
            is_active=True,
        ),
    )
    plugin.metrics[0].fields.insert(
        1,
        MetricPluginMetricField(
            name="inactive_dim",
            type="string",
            monitor_type="dimension",
            unit="none",
            description="禁用维度",
            is_active=False,
        ),
    )
    linker = CustomSQLPluginDataLinker(plugin, plugin_model=Mock())

    metric_info_list = linker._get_time_series_metrics()
    tag_fields = [tag["field_name"] for tag in metric_info_list[0]["tag_list"]]
    tag_map = {tag["field_name"]: tag for tag in metric_info_list[0]["tag_list"]}

    assert tag_fields.count("bk_target_ip") == 1
    assert tag_map["bk_target_ip"]["description"] == "用户已声明的目标IP"
    assert "inactive_dim" not in tag_fields
