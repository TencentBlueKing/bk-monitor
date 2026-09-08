import logging
from pathlib import Path
from typing import Any, ClassVar, final

from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.constants import PluginType
from bk_monitor_base.domains.metric_plugin.errors import ParseOsTypeError, PluginParseError
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.node_man.base import NodemanPluginManager

logger = logging.getLogger(__name__)


@final
class JMXPluginManager(NodemanPluginManager):
    """JMX插件管理器"""

    type: ClassVar[str] = PluginType.JMX
    _SUB_CONFIG_NAME: ClassVar[str] = "bkmonitorbeat_prometheus.conf"
    config_files: ClassVar[list[str]] = ["config.yaml.tpl", "env.yaml.tpl"]

    @override
    def get_supported_os_types(self) -> list[OSType]:
        """获取支持的操作系统类型"""

        return [OSType.LINUX, OSType.LINUX_AARCH64, OSType.WINDOWS]

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

        ssl_enabled = plugin_params.get("ssl_enabled", "false")
        context = {
            "config.yaml": {
                "username": plugin_params.pop("username"),
                "password": plugin_params.pop("password"),
                "jmx_url": plugin_params.pop("jmx_url"),
                "ssl_enabled": ssl_enabled,
            },
            "env.yaml": {
                "host": collect_params["host"],
                "port": collect_params["port"],
                "ssl_enabled": ssl_enabled,
                "ssl_trust_store": plugin_params.get("ssl_trust_store", ""),
                "ssl_trust_store_password": plugin_params.get("ssl_trust_store_password", ""),
                "ssl_key_store": plugin_params.get("ssl_key_store", ""),
                "ssl_key_store_password": plugin_params.get("ssl_key_store_password", ""),
            },
            "bkmonitorbeat_debug.yaml": {
                "host": collect_params["host"],
                "port": collect_params["port"],
                "period": collect_params["period"],
                "metric_url": f"{collect_params['host']}:{collect_params['port']}",
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
            plugin_params: 插件定义参数，用户自定义的参数
            target_nodes: 采集目标节点
        Returns:
            部署步骤参数列表
        """

        if collect_params.get("port"):
            plugin_params["port"] = collect_params["port"]
        else:
            plugin_params["port"] = "{{ control_info.listen_port }}"
            collect_params["port"] = f"{{{{ step_data.{self.plugin.id}.control_info.listen_port }}}}"
        plugin_params["host"] = collect_params["host"]
        collect_params["metric_url"] = f"{collect_params['host']}:{collect_params['port']}"
        # 处理差异化指标
        diff_fields: str = self.plugin.define.get("diff_fields", "")
        collect_params["diff_metrics"] = diff_fields.split(",") if diff_fields else []

        steps: list[dict[str, Any]] = [
            # 配置文件下发
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
                        "username": plugin_params["username"],
                        "password": plugin_params["password"],
                        "jmx_url": plugin_params["jmx_url"],
                        "host": plugin_params["host"],
                        "port": plugin_params["port"],
                        "ssl_enabled": plugin_params.get("ssl_enabled", "false"),
                        "ssl_trust_store": plugin_params.get("ssl_trust_store", ""),
                        "ssl_trust_store_password": plugin_params.get("ssl_trust_store_password", ""),
                        "ssl_key_store": plugin_params.get("ssl_key_store", ""),
                        "ssl_key_store_password": plugin_params.get("ssl_key_store_password", ""),
                    }
                },
            },
            # bkmonitorbeat子配置文件
            {
                "id": "bkmonitorbeat",  # 单次 task 内唯一，否则节点管理 step 入库会报错
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "plugin_version": "latest",
                    "config_templates": [{"name": self._SUB_CONFIG_NAME, "version": "latest"}],
                },
                "params": {
                    "context": {
                        "period": str(collect_params.get("period", 60)),
                        "task_id": str(collect_task_id),
                        "bk_biz_id": str(bk_biz_id),
                        "config_name": self.plugin.id,
                        "config_version": "1.0",
                        "namespace": self.plugin.id,
                        "timeout": str(collect_params.get("timeout", 60)),
                        "max_timeout": str(collect_params.get("timeout", 60)),
                        "dataid": bk_data_ids["bk_data_id"],
                        "labels": {
                            "$for": "cmdb_instance.scope",
                            "$item": "scope",
                            "$body": {
                                "bk_target_host_id": "{{ cmdb_instance.host.bk_host_id }}",
                                "bk_target_ip": "{{ cmdb_instance.host.bk_host_innerip }}",
                                "bk_target_cloud_id": "{{ cmdb_instance.host.bk_cloud_id[0].id if cmdb_instance.host.bk_cloud_id is iterable and cmdb_instance.host.bk_cloud_id is not string else cmdb_instance.host.bk_cloud_id }}",
                                "bk_target_topo_level": "{{ scope.bk_obj_id }}",
                                "bk_target_topo_id": "{{ scope.bk_inst_id }}",
                                "bk_target_service_category_id": "{{ cmdb_instance.service.service_category_id | default('', true) }}",
                                "bk_target_service_instance_id": "{{ cmdb_instance.service.id }}",
                                "bk_collect_config_id": str(collect_task_id),
                            },
                        },
                        "host": collect_params["host"],
                        "port": collect_params["port"],
                        "metric_url": collect_params["metric_url"],
                        "diff_metrics": collect_params["diff_metrics"],
                    }
                },
            },
        ]

        return steps

    # config_yaml
    @override
    @classmethod
    def _parse_define(
        cls,
        bk_tenant_id: str,
        operator: str,
        extract_dir: Path,
        plugin_id: str,
        meta_data: dict[str, Any],
    ) -> dict[str, Any]:
        """解析插件定义

        jmx 插件需要解析 config.yaml.tpl 中的参数，因为它们属于插件定义的一部分.

        Args:
            bk_tenant_id: 租户ID
            operator: 操作人
            extract_dir: 解压根目录路径
            plugin_id: 插件ID
            meta_data: meta.yaml 解析后的数据

        Returns:
            插件定义字典，将赋值给 CreatePluginParams.define

        Example:
            {
                "config_yaml": "username: {{ username }}\npassword: {{ password }}\n..."
            }
        """
        define: dict[str, Any] = {}
        # 实际各个操作系统 jmx 配置是一致的，从实际存在的插件目录中选择一个 config.yaml.tpl 作为插件定义的一部分
        # 复用基类的 _find_plugin_dir 以支持仅包含单一 OS 目录的插件包
        try:
            plugin_dir, found_plugin_id = cls._find_plugin_dir(extract_dir)
        except ValueError as error:
            logger.warning(f"未找到可用的插件操作系统目录: {error}")
            raise ParseOsTypeError(str(error)) from error
        if found_plugin_id != plugin_id:
            logger.warning(f"插件目录与 meta.yaml 中的 plugin_id 不一致: {found_plugin_id} != {plugin_id}")
            raise PluginParseError(f"插件目录与 meta.yaml 中的 plugin_id 不一致: {found_plugin_id} != {plugin_id}")
        # 构建 config.yaml.tpl 文件路径
        config_yaml_tpl_path: Path = plugin_dir / "etc/config.yaml.tpl"
        if not config_yaml_tpl_path.exists() or not config_yaml_tpl_path.is_file():
            logger.warning(f"配置文件模板不存在: {config_yaml_tpl_path}, 跳过")
            raise PluginParseError(f"配置文件模板不存在: {config_yaml_tpl_path}")
        # config.yaml.tpl 可能包含 Jinja 占位符，导入时保留模板原文，避免被 YAML 解析器误判。
        try:
            define["config_yaml"] = config_yaml_tpl_path.read_text(encoding="utf-8")
        except OSError as error:
            logger.error(f"读取配置文件模板失败: {error}")
            raise PluginParseError(f"读取配置文件模板失败: {error}") from error

        return define
