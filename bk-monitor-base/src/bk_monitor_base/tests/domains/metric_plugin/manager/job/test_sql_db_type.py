import pytest

from bk_monitor_base.domains.metric_plugin.manager.job.db2 import DB2PluginManager
from bk_monitor_base.domains.metric_plugin.manager.job.mssql import MSSQLPluginManager
from bk_monitor_base.domains.metric_plugin.manager.job.mysql import MysqlPluginManager
from bk_monitor_base.domains.metric_plugin.manager.job.oracle import OraclePluginManager
from bk_monitor_base.metric_plugin import MetricPlugin, MetricPluginStatus, VersionTuple


def make_metric_plugin(plugin_type: str) -> MetricPlugin:
    return MetricPlugin(
        bk_tenant_id="test_tenant",
        bk_biz_id=1,
        id=f"test_{plugin_type}",
        type=plugin_type,
        name=f"Test {plugin_type}",
        description_md="test plugin",
        version=VersionTuple(1, 0),
        status=MetricPluginStatus.DEBUG,
        created_by="admin",
        updated_by="admin",
        define={
            "linux": {},
            "sql_content": [
                {
                    "classification_id": "sql1",
                    "classification_name": "SQL-1",
                    "content": "SELECT 1;",
                }
            ],
        },
        params=[],
        metrics=[],
    )


@pytest.mark.parametrize(
    ("manager_cls", "expected_db_type"),
    [
        (MysqlPluginManager, "mysql"),
        (OraclePluginManager, "oracle"),
        (MSSQLPluginManager, "mssql"),
        (DB2PluginManager, "db2"),
    ],
)
def test_generate_config_yaml_content_uses_manager_db_type(manager_cls, expected_db_type):
    plugin = make_metric_plugin(plugin_type=manager_cls.type)
    manager = manager_cls(plugin)

    config = manager.generate_config_yaml_content(
        plugin_params={
            "db_type": "wrong_db_type",
            "host": "10.10.28.200",
            "name": "test_db",
            "password": "secret",
            "port": "3306",
            "session": "10",
            "time": "60",
            "user": "root",
        }
    )

    assert config["db_type"] == expected_db_type
