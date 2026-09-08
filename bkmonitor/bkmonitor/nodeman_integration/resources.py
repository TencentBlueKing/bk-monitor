from django.db import models


class NodeManResourceType(models.TextChoices):
    """Stable monitor-side identities managed through NodeMan."""

    COLLECT_CONFIG = "COLLECT_CONFIG", "采集配置"
    APM_PLATFORM_CONFIG = "APM_PLATFORM_CONFIG", "APM 平台配置"
    APM_APPLICATION_CONFIG = "APM_APPLICATION_CONFIG", "APM 应用配置"
    APM_LOG_TRACE_CONFIG = "APM_LOG_TRACE_CONFIG", "APM 行日志配置"
    CUSTOM_REPORT = "CUSTOM_REPORT", "自定义上报"
    PING_SERVER = "PING_SERVER", "拨测服务"
    PROXY_PLUGIN_DEPLOYMENT = "PROXY_PLUGIN_DEPLOYMENT", "Proxy 插件部署"
    OFFICIAL_PLUGIN_DEPLOYMENT = "OFFICIAL_PLUGIN_DEPLOYMENT", "官方插件部署"
    MONITOR_PLUGIN = "MONITOR_PLUGIN", "监控插件"


def _identity_component(components: dict, name: str) -> str:
    if name not in components:
        raise ValueError(f"{name} is required")
    value = components[name]
    if value is None or value == "":
        raise ValueError(f"{name} is required")
    return str(value)


def build_nodeman_resource_key(resource_type: str, **components) -> str:
    """Build the stable business identity required by the V3 binding contract."""

    resource_type = NodeManResourceType(resource_type)
    if resource_type == NodeManResourceType.APM_PLATFORM_CONFIG:
        if components:
            raise ValueError(f"unexpected identity components: {sorted(components)}")
        return "platform"

    if resource_type in {
        NodeManResourceType.COLLECT_CONFIG,
        NodeManResourceType.APM_APPLICATION_CONFIG,
        NodeManResourceType.APM_LOG_TRACE_CONFIG,
    }:
        allowed = {"object_id"}
        key = _identity_component(components, "object_id")
    elif resource_type == NodeManResourceType.CUSTOM_REPORT:
        allowed = {"data_id"}
        key = f"data_id:{_identity_component(components, 'data_id')}"
    elif resource_type in {NodeManResourceType.PING_SERVER, NodeManResourceType.PROXY_PLUGIN_DEPLOYMENT}:
        allowed = {"bk_cloud_id", "bk_host_id", "plugin_name"}
        key = (
            f"cloud:{_identity_component(components, 'bk_cloud_id')}:"
            f"host:{_identity_component(components, 'bk_host_id')}:"
            f"plugin:{_identity_component(components, 'plugin_name')}"
        )
    elif resource_type == NodeManResourceType.OFFICIAL_PLUGIN_DEPLOYMENT:
        allowed = {"bk_host_id", "plugin_name"}
        key = (
            f"host:{_identity_component(components, 'bk_host_id')}:"
            f"plugin:{_identity_component(components, 'plugin_name')}"
        )
    else:
        allowed = {"plugin_id"}
        key = _identity_component(components, "plugin_id")

    unexpected = set(components) - allowed
    if unexpected:
        raise ValueError(f"unexpected identity components: {sorted(unexpected)}")
    if len(key) > 255:
        raise ValueError("resource key exceeds 255 characters")
    return key
