"""
拨测配置生成服务

负责根据协议类型和任务配置,生成 bkmonitorbeat 所需的配置文件
"""

from base64 import b64encode
from pathlib import Path
from typing import Any, final

from jinja2.sandbox import SandboxedEnvironment as Environment

from bk_monitor_base.config import get_config
from bk_monitor_base.domains.uptime_check.constants import (
    DEFAULT_MAX_TIMEOUT,
    DEFAULT_UPTIMECHECK_OUTPUT_FIELDS,
    UptimeCheckProtocol,
)
from bk_monitor_base.domains.uptime_check.models import UptimeCheckTaskModel


@final
class ConfigGeneratorService:
    """
    配置生成器服务

    使用 Jinja2 模板引擎,根据协议类型生成拨测任务的配置文件
    """

    # 协议与模板文件的映射
    TEMPLATE_MAP = {
        UptimeCheckProtocol.HTTP: "bkmonitorbeat_http_global.conf.tpl",
        UptimeCheckProtocol.TCP: "bkmonitorbeat_tcp_global.conf.tpl",
        UptimeCheckProtocol.UDP: "bkmonitorbeat_udp_global.conf.tpl",
        UptimeCheckProtocol.ICMP: "bkmonitorbeat_icmp_global.conf.tpl",
    }

    # 协议与默认 DataID 的映射
    DEFAULT_DATAID_MAP = {
        UptimeCheckProtocol.HTTP: 1011,
        UptimeCheckProtocol.TCP: 1009,
        UptimeCheckProtocol.UDP: 1010,
        UptimeCheckProtocol.ICMP: 1100003,
    }

    def __init__(self, template_dir: str | Path | None = None):
        """
        初始化配置生成器

        Args:
            template_dir: 模板文件目录,默认使用内置模板目录
        """
        if template_dir is None:
            # 使用内置模板目录
            current_dir = Path(__file__).parent.parent
            template_dir = current_dir / "templates"

        self.template_dir = Path(template_dir)
        self._env = Environment()

    def render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """
        渲染 Jinja2 模板

        Args:
            template_name: 模板文件名
            context: 模板上下文数据

        Returns:
            渲染后的配置文件内容

        Raises:
            FileNotFoundError: 模板文件不存在
        """
        # 获取模版文件路径
        template_path = self.template_dir / template_name

        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")

        with open(template_path, encoding="utf-8") as f:
            template_content = f.read()

        template = self._env.from_string(template_content)
        return template.render(context or {})

    def generate_config(
        self,
        protocol: str,
        config: dict[str, Any],
        data_id: int | None = None,
        max_timeout: int = DEFAULT_MAX_TIMEOUT,
        **kwargs: Any,
    ) -> str:
        """
        生成拨测任务配置

        Args:
            protocol: 协议类型 (HTTP/TCP/UDP/ICMP)
            config: 任务配置参数
            data_id: 数据ID,如果未指定则使用默认值
            max_timeout: 最大超时时间(毫秒)
            **kwargs: 其他模板参数

        Returns:
            生成的配置文件内容

        Raises:
            ValueError: 不支持的协议类型
            FileNotFoundError: 模板文件不存在
        """
        protocol_enum = UptimeCheckProtocol(protocol.upper())

        if protocol_enum not in self.TEMPLATE_MAP:
            raise ValueError(f"Unsupported protocol: {protocol}")

        template_name = self.TEMPLATE_MAP[protocol_enum]

        # 如果没有指定 data_id,使用默认值
        if data_id is None:
            data_id = self.DEFAULT_DATAID_MAP[protocol_enum]

        # 准备模板上下文
        context = {
            "data_id": data_id,
            "max_timeout": f"{max_timeout}ms",
            "tasks": [config],
            **kwargs,
        }

        return self.render_template(template_name, context)

    def generate_sub_config(
        self,
        protocol: str,
        config: dict[str, Any] | None = None,
        task_id: int = 0,
        bk_biz_id: int = 0,
        labels: dict[str, Any] | None = None,
        test: bool = False,
    ) -> list[dict[str, Any]]:
        """
        生成bkmonitorbeat任务配置

        将前端/API传入的业务配置转换为bkmonitorbeat能理解的任务配置格式。
        这是配置生成的第一步,输出将作为beat配置模板中的tasks参数。

        转换示例:
            输入(业务配置): {"period": 60, "port": 80, "timeout": 3000}
            输出(beat任务): [{"period": "60s", "target_port": 80, "timeout": "3000ms", ...}]

        Args:
            protocol: 协议类型 (HTTP/TCP/UDP/ICMP)
            config: 业务配置字典,包含前端传入的原始参数
            task_id: 任务ID (测试模式下为0)
            bk_biz_id: 业务ID (测试模式下为0)
            labels: 自定义标签
            test: 是否为测试模式

        Returns:
            beat任务配置列表,每个元素是一个任务的完整配置

        Note:
            - 返回列表是因为beat配置支持多任务
            - 当前实现每次只生成一个任务配置
            - 此方法处理单位转换(秒->s, 毫秒->ms)和格式标准化
            - request/response 字段需要经过 Base64 编码处理
        """
        # 确保 labels 始终为字典类型
        labels = labels if labels is not None else {}

        # 如果有 task_id，从数据库加载
        if task_id and not config:
            task = UptimeCheckTaskModel.objects.get(pk=task_id)
            protocol = task.protocol
            config = task.config
            bk_biz_id = task.bk_biz_id
            labels = task.labels if task.labels is not None else {}

        if not config:
            raise ValueError("任务配置为空")

        # 计算 available_duration 和 timeout
        available_duration = int(config.get("timeout", config.get("period", 60) * 1000))

        # 当子任务配置的available_duration超过默认最大超时时间时，需要更新timeout
        timeout = DEFAULT_MAX_TIMEOUT
        if available_duration > timeout:
            timeout = available_duration + 5000

        # 获取输出字段配置
        output_fields = config.get("output_fields", DEFAULT_UPTIMECHECK_OUTPUT_FIELDS)

        # 准备 target_host_list (url_list + ip_list)
        url_list = config.get("url_list", [])
        ip_list = config.get("ip_list", [])
        target_host_list = ip_list + url_list

        # 根据协议类型生成配置
        task = None

        if protocol == UptimeCheckProtocol.TCP:
            task = {
                "task_id": 0 if test else task_id,
                "labels": labels,
                "bk_biz_id": 0 if test else bk_biz_id,
                "period": f"{config.get('period', 60)}s",
                "available_duration": f"{available_duration}ms",
                "timeout": f"{timeout}ms",
                "target_host_list": target_host_list,
                "target_port": config.get("port", 0),
                "response": self.encode_data_with_prefix(config.get("response", "")),
                "response_format": config.get("response_format", "in"),
                "node_list": config.get("node_list", []),
                "output_fields": output_fields,
                "dns_check_mode": config.get("dns_check_mode", "single"),
                "target_ip_type": config.get("target_ip_type", 0),
            }

        elif protocol == UptimeCheckProtocol.UDP:
            task = {
                "task_id": 0 if test else task_id,
                "labels": labels,
                "bk_biz_id": 0 if test else bk_biz_id,
                "period": f"{config.get('period', 60)}s",
                "available_duration": f"{available_duration}ms",
                "timeout": f"{timeout}ms",
                "target_host_list": target_host_list,
                "target_port": config.get("port", 0),
                "request_format": config.get("request_format", "hex"),
                "response_format": config.get("response_format", "hex|eq"),
                "wait_empty_response": "true" if config.get("wait_empty_response", True) else "false",
                "request": self.encode_data_with_prefix(config.get("request", "")),
                "response": self.encode_data_with_prefix(config.get("response", "")),
                "node_list": config.get("node_list", []),
                "output_fields": output_fields,
                "dns_check_mode": config.get("dns_check_mode", "single"),
                "target_ip_type": config.get("target_ip_type", 0),
            }

        elif protocol == UptimeCheckProtocol.HTTP:
            # 处理 headers
            header_dict = {
                item["key"]: self.encode_data_with_prefix(item["value"])
                for item in config.get("headers", [])
                if item.get("is_enabled")
            }

            # 处理 body 和 authorization
            from bk_monitor_base.domains.uptime_check.services.http_helper import GetHTTPConfig

            get_http_config = GetHTTPConfig(header_dict)
            body = get_http_config.get_body(
                config.get("body", {"data_type": "default", "params": [], "content": "", "content_type": ""})
            )
            auth = config.get("authorize", {})
            header_dict = get_http_config.get_authorization(auth)

            # 拼接 URL 参数后缀 (GET 方法)
            if config.get("method") == "GET":
                from bk_monitor_base.domains.uptime_check.services.http_helper import url_join_args

                fields = {
                    item["key"]: item["value"] for item in config.get("query_params", []) if item.get("is_enabled")
                }
                url_list = url_join_args(url_list, fields)

            task = {
                "task_id": 0 if test else task_id,
                "labels": labels,
                "bk_biz_id": 0 if test else bk_biz_id,
                "period": f"{config.get('period', 60)}s",
                "proxy": "",
                # 注意: insecure_skip_verify 是反向逻辑
                "insecure_skip_verify": not auth.get("insecure_skip_verify", False),
                "disable_keep_alives": False,
                "available_duration": f"{available_duration}ms",
                "timeout": f"{timeout}ms",
                "dns_check_mode": config.get("dns_check_mode", "single"),
                "target_ip_type": config.get("target_ip_type", 0),
                "steps": [
                    {
                        "url_list": url_list,
                        "method": config.get("method", "GET"),
                        "response_format": config.get("response_format", "in"),
                        "headers": header_dict if header_dict else {},
                        "request": self.encode_data_with_prefix(body),
                        "response": self.encode_data_with_prefix(config.get("response", "")),
                        "response_code": config.get("response_code", ""),
                        # available_duration 参数在 step 下
                        "available_duration": f"{available_duration}ms",
                    }
                ],
            }

        elif protocol == UptimeCheckProtocol.ICMP:
            # 处理目标列表格式
            target_url_list = [{"target": url, "target_type": "domain"} for url in url_list]
            target_ip_list = [{"target": ip, "target_type": "ip"} for ip in ip_list]
            target_host_list_with_type = target_url_list + target_ip_list

            # 注入目标主机标签
            target_labels = config.get("target_labels", {})
            for target in target_host_list_with_type:
                if target["target"] in target_labels:
                    target["labels"] = target_labels[target["target"]]

            task = {
                "task_id": 0 if test else task_id,
                "labels": labels,
                "bk_biz_id": 0 if test else bk_biz_id,
                "period": f"{config.get('period', 60)}s",
                # 测试时减小测试参数,以保证前端不会等待太久
                "max_rtt": "3000ms" if test else f"{config.get('max_rtt', 3000)}ms",
                "total_num": 1 if test else config.get("total_num", 3),
                "size": config.get("size", 56),
                "available_duration": f"{available_duration}ms",
                "timeout": f"{timeout}ms",
                "target_host_list": target_host_list_with_type,
                "node_list": config.get("node_list", []),
                "output_fields": output_fields,
                "dns_check_mode": config.get("dns_check_mode", "single"),
                "target_ip_type": config.get("target_ip_type", 0),
            }

        if not task:
            return []

        return [task]

    def add_escape(self, input_string: str) -> str:
        """
        对字符串进行转义处理

        外层增加单引号,内层对单引号进行转义(单引号双写)

        Args:
            input_string: 要转义的原始字符串

        Returns:
            转义后的字符串,格式: '转义后的内容'

        Examples:
            >>> add_escape("hello")
            "'hello'"
            >>> add_escape("it's")
            "'it''s'"
        """
        if not input_string:
            return input_string
        # 单引号双写进行转义,外层加单引号
        temp = input_string.replace("'", "''")
        return f"'{temp}'"

    def encode_data_with_prefix(self, input_string: str, prefix: str = "base64://") -> str:
        """
        对数据进行Base64编码,并添加指定前缀

        Args:
            input_string: 要编码的原始数据
            prefix: 添加到编码数据前面的前缀

        Returns:
            编码且带有前缀的字符串
        """
        if not input_string:
            return self.add_escape(input_string)

        # 获取触发Base64编码的字符列表
        trigger_chars = get_config().domains.uptime_check.base64_encode_trigger_chars
        if not trigger_chars:
            return self.add_escape(input_string)

        # 检查是否包含触发字符
        for char in trigger_chars:
            if char in input_string:
                encoded_data = b64encode(input_string.encode("utf-8")).decode("utf-8")
                return f"{prefix}{encoded_data}"

        return self.add_escape(input_string)
