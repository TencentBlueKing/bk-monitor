from typing import Any, ClassVar, final

from typing_extensions import override

from bk_monitor_base.domains.metric_plugin.constants import MetricPluginStatus, PluginType
from bk_monitor_base.domains.metric_plugin.define import (
    CreatePluginParams,
    MetricPluginMetricField,
    MetricPluginMetricGroup,
)
from bk_monitor_base.domains.metric_plugin.manager.node_man.built_in import BuiltInPluginManager
from bk_monitor_base.domains.metric_plugin.manager.node_man.datalink import ProcessPluginDataLinker
from bk_monitor_base.domains.metric_plugin.models import MetricPluginModel

# 进程插件指标信息
PROCESS_METRIC_INFO = {
    "perf": {
        "metric_list": [
            "cpu_start_time",
            "cpu_system",
            "cpu_total_pct",
            "cpu_total_ticks",
            "cpu_user",
            "fd_limit_hard",
            "fd_limit_soft",
            "fd_open",
            "io_read_bytes",
            "io_read_speed",
            "io_write_bytes",
            "io_write_speed",
            "memory_rss_bytes",
            "memory_rss_pct",
            "memory_share",
            "memory_size",
        ],
        "dimensions": ["process_name", "pid"],
    },
    "port": {"metric_list": ["alive"], "dimensions": ["listen_address", "listen_port", "process_name", "pid"]},
}


@final
class ProcessPluginManager(BuiltInPluginManager):
    """进程采集插件管理器"""

    type: ClassVar[str] = PluginType.PROCESS
    _SUB_CONFIG_NAME = "monitor_process.conf"

    # 指标字段描述和单位映射 (描述, 单位)
    METRIC_FIELD_INFO_MAP = {
        "cpu_total_pct": ("进程CPU使用率", "percentunit"),
        "io_read_bytes": ("进程io累计读", "bytes"),
        "io_read_speed": ("进程io读速率", "Bps"),
        "io_write_bytes": ("进程io累计写", "bytes"),
        "io_write_speed": ("进程io写速率", "Bps"),
        "memory_rss_bytes": ("物理内存", "bytes"),
        "memory_rss_pct": ("物理内存使用率", "percentunit"),
        "memory_share": ("共享内存", "bytes"),
        "memory_size": ("虚拟内存", "bytes"),
        "fd_limit_hard": ("fd_limit_hard", "short"),
        "fd_limit_soft": ("fd_limit_soft", "short"),
        "fd_open": ("打开的文件描述符数量", "short"),
        "cpu_system": ("进程占用系统态时间", "ms"),
        "cpu_total_ticks": ("整体占用时间", "ms"),
        "cpu_user": ("进程占用用户态时间", "ms"),
        "cpu_start_time": ("进程启动时间", "none"),
        "alive": ("端口存活", "none"),
    }

    # 维度字段描述映射
    DIMENSION_INFO_MAP = {
        "bk_target_ip": "目标IP",
        "bk_target_cloud_id": "目标机器云区域ID",
        "bk_collect_config_id": "采集配置",
        "bk_biz_id": "业务ID",
        "process_name": "进程名",
        "pid": "进程序号",
        "listen_address": "监听地址",
        "listen_port": "监听端口",
    }

    @override
    @classmethod
    def get_metric_info(cls, **kwargs: Any) -> list[MetricPluginMetricGroup]:
        """获取进程采集插件的指标信息

        Returns:
            list[MetricPluginMetricGroup]: 指标组列表
        """
        metrics: list[MetricPluginMetricGroup] = []
        for table_name, field_info in PROCESS_METRIC_INFO.items():
            field_list: list[MetricPluginMetricField] = []

            # 添加指标字段
            for metric_field in field_info["metric_list"]:
                metric_desc, unit = cls.METRIC_FIELD_INFO_MAP.get(metric_field, (metric_field, ""))
                field_list.append(
                    MetricPluginMetricField(
                        name=metric_field,
                        is_active=True,
                        type="double",
                        monitor_type="metric",
                        unit=unit,
                        description=metric_desc,
                    )
                )

            # 添加维度字段
            for dimension_field in field_info["dimensions"]:
                field_list.append(
                    MetricPluginMetricField(
                        name=dimension_field,
                        is_active=True,
                        type="string",
                        monitor_type="dimension",
                        unit="none",
                        description=cls.DIMENSION_INFO_MAP.get(dimension_field, dimension_field),
                    )
                )

            # 创建指标组对象
            metrics.append(MetricPluginMetricGroup(table_name=table_name, table_desc=table_name, fields=field_list))
        return metrics

    @override
    @classmethod
    def create_built_in_plugin(
        cls, bk_tenant_id: str, bk_biz_id: int, operator: str, **kwargs: Any
    ) -> "ProcessPluginManager":
        """创建并发布进程内置插件

        Args:
            bk_tenant_id: 租户ID
            bk_biz_id: 业务ID
            operator: 操作人
            **kwargs: 额外参数（进程插件暂不需要额外参数）

        Returns:
            ProcessPluginManager: 插件管理器实例
        """
        plugin_id = "bkprocessbeat"

        # 检查插件是否已存在
        existing_plugin = MetricPluginModel.objects.filter(
            bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, is_deleted=False
        ).first()

        if existing_plugin:
            # 如果插件已存在，直接返回现有插件的管理器实例
            plugin = existing_plugin.to_plugin()
            return cls(plugin=plugin)

        # 插件不存在，创建新插件
        params = CreatePluginParams(
            id=plugin_id,
            type=cls.type,
            is_internal=True,
            name="进程采集插件",
            description_md="用于采集系统进程信息的内置插件",
            label="host_process",
            status=MetricPluginStatus.RELEASE,  # 内置插件创建时即是发布状态
            metrics=cls.get_metric_info(),
        )

        return cls.create_plugin(bk_tenant_id, bk_biz_id, params, operator)

    @override
    def apply_data_link(self, operator: str) -> dict[str, Any]:
        """申请数据链路。"""
        data_linker = ProcessPluginDataLinker(self.plugin)
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

        plugin_config_dict = {
            "process_name": plugin_params.get("process_name", ""),
            "port_detect": plugin_params["port_detect"],
        }

        # 根据匹配类型添加不同的参数
        match_type = plugin_params["match_type"]
        if match_type == "command":
            plugin_config_dict.update(
                {
                    "match_pattern": plugin_params["match_pattern"],
                    "exclude_pattern": plugin_params["exclude_pattern"],
                    # 维度注入能力
                    "extract_pattern": plugin_params.get("extract_pattern", ""),
                }
            )
        elif match_type == "pid":
            plugin_config_dict.update(
                {
                    "pid_path": plugin_params["pid_path"],
                }
            )

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
                        "config": {
                            **plugin_config_dict,
                            "taskid": str(collect_task_id),
                            "namespace": self.plugin.id,
                            # 采集周期带上单位 `s`
                            "period": f"{collect_params['period']}s",
                            # 采集超时时间
                            "timeout": str(collect_params.get("timeout", 60)),
                            "max_timeout": str(collect_params.get("timeout", 60)),
                            "dataid": str(bk_data_ids["perf_data_id"]),
                            "port_dataid": str(bk_data_ids["port_data_id"]),
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
                                    "bk_collect_config_id": collect_task_id,
                                    "bk_biz_id": str(bk_biz_id),
                                },
                            },
                            "tags": collect_params["collector"].get("tag", {}),
                        },
                    }
                },
            },
        ]

        return steps
