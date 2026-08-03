from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from metadata.models import ClusterInfo
from metadata.resources.cluster import GetClusterStatusResource
from metadata.service.cluster_status import ClusterStatusService


def make_cluster(cluster_id: int, cluster_type: str = ClusterInfo.TYPE_ES):
    return SimpleNamespace(
        cluster_id=cluster_id,
        cluster_name=f"cluster-{cluster_id}",
        display_name=f"Cluster {cluster_id}",
        cluster_type=cluster_type,
    )


def make_health_result(cluster, **kwargs):
    result = {
        "cluster_id": cluster.cluster_id,
        "cluster_name": cluster.cluster_name,
        "cluster_type": cluster.cluster_type,
        "status": ClusterInfo.CHECK_STATUS_AVAILABLE,
        "is_connected": True,
        "is_available": True,
        "error": None,
        "details": {},
    }
    result.update(kwargs)
    return result


def test_get_status_projects_standard_fields_and_es_degraded():
    cluster = make_cluster(1)
    cluster.health_check = lambda timeout, include_node_details=False: make_health_result(
        cluster,
        details={
            "health_status": "yellow",
            "nodes": {"total": 2, "available": 2},
            "capacity": {
                "total_bytes": 100,
                "used_bytes": 40,
                "available_bytes": 60,
                "used_percent": 40.0,
            },
            "indices_store_bytes": 30,
            "node_details": [
                {
                    "name": "node-1",
                    "host": "es-1",
                    "ip": "127.0.0.1",
                    "roles": "data,ingest",
                    "shard_count": 3,
                    "capacity": {
                        "total_bytes": 100,
                        "used_bytes": 40,
                        "available_bytes": 60,
                        "used_percent": 40.0,
                        "raw_capacity": "drop",
                    },
                    "indices_store_bytes": 30,
                    "raw_node_field": "drop",
                }
            ],
            "raw_backend_response": {"must_not": "leak"},
        },
    )

    default_result = ClusterStatusService.get_status(cluster, timeout=3)
    result = ClusterStatusService.get_status(cluster, timeout=3, include_node_details=True)

    assert "node_details" not in default_result["details"]
    assert result["status"] == ClusterStatusService.STATUS_DEGRADED
    assert result["is_available"] is True
    assert result["nodes"] == {"total": 2, "available": 2}
    assert result["capacity"]["used_bytes"] == 40
    assert result["details"]["health_status"] == "yellow"
    assert result["details"]["indices_store_bytes"] == 30
    assert result["details"]["node_details"][0] == {
        "name": "node-1",
        "host": "es-1",
        "ip": "127.0.0.1",
        "roles": ["data", "ingest"],
        "shard_count": 3,
        "capacity": {
            "total_bytes": 100,
            "used_bytes": 40,
            "available_bytes": 60,
            "used_percent": 40.0,
        },
        "indices_store_bytes": 30,
    }
    assert result["details"]["collection_errors"] == []
    assert "raw_backend_response" not in result["details"]


@pytest.mark.parametrize(
    ("nodes", "expected_status", "expected_available"),
    [
        ({"total": 2, "available": 2}, "available", True),
        ({"total": 2, "available": 1}, "degraded", True),
        ({"total": 2, "available": 0}, "unavailable", False),
        ({"total": 0, "available": 0}, "unavailable", False),
    ],
)
def test_get_status_projects_doris_backend_status(nodes, expected_status, expected_available):
    cluster = make_cluster(2, ClusterInfo.TYPE_DORIS)
    cluster.health_check = lambda timeout, include_node_details=False: make_health_result(
        cluster, details={"nodes": nodes}
    )

    result = ClusterStatusService.get_status(cluster, timeout=3, include_node_details=True)

    assert result["status"] == expected_status
    assert result["is_available"] is expected_available
    if not expected_available:
        assert result["error"]["code"] == ClusterInfo.CHECK_ERROR_CLUSTER_UNHEALTHY


def test_get_status_degrades_when_doris_backends_cannot_be_queried():
    cluster = make_cluster(2, ClusterInfo.TYPE_DORIS)
    cluster.health_check = lambda timeout, include_node_details=False: make_health_result(
        cluster,
        details={
            "collection_errors": [
                {
                    "component": "backends",
                    "code": "DORIS_BACKENDS_QUERY_FAILED",
                    "message": "Doris 集群后端状态和容量查询失败",
                    "details": {"type": "OperationalError", "message": "access denied"},
                }
            ]
        },
    )

    result = ClusterStatusService.get_status(cluster, timeout=3)

    assert result["status"] == ClusterStatusService.STATUS_DEGRADED
    assert result["is_connected"] is True
    assert result["is_available"] is True
    assert result["nodes"] == {"total": None, "available": None}
    assert result["capacity"]["total_bytes"] is None
    assert result["error"] is None
    assert result["details"]["collection_errors"][0]["code"] == "DORIS_BACKENDS_QUERY_FAILED"


def test_get_status_projects_fixed_doris_node_fields():
    cluster = make_cluster(2, ClusterInfo.TYPE_DORIS)
    cluster.health_check = lambda timeout, include_node_details=False: make_health_result(
        cluster,
        details={
            "nodes": {"total": 1, "available": 1},
            "query": "SHOW BACKENDS",
            "response": {"raw": "drop"},
            "node_details": [
                {
                    "backend_id": 10001,
                    "host": "doris-1",
                    "alive": True,
                    "decommissioned": False,
                    "tablet_count": 10,
                    "capacity": {"total_bytes": 100, "used_bytes": 40, "available_bytes": 60},
                    "data_used_bytes": 20,
                    "trash_used_bytes": 2,
                    "remote_used_bytes": None,
                    "max_disk_used_percent": 45.0,
                    "last_heartbeat": "2026-08-03 10:00:00",
                    "error_message": "",
                    "version": "2.1.7",
                    "node_role": "mix",
                    "raw_status": {"must_not": "leak"},
                }
            ],
        },
    )

    result = ClusterStatusService.get_status(cluster, timeout=3, include_node_details=True)

    assert "query" not in result["details"]
    assert "response" not in result["details"]
    node = result["details"]["node_details"][0]
    assert set(node) == {
        "backend_id",
        "host",
        "alive",
        "decommissioned",
        "tablet_count",
        "capacity",
        "data_used_bytes",
        "trash_used_bytes",
        "remote_used_bytes",
        "max_disk_used_percent",
        "last_heartbeat",
        "error_message",
        "version",
        "node_role",
    }
    assert node["capacity"]["used_percent"] is None


@pytest.mark.parametrize("cluster_type", [ClusterInfo.TYPE_KAFKA, ClusterInfo.TYPE_VM])
def test_get_status_keeps_standard_shape_for_clusters_without_capacity(cluster_type):
    cluster = make_cluster(3, cluster_type)
    details = (
        {"broker_count": 2, "topic_count": 10, "unexpected": "drop"}
        if cluster_type == ClusterInfo.TYPE_KAFKA
        else {"url": "http://vm/health", "status_code": 200, "unexpected": "drop"}
    )
    cluster.health_check = lambda timeout, include_node_details=False: make_health_result(cluster, details=details)

    result = ClusterStatusService.get_status(cluster, timeout=3)

    assert result["status"] == ClusterStatusService.STATUS_AVAILABLE
    assert result["nodes"] == {"total": None, "available": None}
    assert result["capacity"] == {
        "total_bytes": None,
        "used_bytes": None,
        "available_bytes": None,
        "used_percent": None,
    }
    assert result["details"]["collection_errors"] == []
    assert "unexpected" not in result["details"]
    if cluster_type == ClusterInfo.TYPE_KAFKA:
        assert result["details"]["broker_count"] == 2
        assert result["details"]["topic_count"] == 10
    else:
        assert result["details"]["url"] == "http://vm/health"
        assert result["details"]["status_code"] == 200


def test_get_status_projects_unsupported_cluster():
    cluster = make_cluster(4, ClusterInfo.TYPE_REDIS)
    cluster.health_check = lambda timeout, include_node_details=False: make_health_result(
        cluster,
        status=ClusterInfo.CHECK_STATUS_UNSUPPORTED,
        is_connected=False,
        is_available=False,
        error={"code": ClusterInfo.CHECK_ERROR_UNSUPPORTED_CLUSTER_TYPE},
    )

    result = ClusterStatusService.get_status(cluster, timeout=3)

    assert result["status"] == ClusterStatusService.STATUS_UNSUPPORTED
    assert result["is_available"] is False
    assert result["error"]["code"] == ClusterInfo.CHECK_ERROR_UNSUPPORTED_CLUSTER_TYPE


def test_get_statuses_deduplicates_preserves_order_and_returns_not_found(mocker):
    clusters = [make_cluster(2), make_cluster(1)]
    cluster_filter = mocker.patch(
        "metadata.service.cluster_status.ClusterInfo.objects.filter",
        return_value=clusters,
    )
    mocker.patch.object(
        ClusterStatusService,
        "get_status",
        side_effect=lambda cluster, timeout, include_node_details: {
            "cluster_id": cluster.cluster_id,
            "timeout": timeout,
            "include_node_details": include_node_details,
        },
    )

    results = ClusterStatusService.get_statuses("tenant-a", [2, 1, 2, 404], timeout=7)

    assert [result["cluster_id"] for result in results] == [2, 1, 404]
    assert results[-1]["status"] == ClusterStatusService.STATUS_UNKNOWN
    assert results[-1]["error"]["code"] == "CLUSTER_NOT_FOUND"
    cluster_filter.assert_called_once_with(bk_tenant_id="tenant-a", cluster_id__in=[2, 1, 404])


def test_get_statuses_limits_workers_to_five(mocker):
    clusters = [make_cluster(cluster_id) for cluster_id in range(1, 7)]
    mocker.patch("metadata.service.cluster_status.ClusterInfo.objects.filter", return_value=clusters)
    mocker.patch.object(
        ClusterStatusService,
        "get_status",
        side_effect=lambda cluster, timeout, include_node_details: {"cluster_id": cluster.cluster_id},
    )
    executor = mocker.patch(
        "metadata.service.cluster_status.ThreadPoolExecutor",
        wraps=ThreadPoolExecutor,
    )

    results = ClusterStatusService.get_statuses("system", list(range(1, 7)))

    executor.assert_called_once_with(max_workers=5)
    assert [result["cluster_id"] for result in results] == list(range(1, 7))


def test_get_statuses_isolates_single_cluster_failure(mocker):
    clusters = [make_cluster(1), make_cluster(2)]
    mocker.patch("metadata.service.cluster_status.ClusterInfo.objects.filter", return_value=clusters)

    def get_status(cluster, timeout, include_node_details):
        if cluster.cluster_id == 2:
            raise RuntimeError("probe failed")
        return {"cluster_id": cluster.cluster_id, "status": "available"}

    mocker.patch.object(ClusterStatusService, "get_status", side_effect=get_status)

    results = ClusterStatusService.get_statuses("system", [1, 2])

    assert results[0] == {"cluster_id": 1, "status": "available"}
    assert results[1]["status"] == ClusterStatusService.STATUS_UNAVAILABLE
    assert results[1]["error"]["code"] == "STATUS_COLLECTION_FAILED"


@pytest.mark.parametrize("raises", [False, True])
def test_status_worker_closes_old_connections_at_task_boundaries(mocker, raises):
    cluster = make_cluster(1)
    close_connections = mocker.patch.object(ClusterStatusService, "_close_old_connections")
    get_status = mocker.patch.object(ClusterStatusService, "get_status")
    if raises:
        get_status.side_effect = RuntimeError("probe failed")
        with pytest.raises(RuntimeError, match="probe failed"):
            ClusterStatusService._get_status_in_worker(cluster, 5, False)
    else:
        get_status.return_value = {"cluster_id": 1}
        assert ClusterStatusService._get_status_in_worker(cluster, 5, False) == {"cluster_id": 1}

    assert close_connections.call_count == 2


@pytest.mark.parametrize(
    "data",
    [
        {"cluster_ids": []},
        {"cluster_ids": list(range(1, 22))},
        {"cluster_ids": [1], "timeout": 0},
        {"cluster_ids": [1], "timeout": 31},
    ],
)
def test_resource_serializer_rejects_invalid_batch(data):
    serializer = GetClusterStatusResource.RequestSerializer(data={"bk_tenant_id": "system", **data})

    assert serializer.is_valid() is False


def test_resource_calls_cluster_status_service(mocker):
    get_statuses = mocker.patch.object(ClusterStatusService, "get_statuses", return_value=[{"cluster_id": 1}])

    result = GetClusterStatusResource().perform_request(
        {"bk_tenant_id": "tenant-a", "cluster_ids": [1, 1], "timeout": 6}
    )

    assert result == [{"cluster_id": 1}]
    get_statuses.assert_called_once_with(
        bk_tenant_id="tenant-a",
        cluster_ids=[1, 1],
        timeout=6,
        include_node_details=False,
    )


def test_resource_serializer_defaults_to_no_node_details():
    serializer = GetClusterStatusResource.RequestSerializer(data={"bk_tenant_id": "system", "cluster_ids": [1]})

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["include_node_details"] is False
