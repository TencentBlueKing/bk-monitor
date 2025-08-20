"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from aidev_agent.services.command_handler import CommandHandler
from ai_agents.utils import get_nested_value
from bkmonitor.utils.request import get_request
from core.drf_resource import api
from core.errors.api import BKAPIError

logger = logging.getLogger("ai_agents")


class LocalCommandRegistry:
    """本地快捷指令处理器注册表"""

    _handlers: dict[str, type[CommandHandler]] = {}

    @classmethod
    def register(cls, command: str, handler_class: type[CommandHandler]):
        """注册本地处理器"""
        cls._handlers[command] = handler_class
        logger.info(f"LocalCommandRegistry: registered handler for command->[{command}]")

    @classmethod
    def get_handler(cls, command: str) -> type[CommandHandler] | None:
        """获取本地处理器"""
        return cls._handlers.get(command)

    @classmethod
    def has_handler(cls, command: str) -> bool:
        """检查是否存在本地处理器"""
        return command in cls._handlers

    @classmethod
    def list_commands(cls) -> list:
        """列出所有注册的命令"""
        return list(cls._handlers.keys())


def local_command_handler(command: str):
    """
    本地快捷指令处理器装饰器

    Args:
        command: 快捷指令名称

    Usage:
        @local_command_handler("tracing_analysis")
        class TracingAnalysisCommandHandler(CommandHandler):
            def process_content(self, context: list[dict]) -> str:
                # 实现处理逻辑
                pass
    """

    def decorator(handler_class: type[CommandHandler]):
        if not issubclass(handler_class, CommandHandler):
            raise TypeError("Handler class must inherit from CommandHandler")

        # 设置command属性（如果未设置）
        if not hasattr(handler_class, "command") or not handler_class.command:
            handler_class.command = command

        # 注册到本地注册表
        LocalCommandRegistry.register(command, handler_class)

        return handler_class

    return decorator


class LocalCommandProcessor:
    """本地快捷指令处理器"""

    def __init__(self):
        self._handler_instances: dict[str, CommandHandler] = {}

    @classmethod
    def has_local_handler(cls, command: str) -> bool:
        """检查是否存在本地处理器"""
        return LocalCommandRegistry.has_handler(command)

    def process_command(self, command_data: dict) -> str:
        """
        处理快捷指令

        Args:
            command_data: 包含command和context的字典

        Returns:
            处理后的内容

        Raises:
            ValueError: 当命令不存在或处理失败时
        """
        command = command_data.get("command")
        if not command:
            raise ValueError("Command is required")

        if not self.has_local_handler(command):
            raise ValueError(f"No local handler found for command: {command}")

        # 获取或创建处理器实例
        if command not in self._handler_instances:
            handler_class = LocalCommandRegistry.get_handler(command)
            self._handler_instances[command] = handler_class()

        handler = self._handler_instances[command]
        context = command_data.get("context", [])

        try:
            return handler.process_content(context)
        except Exception as e:
            logger.error(f"LocalCommandProcessor: failed to process command->[{command}], error->[{e}]")
            raise ValueError(f"Failed to process command {command}") from e


# TODO:平台暂时不支持MCP，若需要对输入数据进行特殊处理，临时在业务逻辑中实现LocalCommandHandler,实现process_content和get_template方法
@local_command_handler("tracing_analysis")
class TracingAnalysisCommandHandler(CommandHandler):
    keys = ["status", "kind", "elapsed_time", "start_time", "span_name"]

    # 基于 128K 上下文长度设置
    max_character_length = 120_000
    max_span = 50

    def process_content(self, context: list[dict]) -> str:
        template = self.get_template()
        variables = self.extract_context_vars(context)

        req = get_request()
        if not req:
            raise ValueError("TracingAnalysisCommandHandler requires 'local request'")

        try:
            biz_id = req.session["bk_biz_id"]
            resp = api.apm_api.query_trace_detail(
                {
                    "bk_biz_id": biz_id,
                    "app_name": variables["app_name"],
                    "trace_id": variables["trace_id"],
                }
            )
            trace_data = resp["trace_data"]

            processed_trace_data = trace_data
            if len(trace_data) > self.max_span:
                processed_trace_data = [{k: get_nested_value(x, k) for k in self.keys} for x in trace_data]
        except (BKAPIError, KeyError) as e:
            raise ValueError("TracingAnalysis failed to query trace data") from e

        trace_data_lite = str(processed_trace_data)[: self.max_character_length]

        variables["trace_data"] = trace_data_lite

        return self.jinja_env.render(template, variables)

    def get_template(self):
        return """
        请帮助我分析Tracing数据: {{ trace_data }}.
        应用名称: {{ app_name }}
        结果要求: 确保分析准确无误，无需冗余回答内容
        """
