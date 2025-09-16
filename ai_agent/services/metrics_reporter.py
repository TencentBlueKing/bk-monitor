"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time
import json
import logging
from functools import wraps
from typing import Any
from collections.abc import Generator
from ai_agent.utils import get_request_username
from django.conf import settings
from django.http import StreamingHttpResponse

logger = logging.getLogger("ai_whale")


# ===================== 状态常量 =====================


class RequestStatus:
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    STREAMING = "streaming"
    STARTED = "started"
    COMPLETED = "completed"


# ===================== 指标上报基类 =====================


class AIMetricsReporter:
    """AI小鲸指标上报器"""

    def __init__(self, requests_total, requests_cost):
        """
        第一期包含总数统计 / 耗时统计两个指标
        """
        self.requests_total = requests_total
        self.requests_cost = requests_cost

    def report_request(
        self,
        resource_name: str,
        status: str,
        duration: float | None = None,
        agent_code: str | None = None,
        username: str | None = None,
        command: str | None = None,
    ):
        """
        上报请求指标
        @params resource_name: 资源名称（Resource类名）
        @params status: 请求状态
        @params duration: 请求耗时（秒）
        @params agent_code: Agent代码
        @params username: 用户名
        """
        # 获取默认值
        agent_code = agent_code or "unknown"
        username = username or get_request_username()

        # 上报请求总数
        self.requests_total.labels(
            agent_code=agent_code,
            resource_name=resource_name,
            status=status,
            username=username,
            command=command,
        ).inc()

        # 上报请求耗时(如有)
        if duration is not None:
            self.requests_cost.labels(
                agent_code=agent_code,
                resource_name=resource_name,
                status=status,
                username=username,
                command=command,
            ).set(duration)

        logger.info(
            f"AIMetricsReporter: resource={resource_name}, status={status}, "
            f"duration={duration}, agent_code={agent_code}"
        )


# ===================== 装饰器实现 =====================


def ai_metrics_decorator(
    ai_metrics_reporter, extract_agent_code_func=None, extract_username_func=None, extract_command_func=None
):
    """
    AI服务指标上报装饰器

    Args:
        ai_metrics_reporter: 指标上报器实例
        extract_agent_code_func: 提取agent_code的函数
        extract_username_func: 提取username的函数
        extract_command_func: 提取command的函数
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, validated_request_data, *args, **kwargs):
            resource_name = self.__class__.__name__
            start_time = time.time()

            # 提取标签值
            agent_code = None
            username = None
            command = None

            try:
                # 从请求数据中提取标签
                if extract_agent_code_func:
                    agent_code = extract_agent_code_func(validated_request_data)
                else:
                    agent_code = validated_request_data.get("agent_code")

                if extract_username_func:
                    username = extract_username_func(validated_request_data)

                if extract_command_func:
                    command = extract_command_func(validated_request_data)

                # 上报开始状态
                ai_metrics_reporter.report_request(
                    resource_name=resource_name,
                    status=RequestStatus.STARTED,
                    agent_code=agent_code,
                    username=username,
                    command=command,
                )

                # 执行原方法
                result = func(self, validated_request_data, *args, **kwargs)

                # 计算耗时
                duration = time.time() - start_time

                # 判断是否为流式响应
                if hasattr(result, "as_streaming_response"):
                    # 流式响应
                    status = RequestStatus.STREAMING
                else:
                    # 普通响应
                    status = RequestStatus.SUCCESS

                # 上报成功状态和耗时
                ai_metrics_reporter.report_request(
                    resource_name=resource_name,
                    status=status,
                    duration=duration,
                    agent_code=agent_code,
                    username=username,
                    command=command,
                )

                return result

            except Exception as e:
                # 计算耗时
                duration = time.time() - start_time

                # 上报错误状态和耗时
                ai_metrics_reporter.report_request(
                    resource_name=resource_name,
                    status=RequestStatus.ERROR,
                    duration=duration,
                    agent_code=agent_code,
                    username=username,
                    command=command,
                )

                logger.error(f"AIMetricsReporter: AI service error in {resource_name}: {e}")
                raise

        return wrapper

    return decorator


# ===================== 参数提取方法 =====================


def extract_command_from_request(validated_request_data):
    """提取快捷指令类型"""
    try:
        property_data = validated_request_data.get("property", {})
        command_data = property_data.get("extra", {})
        command = command_data.get("command")
        if command:
            return command  # 返回具体的指令名称
        return "none"
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"AIMetricsReporter: Failed to extract command: {e}")
        return "none"


def extract_agent_code_from_request(validated_request_data):
    """自定义Agent代码提取函数"""
    return validated_request_data.get("agent_code", settings.AIDEV_AGENT_APP_CODE)


# ===================== 流式响应指标上报器 =====================


class StreamingMetricsTracker:
    """流式响应指标跟踪器"""

    def __init__(self, ai_metrics_reporter: AIMetricsReporter, resource_name: str, agent_code: str, username: str):
        self.resource_name = resource_name
        self.agent_code = agent_code
        self.username = username

        # 上报器实例
        self.ai_metrics_reporter = ai_metrics_reporter

        # 时间节点
        self.start_time = time.time()
        self.first_chunk_time = None
        self.last_chunk_time = None
        self.end_time = None

        # 统计信息
        self.chunk_count = 0
        self.total_size = 0
        self.error_occurred = False
        self.error_message = None

    def on_first_chunk(self):
        """第一个数据块产生时调用"""
        if self.first_chunk_time is None:
            self.first_chunk_time = time.time()

            # 上报流式开始指标（到第一个chunk的耗时）
            setup_duration = self.first_chunk_time - self.start_time
            self.ai_metrics_reporter.report_request(
                resource_name=self.resource_name,
                status=RequestStatus.STREAMING,
                duration=setup_duration,
                agent_code=self.agent_code,
                username=self.username,
            )

            logger.info(f"AIMetricsReporter: Streaming started, setup time: {setup_duration:.3f}s")

    def on_chunk_yield(self, chunk: Any):
        """每次产生数据块时调用"""
        self.chunk_count += 1
        self.last_chunk_time = time.time()

        # 统计数据大小（如果是字符串）
        if isinstance(chunk, str | bytes):
            self.total_size += len(chunk)

    def on_streaming_complete(self):
        """流式响应完成时调用"""
        self.end_time = time.time()

        # 计算各种耗时
        total_duration = self.end_time - self.start_time
        streaming_duration = (self.end_time - self.first_chunk_time) if self.first_chunk_time else 0

        # 上报完成指标
        self.ai_metrics_reporter.report_request(
            resource_name=self.resource_name,
            status=RequestStatus.COMPLETED,
            duration=total_duration,
            agent_code=self.agent_code,
            username=self.username,
        )

        # 上报流式统计信息（用额外的指标记录）
        self.ai_metrics_reporter.report_request(
            resource_name=f"{self.resource_name}_StreamingStats",
            status="chunk_count",
            duration=self.chunk_count,  # 使用duration字段存储chunk数量
            agent_code=self.agent_code,
            username=self.username,
        )

        logger.info(
            f"AIMetricsReporter: Streaming completed: total={total_duration:.3f}s, "
            f"streaming={streaming_duration:.3f}s, chunks={self.chunk_count}, "
            f"size={self.total_size} bytes"
        )

    def on_streaming_error(self, error: Exception):
        """流式响应出错时调用"""
        self.error_occurred = True
        self.error_message = str(error)
        self.end_time = time.time()

        total_duration = self.end_time - self.start_time

        # 上报错误指标
        self.ai_metrics_reporter.report_request(
            resource_name=self.resource_name,
            status=RequestStatus.ERROR,
            duration=total_duration,
            agent_code=self.agent_code,
            username=self.username,
        )

        logger.error(f"AIMetricsReporter: Streaming error after {total_duration:.3f}s: {error}")


# ===================== 增强的流式响应包装器 =====================


class EnhancedStreamingResponseWrapper:
    """增强的流式响应包装器，支持指标统计"""

    def __init__(self, generator: Generator, metrics_tracker: StreamingMetricsTracker):
        self.original_generator = generator
        self.metrics_tracker = metrics_tracker

    def _monitored_generator(self):
        """带监控的生成器"""
        try:
            first_chunk = True
            for chunk in self.original_generator:
                if first_chunk:
                    self.metrics_tracker.on_first_chunk()
                    first_chunk = False

                # 过滤逻辑：跳过event为think的数据块
                if self._should_skip_chunk(chunk):
                    continue

                self.metrics_tracker.on_chunk_yield(chunk)
                yield chunk

            # 流式响应正常完成
            self.metrics_tracker.on_streaming_complete()

        except Exception as error:
            # 流式响应出错
            self.metrics_tracker.on_streaming_error(error)
            raise

    def _should_skip_chunk(self, chunk):
        """判断是否应该跳过当前数据块"""
        try:
            # 检查chunk是否为字符串且以'data: '开头
            if isinstance(chunk, str) and chunk.startswith('data: '):
                # 提取JSON部分
                json_str = chunk[6:]  # 去掉'data: '前缀
                data = json.loads(json_str)

                # 检查event字段是否为'think'
                if data.get('event') == 'think':
                    logger.debug(f"EnhancedStreamingResponseWrapper: Skipping chunk with event=think")
                    return True

        except (json.JSONDecodeError, AttributeError, KeyError) as e:
            # JSON解析失败或其他错误，不跳过该chunk
            logger.debug(f"EnhancedStreamingResponseWrapper: Failed to parse chunk for filtering: {e}")

        return False

    def as_streaming_response(self):
        """转换为 Django 流式响应"""
        sr = StreamingHttpResponse(self._monitored_generator())
        sr.headers["Cache-Control"] = "no-cache"
        sr.headers["X-Accel-Buffering"] = "no"
        sr.headers["content-type"] = "text/event-stream"
        return sr


# ===================== 改进的装饰器 =====================


def ai_enhanced_streaming_metrics(ai_metrics_reporter: AIMetricsReporter):
    """增强的流式响应指标装饰器"""

    def decorator(func):
        @wraps(func)
        def wrapper(self, validated_request_data, *args, **kwargs):
            resource_name = self.__class__.__name__
            start_time = time.time()

            # 提取标签值
            agent_code = validated_request_data.get("agent_code", "unknown")
            username = get_request_username()
            execute_kwargs = validated_request_data["execute_kwargs"]

            try:
                # 上报请求开始
                ai_metrics_reporter.report_request(
                    resource_name=resource_name,
                    status=RequestStatus.STARTED,
                    agent_code=agent_code,
                    username=username,
                )

                # 执行原方法
                result = func(self, validated_request_data, *args, **kwargs)

                # 对于流式响应，我们不在这里上报完成状态
                # 完成状态由 StreamingMetricsTracker 负责上报
                if execute_kwargs.get("stream", False):
                    setup_duration = time.time() - start_time
                    logger.info(f"Streaming response setup completed in {setup_duration:.3f}s")
                else:
                    # 非流式响应，正常上报
                    duration = time.time() - start_time
                    ai_metrics_reporter.report_request(
                        resource_name=resource_name,
                        status=RequestStatus.SUCCESS,
                        duration=duration,
                        agent_code=agent_code,
                        username=username,
                    )

                return result

            except Exception as e:
                duration = time.time() - start_time
                ai_metrics_reporter.report_request(
                    resource_name=resource_name,
                    status=RequestStatus.ERROR,
                    duration=duration,
                    agent_code=agent_code,
                    username=username,
                )
                logger.error(f"AIMetricsReporter: AI streaming service error in {resource_name}: {e}")
                raise

        return wrapper

    return decorator
