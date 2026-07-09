import json
from contextlib import nullcontext
from dataclasses import dataclass

from monitor_web.data_migrate import plugin_dashboard_result_table
from monitor_web.data_migrate.plugin_strategy_result_table import PluginResultTable


@dataclass
class FakeDashboard:
    id: int
    uid: str
    title: str
    org_id: int
    data: str

    @property
    def pk(self):
        return self.id


class FakeMeta:
    db_table = "dashboard"


class FakeDashboardModel:
    _meta = FakeMeta()
    objects = None


class FakeQuerySet:
    def __init__(self, dashboards):
        self.dashboards = list(dashboards)

    def filter(self, **kwargs):
        dashboards = self.dashboards
        if "id__in" in kwargs:
            ids = set(kwargs["id__in"])
            dashboards = [dashboard for dashboard in dashboards if dashboard.id in ids]
        return FakeQuerySet(dashboards)

    def only(self, *args):
        return self

    def order_by(self, *args):
        return self

    def iterator(self, chunk_size=None):
        yield from self.dashboards

    def __iter__(self):
        return iter(self.dashboards)


class FakeDashboardManager:
    def __init__(self, dashboards):
        self.dashboards = dashboards
        self.updated = []

    def select_for_update(self):
        return FakeQuerySet(self.dashboards)

    def bulk_update(self, dashboards, fields, batch_size=None):
        self.updated.extend(dashboards)


def _plugin_result_table():
    return PluginResultTable(
        plugin_id="get_current_online",
        plugin_type="Script",
        bk_biz_id=2,
        result_table_prefix="script_get_current_online",
        default_result_table_id="script_get_current_online.__default__",
    )


def _dashboard_data():
    return {
        "panels": [
            {
                "id": 68,
                "title": "Online Count - Register",
                "type": "timeseries",
                "targets": [
                    {
                        "refId": "A",
                        "query_configs": [
                            {
                                "alias": "IOS",
                                "data_source_label": "bk_monitor",
                                "data_type_label": "time_series",
                                "metric_field": "ios_online",
                                "refId": "a",
                                "result_table_id": "script_get_current_online.online",
                            }
                        ],
                    },
                    {
                        "refId": "B",
                        "query_configs": [
                            {
                                "alias": "Android",
                                "data_source_label": "bk_monitor",
                                "data_type_label": "time_series",
                                "metric_field": "android_online",
                                "refId": "a",
                                "result_table_id": "script_get_current_online.__default__",
                            },
                            {
                                "alias": "Other",
                                "data_source_label": "bk_monitor",
                                "data_type_label": "time_series",
                                "metric_field": "other",
                                "refId": "b",
                                "result_table_id": "system.cpu_detail",
                            },
                        ],
                    },
                ],
            },
            {
                "id": 69,
                "title": "row",
                "type": "row",
                "panels": [
                    {
                        "id": 70,
                        "title": "Register",
                        "type": "timeseries",
                        "targets": [
                            {
                                "refId": "D",
                                "query_configs": [
                                    {
                                        "alias": "Register",
                                        "data_source_label": "bk_monitor",
                                        "data_type_label": "time_series",
                                        "metric_field": "total_register",
                                        "refId": "a",
                                        "result_table_id": "script_get_current_online.register",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        ]
    }


def test_repair_plugin_dashboard_result_table_dry_run_keeps_dashboard_data(monkeypatch):
    dashboard_data = _dashboard_data()
    dashboard = FakeDashboard(1, "uid-a", "dashboard-a", 100, json.dumps(dashboard_data))

    monkeypatch.setattr(
        plugin_dashboard_result_table, "_list_target_plugin_result_tables", lambda: [_plugin_result_table()]
    )
    monkeypatch.setattr(
        plugin_dashboard_result_table,
        "_build_dashboard_queryset",
        lambda **kwargs: FakeQuerySet([dashboard]),
    )

    result = plugin_dashboard_result_table.repair_plugin_dashboard_result_table_id(bk_biz_id=[2], dry_run=True)

    assert result["bk_biz_ids"] == [2]
    assert result["changed_count"] == 2
    assert result["applied_count"] == 0
    assert json.loads(dashboard.data) == dashboard_data
    assert {change["old_result_table_id"] for change in result["changes"]} == {
        "script_get_current_online.online",
        "script_get_current_online.register",
    }
    assert all(change["new_result_table_id"] == "script_get_current_online.__default__" for change in result["changes"])
    assert result["changes"][1]["panel_path"] == [1, 0]


def test_repair_plugin_dashboard_result_table_applies_changes(monkeypatch):
    dashboard = FakeDashboard(1, "uid-a", "dashboard-a", 100, json.dumps(_dashboard_data()))
    fake_manager = FakeDashboardManager([dashboard])
    FakeDashboardModel.objects = fake_manager

    monkeypatch.setattr(plugin_dashboard_result_table, "Dashboard", FakeDashboardModel)
    monkeypatch.setattr(plugin_dashboard_result_table.transaction, "atomic", nullcontext)
    monkeypatch.setattr(
        plugin_dashboard_result_table, "_list_target_plugin_result_tables", lambda: [_plugin_result_table()]
    )
    monkeypatch.setattr(
        plugin_dashboard_result_table,
        "_build_dashboard_queryset",
        lambda **kwargs: FakeQuerySet([dashboard]),
    )

    result = plugin_dashboard_result_table.repair_plugin_dashboard_result_table_id(dry_run=False)

    updated_data = json.loads(dashboard.data)
    assert result["changed_count"] == 2
    assert result["applied_count"] == 2
    assert len(fake_manager.updated) == 1
    assert updated_data["panels"][0]["targets"][0]["query_configs"][0]["result_table_id"] == (
        "script_get_current_online.__default__"
    )
    assert updated_data["panels"][0]["targets"][0]["query_configs"][0]["metric_field"] == "ios_online"
    assert updated_data["panels"][1]["panels"][0]["targets"][0]["query_configs"][0]["result_table_id"] == (
        "script_get_current_online.__default__"
    )
    assert updated_data["panels"][0]["targets"][1]["query_configs"][0]["result_table_id"] == (
        "script_get_current_online.__default__"
    )
    assert updated_data["panels"][0]["targets"][1]["query_configs"][1]["result_table_id"] == "system.cpu_detail"


def test_repair_plugin_dashboard_result_table_records_invalid_json(monkeypatch):
    dashboard = FakeDashboard(1, "uid-a", "dashboard-a", 100, "{")

    monkeypatch.setattr(
        plugin_dashboard_result_table, "_list_target_plugin_result_tables", lambda: [_plugin_result_table()]
    )
    monkeypatch.setattr(
        plugin_dashboard_result_table,
        "_build_dashboard_queryset",
        lambda **kwargs: FakeQuerySet([dashboard]),
    )

    result = plugin_dashboard_result_table.repair_plugin_dashboard_result_table_id(dry_run=True)

    assert result["changed_count"] == 0
    assert result["invalid_json_count"] == 1
    assert result["invalid_json"][0]["dashboard_uid"] == "uid-a"
