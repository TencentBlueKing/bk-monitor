"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from abc import ABC, abstractmethod
from string import Formatter

import logging

logger = logging.getLogger("ai_agents")


class CommandHandler(ABC):
    """
    快捷指令处理器基类
    """

    agent_code = None
    command = None

    @abstractmethod
    def get_template(self) -> str:
        """获取命令对应的提示词模板"""
        pass

    def extract_context_vars(self, context: list[dict]) -> dict[str, str]:
        """
        从上下文中提取模板变量（通用实现可被重写）
        """
        variables = {}
        for item in context:
            if "__key" in item and "__value" in item:
                variables[item["__key"]] = item["__value"]  # 去除__前缀
        return variables

    def process_content(self, context: list[dict]) -> str:
        """
        处理内容（使用模板和变量）
        """
        template = self.get_template()
        variables = self.extract_context_vars(context)

        try:
            # 安全格式化，缺失变量保持原样
            return Formatter().vformat(template, (), variables)
        except KeyError as e:
            missing = str(e).strip("'")
            raise ValueError(f"Missing required context variable: {missing}")


class TranslateCommandHandler(CommandHandler):
    command = "translate"

    def get_template(self) -> str:
        return """
        请将以下内容翻译为{language}:
        {content}
        翻译要求: 确保翻译准确无误，无需冗余回答内容
        """

    def extract_context_vars(self, context: list[dict]) -> dict[str, str]:
        variables = super().extract_context_vars(context)
        # 特殊处理：确保必须有content变量
        if "content" not in variables:
            raise ValueError("Translation requires 'content' in context")
        return variables


class ExplanationCommandHandler(CommandHandler):
    command = "explanation"

    def get_template(self) -> str:
        return """
        请解释以下内容{content}
        解释要求: 确保解释准确无误，无需冗余回答内容
        """


class MetadataDiagnosisCommandHandler(CommandHandler):
    command = "metadata_diagnosis"
    agent_code = "aidev-metadata"

    def get_template(self) -> str:
        return """
        请帮助我分析排障,数据源ID为{bk_data_id}
        """


class CommandProcessor:
    _handlers: dict[str, type[CommandHandler]] = {}

    @classmethod
    def register_handler(cls, command: str, handler: type[CommandHandler]):
        cls._handlers[command] = handler

    def process_command(self, command_data: dict) -> str:
        if not (command := command_data.get("command")):
            logger.warning("CommandProcessor: No command found in data->[%s]", command_data)
            raise ValueError("No command found in data")

        if (handler_class := self._handlers.get(command)) is None:
            logger.warning("CommandProcessor: No handler registered for command->[%s]", command)
            raise ValueError(f"No handler registered for command: {command}")

        try:
            logger.info("CommandProcessor: Processing command->[%s]", command)
            return handler_class().process_content(command_data.get("context", []))
        except ValueError as e:
            logger.warning("CommandProcessor: Command processing failed->[%s]", str(e))
            raise e


# 注册处理器
CommandProcessor.register_handler("translate", TranslateCommandHandler)
CommandProcessor.register_handler("explanation", ExplanationCommandHandler)
CommandProcessor.register_handler("metadata_diagnosis", MetadataDiagnosisCommandHandler)
