from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Callable, Sequence
from typing import cast

from bkmonitor.nodeman_integration.v3.client import (
    NodeManV3HTTPClient,
    NodeManV3RequestContext,
    NodeManV3UnknownResultError,
)
from bkmonitor.nodeman_integration.v3.client.deploy_policy import DeployPolicyClient
from bkmonitor.nodeman_integration.v3.exceptions import NodeManV3PayloadError
from monitor_web.collecting.constant import OperationType
from monitor_web.models.node_man import NodeManIntegrationBinding
from monitor_web.plugin.constant import ParamMode, PluginType
from monitor_web.plugin.manager import PluginManagerFactory
from monitor_web.plugin.manager.process import ProcessPluginManager

from .validation import NodeManV3CapabilityBlocked
from .scopes import CollectDeployPolicyScopeBuilder


class CollectDeployPolicyPayloadBuilder:
    """Translate the existing plugin-manager step contract into NodeMan V3 deploy-policy specs."""

    def __init__(self, *, step_builder: Callable | None = None, scope_builder=None):
        self.step_builder = step_builder or self._build_existing_steps
        self.scope_builder = scope_builder or CollectDeployPolicyScopeBuilder()

    def build(self, collect_config) -> dict:
        deployment = collect_config.deployment_config
        remote_collecting_host = deployment.remote_collecting_host
        if remote_collecting_host and collect_config.plugin.plugin_type != PluginType.EXPORTER:
            raise NodeManV3CapabilityBlocked(
                "only remote Exporter collection has a confirmed DeployPolicy projection contract"
            )
        if collect_config.last_operation == OperationType.STOP:
            raise NodeManV3CapabilityBlocked("collection enable/disable requires the DeployPolicy reverse protocol")

        scopes = self.scope_builder.build(collect_config, deployment)
        steps = self.step_builder(collect_config, deployment)
        placement_host_ids = None
        if remote_collecting_host:
            placement_host_ids = self.scope_builder._host_ids(
                [remote_collecting_host], bk_biz_id=collect_config.bk_biz_id
            )
        specs = self._build_specs(collect_config, steps, placement_host_ids=placement_host_ids)
        if not specs:
            raise NodeManV3PayloadError("collect deployment produced no deploy-policy specs")

        return {
            "name": self.policy_name(collect_config),
            "description": f"bk-monitor collect config {collect_config.pk}",
            "enabled": True,
            "specs": specs,
            "scopes": scopes,
        }

    @staticmethod
    def policy_name(collect_config) -> str:
        return f"bkm-collect-{collect_config.pk}"

    @staticmethod
    def fingerprint(payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def update_payload(deploy_policy_id: int, create_payload: dict) -> dict:
        return {
            "deploy_policies": [
                {
                    "deploy_policy_id": deploy_policy_id,
                    "meta": {
                        "name": create_payload["name"],
                        "description": create_payload["description"],
                    },
                    "enabled": create_payload["enabled"],
                    "specs": create_payload["specs"],
                    "scopes": create_payload["scopes"],
                }
            ],
            "fields": {"meta": True, "enabled": True, "specs": True, "scopes": True},
        }

    @staticmethod
    def _build_existing_steps(collect_config, deployment) -> list[dict]:
        plugin = collect_config.plugin
        plugin_manager = PluginManagerFactory.get_manager(plugin=plugin)
        config_params = copy.deepcopy(deployment.params)
        dms_insert_params = CollectDeployPolicyPayloadBuilder._dms_insert_params(deployment, config_params)

        if plugin.plugin_type == PluginType.PROCESS:
            plugin_manager = cast(ProcessPluginManager, plugin_manager)
            config_params["collector"].update(
                {
                    "taskid": str(collect_config.pk),
                    "namespace": plugin.plugin_id,
                    "period": f"{config_params['collector']['period']}s",
                    "timeout": f"{config_params['collector'].get('timeout', 60)}",
                    "max_timeout": f"{config_params['collector'].get('timeout', 60)}",
                    "dataid": str(plugin_manager.perf_data_id(collect_config.bk_biz_id)),
                    "port_dataid": str(plugin_manager.port_data_id(collect_config.bk_biz_id)),
                    "match_pattern": config_params["process"]["match_pattern"],
                    "process_name": config_params["process"].get("process_name", ""),
                    "exclude_pattern": config_params["process"]["exclude_pattern"],
                    "port_detect": config_params["process"]["port_detect"],
                    "extract_pattern": config_params["process"].get("extract_pattern", ""),
                    "pid_path": config_params["process"]["pid_path"],
                    "labels": CollectDeployPolicyPayloadBuilder._common_labels(collect_config),
                    "tags": config_params["collector"].get("tag", {}),
                }
            )
        else:
            labels = CollectDeployPolicyPayloadBuilder._common_labels(collect_config)
            labels["$body"].update(
                {
                    "bk_target_service_instance_id": "{{ cmdb_instance.service.id }}",
                    **dms_insert_params,
                }
            )
            config_params["collector"].update(
                {
                    "task_id": str(collect_config.pk),
                    "bk_biz_id": str(collect_config.bk_biz_id),
                    "config_name": plugin.plugin_id,
                    "config_version": "1.0",
                    "namespace": plugin.plugin_id,
                    "period": str(config_params["collector"]["period"]),
                    "timeout": f"{config_params['collector'].get('timeout', 60)}",
                    "max_timeout": f"{config_params['collector'].get('timeout', 60)}",
                    "dataid": str(collect_config.data_id),
                    "labels": labels,
                }
            )
        config_params["subscription_id"] = deployment.subscription_id
        return plugin_manager.get_deploy_steps_params(
            deployment.plugin_version,
            config_params,
            deployment.target_nodes,
        )

    @staticmethod
    def _dms_insert_params(deployment, config_params: dict) -> dict:
        result = {}
        for param in deployment.plugin_version.config.config_json:
            if param["mode"] != ParamMode.DMS_INSERT:
                continue
            for key, value in config_params["plugin"].get(param["name"], {}).items():
                if param["type"] == "host":
                    result[key] = "{{ " + f"cmdb_instance.host.{value} or '{value}' or '-'" + " }}"
                elif param["type"] == "service":
                    result[key] = "{{ " + f"cmdb_instance.service.labels['{value}']  or '{value}' or '-'" + " }}"
                elif param["type"] == "custom":
                    result[key] = value
        return result

    @staticmethod
    def _common_labels(collect_config) -> dict:
        return {
            "$for": "cmdb_instance.scope",
            "$item": "scope",
            "$body": {
                "bk_target_host_id": "{{ cmdb_instance.host.bk_host_id }}",
                "bk_target_ip": "{{ cmdb_instance.host.bk_host_innerip }}",
                "bk_target_cloud_id": (
                    "{{ cmdb_instance.host.bk_cloud_id[0].id "
                    "if cmdb_instance.host.bk_cloud_id is iterable and "
                    "cmdb_instance.host.bk_cloud_id is not string "
                    "else cmdb_instance.host.bk_cloud_id }}"
                ),
                "bk_target_topo_level": "{{ scope.bk_obj_id }}",
                "bk_target_topo_id": "{{ scope.bk_inst_id }}",
                "bk_target_service_category_id": (
                    "{{ cmdb_instance.service.service_category_id | default('', true) }}"
                ),
                "bk_collect_config_id": collect_config.pk,
            },
        }

    @classmethod
    def _build_specs(
        cls,
        collect_config,
        steps: Sequence[dict],
        *,
        placement_host_ids: Sequence[int] | None = None,
    ) -> list[dict]:
        specs = []
        remote_projection = bool(placement_host_ids)
        for step in steps:
            config = step.get("config", {})
            plugin_name = config.get("plugin_name")
            if not plugin_name:
                continue
            context = step.get("params", {}).get("context", {})
            if plugin_name == "bkmonitorbeat":
                if cls._contains_step_data_reference(context):
                    raise NodeManV3CapabilityBlocked(
                        "deploy-policy context cannot resolve the V2 step_data cross-step reference"
                    )
                details = [
                    {
                        "template_name": template["name"],
                        "content": template.get("content", ""),
                        "is_main_config": False,
                    }
                    for template in config.get("config_templates", ())
                    if template.get("name")
                ]
                if not details:
                    raise NodeManV3PayloadError("bkmonitorbeat deploy-policy has no config template")
                spec_type = (
                    "project_plugin_config_template_to_hosts"
                    if remote_projection
                    else "specify_plugin_sub_config_template"
                )
                specs.append(
                    {
                        "type": spec_type,
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
                raise NodeManV3PayloadError(f"plugin version is missing for {plugin_name}")
            if any("content" in template for template in config.get("config_templates", ())):
                raise NodeManV3CapabilityBlocked(
                    f"dynamic config file templates for isolated plugin {plugin_name} "
                    "have no confirmed target identity contract"
                )
            if collect_config.plugin.plugin_type in {PluginType.EXPORTER, PluginType.JMX}:
                spec_type = "project_plugin_pkg_to_hosts" if remote_projection else "specify_plugin_pkg"
                param = {
                    "plugin_pkg_name": plugin_name,
                    "version": version,
                    "custom_config_context": context,
                }
                if remote_projection:
                    param["placement_host_ids"] = list(placement_host_ids or ())
                specs.append(
                    {
                        "type": spec_type,
                        "param": param,
                    }
                )
            else:
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

    @classmethod
    def _contains_step_data_reference(cls, value) -> bool:
        if isinstance(value, str):
            return "step_data." in value
        if isinstance(value, dict):
            return any(cls._contains_step_data_reference(item) for item in value.values())
        if isinstance(value, list | tuple):
            return any(cls._contains_step_data_reference(item) for item in value)
        return False


class NodeManV3DeployPolicyGateway:
    def __init__(self, *, client=None, payload_builder=None):
        self.client = client or DeployPolicyClient(NodeManV3HTTPClient())
        self.payload_builder = payload_builder or CollectDeployPolicyPayloadBuilder()

    def ensure_policy(
        self, binding: NodeManIntegrationBinding, payload: dict, *, context: NodeManV3RequestContext
    ) -> dict:
        deploy_policy_id = binding.node_man_deploy_policy_id or self._recover_policy_id(
            payload["name"], context=context
        )
        if deploy_policy_id:
            self.client.update(
                self.payload_builder.update_payload(deploy_policy_id, payload),
                context=context,
            )
        else:
            result = self.client.create(payload, context=context)
            deploy_policy_id = result.get("deploy_policy_id") if isinstance(result, dict) else None
            if not deploy_policy_id:
                raise NodeManV3UnknownResultError("NodeMan V3 deploy-policy create response has no deploy_policy_id")
        self._persist_policy_id(binding, int(deploy_policy_id), self.payload_builder.fingerprint(payload))
        return self.execute_policy(binding, context=context)

    def execute_policy(self, binding, *, context: NodeManV3RequestContext) -> dict:
        deploy_policy_id = binding.node_man_deploy_policy_id
        if not deploy_policy_id:
            raise NodeManV3PayloadError("collection has no NodeMan deploy policy to execute")
        result = self.client.execute({"deploy_policy_id": int(deploy_policy_id)}, context=context)
        trigger_id = result.get("trigger_id") if isinstance(result, dict) else None
        if not trigger_id:
            raise NodeManV3UnknownResultError("NodeMan V3 deploy-policy execute response has no trigger_id")
        return {"trigger_id": str(trigger_id)}

    def _recover_policy_id(self, name: str, *, context: NodeManV3RequestContext) -> int | None:
        result = self.client.list(
            {
                "page": {"offset": 0, "limit": 2},
                "exact_include_conditions": {"deploy_policy_name": [name]},
            },
            context=context,
        )
        items = result.get("items") if isinstance(result, dict) else None
        if not isinstance(items, list):
            raise NodeManV3PayloadError("NodeMan deploy-policy list response has no items list")
        exact = [item for item in items if item.get("meta", {}).get("name") == name]
        if len(exact) > 1:
            raise NodeManV3PayloadError(f"multiple deploy policies found for stable name {name}")
        return int(exact[0]["deploy_policy_id"]) if exact else None

    @staticmethod
    def _persist_policy_id(binding: NodeManIntegrationBinding, deploy_policy_id: int, fingerprint: str) -> None:
        if binding.node_man_deploy_policy_id and binding.node_man_deploy_policy_id != deploy_policy_id:
            raise NodeManV3UnknownResultError(
                f"binding {binding.pk} is already bound to deploy policy {binding.node_man_deploy_policy_id}"
            )
        updated = NodeManIntegrationBinding.objects.filter(
            pk=binding.pk,
            generation=binding.generation,
            node_man_deploy_policy_id=binding.node_man_deploy_policy_id,
        ).update(node_man_deploy_policy_id=deploy_policy_id, node_man_policy_fingerprint=fingerprint)
        if not updated:
            raise NodeManV3UnknownResultError(f"binding {binding.pk} changed while its policy was submitted")
        binding.node_man_deploy_policy_id = deploy_policy_id
        binding.node_man_policy_fingerprint = fingerprint
