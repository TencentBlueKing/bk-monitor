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
    client.cluster.health.return_value = {"status": health_status, "number_of_nodes": 2}
    mocker.patch("metadata.models.storage.es_tools.get_client", return_value=client)

    result = make_cluster(ClusterInfo.TYPE_ES).health_check(timeout=3)

    assert_standard_check_fields(result)
    assert result["status"] == ClusterInfo.CHECK_STATUS_AVAILABLE
    assert result["is_connected"] is True
    assert result["is_available"] is True
    assert result["details"]["health_status"] == health_status
    client.cluster.health.assert_called_once_with(request_timeout=3)


def test_health_check_es_cluster_red_is_unavailable(mocker):
    client = mocker.Mock()
    client.cluster.health.return_value = {"status": "red", "number_of_nodes": 1}
    mocker.patch("metadata.models.storage.es_tools.get_client", return_value=client)

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
    cursor.execute.assert_called_once_with("SELECT 1")
    connection.close.assert_called_once()
    connect.assert_called_once()


@pytest.mark.parametrize("cluster_type", [ClusterInfo.TYPE_REDIS, ClusterInfo.TYPE_INFLUXDB, ClusterInfo.TYPE_ARGUS])
def test_health_check_unsupported_cluster_type(cluster_type):
    result = make_cluster(cluster_type).health_check()

    assert_standard_check_fields(result)
    assert result["status"] == ClusterInfo.CHECK_STATUS_UNSUPPORTED
    assert result["is_connected"] is False
    assert result["is_available"] is False
    assert result["error"]["code"] == ClusterInfo.CHECK_ERROR_UNSUPPORTED_CLUSTER_TYPE
