"""
拨测模块核心流程测试

测试范围:
- 拨测任务完整部署流程 (deploy)
- 拨测任务测试流程 (test)
- 测试数据单独维护，当流程改变时只需更新数据
"""

import json
from base64 import b64decode
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from bk_monitor_base.domains.uptime_check.constants import RESULT_MSG
from bk_monitor_base.domains.uptime_check.models import (
    UptimeCheckNodeModel,
    UptimeCheckTaskModel,
    UptimeCheckTaskSubscription,
)
from bk_monitor_base.domains.uptime_check.services.task_manager import TaskManager

# =============================================================================
# 测试数据管理
# =============================================================================


class TestDataManager:
    """测试数据管理器 - 维护测试用例的入参和期望结果"""

    # 测试用例数据目录
    DATA_DIR = Path(__file__).parent / "test_data"

    @classmethod
    def get_test_case(cls, protocol: str, case_name: str) -> dict[str, Any]:
        """
        获取测试用例数据

        Args:
            protocol: 协议类型 (http, tcp, udp, icmp)
            case_name: 用例名称

        Returns:
            测试用例数据
        """
        # 确保数据目录存在
        cls.DATA_DIR.mkdir(exist_ok=True)

        # 构造数据文件路径
        data_file = cls.DATA_DIR / f"{protocol}_{case_name}.json"

        if data_file.exists():
            with open(data_file, encoding="utf-8") as f:
                return json.load(f)

        # 如果文件不存在，返回默认的空用例
        return {"task_config": {}, "nodes": [], "expected_deployment": {}}


# =============================================================================
# 核心流程测试
# =============================================================================


@pytest.mark.django_db(databases=["default"])
class TestDeployAndTestFlow:
    """拨测任务的核心流程测试 - 只测试 deploy 和 test，不测试中间步骤"""

    @staticmethod
    def _build_actual_deployment_result(
        task: UptimeCheckTaskModel,
        subscription: UptimeCheckTaskSubscription,
    ) -> dict[str, Any]:
        """
        从部署结果构建实际值字典，用于与期望值直接对比

        Args:
            task: 部署后的拨测任务
            subscription: 创建的订阅关系

        Returns:
            实际部署结果字典
        """
        headers = task.config.get("headers", [])
        ip_list = task.config.get("ip_list", [])

        # 构建与 expected_deployment 结构一致的实际值
        actual = {
            "subscription_created": subscription is not None,
            "node_count": task.nodes.count(),  # pyright: ignore[reportAttributeAccessIssue]
            "protocol": task.protocol.lower() if task.protocol else "",
            "verify_fields": {},
        }

        # 构建 verify_fields - 只包含 config 中实际存在的字段
        config = task.config or {}
        verify_fields: dict[str, Any] = {}

        # HTTP 相关字段
        if "method" in config:
            verify_fields["method"] = config["method"]
        if "url_list" in config:
            verify_fields["url_list"] = config["url_list"]
        if "response_code" in config:
            verify_fields["response_code"] = config["response_code"]
        if "response_format" in config:
            verify_fields["response_format"] = config["response_format"]

        # 超时和周期（转换为带单位的字符串格式，与期望值格式一致）
        if "timeout" in config:
            verify_fields["timeout"] = f"{config['timeout']}ms"
        if "period" in config:
            verify_fields["period"] = f"{config['period']}s"

        # 头部数量
        if headers:
            verify_fields["headers_count"] = len(headers)

        # TCP/UDP/ICMP 相关字段
        if "ip_list" in config:
            # TCP 协议包含完整的 ip_list，UDP/ICMP 只包含 ip_list_count
            if task.protocol == UptimeCheckTaskModel.Protocol.TCP:
                verify_fields["ip_list"] = config["ip_list"]
            else:
                verify_fields["ip_list_count"] = len(ip_list)
        if "port" in config:
            verify_fields["port"] = config["port"]
        if "request" in config:
            verify_fields["request"] = config["request"]
        if "response" in config:
            verify_fields["response"] = config["response"]

        # ICMP 特有字段
        if "size" in config:
            verify_fields["size"] = config["size"]
        if "max_rtt" in config:
            verify_fields["max_rtt"] = config["max_rtt"]
        if "total_num" in config:
            verify_fields["total_num"] = config["total_num"]

        actual["verify_fields"] = verify_fields
        return actual

    @staticmethod
    def _filter_expected_for_comparison(expected: dict[str, Any]) -> dict[str, Any]:
        """
        过滤期望值，移除非验证字段（如 notes、description 等）

        Args:
            expected: 原始期望值

        Returns:
            过滤后的期望值
        """
        # 只保留需要对比的字段
        compare_keys = {"subscription_created", "node_count", "protocol", "verify_fields"}
        return {k: v for k, v in expected.items() if k in compare_keys}

    @staticmethod
    def _create_task_from_data(test_data: dict[str, Any]) -> UptimeCheckTaskModel:
        """从 JSON 数据创建拨测任务对象"""
        task_config = test_data["task_config"]

        # 将协议字符串映射到模型协议枚举
        protocol_map = {
            "http": UptimeCheckTaskModel.Protocol.HTTP,
            "tcp": UptimeCheckTaskModel.Protocol.TCP,
            "udp": UptimeCheckTaskModel.Protocol.UDP,
            "icmp": UptimeCheckTaskModel.Protocol.ICMP,
        }
        protocol = protocol_map.get(task_config.get("protocol", "http"))

        # 创建拨测任务
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=task_config.get("bk_biz_id", 2),
            name=task_config.get("name", "拨测任务"),
            protocol=protocol,
            labels=task_config.get("labels", {}),
            config=task_config.get("config", {}),
        )

        # 创建节点并关联
        nodes = []
        for node_data in test_data.get("nodes", []):
            node = UptimeCheckNodeModel.objects.create(
                bk_biz_id=node_data.get("bk_biz_id", 2),
                name=node_data.get("name", "节点"),
                bk_host_id=node_data.get("bk_host_id"),
                ip=node_data.get("ip"),
                plat_id=node_data.get("plat_id", 0),
                location=node_data.get("location", {}),
                carrieroperator=node_data.get("carrieroperator", ""),
            )
            nodes.append(node)

        if nodes:
            task.nodes.add(*nodes)  # pyright: ignore[reportAttributeAccessIssue]

        return task

    @pytest.fixture
    def http_task(self, db: Any) -> UptimeCheckTaskModel:
        """从 JSON 数据创建 HTTP 拨测任务"""
        test_data = TestDataManager.get_test_case("http", "basic")
        return self._create_task_from_data(test_data)

    @pytest.fixture
    def tcp_task(self, db: Any) -> UptimeCheckTaskModel:
        """从 JSON 数据创建 TCP 拨测任务"""
        test_data = TestDataManager.get_test_case("tcp", "basic")
        return self._create_task_from_data(test_data)

    @pytest.fixture
    def udp_task(self, db: Any) -> UptimeCheckTaskModel:
        """从 JSON 数据创建 UDP 拨测任务"""
        test_data = TestDataManager.get_test_case("udp", "basic")
        return self._create_task_from_data(test_data)

    @pytest.fixture
    def icmp_task(self, db: Any) -> UptimeCheckTaskModel:
        """从 JSON 数据创建 ICMP 拨测任务"""
        test_data = TestDataManager.get_test_case("icmp", "basic")
        return self._create_task_from_data(test_data)

    # =========================================================================
    # Deploy 流程测试
    # =========================================================================

    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.switch_subscription")
    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.create_subscription")
    @patch("bk_monitor_base.domains.uptime_check.services.data_access.DataAccessService.get_or_create_data_id")
    @patch("bk_monitor_base.domains.uptime_check.services.config_generator.get_config")
    def test_http_deploy_flow(
        self,
        mock_get_config: Mock,
        mock_get_data_id: Mock,
        mock_create_subscription: Mock,
        mock_switch_subscription: Mock,
        http_task: UptimeCheckTaskModel,
    ):
        """测试 HTTP 任务完整部署流程"""
        # 配置 mock
        mock_config = MagicMock()
        mock_config.domains.uptime_check.base64_encode_trigger_chars = []
        mock_get_config.return_value = mock_config

        mock_get_data_id.return_value = (False, 1011)
        mock_create_subscription.return_value = {"subscription_id": 9527}

        # 执行部署
        manager = TaskManager(task=http_task)
        result = manager.deploy()

        # 验证部署成功
        assert result == "success"

        # 验证订阅创建被调用
        mock_create_subscription.assert_called_once()

        # 验证订阅关系保存
        subscription = UptimeCheckTaskSubscription.objects.get(uptimecheck_id=http_task.pk)
        assert subscription.subscription_id == 9527
        assert subscription.bk_biz_id == 2

        # 验证部署结果
        test_data = TestDataManager.get_test_case("http", "basic")
        expected = self._filter_expected_for_comparison(test_data.get("expected_deployment", {}))
        actual = self._build_actual_deployment_result(http_task, subscription)

        assert actual == expected, f"部署结果不符合预期:\n期望: {json.dumps(expected, indent=2, ensure_ascii=False)}\n实际: {json.dumps(actual, indent=2, ensure_ascii=False)}"

    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.switch_subscription")
    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.create_subscription")
    @patch("bk_monitor_base.domains.uptime_check.services.data_access.DataAccessService.get_or_create_data_id")
    @patch("bk_monitor_base.domains.uptime_check.services.config_generator.get_config")
    def test_tcp_deploy_flow(
        self,
        mock_get_config: Mock,
        mock_get_data_id: Mock,
        mock_create_subscription: Mock,
        mock_switch_subscription: Mock,
        tcp_task: UptimeCheckTaskModel,
    ):
        """测试 TCP 任务完整部署流程"""
        # 配置 mock
        mock_config = MagicMock()
        mock_config.domains.uptime_check.base64_encode_trigger_chars = []
        mock_get_config.return_value = mock_config

        mock_get_data_id.return_value = (False, 1012)
        mock_create_subscription.return_value = {"subscription_id": 9528}

        # 执行部署
        manager = TaskManager(task=tcp_task)
        result = manager.deploy()

        # 验证部署成功
        assert result == "success"

        # 验证订阅创建被调用
        mock_create_subscription.assert_called_once()

        # 验证订阅关系保存
        subscription = UptimeCheckTaskSubscription.objects.get(uptimecheck_id=tcp_task.pk)
        assert subscription.subscription_id == 9528
        assert subscription.bk_biz_id == 2

        # 验证部署结果
        test_data = TestDataManager.get_test_case("tcp", "basic")
        expected = self._filter_expected_for_comparison(test_data.get("expected_deployment", {}))
        actual = self._build_actual_deployment_result(tcp_task, subscription)

        assert actual == expected, f"部署结果不符合预期:\n期望: {json.dumps(expected, indent=2, ensure_ascii=False)}\n实际: {json.dumps(actual, indent=2, ensure_ascii=False)}"

    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.switch_subscription")
    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.create_subscription")
    @patch("bk_monitor_base.domains.uptime_check.services.data_access.DataAccessService.get_or_create_data_id")
    @patch("bk_monitor_base.domains.uptime_check.services.config_generator.get_config")
    def test_udp_deploy_flow(
        self,
        mock_get_config: Mock,
        mock_get_data_id: Mock,
        mock_create_subscription: Mock,
        mock_switch_subscription: Mock,
        udp_task: UptimeCheckTaskModel,
    ):
        """测试 UDP 任务完整部署流程 - 多节点场景"""
        # 配置 mock
        mock_config = MagicMock()
        mock_config.domains.uptime_check.base64_encode_trigger_chars = []
        mock_get_config.return_value = mock_config

        mock_get_data_id.return_value = (False, 1010)
        mock_create_subscription.return_value = {"subscription_id": 9529}

        # 执行部署
        manager = TaskManager(task=udp_task)
        result = manager.deploy()

        # 验证部署成功
        assert result == "success"

        # 验证订阅创建被调用
        mock_create_subscription.assert_called_once()

        # 验证订阅关系保存
        subscription = UptimeCheckTaskSubscription.objects.get(uptimecheck_id=udp_task.pk)
        assert subscription.subscription_id == 9529
        assert subscription.bk_biz_id == 2

        # 验证部署结果
        test_data = TestDataManager.get_test_case("udp", "basic")
        expected = self._filter_expected_for_comparison(test_data.get("expected_deployment", {}))
        actual = self._build_actual_deployment_result(udp_task, subscription)

        assert actual == expected, f"部署结果不符合预期:\n期望: {json.dumps(expected, indent=2, ensure_ascii=False)}\n实际: {json.dumps(actual, indent=2, ensure_ascii=False)}"

    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.switch_subscription")
    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.create_subscription")
    @patch("bk_monitor_base.domains.uptime_check.services.data_access.DataAccessService.get_or_create_data_id")
    @patch("bk_monitor_base.domains.uptime_check.services.config_generator.get_config")
    def test_icmp_deploy_flow(
        self,
        mock_get_config: Mock,
        mock_get_data_id: Mock,
        mock_create_subscription: Mock,
        mock_switch_subscription: Mock,
        icmp_task: UptimeCheckTaskModel,
    ):
        """测试 ICMP 任务完整部署流程 - 多节点多IP场景"""
        # 配置 mock
        mock_config = MagicMock()
        mock_config.domains.uptime_check.base64_encode_trigger_chars = []
        mock_get_config.return_value = mock_config

        mock_get_data_id.return_value = (False, 1100003)
        mock_create_subscription.return_value = {"subscription_id": 9530}

        # 执行部署
        manager = TaskManager(task=icmp_task)
        result = manager.deploy()

        # 验证部署成功
        assert result == "success"

        # 验证订阅创建被调用
        mock_create_subscription.assert_called_once()

        # 验证订阅关系保存
        subscription = UptimeCheckTaskSubscription.objects.get(uptimecheck_id=icmp_task.pk)
        assert subscription.subscription_id == 9530
        assert subscription.bk_biz_id == 2

        # 验证部署结果
        test_data = TestDataManager.get_test_case("icmp", "basic")
        expected = self._filter_expected_for_comparison(test_data.get("expected_deployment", {}))
        actual = self._build_actual_deployment_result(icmp_task, subscription)

        assert actual == expected, f"部署结果不符合预期:\n期望: {json.dumps(expected, indent=2, ensure_ascii=False)}\n实际: {json.dumps(actual, indent=2, ensure_ascii=False)}"

    # =========================================================================
    # Test 流程测试
    # =========================================================================

    @patch("bk_monitor_base.domains.uptime_check.collector.fast_execute_script")
    @patch("bk_monitor_base.domains.uptime_check.collector.get_job_instance_status")
    @patch("bk_monitor_base.domains.uptime_check.collector.batch_get_job_instance_ip_log")
    @patch("bk_monitor_base.domains.uptime_check.collector.get_host_by_ip")
    @patch("bk_monitor_base.domains.uptime_check.models.cmdb_api.get_host_by_ip")
    @patch("bk_monitor_base.domains.uptime_check.services.task_manager.node_man_v2_api.plugin_search")
    @patch("bk_monitor_base.domains.uptime_check.services.config_generator.get_config")
    def test_task_flow(
        self,
        mock_get_config: Mock,
        mock_plugin_search: Mock,
        mock_model_cmdb_get_host: Mock,
        mock_collector_cmdb_get_host: Mock,
        mock_batch_get_ip_log: Mock,
        mock_get_job_status: Mock,
        mock_fast_execute: Mock,
        http_task: UptimeCheckTaskModel,
    ):
        """
        测试拨测任务测试流程
        """
        mock_config = MagicMock()
        mock_config.domains.uptime_check.base64_encode_trigger_chars = []
        mock_get_config.return_value = mock_config

        # Mock CMDB API (models 中的) - 返回空列表表示节点已有 bk_host_id，不需要查询
        mock_model_cmdb_get_host.return_value = []

        # task_manager 与 collector 共用同一 NodeMan V2 接口；结果同时包含
        # 版本校验和安装路径所需字段。
        mock_plugin_search.return_value = {
            "list": [
                {
                    "bk_host_id": 10001,
                    "inner_ip": "192.168.1.1",
                    "bk_cloud_id": 0,
                    "os_type": "linux",
                    "setup_path": "/usr/local/gse/plugins",
                    "plugin_status": [
                        {
                            "name": "bkmonitorbeat",
                            "version": "3.5.0",
                            "status": "running",
                        }
                    ],
                }
            ]
        }

        # Mock collector 内部的 get_host_by_ip（用于获取主机 OS 信息）
        mock_host = MagicMock()
        mock_host.bk_host_id = 10001
        mock_host.bk_host_innerip = "192.168.1.1"
        mock_host.bk_host_innerip_v6 = ""
        mock_host.bk_cloud_id = 0
        mock_host.bk_os_type = "1"
        mock_host.bk_os_type_name = "Linux"
        mock_collector_cmdb_get_host.return_value = [mock_host]

        # Mock Job API - fast_execute_script 返回任务 ID
        mock_fast_execute.return_value = {"job_instance_id": 12345, "step_instance_id": 1}

        # Mock Job API - get_job_instance_status 返回执行成功
        mock_get_job_status.return_value = {
            "finished": True,
            "job_instance": {"status": 3},  # 3 = 执行成功
            "step_instance_list": [
                {
                    "step_instance_id": 1,
                    "status": 3,  # 成功状态
                    "step_ip_result_list": [
                        {
                            "bk_host_id": 10001,
                            "ip": "192.168.1.1",
                            "bk_cloud_id": 0,
                            "status": 9,  # 成功
                            "exit_code": 0,
                        }
                    ],
                }
            ],
        }

        # Mock Job API - batch_get_job_instance_ip_log 返回日志
        mock_batch_get_ip_log.return_value = {
            "script_task_logs": [
                {
                    "bk_host_id": 10001,
                    "ip": "192.168.1.1",
                    "bk_cloud_id": 0,
                    "log_content": '---result---\n{"error_code": 0, "message": "success"}',
                }
            ]
        }

        manager = TaskManager(task=http_task)
        first_node = http_task.nodes.first()  # pyright: ignore[reportOptionalMemberAccess]
        result = manager.test(node_id_list=[first_node.pk] if first_node else [])

        # 验证 fast_execute_script 被调用
        mock_fast_execute.assert_called_once()
        call_args = mock_fast_execute.call_args

        # 验证参数中的业务ID
        params = call_args.kwargs["params"]
        # params 可能是对象或字典，统一处理
        bk_biz_id = params.bk_biz_id if hasattr(params, "bk_biz_id") else params.get("bk_biz_id")
        script_content = params.script_content if hasattr(params, "script_content") else params.get("script_content")

        assert bk_biz_id == http_task.bk_biz_id, "传递的业务ID应与任务一致"

        # 验证脚本内容被正确编码（base64）
        assert isinstance(script_content, str), "脚本内容应为字符串"
        decoded_script = b64decode(script_content).decode("utf-8")
        assert len(decoded_script) > 0, "解码后的脚本内容不应为空"

        # 验证返回值是预期的成功消息
        expected_result = RESULT_MSG["0"]
        assert result == expected_result, f"期望返回 '{expected_result}'，但得到 '{result}'"

        # 验证 plugin_search 被调用
        assert mock_plugin_search.call_count == 2
