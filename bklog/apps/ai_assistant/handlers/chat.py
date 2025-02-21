# -*- coding: utf-8 -*-
import json
import time

import requests
from django.conf import settings
from django.utils import translation

from apps.ai_assistant.constants import InterpretLogFeatureConf
from apps.api.base import get_request_api_headers
from apps.exceptions import ApiRequestError
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import AI_ASSISTANT
from apps.utils.local import get_request_id
from apps.utils.log import logger


class ChatHandler:
    def call_chat_completion(self, model: str, messages: list, stream: bool = True):
        """
        调用聊天接口（支持流式返回）
        :param model: 使用模型
        :param messages: 消息列表
        :param stream: 是否启用流式返回
        :return: 响应生成器
        """
        request_id = get_request_id()
        headers = {
            "blueking-language": translation.get_language(),
            "request-id": request_id,
            "X-Bkapi-Authorization": get_request_api_headers({}),
        }

        data = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        start_time = time.time()

        try:
            with requests.post(
                f"{settings.AIDEV_API_BASE_URL}/appspace/gateway/llm/v1/chat/completions",
                headers=headers,
                json=data,
                stream=stream,
                timeout=30,
            ) as response:
                response.raise_for_status()

                if not stream:
                    result = response.json()
                    return result["choices"][0]["message"]

                for chunk in response.iter_lines():
                    if not chunk:
                        continue

                    decoded_chunk = chunk.decode("utf-8")
                    if not decoded_chunk.startswith("data: "):
                        continue

                    json_chunk = decoded_chunk[6:]
                    if json_chunk.strip() == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(json_chunk)
                        if not chunk_data["choices"]:
                            continue
                        content = chunk_data["choices"][0]["delta"].get("content")
                        if not content:
                            continue
                        data_to_send = json.dumps({"event": "text", "content": content}, ensure_ascii=False)
                        yield f"data: {data_to_send}\n\n"
                    except json.JSONDecodeError:
                        continue

                yield "data: [DONE]\n\n"

        except requests.exceptions.RequestException as e:
            try:
                exc_info = response.json()
            except Exception:  # pylint: disable=broad-except
                exc_info = response.text
            logger.exception(f"[call_chat_completion] api error: {e} => {exc_info}")
            raise ApiRequestError(f"aidev request error: {e}  => {exc_info}", request_id)

        end_time = time.time() - start_time
        logger.info(f"[call_chat_completion] params: {json.dumps(data)}, time taken: {end_time}s")

    def interpret_log(self, index_set_id: str, log_data: dict, query: str, chat_context: list, stream=True):
        """
        处理日志分析请求
        :param index_set_id: 索引集ID
        :param log_data: 日志内容
        :param query: 当前聊天输入内容
        :param chat_context: 上下文信息
        :param stream: 是否流式返回
        :return: 响应生成器
        """
        # 构造系统提示词
        feature_toggle = FeatureToggleObject.toggle(AI_ASSISTANT)

        custom_conf = {}
        if feature_toggle and feature_toggle.feature_config:
            custom_conf = feature_toggle.feature_config.get("interpret_log", {})

        feature_conf = InterpretLogFeatureConf(**custom_conf)

        # 构造消息列表
        messages = [
            {"role": "system", "content": feature_conf.prompt.format(log_content=json.dumps(log_data))},
            *chat_context[-feature_conf.max_chat_context_count * 2 :],
            {"role": "user", "content": query},
        ]

        # 调用OpenAI接口
        return self.call_chat_completion(model=feature_conf.model, messages=messages, stream=stream)
