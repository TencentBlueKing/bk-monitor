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
from aidev_agent.services.chat import ExecuteKwargs
from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.services.agent import AgentInstanceFactory
from aidev_agent.enums import AgentBuildType
from ai_agent.utils import get_langfuse_callback, handle_streaming_response_with_metrics
from ai_agent.services.local_command_handler import LocalCommandProcessor

logger = logging.getLogger("ai_whale")


class AIDevInterface:
    def __init__(self, app_code, app_secret, metrics_reporter=None):
        self.api_client = BKAidevApi.get_client(app_code=app_code, app_secret=app_secret)
        self.local_command_processor = LocalCommandProcessor()
        self.metrics_reporter = metrics_reporter

    # -------------------- Agent管理 -------------------- #
    def get_agent_info(self, agent_code):
        return self.api_client.api.retrieve_agent_config(path_params={"agent_code": agent_code})

    # -------------------- 会话管理 -------------------- #

    def create_chat_session(self, params, username):
        return self.api_client.api.create_chat_session(json=params, headers={"X-BKAIDEV-USER": username})

    def retrieve_chat_session(self, session_code):
        return self.api_client.api.retrieve_chat_session(path_params={"session_code": session_code})

    def list_chat_sessions(self, username):
        return self.api_client.api.list_chat_session(headers={"X-BKAIDEV-USER": username})

    def destroy_chat_session(self, session_code):
        """删除会话"""
        return self.api_client.api.destroy_chat_session(path_params={"session_code": session_code})

    def update_chat_session(self, session_code, params):
        """更新会话"""
        return self.api_client.api.update_chat_session(path_params={"session_code": session_code}, json=params)

    # ==================== 会话内容管理 ====================
    def create_chat_session_content(self, params):
        """创建会话内容"""
        property_data = params.get("property", {})

        # 快捷指令
        try:
            command_data = property_data.get("extra", {})
            command = command_data.get("command")
            # 若存在注册的LocalHandler，则使用本地处理逻辑用于渲染会话内容
            if command and self.local_command_processor.has_local_handler(command):
                logger.info("create_chat_session_content: try to process command->[%s]", command_data)
                processed_content = self.local_command_processor.process_command(command_data)
                if processed_content:
                    params["property"]["extra"]["rendered_content"] = processed_content
        except Exception as e:  # pylint: disable=broad-except
            logger.error("create_chat_session_content: process command error->[%s]", e)

        res = self.api_client.api.create_chat_session_content(json=params)
        return res

    def get_chat_session_contents(self, session_code):
        """获取会话内容列表"""
        return self.api_client.api.get_chat_session_contents(params={"session_code": session_code})

    def destroy_chat_session_content(self, id):
        """删除单条会话内容"""
        return self.api_client.api.destroy_chat_session_content(path_params={"id": id})

    def batch_delete_session_contents(self, params):
        """批量删除会话内容"""
        return self.api_client.api.batch_delete_chat_session_content(json=params)

    def update_chat_session_content(self, params):
        """更新单条会话内容"""
        id = params.get("id")
        return self.api_client.api.update_chat_session_content(path_params={"id": id}, json=params)

    # ==================== 发起对话 ====================
    def create_chat_completion(self, session_code, execute_kwargs, agent_code, username):
        """发起流式/非流式会话"""
        callbacks = [get_langfuse_callback()]
        agent_instance = AgentInstanceFactory.build_agent(
            build_type=AgentBuildType.SESSION,
            session_code=session_code,
            resource_manager=self.api_client,
            callbacks=callbacks,
        )
        if execute_kwargs.get("stream", False):
            # 使用增强的流式处理函数
            streaming_wrapper = handle_streaming_response_with_metrics(
                agent_instance=agent_instance,
                execute_kwargs=execute_kwargs,
                resource_name=self.__class__.__name__,
                agent_code=agent_code,
                username=username,
                metrics_reporter=self.metrics_reporter,
            )
            return streaming_wrapper.as_streaming_response()
        else:  # 非流式
            execute_kwargs = ExecuteKwargs.model_validate(execute_kwargs)
            result = agent_instance.execute(execute_kwargs)
            return result
