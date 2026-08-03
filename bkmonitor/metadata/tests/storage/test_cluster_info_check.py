"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest

from metadata.models import ClusterInfo


def make_cluster(cluster_type: str, **kwargs) -> ClusterInfo:
    data = {
        "cluster_id": 1,
        "cluster_name": "test_cluster",
        "cluster_type": cluster_type,
        "domain_name": "127.0.0.1",
        "port": 9092,
        "is_default_cluster": False,
        "description": "",
    }
    data.update(kwargs)
    return ClusterInfo(**data)


def assert_standard_check_fields(result: dict):
    assert set(result) == {
        "cluster_id",
        "cluster_name",
        "cluster_type",
        "status",
        "is_connected",
        "is_available",
        "error",
        "details",
    }


def test_health_check_kafka_cluster_available(mocker):
    metadata = SimpleNamespace(brokers={1: object(), 2: object()}, topics={"topic_a": object()})
    admin_client = mocker.Mock()
    admin_client.list_topics.return_value = metadata
    admin_client_class = mocker.Mock(return_value=admin_client)
    mocker.patch.object(ClusterInfo, "_get_kafka_admin_client_class", return_value=admin_client_class)

    cluster = make_cluster(
        ClusterInfo.TYPE_KAFKA,
        username="admin",
        password="password",
        is_auth=True,
        sasl_mechanisms="SCRAM-SHA-256",
    )

    result = cluster.health_check(timeout=3)

    assert_standard_check_fields(result)
    assert result["status"] == ClusterInfo.CHECK_STATUS_AVAILABLE
    assert result["is_connected"] is True
    assert result["is_available"] is True
    assert result["error"] is None
    assert result["details"]["broker_count"] == 2
    assert result["details"]["topic_count"] == 1

    admin_conf = admin_client_class.call_args.args[0]
    assert admin_conf["bootstrap.servers"] == "127.0.0.1:9092"
    assert admin_conf["security.protocol"] == "SASL_PLAINTEXT"
    assert admin_conf["sasl.mechanisms"] == "SCRAM-SHA-256"


def test_health_check_kafka_cluster_requires_auth_info():
    cluster = make_cluster(ClusterInfo.TYPE_KAFKA, is_auth=True, username="", password="")

    result = cluster.health_check()

    assert_standard_check_fields(result)
    assert result["status"] == ClusterInfo.CHECK_STATUS_UNAVAILABLE
    assert result["is_connected"] is False
    assert result["is_available"] is False
    assert result["error"]["code"] == ClusterInfo.CHECK_ERROR_INVALID_CONFIG


def test_health_check_kafka_cluster_ignores_stale_sasl_config_when_auth_disabled(mocker):
    metadata = SimpleNamespace(brokers={1: object()}, topics={})
    admin_client = mocker.Mock()
    admin_client.list_topics.return_value = metadata
    admin_client_class = mocker.Mock(return_value=admin_client)
    mocker.patch.object(ClusterInfo, "_get_kafka_admin_client_class", return_value=admin_client_class)

    cluster = make_cluster(
        ClusterInfo.TYPE_KAFKA,
        username="stale-user",
        password="stale-password",
        is_auth=False,
        sasl_mechanisms="SCRAM-SHA-512",
        security_protocol="SASL_PLAINTEXT",
    )

    result = cluster.health_check(timeout=3)

    assert result["status"] == ClusterInfo.CHECK_STATUS_AVAILABLE
    assert result["details"]["security_protocol"] == "PLAINTEXT"
    assert result["details"]["sasl_mechanisms"] is None
    assert result["details"]["auth_enabled"] is False
    admin_conf = admin_client_class.call_args.args[0]
    assert admin_conf["security.protocol"] == "PLAINTEXT"
    assert "sasl.mechanisms" not in admin_conf
    assert "sasl.username" not in admin_conf
    assert "sasl.password" not in admin_conf


def test_health_check_kafka_cluster_keeps_ssl_transport_when_auth_disabled(mocker):
    metadata = SimpleNamespace(brokers={1: object()}, topics={})
    admin_client = mocker.Mock()
    admin_client.list_topics.return_value = metadata
    admin_client_class = mocker.Mock(return_value=admin_client)
    mocker.patch.object(ClusterInfo, "_get_kafka_admin_client_class", return_value=admin_client_class)

    cluster = make_cluster(
        ClusterInfo.TYPE_KAFKA,
        is_auth=False,
        sasl_mechanisms="SCRAM-SHA-512",
        security_protocol="SASL_SSL",
    )

    result = cluster.health_check(timeout=3)

    assert result["status"] == ClusterInfo.CHECK_STATUS_AVAILABLE
    assert result["details"]["security_protocol"] == "SSL"
    assert result["details"]["sasl_mechanisms"] is None
    admin_conf = admin_client_class.call_args.args[0]
    assert admin_conf["security.protocol"] == "SSL"
    assert "sasl.mechanisms" not in admin_conf


def test_health_check_kafka_cluster_forces_sasl_protocol_when_auth_enabled(mocker):
    metadata = SimpleNamespace(brokers={1: object()}, topics={})
    admin_client = mocker.Mock()
    admin_client.list_topics.return_value = metadata
    admin_client_class = mocker.Mock(return_value=admin_client)
    mocker.patch.object(ClusterInfo, "_get_kafka_admin_client_class", return_value=admin_client_class)

    cluster = make_cluster(
        ClusterInfo.TYPE_KAFKA,
        username="admin",
        password="password",
        is_auth=True,
        sasl_mechanisms="SCRAM-SHA-512",
        security_protocol="PLAINTEXT",
    )

    result = cluster.health_check(timeout=3)

    assert result["status"] == ClusterInfo.CHECK_STATUS_AVAILABLE
    assert result["details"]["security_protocol"] == "SASL_PLAINTEXT"
    assert result["details"]["sasl_mechanisms"] == "SCRAM-SHA-512"
    assert result["details"]["auth_enabled"] is True
    admin_conf = admin_client_class.call_args.args[0]
    assert admin_conf["security.protocol"] == "SASL_PLAINTEXT"
    assert admin_conf["sasl.mechanisms"] == "SCRAM-SHA-512"
    assert admin_conf["sasl.username"] == "admin"
    assert admin_conf["sasl.password"] == "password"


def test_health_check_rejects_non_positive_timeout():
    result = make_cluster(ClusterInfo.TYPE_KAFKA).health_check(timeout=0)

    assert_standard_check_fields(result)
    assert result["status"] == ClusterInfo.CHECK_STATUS_UNAVAILABLE
    assert result["is_connected"] is False
    assert result["is_available"] is False
    assert result["error"]["code"] == ClusterInfo.CHECK_ERROR_INVALID_CONFIG
    assert result["error"]["details"]["message"] == "timeout 必须是大于 0 的整数"


@pytest.mark.parametrize(
    ("domain_name", "expected"),
    [
        ("::1", "[::1]:9092"),
        ("[::1]", "[::1]:9092"),
        ("[::1]:9093", "[::1]:9093"),
        ("::1:9093", "[::1]:9093"),
        ("2001:db8::1", "[2001:db8::1]:9092"),
    ],
)
def test_compose_kafka_bootstrap_servers_supports_ipv6(domain_name, expected):
    cluster = make_cluster(ClusterInfo.TYPE_KAFKA, domain_name=domain_name)

    assert cluster._compose_kafka_bootstrap_servers() == expected


def test_health_check_kafka_cluster_connection_failed(mocker):
    admin_client = mocker.Mock()
    admin_client.list_topics.side_effect = RuntimeError("metadata timeout")
    mocker.patch.object(
        ClusterInfo,
        "_get_kafka_admin_client_class",
        return_value=mocker.Mock(return_value=admin_client),
    )

    result = make_cluster(ClusterInfo.TYPE_KAFKA).health_check()

    assert_standard_check_fields(result)
    assert result["status"] == ClusterInfo.CHECK_STATUS_UNAVAILABLE
    assert result["is_connected"] is False
    assert result["is_available"] is False
    assert result["error"]["code"] == ClusterInfo.CHECK_ERROR_CONNECTION_FAILED
    assert result["error"]["details"]["message"] == "metadata timeout"


@pytest.mark.parametrize("health_status", ["green", "yellow"])
def test_health_check_es_cluster_available(mocker, health_status):
    client = mocker.Mock()
    client.cluster.health.return_value = {
        "status": health_status,
        "number_of_nodes": 2,
        "number_of_data_nodes": 2,
    }
    client.cat.nodes.return_value = [
        {"name": "node-1", "ip": "127.0.0.1", "node.role": "d"},
        {"ip": "127.0.0.2", "roles": ["data", "ingest"]},
    ]
    client.cat.allocation.return_value = [
        {
            "node": "node-1",
            "host": "es-1",
            "ip": "127.0.0.1",
            "shards": "3",
            "disk.total": "1000",
            "disk.used": "400",
            "disk.avail": "600",
            "disk.percent": "40",
            "disk.indices": "300",
        },
        {
            "name": "node-2",
            "ip": "127.0.0.2",
            "shardCount": "4",
            "diskTotal": "2000",
            "diskUsed": "500",
            "diskAvail": "1500",
            "diskPercent": "25",
            "diskIndices": "450",
        },
        {"node": "UNASSIGNED", "shards": "1"},
    ]
    client_factory = mocker.patch(
        "metadata.models.storage.es_tools.get_client_by_datasource_info",
        return_value=client,
    )
    legacy_client_factory = mocker.patch("metadata.models.storage.es_tools.get_client")

    result = make_cluster(ClusterInfo.TYPE_ES).health_check(timeout=3, include_node_details=True)

    assert_standard_check_fields(result)
    assert result["status"] == ClusterInfo.CHECK_STATUS_AVAILABLE
    assert result["is_connected"] is True
    assert result["is_available"] is True
    assert result["details"]["health_status"] == health_status
    assert result["details"]["nodes"] == {"total": 2, "available": 2}
    assert result["details"]["capacity"] == {
        "total_bytes": 3000,
        "used_bytes": 900,
        "available_bytes": 2100,
        "used_percent": 30.0,
    }
    assert result["details"]["indices_store_bytes"] == 750
    assert len(result["details"]["node_details"]) == 2
    assert result["details"]["node_details"][0]["roles"] == ["d"]
    assert result["details"]["node_details"][1]["roles"] == ["data", "ingest"]
    client.cluster.health.assert_called_once_with(request_timeout=3)
    client.cat.nodes.assert_called_once_with(
        format="json",
        h="name,ip,node.role",
        params={"request_timeout": 3},
    )
    legacy_client_factory.assert_not_called()
    assert client_factory.call_args.args[0]["domain_name"] == "127.0.0.1"
    assert client_factory.call_args.args[0]["port"] == 9092


def test_health_check_es_cluster_red_is_unavailable(mocker):
    client = mocker.Mock()
    client.cluster.health.return_value = {"status": "red", "number_of_nodes": 1}
    client.cat.allocation.return_value = []
    mocker.patch("metadata.models.storage.es_tools.get_client_by_datasource_info", return_value=client)

    result = make_cluster(ClusterInfo.TYPE_ES).health_check()

    assert_standard_check_fields(result)
    assert result["status"] == ClusterInfo.CHECK_STATUS_UNAVAILABLE
    assert result["is_connected"] is True
    assert result["is_available"] is False
    assert result["error"]["code"] == ClusterInfo.CHECK_ERROR_CLUSTER_UNHEALTHY


def test_health_check_vm_cluster_available(mocker):
    response = mocker.Mock(status_code=200, text="ok")
    request = mocker.patch("metadata.models.storage.requests.get", return_value=response)

    result = make_cluster(ClusterInfo.TYPE_VM, domain_name="vm.example.com", port=8428).health_check(timeout=4)

    assert_standard_check_fields(result)
    assert result["status"] == ClusterInfo.CHECK_STATUS_AVAILABLE
    assert result["is_connected"] is True
    assert result["is_available"] is True
    assert result["details"]["url"] == "http://vm.example.com:8428/health"
    request.assert_called_once_with("http://vm.example.com:8428/health", timeout=4, verify=True)


def test_health_check_vm_cluster_http_unhealthy(mocker):
    response = mocker.Mock(status_code=503, text="not ready")
    mocker.patch("metadata.models.storage.requests.get", return_value=response)

    result = make_cluster(ClusterInfo.TYPE_VM).health_check()

    assert_standard_check_fields(result)
    assert result["status"] == ClusterInfo.CHECK_STATUS_UNAVAILABLE
    assert result["is_connected"] is True
    assert result["is_available"] is False
    assert result["error"]["code"] == ClusterInfo.CHECK_ERROR_HTTP_UNHEALTHY


def test_health_check_doris_cluster_available(mocker):
    cursor = mocker.Mock()
    cursor.__enter__ = mocker.Mock(return_value=cursor)
    cursor.__exit__ = mocker.Mock(return_value=None)
    cursor.fetchone.return_value = {"1": 1}
    cursor.fetchall.return_value = [
        {
            "BackendId": "10001",
            "Host": "doris-1",
            "Alive": "true",
            "SystemDecommissioned": "false",
            "TabletNum": "10",
            "DataUsedCapacity": "1 GB",
            "TrashUsedCapcacity": "128 MB",
            "AvailCapacity": "3 GB",
            "TotalCapacity": "4 GB",
            "UsedPct": "25%",
            "MaxDiskUsedPct": "30%",
            "RemoteUsedCapacity": "256 MB",
            "LastHeartbeat": "2026-08-03 10:00:00",
            "ErrMsg": "",
            "Version": "2.1.7",
            "NodeRole": "mix",
        },
        {
            "BackendId": "10002",
            "Host": "doris-2",
            "Alive": "false",
            "SystemDecommissioned": "false",
            "TabletNum": "20",
            "DataUsedCapacity": "2 GB",
            "TrashUsedCapacity": "0 B",
            "AvailCapacity": "2 GB",
            "TotalCapacity": "4 GB",
            "UsedPct": "50%",
            "MaxDiskUsedPct": "60%",
            "RemoteUsedCapacity": "0 B",
        },
        {
            "BackendId": "10003",
            "Host": "doris-3",
            "Alive": "true",
            "IsDecommissioned": "true",
            "AvailCapacity": "8 GB",
            "TotalCapacity": "8 GB",
        },
    ]
    connection = mocker.Mock()
    connection.cursor.return_value = cursor
    connect = mocker.patch("metadata.models.storage.pymysql.connect", return_value=connection)

    cluster = make_cluster(ClusterInfo.TYPE_DORIS, port=9030, username="root", password="password")
    result = cluster.health_check(timeout=2)

    assert_standard_check_fields(result)
    assert result["status"] == ClusterInfo.CHECK_STATUS_AVAILABLE
    assert result["is_connected"] is True
    assert result["is_available"] is True
    assert result["details"]["query"] == "SELECT 1"
    assert cursor.execute.call_count == 2
    assert cursor.execute.call_args_list[0].args == ("SELECT 1",)
    assert cursor.execute.call_args_list[1].args == ("SHOW BACKENDS",)
    assert result["details"]["nodes"] == {"total": 2, "available": 1}
    assert result["details"]["capacity"] == {
        "total_bytes": 8 * 1024**3,
        "used_bytes": 3 * 1024**3,
        "available_bytes": 5 * 1024**3,
        "used_percent": 37.5,
    }
    assert result["details"]["data_used_bytes"] == 3 * 1024**3
    assert result["details"]["trash_used_bytes"] == 128 * 1024**2
    assert result["details"]["remote_used_bytes"] == 256 * 1024**2
    assert result["details"]["tablet_count"] == 30
    assert result["details"]["max_disk_used_percent"] == 60
    assert len(result["details"]["node_details"]) == 3
    connection.close.assert_called_once()
    connect.assert_called_once()


def test_health_check_es_capacity_failure_does_not_override_health(mocker):
    client = mocker.Mock()
    client.cluster.health.return_value = {"status": "green", "number_of_data_nodes": 1}
    client.cat.allocation.side_effect = RuntimeError("allocation forbidden")
    mocker.patch("metadata.models.storage.es_tools.get_client_by_datasource_info", return_value=client)

    result = make_cluster(ClusterInfo.TYPE_ES).health_check(timeout=3)

    assert result["status"] == ClusterInfo.CHECK_STATUS_AVAILABLE
    assert result["is_available"] is True
    assert result["details"]["collection_errors"][0]["code"] == "ES_ALLOCATION_QUERY_FAILED"
    client.cat.nodes.assert_not_called()


def test_health_check_es_node_roles_failure_does_not_override_health_or_capacity(mocker):
    client = mocker.Mock()
    client.cluster.health.return_value = {"status": "green", "number_of_data_nodes": 1}
    client.cat.nodes.side_effect = RuntimeError("nodes forbidden")
    client.cat.allocation.return_value = [
        {
            "node": "node-1",
            "ip": "127.0.0.1",
            "shards": "3",
            "disk.total": "1000",
            "disk.used": "400",
            "disk.avail": "600",
        }
    ]
    mocker.patch("metadata.models.storage.es_tools.get_client_by_datasource_info", return_value=client)

    result = make_cluster(ClusterInfo.TYPE_ES).health_check(timeout=3, include_node_details=True)

    assert result["status"] == ClusterInfo.CHECK_STATUS_AVAILABLE
    assert result["is_available"] is True
    assert result["details"]["capacity"]["total_bytes"] == 1000
    assert result["details"]["node_details"][0]["roles"] == []
    assert result["details"]["collection_errors"][0]["code"] == "ES_NODES_QUERY_FAILED"


def test_health_check_doris_backend_failure_does_not_override_connection(mocker):
    cursor = mocker.Mock()
    cursor.__enter__ = mocker.Mock(return_value=cursor)
    cursor.__exit__ = mocker.Mock(return_value=None)
    cursor.fetchone.return_value = {"1": 1}
    cursor.execute.side_effect = [None, RuntimeError("access denied")]
    connection = mocker.Mock()
    connection.cursor.return_value = cursor
    mocker.patch("metadata.models.storage.pymysql.connect", return_value=connection)

    result = make_cluster(ClusterInfo.TYPE_DORIS, port=9030).health_check(timeout=2)

    assert result["status"] == ClusterInfo.CHECK_STATUS_AVAILABLE
    assert result["is_available"] is True
    assert result["details"]["collection_errors"][0]["code"] == "DORIS_BACKENDS_QUERY_FAILED"


@pytest.mark.parametrize("cluster_type", [ClusterInfo.TYPE_REDIS, ClusterInfo.TYPE_INFLUXDB, ClusterInfo.TYPE_ARGUS])
def test_health_check_unsupported_cluster_type(cluster_type):
    result = make_cluster(cluster_type).health_check()

    assert_standard_check_fields(result)
    assert result["status"] == ClusterInfo.CHECK_STATUS_UNSUPPORTED
    assert result["is_connected"] is False
    assert result["is_available"] is False
    assert result["error"]["code"] == ClusterInfo.CHECK_ERROR_UNSUPPORTED_CLUSTER_TYPE
