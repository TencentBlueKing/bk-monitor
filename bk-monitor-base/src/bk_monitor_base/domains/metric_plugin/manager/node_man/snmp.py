from pathlib import Path
from typing import Any, ClassVar, final

from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.constants import PluginType
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.node_man.base import NodemanPluginManager


@final
class SNMPPluginManager(NodemanPluginManager):
    """SNMP插件管理器"""

    type: ClassVar[str] = PluginType.SNMP
    _SUB_CONFIG_NAME: ClassVar[str] = "bkmonitorbeat_prometheus_remote.conf"

    @override
    def get_supported_os_types(self) -> list[OSType]:
        """获取支持的操作系统类型"""

        return [OSType.LINUX]

    @override
    def _get_package_context(self) -> dict[str, Any]:
        """获取上下文，用于渲染插件包中的文本文件"""

        context = super()._get_package_context()
        # 端口探测能力，当 port 未配置时，默认探测 10000-65535 端口；当 port 配置了默认值时，优先探测默认值端口，再探测 10000-65535 端口
        context["port_range"] = "10000-65535"
        try:
            default_port = [x for x in self.plugin.params if x.name == "port"][0].default
            if default_port:
                context["port_range"] = f"{default_port},10000-65535"
        except Exception:
            pass
        return context

    @override
    def make_package(self, is_compress: bool = True) -> Path:
        """制作插件包
        Args:
            is_compress: 是否压缩
        Returns:
            如果不需要压缩，则返回插件包目录路径；如果需要压缩，则返回压缩包路径
        """

        return self._make_package(is_compress=is_compress)

    @override
    def _get_debug_config_context(
        self,
        collect_params: dict[str, Any],
        plugin_params: dict[str, Any],
        target_nodes: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """构建调试配置上下文
        Args:
            collect_params: 采集参数
            plugin_params: 插件参数
            target_nodes: 目标节点列表
        Returns:
            调试配置上下文
        """
        context = {
            "config.yaml": {
                "community": plugin_params.pop("community", ""),
                "security_level": plugin_params.pop("security_level", ""),
                "context_name": plugin_params.pop("context_name", ""),
                "username": plugin_params.pop("security_name", ""),
                "password": plugin_params.pop("authentication_passphrase", ""),
                "auth_protocol": plugin_params.pop("authentication_protocol", ""),
                "priv_protocol": plugin_params.pop("privacy_protocol", ""),
                "priv_password": plugin_params.pop("privacy_passphrase", ""),
            },
            "env.yaml": {
                "host": collect_params["host"],
                "port": collect_params["port"],
            },
            "bkmonitorbeat_debug.yaml": {
                "host": collect_params["host"],
                "port": collect_params["port"],
                "period": collect_params["period"],
                "target_nodes": [node["ip"] for node in target_nodes],
                "metric_url": f"{collect_params['host']}:{collect_params['port']}/snmp?target=",
            },
        }
        return context

    @override
    def get_deploy_steps_params(
        self,
        bk_biz_id: int,
        collect_task_id: int,
        bk_data_ids: dict[str, int],
        collect_params: dict[str, Any],
        plugin_params: dict[str, Any],
        target_nodes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """获取部署步骤参数
        Args:
            bk_biz_id: 蓝鲸业务ID
            collect_task_id: 采集任务ID
            bk_data_ids: 数据ID映射
            collect_params: 采集参数，如采集周期，超时时间，绑定IP/端口，可以理解为内置参数
            plugin_params: 插件参数，用户自定义的参数
            target_nodes: 采集目标节点
        Returns:
            部署步骤参数列表
        """
        # 在SNMP采集时默认使用远程采集，设置远程采集目标主机为"target_nodes", 下发采集配置文件与执行采集任务的主机为"remote_collecting_host"
        collect_params["tasks"] = []
        for node in target_nodes:
            collect_params["tasks"].append(
                {
                    "task_id": str(collect_task_id),
                    "bk_biz_id": str(bk_biz_id),
                    "dataid": bk_data_ids["bk_data_id"],
                    "period": str(collect_params["period"]),
                    "timeout": str(collect_params.get("timeout", 60)),
                    "metric_url": f"{collect_params['host']}:{collect_params['port']}/snmp?target={node['ip']}:{collect_params.get('snmp_port', '161')}",
                    "config_name": self.plugin.id,
                    "diff_metrics": collect_params.get("diff_metrics", []),
                    "labels": {
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
                            "bk_target_service_instance_id": "{{ cmdb_instance.service.id }}",
                            "bk_collect_config_id": collect_task_id,
                            # 将labels中的target_ip改成远程采集的ip
                            "bk_target_device_ip": node["ip"],
                        },
                    },
                }
            )

        steps: list[dict[str, Any]] = [
            # SNMP插件配置文件下发
            {
                "id": self.plugin.id,
                "type": "PLUGIN",
                "config": {
                    "plugin_name": self.plugin.id,
                    "plugin_version": self.plugin.version_str(),
                    "config_templates": [
                        {"name": "config.yaml", "version": str(self.plugin.version.major)},
                        {"name": "env.yaml", "version": str(self.plugin.version.major)},
                    ],
                },
                "params": {
                    "context": {
                        "community": plugin_params.pop("community", ""),
                        "security_level": plugin_params.pop("security_level", ""),
                        "context_name": plugin_params.pop("context_name", ""),
                        "username": plugin_params.pop("security_name", ""),
                        "password": plugin_params.pop("authentication_passphrase", ""),
                        "auth_protocol": plugin_params.pop("authentication_protocol", ""),
                        "priv_protocol": plugin_params.pop("privacy_protocol", ""),
                        "priv_password": plugin_params.pop("privacy_passphrase", ""),
                        "host": collect_params["host"],
                        "port": collect_params["port"],
                    }
                },
            },
            # bkmonitorbeat子配置文件
            {
                "id": self.plugin.id,
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "plugin_version": "latest",
                    "config_templates": [{"name": self._SUB_CONFIG_NAME, "version": "latest"}],
                },
                "params": {
                    "context": {
                        "host": collect_params["host"],
                        "port": collect_params["port"],
                        "snmp_port": collect_params["snmp_port"],
                        "tasks": collect_params["tasks"],
                        "config_version": "1.0",
                        "namespace": self.plugin.id,
                        "max_timeout": str(collect_params.get("timeout", 60)),
                    }
                },
            },
        ]

        return steps
