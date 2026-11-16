"""嵌入式 Hermes 执行适配：平台继续负责资源、会话和请求级工具授权。"""

import contextvars
import hashlib
import json
import logging
import re
import time
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from ai_agent.services.hermes_history import convert_session_context
from ai_agent.services.hermes_runtime import prepare_home, require_runtime

logger = logging.getLogger("ai_whale")


def _sse(event, **data):
    return f"data: {json.dumps({'event': event, **data}, ensure_ascii=False, default=str)}\n\n"


def _error():
    # 提供方异常可能含认证头、请求地址或工具凭据，不能原样返回浏览器。
    return _sse("error", code=500, message="智能体执行失败，请稍后重试或联系管理员查看 Trace")


class ContextIterator:
    def __init__(self, iterator, context, on_unstarted_close=None):
        self.iterator = iterator
        self.context = context
        self.on_unstarted_close = on_unstarted_close
        self.started = False
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.closed:
            raise StopIteration
        self.started = True
        try:
            return self.context.run(next, self.iterator)
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            close = getattr(self.iterator, "close", None)
            if callable(close):
                self.context.run(close)
        finally:
            if not self.started and self.on_unstarted_close is not None:
                self.context.run(self.on_unstarted_close)


def iterate_in_context(iterator, context, on_unstarted_close=None):
    return ContextIterator(iterator, context, on_unstarted_close)


def tools_to_hermes(tools):
    from hermes_core import HermesTool

    converted, used = [], set()
    for tool in tools:
        base = re.sub(r"[^A-Za-z0-9_-]", "_", str(tool.name or "tool"))[:110]
        if not re.match(r"^[A-Za-z_]", base):
            base = f"t_{base}"
        name, index = base, 1
        while name in used:
            name, index = f"{base}_{index}", index + 1
        used.add(name)
        schema = getattr(tool, "args_schema", None)
        if isinstance(schema, dict):
            parameters = schema
        elif hasattr(schema, "model_json_schema"):
            parameters = schema.model_json_schema()
        elif hasattr(schema, "schema"):
            parameters = schema.schema()
        else:
            parameters = {"type": "object", "properties": {}}
        converted.append(
            HermesTool(
                name=name,
                description=str(tool.description or name),
                parameters=parameters,
                handler=tool_handler(tool),
            )
        )
    return converted


def tool_handler(tool):
    if getattr(tool, "coroutine", None) is not None and getattr(tool, "func", None) is None:

        async def invoke_async(**arguments):
            return await tool.ainvoke(arguments)

        return invoke_async

    def invoke(**arguments):
        return tool.invoke(arguments)

    return invoke


def build_model_config(session_id, model, app_code, app_secret, temperature):
    from hermes_core import AgentConfig

    direct_key = str(getattr(settings, "AI_AGENT_HERMES_LLM_API_KEY", "") or "").strip()
    if direct_key:
        endpoint = str(getattr(settings, "AI_AGENT_HERMES_LLM_BASE_URL", "") or "").strip()
        model = str(getattr(settings, "AI_AGENT_HERMES_LLM_MODEL", "") or "").strip()
        provider = str(getattr(settings, "AI_AGENT_HERMES_LLM_PROVIDER", "") or "").strip()
        if not all((endpoint, model, provider)):
            raise ImproperlyConfigured("Hermes 直连模型必须配置 BASE_URL、MODEL 和 PROVIDER")
        overrides = {"temperature": temperature}
        api_key = direct_key
    else:
        from aidev_agent.config import settings as aidev_settings

        endpoint = str(
            getattr(settings, "AIDEV_AGENT_LLM_GW_ENDPOINT", "") or aidev_settings.LLM_GW_ENDPOINT or ""
        ).strip()
        if not endpoint or not model:
            raise ImproperlyConfigured("Hermes 缺少模型网关地址或模型名称")
        api_key = getattr(settings, "AI_AGENT_HERMES_ACCESS_TOKEN", "") or "empty"
        overrides = {
            "temperature": temperature,
            "extra_headers": {
                "X-Bkapi-Authorization": json.dumps({"bk_app_code": app_code, "bk_app_secret": app_secret}),
                "X-Model-Name": model,
            },
        }
    return AgentConfig(
        base_url=endpoint,
        api_key=api_key,
        model=model,
        session_id=session_id,
        home=prepare_home(),
        enabled_toolsets=(),
        max_iterations=int(getattr(settings, "AI_AGENT_HERMES_MAX_ITERATIONS", 15)),
        request_overrides=overrides,
        extra_agent_kwargs={
            "session_db": None,
            "skip_context_files": True,
            "load_soul_identity": True,
        },
    )


def build_telemetry(agent_config, agent_code, username):
    from hermes_core import TelemetryConfig

    enabled = bool(getattr(settings, "AI_AGENT_OTEL_ENABLED", False))
    if enabled:
        from bkai_otel_hermes import instrument_sdk
        from opentelemetry import trace

        if not instrument_sdk(tracer_provider=trace.get_tracer_provider()):
            raise ImproperlyConfigured("Hermes 观测初始化失败，请检查宿主 TracerProvider 或 OTLP 配置")
    direct_key = getattr(settings, "AI_AGENT_HERMES_LLM_API_KEY", "")
    return TelemetryConfig(
        enabled=enabled,
        agent_id=agent_code,
        agent_name=str(getattr(agent_config, "agent_name", "") or agent_code),
        agent_version=str(getattr(settings, "VERSION", "") or ""),
        provider_name=getattr(settings, "AI_AGENT_HERMES_LLM_PROVIDER", "") if direct_key else "bkaidev",
        user_id=username,
        user_name=username,
        capture_content=bool(getattr(settings, "AI_AGENT_OTEL_CAPTURE_CONTENT", False)),
    )


class HermesChatExecutor:
    def __init__(self, interface, session_code, agent_code, username, context, config_manager, temperature=0.3):
        self.interface = interface
        self.session_code = session_code
        self.agent_code = agent_code
        self.username = username
        self.context = context
        self.config_manager = config_manager
        self.temperature = temperature
        self.on_error = None

    def prepare(self):
        from aidev_agent.packages.langchain.tools.base import make_mcp_tools
        from hermes_core import HermesAgent, HermesTool

        config = self.config_manager.get_config(self.agent_code, self.interface.api_client)
        prompt, history, message = convert_session_context(self.context)
        structured = [self.interface.api_client.construct_tool(code) for code in config.tool_codes or []]
        if config.mcp_server_config:
            structured.extend(make_mcp_tools(config.mcp_server_config))
        tools = tools_to_hermes(structured)
        knowledgebases = list(getattr(config, "knowledgebase_ids", None) or [])
        knowledge_ids = list(getattr(config, "knowledge_ids", None) or [])
        if knowledgebases or knowledge_ids:

            def knowledge_query(query):
                return self.interface.api_client.knowledge_query(
                    {
                        "knowledgebase_ids": knowledgebases,
                        "knowledge_ids": knowledge_ids,
                        "query": query,
                        "type": "knowledge",
                    }
                )

            name, index = "aidev_knowledge_query", 1
            while any(tool.name == name for tool in tools):
                name, index = f"aidev_knowledge_query_{index}", index + 1
            tools.append(
                HermesTool(
                    name=name,
                    description="查询当前智能体已挂载的知识库，返回相关知识片段。",
                    parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                    handler=knowledge_query,
                )
            )
        # SDK 会话与插件内部状态也按当前身份隔离；业务历史只从平台恢复。
        sdk_session = hashlib.sha256(f"{self.username}\0{self.session_code}".encode()).hexdigest()
        model_config = build_model_config(
            sdk_session, config.llm_model_name, self.interface.app_code, self.interface.app_secret, self.temperature
        )
        agent = HermesAgent(
            model_config, tools=tools, telemetry=build_telemetry(config, self.agent_code, self.username)
        )
        return agent, prompt or config.role_prompt or None, history, message

    def persist(self, content):
        if not content:
            return
        from opentelemetry import trace

        with trace.get_tracer(__name__).start_as_current_span("ai_whale.persist_reply"):
            result = self.interface.api_client.api.create_chat_session_content(
                json={"session_code": self.session_code, "role": "ai", "content": content, "property": {}}
            )
            if isinstance(result, dict) and result.get("result") is False:
                raise RuntimeError("智能体回复保存失败")

    def execute_invoke(self):
        agent = None
        try:
            agent, prompt, history, message = self.prepare()
            result = agent.run(message, history=history, system_prompt=prompt)
            self.persist(result.text)
            return {
                "choices": [{"delta": {"role": "assistant", "content": result.text}}],
                "model": agent.config.model,
                "id": uuid4().hex,
                "usage": dict(result.usage or {}),
            }
        except Exception as error:
            logger.error("Hermes completion failed (%s)", type(error).__name__)
            raise RuntimeError("智能体执行失败，请稍后重试或联系管理员查看 Trace") from None
        finally:
            if agent is not None:
                agent.close()

    def execute_stream(self):
        request_context = contextvars.copy_context()
        # 配置和工具在请求阶段装配，避免延迟生成器丢失请求身份。
        try:
            prepared = self.prepare()
        except Exception as error:
            logger.error("Hermes preparation failed (%s)", type(error).__name__)
            raise RuntimeError("智能体初始化失败，请联系管理员查看运行配置") from None
        return iterate_in_context(self._stream(*prepared), request_context, prepared[0].close)

    def _stream(self, agent, prompt, history, message):
        parts, completed = [], False
        started = time.monotonic()
        events = None
        try:
            events = agent.stream(
                message,
                history=history,
                system_prompt=prompt,
                heartbeat_interval_seconds=float(getattr(settings, "AI_AGENT_STREAM_HEARTBEAT_INTERVAL_SECONDS", 10)),
            )
            for event in events:
                if event.type == "text_delta":
                    parts.append(event.delta)
                    yield _sse("text", content=event.delta, cover=False)
                elif event.type in ("tool_start", "tool_end"):
                    call = event.tool_call
                    if event.type == "tool_start":
                        text = json.dumps({"action": call.name, "action_input": call.arguments}, ensure_ascii=False)
                    else:
                        text = "工具执行结束；回答将引用本轮结果。"
                    yield _sse("think", content=f"\n```json\n{text}\n```\n", cover=False)
                elif event.type == "heartbeat":
                    yield ": heartbeat\n\n"
                elif event.type == "error":
                    raise RuntimeError("SDK 返回执行失败")
                elif event.type == "done":
                    if not parts and event.result is not None and event.result.text:
                        parts.append(event.result.text)
                        yield _sse("text", content=event.result.text, cover=False)
                    content = "".join(parts)
                    self.persist(content)
                    completed = True
                    yield _sse("think", content="\n", cover=False, elapsed_time=(time.monotonic() - started) * 1000)
                    yield _sse("done", content=content, cover=False)
            if not completed:
                raise RuntimeError("SDK 流缺少完成事件")
        except GeneratorExit:
            agent.interrupt()
            raise
        except Exception as error:
            logger.error("Hermes completion failed (%s)", type(error).__name__)
            if self.on_error is not None:
                self.on_error(RuntimeError("智能体执行或回复保存失败"))
            yield _error()
        finally:
            try:
                close = getattr(events, "close", None)
                if callable(close):
                    close()
            finally:
                agent.close()
        yield "data: [DONE]\n\n"


def create_chat_completion(
    interface, *, session_code, execute_kwargs, agent_code, username, temperature, switch_agent_by_scene
):
    from aidev_agent.services.agent import AgentInstanceFactory

    from ai_agent.core.custom_config_manager import CustomConfigManager
    from ai_agent.services.metrics_reporter import EnhancedStreamingResponseWrapper, StreamingMetricsTracker

    require_runtime()

    class RequestConfigManager(CustomConfigManager):
        # 配置包含用户 MCP 认证头，缓存只在这一轮请求内复用。
        _config_cache = {}

    session = interface.retrieve_chat_session(session_code)
    factory = AgentInstanceFactory(
        agent_code=agent_code,
        session_code=session_code,
        resource_manager=interface.api_client,
        config_manager_class=RequestConfigManager,
        switch_agent_by_scene=switch_agent_by_scene,
        is_temporary=bool((session.get("data") or {}).get("is_temporary", False)),
    )
    prepared = factory._build_from_session()
    factory.handle_agent_switch(prepared["session_context_data"], prepared["agent_code"], prepared["switch_agent"])
    executor = HermesChatExecutor(
        interface,
        session_code,
        prepared["agent_code"],
        username,
        prepared["session_context_data"],
        RequestConfigManager,
        temperature,
    )
    if not execute_kwargs.get("stream", False):
        return executor.execute_invoke()
    tracker = StreamingMetricsTracker(
        ai_metrics_reporter=interface.metrics_reporter,
        resource_name="CreateChatCompletionResource",
        agent_code=prepared["agent_code"],
        username=username,
    )
    executor.on_error = tracker.on_streaming_error
    return EnhancedStreamingResponseWrapper(executor.execute_stream(), tracker).as_streaming_response()
