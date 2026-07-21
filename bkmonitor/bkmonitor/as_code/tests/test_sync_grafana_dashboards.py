"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import threading
import time
from types import SimpleNamespace

import pytest

from bkmonitor.as_code import parse


def test_sync_grafana_dashboards_runs_independent_requests_concurrently(monkeypatch):
    initial_request_barrier = threading.Barrier(2)
    import_barrier = threading.Barrier(2)
    imported_dashboards = []

    def search_folder_or_dashboard(**kwargs):
        assert kwargs == {"type": "dash-folder", "org_id": 11}
        initial_request_barrier.wait(timeout=1)
        return {"data": []}

    def get_all_data_source(**kwargs):
        assert kwargs == {"org_id": 11}
        initial_request_barrier.wait(timeout=1)
        return {"data": [{"type": "prometheus", "uid": "prometheus-uid"}]}

    def create_folder(**kwargs):
        assert kwargs == {"org_id": 11, "title": "operations"}
        return {"result": True, "data": {"id": 21}}

    def import_dashboard(**kwargs):
        import_barrier.wait(timeout=1)
        imported_dashboards.append(kwargs)

    monkeypatch.setattr(parse, "get_or_create_org", lambda bk_biz_id: {"id": 11})
    monkeypatch.setattr(
        parse.api,
        "grafana",
        SimpleNamespace(
            search_folder_or_dashboard=search_folder_or_dashboard,
            get_all_data_source=get_all_data_source,
            create_folder=create_folder,
            import_dashboard=import_dashboard,
        ),
    )
    dashboards = {
        "datasources.yaml": {"PROMETHEUS": "prometheus-uid"},
        "operations/overview.json": {
            "id": 1,
            "title": "overview",
            "__inputs": [{"name": "PROMETHEUS", "type": "datasource", "pluginId": "prometheus"}],
        },
        "operations/detail.json": {
            "id": 2,
            "title": "detail",
            "__inputs": [{"name": "PROMETHEUS", "type": "datasource", "pluginId": "prometheus"}],
        },
    }

    parse.sync_grafana_dashboards(2, dashboards)

    assert len(imported_dashboards) == 2
    assert {item["dashboard"]["title"] for item in imported_dashboards} == {"overview", "detail"}
    assert all(item["folderId"] == 21 for item in imported_dashboards)
    assert all(item["inputs"][0]["value"] == "prometheus-uid" for item in imported_dashboards)
    assert dashboards["operations/overview.json"]["id"] == 1
    assert "datasources.yaml" in dashboards


def test_sync_grafana_dashboards_uses_existing_folder_and_datasource_type(monkeypatch):
    imported_dashboards = []
    grafana = SimpleNamespace(
        search_folder_or_dashboard=lambda **kwargs: {"data": [{"title": "default", "id": 31}]},
        get_all_data_source=lambda **kwargs: {"data": [{"type": "loki", "uid": "loki-uid"}]},
        create_folder=lambda **kwargs: (_ for _ in ()).throw(AssertionError("folder should not be created")),
        import_dashboard=lambda **kwargs: imported_dashboards.append(kwargs),
    )
    monkeypatch.setattr(parse, "get_or_create_org", lambda bk_biz_id: {"id": 11})
    monkeypatch.setattr(parse.api, "grafana", grafana)

    parse.sync_grafana_dashboards(
        2,
        {
            "default/log.json": {
                "title": "logs",
                "__inputs": [{"name": "LOKI", "type": "datasource", "pluginId": "loki"}],
            }
        },
    )

    assert imported_dashboards == [
        {
            "dashboard": {
                "title": "logs",
                "__inputs": [{"name": "LOKI", "type": "datasource", "pluginId": "loki"}],
            },
            "org_id": 11,
            "inputs": [{"name": "LOKI", "type": "datasource", "pluginId": "loki", "value": "loki-uid"}],
            "overwrite": True,
            "folderId": 31,
        }
    ]


# --------------------------------------------------------------------------- #
# 以下用例聚焦 import dashboard 的目录归属（问题1）与重复实体串行（问题3）。
# 统一用一个 helper 构造 grafana mock，记录每次 import 的调用。
# --------------------------------------------------------------------------- #


def _make_grafana(folders=None, datasources=None, on_import=None, on_create_folder=None):
    """构造一个可注入的 grafana mock。

    - folders: search_folder_or_dashboard 返回的已存在目录
    - datasources: get_all_data_source 返回的数据源
    - on_import: import_dashboard 被调用时执行的回调（默认追加到 imported 列表）
    - on_create_folder: create_folder 的行为（默认成功，id 自增）
    """
    imported = []
    created = []
    counter = {"next_id": 100}

    def default_create_folder(**kwargs):
        counter["next_id"] += 1
        created.append(kwargs)
        return {"result": True, "data": {"id": counter["next_id"]}}

    def default_import(**kwargs):
        imported.append(kwargs)

    grafana = SimpleNamespace(
        search_folder_or_dashboard=lambda **kwargs: {"data": folders or []},
        get_all_data_source=lambda **kwargs: {"data": datasources or []},
        create_folder=on_create_folder or default_create_folder,
        import_dashboard=on_import or default_import,
    )
    return grafana, imported, created


def test_import_dashboard_root_folder_uses_folder_id_0(monkeypatch):
    """path 无目录段（folder=""）时，应导入到 General 根目录 folderId=0。"""
    grafana, imported, _ = _make_grafana(datasources=[{"type": "prometheus", "uid": "p-uid"}])
    monkeypatch.setattr(parse, "get_or_create_org", lambda bk_biz_id: {"id": 11})
    monkeypatch.setattr(parse.api, "grafana", grafana)

    parse.sync_grafana_dashboards(2, {"root.json": {"title": "root-dash"}})

    assert len(imported) == 1
    assert imported[0]["folderId"] == 0


def test_import_dashboard_existing_folder_uses_its_id(monkeypatch):
    """folder 已存在于 Grafana 时，应复用其 id，且不新建目录。"""
    grafana, imported, created = _make_grafana(folders=[{"title": "ops", "id": 55}])
    monkeypatch.setattr(parse, "get_or_create_org", lambda bk_biz_id: {"id": 11})
    monkeypatch.setattr(parse.api, "grafana", grafana)

    parse.sync_grafana_dashboards(2, {"ops/a.json": {"title": "a"}})

    assert created == []  # 未新建目录
    assert imported[0]["folderId"] == 55


def test_import_dashboard_missing_folder_created_then_used(monkeypatch):
    """folder 不存在时应先创建，再用新 id 导入。"""
    grafana, imported, created = _make_grafana()
    monkeypatch.setattr(parse, "get_or_create_org", lambda bk_biz_id: {"id": 11})
    monkeypatch.setattr(parse.api, "grafana", grafana)

    parse.sync_grafana_dashboards(2, {"newfolder/a.json": {"title": "a"}})

    assert len(created) == 1
    assert created[0]["title"] == "newfolder"
    # 新建目录返回的 id（helper 从 101 起自增）应被用于 import
    assert imported[0]["folderId"] == 101


def test_import_dashboard_create_folder_failure_raises(monkeypatch):
    """创建目录失败时应抛出 ValueError，而不是静默继续。"""

    def failing_create_folder(**kwargs):
        return {"result": False, "message": "boom"}

    grafana, _, _ = _make_grafana(on_create_folder=failing_create_folder)
    monkeypatch.setattr(parse, "get_or_create_org", lambda bk_biz_id: {"id": 11})
    monkeypatch.setattr(parse.api, "grafana", grafana)

    with pytest.raises(ValueError):
        parse.sync_grafana_dashboards(2, {"badfolder/a.json": {"title": "a"}})


def test_import_dashboard_duplicate_uid_serialized_no_overlap(monkeypatch):
    """相同 uid 的两个仪表盘必须串行导入，不能同时进入 import_dashboard。

    通过在 import 内部检测重入并发来验证：若并发，active 计数会 >1。
    """
    lock = threading.Lock()
    state = {"active": 0, "max_active": 0}
    order = []

    def on_import(**kwargs):
        with lock:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
            order.append(kwargs["dashboard"]["title"])
        # 稍作停留放大并发窗口
        time.sleep(0.02)
        with lock:
            state["active"] -= 1

    grafana, _, _ = _make_grafana(on_import=on_import)
    monkeypatch.setattr(parse, "get_or_create_org", lambda bk_biz_id: {"id": 11})
    monkeypatch.setattr(parse.api, "grafana", grafana)

    dashboards = {
        "ops/first.json": {"uid": "same-uid", "title": "first"},
        "ops/second.json": {"uid": "same-uid", "title": "second"},
    }
    parse.sync_grafana_dashboards(2, dashboards)

    # 同 uid → 同组 → 串行，最大并发数必须为 1
    assert state["max_active"] == 1
    # 两个都被导入，且组内保持插入顺序（后者覆盖前者的语义）
    assert order == ["first", "second"]


def test_import_dashboard_same_folder_same_title_serialized(monkeypatch):
    """无 uid、同目录同 title 的仪表盘也应串行（Grafana 按 folder+title 定位）。"""
    lock = threading.Lock()
    state = {"active": 0, "max_active": 0}

    def on_import(**kwargs):
        with lock:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
        time.sleep(0.02)
        with lock:
            state["active"] -= 1

    grafana, _, _ = _make_grafana(folders=[{"title": "ops", "id": 7}], on_import=on_import)
    monkeypatch.setattr(parse, "get_or_create_org", lambda bk_biz_id: {"id": 11})
    monkeypatch.setattr(parse.api, "grafana", grafana)

    dashboards = {
        "ops/a.json": {"title": "dup"},
        "ops/b.json": {"title": "dup"},
    }
    parse.sync_grafana_dashboards(2, dashboards)

    assert state["max_active"] == 1


def test_import_dashboard_different_uids_same_folder_same_title_serialized(monkeypatch):
    """即使 uid 不同，同目录同 title 的仪表盘仍指向冲突实体，必须串行导入。"""
    lock = threading.Lock()
    state = {"active": 0, "max_active": 0}

    def on_import(**kwargs):
        with lock:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
        time.sleep(0.02)
        with lock:
            state["active"] -= 1

    grafana, _, _ = _make_grafana(folders=[{"title": "ops", "id": 7}], on_import=on_import)
    monkeypatch.setattr(parse, "get_or_create_org", lambda bk_biz_id: {"id": 11})
    monkeypatch.setattr(parse.api, "grafana", grafana)

    dashboards = {
        "ops/a.json": {"uid": "uid-a", "title": "dup"},
        "ops/b.json": {"uid": "uid-b", "title": "dup"},
    }
    parse.sync_grafana_dashboards(2, dashboards)

    assert state["max_active"] == 1


def test_import_dashboard_transitive_conflicts_serialized(monkeypatch):
    """UID 与 title 冲突关系可传递时，整个连通分组必须串行导入。"""
    lock = threading.Lock()
    state = {"active": 0, "max_active": 0}

    def on_import(**kwargs):
        with lock:
            state["active"] += 1
            state["max_active"] = max(state["max_active"], state["active"])
        time.sleep(0.02)
        with lock:
            state["active"] -= 1

    grafana, _, _ = _make_grafana(folders=[{"title": "ops", "id": 7}], on_import=on_import)
    monkeypatch.setattr(parse, "get_or_create_org", lambda bk_biz_id: {"id": 11})
    monkeypatch.setattr(parse.api, "grafana", grafana)

    dashboards = {
        "ops/a.json": {"uid": "shared-uid", "title": "first"},
        "ops/b.json": {"uid": "shared-uid", "title": "bridge"},
        "ops/c.json": {"uid": "other-uid", "title": "bridge"},
    }
    parse.sync_grafana_dashboards(2, dashboards)

    assert state["max_active"] == 1


def test_import_dashboard_distinct_entities_run_concurrently(monkeypatch):
    """不同实体（不同 uid）应能并发导入：两个线程需同时到达屏障。"""
    barrier = threading.Barrier(2, timeout=2)

    def on_import(**kwargs):
        barrier.wait()

    grafana, _, _ = _make_grafana(folders=[{"title": "ops", "id": 7}], on_import=on_import)
    monkeypatch.setattr(parse, "get_or_create_org", lambda bk_biz_id: {"id": 11})
    monkeypatch.setattr(parse.api, "grafana", grafana)

    dashboards = {
        "ops/a.json": {"uid": "uid-a", "title": "a"},
        "ops/b.json": {"uid": "uid-b", "title": "b"},
    }
    # 若未并发，barrier.wait 会超时抛 BrokenBarrierError，测试失败
    parse.sync_grafana_dashboards(2, dashboards)


def test_import_dashboard_datasources_yaml_skipped(monkeypatch):
    """datasources.yaml 不应作为仪表盘导入，且不应被从入参 dict 中 pop 掉。"""
    grafana, imported, _ = _make_grafana(datasources=[{"type": "prometheus", "uid": "p-uid"}])
    monkeypatch.setattr(parse, "get_or_create_org", lambda bk_biz_id: {"id": 11})
    monkeypatch.setattr(parse.api, "grafana", grafana)

    dashboards = {
        "datasources.yaml": {"PROMETHEUS": "p-uid"},
        "a.json": {"title": "a"},
    }
    parse.sync_grafana_dashboards(2, dashboards)

    assert len(imported) == 1
    assert imported[0]["dashboard"]["title"] == "a"
    assert "datasources.yaml" in dashboards  # 未被 pop


def test_import_dashboard_unknown_datasource_uid_raises(monkeypatch):
    """datasources.yaml 引用了不存在的数据源 uid 时应报错。"""
    grafana, _, _ = _make_grafana(datasources=[{"type": "prometheus", "uid": "p-uid"}])
    monkeypatch.setattr(parse, "get_or_create_org", lambda bk_biz_id: {"id": 11})
    monkeypatch.setattr(parse.api, "grafana", grafana)

    dashboards = {"datasources.yaml": {"PROMETHEUS": "missing-uid"}}
    with pytest.raises(ValueError):
        parse.sync_grafana_dashboards(2, dashboards)


def test_import_dashboard_id_field_stripped(monkeypatch):
    """dashboard 的 id 字段应在导入前被移除，避免与目标环境 id 冲突。"""
    grafana, imported, _ = _make_grafana()
    monkeypatch.setattr(parse, "get_or_create_org", lambda bk_biz_id: {"id": 11})
    monkeypatch.setattr(parse.api, "grafana", grafana)

    parse.sync_grafana_dashboards(2, {"a.json": {"id": 999, "title": "a"}})

    assert "id" not in imported[0]["dashboard"]
