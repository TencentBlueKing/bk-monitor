import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass

from constants.cmdb import TargetNodeType, TargetObjectType
from core.drf_resource import api
from monitor_web.collecting.constant import OperationType


class CollectTargetResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedCollectTarget:
    identity_key: str
    observed_target: dict
    service_instance_id: int | None
    execution_bk_host_id: int
    remote_target: dict
    plugin_name: str
    desired_enabled: bool
    desired_revision: str

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CMDBCollectTargetResolver:
    """Resolve V3 desired targets directly from CMDB, never from a V2 NodeMan subscription."""

    def __init__(self, *, cmdb=None):
        self.cmdb = cmdb or api.cmdb

    def resolve(self, collect_config) -> tuple[ResolvedCollectTarget, ...]:
        deployment = collect_config.deployment_config
        if deployment.target_node_type == TargetNodeType.CLUSTER:
            raise CollectTargetResolutionError("K8S collection must keep using K8sInstaller")

        if collect_config.target_object_type == TargetObjectType.HOST:
            observed = self._resolve_hosts(
                bk_biz_id=collect_config.bk_biz_id,
                node_type=deployment.target_node_type,
                target_nodes=deployment.target_nodes,
            )
            targets = [self._host_target(host) for host in observed]
        elif collect_config.target_object_type == TargetObjectType.SERVICE:
            observed = self._resolve_services(
                bk_biz_id=collect_config.bk_biz_id,
                node_type=deployment.target_node_type,
                target_nodes=deployment.target_nodes,
            )
            targets = [self._service_target(service) for service in observed]
        else:
            raise CollectTargetResolutionError(
                f"unsupported target object type for NodeMan V3: {collect_config.target_object_type}"
            )

        remote_execution_host = self._resolve_remote_execution_host(
            bk_biz_id=collect_config.bk_biz_id,
            remote_collecting_host=deployment.remote_collecting_host,
        )
        desired_revision = self._desired_revision(deployment)
        desired_enabled = getattr(collect_config, "last_operation", None) != OperationType.STOP
        resolved = {}
        for identity_key, observed_target, service_instance_id, observed_host_id in targets:
            execution_host_id = remote_execution_host or observed_host_id
            target = ResolvedCollectTarget(
                identity_key=identity_key,
                observed_target=observed_target,
                service_instance_id=service_instance_id,
                execution_bk_host_id=execution_host_id,
                remote_target=observed_target if remote_execution_host else {},
                plugin_name=collect_config.plugin_id,
                desired_enabled=desired_enabled,
                desired_revision=desired_revision,
            )
            previous = resolved.get(identity_key)
            if previous and previous != target:
                raise CollectTargetResolutionError(f"conflicting CMDB records for target {identity_key}")
            resolved[identity_key] = target
        return tuple(resolved[key] for key in sorted(resolved))

    def _resolve_hosts(self, *, bk_biz_id: int, node_type: str, target_nodes: list[dict]):
        if node_type == TargetNodeType.INSTANCE:
            host_ids = sorted({int(node["bk_host_id"]) for node in target_nodes if node.get("bk_host_id")})
            ip_nodes = [
                {"ip": node.get("ip") or node.get("bk_target_ip"), "bk_cloud_id": node.get("bk_cloud_id", 0)}
                for node in target_nodes
                if not node.get("bk_host_id")
            ]
            hosts = []
            if host_ids:
                hosts.extend(self.cmdb.get_host_by_id(bk_biz_id=bk_biz_id, bk_host_ids=host_ids))
            if ip_nodes:
                if any(not node["ip"] for node in ip_nodes):
                    raise CollectTargetResolutionError("host instance target requires bk_host_id or ip")
                hosts.extend(self.cmdb.get_host_by_ip(bk_biz_id=bk_biz_id, ips=ip_nodes, search_outer_ip=True))
            return hosts

        if node_type == TargetNodeType.TOPO:
            return self.cmdb.get_host_by_topo_node(
                bk_biz_id=bk_biz_id,
                topo_nodes=self._group_topo_nodes(target_nodes),
            )

        if node_type in {TargetNodeType.SERVICE_TEMPLATE, TargetNodeType.SET_TEMPLATE}:
            return self.cmdb.get_host_by_template(
                bk_biz_id=bk_biz_id,
                bk_obj_id=node_type,
                template_ids=self._template_ids(target_nodes),
            )

        if node_type == TargetNodeType.DYNAMIC_GROUP:
            groups = self.cmdb.batch_execute_dynamic_group(
                bk_biz_id=bk_biz_id,
                ids=self._template_ids(target_nodes),
                bk_obj_id="host",
            )
            return [host for group_hosts in groups.values() for host in group_hosts]

        raise CollectTargetResolutionError(f"unsupported host target node type: {node_type}")

    def _resolve_services(self, *, bk_biz_id: int, node_type: str, target_nodes: list[dict]):
        if node_type == TargetNodeType.TOPO:
            return self.cmdb.get_service_instance_by_topo_node(
                bk_biz_id=bk_biz_id,
                topo_nodes=self._group_topo_nodes(target_nodes),
            )
        if node_type in {TargetNodeType.SERVICE_TEMPLATE, TargetNodeType.SET_TEMPLATE}:
            return self.cmdb.get_service_instance_by_template(
                bk_biz_id=bk_biz_id,
                bk_obj_id=node_type,
                template_ids=self._template_ids(target_nodes),
            )
        raise CollectTargetResolutionError(f"unsupported service target node type: {node_type}")

    def _resolve_remote_execution_host(self, *, bk_biz_id: int, remote_collecting_host: dict | None) -> int | None:
        if not remote_collecting_host:
            return None
        if remote_collecting_host.get("bk_host_id"):
            return int(remote_collecting_host["bk_host_id"])
        ip = remote_collecting_host.get("ip")
        if not ip:
            raise CollectTargetResolutionError("remote collecting host requires bk_host_id or ip")
        hosts = self.cmdb.get_host_by_ip(
            bk_biz_id=bk_biz_id,
            ips=[{"ip": ip, "bk_cloud_id": remote_collecting_host.get("bk_cloud_id", 0)}],
            search_outer_ip=True,
        )
        if len(hosts) != 1:
            raise CollectTargetResolutionError(f"remote collecting host resolved to {len(hosts)} hosts")
        return int(hosts[0].bk_host_id)

    @staticmethod
    def _group_topo_nodes(target_nodes: list[dict]) -> dict[str, list[int]]:
        grouped = defaultdict(set)
        for node in target_nodes:
            if not node.get("bk_obj_id") or node.get("bk_inst_id") is None:
                raise CollectTargetResolutionError("topology target requires bk_obj_id and bk_inst_id")
            grouped[str(node["bk_obj_id"])].add(int(node["bk_inst_id"]))
        return {key: sorted(values) for key, values in sorted(grouped.items())}

    @staticmethod
    def _template_ids(target_nodes: list[dict]) -> list:
        if any(node.get("bk_inst_id") is None for node in target_nodes):
            raise CollectTargetResolutionError("template or dynamic group target requires bk_inst_id")
        return sorted({node["bk_inst_id"] for node in target_nodes}, key=str)

    @staticmethod
    def _host_target(host):
        host_id = int(host.bk_host_id)
        return f"host:{host_id}", {"bk_host_id": host_id}, None, host_id

    @staticmethod
    def _service_target(service):
        service_instance_id = int(service.service_instance_id)
        host_id = int(service.bk_host_id)
        if not host_id:
            raise CollectTargetResolutionError(f"service instance {service_instance_id} has no execution host")
        return (
            f"service:{service_instance_id}",
            {"bk_host_id": host_id, "service_instance_id": service_instance_id},
            service_instance_id,
            host_id,
        )

    @staticmethod
    def _desired_revision(deployment) -> str:
        version = deployment.plugin_version
        payload = {
            "deployment_config_version_id": deployment.id,
            "plugin_config_version": version.config_version,
            "plugin_info_version": version.info_version,
            "params": deployment.params,
        }
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
        return f"{version.config_version}.{version.info_version}:{digest[:32]}"
