import logging
from pathlib import Path
from typing import Any, ClassVar, final

from furl import furl
from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.constants import PluginType
from bk_monitor_base.domains.metric_plugin.manager.base import OSType
from bk_monitor_base.domains.metric_plugin.manager.node_man.base import CommandPluginManager

logger = logging.getLogger(__name__)


@final
class PushgatewayPluginManager(CommandPluginManager):
    """BK-Pull (Pushgateway) 插件管理器

    通过bkmonitorbeat采集指定的指标数据地址, 要求返回Prometheus格式的指标数据。

    define 字段定义: 不需要任何字段。
    params 字段定义:
        metrics_url: 采集指标数据的地址, 必填。
        username: 基础认证用户名, 可选。
        password: 基础认证密码, 可选。
    """

    type: ClassVar[str] = PluginType.PUSHGATEWAY
    _SUB_CONFIG_NAME: ClassVar[str] = "bkmonitorbeat_prometheus.conf"

    @override
    def get_supported_os_types(self) -> list[OSType]:
        """获取支持的操作系统类型"""

        return [OSType.LINUX, OSType.LINUX_AARCH64, OSType.WINDOWS]

    @override
    def make_package(self, is_compress: bool = True) -> Path:
        """制作插件包

        Args:
            is_compress: 是否压缩

        Returns:
            如果不需要压缩，则返回插件包目录路径；如果需要压缩，则返回压缩包路径
        """
        return self._make_package(is_compress=is_compress)

    @staticmethod
    def _add_basic_auth_to_url(url: str, username: str, password: str) -> str:
        """为 URL 添加基础认证信息

        Args:
            url: 原始 URL
            username: 用户名
            password: 密码

        Returns:
            包含基础认证信息的 URL
        """
        if not username:
            return url

        parsed_url = furl(url)
        parsed_url.username = username
        parsed_url.password = password
        return parsed_url.tostr()

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
        metric_url = collect_params.get("metrics_url", "")
        username = collect_params.get("username", "")
        password = collect_params.get("password", "")

        # 对存量数据进行处理
        # 如果 password 为 True 抛出异常让用户修改密码
        # 如果 password 为 False 则在上面转成 ""
        if password is True:
            raise TypeError("Please reset your password")
        # 如果用户填写了用户名，则在url中添加基础认证
        metric_url = self._add_basic_auth_to_url(metric_url, username, password)

        debug_params = {
            "metric_url": metric_url,
            "period": collect_params["period"],
        }

        # 处理维度注入参数
        _, _, extra_dimensions = self._process_plugin_params(collect_params, plugin_params)
        if extra_dimensions:
            debug_params["labels"] = {
                "$for": "cmdb_instance.scope",
                "$item": "scope",
                "$body": extra_dimensions,
            }

        return {
            "bkmonitorbeat_debug.yaml": debug_params,
            "env.yaml": {},
        }

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

        # 处理维度注入参数
        _, _, extra_dimensions = self._process_plugin_params(collect_params, plugin_params)

        # 处理指标 URL
        metric_url = collect_params.pop("metrics_url", "")
        username = collect_params.get("username", "")
        password = collect_params.get("password", "")
        # 如果用户填写了用户名，则在url中添加基础认证
        metric_url = self._add_basic_auth_to_url(metric_url, username, password)

        # 处理差异化指标
        diff_fields: str = self.plugin.define.get("diff_fields", "")
        diff_metrics = diff_fields.split(",") if diff_fields else []

        steps: list[dict[str, Any]] = [
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
                                **extra_dimensions,
                            },
                        },
                        "metric_url": metric_url,
                        "diff_metrics": diff_metrics,
                    }
                },
            },
        ]

        return steps
