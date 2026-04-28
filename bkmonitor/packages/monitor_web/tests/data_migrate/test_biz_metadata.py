from types import SimpleNamespace

from monitor_web.data_migrate.biz_matadata import _collect_normal_plugin_data
from monitor_web.plugin.constant import PluginType


class _FakePluginQuerySet:
    def __init__(self, plugins):
        self._plugins = list(plugins)

    def exclude(self, plugin_type__in):
        return _FakePluginQuerySet([plugin for plugin in self._plugins if plugin.plugin_type not in plugin_type__in])

    def only(self, *args, **kwargs):
        return self

    def values_list(self, field_name, flat=False):
        values = [getattr(plugin, field_name) for plugin in self._plugins]
        if flat:
            return values
        return [(value,) for value in values]

    def __iter__(self):
        return iter(self._plugins)


class _FakePluginManager:
    def __init__(self, plugins):
        self._plugins = plugins

    def filter(self, **kwargs):
        bk_biz_id = kwargs.get("bk_biz_id")
        plugins = [plugin for plugin in self._plugins if bk_biz_id is None or plugin.bk_biz_id == bk_biz_id]
        return _FakePluginQuerySet(plugins)


class _FakeDataSourceQuerySet:
    def __init__(self, rows):
        self._rows = list(rows)

    def values_list(self, *args, **kwargs):
        return list(self._rows)


class _FakeDataSourceManager:
    def __init__(self, expected_rows):
        self._expected_rows = list(expected_rows)

    def filter(self, **kwargs):
        return _FakeDataSourceQuerySet(self._expected_rows)


def test_collect_normal_plugin_data_includes_k8s_plugin(monkeypatch):
    plugin = SimpleNamespace(
        plugin_type=PluginType.K8S,
        plugin_id="demo",
        bk_biz_id=2,
        bk_tenant_id="system",
    )

    from monitor_web.data_migrate import biz_matadata

    monkeypatch.setattr(
        biz_matadata.CollectorPluginMeta,
        "objects",
        _FakePluginManager([plugin]),
    )
    monkeypatch.setattr(
        biz_matadata.DataSource,
        "objects",
        _FakeDataSourceManager([("k8s_demo", 1234)]),
    )
    monkeypatch.setattr(
        biz_matadata.PluginVersionHistory,
        "get_result_table_id",
        staticmethod(lambda plugin, table_name: f"{plugin.plugin_type}_{plugin.plugin_id}.{table_name}"),
    )

    table_ids = set()
    data_ids = set()

    _collect_normal_plugin_data(2, table_ids, data_ids)

    assert data_ids == {1234}
    assert table_ids == {"k8s_demo.__default__"}
