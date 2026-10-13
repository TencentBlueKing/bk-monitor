"""
testtaskresult 兼容性测试。

本文件聚焦两类行为：
1. 采集器测试脚本生成与日志分隔符裁剪语义；
2. TaskManager.test 的新旧错误码提示、ICMP 日志结构和节点失败隔离。
"""

import base64
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from bk_monitor_base.domains.uptime_check.constants import (
    DEFAULT_UPTIMECHECK_OUTPUT_FIELDS,
    RESULT_MSG,
    UDP_RESULT_MSG,
)
from bk_monitor_base.domains.uptime_check.models import UptimeCheckNodeModel, UptimeCheckTaskModel
from bk_monitor_base.domains.uptime_check.services.task_manager import (
    TaskManager,
    UptimeCheckCollector,
)
from bk_monitor_base.domains.uptime_check.services.task_manager import (
    TestTaskError as UptimeCheckTestTaskError,
)
from bk_monitor_base.infras.declaratives.constants import TargetNodeType

pytestmark = pytest.mark.django_db(databases=["default"])


class TestCollectorScriptGeneration:
    """测试采集器脚本生成与日志裁剪行为。"""

    def test_render_test_script_linux_contains_legacy_steps(self):
        """Linux 脚本应包含 legacy 关键步骤。"""
        collector = UptimeCheckCollector(bk_biz_id=2)

        script = collector._render_test_script(
            os_type="linux",
            setup_path="/usr/local/gse",
            test_config_yml="a: 1\nb: 2",
        )

        assert 'echo "=======bkmonitor======="' in script
        assert "cat << 'EOF'" in script
        assert "cd /usr/local/gse/plugins/bin" in script
        assert "./bkmonitorbeat -T  -c /tmp/bkdata/download/test_bkmonitorbeat.yml" in script

    def test_render_test_script_windows_contains_legacy_steps(self):
        """Windows 脚本应包含 legacy 关键步骤。"""
        collector = UptimeCheckCollector(bk_biz_id=2)

        script = collector._render_test_script(
            os_type="windows",
            setup_path=r"C:\gse",
            test_config_yml="a: 1\nb: 2",
        )

        assert "echo =======bkmonitor=======" in script
        assert "if not exist C:\\gse\\download md C:\\gse\\download" in script
        assert "cd C:\\gse\\plugins\\bin" in script
        assert "bkmonitorbeat.exe -T  -c C:\\gse\\download\\test_bkmonitorbeat.yml" in script

    def test_fetch_content_should_trim_by_divide_symbol(self):
        """成功日志包含分隔符时，应仅保留分隔符之后内容。"""
        collector = UptimeCheckCollector(bk_biz_id=2)
        result = {
            "success": [{"log_content": 'prefix\n=======bkmonitor=======\n{"error_code":0}'}],
            "failed": [],
        }

        trimmed = collector.fetch_content(result)

        assert trimmed["success"][0]["log_content"] == '{"error_code":0}'

    def test_generate_uptimecheck_config_should_render_non_empty_http_task(self) -> None:
        """HTTP 测试配置应渲染出完整任务字段，避免 tasks 二次嵌套导致空值。"""
        collector = UptimeCheckCollector(bk_biz_id=2)
        task = {
            "bk_biz_id": 2,
            "protocol": "HTTP",
            "config": {
                "period": 60,
                "timeout": 3000,
                "response": "",
                "response_format": "nin",
                "method": "GET",
                "url_list": ["https://www.baidu.com"],
                "headers": [],
                "body": {"data_type": "default", "params": [], "content": "", "content_type": ""},
                "authorize": {"auth_type": "none", "auth_config": {}, "insecure_skip_verify": False},
                "query_params": [],
                "response_code": "",
            },
        }

        rendered = collector.generate_uptimecheck_config(task=task)

        assert "task_id: 0" in rendered
        assert "bk_biz_id: 0" in rendered
        assert "period: 60s" in rendered
        assert "steps:" in rendered
        http_task = yaml.safe_load(rendered)["bkmonitorbeat"]["http_task"]["tasks"][0]
        assert http_task["steps"][0]["url_list"] == ["https://www.baidu.com"]


class TestCollectorHostGrouping:
    """测试采集器主机分组的系统类型兼容行为。"""

    def test_separate_hosts_supports_numeric_os_type_code(self) -> None:
        """CMDB 返回数字编码时，应能映射到受支持系统类型。"""
        collector = UptimeCheckCollector(bk_biz_id=2)

        cmdb_hosts = [
            SimpleNamespace(
                bk_host_id=51983,
                bk_host_innerip="127.0.0.1",
                bk_host_innerip_v6="",
                bk_cloud_id=0,
                bk_os_type="1",
                bk_os_type_name="",
            )
        ]
        plugin_result = {"list": [{"bk_host_id": 51983, "inner_ip": "127.0.0.1", "bk_cloud_id": 0, "setup_path": ""}]}

        with (
            patch("bk_monitor_base.domains.uptime_check.collector.get_host_by_ip", return_value=cmdb_hosts),
            patch("bk_monitor_base.domains.uptime_check.collector.plugin_search", return_value=plugin_result),
        ):
            task_groups, error_hosts = collector._separate_hosts_by_system_and_path(
                bk_tenant_id="default",
                hosts=[{"bk_host_id": 51983}],
            )

        assert error_hosts == []
        assert len(task_groups) == 1
        assert task_groups[0]["system"]["os_type"] == "linux"
        assert task_groups[0]["hosts"] == [{"bk_host_id": 51983}]


class TestCollectorTopoConversion:
    """测试拓扑节点转换的默认输出字段行为。"""

    def test_convert_topo_to_hosts_should_use_current_default_output_fields_for_templates(self) -> None:
        """模板节点未显式传 output_fields 时，应返回默认的 IPv4/IPv6 地址列表。"""
        collector = UptimeCheckCollector(bk_biz_id=2)
        template_hosts = [
            {"host": {"bk_host_innerip": "127.0.0.1", "bk_host_innerip_v6": "", "bk_cloud_id": 0}},
            {"host": {"bk_host_innerip": "", "bk_host_innerip_v6": "::1", "bk_cloud_id": 0}},
        ]

        with patch(
            "bk_monitor_base.domains.uptime_check.collector.get_host_by_template",
            return_value=template_hosts,
        ) as mock_get_host_by_template:
            result = collector._convert_topo_to_hosts(
                bk_tenant_id="default",
                bk_biz_id=2,
                node_list=[{"bk_obj_id": TargetNodeType.SET_TEMPLATE, "bk_inst_id": 1}],
            )

        assert result == ["127.0.0.1", "::1"]
        assert mock_get_host_by_template.call_args.kwargs["fields"] == DEFAULT_UPTIMECHECK_OUTPUT_FIELDS

    def test_fetch_job_result_fallback_to_failed_when_ip_detail_missing(self) -> None:
        """JOB 未返回主机明细时，应该回填失败信息而不是返回空结果。"""
        collector = UptimeCheckCollector(bk_biz_id=2)
        status_result = {
            "finished": True,
            "step_instance_list": [
                {
                    "step_instance_id": 20046656067,
                    "status": 4,
                    "step_ip_result_list": None,
                }
            ],
        }

        with patch(
            "bk_monitor_base.domains.uptime_check.collector.get_job_instance_status", return_value=status_result
        ):
            result = collector._fetch_job_result(
                bk_tenant_id="default",
                job_instance_id=20038806241,
                step_instance_id=20046656067,
                fallback_hosts=[{"bk_host_id": 51983}],
            )

        assert result["success"] == []
        assert result["pending"] == []
        assert len(result["failed"]) == 1
        assert result["failed"][0]["bk_host_id"] == 51983
        assert "JOB步骤未返回主机执行详情" in result["failed"][0]["errmsg"]

    def test_fetch_job_result_should_request_ip_level_result(self) -> None:
        """查询 JOB 状态时应显式要求返回 IP 维度结果。"""
        collector = UptimeCheckCollector(bk_biz_id=2)
        status_result = {"finished": True, "step_instance_list": []}

        with patch(
            "bk_monitor_base.domains.uptime_check.collector.get_job_instance_status", return_value=status_result
        ) as mock_status:
            collector._fetch_job_result(
                bk_tenant_id="default",
                job_instance_id=20038806241,
                step_instance_id=20046656067,
                fallback_hosts=[{"bk_host_id": 51983}],
            )

        kwargs = mock_status.call_args.kwargs
        assert kwargs["return_ip_result"] is True
        assert kwargs["host_id_list"] == [51983]

    def test_fetch_job_result_should_use_batch_get_ip_log(self) -> None:
        """查询步骤日志时应使用批量接口，避免逐个 IP 拉取。"""
        collector = UptimeCheckCollector(bk_biz_id=2)
        status_result = {
            "finished": True,
            "step_instance_list": [
                {
                    "step_instance_id": 20046656067,
                    "status": 3,
                    "step_ip_result_list": [
                        {
                            "bk_host_id": 51983,
                            "ip": "127.0.0.1",
                            "bk_cloud_id": 0,
                        }
                    ],
                }
            ],
        }
        batch_log_result = {
            "script_task_logs": [
                {
                    "log_type": 1,
                    "bk_host_id": 51983,
                    "ip": "127.0.0.1",
                    "bk_cloud_id": 0,
                    "log_content": '{"error_code":0}',
                }
            ],
            "file_task_logs": None,
        }

        with (
            patch("bk_monitor_base.domains.uptime_check.collector.get_job_instance_status", return_value=status_result),
            patch(
                "bk_monitor_base.domains.uptime_check.collector.batch_get_job_instance_ip_log",
                return_value=batch_log_result,
            ) as mock_batch_log,
        ):
            result = collector._fetch_job_result(
                bk_tenant_id="default",
                job_instance_id=20038806241,
                step_instance_id=20046656067,
                fallback_hosts=[{"bk_host_id": 51983}],
            )

        assert result["pending"] == []
        assert result["failed"] == []
        assert len(result["success"]) == 1
        assert result["success"][0]["log_content"] == '{"error_code":0}'
        batch_kwargs = mock_batch_log.call_args.kwargs
        assert batch_kwargs["host_id_list"] == [51983]

    def test_fast_execute_script_should_base64_encode_script_content(self) -> None:
        """下发 JOB 脚本时应对 script_content 做 base64 编码。"""
        collector = UptimeCheckCollector(bk_biz_id=2)
        hosts = [{"bk_host_id": 51983}]
        task_groups = [
            {
                "system": {"os_type": "linux", "script_language": 1, "account_alias": "root"},
                "setup_path": "/usr/local/gse2_opbk",
                "hosts": hosts,
            }
        ]
        raw_script_content = "#!/bin/bash\necho test"

        with (
            patch.object(
                collector,
                "_separate_hosts_by_system_and_path",
                return_value=(task_groups, []),
            ),
            patch.object(collector, "_render_test_script", return_value=raw_script_content),
            patch(
                "bk_monitor_base.domains.uptime_check.collector.fast_execute_script",
                return_value={"job_instance_id": 1, "step_instance_id": 2},
            ) as mock_fast_execute_script,
            patch.object(
                collector,
                "_fetch_job_result",
                return_value={"success": [], "pending": [], "failed": []},
            ),
        ):
            collector._fast_execute_script(
                bk_tenant_id="default",
                hosts=hosts,
                test_config_yml="dummy: true",
            )

        params = mock_fast_execute_script.call_args.kwargs["params"]
        encoded_script_content = str(params["script_content"])
        assert base64.b64decode(encoded_script_content.encode("utf-8")).decode("utf-8") == raw_script_content


class TestTaskManagerTesttaskresult:
    """测试 TaskManager.test 的错误提示与成功判定。"""

    @pytest.fixture
    def task_with_node(self) -> tuple[UptimeCheckTaskModel, UptimeCheckNodeModel]:
        """创建合成任务与节点，由 pytest 数据库事务清理。"""
        task = UptimeCheckTaskModel.objects.create(
            bk_biz_id=2,
            name="testtaskresult-task",
            protocol=UptimeCheckTaskModel.Protocol.TCP,
            config={"period": 60, "ip_list": ["192.0.2.1"], "port": 80},
        )
        node = UptimeCheckNodeModel.objects.create(
            bk_tenant_id="default",
            bk_biz_id=2,
            name="node-a",
            ip="192.0.2.1",
            bk_host_id=1,
            plat_id=0,
            is_common=False,
        )
        task.nodes.add(node)  # pyright: ignore[reportAttributeAccessIssue]
        return task, node

    @staticmethod
    def _mock_plugin_search_result() -> dict:
        """返回可通过版本校验的插件结果。"""
        return {
            "list": [
                {
                    "plugin_status": [{"name": "bkmonitorbeat", "version": "3.5.0.1\n"}],
                    "inner_ip": "192.0.2.1",
                    "inner_ipv6": "",
                    "bk_cloud_id": 0,
                }
            ]
        }

    def _run_task_test(self, task: UptimeCheckTaskModel, collector_result: dict[str, Any]) -> str:
        """仅模拟下发与版本查询，执行实际的结果解析及节点查询。"""
        manager = TaskManager(task=task)
        with (
            patch.object(UptimeCheckNodeModel, "set_host_id", return_value=None),
            patch(
                "bk_monitor_base.domains.uptime_check.services.task_manager.plugin_search",
                return_value=self._mock_plugin_search_result(),
            ),
            patch(
                "bk_monitor_base.domains.uptime_check.services.task_manager.UptimeCheckCollector.test",
                return_value=collector_result,
            ),
        ):
            return manager.test()

    @staticmethod
    def _collector_result(node: UptimeCheckNodeModel, log_line: str) -> dict[str, Any]:
        """将合成日志封装为单节点采集器返回结构。"""
        return {
            "success": [{"bk_host_id": node.bk_host_id, "ip": node.ip, "log_content": log_line}],
            "failed": [],
        }

    @pytest.mark.parametrize(
        ("protocol", "log_line"),
        [
            (UptimeCheckTaskModel.Protocol.HTTP, '{"error_code":0}'),
            (UptimeCheckTaskModel.Protocol.TCP, '{"error_code":0}'),
            (UptimeCheckTaskModel.Protocol.UDP, '{"error_code":0}'),
            (UptimeCheckTaskModel.Protocol.ICMP, '{"dimensions":{"error_code":0}}'),
            (UptimeCheckTaskModel.Protocol.ICMP, '{"dimensions":{"error_code":"0"}}'),
        ],
    )
    def test_task_manager_test_success_returns_legacy_success_message(
        self, protocol: str, log_line: str, task_with_node: tuple[UptimeCheckTaskModel, UptimeCheckNodeModel]
    ) -> None:
        """各协议 error_code=0 时应继续返回原成功文案。"""
        task, node = task_with_node
        task.protocol = protocol

        assert self._run_task_test(task, self._collector_result(node, log_line)) == RESULT_MSG["0"]

    @pytest.mark.parametrize(
        ("protocol", "log_line", "expected_message"),
        [
            (
                UptimeCheckTaskModel.Protocol.TCP,
                '{"error_code":3002,"target_host":"synthetic-target","message":"tcp failed"}',
                "请确认响应内容是否正确（3002）",
            ),
            (
                UptimeCheckTaskModel.Protocol.UDP,
                '{"error_code":3002,"target_host":"synthetic-target","message":"udp failed"}',
                "响应内容匹配失败，请确认响应内容是否正确（3002）",
            ),
            (
                UptimeCheckTaskModel.Protocol.ICMP,
                '{"dimensions":{"error_code":"3002"},"target_host":"synthetic-target","message":"icmp failed"}',
                "请确认响应内容是否正确（3002）",
            ),
        ],
    )
    def test_task_manager_test_error_code_mapping(
        self,
        protocol: str,
        log_line: str,
        expected_message: str,
        task_with_node: tuple[UptimeCheckTaskModel, UptimeCheckNodeModel],
    ) -> None:
        """保留旧错误码提示，ICMP 只在 dimensions 提供错误码。"""
        task, node = task_with_node
        task.protocol = protocol
        with pytest.raises(UptimeCheckTestTaskError) as exc_info:
            self._run_task_test(task, self._collector_result(node, log_line))

        assert expected_message in str(exc_info.value)
        assert log_line not in str(exc_info.value)

    @pytest.mark.parametrize("protocol", ["HTTP", "TCP", "UDP"])
    @pytest.mark.parametrize(
        ("error_code", "expected_message"),
        [
            (1100, "请求失败，请确认网络/目标服务是否可访问（1100）"),
            (1101, "请求超时，请确认网络/目标服务是否可访问（1101）"),
            (1103, "请求参数错误，请检查任务配置（1103）"),
            (1200, "响应处理失败（1200）"),
            (1202, "响应不符合预期，请检查状态码或响应内容（1202）"),
            (1211, "未找到可用IP地址，请检查域名解析及IP类型配置（1211）"),
            (1213, "URL格式非法，请检查任务配置（1213）"),
            (1501, "临时文件写入失败，请检查节点文件权限或磁盘空间（1501）"),
            (2102, "IP地址非法，请检查任务配置（2102）"),
            (2501, "连接被拒绝，请确认目标端口及服务状态（2501）"),
        ],
    )
    def test_task_manager_test_collector_error_codes(
        self,
        protocol: str,
        error_code: int,
        expected_message: str,
        task_with_node: tuple[UptimeCheckTaskModel, UptimeCheckNodeModel],
    ) -> None:
        """HTTP、TCP 和 UDP 均能识别新采集器错误码，并保持测试失败。"""
        task, node = task_with_node
        task.protocol = protocol
        log_line = json.dumps({"error_code": error_code, "target_host": "synthetic-target", "message": "failed"})

        with pytest.raises(UptimeCheckTestTaskError) as exc_info:
            self._run_task_test(task, self._collector_result(node, log_line))

        assert expected_message in str(exc_info.value)
        assert log_line not in str(exc_info.value)

    @pytest.mark.parametrize("message", ["status code does not match", "response content does not match"])
    def test_task_manager_test_http_response_mismatch(
        self, message: str, task_with_node: tuple[UptimeCheckTaskModel, UptimeCheckNodeModel]
    ) -> None:
        """HTTP 状态码或内容校验失败共用 1202，提示需覆盖两种原因。"""
        task, node = task_with_node
        task.protocol = UptimeCheckTaskModel.Protocol.HTTP
        log_line = json.dumps({"error_code": 1202, "message": message})

        with pytest.raises(UptimeCheckTestTaskError) as exc_info:
            self._run_task_test(task, self._collector_result(node, log_line))

        assert "响应不符合预期，请检查状态码或响应内容（1202）" in str(exc_info.value)
        assert message in str(exc_info.value)

    @pytest.mark.parametrize("error_code", ["1000", "2000", "2003", "3001", "3002", "3007", "1004"])
    def test_task_manager_test_udp_mapping_priority(
        self, error_code: str, task_with_node: tuple[UptimeCheckTaskModel, UptimeCheckNodeModel]
    ) -> None:
        """UDP 优先保留专用旧提示，未单独定义的 DNS 错误使用通用提示。"""
        task, node = task_with_node
        task.protocol = UptimeCheckTaskModel.Protocol.UDP
        log_line = json.dumps({"error_code": int(error_code)})

        with pytest.raises(UptimeCheckTestTaskError) as exc_info:
            self._run_task_test(task, self._collector_result(node, log_line))

        assert str(UDP_RESULT_MSG.get(error_code, RESULT_MSG[error_code])) in str(exc_info.value)

    @pytest.mark.parametrize("protocol", ["HTTP", "TCP", "UDP", "ICMP"])
    def test_task_manager_test_unknown_error_code_returns_concise_message(
        self, protocol: str, task_with_node: tuple[UptimeCheckTaskModel, UptimeCheckNodeModel]
    ) -> None:
        """未知错误码继续判失败，提示包含码值且不附加原始 JSON。"""
        task, node = task_with_node
        task.protocol = protocol
        log_content: dict[str, Any] = {
            "target_host": "synthetic-target",
            "message": "unknown",
            "diagnostics": "synthetic-detail",
        }
        if protocol == UptimeCheckTaskModel.Protocol.ICMP:
            log_content["dimensions"] = {"error_code": "9999"}
        else:
            log_content["error_code"] = 9999
        raw_log = json.dumps(log_content)

        with pytest.raises(UptimeCheckTestTaskError) as exc_info:
            self._run_task_test(task, self._collector_result(node, raw_log))

        assert "采集器返回未知错误码（9999）" in str(exc_info.value)
        assert raw_log not in str(exc_info.value)
        assert "synthetic-detail" not in str(exc_info.value)

    def test_task_manager_test_icmp_uses_nested_error_code(
        self, task_with_node: tuple[UptimeCheckTaskModel, UptimeCheckNodeModel]
    ) -> None:
        """ICMP 顶层码与维度码冲突时，筛选和格式化都使用维度码。"""
        task, node = task_with_node
        task.protocol = UptimeCheckTaskModel.Protocol.ICMP
        log_line = '{"error_code":0,"dimensions":{"error_code":"1101"}}'

        with pytest.raises(UptimeCheckTestTaskError) as exc_info:
            self._run_task_test(task, self._collector_result(node, log_line))

        assert "请求超时，请确认网络/目标服务是否可访问（1101）" in str(exc_info.value)
        assert str(RESULT_MSG["0"]) not in str(exc_info.value)

    def test_task_manager_test_reports_all_failed_nodes(
        self, task_with_node: tuple[UptimeCheckTaskModel, UptimeCheckNodeModel]
    ) -> None:
        """一个未知码节点不阻断其余节点解析，健康节点不混入失败提示。"""
        task, healthy_node = task_with_node
        known_error_node = UptimeCheckNodeModel.objects.create(
            bk_tenant_id="default", bk_biz_id=2, name="node-b", ip="192.0.2.2", bk_host_id=2, plat_id=0
        )
        unknown_error_node = UptimeCheckNodeModel.objects.create(
            bk_tenant_id="default", bk_biz_id=2, name="node-c", ip="192.0.2.3", bk_host_id=3, plat_id=0
        )
        task.nodes.add(known_error_node, unknown_error_node)  # pyright: ignore[reportAttributeAccessIssue]
        collector_result: dict[str, Any] = {"success": [], "failed": []}
        for node, error_code in [(unknown_error_node, 9999), (healthy_node, 0), (known_error_node, 1202)]:
            collector_result["success"].extend(
                self._collector_result(node, json.dumps({"error_code": error_code}))["success"]
            )

        with pytest.raises(UptimeCheckTestTaskError) as exc_info:
            self._run_task_test(task, collector_result)

        error_message = str(exc_info.value)
        assert "node:node-b" in error_message
        assert "node:node-c" in error_message
        assert "node:node-a" not in error_message
        assert "响应不符合预期，请检查状态码或响应内容（1202）" in error_message
        assert "采集器返回未知错误码（9999）" in error_message
        assert '{"error_code"' not in error_message

    def test_task_manager_test_empty_collector_result_returns_no_response_error(
        self, task_with_node: tuple[UptimeCheckTaskModel, UptimeCheckNodeModel]
    ) -> None:
        """采集器返回空结果时，应该返回明确错误而非数组越界。"""
        task, _ = task_with_node
        collector_result: dict[str, Any] = {"success": [], "pending": [], "failed": []}

        with pytest.raises(UptimeCheckTestTaskError) as exc_info:
            self._run_task_test(task, collector_result)

        assert "采集器无返回" in str(exc_info.value)
