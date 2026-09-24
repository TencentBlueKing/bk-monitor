"""
订阅管理服务

负责生成节点管理订阅配置、管理订阅生命周期
"""

import logging
from typing import Any, final

from bk_monitor_base.domains.uptime_check.constants import DEFAULT_MAX_TIMEOUT, UptimeCheckProtocol
from bk_monitor_base.domains.uptime_check.services.config_generator import ConfigGeneratorService
from bk_monitor_base.infras.constant import BK_SUPPLIER_ID

logger = logging.getLogger(__name__)


@final
class SubscriptionService:
    """
    订阅管理服务

    负责生成节点管理订阅配置、处理订阅的创建/更新/删除
    """

    def __init__(self, bk_biz_id: int = 0):
        """
        初始化订阅服务

        Args:
            bk_biz_id: 业务ID
        """
        self.bk_biz_id = bk_biz_id
        self.config_generator = ConfigGeneratorService()

    def generate_subscription_config(
        self,
        task_id: int,
        protocol: str,
        config: dict[str, Any],
        nodes: list[dict[str, Any]],
        data_id: int,
        labels: dict[str, Any] | None = None,
        task_group_id: str = "0",
        use_custom_report: bool = False,
    ) -> list[dict[str, Any]]:
        """
        生成订阅配置(对应原 generate_subscription_configs)

        将拨测任务信息转换为节点管理可以识别的订阅配置格式。
        按业务ID对节点进行分组,为每个业务生成独立的订阅配置。

        Args:
            task_id: 拨测任务ID
            protocol: 协议类型(HTTP/TCP/UDP/ICMP)
            config: 任务配置字典
            nodes: 节点列表,每个节点包含 bk_biz_id, bk_host_id, ip, plat_id 等字段
            data_id: 数据ID
            labels: 自定义标签
            task_group_id: 任务分组ID,多个用逗号分隔
            use_custom_report: 是否使用自定义上报

        Returns:
            订阅配置列表,每个业务一个配置

            configs = service.generate_subscription_config(
                task_id=1,
                protocol="HTTP",
                config={"period": 60, ...},
                nodes=[
                    {"bk_biz_id": 2, "bk_host_id": 123, ...},
                    {"bk_biz_id": 3, "bk_host_id": 456, ...}
                ],
                data_id=1011
            )
            # 返回: [
            #   {业务2的订阅配置},
            #   {业务3的订阅配置}
            # ]
        """
        protocol_lower = protocol.lower()
        labels = labels or {}

        # 第一步: 按业务ID对节点进行分组
        biz_nodes = self._group_nodes_by_biz(nodes)

        # 第二步: 计算超时配置
        available_duration = int(config.get("timeout", config.get("period", 60) * 1000))
        timeout = self._calculate_timeout(available_duration)

        # 第三步: 生成beat任务配置
        tasks = self.config_generator.generate_sub_config(
            protocol=protocol,
            config=config,
            task_id=task_id,
            bk_biz_id=self.bk_biz_id,
            labels=labels,
            test=False,
        )

        # 第四步: 为每个业务生成订阅配置
        params_list: list[dict[str, Any]] = []
        for target_bk_biz_id, biz_node_list in biz_nodes.items():
            params = self._build_subscription_params(
                task_id=task_id,
                protocol=protocol_lower,
                target_bk_biz_id=target_bk_biz_id,
                nodes=biz_node_list,
                data_id=data_id,
                timeout=timeout,
                tasks=tasks,
                config=config,
                task_group_id=task_group_id,
                use_custom_report=use_custom_report,
            )
            params_list.append(params)

        return params_list

    def _group_nodes_by_biz(self, nodes: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
        """
        按业务ID对节点进行分组

        Args:
            nodes: 节点列表

        Returns:
            {bk_biz_id: [nodes]} 的字典
        """
        biz_nodes: dict[int, list[dict[str, Any]]] = {}

        for node in nodes:
            bk_biz_id = node.get("bk_biz_id", self.bk_biz_id)
            if bk_biz_id not in biz_nodes:
                biz_nodes[bk_biz_id] = []
            biz_nodes[bk_biz_id].append(node)

        return biz_nodes

    def _calculate_timeout(self, available_duration: int) -> int:
        """
        计算超时时间

        Args:
            available_duration: 可用时长(毫秒)
        Returns:
            计算后的超时时间(毫秒)
        """
        if available_duration > DEFAULT_MAX_TIMEOUT:
            return available_duration + 5000
        return DEFAULT_MAX_TIMEOUT

    def _build_subscription_params(
        self,
        task_id: int,
        protocol: str,
        target_bk_biz_id: int,
        nodes: list[dict[str, Any]],
        data_id: int,
        timeout: int,
        tasks: list[dict[str, Any]],
        config: dict[str, Any],
        task_group_id: str,
        use_custom_report: bool,
    ) -> dict[str, Any]:
        """
        构建单个业务的订阅配置参数

        Args:
            task_id: 任务ID
            protocol: 协议(小写)
            target_bk_biz_id: 目标业务ID
            nodes: 节点列表
            data_id: 数据ID
            timeout: 超时时间(毫秒)
            tasks: beat任务配置列表
            config: 原始任务配置
            task_group_id: 任务分组ID
            use_custom_report: 是否使用自定义上报

        Returns:
            订阅配置字典
        """
        # 构建作用域(scope) - 定义在哪些节点上执行
        scope = self._build_scope(target_bk_biz_id, nodes)

        # 构建步骤(steps) - 定义执行什么操作
        step = self._build_step(
            protocol=protocol,
            task_id=task_id,
            data_id=data_id,
            timeout=timeout,
            tasks=tasks,
            config=config,
            task_group_id=task_group_id,
            use_custom_report=use_custom_report,
        )

        return {"scope": scope, "steps": [step], "run_immediately": True}

    def _build_scope(self, bk_biz_id: int, nodes: list[dict[str, Any]]) -> dict[str, Any]:
        """
        构建订阅作用域

        Args:
            bk_biz_id: 业务ID
            nodes: 节点列表

        Returns:
            作用域配置
        """
        return {
            "bk_biz_id": bk_biz_id,
            "object_type": "HOST",
            "node_type": "INSTANCE",
            "nodes": [
                {"bk_host_id": node["bk_host_id"]}
                if node.get("bk_host_id")
                else {
                    "ip": node["ip"],
                    "bk_cloud_id": node["plat_id"],
                    "bk_supplier_id": BK_SUPPLIER_ID,
                }
                for node in nodes
            ],
        }

    def _build_step(
        self,
        protocol: str,
        task_id: int,
        data_id: int,
        timeout: int,
        tasks: list[dict[str, Any]],
        config: dict[str, Any],
        task_group_id: str,
        use_custom_report: bool,
    ) -> dict[str, Any]:
        """
        构建订阅步骤

        Args:
            protocol: 协议(小写)
            task_id: 任务ID
            data_id: 数据ID
            timeout: 超时时间
            tasks: 任务配置列表
            config: 原始配置
            task_group_id: 任务分组ID
            use_custom_report: 是否使用自定义上报

        Returns:
            步骤配置
        """
        # 构建标签配置
        label_config = self._build_labels(
            protocol=protocol,
            task_group_id=task_group_id,
        )

        # 构建上下文参数
        context = {
            "data_id": data_id,
            "max_timeout": f"{timeout}ms",
            "custom_report": "true" if use_custom_report else "false",
            "send_interval": config.get("send_interval"),
            "tasks": tasks,
            "config_hosts": config.get("hosts", []),
            "labels": label_config,
            # 针对动态节点的情况
            "task_id": task_id,
            # 历史逻辑要求使用任务所属业务ID，而不是订阅目标业务ID
            "bk_biz_id": self.bk_biz_id,
        }

        # 添加协议特定的参数
        self._add_protocol_specific_context(context, protocol, config, timeout)

        return {
            "id": f"bkmonitorbeat_{protocol}",
            "type": "PLUGIN",
            "config": {
                "plugin_name": "bkmonitorbeat",
                "plugin_version": "latest",
                "config_templates": [{"name": f"bkmonitorbeat_{protocol}.conf", "version": "latest"}],
            },
            "params": {"context": context},
        }

    def _build_labels(
        self,
        protocol: str,
        task_group_id: str,
    ) -> dict[str, Any]:
        """
        构建标签配置

        Args:
            protocol: 协议
            task_group_id: 任务分组ID
        Returns:
            标签配置
        """
        label_config: dict[str, Any] = {
            "$for": "cmdb_instance.scope",
            "$body": {"task_group_id": task_group_id},
            "$item": "scope",
        }

        # ICMP协议需要特殊处理node_id
        if protocol.upper() == UptimeCheckProtocol.ICMP:
            body = label_config["$body"]
            assert isinstance(body, dict)  # 类型守卫
            body["node_id"] = (
                "{{ cmdb_instance.host.bk_cloud_id[0].id if cmdb_instance.host.bk_cloud_id is iterable and "
                "cmdb_instance.host.bk_cloud_id is not string "
                "else cmdb_instance.host.bk_cloud_id }}:{{ cmdb_instance.host.bk_host_innerip }}"
            )

        return label_config

    def _add_protocol_specific_context(
        self,
        context: dict[str, Any],
        protocol: str,
        config: dict[str, Any],
        timeout: int,
    ) -> None:
        """
        添加协议特定的上下文参数

        Args:
            context: 上下文字典(会被修改)
            protocol: 协议
            config: 配置
            timeout: 超时时间
        """
        period = config.get("period", 60)
        available_duration = int(config.get("timeout", period * 1000))

        # 通用参数
        response_with_prefix = self.config_generator.encode_data_with_prefix(config.get("response", ""))
        request_with_prefix = self.config_generator.encode_data_with_prefix(config.get("request", ""))
        context.update(
            {
                "period": f"{period}s",
                "available_duration": f"{available_duration}ms",
                "timeout": f"{timeout}ms",
                "target_port": config.get("port"),
                "response": response_with_prefix,
                "request": request_with_prefix,
                "response_format": config.get("response_format", "in"),
            }
        )

        # ICMP 特定参数
        if protocol == "icmp":
            context.update(
                {
                    "size": config.get("size", 56),
                    "total_num": config.get("total_num", 3),
                    "max_rtt": f"{config.get('max_rtt', 3000)}ms",
                }
            )
