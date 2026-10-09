import uuid
from typing import Any, ClassVar, final

import yaml
from typing_extensions import override

from bk_monitor_base.config import get_config
from bk_monitor_base.domains.metric_plugin.constants import MetricPluginStatus, PluginType
from bk_monitor_base.domains.metric_plugin.define import (
    CreatePluginParams,
    MetricPlugin,
    MetricPluginMetricField,
    MetricPluginMetricGroup,
    MetricPluginParams,
)
from bk_monitor_base.domains.metric_plugin.manager.node_man.datalink import SNMPTrapPluginDataLinker
from bk_monitor_base.domains.metric_plugin.manager.node_man.log import LogPluginManager

# 默认的SNMP Trap配置
DEFAULT_TRAP_CONFIG: dict[str, Any] = {
    "server_port": "162",
    "listen_ip": "0.0.0.0",
    "yaml": {"filename": "", "value": ""},
    "community": "",
    "aggregate": True,
}

# 默认的SNMP Trap V3认证信息
DEFAULT_TRAP_V3_AUTH_INFO: dict[str, Any] = {
    "version": "v3",
    "auth_info": [
        {
            "security_level": "noAuthNoPriv",
            "security_name": "",
            "context_name": "",
            "authentication_protocol": "MD5",
            "authentication_passphrase": "",
            "privacy_protocol": "DES",
            "privacy_passphrase": "",
            "authoritative_engineID": "",
        }
    ],
}


@final
class SNMPTrapPluginManager(LogPluginManager):
    """SNMP Trap插件管理器"""

    type: ClassVar[str] = PluginType.SNMP_TRAP
    _SUB_CONFIG_NAME: ClassVar[str] = "bkmonitorbeat_snmptrap.conf"

    @override
    @classmethod
    def get_metric_info(cls, **kwargs: Any) -> list[MetricPluginMetricGroup]:
        """获取SNMP Trap插件的指标信息

        Returns:
            指标组列表
        """
        field_list: list[MetricPluginMetricField] = []

        # 添加指标字段
        field_list.append(
            MetricPluginMetricField(
                name="event.count",
                is_active=True,
                type="double",
                monitor_type="metric",
                unit="",
                description="event_count",
            )
        )

        return [MetricPluginMetricGroup(table_name="base", table_desc="默认分类", fields=field_list)]

    @override
    @classmethod
    def create_built_in_plugin(
        cls, bk_tenant_id: str, bk_biz_id: int, operator: str, **kwargs: Any
    ) -> "SNMPTrapPluginManager":
        """创建并发布SNMP Trap内置插件

        Args:
            bk_tenant_id: 租户ID
            bk_biz_id: 业务ID
            operator: 操作人
            **kwargs: 额外参数，包括：
                - label(str): 插件标签（必传）

        Returns:
            SNMPTrapPluginManager: 插件管理器实例
        """
        if "label" not in kwargs:
            raise ValueError("Missing required parameter: label")

        params = CreatePluginParams(
            id=f"snmp_trap_{uuid.uuid4().hex[:22]}",
            type=cls.type,
            is_internal=True,
            name="SNMP Trap采集插件",
            description_md="SNMP Trap采集插件",
            label=kwargs["label"],
            status=MetricPluginStatus.RELEASE,  # 内置插件创建时即是发布状态
            metrics=cls.get_metric_info(),
        )

        return cls.create_plugin(bk_tenant_id, bk_biz_id, params, operator)

    @override
    def apply_data_link(self, operator: str) -> dict[str, Any]:
        """申请数据链路。"""
        data_linker = SNMPTrapPluginDataLinker(self.plugin)
        data_linker.apply_data_ids(operator)
        data_linker.apply_result_tables(operator)
        return self.plugin.related_params

    @override
    def get_deploy_steps_params(
        self,
        bk_biz_id: int,
        collect_task_id: int,
        bk_data_ids: dict[str, int],
        collect_params: dict[str, Any],
        plugin_params: dict[str, Any],
        target_nodes: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """获取部署步骤参数
        Args:
            bk_biz_id: 蓝鲸业务ID
            collect_task_id: 采集任务ID
            bk_data_ids: 数据ID映射
            collect_params: 采集参数，如采集周期，超时时间，绑定IP/端口，可以理解为内置参数
            plugin_params: 插件参数，用户自定义的参数
            target_nodes: 采集目标节点(当前 SNMP Trap 类型未使用，为接口一致性保留)
        Returns:
            部署步骤参数列表
        """
        # 提取snmp trap YAML配置文件里面的配置数据
        config_data = yaml.safe_load(plugin_params["yaml"]["value"])
        oids_list: list[dict[str, Any]] = []
        report_oid_dimensions: list[str] = []
        raw_byte_oids: list[str] = []
        encode: str = ""
        hide_agent_port: bool = False
        for item in list(config_data.values()):
            oids_list.extend(item.get("metrics", []))
            report_oid_dimensions.extend(item.get("report_oid_dimensions", []))
            raw_byte_oids.extend(item.get("raw_byte_oids", []))
            encode = item.get("encode", "")
            hide_agent_port = item.get("hide_agent_port", False)

        translate_oid = get_config().domains.metric_plugin.translate_snmp_trap_dimensions

        # 构建采集器参数
        collector_params: dict[str, Any] = {
            "tasks": [
                {
                    "task_id": str(collect_task_id),
                    "bk_biz_id": str(bk_biz_id),
                    "dataid": bk_data_ids["bk_data_id"],
                    "community": plugin_params.get("community", ""),
                    "listen_ip": plugin_params["listen_ip"],
                    "listen_port": plugin_params["server_port"],
                    "snmp_version": plugin_params["version"],
                    "aggregate": plugin_params["aggregate"],
                    "period": f"{collect_params['period']}s",
                    "oids": {oid["oid"]: oid["name"] for oid in oids_list},
                    "report_oid_dimensions": report_oid_dimensions,
                    "raw_byte_oids": raw_byte_oids,
                    "use_display_name_oid": translate_oid,
                    "encode": encode,
                    "hide_agent_port": hide_agent_port,
                    "usm_info": [
                        {
                            "context_name": i.get("context_name", ""),
                            "msg_flags": i.get("security_level", ""),
                            "usm_config": {
                                "username": i.get("security_name", ""),
                                "authentication_protocol": i.get("authentication_protocol", ""),
                                "authentication_passphrase": i.get("authentication_passphrase", ""),
                                "privacy_protocol": i.get("privacy_protocol", ""),
                                "privacy_passphrase": i.get("privacy_passphrase", ""),
                                "authoritative_engineID": i.get("authoritative_engineID", ""),
                                # authoritative_engineboots,authoritative_enginetime为预留默认参数
                                "authoritative_engineboots": 1,
                                "authoritative_enginetime": 1,
                            },
                        }
                        for i in plugin_params.get("auth_info", DEFAULT_TRAP_V3_AUTH_INFO["auth_info"])
                    ],
                    "labels": collect_params["labels"],
                    "target": self._get_target(collect_params["target_object_type"]),
                }
            ]
        }

        # 构建部署步骤
        return [
            {
                "id": self.plugin.id,
                "type": "PLUGIN",
                "config": {
                    "plugin_name": "bkmonitorbeat",
                    "plugin_version": "latest",
                    "config_templates": [{"name": self._SUB_CONFIG_NAME, "version": "latest"}],
                },
                "params": {"context": collector_params},
            }
        ]

    @classmethod
    def get_virtual_plugins(cls, bk_tenant_id: str, plugin_ids: list[str] | None = None) -> list[MetricPlugin]:
        """获取虚拟插件"""
        plugin_ids = plugin_ids or ["snmp_v1", "snmp_v2c", "snmp_v3"]
        plugins: list[MetricPlugin] = []

        for plugin_id in plugin_ids:
            version = plugin_id.split("_")[1]

            # 根据版本获取默认配置
            params = [
                MetricPluginParams(
                    default=DEFAULT_TRAP_CONFIG["server_port"],
                    mode="collector",
                    type="text",
                    name="server_port",
                    alias="Trap服务端口",
                    description="Trap服务端口",
                ),
                MetricPluginParams(
                    default=DEFAULT_TRAP_CONFIG["listen_ip"],
                    mode="collector",
                    type="text",
                    name="listen_ip",
                    alias="绑定地址",
                    description="绑定地址",
                ),
                MetricPluginParams(
                    default=DEFAULT_TRAP_CONFIG["yaml"],
                    mode="collector",
                    type="file",
                    name="yaml",
                    alias="Yaml配置文件",
                    description="Yaml配置文件",
                ),
                MetricPluginParams(
                    default=DEFAULT_TRAP_CONFIG["community"],
                    mode="collector",
                    type="text",
                    name="community",
                    alias="团体名",
                    description="团体名",
                ),
                MetricPluginParams(
                    default=DEFAULT_TRAP_CONFIG["aggregate"],
                    mode="collector",
                    type="boolean",
                    name="aggregate",
                    alias="是否汇聚",
                    description="是否汇聚",
                ),
            ]

            plugins.append(
                MetricPlugin(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=0,
                    id=plugin_id,
                    type=cls.type,
                    is_internal=True,
                    name=f"snmp trap {version}",
                    label="hardware",
                    status=MetricPluginStatus.RELEASE,
                    params=params,
                )
            )

        return plugins
