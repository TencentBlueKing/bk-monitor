"""存储集群运行状态查询服务。"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from django.db import close_old_connections

from metadata.models.storage import ClusterInfo


logger = logging.getLogger(__name__)


def _empty_nodes() -> dict[str, int | None]:
    return {"total": None, "available": None}


def _empty_capacity() -> dict[str, int | float | None]:
    return {
        "total_bytes": None,
        "used_bytes": None,
        "available_bytes": None,
        "used_percent": None,
    }


class ClusterStatusService:
    """批量查询并投影 ClusterInfo 的统一运行状态。"""

    MAX_CLUSTER_COUNT = 20
    MAX_WORKERS = 5
    DEFAULT_TIMEOUT = ClusterInfo.DEFAULT_CHECK_TIMEOUT
    MIN_TIMEOUT = 1
    MAX_TIMEOUT = 30

    STATUS_AVAILABLE = "available"
    STATUS_DEGRADED = "degraded"
    STATUS_UNAVAILABLE = "unavailable"
    STATUS_UNSUPPORTED = "unsupported"
    STATUS_UNKNOWN = "unknown"

    @classmethod
    def get_statuses(
        cls,
        bk_tenant_id: str,
        cluster_ids: list[int],
        timeout: int | None = None,
        include_node_details: bool = False,
    ) -> list[dict]:
        if timeout is None:
            timeout = cls.DEFAULT_TIMEOUT
        unique_cluster_ids = list(dict.fromkeys(cluster_ids))
        clusters = {
            cluster.cluster_id: cluster
            for cluster in ClusterInfo.objects.filter(
                bk_tenant_id=bk_tenant_id,
                cluster_id__in=unique_cluster_ids,
            )
        }

        statuses: dict[int, dict[str, Any]] = {}
        if clusters:
            max_workers = min(cls.MAX_WORKERS, len(clusters))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_cluster_ids = {
                    executor.submit(cls._get_status_in_worker, cluster, timeout, include_node_details): cluster_id
                    for cluster_id, cluster in clusters.items()
                }
                for future in as_completed(future_cluster_ids):
                    cluster_id = future_cluster_ids[future]
                    try:
                        statuses[cluster_id] = future.result()
                    except Exception as error:  # pylint: disable=broad-except
                        logger.exception("query cluster status failed, cluster_id->[%s]", cluster_id)
                        statuses[cluster_id] = cls._build_collection_failed_status(clusters[cluster_id], error)

        return [
            statuses.get(cluster_id) or cls._build_not_found_status(cluster_id) for cluster_id in unique_cluster_ids
        ]

    @classmethod
    def _get_status_in_worker(
        cls,
        cluster: ClusterInfo,
        timeout: int,
        include_node_details: bool,
    ) -> dict[str, Any]:
        """在线程任务边界清理 Django 连接，避免连接跨任务残留。"""

        cls._close_old_connections()
        try:
            return cls.get_status(cluster, timeout, include_node_details)
        finally:
            cls._close_old_connections()

    @staticmethod
    def _close_old_connections() -> None:
        """以 best-effort 方式清理线程中的 Django 数据库连接。"""

        try:
            close_old_connections()
        except Exception:  # pylint: disable=broad-except
            logger.debug("close old database connections failed", exc_info=True)

    @classmethod
    def get_status(cls, cluster: ClusterInfo, timeout: int, include_node_details: bool = False) -> dict[str, Any]:
        try:
            health_check_kwargs: dict[str, Any] = {"timeout": timeout}
            if include_node_details:
                health_check_kwargs["include_node_details"] = True
            health_result = cluster.health_check(**health_check_kwargs)
        except Exception as error:  # health_check 已有兜底，此处防止未来实现异常破坏整批请求
            logger.exception("ClusterInfo.health_check unexpectedly failed, cluster_id->[%s]", cluster.cluster_id)
            return cls._build_collection_failed_status(cluster, error)

        details = dict(health_result.get("details") or {})
        nodes = cls._normalize_nodes(details.pop("nodes", None))
        capacity = cls._normalize_capacity(details.pop("capacity", None))
        details = cls._normalize_details(
            cluster.cluster_type,
            details,
            include_node_details=include_node_details,
        )
        status, is_available, error = cls._project_status(
            cluster=cluster,
            health_result=health_result,
            nodes=nodes,
        )
        return {
            "cluster_id": cluster.cluster_id,
            "cluster_name": cluster.cluster_name,
            "display_name": cluster.display_name,
            "cluster_type": cluster.cluster_type,
            "status": status,
            "is_connected": bool(health_result.get("is_connected")),
            "is_available": is_available,
            "nodes": nodes,
            "capacity": capacity,
            "details": details,
            "error": error,
        }

    @classmethod
    def _project_status(
        cls,
        cluster: ClusterInfo,
        health_result: dict[str, Any],
        nodes: dict[str, int | None],
    ) -> tuple[str, bool, dict[str, Any] | None]:
        status = health_result.get("status") or cls.STATUS_UNKNOWN
        is_available = bool(health_result.get("is_available"))
        error = health_result.get("error")

        if status == ClusterInfo.CHECK_STATUS_UNSUPPORTED:
            return cls.STATUS_UNSUPPORTED, False, error
        if status != ClusterInfo.CHECK_STATUS_AVAILABLE:
            return cls.STATUS_UNAVAILABLE, False, error

        details = health_result.get("details") or {}
        if cluster.cluster_type == ClusterInfo.TYPE_ES:
            health_status = str(details.get("health_status") or "").lower()
            if health_status == "yellow":
                return cls.STATUS_DEGRADED, True, error
            if health_status == "red":
                return cls.STATUS_UNAVAILABLE, False, error

        if cluster.cluster_type == ClusterInfo.TYPE_DORIS:
            collection_errors = details.get("collection_errors") or []
            if any(
                isinstance(collection_error, dict) and collection_error.get("code") == "DORIS_BACKENDS_QUERY_FAILED"
                for collection_error in collection_errors
            ):
                return cls.STATUS_DEGRADED, True, error

            total_nodes = nodes["total"]
            available_nodes = nodes["available"]
            if total_nodes is not None and available_nodes is not None:
                if total_nodes == 0 or available_nodes == 0:
                    return (
                        cls.STATUS_UNAVAILABLE,
                        False,
                        error
                        or {
                            "code": ClusterInfo.CHECK_ERROR_CLUSTER_UNHEALTHY,
                            "message": "Doris 集群无可用后端节点",
                            "details": nodes,
                        },
                    )
                if available_nodes < total_nodes:
                    return cls.STATUS_DEGRADED, True, error

        return cls.STATUS_AVAILABLE, is_available, error

    @staticmethod
    def _normalize_nodes(nodes: Any) -> dict[str, int | None]:
        result = _empty_nodes()
        if isinstance(nodes, dict):
            result.update({key: nodes.get(key) for key in result})
        return result

    @staticmethod
    def _normalize_capacity(capacity: Any) -> dict[str, int | float | None]:
        result = _empty_capacity()
        if isinstance(capacity, dict):
            result.update({key: capacity.get(key) for key in result})
        return result

    @classmethod
    def _normalize_details(
        cls,
        cluster_type: str,
        details: dict[str, Any],
        include_node_details: bool = False,
    ) -> dict[str, Any]:
        collection_errors = cls._normalize_collection_errors(details.get("collection_errors"))
        if cluster_type == ClusterInfo.TYPE_ES:
            result = {
                "health_status": details.get("health_status"),
                "number_of_nodes": details.get("number_of_nodes"),
                "active_shards": details.get("active_shards"),
                "initializing_shards": details.get("initializing_shards"),
                "relocating_shards": details.get("relocating_shards"),
                "unassigned_shards": details.get("unassigned_shards"),
                "indices_store_bytes": details.get("indices_store_bytes"),
                "collection_errors": collection_errors,
            }
            if include_node_details:
                result["node_details"] = cls._normalize_es_node_details(details.get("node_details"))
            return result
        if cluster_type == ClusterInfo.TYPE_DORIS:
            result = {
                "data_used_bytes": details.get("data_used_bytes"),
                "trash_used_bytes": details.get("trash_used_bytes"),
                "remote_used_bytes": details.get("remote_used_bytes"),
                "tablet_count": details.get("tablet_count"),
                "max_disk_used_percent": details.get("max_disk_used_percent"),
                "collection_errors": collection_errors,
            }
            if include_node_details:
                result["node_details"] = cls._normalize_doris_node_details(details.get("node_details"))
            return result
        if cluster_type == ClusterInfo.TYPE_KAFKA:
            return {
                "bootstrap_servers": details.get("bootstrap_servers"),
                "broker_count": details.get("broker_count"),
                "topic_count": details.get("topic_count"),
                "security_protocol": details.get("security_protocol"),
                "sasl_mechanisms": details.get("sasl_mechanisms"),
                "auth_enabled": details.get("auth_enabled"),
                "collection_errors": collection_errors,
            }
        if cluster_type == ClusterInfo.TYPE_VM:
            return {
                "url": details.get("url"),
                "status_code": details.get("status_code"),
                "response": details.get("response"),
                "collection_errors": collection_errors,
            }
        return {}

    @classmethod
    def _normalize_es_node_details(cls, node_details: Any) -> list[dict[str, Any]]:
        if not isinstance(node_details, list):
            return []
        return [
            {
                "name": node.get("name"),
                "host": node.get("host"),
                "ip": node.get("ip"),
                "roles": cls._normalize_string_list(node.get("roles")),
                "shard_count": node.get("shard_count"),
                "capacity": cls._normalize_capacity(node.get("capacity")),
                "indices_store_bytes": node.get("indices_store_bytes"),
            }
            for node in node_details
            if isinstance(node, dict)
        ]

    @classmethod
    def _normalize_doris_node_details(cls, node_details: Any) -> list[dict[str, Any]]:
        if not isinstance(node_details, list):
            return []
        return [
            {
                "backend_id": node.get("backend_id"),
                "host": node.get("host"),
                "alive": node.get("alive"),
                "decommissioned": node.get("decommissioned"),
                "tablet_count": node.get("tablet_count"),
                "capacity": cls._normalize_capacity(node.get("capacity")),
                "data_used_bytes": node.get("data_used_bytes"),
                "trash_used_bytes": node.get("trash_used_bytes"),
                "remote_used_bytes": node.get("remote_used_bytes"),
                "max_disk_used_percent": node.get("max_disk_used_percent"),
                "last_heartbeat": node.get("last_heartbeat"),
                "error_message": node.get("error_message") or "",
                "version": node.get("version"),
                "node_role": node.get("node_role"),
            }
            for node in node_details
            if isinstance(node, dict)
        ]

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, list | tuple | set):
            return [str(item) for item in value if item not in (None, "")]
        return [item.strip() for item in str(value).split(",") if item.strip()]

    @staticmethod
    def _normalize_collection_errors(errors: Any) -> list[dict[str, Any]]:
        if not isinstance(errors, list):
            return []
        results = []
        for error in errors:
            if not isinstance(error, dict):
                continue
            error_details = error.get("details") if isinstance(error.get("details"), dict) else {}
            results.append(
                {
                    "component": error.get("component"),
                    "code": error.get("code"),
                    "message": error.get("message"),
                    "details": {
                        "type": error_details.get("type"),
                        "message": error_details.get("message"),
                    },
                }
            )
        return results

    @classmethod
    def _build_not_found_status(cls, cluster_id: int) -> dict[str, Any]:
        return {
            "cluster_id": cluster_id,
            "cluster_name": None,
            "display_name": None,
            "cluster_type": None,
            "status": cls.STATUS_UNKNOWN,
            "is_connected": False,
            "is_available": False,
            "nodes": _empty_nodes(),
            "capacity": _empty_capacity(),
            "details": {},
            "error": {
                "code": "CLUSTER_NOT_FOUND",
                "message": f"找不到指定的集群配置: cluster_id={cluster_id}",
                "details": {"cluster_id": cluster_id},
            },
        }

    @classmethod
    def _build_collection_failed_status(cls, cluster: ClusterInfo, error: Exception) -> dict[str, Any]:
        return {
            "cluster_id": cluster.cluster_id,
            "cluster_name": cluster.cluster_name,
            "display_name": cluster.display_name,
            "cluster_type": cluster.cluster_type,
            "status": cls.STATUS_UNAVAILABLE,
            "is_connected": False,
            "is_available": False,
            "nodes": _empty_nodes(),
            "capacity": _empty_capacity(),
            "details": {},
            "error": {
                "code": "STATUS_COLLECTION_FAILED",
                "message": "集群状态查询失败",
                "details": {"type": error.__class__.__name__, "message": str(error)},
            },
        }
