from bkmonitor.nodeman_integration.v3 import compat
from monitor_web.nodeman_integration.v3 import plugin_deployment, policy
from monitor_web.plugin import nodeman_v3


class NodeManV3Backend:
    """V3 capabilities consumed by monitor-side business modules."""

    @staticmethod
    def ensure_record_ownership(**kwargs) -> None:
        policy.ensure_v3_record_ownership(**kwargs)

    @staticmethod
    def mark_config(config: dict) -> dict:
        return policy.mark_v3_config(config)

    @staticmethod
    def get_proxies(**kwargs) -> list[dict]:
        return compat.get_proxies(**kwargs)

    @staticmethod
    def get_proxies_by_biz(**kwargs) -> list[dict]:
        return compat.get_proxies_by_biz(**kwargs)

    @staticmethod
    def ipchooser_host_detail(params: dict) -> list[dict]:
        return compat.ipchooser_host_detail(params)

    @staticmethod
    def latest_enabled_plugin_version(**kwargs) -> str:
        return compat.latest_enabled_plugin_version(**kwargs)

    @staticmethod
    def plugin_exists(**kwargs) -> bool:
        return compat.plugin_exists(**kwargs)

    @staticmethod
    def plugin_search_host_status(**kwargs) -> list[dict]:
        return compat.plugin_search_host_status(**kwargs)

    @staticmethod
    def policy_service():
        return policy.NodeManV3PolicyService()

    @staticmethod
    def plugin_deployment_service(**kwargs):
        return plugin_deployment.NodeManV3PluginDeploymentService(**kwargs)

    @staticmethod
    def package_workflow_service():
        return nodeman_v3.NodeManV3PackageWorkflowService()

    @staticmethod
    def plugin_debug_service(**kwargs):
        return nodeman_v3.NodeManV3PluginDebugService(**kwargs)


node_man_v3_backend = NodeManV3Backend()
