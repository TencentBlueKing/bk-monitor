from types import SimpleNamespace

import pytest

from api.gse.default import AddRoute, DeleteRoute, UpdateRoute
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
        cluster_name = kwargs.get("cluster_name")
        cluster_type = kwargs.get("cluster_type")
        bk_tenant_id = kwargs.get("bk_tenant_id")
        return _FakeQuerySet(
            row
            for row in self._rows
            if row.cluster_type == cluster_type
            and (not cluster_names or row.cluster_name in cluster_names)
            and (cluster_name is None or row.cluster_name == cluster_name)
            and (bk_tenant_id is None or row.bk_tenant_id == bk_tenant_id)
        )


def test_delete_gse_route_with_fallback_retries_with_default_platform(monkeypatch):
    class FakeBKAPIError(Exception):
        pass

    requests = []

    def delete_route(**kwargs):
        requests.append(kwargs)
        if len(requests) == 1:
            raise FakeBKAPIError("tgdp route not found")

    monkeypatch.setattr(data_rebuilder, "BKAPIError", FakeBKAPIError)
    monkeypatch.setattr(data_rebuilder.api, "gse", SimpleNamespace(delete_route=delete_route))

    data_rebuilder._delete_gse_route_with_fallback(
        {
            "condition": {"channel_id": 7788, "plat_name": "tgdp"},
            "operation": {"operator_name": "admin", "method": "specification"},
            "specification": {"route": ["old-route"]},
        }
    )

    assert [request["condition"]["plat_name"] for request in requests] == [
        "tgdp",
        data_rebuilder.config.DEFAULT_GSE_API_PLAT_NAME,
    ]


def test_build_profiling_migrate_route_rejects_pulsar_without_topic():
    with pytest.raises(ValueError, match=r"data_id\(7788\) source pulsar router topic_name is empty"):
        data_rebuilder._build_profiling_migrate_route(
            source_route={
                "name": "stream_to_tgdp_pulsar_profile_topic",
                "stream_to": {
                    "stream_to_id": 500,
                    "pulsar": {"tenant": "biz_2", "namespace": "data"},
                },
            },
            data_id=7788,
            migrate_route_name="migrate_profiling_data_id_7788",
            migrate_stream_to_id=900,
        )


@pytest.mark.parametrize("pulsar_config", [{"name": "profile-topic"}, {"topic_name": "profile-topic"}])
def test_update_route_accepts_pulsar_topic_compatible_fields(pulsar_config):
    serializer = UpdateRoute.RequestSerializer(
        data={
            "condition": {"channel_id": 7788, "plat_name": "bkmonitor"},
            "operation": {"operator_name": "admin"},
            "specification": {
                "route": [
                    {
                        "name": "stream_to_tgdp_pulsar_profile_topic",
                        "stream_to": {"stream_to_id": 500, "pulsar": pulsar_config},
                    }
                ]
            },
        }
    )

    assert serializer.is_valid(), serializer.errors


@pytest.mark.parametrize("pulsar_config", [{"name": "profile-topic"}, {"topic_name": "profile-topic"}])
def test_add_route_accepts_pulsar_topic_compatible_fields(pulsar_config):
    serializer = AddRoute.RequestSerializer(
        data={
            "metadata": {"channel_id": 7788, "plat_name": "bkmonitor"},
            "operation": {"operator_name": "admin"},
            "route": [
                {
                    "name": "stream_to_tgdp_pulsar_profile_topic",
                    "stream_to": {"stream_to_id": 500, "pulsar": pulsar_config},
                }
            ],
        }
    )

    assert serializer.is_valid(), serializer.errors


def test_update_route_rejects_pulsar_without_topic():
    serializer = UpdateRoute.RequestSerializer(
        data={
            "condition": {"channel_id": 7788, "plat_name": "bkmonitor"},
            "operation": {"operator_name": "admin"},
            "specification": {
                "route": [
                    {
                        "name": "stream_to_tgdp_pulsar_profile_topic",
                        "stream_to": {"stream_to_id": 500, "pulsar": {"tenant": "biz_2"}},
                    }
                ]
            },
        }
    )

    assert not serializer.is_valid()


def test_add_route_rejects_pulsar_without_topic():
    serializer = AddRoute.RequestSerializer(
        data={
            "metadata": {"channel_id": 7788, "plat_name": "bkmonitor"},
            "operation": {"operator_name": "admin"},
            "route": [
                {
                    "name": "stream_to_tgdp_pulsar_profile_topic",
                    "stream_to": {"stream_to_id": 500, "pulsar": {"tenant": "biz_2"}},
                }
            ],
        }
    )

    assert not serializer.is_valid()


def test_add_profiling_migrate_data_id_route_converts_pulsar_route_to_kafka(monkeypatch):
    updated = {}
    original_route = {
        "name": "stream_to_tgdp_pulsar_profile_topic",
        "stream_to": {
            "stream_to_id": 500,
            "pulsar": {
                "topic_name": "profile-topic",
                "tenant": "biz_2",
                "namespace": "data",
            },
        },
        "deliver_type": 0,
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
        "deliver_type": 0,
    }
    serializer = UpdateRoute.RequestSerializer(data=updated)
    assert serializer.is_valid(), serializer.errors


def test_replace_profiling_data_id_route_uses_exact_kafka_cluster_and_removes_dual_write(monkeypatch):
    updated = {}
    deleted = {}
    source_route = {
        "name": "stream_to_tgdp_pulsar_profile-topic",
        "stream_to": {
            "stream_to_id": 500,
            "pulsar": {
                "topic_name": "profile-topic",
                "tenant": "biz_2",
                "namespace": "data",
            },
        },
        "deliver_type": 0,
    }
    migrate_route = {
        "name": "migrate_profiling_data_id_7788",
        "stream_to": {"stream_to_id": 800, "kafka": {"topic_name": "profile-topic"}},
        "deliver_type": 0,
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
                    cluster_name="apm-kafka-public-1",
                    cluster_type="kafka",
                    gse_stream_to_id=900,
                ),
                SimpleNamespace(
                    bk_tenant_id="target-tenant",
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
            query_route=lambda **kwargs: [{"route": [source_route, migrate_route]}],
            update_route=lambda **kwargs: updated.update(kwargs),
            delete_route=lambda **kwargs: deleted.update(kwargs),
        ),
    )

    dry_run_result = data_rebuilder.replace_profiling_data_id_route(
        bk_tenant_id="target-tenant",
        bk_biz_id=2,
        app_name="demo",
        kafka_cluster_name="apm-kafka-public-1",
        dry_run=True,
    )

    assert dry_run_result["updated"] is False
    assert updated == {}
    assert deleted == {}

    result = data_rebuilder.replace_profiling_data_id_route(
        bk_tenant_id="target-tenant",
        bk_biz_id=2,
        app_name="demo",
        kafka_cluster_name="apm-kafka-public-1",
    )

    expected_route = {
        "name": "stream_to_tgdp_kafka_profile-topic",
        "stream_to": {"stream_to_id": 900, "kafka": {"topic_name": "profile-topic"}},
        "deliver_type": 0,
    }
    assert result["kafka_cluster_name"] == "apm-kafka-public-1"
    assert result["kafka_stream_to_id"] == 900
    assert result["before"] == [source_route, migrate_route]
    assert result["after"] == [expected_route]
    assert result["deleted_route_names"] == [
        "migrate_profiling_data_id_7788",
        "stream_to_tgdp_pulsar_profile-topic",
    ]
    assert updated["specification"]["route"] == [expected_route]
    assert deleted == {
        "condition": {"channel_id": 7788, "plat_name": "tgdp"},
        "operation": {"operator_name": data_rebuilder.settings.COMMON_USERNAME, "method": "specification"},
        "specification": {"route": ["migrate_profiling_data_id_7788", "stream_to_tgdp_pulsar_profile-topic"]},
    }
    serializer = UpdateRoute.RequestSerializer(data=updated)
    assert serializer.is_valid(), serializer.errors
    serializer = DeleteRoute.RequestSerializer(data=deleted)
    assert serializer.is_valid(), serializer.errors


def test_replace_profiling_data_id_route_is_reentrant_and_prefers_existing_kafka(monkeypatch):
    pulsar_route = {
        "name": "stream_to_tgdp_pulsar_legacy-topic",
        "stream_to": {
            "stream_to_id": 500,
            "pulsar": {"topic_name": "legacy-topic", "tenant": "biz_2", "namespace": "data"},
        },
    }
    kafka_route = {
        "name": "stream_to_tgdp_kafka_profile-topic",
        "stream_to": {"stream_to_id": 700, "kafka": {"topic_name": "profile-topic"}},
    }
    current_routes = [pulsar_route, kafka_route]
    update_requests = []
    delete_requests = []

    def update_route(**kwargs):
        update_requests.append(kwargs)
        refreshed_route = kwargs["specification"]["route"][0]
        current_routes[:] = [route for route in current_routes if route["name"] != refreshed_route["name"]]
        current_routes.append(refreshed_route)

    def delete_route(**kwargs):
        delete_requests.append(kwargs)
        deleted_names = set(kwargs["specification"]["route"])
        current_routes[:] = [route for route in current_routes if route["name"] not in deleted_names]

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
                    cluster_name="apm-kafka-public-1",
                    cluster_type="kafka",
                    gse_stream_to_id=900,
                )
            ]
        ),
    )
    monkeypatch.setattr(
        data_rebuilder.api,
        "gse",
        SimpleNamespace(
            query_route=lambda **kwargs: [{"route": list(current_routes)}],
            update_route=update_route,
            delete_route=delete_route,
        ),
    )

    first_result = data_rebuilder.replace_profiling_data_id_route(
        bk_tenant_id="target-tenant",
        bk_biz_id=2,
        app_name="demo",
        kafka_cluster_name="apm-kafka-public-1",
    )
    second_result = data_rebuilder.replace_profiling_data_id_route(
        bk_tenant_id="target-tenant",
        bk_biz_id=2,
        app_name="demo",
        kafka_cluster_name="apm-kafka-public-1",
    )

    expected_route = {
        "name": "stream_to_tgdp_kafka_profile-topic",
        "stream_to": {"stream_to_id": 900, "kafka": {"topic_name": "profile-topic"}},
    }
    assert first_result["after"] == [expected_route]
    assert first_result["deleted_route_names"] == ["stream_to_tgdp_pulsar_legacy-topic"]
    assert second_result["before"] == [expected_route]
    assert second_result["after"] == [expected_route]
    assert second_result["deleted_route_names"] == []
    assert current_routes == [expected_route]
    assert len(update_requests) == 2
    assert len(delete_requests) == 1


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
