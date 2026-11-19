"""Resolve the Kafka chosen by the log platform without provisioning resources."""

from django.conf import settings
from rest_framework.exceptions import ValidationError


def resolve_clustering_kafka(bk_tenant_id: str, cluster_id: int) -> dict:
    from metadata.models import ClusterInfo
    from metadata.models.data_link.constants import BKBASE_NAMESPACE_BK_LOG, DataLinkKind
    from metadata.models.data_link.data_link_configs import ClusterConfig

    try:
        cluster = ClusterInfo.objects.get(
            bk_tenant_id=bk_tenant_id,
            cluster_id=cluster_id,
            cluster_type=ClusterInfo.TYPE_KAFKA,
            registered_to_bkbase=True,
        )
        channel = ClusterConfig.objects.get(
            bk_tenant_id=bk_tenant_id,
            namespace=BKBASE_NAMESPACE_BK_LOG,
            name=cluster.cluster_name,
            kind=DataLinkKind.KAFKACHANNEL.value,
        )
    except (ClusterInfo.DoesNotExist, ClusterConfig.DoesNotExist):
        raise ValidationError("Kafka 集群或已同步的 KafkaChannel 不存在") from None
    # KafkaChannel currently supports plaintext and SASL plaintext only. Never
    # return an SSL connection which the other end would silently downgrade.
    protocol = cluster.security_protocol or ("SASL_PLAINTEXT" if cluster.is_auth else "PLAINTEXT")
    if protocol not in {"PLAINTEXT", "SASL_PLAINTEXT"} or any(
        (
            cluster.is_ssl_verify,
            cluster.ssl_certificate_authorities,
            cluster.ssl_certificate,
            cluster.ssl_certificate_key,
        )
    ):
        raise ValidationError("当前 KafkaChannel 尚不支持此 Kafka TLS 配置")
    # Use the successfully applied payload, not a ClusterInfo edit which has
    # not reached BKBase yet. Both consumers then use the same host/auth data.
    spec = (channel.origin_config or {}).get("spec", {})
    sasl = (spec.get("auth") or {}).get("sasl") or {}
    if not spec.get("host") or type(spec.get("port")) is not int or not 1 <= spec["port"] <= 65535:
        raise ValidationError("KafkaChannel 尚未完成同步")
    enabled = sasl.get("enabled") is True
    connection = {
        "bootstrap.servers": f"{spec['host']}:{spec['port']}",
        "security.protocol": "SASL_PLAINTEXT" if enabled else "PLAINTEXT",
    }
    if enabled:
        if not all(sasl.get(k) for k in ("username", "password", "mechanism")):
            raise ValidationError("KafkaChannel 认证信息不完整")
        connection.update(
            {"sasl.username": sasl["username"], "sasl.password": sasl["password"], "sasl.mechanism": sasl["mechanism"]}
        )
    return {
        "cluster_id": cluster.cluster_id,
        "kafka_resource": {
            "kind": "KafkaChannel",
            "namespace": channel.namespace,
            "name": channel.name,
            **({"tenant": bk_tenant_id} if settings.ENABLE_MULTI_TENANT_MODE else {}),
        },
        "connection": connection,
    }
