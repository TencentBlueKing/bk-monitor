"""Cluster-owned inspection context; no SaaS collector or ownership lookup is needed."""

from dataclasses import dataclass
from typing import Any

from apps.exceptions import ValidationError
from apps.log_admin_resource.k8s_inspection import safe_spec_projection, sha256_json
from apps.log_admin_resource.k8s_inspection_client import K8sInspectionClient
from apps.log_databus.constants import ContainerCollectorType


@dataclass
class ClusterInspectionContext:
    bcs_cluster_id: str
    config: dict[str, Any]
    collector_config_id: None = None
    bk_biz_id: None = None
    is_active: bool = True

    @property
    def bk_data_id(self):
        return self.config["spec"].get("dataId") or None

    @property
    def collector_config_name(self):
        return self.config["metadata"]["name"]

    @property
    def binding(self):
        metadata = self.config["metadata"]
        return {
            "namespace": metadata["namespace"],
            "name": metadata["name"],
            "uid": metadata["uid"],
            "spec_sha256": sha256_json(self.config["spec"]),
            "bk_env": (metadata.get("labels") or {}).get("bk_env"),
        }

    @property
    def expected(self):
        spec = self.config["spec"]
        return [
            {
                "name": self.collector_config_name,
                "namespace": self.binding["namespace"],
                "container_config_id": None,
                "collector_type": spec["logConfigType"],
                "spec": spec,
                "safe_spec": safe_spec_projection(spec),
            }
        ]


def load_cluster_context(cluster_id: str, reference: dict[str, Any]) -> ClusterInspectionContext:
    config = K8sInspectionClient(cluster_id=cluster_id).read_bklog_config(reference["namespace"], reference["name"])
    metadata = config.get("metadata") or {}
    spec = config.get("spec") or {}
    if (metadata.get("namespace"), metadata.get("name")) != (reference["namespace"], reference["name"]):
        raise ValidationError("bklog_config_identity_mismatch")
    if not metadata.get("uid") or metadata.get("deletionTimestamp"):
        raise ValidationError("bklog_config_unavailable")
    if spec.get("logConfigType") not in {
        ContainerCollectorType.NODE,
        ContainerCollectorType.CONTAINER,
        ContainerCollectorType.STDOUT,
    }:
        raise ValidationError("bklog_config_type_unsupported")
    data_id = spec.get("dataId")
    if data_id is not None and (isinstance(data_id, bool) or not isinstance(data_id, int) or data_id < 0):
        raise ValidationError("bklog_config_data_id_invalid")
    context = ClusterInspectionContext(cluster_id, config)
    if "uid" in reference and context.binding != reference:
        raise ValidationError("bklog_config_changed_after_dispatch")
    return context
