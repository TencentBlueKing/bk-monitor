# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import logging  # noqa
from logging.handlers import DatagramHandler

from opentelemetry import trace
from opentelemetry.sdk._logs import LoggingHandler as OTLPHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.trace import format_trace_id

"""
Usage:

    from apps.common.log import logger

    logger.info("test")
    logger.error("wrong1")
    logger.exception("wrong2")

    # with traceback
    try:
        1 / 0
    except Exception:
        logger.exception("wrong3")
"""

from apps.utils.local import get_request_id  # noqa  pylint: disable=unused-import

logger_detail = logging.getLogger("root")


class UdpHandler(DatagramHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            self.send(msg.encode())
        except Exception:  # pylint:disable=broad-except
            self.handleError(record)


class LazyBatchLogProcessor(BatchLogRecordProcessor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # shutdown
        self._shutdown = True
        with self._condition:
            self._condition.notify_all()
        self._worker_thread.join()
        # clean worker thread
        self._shutdown = False
        self._worker_thread = None

    def emit(self, log_data) -> None:
        # re init work thread
        if self._worker_thread is None:
            self._at_fork_reinit()
        # emit
        super().emit(log_data)

    def shutdown(self) -> None:
        # shutdown
        self._shutdown = True
        with self._condition:
            self._condition.notify_all()
        # work thread exist
        if self._worker_thread:
            self._worker_thread.join()
        # shutdown exporter
        self._exporter.shutdown()


class OTLPLogHandler(OTLPHandler):
    """A handler class which writes logging records, in OTLP format, to
    a network destination or file.
    """

    def __init__(self, level=logging.NOTSET) -> None:
        from django.conf import settings
        from opentelemetry._logs._internal import set_logger_provider
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs import LoggerProvider
        from opentelemetry.sdk.resources import Resource

        service_name = settings.SERVICE_NAME or settings.APP_CODE
        otlp_grpc_host = settings.OTLP_GRPC_HOST
        otlp_bk_log_token = settings.OTLP_BK_LOG_TOKEN

        log_emitter_provider = LoggerProvider(
            resource=Resource.create({"service.name": service_name, "bk.data.token": otlp_bk_log_token})
        )
        set_logger_provider(log_emitter_provider)

        # init exporter
        exporter = OTLPLogExporter(endpoint=otlp_grpc_host)
        log_emitter_provider.add_log_record_processor(LazyBatchLogProcessor(exporter))
        super(OTLPLogHandler, self).__init__(level=level, logger_provider=log_emitter_provider.get_logger(service_name))


# ===============================================================================
# 自定义添加打印内容
# ===============================================================================
# traceback--打印详细错误日志
class LoggerTraceback(object):
    """
    详细异常信息追踪
    """

    def error(self, message="", *args, **kwargs):
        """
        打印 error 日志方法
        """
        message = self.build_message(message)
        logger_detail.error(message, *args, **kwargs)

    def info(self, message="", *args, **kwargs):
        """
        info 日志
        """
        message = self.build_message(message)
        logger_detail.info(message, *args, **kwargs)

    def warning(self, message="", *args, **kwargs):
        """
        warning 日志
        """
        message = self.build_message(message)
        logger_detail.warning(message, *args, **kwargs)

    def debug(self, message="", *args, **kwargs):
        """
        debug 日志
        """
        message = self.build_message(message)
        logger_detail.debug(message, *args, **kwargs)

    def critical(self, message="", *args, **kwargs):
        """
        critical 日志
        """
        message = self.build_message(message)
        logger_detail.critical(message, *args, **kwargs)

    def exception(self, message="", *args, **kwargs):
        message = self.build_message(message)
        logger_detail.exception(message, *args, **kwargs)

    @staticmethod
    def build_message(message):
        trace_id = trace.get_current_span().get_span_context().trace_id
        return "{} | {}".format(format_trace_id(trace_id), message)


# traceback--打印详细错误日志
logger = LoggerTraceback()


def requests_curl_log(resp, *args, **kwargs):
    """记录requests curl log"""
    # 添加日志信息
    curl_req = "REQ: curl -X {method} '{url}'".format(method=resp.request.method, url=resp.request.url)

    if resp.request.body:
        curl_req += " -d '{body}'".format(body=resp.request.body)

    if resp.request.headers:
        for key, value in resp.request.headers.items():
            # ignore headers
            if key in ["User-Agent", "Accept-Encoding", "Connection", "Accept", "Content-Length"]:
                continue
            if key == "Cookie" and value.startswith("x_host_key"):
                continue

            curl_req += " -H '{k}: {v}'".format(k=key, v=value)

    if resp.headers.get("Content-Type", "").startswith("application/json"):
        resp_text = resp.content
    else:
        resp_text = f"Bin...(total {len(resp.content)} Bytes)"

    curl_resp = "RESP: [{}] {:.2f}ms {}".format(resp.status_code, resp.elapsed.total_seconds() * 1000, resp_text)

    logger.info("%s\n \t %s", curl_req, curl_resp)
