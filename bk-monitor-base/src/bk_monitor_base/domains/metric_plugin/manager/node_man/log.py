import re
import uuid
from typing import Any, ClassVar, final

from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.constants import LOG_DEFAULT_DIMENSIONS, MetricPluginStatus, PluginType
from bk_monitor_base.domains.metric_plugin.define import (
    CreatePluginParams,
    MetricPluginMetricField,
    MetricPluginMetricGroup,
)
from bk_monitor_base.domains.metric_plugin.manager.node_man.built_in import BuiltInPluginManager
from bk_monitor_base.domains.metric_plugin.manager.node_man.datalink import LogPluginDataLinker


@final
class LogPluginManager(BuiltInPluginManager):
    """日志关键字内置插件管理器"""

    type: ClassVar[str] = PluginType.LOG
    _SUB_CONFIG_NAME = "bkmonitorbeat_keyword.conf"

    @override
    @classmethod
    def get_metric_info(cls, **kwargs: Any) -> list[MetricPluginMetricGroup]:
        """获取日志关键字插件的指标信息

        Args:
            **kwargs: 包含以下参数：
                - rules(list[dict]): 日志关键字规则列表（必传）
                - label(str): 插件标签（可选）

        Returns:
            指标组列表

        Raises:
            ValueError: 当缺少必传参数 rules 时抛出
        """
        if "rules" not in kwargs:
            raise ValueError("Missing required parameter: rules")

        rules = kwargs["rules"]
        label = kwargs.get("label")

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

        # 收集所有维度
        dimensions: set[str] = set()
        pattern = re.compile(r"(?<=<)[^<>]+(?=>)")

        # 从规则中提取维度
        for rule in rules:
            if "pattern" in rule:
                dimensions.update(pattern.findall(rule["pattern"]))

        # 添加默认维度
        default_dimensions = LOG_DEFAULT_DIMENSIONS.copy()
        if label in ["component", "service_module"]:
            default_dimensions.append("bk_service_instance_id")
        dimensions.update(default_dimensions)

        # 添加维度字段
        for dimension in sorted(dimensions):
            field_list.append(
                MetricPluginMetricField(
                    name=dimension,
                    is_active=True,
                    type="string",
                    monitor_type="dimension",
                    unit="",
                    description=dimension,
                )
            )

        # 创建指标组对象
        return [MetricPluginMetricGroup(table_name="base", table_desc="默认分类", fields=field_list)]

    @override
    @classmethod
    def create_built_in_plugin(
        cls, bk_tenant_id: str, bk_biz_id: int, operator: str, **kwargs: Any
    ) -> "LogPluginManager":
        """创建并发布日志关键字内置插件

        Args:
            bk_tenant_id: 租户ID
            bk_biz_id: 业务ID
            operator: 操作人
            **kwargs: 额外参数，包括：
                - label(str): 插件标签（必传）
                - rules(list[dict]): 日志关键字规则列表(必传)

        Returns:
            LogPluginManager: 插件管理器实例
        """
        if "label" not in kwargs:
            raise ValueError("Missing required parameter: label")
        if "rules" not in kwargs:
            raise ValueError("Missing required parameter: rules")

        params = CreatePluginParams(
            id=f"log_{uuid.uuid4().hex[:22]}",
            type=cls.type,
            is_internal=True,
            name="日志关键字采集插件",
            description_md="用于采集系统日志信息的内置插件",
            label=kwargs["label"],
            status=MetricPluginStatus.RELEASE,  # 内置插件创建时即是发布状态
            metrics=cls.get_metric_info(rules=kwargs["rules"], label=kwargs["label"]),
        )

        plugin_manager = cls.create_plugin(bk_tenant_id, bk_biz_id, params, operator)

        # 将 rules 保存到 related_params 中，供后续创建事件分组时使用
        plugin_model = plugin_manager._get_plugin_model()
        plugin_model.related_params["rules"] = kwargs["rules"]
        plugin_model.save(update_fields=["related_params"])
        plugin_manager.plugin.related_params["rules"] = kwargs["rules"]

        return plugin_manager

    @override
    def apply_data_link(self, operator: str) -> dict[str, Any]:
        """申请数据链路。"""
        data_linker = LogPluginDataLinker(self.plugin)
        data_linker.apply_data_ids(operator)
        data_linker.apply_result_tables(operator)
        return self.plugin.related_params

    @staticmethod
    def _get_target(object_type: str) -> str:
        """获取目标标识
        Args:
            object_type: 对象类型
        Returns:
            目标标识字符串
        """
        if object_type == "SERVICE":
            target = "{{ cmdb_instance.service.id }}"
        else:
            target = (
                "{{ '{}:{}'.format(cmdb_instance.host.bk_cloud_id[0].id, cmdb_instance.host.bk_host_innerip) "
                "if cmdb_instance.host.bk_cloud_id is iterable and cmdb_instance.host.bk_cloud_id is not string "
                "else '{}:{}'.format(cmdb_instance.host.bk_cloud_id, cmdb_instance.host.bk_host_innerip) }}"
            )
        return target

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

        # 构建采集器参数
        collector_params: dict[str, Any] = {
            "tasks": [
                {
                    "task_id": collect_task_id,
                    "bk_biz_id": bk_biz_id,
                    "dataid": bk_data_ids["bk_data_id"],
                    "type": "keyword",
                    "close_inactive": "86400s",
                    "path_list": plugin_params["log_path"],
                    "report_period": collect_params["period"],
                    "encoding": plugin_params["charset"],
                    "filter_patterns": plugin_params.get("filter_patterns", []),
                    "task_list": [
                        {"name": rule["name"], "pattern": rule["pattern"]} for rule in plugin_params["rules"]
                    ],
                    "target": self._get_target(collect_params["target_object_type"]),
                    "labels": collect_params["labels"],
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
