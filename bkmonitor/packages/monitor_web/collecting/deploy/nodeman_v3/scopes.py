from constants.cmdb import TargetNodeType, TargetObjectType
from core.drf_resource import api

from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3PayloadError


class CollectDeployPolicyScopeBuilder:
    """Preserve the user's target expression; NodeMan expands its current members."""

    def __init__(self, *, cmdb=None):
        self.cmdb = cmdb or api.cmdb

    def build(self, collect_config, deployment) -> list[dict]:
        granularities = {TargetObjectType.HOST: "host", TargetObjectType.SERVICE: "service_instance"}
        try:
            granularity = granularities[collect_config.target_object_type]
        except KeyError as error:
            raise NodeManV3PayloadError("Kubernetes collection must keep using K8sInstaller") from error
        node_type = deployment.target_node_type
        nodes = deployment.target_nodes
        if not isinstance(nodes, list) or not nodes or any(not isinstance(node, dict) for node in nodes):
            raise NodeManV3PayloadError("collection scope requires non-empty target nodes")

        scope = {"granularity": granularity, "bk_biz_id": collect_config.bk_biz_id}
        if node_type == TargetNodeType.INSTANCE:
            if granularity == "host":
                scope["instance_ids"] = self._host_ids(nodes, bk_biz_id=collect_config.bk_biz_id)
            else:
                scope["instance_ids"] = sorted(
                    {self._id(node.get("service_instance_id", node.get("bk_inst_id"))) for node in nodes}
                )
        elif node_type == TargetNodeType.TOPO:
            paths = set()
            for node in nodes:
                obj_id = node.get("bk_obj_id")
                if not isinstance(obj_id, str) or not obj_id:
                    raise NodeManV3PayloadError("topology target requires bk_obj_id")
                paths.add((obj_id, self._id(node.get("bk_inst_id"))))
            scope["paths"] = [{"topo_obj_id": obj_id, "topo_inst_id": inst_id} for obj_id, inst_id in sorted(paths)]
        elif node_type in {TargetNodeType.SERVICE_TEMPLATE, TargetNodeType.SET_TEMPLATE}:
            key = "service_template_ids" if node_type == TargetNodeType.SERVICE_TEMPLATE else "set_template_ids"
            scope[key] = sorted({self._id(node.get("bk_inst_id")) for node in nodes})
        elif node_type == TargetNodeType.DYNAMIC_GROUP:
            if granularity != "host":
                raise NodeManV3PayloadError("NodeMan dynamic_group scope only supports host targets")
            if any(not isinstance(node.get("bk_inst_id"), str) or not node["bk_inst_id"] for node in nodes):
                raise NodeManV3PayloadError("dynamic group requires a non-empty string bk_inst_id")
            scope["dynamic_group_ids"] = sorted({node["bk_inst_id"] for node in nodes})
        else:
            raise NodeManV3PayloadError(f"unsupported target node type: {node_type}")
        return [{"type": node_type.lower(), "scope": scope}]

    def _host_ids(self, nodes, *, bk_biz_id):
        host_ids = {self._id(node["bk_host_id"]) for node in nodes if node.get("bk_host_id") is not None}
        ip_nodes = [node for node in nodes if node.get("bk_host_id") is None]
        if ip_nodes:
            requested = set()
            for node in ip_nodes:
                ip = node.get("ip") or node.get("bk_target_ip")
                if not isinstance(ip, str) or not ip:
                    raise NodeManV3PayloadError("host instance requires bk_host_id or ip")
                requested.add((ip, node.get("bk_cloud_id", 0)))
            hosts = self.cmdb.get_host_by_ip(
                bk_biz_id=bk_biz_id,
                ips=[{"ip": ip, "bk_cloud_id": cloud_id} for ip, cloud_id in requested],
            )
            matched = {}
            for host in hosts:
                key = (host.bk_host_innerip, host.bk_cloud_id)
                if key in matched and matched[key] != host.bk_host_id:
                    raise NodeManV3PayloadError("host IP resolves to multiple CMDB hosts")
                matched[key] = host.bk_host_id
            if not requested <= matched.keys():
                raise NodeManV3PayloadError("some selected host IPs could not be resolved to CMDB host IDs")
            host_ids.update(self._id(matched[key]) for key in requested)
        return sorted(host_ids)

    @staticmethod
    def _id(value) -> int:
        if isinstance(value, bool) or not isinstance(value, int | str):
            raise NodeManV3PayloadError("CMDB target ID must be a positive integer")
        try:
            result = int(value)
        except ValueError as error:
            raise NodeManV3PayloadError("CMDB target ID must be a positive integer") from error
        if result <= 0:
            raise NodeManV3PayloadError("CMDB target ID must be a positive integer")
        return result
