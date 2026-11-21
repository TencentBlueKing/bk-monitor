"""Backend Kafka resolution never creates resources or falls back across tenants."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rest_framework.exceptions import ValidationError

from metadata.service.clustering_kafka import resolve_clustering_kafka


@pytest.fixture
def cluster(monkeypatch, settings):
    settings.ENABLE_MULTI_TENANT_MODE = True

    class MissingCluster(Exception):
        pass

    class MissingChannel(Exception):
        pass

    ClusterInfo = SimpleNamespace(TYPE_KAFKA="kafka", DoesNotExist=MissingCluster, objects=SimpleNamespace(get=Mock()))
    ClusterConfig = SimpleNamespace(DoesNotExist=MissingChannel, objects=SimpleNamespace(get=Mock()))
    monkeypatch.setitem(sys.modules, "metadata.models", SimpleNamespace(ClusterInfo=ClusterInfo))
    monkeypatch.setitem(
        sys.modules,
        "metadata.models.data_link.constants",
        SimpleNamespace(
            BKBASE_NAMESPACE_BK_LOG="bklog",
            DataLinkKind=SimpleNamespace(KAFKACHANNEL=SimpleNamespace(value="KafkaChannel")),
        ),
    )
    monkeypatch.setitem(
        sys.modules, "metadata.models.data_link.data_link_configs", SimpleNamespace(ClusterConfig=ClusterConfig)
    )
    value = SimpleNamespace(
        bk_tenant_id="tenant-a",
        cluster_id=42,
        cluster_name="log-kafka",
        domain_name="kafka.test",
        port=9092,
        is_auth=True,
        security_protocol="SASL_PLAINTEXT",
        username="log-reader",
        password="test-only",
        sasl_mechanisms="SCRAM-SHA-512",
        is_ssl_verify=False,
        ssl_certificate_authorities="",
        ssl_certificate="",
        ssl_certificate_key="",
    )
    get = Mock(return_value=value)
    channel = Mock(
        return_value=SimpleNamespace(
            namespace="bklog",
            name="log-kafka",
            origin_config={
                "spec": {
                    "host": "kafka.test",
                    "port": 9092,
                    "auth": {
                        "sasl": {
                            "enabled": True,
                            "username": "log-reader",
                            "password": "test-only",
                            "mechanism": "SCRAM-SHA-512",
                        }
                    },
                }
            },
        )
    )
    monkeypatch.setattr(ClusterInfo.objects, "get", get)
    monkeypatch.setattr(ClusterConfig.objects, "get", channel)
    return value, get, channel


def test_cluster_id_selects_connection_and_registered_channel(cluster):
    value, get, channel = cluster
    result = resolve_clustering_kafka("tenant-a", 42)
    assert result["connection"] == {
        "bootstrap.servers": "kafka.test:9092",
        "security.protocol": "SASL_PLAINTEXT",
        "sasl.username": "log-reader",
        "sasl.password": "test-only",
        "sasl.mechanism": "SCRAM-SHA-512",
    }
    assert result["kafka_resource"] == {
        "kind": "KafkaChannel",
        "tenant": "tenant-a",
        "namespace": "bklog",
        "name": "log-kafka",
    }
    get.assert_called_once_with(bk_tenant_id="tenant-a", cluster_id=42, cluster_type="kafka", registered_to_bkbase=True)
    channel.assert_called_once_with(bk_tenant_id="tenant-a", namespace="bklog", name="log-kafka", kind="KafkaChannel")


def test_plaintext_does_not_send_unused_credentials(cluster):
    value, _, channel = cluster
    value.is_auth, value.security_protocol = False, "PLAINTEXT"
    channel.return_value.origin_config["spec"].pop("auth")
    assert resolve_clustering_kafka("tenant-a", 42)["connection"] == {
        "bootstrap.servers": "kafka.test:9092",
        "security.protocol": "PLAINTEXT",
    }


@pytest.mark.parametrize("target", ["cluster", "channel"])
def test_missing_or_foreign_resource_does_not_provision(cluster, monkeypatch, target):
    _, get, channel = cluster
    selected = get if target == "cluster" else channel
    selected.side_effect = (
        sys.modules["metadata.models"].ClusterInfo.DoesNotExist()
        if target == "cluster"
        else sys.modules["metadata.models.data_link.data_link_configs"].ClusterConfig.DoesNotExist()
    )
    with pytest.raises(ValidationError, match="KafkaChannel"):
        resolve_clustering_kafka("other-tenant", 42)
    assert get.call_args.kwargs["bk_tenant_id"] == "other-tenant"


@pytest.mark.parametrize("change", [{"security_protocol": "SASL_SSL"}, {"is_ssl_verify": True}])
def test_unsupported_tls_is_explicit(cluster, change):
    value, _, _ = cluster
    for key, item in change.items():
        setattr(value, key, item)
    with pytest.raises(ValidationError):
        resolve_clustering_kafka("tenant-a", 42)


@pytest.mark.parametrize("change", ["unsynced", "password", "mechanism"])
def test_incomplete_applied_channel_is_not_used(cluster, change):
    _, _, channel = cluster
    if change == "unsynced":
        channel.return_value.origin_config = {}
    else:
        channel.return_value.origin_config["spec"]["auth"]["sasl"].pop(change)
    with pytest.raises(ValidationError):
        resolve_clustering_kafka("tenant-a", 42)


def test_unsynced_cluster_edits_cannot_split_worker_and_databus_connection(cluster):
    value, _, _ = cluster
    value.domain_name, value.password = "not-synced.invalid", "not-synced"
    result = resolve_clustering_kafka("tenant-a", 42)
    assert result["connection"]["bootstrap.servers"] == "kafka.test:9092"
    assert result["connection"]["sasl.password"] == "test-only"


def test_single_tenant_channel_uses_bkbase_default_instead_of_metadata_system(cluster, settings):
    settings.ENABLE_MULTI_TENANT_MODE = False
    assert "tenant" not in resolve_clustering_kafka("system", 42)["kafka_resource"]
