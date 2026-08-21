from dataclasses import dataclass

from monitor_web.plugin.constant import PluginType


@dataclass(frozen=True)
class CollectRecipeResource:
    role: str
    identity_key: str
    plugin_name: str


@dataclass(frozen=True)
class CollectDeploymentRecipe:
    plugin_type: str
    resources: tuple[CollectRecipeResource, ...]


def build_collect_recipe(*, plugin_type: str, collect_config_id: int, plugin_name: str) -> CollectDeploymentRecipe:
    if plugin_type == PluginType.K8S:
        raise ValueError("K8S collection must keep using K8sInstaller")

    prefix = f"collect:{collect_config_id}"
    resources = []
    if plugin_type == PluginType.EXPORTER:
        resources.append(
            CollectRecipeResource(
                role="plugin_instance",
                identity_key=f"{prefix}:plugin:{plugin_name}",
                plugin_name=plugin_name,
            )
        )
    resources.append(
        CollectRecipeResource(
            role="bkmonitorbeat_subconfig",
            identity_key=f"{prefix}:bkmonitorbeat:{plugin_name}",
            plugin_name="bkmonitorbeat",
        )
    )
    return CollectDeploymentRecipe(plugin_type=plugin_type, resources=tuple(resources))
