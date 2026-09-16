from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from django.db import transaction

from core.drf_resource import api

from bkmonitor.nodeman_integration.v3.compat import latest_enabled_plugin_version
from bkmonitor.nodeman_integration.v3.client import (
    NodeManV3HTTPClient,
    NodeManV3RequestContext,
    NodeManV3UnknownResultError,
)
from bkmonitor.nodeman_integration.v3.client.host import HostClient
from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3PayloadError
from monitor_web.collecting.deploy.nodeman_v3.deploy_policy import NodeManV3DeployPolicyGateway
from monitor_web.models.node_man import (
    MonitorNodeManOperation,
    MonitorNodeManWorkflow,
    NodeManBindingState,
    NodeManIntegrationBinding,
    NodeManOperationStatus,
    NodeManOperationType,
    NodeManResourceType,
    NodeManV3ResultState,
)
from monitor_web.nodeman_integration.v3.operation import (
    NodeManExecutionLeaseConflict,
    NodeManV3OperationService,
    PreparedTargetOperation,
)
from monitor_web.nodeman_integration.v3.status import TERMINAL_OPERATION_STATUSES


NODE_MAN_BACKEND_CONFIG_KEY = "node_man_backend"
NODE_MAN_V3_CONFIG_VALUE = "v3"


def ensure_v3_record_ownership(
    *,
    config: dict | None,
    persisted_identifier: int | None,
    resource: str,
    binding_identity: dict | None = None,
) -> None:
    """Do not reinterpret a persisted subscription identifier as an unrelated V3 binding."""

    if not persisted_identifier:
        return
    if (config or {}).get(NODE_MAN_BACKEND_CONFIG_KEY) != NODE_MAN_V3_CONFIG_VALUE:
        raise NodeManV3PayloadError(f"{resource} still references a V2 subscription in a V3-only environment")
    if binding_identity is None:
        return

    binding_id = NodeManIntegrationBinding.objects.filter(**binding_identity).values_list("pk", flat=True).first()
    if binding_id != persisted_identifier:
        raise NodeManV3PayloadError(
            f"{resource} references unexpected V3 binding {persisted_identifier}; expected {binding_id or '<missing>'}"
        )


def mark_v3_config(config: dict) -> dict:
    return {**config, NODE_MAN_BACKEND_CONFIG_KEY: NODE_MAN_V3_CONFIG_VALUE}


class SubscriptionDeployPolicyPayloadBuilder:
    """Translate the shared V2 subscription shape used outside collecting into a V3 policy."""

    ENABLED = True

    def build(
        self,
        *,
        name: str,
        description: str,
        bk_biz_id: int,
        scope: dict,
        steps: list[dict],
        resolved_scopes: list[dict] | None = None,
    ) -> dict:
        specs = self._build_specs(steps)
        if not specs:
            raise NodeManV3PayloadError("subscription compatibility policy produced no deploy specs")
        return {
            "name": name,
            "description": description,
            "enabled": self.ENABLED,
            "specs": specs,
            "scopes": resolved_scopes or [self._build_scope(bk_biz_id=bk_biz_id, scope=scope)],
        }

    @staticmethod
    def fingerprint(payload: dict) -> str:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode()).hexdigest()

    @classmethod
    def update_payload(cls, deploy_policy_id: int, create_payload: dict) -> dict:
        return {
            "deploy_policies": [
                {
                    "deploy_policy_id": deploy_policy_id,
                    "meta": {
                        "name": create_payload["name"],
                        "description": create_payload["description"],
                    },
                    "enabled": cls.ENABLED,
                    "specs": create_payload["specs"],
                    "scopes": create_payload["scopes"],
                }
            ],
            "fields": {"meta": True, "enabled": True, "specs": True, "scopes": True},
        }

    @classmethod
    def _build_scope(cls, *, bk_biz_id: int, scope: dict) -> dict:
        object_type = str(scope.get("object_type") or "").upper()
        granularity = {"HOST": "host", "SERVICE": "service_instance"}.get(object_type)
        if granularity is None:
            raise NodeManV3PayloadError(f"unsupported subscription object_type: {object_type or '<empty>'}")

        node_type = str(scope.get("node_type") or "").upper()
        nodes = scope.get("nodes") or []
        if not isinstance(nodes, list) or not nodes or any(not isinstance(node, dict) for node in nodes):
            raise NodeManV3PayloadError("subscription scope requires non-empty nodes")

        result = {"granularity": granularity, "bk_biz_id": int(scope.get("bk_biz_id", bk_biz_id))}
        if node_type == "INSTANCE":
            key = "bk_host_id" if granularity == "host" else "service_instance_id"
            fallback = "bk_inst_id"
            result["instance_ids"] = sorted({cls._positive_id(node.get(key, node.get(fallback))) for node in nodes})
        elif node_type == "TOPO":
            paths = {(str(node.get("bk_obj_id") or ""), cls._positive_id(node.get("bk_inst_id"))) for node in nodes}
            if any(not obj_id for obj_id, _inst_id in paths):
                raise NodeManV3PayloadError("topology scope requires bk_obj_id")
            result["paths"] = [{"topo_obj_id": obj_id, "topo_inst_id": inst_id} for obj_id, inst_id in sorted(paths)]
        elif node_type in {"SET_TEMPLATE", "SERVICE_TEMPLATE"}:
            key = "set_template_ids" if node_type == "SET_TEMPLATE" else "service_template_ids"
            result[key] = sorted({cls._positive_id(node.get("bk_inst_id")) for node in nodes})
        elif node_type == "DYNAMIC_GROUP" and granularity == "host":
            dynamic_group_ids = {str(node.get("bk_inst_id") or node.get("dynamic_group_id") or "") for node in nodes}
            if "" in dynamic_group_ids:
                raise NodeManV3PayloadError("dynamic group scope requires bk_inst_id")
            result["dynamic_group_ids"] = sorted(dynamic_group_ids)
        else:
            raise NodeManV3PayloadError(
                f"unsupported subscription scope: object_type={object_type}, node_type={node_type}"
            )
        return {"type": node_type.lower(), "scope": result}

    @staticmethod
    def _build_specs(steps: list[dict]) -> list[dict]:
        specs = []
        for step in steps:
            if str(step.get("type") or "").upper() != "PLUGIN":
                raise NodeManV3PayloadError("only PLUGIN subscription steps can be converted to DeployPolicy")
            config = step.get("config") or {}
            plugin_name = config.get("plugin_name")
            if not plugin_name:
                raise NodeManV3PayloadError("subscription plugin step requires plugin_name")
            context = (step.get("params") or {}).get("context") or {}
            templates = config.get("config_templates") or []
            if templates:
                details = []
                for template in templates:
                    template_name = template.get("name")
                    if not template_name:
                        raise NodeManV3PayloadError(f"subscription config template for {plugin_name} requires name")
                    details.append({"template_name": template_name, "is_main_config": False})
                specs.append(
                    {
                        "type": "specify_plugin_sub_config_template",
                        "param": {
                            "plugin_name": plugin_name,
                            "config_files_detail": details,
                            "custom_config_context": context,
                        },
                    }
                )
                continue

            version = config.get("plugin_version")
            if not version:
                raise NodeManV3PayloadError(f"subscription plugin step for {plugin_name} requires plugin_version")
            specs.append(
                {
                    "type": "specify_plugin",
                    "param": {
                        "plugin_name": plugin_name,
                        "version": version,
                        "custom_config_context": context,
                    },
                }
            )
        return specs

    @staticmethod
    def _positive_id(value) -> int:
        if isinstance(value, bool):
            raise NodeManV3PayloadError("scope instance ID must be a positive integer")
        try:
            result = int(value)
        except (TypeError, ValueError) as error:
            raise NodeManV3PayloadError("scope instance ID must be a positive integer") from error
        if result <= 0:
            raise NodeManV3PayloadError("scope instance ID must be a positive integer")
        return result


class NodeManV3HostScopeResolver:
    """Resolve host scopes for NodeMan policies and plugin prerequisites."""

    PAGE_SIZE = 500

    def __init__(self, *, client=None, cmdb=None):
        self.client = client or HostClient(NodeManV3HTTPClient())
        self.cmdb = cmdb or api.cmdb

    def resolve(
        self,
        *,
        owner_bk_tenant_id: str,
        execution_bk_tenant_id: str,
        bk_biz_id: int,
        scope: dict,
        payload_builder: SubscriptionDeployPolicyPayloadBuilder,
    ) -> list[dict]:
        object_type = str(scope.get("object_type") or "").upper()
        node_type = str(scope.get("node_type") or "").upper()
        if object_type != "HOST" or node_type != "INSTANCE":
            return [payload_builder._build_scope(bk_biz_id=bk_biz_id, scope=scope)]

        nodes = scope.get("nodes") or []
        if not isinstance(nodes, list) or not nodes or any(not isinstance(node, dict) for node in nodes):
            raise NodeManV3PayloadError("subscription scope requires non-empty nodes")
        host_ids = sorted({payload_builder._positive_id(node.get("bk_host_id")) for node in nodes})
        hosts = self._list_hosts(
            host_ids=host_ids,
            execution_bk_tenant_id=execution_bk_tenant_id,
            bk_biz_id=bk_biz_id,
        )
        biz_to_host_ids: dict[int, set[int]] = {}
        resolved_host_ids = set()
        for host in hosts:
            host_id = payload_builder._positive_id(host.get("bk_host_id"))
            host_biz_id = payload_builder._positive_id((host.get("info") or {}).get("bk_biz_id"))
            resolved_host_ids.add(host_id)
            biz_to_host_ids.setdefault(host_biz_id, set()).add(host_id)

        missing_host_ids = sorted(set(host_ids) - resolved_host_ids)
        if missing_host_ids:
            raise NodeManV3PayloadError(
                f"NodeMan V3 host query did not resolve host IDs for owner tenant "
                f"{owner_bk_tenant_id}: {missing_host_ids}"
            )
        return [
            {
                "type": "instance",
                "scope": {
                    "granularity": "host",
                    "bk_biz_id": host_biz_id,
                    "instance_ids": sorted(biz_to_host_ids[host_biz_id]),
                },
            }
            for host_biz_id in sorted(biz_to_host_ids)
        ]

    def resolve_current_host_ids(
        self,
        *,
        bk_tenant_id: str,
        bk_biz_id: int,
        scope: dict,
        payload_builder: SubscriptionDeployPolicyPayloadBuilder,
    ) -> list[int]:
        """Expand the current members of a host scope for host-level plugin policies."""

        object_type = str(scope.get("object_type") or "").upper()
        node_type = str(scope.get("node_type") or "").upper()
        nodes = scope.get("nodes") or []
        if object_type != "HOST":
            raise NodeManV3PayloadError("plugin prerequisite requires a host collection scope")
        if not isinstance(nodes, list) or not nodes or any(not isinstance(node, dict) for node in nodes):
            raise NodeManV3PayloadError("subscription scope requires non-empty nodes")

        if node_type == "INSTANCE":
            return sorted({payload_builder._positive_id(node.get("bk_host_id")) for node in nodes})

        if node_type == "TOPO":
            topo_nodes: dict[str, list[int]] = {}
            for node in nodes:
                object_id = str(node.get("bk_obj_id") or "")
                if not object_id:
                    raise NodeManV3PayloadError("topology scope requires bk_obj_id")
                topo_nodes.setdefault(object_id, []).append(payload_builder._positive_id(node.get("bk_inst_id")))
            hosts = self.cmdb.get_host_by_topo_node(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                topo_nodes=topo_nodes,
            )
            return self._host_ids(hosts, payload_builder=payload_builder)

        if node_type in {"SET_TEMPLATE", "SERVICE_TEMPLATE"}:
            template_ids = sorted({payload_builder._positive_id(node.get("bk_inst_id")) for node in nodes})
            hosts = self.cmdb.get_host_by_template(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                bk_obj_id=node_type,
                template_ids=template_ids,
            )
            return self._host_ids(hosts, payload_builder=payload_builder)

        if node_type == "DYNAMIC_GROUP":
            dynamic_group_ids = {str(node.get("bk_inst_id") or node.get("dynamic_group_id") or "") for node in nodes}
            if "" in dynamic_group_ids:
                raise NodeManV3PayloadError("dynamic group scope requires bk_inst_id")
            groups = self.cmdb.search_dynamic_group(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=bk_biz_id,
                bk_obj_id="host",
                dynamic_group_ids=sorted(dynamic_group_ids),
                with_instance_id=True,
            )
            resolved_group_ids = {str(group.get("id") or "") for group in groups}
            missing_group_ids = sorted(dynamic_group_ids - resolved_group_ids)
            if missing_group_ids:
                raise NodeManV3PayloadError(f"CMDB did not resolve dynamic group IDs: {missing_group_ids}")
            return sorted(
                {
                    payload_builder._positive_id(host_id)
                    for group in groups
                    for host_id in group.get("instance_ids") or []
                }
            )

        raise NodeManV3PayloadError(f"unsupported host scope for plugin prerequisite: {node_type or '<empty>'}")

    @staticmethod
    def _host_ids(hosts, *, payload_builder: SubscriptionDeployPolicyPayloadBuilder) -> list[int]:
        return sorted(
            {
                payload_builder._positive_id(
                    host.get("bk_host_id") if isinstance(host, dict) else getattr(host, "bk_host_id", None)
                )
                for host in hosts
            }
        )

    def _list_hosts(self, *, host_ids: list[int], execution_bk_tenant_id: str, bk_biz_id: int) -> list[dict]:
        context = NodeManV3RequestContext(
            bk_tenant_id=execution_bk_tenant_id,
            bk_biz_id=bk_biz_id,
        )
        hosts = []
        for offset in range(0, len(host_ids), self.PAGE_SIZE):
            batch = host_ids[offset : offset + self.PAGE_SIZE]
            result = self.client.list(
                {
                    "page": {"offset": 0, "limit": len(batch)},
                    "only_count": False,
                    "exact_include_conditions": {"bk_host_id": batch},
                },
                context=context,
            )
            if not isinstance(result, dict):
                raise NodeManV3PayloadError("NodeMan V3 host query returned an invalid response")
            hosts.extend(result.get("items") or [])
        return hosts


@dataclass(frozen=True)
class DeployPolicySubmission:
    binding_id: int
    operation_id: str
    prepared: bool


class NodeManV3PolicyService:
    """Persist and submit a stable DeployPolicy for a non-collection monitor resource."""

    def __init__(
        self,
        *,
        payload_builder=None,
        gateway=None,
        operation_service=None,
        scope_resolver=None,
        plugin_version_resolver=None,
    ):
        self.payload_builder = payload_builder or SubscriptionDeployPolicyPayloadBuilder()
        self.gateway = gateway or NodeManV3DeployPolicyGateway(payload_builder=self.payload_builder)
        self.operation_service = operation_service or NodeManV3OperationService(terminal_handler=lambda *_args: True)
        self.scope_resolver = scope_resolver or NodeManV3HostScopeResolver()
        self.plugin_version_resolver = plugin_version_resolver or latest_enabled_plugin_version

    def ensure(
        self,
        *,
        resource_type: str,
        resource_key: str,
        owner_bk_tenant_id: str,
        execution_bk_tenant_id: str,
        bk_biz_id: int,
        policy_name: str,
        description: str,
        scope: dict,
        steps: list[dict],
        force: bool = False,
        resolved_scopes: list[dict] | None = None,
    ) -> DeployPolicySubmission:
        if not transaction.get_connection().in_atomic_block:
            raise RuntimeError(
                "NodeMan V3 policy preparation must run inside transaction.atomic so business state "
                "is committed before the external write"
            )
        if resolved_scopes is None:
            resolved_scopes = self.scope_resolver.resolve(
                owner_bk_tenant_id=owner_bk_tenant_id,
                execution_bk_tenant_id=execution_bk_tenant_id,
                bk_biz_id=bk_biz_id,
                scope=scope,
                payload_builder=self.payload_builder,
            )
        payload = self.payload_builder.build(
            name=policy_name,
            description=description,
            bk_biz_id=bk_biz_id,
            scope=scope,
            steps=steps,
            resolved_scopes=resolved_scopes,
        )
        self._ensure_plugin_prerequisites(
            owner_bk_tenant_id=owner_bk_tenant_id,
            execution_bk_tenant_id=execution_bk_tenant_id,
            bk_biz_id=bk_biz_id,
            steps=steps,
            scope=scope,
        )
        binding, _created = NodeManIntegrationBinding.objects.get_or_create(
            resource_type=resource_type,
            resource_key=resource_key,
            owner_bk_tenant_id=owner_bk_tenant_id,
            execution_bk_tenant_id=execution_bk_tenant_id,
            bk_biz_id=bk_biz_id,
        )
        prepared = self._prepare(binding, payload, force=force)
        if prepared is None:
            return DeployPolicySubmission(binding.pk, "", False)
        transaction.on_commit(lambda: self._dispatch(prepared, payload))
        return DeployPolicySubmission(binding.pk, str(prepared.operation.pk), True)

    def _ensure_plugin_prerequisites(
        self,
        *,
        owner_bk_tenant_id: str,
        execution_bk_tenant_id: str,
        bk_biz_id: int,
        steps: list[dict],
        scope: dict,
    ) -> None:
        plugin_versions = {}
        for step in steps:
            config = step.get("config") or {}
            if not config.get("config_templates"):
                continue
            plugin_name = config.get("plugin_name")
            plugin_version = config.get("plugin_version")
            if not plugin_version:
                raise NodeManV3PayloadError(
                    f"subscription config step for {plugin_name or '<missing>'} requires plugin_version"
                )
            if plugin_version == "latest":
                plugin_version = self.plugin_version_resolver(
                    bk_tenant_id=execution_bk_tenant_id,
                    plugin_name=plugin_name,
                )
            previous_version = plugin_versions.setdefault(plugin_name, plugin_version)
            if previous_version != plugin_version:
                raise NodeManV3PayloadError(
                    f"subscription config steps require conflicting versions for plugin {plugin_name}"
                )

        if not plugin_versions:
            return

        host_ids = self.scope_resolver.resolve_current_host_ids(
            bk_tenant_id=execution_bk_tenant_id,
            bk_biz_id=bk_biz_id,
            scope=scope,
            payload_builder=self.payload_builder,
        )
        if not host_ids:
            return
        from monitor_web.nodeman_integration.v3.plugin_deployment import NodeManV3PluginDeploymentService

        deployment_service = NodeManV3PluginDeploymentService(policy_service=self)
        for plugin_name, plugin_version in sorted(plugin_versions.items()):
            # A template-config spec is config-only in NodeMan V3. Keep plugin installation as one
            # host-level desired-state policy so overlapping config policies cannot compete for it.
            deployment_service.ensure_hosts(
                resource_type=NodeManResourceType.OFFICIAL_PLUGIN_DEPLOYMENT,
                owner_bk_tenant_id=owner_bk_tenant_id,
                execution_bk_tenant_id=execution_bk_tenant_id,
                bk_biz_id=bk_biz_id,
                plugin_name=plugin_name,
                plugin_version=plugin_version,
                bk_host_ids=host_ids,
            )

    def _prepare(self, binding, payload: dict, *, force: bool) -> PreparedTargetOperation | None:
        fingerprint = self.payload_builder.fingerprint(payload)
        with transaction.atomic():
            locked = NodeManIntegrationBinding.objects.select_for_update().get(pk=binding.pk)
            if locked.state != NodeManBindingState.ACTIVE:
                raise NodeManV3PayloadError("NodeMan V3 policy binding must be active")
            if locked.operations.filter(result_state=NodeManV3ResultState.WRITE_RESULT_UNKNOWN).exists():
                raise NodeManV3UnknownResultError("an earlier NodeMan V3 policy write is unresolved")
            active = locked.operations.exclude(status__in=TERMINAL_OPERATION_STATUSES).order_by("-created_at").first()
            if active and not force and active.request_summary.get("deploy_policy_fingerprint") == fingerprint:
                return None
            if active:
                raise NodeManExecutionLeaseConflict("a NodeMan V3 policy operation has not reached a terminal state")
            latest = (
                locked.operations.filter(operation_type=NodeManOperationType.RECONCILE).order_by("-created_at").first()
            )
            if (
                not force
                and locked.node_man_deploy_policy_id
                and locked.node_man_policy_fingerprint == fingerprint
                and latest
                and latest.status == NodeManOperationStatus.SUCCESS
            ):
                return None

            locked.advance_generation(expected_generation=locked.generation)
            operation = MonitorNodeManOperation.objects.create(
                binding=locked,
                operation_type=NodeManOperationType.RECONCILE,
                generation=locked.generation,
                request_summary={"deploy_policy_fingerprint": fingerprint, "scopes": payload["scopes"]},
                status=NodeManOperationStatus.DISPATCHING,
            )
            workflow = MonitorNodeManWorkflow.objects.create(
                monitor_operation=operation,
                batch_index=0,
                target_summary={"scopes": payload["scopes"]},
            )
        return PreparedTargetOperation(operation, (workflow,), ())

    def _dispatch(self, prepared: PreparedTargetOperation, payload: dict) -> None:
        operation = prepared.operation
        self.operation_service.dispatch_batches(
            binding=operation.binding,
            operation_type=operation.operation_type,
            generation=operation.generation,
            batches=[{"target_summary": {"scopes": payload["scopes"]}, "target_count": 0}],
            request_summary=operation.request_summary,
            submit_batch=lambda _batch, *, context: self.gateway.ensure_policy(
                operation.binding,
                payload,
                context=context,
            ),
            prepared_operation=operation,
            prepared_workflows=prepared.workflows,
        )
