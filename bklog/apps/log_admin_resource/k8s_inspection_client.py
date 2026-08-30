"""Read-only Kubernetes transport used only by Resource Call inspections."""

from __future__ import annotations

from typing import Any

from kubernetes import client as k8s_client

from apps.utils.bcs import Bcs


K8S_API_TIMEOUT_SECONDS = 10
POD_LOG_TIMEOUT_SECONDS = 15
MAX_POD_LOG_BYTES = 5 * 1024 * 1024


def object_to_dict(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        return {str(key): object_to_dict(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [object_to_dict(item) for item in value]
    if hasattr(value, "to_dict"):
        return object_to_dict(value.to_dict())
    return object_to_dict(k8s_client.ApiClient().sanitize_for_serialization(value))


def bounded_text(value: Any, maximum: int) -> tuple[str, bool]:
    if value is None:
        return "", False
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
    encoded = text.encode("utf-8", errors="replace")
    if maximum <= 0:
        return "", bool(encoded)
    if len(encoded) <= maximum:
        return text, False
    # Dropping an incomplete leading code point keeps the returned UTF-8 byte size within the hard limit.
    return encoded[-maximum:].decode("utf-8", errors="ignore"), True


class K8sInspectionClient:
    """Expose only GET/LIST and bounded pod-log operations."""

    def __init__(self, cluster_id: str):
        self.cluster_id = cluster_id
        self.bcs = Bcs(cluster_id=cluster_id)

    def read_crd(self, name: str) -> Any:
        return self.bcs.extension_v1api.read_custom_resource_definition(
            name=name, _request_timeout=K8S_API_TIMEOUT_SECONDS
        )

    def list_bklog_configs(self, namespace: str) -> dict[str, Any]:
        return self.bcs.crd_api.list_namespaced_custom_object(
            group=self.bcs.BKLOG_CONFIG_GROUP,
            version=self.bcs.BKLOG_CONFIG_VERSION,
            namespace=namespace,
            plural=self.bcs.BKLOG_CONFIG_PLURAL,
            _request_timeout=K8S_API_TIMEOUT_SECONDS,
        )

    def read_pod(self, namespace: str, name: str) -> Any:
        return self.bcs.api_instance_core_v1.read_namespaced_pod(
            namespace=namespace, name=name, _request_timeout=K8S_API_TIMEOUT_SECONDS
        )

    def read_node(self, name: str) -> Any:
        return self.bcs.api_instance_core_v1.read_node(name=name, _request_timeout=K8S_API_TIMEOUT_SECONDS)

    def read_config_map(self, namespace: str, name: str) -> Any:
        return self.bcs.api_instance_core_v1.read_namespaced_config_map(
            namespace=namespace, name=name, _request_timeout=K8S_API_TIMEOUT_SECONDS
        )

    def read_daemon_set(self, namespace: str, name: str) -> Any:
        return self.bcs.api_instance_apps_v1.read_namespaced_daemon_set(
            namespace=namespace, name=name, _request_timeout=K8S_API_TIMEOUT_SECONDS
        )

    def list_daemon_sets(self, namespace: str | None = None) -> list[Any]:
        if namespace:
            result = self.bcs.api_instance_apps_v1.list_namespaced_daemon_set(
                namespace=namespace, _request_timeout=K8S_API_TIMEOUT_SECONDS
            )
        else:
            result = self.bcs.api_instance_apps_v1.list_daemon_set_for_all_namespaces(
                _request_timeout=K8S_API_TIMEOUT_SECONDS
            )
        result_dict = object_to_dict(result)
        return list(getattr(result, "items", None) or result_dict.get("items") or [])

    def list_pods(self, namespace: str, *, label_selector: str | None = None) -> list[Any]:
        kwargs: dict[str, Any] = {"namespace": namespace, "_request_timeout": K8S_API_TIMEOUT_SECONDS}
        if label_selector:
            kwargs["label_selector"] = label_selector
        result = self.bcs.api_instance_core_v1.list_namespaced_pod(**kwargs)
        result_dict = object_to_dict(result)
        return list(getattr(result, "items", None) or result_dict.get("items") or [])

    def list_events(self, namespace: str, pod_uid: str) -> list[Any]:
        result = self.bcs.api_instance_core_v1.list_namespaced_event(
            namespace=namespace,
            field_selector=f"involvedObject.uid={pod_uid}",
            limit=20,
            _request_timeout=K8S_API_TIMEOUT_SECONDS,
        )
        result_dict = object_to_dict(result)
        return list(getattr(result, "items", None) or result_dict.get("items") or [])

    def read_pod_log(self, namespace: str, pod_name: str, container: str, *, previous: bool) -> dict[str, Any]:
        value = self.bcs.api_instance_core_v1.read_namespaced_pod_log(
            namespace=namespace,
            name=pod_name,
            container=container,
            previous=previous,
            timestamps=True,
            limit_bytes=MAX_POD_LOG_BYTES,
            _request_timeout=POD_LOG_TIMEOUT_SECONDS,
        )
        content, truncated = bounded_text(value, MAX_POD_LOG_BYTES)
        returned_bytes = len(content.encode("utf-8", errors="replace"))
        return {
            "files": [
                {
                    "path": f"pods/log:{namespace}/{pod_name}/{container}:{'previous' if previous else 'current'}",
                    "content": content,
                    "start_offset_bytes": None,
                    "end_offset_bytes": returned_bytes,
                    "returned_size_bytes": returned_bytes,
                    "truncated": truncated,
                }
            ],
            "returned_size_bytes": returned_bytes,
            "maximum_size_bytes": MAX_POD_LOG_BYTES,
            "truncated": truncated,
            "previous": previous,
        }
