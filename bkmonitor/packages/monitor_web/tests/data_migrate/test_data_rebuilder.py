from types import SimpleNamespace

import pytest

from monitor_web.data_migrate import data_rebuilder


class _FakeQuerySet:
    def __init__(self, rows):
        self._rows = list(rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class _FakeProfileDataSourceManager:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, **kwargs):
        return _FakeQuerySet(
            row
            for row in self._rows
            if row.bk_biz_id == kwargs.get("bk_biz_id") and row.app_name == kwargs.get("app_name")
        )


class _FakeClusterInfoManager:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, **kwargs):
        cluster_names = set(kwargs.get("cluster_name__in") or [])
        cluster_type = kwargs.get("cluster_type")
        bk_tenant_id = kwargs.get("bk_tenant_id")
        return _FakeQuerySet(
            row
            for row in self._rows
            if row.cluster_type == cluster_type
            and row.cluster_name in cluster_names
            and (bk_tenant_id is None or row.bk_tenant_id == bk_tenant_id)
        )


def test_add_profiling_migrate_data_id_route_clones_existing_route(monkeypatch):
    updated = {}
    original_route = {
        "name": "stream_to_tgdp_kafka_profile_topic",
        "stream_to": {
            "stream_to_id": 500,
            "kafka": {
                "topic_name": "profile-topic",
            },
        },
    }

    monkeypatch.setattr(
        data_rebuilder.ProfileDataSource,
        "objects",
        _FakeProfileDataSourceManager(
            [SimpleNamespace(bk_biz_id=2, app_name="demo", bk_data_id=7788)],
        ),
    )
    monkeypatch.setattr(data_rebuilder.ClusterInfo, "TYPE_KAFKA", "kafka")
    monkeypatch.setattr(
        data_rebuilder.ClusterInfo,
        "objects",
        _FakeClusterInfoManager(
            [
                SimpleNamespace(
                    bk_tenant_id="target-tenant",
                    cluster_name="migrate_apm-kafka-public-1",
                    cluster_type="kafka",
                    gse_stream_to_id=900,
                ),
                SimpleNamespace(
                    bk_tenant_id="other-tenant",
                    cluster_name="migrate_apm-kafka-public-1",
                    cluster_type="kafka",
                    gse_stream_to_id=901,
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        data_rebuilder.api,
        "gse",
        SimpleNamespace(
            query_route=lambda **kwargs: [{"route": [original_route]}],
            update_route=lambda **kwargs: updated.update(kwargs),
        ),
    )

    result = data_rebuilder.add_profiling_migrate_data_id_route(
        bk_tenant_id="target-tenant",
        bk_biz_id=2,
        app_name="demo",
        migrate_cluster_name="apm-kafka-public-1",
    )

    assert result["bk_data_id"] == 7788
    assert result["migrate_cluster_name"] == "migrate_apm-kafka-public-1"
    assert result["replaced"] is False
    assert updated["condition"] == {"channel_id": 7788, "plat_name": data_rebuilder.config.DEFAULT_GSE_API_PLAT_NAME}
    new_routes = updated["specification"]["route"]
    assert new_routes[0] == original_route
    assert new_routes[1] == {
        "name": "migrate_profiling_data_id_7788",
        "stream_to": {
            "stream_to_id": 900,
            "kafka": {
                "topic_name": "profile-topic",
            },
        },
    }


def test_add_profiling_migrate_data_id_route_replaces_existing_migrate_route(monkeypatch):
    updated = {}
    source_route = {
        "name": "stream_to_tgdp_kafka_profile_topic",
        "stream_to": {"stream_to_id": 500, "kafka": {"topic_name": "profile-topic"}},
    }
    old_migrate_route = {
        "name": "migrate_profiling_data_id_7788",
        "stream_to": {"stream_to_id": 800, "kafka": {"topic_name": "old-topic"}},
    }

    monkeypatch.setattr(
        data_rebuilder.ProfileDataSource,
        "objects",
        _FakeProfileDataSourceManager([SimpleNamespace(bk_biz_id=2, app_name="demo", bk_data_id=7788)]),
    )
    monkeypatch.setattr(data_rebuilder.ClusterInfo, "TYPE_KAFKA", "kafka")
    monkeypatch.setattr(
        data_rebuilder.ClusterInfo,
        "objects",
        _FakeClusterInfoManager(
            [
                SimpleNamespace(
                    bk_tenant_id="target-tenant",
                    cluster_name="migrate_apm-kafka-public-1",
                    cluster_type="kafka",
                    gse_stream_to_id=900,
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        data_rebuilder.api,
        "gse",
        SimpleNamespace(
            query_route=lambda **kwargs: [{"route": [source_route, old_migrate_route]}],
            update_route=lambda **kwargs: updated.update(kwargs),
        ),
    )

    result = data_rebuilder.add_profiling_migrate_data_id_route(
        bk_tenant_id="target-tenant",
        bk_biz_id=2,
        app_name="demo",
        migrate_cluster_name="migrate_apm-kafka-public-1",
    )

    assert result["replaced"] is True
    assert updated["specification"]["route"] == [
        source_route,
        {
            "name": "migrate_profiling_data_id_7788",
            "stream_to": {"stream_to_id": 900, "kafka": {"topic_name": "profile-topic"}},
        },
    ]


def test_add_profiling_migrate_data_id_route_converts_update_error(monkeypatch):
    class FakeBKAPIError(Exception):
        pass

    source_route = {
        "name": "stream_to_tgdp_kafka_profile_topic",
        "stream_to": {"stream_to_id": 500, "kafka": {"topic_name": "profile-topic"}},
    }

    monkeypatch.setattr(
        data_rebuilder.ProfileDataSource,
        "objects",
        _FakeProfileDataSourceManager([SimpleNamespace(bk_biz_id=2, app_name="demo", bk_data_id=7788)]),
    )
    monkeypatch.setattr(data_rebuilder.ClusterInfo, "TYPE_KAFKA", "kafka")
    monkeypatch.setattr(
        data_rebuilder.ClusterInfo,
        "objects",
        _FakeClusterInfoManager(
            [
                SimpleNamespace(
                    bk_tenant_id="target-tenant",
                    cluster_name="migrate_apm-kafka-public-1",
                    cluster_type="kafka",
                    gse_stream_to_id=900,
                ),
            ]
        ),
    )
    monkeypatch.setattr(data_rebuilder, "BKAPIError", FakeBKAPIError)
    monkeypatch.setattr(
        data_rebuilder.api,
        "gse",
        SimpleNamespace(
            query_route=lambda **kwargs: [{"route": [source_route]}],
            update_route=lambda **kwargs: (_ for _ in ()).throw(FakeBKAPIError("gse unavailable")),
        ),
    )

    with pytest.raises(ValueError, match=r"data_id\(7788\) update gse router failed"):
        data_rebuilder.add_profiling_migrate_data_id_route(
            bk_tenant_id="target-tenant",
            bk_biz_id=2,
            app_name="demo",
            migrate_cluster_name="migrate_apm-kafka-public-1",
        )
