"""
拨测采集器管理

负责拨测任务的配置生成、测试下发等功能
"""

import logging
import ntpath
import posixpath
import time
from base64 import b64encode
from collections import defaultdict
from typing import Any, TypedDict, cast, final

from bkmonitor.nodeman_integration.backend import node_man_backend
from jinja2.sandbox import SandboxedEnvironment as JinjaEnvironment

from bk_monitor_base.config import get_config
from bk_monitor_base.domains.uptime_check.constants import (
    COLLECTOR_NAME,
    DEFAULT_MAX_TIMEOUT,
    DEFAULT_UPTIMECHECK_OUTPUT_FIELDS,
    UptimeCheckProtocol,
)
from bk_monitor_base.domains.uptime_check.services.config_generator import ConfigGeneratorService
from bk_monitor_base.infras.declaratives.constants import TargetNodeType
from bk_monitor_base.infras.third_party_api.cmdb.api import (
    HostIPParams,
    HostPropertyFilter,
    HostTopoItem,
    get_host_by_ip,
    get_host_by_template,
    list_biz_all_hosts_topo,
    list_hosts_without_biz,
)
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.infras.third_party_api.job.api import (
    JOB_STEP_RUNNING_STATUS,
    JOB_STEP_SUCCESS_STATUS,
    FastExecuteScriptParams,
    JobTargetIpInfo,
    batch_get_job_instance_ip_log,
    fast_execute_script,
    get_job_instance_status,
)
from bk_monitor_base.infras.third_party_api.nodeman import api as node_man_v2_api

logger = logging.getLogger(__name__)


class _SystemInfo(TypedDict):
    """主机系统执行参数。"""

    os_type: str
    script_language: int
    account_alias: str


class _TaskGroup(TypedDict):
    """按系统与安装路径聚合后的执行分组。"""

    system: _SystemInfo
    setup_path: str
    hosts: list[dict[str, Any]]


@final
class UptimeCheckCollector:
    """
    拨测采集器

    用于生成拨测任务配置并支持测试下发
    """

    COLLECTOR_NAME = COLLECTOR_NAME
    DIVIDE_SYMBOL = "=======bkmonitor======="
    LINUX_DOWNLOAD_PATH = "/tmp/bkdata/download/"
    TEST_CONFIG_FILE_NAME = "test_bkmonitorbeat.yml"
    SYSTEM_INFO: dict[str, _SystemInfo] = {
        "linux": {"os_type": "linux", "script_language": 1, "account_alias": "root"},
        "aix": {"os_type": "aix", "script_language": 1, "account_alias": "root"},
        "windows": {"os_type": "windows", "script_language": 2, "account_alias": "system"},
    }
    OS_TYPE_CODE_MAP: dict[str, str] = {"1": "linux", "2": "windows", "3": "aix"}

    def __init__(self, bk_biz_id: int, operator: str | None = None):
        """
        初始化采集器

        Args:
            bk_biz_id: 业务ID
            operator: 操作者
        """
        self.bk_biz_id = bk_biz_id
        self.operator = operator
        self.config_generator = ConfigGeneratorService()

    def generate_uptimecheck_config(
        self,
        task: dict[str, Any],
        data_id: int | None = None,
        max_timeout: int = DEFAULT_MAX_TIMEOUT,
    ) -> str:
        """
        生成拨测配置文件

        Args:
            task: 任务配置字典,包含 protocol 和 config 字段
            data_id: 数据ID,如果未指定则使用默认值
            max_timeout: 最大超时时间(毫秒)

        Returns:
            生成的配置文件内容

        Raises:
            ValueError: 不支持的协议类型
            KeyError: 缺少必要的配置字段
        """
        protocol = task.get("protocol")
        config = task.get("config")

        if not protocol:
            raise KeyError("Task must have 'protocol' field")

        if not config:
            raise KeyError("Task must have 'config' field")

        # 第一步: 将业务配置转换为bkmonitorbeat任务格式
        task_configs = self.config_generator.generate_sub_config(
            protocol=protocol,
            config=config,
            test=True,
        )
        if not task_configs:
            raise ValueError("生成拨测任务配置失败：task_configs 为空")

        # 第二步: 使用Jinja2模板渲染完整的beat配置文件
        return self.config_generator.generate_config(
            protocol=protocol,
            # generate_config 会自动包装成 tasks=[config]，这里传入单个 task 即可
            config=task_configs[0],
            data_id=data_id,
            max_timeout=max_timeout,
        )

    def test(
        self,
        bk_tenant_id: str,
        task: dict[str, Any],
        hosts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        测试拨测配置

        Args:
            task: 任务配置
            hosts: 测试主机列表
            bk_tenant_id: 租户ID，用于调用Job API

        Returns:
            测试结果字典,包含 success 和 failed 字段

        Note:
            此方法通过Job API下发测试脚本，执行一次数据采集并返回结果
        """
        # 如果是动态拓扑，转化为主机
        node_ip_list = []
        if task.get("config", {}).get("node_list", []):
            node_ip_list = self._convert_topo_to_hosts(
                bk_biz_id=task["bk_biz_id"],
                node_list=task["config"]["node_list"],
                output_fields=task["config"].get("output_fields"),
                bk_tenant_id=bk_tenant_id,
            )
            # 清空 node_list，避免重复处理
            task["config"]["node_list"] = []
        # 将转换后的 IP 添加到 ip_list
        task["config"]["ip_list"] = task["config"].get("ip_list", []) + node_ip_list

        # 检查目标服务是否为空
        if not task.get("config", {}).get("ip_list", []) and not task.get("config", {}).get("url_list", []):
            from bk_monitor_base.infras.exception.base_error import BaseError

            raise BaseError("节点测试失败: 目标服务为空")

        # 生成配置
        config_content = self.generate_uptimecheck_config(task)

        logger.info(
            f"Generated uptime check config for task (bk_biz_id={self.bk_biz_id}, protocol={task.get('protocol')})"
        )

        # 如果没有提供hosts，返回配置内容
        if not hosts:
            return {
                "success": [],
                "failed": [],
                "config": config_content,
            }

        result = self._fast_execute_script(
            bk_tenant_id=bk_tenant_id,
            hosts=hosts,
            test_config_yml=config_content,
        )
        result = self.fetch_content(result)
        result = self.label_failed_ip(result, "测试任务失败")
        result["config"] = config_content

        return result

    def fetch_content(self, result: dict[str, Any]) -> dict[str, Any]:
        """按分隔符裁剪脚本输出，保留采集器真实结果。"""
        for success_item in result.get("success", []):
            log_content = success_item.get("log_content", "")
            if isinstance(log_content, str) and self.DIVIDE_SYMBOL in log_content:
                success_item["log_content"] = log_content.split(self.DIVIDE_SYMBOL, 1)[1].strip()
        return result

    def label_failed_ip(self, task_result: dict[str, Any], label: str) -> dict[str, Any]:
        """给失败结果补充统一错误前缀，便于前端与日志定位。"""
        failed_hosts = task_result.get("failed", [])
        for host in failed_hosts:
            host["errmsg"] = f"[{self.COLLECTOR_NAME}] {label}: {host.get('errmsg', '')}"
        if failed_hosts:
            logger.warning("Execute job task failed: result = %s", task_result)
        return task_result

    def _fast_execute_script(
        self,
        bk_tenant_id: str,
        hosts: list[dict[str, Any]],
        test_config_yml: str,
    ) -> dict[str, Any]:
        """按系统分组下发测试脚本并合并执行结果。"""
        task_groups, error_hosts = self._separate_hosts_by_system_and_path(bk_tenant_id=bk_tenant_id, hosts=hosts)
        merged_result: dict[str, Any] = {"success": [], "pending": [], "failed": error_hosts}

        for group in task_groups:
            script_content = self._render_test_script(
                os_type=group["system"]["os_type"],
                setup_path=group["setup_path"],
                test_config_yml=test_config_yml,
            )
            # Job fast_execute_script 要求脚本内容使用 base64 编码，避免服务端解码异常导致脚本乱码。
            script_content_base64 = b64encode(script_content.encode("utf-8")).decode("utf-8")
            target_server = self._build_target_server(group["hosts"])

            try:
                job_result = fast_execute_script(
                    bk_tenant_id=bk_tenant_id,
                    params=FastExecuteScriptParams(
                        bk_biz_id=self.bk_biz_id,
                        script_content=script_content_base64,
                        script_language=group["system"]["script_language"],
                        target_server=target_server,
                        account_alias=group["system"]["account_alias"],
                        timeout=300,
                    ),
                )
            except BkApiError as error:
                logger.error("执行测试脚本失败: %s", error, exc_info=True)
                group_failed = [
                    {
                        "bk_host_id": host.get("bk_host_id"),
                        "ip": host.get("ip"),
                        "bk_cloud_id": host.get("bk_cloud_id", host.get("plat_id", 0)),
                        "errmsg": str(error),
                    }
                    for host in group["hosts"]
                ]
                self._merge_task_result(merged_result, {"success": [], "pending": [], "failed": group_failed})
                continue

            group_result = self._fetch_job_result(
                bk_tenant_id=bk_tenant_id,
                job_instance_id=job_result["job_instance_id"],
                step_instance_id=job_result["step_instance_id"],
                fallback_hosts=group["hosts"],
            )
            self._merge_task_result(merged_result, group_result)

        return merged_result

    def _build_target_server(self, hosts: list[dict[str, Any]]) -> dict[str, Any]:
        """将主机列表转换为 JOB 目标参数。"""
        ip_list: list[JobTargetIpInfo] = []
        host_id_list: list[int] = []
        for host in hosts:
            if host.get("bk_host_id"):
                host_id_list.append(int(host["bk_host_id"]))
            elif host.get("ip"):
                ip_list.append(
                    {
                        "ip": host["ip"],
                        "bk_cloud_id": int(host.get("bk_cloud_id", host.get("plat_id", 0))),
                    }
                )

        target_server: dict[str, Any] = {}
        if host_id_list:
            target_server["host_id_list"] = host_id_list
        if ip_list:
            target_server["ip_list"] = ip_list
        return target_server

    def _render_test_script(self, os_type: str, setup_path: str, test_config_yml: str) -> str:
        """渲染测试脚本模板。"""
        if os_type == "windows":
            download_path = ntpath.join(get_config().blueking.gse.gse_path_variable_windows, "download")
            test_config_file_path = ntpath.join(download_path, self.TEST_CONFIG_FILE_NAME)
            final_setup_path = ntpath.join(
                setup_path or get_config().blueking.gse.gse_path_variable_windows, "plugins", "bin"
            )
            template_content = self._get_windows_script_template()
        else:
            download_path = self.LINUX_DOWNLOAD_PATH
            test_config_file_path = posixpath.join(download_path, self.TEST_CONFIG_FILE_NAME)
            final_setup_path = posixpath.join(
                setup_path or get_config().blueking.gse.gse_path_variable_linux, "plugins", "bin"
            )
            template_content = self._get_linux_script_template()

        context = {
            "divide_symbol": self.DIVIDE_SYMBOL,
            "test_config_file_path": test_config_file_path,
            "test_config_yml": test_config_yml,
            "setup_path": final_setup_path,
            "download_path": download_path,
        }
        # 使用 Jinja2 渲染脚本模板，与原实现保持一致，避免 Django Template 的 HTML 自动转义
        return JinjaEnvironment().from_string(template_content).render(context)

    @staticmethod
    def _get_linux_script_template() -> str:
        """获取 Linux/AIX 脚本模板。"""
        return """#!/bin/bash
echo "{{ divide_symbol }}"
mkdir -p {{ download_path }}

cat << 'EOF' > {{ test_config_file_path }}
{{ test_config_yml }}
EOF

cd {{ setup_path }}
./bkmonitorbeat -T  -c {{ test_config_file_path }}
code=$?

# rm -f {{ test_config_file_path }}  >/dev/null 2>&1

exit $code
"""

    @staticmethod
    def _get_windows_script_template() -> str:
        """获取 Windows 脚本模板。"""
        return r"""@echo off
echo {{ divide_symbol }}
if not exist {{ download_path }} md {{ download_path }}

(
{% for line in test_config_yml.splitlines() %}
{% if line %}echo {{ line }}{% endif %}{% endfor %}
) >{{ test_config_file_path }}

cd {{ setup_path }}

bkmonitorbeat.exe -T  -c {{ test_config_file_path }} || exit 1
"""

    def _fetch_job_result(
        self,
        bk_tenant_id: str,
        job_instance_id: int,
        step_instance_id: int,
        fallback_hosts: list[dict[str, Any]] | None = None,
        max_wait_time: int = 300,
    ) -> dict[str, Any]:
        """查询 JOB 任务结果并转换为 success/pending/failed 结构。"""
        host_id_list: list[int] = []
        ip_list: list[JobTargetIpInfo] = []
        for host in fallback_hosts or []:
            if host.get("bk_host_id"):
                host_id_list.append(int(host["bk_host_id"]))
                continue
            if host.get("ip"):
                ip_list.append(
                    {
                        "ip": str(host["ip"]),
                        "bk_cloud_id": int(host.get("bk_cloud_id", host.get("plat_id", 0))),
                    }
                )

        start_time = time.time()
        status_result: Any = None
        while time.time() - start_time < max_wait_time:
            status_result = get_job_instance_status(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=self.bk_biz_id,
                job_instance_id=job_instance_id,
                return_ip_result=True,
                host_id_list=host_id_list or None,
                ip_list=ip_list or None,
            )
            if status_result.get("finished"):
                break
            time.sleep(2)

        if status_result is None:
            status_result = get_job_instance_status(
                bk_tenant_id=bk_tenant_id,
                bk_biz_id=self.bk_biz_id,
                job_instance_id=job_instance_id,
                return_ip_result=True,
                host_id_list=host_id_list or None,
                ip_list=ip_list or None,
            )
        assert status_result is not None

        result: dict[str, Any] = {"success": [], "pending": [], "failed": []}
        step_instances = status_result.get("step_instance_list", [])
        for step_instance in step_instances:
            if step_instance.get("step_instance_id") != step_instance_id:
                continue
            step_status = int(step_instance.get("status", 0))
            ip_infos: list[dict[str, Any]] = cast(
                list[dict[str, Any]],
                step_instance.get("ip_list") or step_instance.get("step_ip_result_list") or [],
            )
            if not ip_infos:
                err_msg = f"JOB步骤未返回主机执行详情，step_status={step_status}"
                for host in fallback_hosts or []:
                    result["failed"].append(
                        {
                            "ip": str(host.get("ip", "")),
                            "bk_host_id": host.get("bk_host_id"),
                            "bk_cloud_id": int(host.get("bk_cloud_id", host.get("plat_id", 0))),
                            "errmsg": err_msg,
                        }
                    )
                if not fallback_hosts:
                    result["failed"].append({"errmsg": err_msg})
                continue

            query_host_id_list: list[int] = []
            query_ip_list: list[JobTargetIpInfo] = []
            for ip_info in ip_infos:
                raw_host_id = ip_info.get("bk_host_id", ip_info.get("host_id"))
                if raw_host_id:
                    query_host_id_list.append(int(raw_host_id))
                    continue

                ip = str(ip_info.get("ip", ""))
                if not ip:
                    continue

                query_ip_list.append(
                    {
                        "ip": ip,
                        "bk_cloud_id": int(ip_info.get("bk_cloud_id", 0)),
                    }
                )

            host_log_content_map: dict[int, str] = {}
            ip_log_content_map: dict[str, str] = {}
            try:
                batch_log_result = batch_get_job_instance_ip_log(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=self.bk_biz_id,
                    job_instance_id=job_instance_id,
                    step_instance_id=step_instance_id,
                    host_id_list=query_host_id_list or None,
                    ip_list=query_ip_list or None,
                )
            except Exception as error:
                logger.error(
                    "批量获取作业日志失败: job_instance_id=%s, step_instance_id=%s, error=%s",
                    job_instance_id,
                    step_instance_id,
                    error,
                    exc_info=True,
                )
                for ip_info in ip_infos:
                    ip = str(ip_info.get("ip", ""))
                    bk_cloud_id = int(ip_info.get("bk_cloud_id", 0))
                    raw_host_id = ip_info.get("bk_host_id", ip_info.get("host_id"))
                    result["failed"].append(
                        {
                            "ip": ip,
                            "bk_host_id": int(raw_host_id) if raw_host_id else None,
                            "bk_cloud_id": bk_cloud_id,
                            "errmsg": "获取日志异常",
                        }
                    )
                continue

            script_task_logs = cast(list[dict[str, Any]], batch_log_result.get("script_task_logs") or [])
            file_task_logs = cast(list[dict[str, Any]], batch_log_result.get("file_task_logs") or [])
            for log_item in [*script_task_logs, *file_task_logs]:
                raw_host_id = log_item.get("bk_host_id", log_item.get("host_id"))
                ip = str(log_item.get("ip", ""))
                bk_cloud_id = int(log_item.get("bk_cloud_id", 0))
                if "log_content" in log_item:
                    log_content = str(log_item.get("log_content", ""))
                else:
                    file_logs = cast(list[dict[str, Any]], log_item.get("file_logs") or [])
                    log_content = "\n".join(
                        str(file_log.get("log_content", "")) for file_log in file_logs if file_log.get("log_content")
                    )

                if raw_host_id:
                    host_log_content_map[int(raw_host_id)] = log_content
                if ip:
                    ip_log_content_map[f"{ip}|{bk_cloud_id}"] = log_content

            for ip_info in ip_infos:
                ip = str(ip_info.get("ip", ""))
                bk_cloud_id = int(ip_info.get("bk_cloud_id", 0))
                raw_host_id = ip_info.get("bk_host_id", ip_info.get("host_id"))
                bk_host_id = int(raw_host_id) if raw_host_id else None
                log_content = ""
                if bk_host_id is not None:
                    log_content = host_log_content_map.get(bk_host_id, "")
                if not log_content and ip:
                    log_content = ip_log_content_map.get(f"{ip}|{bk_cloud_id}", "")

                host_result: dict[str, Any] = {
                    "ip": ip,
                    "bk_host_id": bk_host_id,
                    "bk_cloud_id": bk_cloud_id,
                    "log_content": log_content,
                }
                if step_status in JOB_STEP_SUCCESS_STATUS:
                    result["success"].append(host_result)
                elif step_status in JOB_STEP_RUNNING_STATUS:
                    result["pending"].append(host_result)
                else:
                    result["failed"].append(
                        {
                            "ip": ip,
                            "bk_host_id": bk_host_id,
                            "bk_cloud_id": bk_cloud_id,
                            "errmsg": log_content,
                        }
                    )
        return result

    @staticmethod
    def _merge_task_result(merged_result: dict[str, Any], task_result: dict[str, Any]) -> None:
        """合并分组执行结果。"""
        merged_result["success"].extend(task_result.get("success", []))
        merged_result["pending"].extend(task_result.get("pending", []))
        merged_result["failed"].extend(task_result.get("failed", []))

    def _separate_hosts_by_system_and_path(
        self,
        bk_tenant_id: str,
        hosts: list[dict[str, Any]],
    ) -> tuple[list[_TaskGroup], list[dict[str, Any]]]:
        """按操作系统与 agent 安装路径拆分主机。"""
        query_host_ids: list[int] = []
        query_ips: list[HostIPParams] = []
        for host in hosts:
            if host.get("bk_host_id"):
                query_host_ids.append(int(host["bk_host_id"]))
                continue

            ip = host.get("ip")
            if not ip:
                continue
            query_ips.append(
                HostIPParams(
                    ip=str(ip),
                    bk_cloud_id=int(host.get("bk_cloud_id", host.get("plat_id", -1))),
                )
            )

        biz_hosts = get_host_by_ip(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=self.bk_biz_id,
            bk_host_ids=list(set(query_host_ids)) if query_host_ids else None,
            ips=query_ips or None,
            fields=[
                "bk_host_id",
                "bk_host_innerip",
                "bk_host_innerip_v6",
                "bk_cloud_id",
                "bk_os_type",
                "bk_os_type_name",
            ],
        )
        ip_os_dict: dict[int | str, str] = {}
        host_key_dict: dict[str, int] = {}
        for host in biz_hosts:
            os_type = self._normalize_os_type(
                os_type_name=getattr(host, "bk_os_type_name", ""),
                os_type_code=getattr(host, "bk_os_type", ""),
            )
            ip_os_dict[int(host.bk_host_id)] = os_type
            if host.bk_host_innerip:
                key = f"{host.bk_host_innerip}|{host.bk_cloud_id}"
                ip_os_dict[key] = os_type
                host_key_dict[key] = int(host.bk_host_id)
            if host.bk_host_innerip_v6:
                key_v6 = f"{host.bk_host_innerip_v6}|{host.bk_cloud_id}"
                ip_os_dict[key_v6] = os_type
                host_key_dict[key_v6] = int(host.bk_host_id)

        bk_host_ids: list[int] = []
        for host in hosts:
            if host.get("bk_host_id"):
                bk_host_ids.append(int(host["bk_host_id"]))
            else:
                key = f"{host['ip']}|{host.get('bk_cloud_id', host.get('plat_id', 0))}"
                resolved_host_id = host_key_dict.get(key)
                if resolved_host_id is not None:
                    bk_host_ids.append(int(resolved_host_id))

        host_info: list[dict[str, Any]] = []
        if bk_host_ids:
            if node_man_backend.is_v3:
                host_info = cast(
                    list[dict[str, Any]],
                    node_man_backend.v3.plugin_search_host_status(
                        bk_tenant_id=bk_tenant_id,
                        bk_host_ids=list(set(bk_host_ids)),
                        plugin_names=["bkmonitorbeat"],
                    ),
                )
            else:
                host_info = cast(
                    list[dict[str, Any]],
                    node_man_v2_api.plugin_search(
                        bk_tenant_id=bk_tenant_id,
                        params=node_man_v2_api.PluginSearchParams(
                            page=1,
                            pagesize=max(len(bk_host_ids), 1),
                            conditions=[],
                            bk_host_id=list(set(bk_host_ids)),
                        ),
                    ).get("list", []),
                )
        host_path_dict: dict[int | str, str] = {}
        for host in host_info:
            setup_path = host.get("setup_path")
            if not setup_path:
                plugin_statuses = cast(list[dict[str, Any]], host.get("plugin_status") or [])
                beat_status: dict[str, Any] = next(
                    (status for status in plugin_statuses if status.get("name") == "bkmonitorbeat"),
                    cast(dict[str, Any], {}),
                )
                setup_path = beat_status.get("setup_path")
            if not setup_path:
                continue
            setup_path_str = str(setup_path)
            host_path_dict[int(host["bk_host_id"])] = setup_path_str
            host_path_dict[f"{host.get('inner_ip', '')}|{host.get('bk_cloud_id', 0)}"] = setup_path_str

        grouped: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        error_hosts: list[dict[str, Any]] = []
        for host in hosts:
            if host.get("bk_host_id"):
                host_id: int | str = int(host["bk_host_id"])
                host_dict = {"bk_host_id": int(host["bk_host_id"])}
                host_name = f"bk_host_id:{host_id}"
            else:
                ip = str(host["ip"])
                bk_cloud_id = int(host.get("bk_cloud_id", host.get("plat_id", 0)))
                host_id = f"{ip}|{bk_cloud_id}"
                host_dict = {"ip": ip, "bk_cloud_id": bk_cloud_id}
                host_name = host_id

            if host_id not in ip_os_dict:
                error_hosts.append({"errmsg": f"{host_name} 主机不属于该业务", **host_dict})
                continue
            os_type = str(ip_os_dict.get(host_id, "")).lower()
            if not os_type:
                error_hosts.append({"errmsg": f"{host_name} 操作系统类型不能为空", **host_dict})
                continue
            if os_type not in self.SYSTEM_INFO:
                error_hosts.append({"errmsg": f"{host_name} 不支持的操作系统类型：{os_type}", **host_dict})
                continue

            setup_path = str(host_path_dict.get(host_id, ""))
            grouped[(os_type, setup_path)].append(host_dict)

        task_groups: list[_TaskGroup] = []
        for (os_type, setup_path), grouped_hosts in grouped.items():
            task_groups.append({"system": self.SYSTEM_INFO[os_type], "setup_path": setup_path, "hosts": grouped_hosts})
        return task_groups, error_hosts

    @classmethod
    def _normalize_os_type(cls, os_type_name: Any, os_type_code: Any) -> str:
        """标准化操作系统类型，兼容 CMDB 的名称与数字编码。"""
        raw_value = str(os_type_name or os_type_code or "").strip().lower()
        if not raw_value:
            return ""
        if raw_value in cls.SYSTEM_INFO:
            return raw_value
        if raw_value in cls.OS_TYPE_CODE_MAP:
            return cls.OS_TYPE_CODE_MAP[raw_value]
        if "windows" in raw_value or raw_value.startswith("win"):
            return "windows"
        if "linux" in raw_value:
            return "linux"
        if "aix" in raw_value:
            return "aix"
        return raw_value

    def _convert_topo_to_hosts(
        self,
        bk_tenant_id: str,
        bk_biz_id: int,
        node_list: list[dict[str, Any]],
        output_fields: list[str] | None = None,
    ) -> list[str]:
        """
        将动态拓扑或模板转换为主机IP列表

        Args:
            bk_biz_id: 业务ID
            node_list: 节点列表，每个节点包含 bk_obj_id 和 bk_inst_id
            output_fields: 输出字段列表，默认为 ["bk_host_innerip", "bk_host_innerip_v6"]
            bk_tenant_id: 租户ID

        Returns:
            IP列表
        """

        if not output_fields:
            output_fields = DEFAULT_UPTIMECHECK_OUTPUT_FIELDS

        new_hosts: list[str] = []
        if not node_list:
            return new_hosts

        host_dicts: list[dict[str, Any]] = []
        # 如果第一个元素有 bk_obj_id，说明是拓扑或模板
        if node_list[0].get("bk_obj_id"):
            bk_obj_id = node_list[0]["bk_obj_id"]

            # 处理模板类型
            if bk_obj_id in [TargetNodeType.SET_TEMPLATE, TargetNodeType.SERVICE_TEMPLATE]:
                bk_inst_ids = [node["bk_inst_id"] for node in node_list]
                # 模板：通过模板获取主机
                template_results: list[HostTopoItem] = get_host_by_template(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    bk_obj_id=bk_obj_id,
                    template_ids=bk_inst_ids,
                    fields=output_fields if output_fields else None,
                )
                host_dicts.extend([dict(result["host"]) for result in template_results])
            else:
                # 动态拓扑：获取业务下所有主机，然后过滤
                _, hosts = list_biz_all_hosts_topo(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=bk_biz_id,
                    fields=["bk_host_id", "bk_host_innerip", "bk_cloud_id", "bk_host_innerip_v6"],
                )

                # 将主机数据统一转换为字典格式，便于处理
                # 注意：bk_set_ids 和 bk_module_ids 需要从 topo 结构中提取
                biz_hosts: list[dict[str, Any]] = []
                for host_item in hosts:
                    # 从 topo 结构中提取 set_ids 和 module_ids
                    bk_set_ids: list[int] = []
                    bk_module_ids: list[int] = []
                    for topo_set in host_item.get("topo", []):
                        bk_set_ids.append(topo_set["bk_set_id"])
                        for topo_module in topo_set.get("module", []):
                            bk_module_ids.append(topo_module["bk_module_id"])

                    biz_hosts.append(
                        {
                            "bk_host_id": host_item["host"]["bk_host_id"],
                            "bk_host_innerip": host_item["host"].get("bk_host_innerip", ""),
                            "bk_host_innerip_v6": host_item["host"].get("bk_host_innerip_v6", ""),
                            "bk_cloud_id": host_item["host"].get("bk_cloud_id", 0),
                            "bk_set_ids": bk_set_ids,
                            "bk_module_ids": bk_module_ids,
                        }
                    )

                for node in node_list:
                    bk_obj_id = node["bk_obj_id"]
                    bk_inst_id = node["bk_inst_id"]

                    if bk_obj_id == "biz":
                        # 业务：返回所有主机
                        filtered_hosts = biz_hosts
                    elif bk_obj_id == "set":
                        # 集群：过滤属于该集群的主机
                        filtered_hosts = [host for host in biz_hosts if bk_inst_id in host.get("bk_set_ids", [])]
                    elif bk_obj_id == "module":
                        # 模块：过滤属于该模块的主机
                        filtered_hosts = [host for host in biz_hosts if bk_inst_id in host.get("bk_module_ids", [])]
                    else:
                        logger.warning(f"不支持的节点类型: {bk_obj_id}")
                        filtered_hosts = []
                    host_dicts.extend(filtered_hosts)
        else:
            # 没有 bk_obj_id，使用 bk_host_id 查询
            bk_host_ids = [node.get("bk_host_id") for node in node_list if node.get("bk_host_id")]
            if bk_host_ids:
                # 分批查询，每批最多500条（CMDB API 限制）
                batch_size = 500
                for start in range(0, len(bk_host_ids), batch_size):
                    batch_host_ids = bk_host_ids[start : start + batch_size]
                    # 构建主机ID过滤条件
                    host_property_filter: HostPropertyFilter = {
                        "condition": "OR",
                        "rules": [{"field": "bk_host_id", "operator": "in", "value": batch_host_ids}],
                    }
                    _, batch_hosts = list_hosts_without_biz(
                        bk_tenant_id=bk_tenant_id,
                        page={"start": 0, "limit": batch_size},
                        host_property_filter=host_property_filter,
                        fields=["bk_host_id", "bk_host_innerip", "bk_host_innerip_v6", "bk_cloud_id"],
                    )
                    host_dicts.extend([host.model_dump() for host in batch_hosts])

        # 提取输出字段
        for host in host_dicts:
            for field in output_fields:
                value = host.get(field)
                if value:
                    new_hosts.append(str(value))

        return new_hosts

    def validate_task_config(self, task: dict[str, Any]) -> tuple[bool, str]:
        """
        验证任务配置的有效性

        Args:
            task: 任务配置字典

        Returns:
            (是否有效, 错误消息)
        """
        # 检查必要字段
        if "protocol" not in task:
            return False, "Missing required field: protocol"

        if "config" not in task:
            return False, "Missing required field: config"

        protocol = task["protocol"]
        config = task["config"]

        # 验证协议类型
        try:
            UptimeCheckProtocol(protocol.upper())
        except ValueError:
            return False, f"Invalid protocol: {protocol}"

        # 验证配置字段
        if not isinstance(config, dict):
            return False, "Config must be a dictionary"

        # 根据协议验证特定字段
        protocol_upper = protocol.upper()

        if protocol_upper == UptimeCheckProtocol.HTTP:
            if "steps" not in config:
                return False, "HTTP protocol requires 'steps' in config"

        elif protocol_upper in [UptimeCheckProtocol.TCP, UptimeCheckProtocol.UDP]:
            if "target_host_list" not in config and "ip_list" not in config:
                return False, f"{protocol_upper} protocol requires 'target_host_list' or 'ip_list' in config"

            if "target_port" not in config:
                return False, f"{protocol_upper} protocol requires 'target_port' in config"

        elif protocol_upper == UptimeCheckProtocol.ICMP:
            if "target_host_list" not in config and "ip_list" not in config:
                return False, "ICMP protocol requires 'target_host_list' or 'ip_list' in config"

        return True, ""
