"""0003 初始化存储后端时，验证历史模型写入数据库的 InfluxDB 凭据。"""

from importlib import import_module

import pytest
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import override_settings


@pytest.mark.parametrize(
    ("primary", "alternate", "legacy", "host_password", "expected"),
    [
        (None, None, "legacy", None, "legacy"),
        ("primary", "alternate", "legacy", None, "primary"),
        ("", "alternate", "legacy", None, ""),
        (None, "alternate", "legacy", None, "alternate"),
        (None, "", "legacy", None, ""),
        (None, None, None, None, ""),
        ("primary", "alternate", "legacy", "", ""),
        ("primary", "alternate", "legacy", "host", "host"),
    ],
)
def test_influxdb_password_written_by_0003(
    monkeypatch: pytest.MonkeyPatch,
    primary: str | None,
    alternate: str | None,
    legacy: str | None,
    host_password: str | None,
    expected: str,
) -> None:
    """只有新变量都未定义时才允许使用旧密码，显式空串写入后仍为空。"""
    for name, value in (
        ("BK_MONITOR_INFLUXDB_PASSWORD", primary),
        ("INFLUXDB_BKMONITORV3_PASS", alternate),
        ("BK_MONITOR_INFLUXDB_PASS", legacy),
    ):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    monkeypatch.setenv("BK_MONITOR_INFLUXDB_IP0", "influx.test")
    monkeypatch.setenv("BK_MONITOR_INFLUXDB_PORT", "8086")

    migration = import_module("bk_monitor_base.metadata.migrations.0003_init_storage_backend_info")
    with override_settings(MIGRATION_MODULES={}):
        apps = MigrationLoader(connection).project_state(("old_metadata", "0002_initial_data")).apps
    # 0003 的入口会替换历史模型注册表，限制在当前测试内。
    monkeypatch.setattr(migration, "models", migration.models.copy())
    host_settings = (
        {
            "INFLUXDB_INIT_IP_LIST": ["influx.test"],
            "INFLUXDB_INIT_USER": "host",
            "INFLUXDB_INIT_PASSWORD": host_password,
        }
        if host_password is not None
        else {}
    )
    with override_settings(
        **host_settings,
        BKCRYPTO={"SYMMETRIC_CIPHERS": {"default": {"common": {"key": b"test-key-16bytes"}}}},
    ):
        apps.get_model("old_metadata", "ClusterInfo").objects.create(
            cluster_name="influx_cluster1", cluster_type="influxdb", is_default_cluster=True, port=8086
        )
        migration.init_backend_info(apps)
        hosts = apps.get_model("old_metadata", "InfluxDBHostInfo").objects
        assert hosts.get(host_name="INFLUXDB_HOST0").password == expected
