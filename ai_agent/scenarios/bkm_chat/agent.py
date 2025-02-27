# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# views.py
import json
import queue

from django.http import StreamingHttpResponse
from langchain.agents import Agent, AgentExecutor
from langchain.callbacks.base import BaseCallbackHandler

from ai_agent.core.qa.retriever import retrieve
from ai_agent.llm import LLMConfig, LLMModel, LLMProvider, get_llm


class StreamCallbackHandler(BaseCallbackHandler):
    """自定义回调处理器用于捕获Agent执行事件"""

    def __init__(self, event_queue):
        self.event_queue = event_queue

    def on_agent_action(self, action, **kwargs):
        """捕获AgentAction事件"""
        event_data = {"type": "action", "tool": action.tool, "input": action.tool_input, "log": action.log}
        self.event_queue.put(event_data)

    def on_agent_finish(self, finish, **kwargs):
        """捕获AgentFinish事件"""
        event_data = {"type": "finish", "output": finish.return_values.get('output'), "log": finish.log}
        self.event_queue.put(event_data)


def agent_event_stream(request):
    """SSE事件流生成器"""
    event_queue = queue.Queue()

    agent = init_agent()
    callback_handler = StreamCallbackHandler(event_queue)

    # 异步执行Agent
    def run_agent():
        agent_executor = AgentExecutor.from_agent_and_tools(agent=agent, tools=[], callback_handlers=[callback_handler])
        agent_executor.run(request.GET.get('query', ''))

    # 启动Agent执行线程
    import threading

    thread = threading.Thread(target=run_agent)
    thread.start()

    # 生成事件流
    while True:
        try:
            event_data = event_queue.get(timeout=1)
            yield f"data: {json.dumps(event_data)}\n\n"

            if event_data.get('type') == 'finish':
                break

        except queue.Empty:
            yield "event: heartbeat\ndata: \n\n"
            break


# 路由配置
def agent_stream_view(request):
    response = StreamingHttpResponse(agent_event_stream(request), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['Connection'] = 'keep-alive'
    return response


def init_agent():
    """
    初始化Agent
    """

    llm = get_llm(LLMConfig(provider=LLMProvider.BLUEKING, model=LLMModel.HUNYUAN_TURBO))
    agent = Agent.from_llm_and_tools(llm=llm, tools=[retrieve])
    return agent
