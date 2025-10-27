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
from blueapps.utils.request_provider import get_local_request, get_local_request_id, get_request_username
from langfuse.callback import CallbackHandler
from ai_agent.services.metrics_reporter import (
    StreamingMetricsTracker,
    EnhancedStreamingResponseWrapper,
    AIMetricsReporter,
)
from aidev_agent.services.chat import ExecuteKwargs

logger = logging.getLogger("ai_whale")


# TODO: 将callback集成至AgentSDK
def get_langfuse_callback(metadata: dict | None = None) -> CallbackHandler | None:
    """
    获取langfuse回调
    """
    user_id = get_request_username()
    if not user_id:
        local_request = get_local_request()
        user_id = getattr(local_request.app, "bk_app_code", "anonymous")
    request_id = get_local_request_id()
    return CallbackHandler(user_id=user_id, session_id=request_id, metadata=metadata)


def handle_streaming_response_with_metrics(
    agent_instance,
    execute_kwargs,
    resource_name: str,
    agent_code: str,
    username: str,
    metrics_reporter: AIMetricsReporter,
):
    """处理流式响应（带指标统计）"""
    logger.info(f"Starting streaming chat completion with kwargs: {execute_kwargs}")

    # 创建指标跟踪器
    metrics_tracker = StreamingMetricsTracker(
        ai_metrics_reporter=metrics_reporter, resource_name=resource_name, agent_code=agent_code, username=username
    )

    # 检查 ExecuteKwargs 解析是否正确
    try:
        validated_kwargs = ExecuteKwargs.model_validate(execute_kwargs)
        logger.info(f"CreateChatCompletionResource: Validated execute_kwargs: {validated_kwargs}")
    except Exception as e:
        logger.error(f"CreateChatCompletionResource: ExecuteKwargs validation failed: {e}")
        metrics_tracker.on_streaming_error(e)
        raise

    def streaming_generator():
        try:
            for chunk in agent_instance.execute(validated_kwargs):
                logger.info(f"CreateChatCompletionResource: Yielding chunk: {chunk}")
                yield chunk
        except Exception as error:
            logger.error(f"CreateChatCompletionResource: Error in streaming generator: {error}")
            raise

    return EnhancedStreamingResponseWrapper(streaming_generator(), metrics_tracker)


def get_username() -> str:
    """获取用户名"""
    try:
        return get_request_username() or "unknown"
    except Exception as e:
        logger.warning(f"Failed to get username: {e}")
        return "unknown"
