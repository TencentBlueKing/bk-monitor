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
        self.local_command_processor = LocalCommandProcessor()  # 本地指令处理器
        self.metrics_reporter = metrics_reporter  # 指标上报器

    # -------------------- Agent管理 -------------------- #
    def get_agent_info(self, agent_code):
        """获取Agent配置信息；去除 data['prompt_setting'] 字段"""
        res = self.api_client.api.retrieve_agent_config(path_params={"agent_code": agent_code})
        try:
            data = res.get("data", {}) if isinstance(res, dict) else None
            if isinstance(data, dict) and "prompt_setting" in data:
                # TODO：AIDEV平台改造完成后移除,不返回 prompt_setting，避免提示词泄漏
                del data["prompt_setting"]
        except Exception as e:  # 出现异常不应影响主流程
            logger.warning("get_agent_info: failed to strip prompt_setting: %s", e)
        return res

    # -------------------- 会话管理 -------------------- #

    def create_chat_session(self, params, username):
        """创建会话"""
        session_code = params["session_code"]
        session_res = self.api_client.api.create_chat_session(json=params, headers={"X-BKAIDEV-USER": username})

        # TODO：监控&日志 场景下，目前只存在单Prompt场景，后续需要规范Prompt的插入时机和行为
        self.create_chat_session_content(
            params={
                "session_code": session_code,
                "role": "hidden-role",
                "content": session_res["data"]["role_info"]["role_content"][0]["content"],
            }
        )
        logger.info(
            "create_chat_session: create session and add system prompt successfully,session_code->[%s]", session_code
        )
        return session_res

    def retrieve_chat_session(self, session_code):
        """获取单个会话"""
        return self.api_client.api.retrieve_chat_session(path_params={"session_code": session_code})

    def list_chat_sessions(self, username):
        """按「用户」粒度拉取会话列表"""
        return self.api_client.api.list_chat_session(headers={"X-BKAIDEV-USER": username})

    def destroy_chat_session(self, session_code):
        """删除会话"""
        return self.api_client.api.destroy_chat_session(path_params={"session_code": session_code})

    def update_chat_session(self, session_code, params):
        """更新会话"""
        return self.api_client.api.update_chat_session(path_params={"session_code": session_code}, json=params)

    def rename_chat_session(self, session_code):
        """AI 智能总结会话标题"""
        return self.api_client.api.rename_chat_session(path_params={"session_code": session_code})

    def rename_chat_session_by_user_question(self, session_code):
        """
        根据用户输入的第一句问题作为会话标题
        """
        context = self.get_chat_session_contents(session_code=session_code)

        # 检查返回结果是否成功
        if not context.get("result", False) or not context.get("data"):
            logger.warning(
                "rename_chat_session_by_user_question: failed to get session contents for session_code->[%s]",
                session_code,
            )
            return None

        # 查找第一条role为'user'的记录
        user_message = None
        for item in context["data"]:
            if item.get("role") == "user":
                user_message = item.get("content", "")
                break

        if not user_message:
            logger.warning(
                "rename_chat_session_by_user_question: no user message found for session_code->[%s]", session_code
            )
            return None

        session_title = user_message

        # 调用更新会话API
        try:
            update_params = {"session_name": session_title}
            update_result = self.update_chat_session(session_code, update_params)

            if update_result.get("result", False):
                logger.info(
                    "rename_chat_session_by_user_question: successfully updated session title to->[%s] for "
                    "session_code->[%s]",
                    session_title,
                    session_code,
                )
                return {
                    "result": True,
                    "code": "success",
                    "data": {"session_name": session_title, "session_code": session_code},
                    "message": "ok",
                    "request_id": update_result.get("request_id"),
                    "trace_id": update_result.get("trace_id"),
                }
            else:
                logger.warning(
                    "rename_chat_session_by_user_question: failed to update session title for "
                    "session_code->[%s], result: %s",
                    session_code,
                    update_result,
                )
                return None
        except Exception as e:
            logger.error(
                "rename_chat_session_by_user_question: exception occurred while updating session title for "
                "session_code->[%s]: %s",
                session_code,
                e,
            )
            return None

    # ==================== 会话内容管理 ====================
    def create_chat_session_content(self, params):
        """创建会话内容"""
        property_data = params.get("property", {})

        # 快捷指令
        try:  # 本地处理（若有处理器）> 平台处理
            command_data = property_data.get("extra", {})
            command = command_data.get("command")
            # 若存在注册的LocalHandler，则使用本地处理逻辑用于渲染会话内容
            if command and self.local_command_processor.has_local_handler(command):
                logger.info("create_chat_session_content: try to process command->[%s]", command_data)
                processed_content = self.local_command_processor.process_command(command_data)
                if processed_content:  # 若处理成功,将渲染后的内容写入到property中,平台不会进行覆盖
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
    def create_chat_completion(
        self, session_code, execute_kwargs, agent_code, username, temperature=0.3, switch_agent_by_scene=False
    ):
        """发起流式/非流式会话"""
        callbacks = [get_langfuse_callback()]  # 添加Langfuse回调
        agent_instance = AgentInstanceFactory.build_agent(
            agent_code=agent_code,
            build_type=AgentBuildType.SESSION,
            session_code=session_code,
            resource_manager=self.api_client,
            callbacks=callbacks,
            temperature=temperature,
            switch_agent_by_scene=switch_agent_by_scene,
        )  # 工厂方法构建Agent实例
        if execute_kwargs.get("stream", False):
            # 使用增强的流式处理函数
            streaming_wrapper = handle_streaming_response_with_metrics(
                agent_instance=agent_instance,
                execute_kwargs=execute_kwargs,
                resource_name="CreateChatCompletionResource",  # 显示指定资源名称
                agent_code=agent_code,
                username=username,
                metrics_reporter=self.metrics_reporter,
            )
            return streaming_wrapper.as_streaming_response()
        else:  # 非流式
            execute_kwargs = ExecuteKwargs.model_validate(execute_kwargs)
            result = agent_instance.execute(execute_kwargs)
            return result
