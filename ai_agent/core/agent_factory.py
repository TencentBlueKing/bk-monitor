import logging
from typing import Any, cast
from collections.abc import Callable

from aidev_agent.api import BKAidevApi
from aidev_agent.api.abstract_client import AbstractBKAidevResourceManager
from aidev_agent.config import settings
from aidev_agent.core.extend.agent.qa import CommonQAAgent
from aidev_agent.core.extend.models.llm_gateway import ChatModel
from aidev_agent.enums import AgentBuildType, AgentType
from aidev_agent.packages.langchain.tools.base import make_mcp_tools
from aidev_agent.services.chat import ChatCompletionAgent
from aidev_agent.services.config_manager import AgentConfig, AgentConfigManager
from aidev_agent.services.pydantic_models import AgentOptions, ChatPrompt

logger = logging.getLogger("aidev-agent")


class AgentInstanceFactory:
    """
    Agent实例工厂 - 支持构建多种类型的Agent
    """

    # Agent类型映射表
    _agent_classes: dict[AgentType, type] = {}
    # Agent构建器注册表
    _agent_builders: dict[AgentType, Callable] = {}

    def __init__(
        self,
        agent_code: str,
        agent_type: AgentType = AgentType.CHAT,
        build_type: AgentBuildType = AgentBuildType.SESSION,
        session_code: str | None = None,
        agent_cls: type[CommonQAAgent] | None = None,
        callbacks: list[Any] | None = None,
        resource_manager: AbstractBKAidevResourceManager | None = None,
        auth_headers: dict[str, str] | None = None,
        temperature: float = None,
        switch_agent_by_scene: bool = False,
        config_manager_class: type[AgentConfigManager] | None = None,
        is_temporary: bool = False,
    ):
        """
        初始化Agent工厂实例
        :param agent_code: Agent代码
        :param agent_type: Agent类型 ("chat", "task", "workflow"等)
        :param build_type: 构建类型 ("session", "direct")
        :param session_code: 会话代码 (build_type="session"时必需)
        :param agent_cls: Agent类
        :param callbacks: 回调函数列表
        :param resource_manager:  bkaidev 资源管理
        :param temperature: 模型温度
        :param switch_agent_by_scene: 是否根据场景切换智能体
        :param is_temporary: 是否为临时Agent
        """
        self.resource_manager = resource_manager or BKAidevApi.get_client()
        self.agent_code = agent_code
        self.agent_type = agent_type
        self.build_type = build_type
        self.session_code = session_code
        self.agent_cls = agent_cls
        self.callbacks = [each for each in callbacks if each] if callbacks else []
        self.auth_headers = auth_headers or None
        self.temperature = temperature or None
        self.switch_agent_by_scene = switch_agent_by_scene
        self.config_manager_class = config_manager_class or AgentConfigManager
        self.is_temporary = is_temporary

    @classmethod
    def build_agent(
        cls,
        agent_code: str = settings.APP_CODE,
        agent_type: AgentType = AgentType.CHAT,
        build_type: AgentBuildType = AgentBuildType.SESSION,
        session_code: str | None = None,
        session_context_data: list[dict] | None = None,
        agent_cls: type[CommonQAAgent] | None = CommonQAAgent,
        callbacks: list[Any] | None = None,
        resource_manager: AbstractBKAidevResourceManager | None = None,
        temperature: float | None = None,
        switch_agent_by_scene: bool = False,
        config_manager_class: type[AgentConfigManager] | None = AgentConfigManager,
        is_temporary: bool = False,
    ):
        """
        构建Agent实例
        :param agent_code: Agent代码
        :param agent_type: Agent类型 ("chat", "task", "workflow"等)
        :param build_type: 构建类型 ("session", "direct")
        :param session_code: 会话代码 (build_type="session"时必需)
        :param session_context_data: 会话上下文数据 (build_type="direct"时使用)
        :param agent_cls: Agent类
        :param callbacks: 回调函数列表
        :param resource_manager: 资源管理类
        :param temperature: 模型温度
        :param switch_agent_by_scene: 是否根据场景切换智能体
        :param config_manager_class: 配置管理类
        :param is_temporary: 是否为临时Agent
        :return: 构建好的Agent实例
        """
        # 创建工厂实例
        factory = cls(
            agent_code=agent_code,
            agent_type=agent_type,
            build_type=build_type,
            session_code=session_code,
            agent_cls=agent_cls,
            callbacks=callbacks,
            resource_manager=resource_manager,
            temperature=temperature,
            switch_agent_by_scene=switch_agent_by_scene,
            config_manager_class=config_manager_class,
            is_temporary=is_temporary,
        )

        # 验证参数
        factory._validate_params()

        # 构建基础参数
        if build_type == AgentBuildType.SESSION:
            base_args = factory._build_from_session()
        elif build_type == AgentBuildType.DIRECT:
            base_args = factory._build_direct(session_context_data or [])
        else:
            raise ValueError(f"Unsupported build_type: {build_type}")

        # 根据agent_type构建特定参数
        agent_args = factory._build_agent_args(base_args)

        # 创建Agent实例
        return factory._create_agent_instance(agent_args)

    def _validate_params(self):
        """验证初始化参数"""
        if self.build_type == AgentBuildType.SESSION and not self.session_code:
            raise ValueError("session_code is required when build_type is 'session'")

        if self.build_type not in [AgentBuildType.SESSION, AgentBuildType.DIRECT]:
            raise ValueError(f"Unsupported build_type: {self.build_type}")

        if self.agent_type not in self._agent_builders:
            raise ValueError(
                f"Unsupported agent_type: {self.agent_type}. Supported types: {list(self._agent_builders.keys())}"
            )

    def _build_agent_args(self, base_args: dict) -> dict:
        """
        构建Agent特定参数
        取决于Agent类别
        """
        builder = self._agent_builders[self.agent_type]
        agent_specific_args = builder(self, **base_args)

        # 合并通用参数
        final_args = {
            "agent_cls": self.agent_cls,
            "callbacks": self.callbacks,
            **agent_specific_args,
        }

        return final_args

    def _create_agent_instance(self, agent_args: dict):
        """创建Agent实例"""
        agent_class = self._agent_classes[self.agent_type]
        return agent_class(**agent_args)

    def _build_from_session(self) -> dict:
        """通过session_code构建基础参数"""
        logger.info(
            f"AgentInstanceFactory: building {self.agent_type} agent for session_code->[{self.session_code}], "
            f"agent_code->[{self.agent_code}]"
        )

        # 获取会话上下文数据
        session_code = cast(str, self.session_code)
        session_context_data = self.resource_manager.get_chat_session_context(session_code)

        base_agent_config = self.config_manager_class.get_config(
            agent_code=self.agent_code, resource_manager=self.resource_manager
        )

        logger.info(
            f"AgentInstanceFactory: session->[{self.session_code}] "
            f"get session_context_data count->[{len(session_context_data)}]"
        )

        # 检查是否需要切换智能体
        switch_agent, final_agent_code = self._check_agent_switch(session_context_data, base_agent_config)

        if not switch_agent and self.switch_agent_by_scene:
            switch_agent = True

        # 处理最后一条assistant消息
        self._clean_last_assistant_message(session_context_data, base_agent_config)

        return {
            "agent_code": final_agent_code,
            "session_context_data": session_context_data,
            "switch_agent": switch_agent,
            "config_manager_class": self.config_manager_class,
        }

    def _build_direct(self, session_context_data: list[dict]) -> dict:
        """直接构建基础参数（使用提供的session_context_data）"""
        logger.info(
            f"AgentInstanceFactory: building {self.agent_type} agent directly with agent_code->[{self.agent_code}]"
        )

        return {
            "agent_code": self.agent_code,
            "session_context_data": session_context_data,
            "switch_agent": False,
            "config_manager_class": self.config_manager_class,
        }

    # ============== 通用构建方法 ==============

    def build_chat_model(self, agent_code: str):
        """构建聊天模型"""
        config = self.config_manager_class.get_config(agent_code=agent_code, resource_manager=self.resource_manager)

        # Prepare kwargs for ChatModel.get_setup_instance
        kwargs = {
            "model": config.llm_model_name,
            "base_url": settings.LLM_GW_ENDPOINT,
        }

        if self.temperature is not None:
            kwargs["temperature"] = self.temperature

        # Only add auth_headers if it has a value
        if self.auth_headers:
            kwargs["auth_headers"] = self.auth_headers

        return ChatModel.get_setup_instance(**kwargs)

    def build_chat_history(self, session_context_data: list[dict]) -> list[ChatPrompt]:
        """构建聊天历史"""
        return [ChatPrompt.model_validate(each) for each in session_context_data if each.get("content", "")]

    def build_knowledge_bases(self, agent_code: str) -> list[dict]:
        """构建知识库"""
        config = self.config_manager_class.get_config(agent_code=agent_code, resource_manager=self.resource_manager)
        return [self.resource_manager.retrieve_knowledgebase(_id) for _id in config.knowledgebase_ids]

    def build_knowledge_items(self, agent_code: str) -> list[dict]:
        """构建知识条目"""
        config = self.config_manager_class.get_config(agent_code=agent_code, resource_manager=self.resource_manager)
        return [self.resource_manager.retrieve_knowledge(_id) for _id in config.knowledge_ids]

    def build_tools(self, agent_code: str) -> list[Any]:
        """构建工具"""
        config = self.config_manager_class.get_config(agent_code=agent_code, resource_manager=self.resource_manager)
        mcp_tools = make_mcp_tools(config.mcp_server_config) if config.mcp_server_config else []
        return [self.resource_manager.construct_tool(tool_code) for tool_code in config.tool_codes] + mcp_tools

    def get_role_prompt(self, agent_code: str) -> str | None:
        """获取角色提示词"""
        config = self.config_manager_class.get_config(agent_code=agent_code, resource_manager=self.resource_manager)
        return config.role_prompt

    def build_agent_options(self, agent_code: str) -> AgentOptions:
        """构建Agent选项"""
        config = self.config_manager_class.get_config(agent_code=agent_code, resource_manager=self.resource_manager)
        return config.agent_options

    def handle_agent_switch(self, session_context_data: list[dict], agent_code: str, switch_agent: bool):
        """处理智能体切换"""
        if not switch_agent:
            return

        logger.info(f"AgentInstanceFactory: switching agent to->[{agent_code}]")
        # 找到最后一条role为system的记录并修改
        for item in reversed(session_context_data):
            if item["role"] == "system":
                item["content"] = self.get_role_prompt(agent_code)
                break

    def _check_agent_switch(self, session_context_data: list[dict], base_agent_config: AgentConfig) -> tuple[bool, str]:
        """检查是否需要切换智能体"""
        switch_agent = False
        final_agent_code = self.agent_code

        try:
            # 获取最后一条用户消息
            last_user_message = (
                next(
                    (msg for msg in reversed(session_context_data) if msg["role"] == "user"),
                    None,
                )
                or {}
            )

            first_user_message = (
                next(
                    (msg for msg in session_context_data if msg["role"] == "user"),
                    None,
                )
                or {}
            )

            last_command = last_user_message.get("extra", {}).get("command")
            first_command = first_user_message.get("extra", {}).get("command")

            if (
                last_command
            ):  # 若最后一条会话记录存在Command，且该Command映射到了新的Agent,那么在本轮对话中使用新的Agent的配置
                command_agent_code = base_agent_config.command_agent_mapping.get(last_command, self.agent_code)
            elif (
                self.is_temporary and first_command
            ):  # 若该会话是临时会话,且第一条用户记录内容中存在Command,使用该Command映射的Agent配置
                command_agent_code = base_agent_config.command_agent_mapping.get(first_command, self.agent_code)
            else:
                command_agent_code = self.agent_code

            switch_agent = command_agent_code != self.agent_code
            final_agent_code = command_agent_code  # 切换Agent

        except Exception as e:  # pylint: disable=broad-except
            logger.warning(f"AgentInstanceFactory: get last user message error->[{e}]")

        return switch_agent, final_agent_code

    def _clean_last_assistant_message(self, session_context_data: list[dict], base_agent_config):
        """清理最后一条assistant消息（如果包含生成中关键词）"""
        # 卫语句：如果没有消息数据，直接返回
        if not session_context_data:
            return

        # 卫语句：如果最后一条消息不是assistant，直接返回
        if session_context_data[-1]["role"] != "assistant":
            return

        logger.info(
            f"AgentInstanceFactory: session->[{self.session_code}] last message is assistant, checking if should remove"
        )

        content = session_context_data[-1]["content"]

        # 卫语句：如果content中没有生成中关键词，直接返回
        if base_agent_config.generating_keyword not in content:
            return

        logger.info("AgentInstanceFactory: removing last assistant message with generating keyword")
        session_context_data.pop()

    @classmethod
    def register_agent_type(
        cls,
        agent_type: AgentType,
        agent_class: type,
        builder_func: Callable,
        override=False,
    ):
        """注册新的Agent类型"""
        if not override and agent_type in cls._agent_classes:
            raise ValueError(f"Agent type '{agent_type}' already exists")
        cls._agent_classes[agent_type] = agent_class
        cls._agent_builders[agent_type] = builder_func
        logger.info(f"AgentInstanceFactory: registered agent type->[{agent_type}] with class->[{agent_class.__name__}]")

    # ============== Agent构建器函数 ==============

    @staticmethod
    def build_chat_agent_args(
        factory: "AgentInstanceFactory",
        agent_code: str,
        session_context_data: list[dict],
        switch_agent: bool,
        config_manager_class: type[AgentConfigManager] | None = None,
    ):
        """构建ChatCompletionAgent参数"""
        logger.info(f"Building ChatCompletionAgent args with agent_code->[{agent_code}]")

        if switch_agent:
            factory.config_manager_class = config_manager_class

        # 处理智能体切换
        factory.handle_agent_switch(session_context_data, agent_code, switch_agent)

        return {
            "chat_model": factory.build_chat_model(agent_code),
            "tools": factory.build_tools(agent_code),
            "knowledge_bases": factory.build_knowledge_bases(agent_code),
            "knowledge_items": factory.build_knowledge_items(agent_code),
            "chat_history": factory.build_chat_history(session_context_data),
            "agent_options": factory.build_agent_options(agent_code),
        }

    @staticmethod
    def build_task_agent_args(
        factory,
        agent_code,
        session_context_data,
        switch_agent,
        config_manager_class: type[AgentConfigManager] | None = None,
    ):
        """构建TaskAgent参数（示例）"""
        # 处理智能体切换
        factory.handle_agent_switch(session_context_data, agent_code, switch_agent)
        if switch_agent:
            factory.config_manager_class = config_manager_class

        # TaskAgent可能需要不同的参数组合
        return {
            "task_config": factory.get_role_prompt(agent_code),
            "tools": factory.build_tools(agent_code),
            "chat_history": factory.build_chat_history(session_context_data),
            # 可能不需要knowledge_bases等
        }


# 注册默认的Agent类型
AgentInstanceFactory.register_agent_type(
    agent_type=AgentType.CHAT,
    agent_class=ChatCompletionAgent,
    builder_func=AgentInstanceFactory.build_chat_agent_args,
)
