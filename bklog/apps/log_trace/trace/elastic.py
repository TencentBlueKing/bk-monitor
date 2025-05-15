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

import json
from logging import getLogger

import elasticsearch
from opentelemetry.instrumentation import elasticsearch as elasticsearch_instrument
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.trace import SpanKind, get_tracer
from wrapt import wrap_function_wrapper as _wrap

logger = getLogger(__name__)


class BkElasticsearchInstrumentor(elasticsearch_instrument.ElasticsearchInstrumentor):
    def _instrument(self, **kwargs):
        """
        Instruments elasticsearch module
        """
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(elasticsearch_instrument.__name__, elasticsearch_instrument.__version__, tracer_provider)
        request_hook = kwargs.get("request_hook")
        response_hook = kwargs.get("response_hook")
        _wrap(
            elasticsearch,
            "Transport.perform_request",
            _wrap_perform_request(tracer, self._span_name_prefix, request_hook, response_hook),
        )


def _wrap_perform_request(tracer, span_name_prefix, request_hook=None, response_hook=None):
    # pylint: disable=R0912,R0914
    def wrapper(wrapped, _, args, kwargs):
        method = url = None
        try:
            method, url, *_ = args
        except IndexError:
            logger.warning(
                "expected perform_request to receive two positional arguments. Got %d",
                len(args),
            )

        op_name = f"{span_name_prefix} {elasticsearch_instrument._DEFAULT_OP_NAME}"

        doc_id = None
        search_target = None

        if url:
            match = elasticsearch_instrument._regex_doc_url.search(url)
            if match is not None:
                # Remove the full document ID from the URL
                # doc_span = match.span()
                # op_name = (
                #     span_name_prefix
                #     + url[: doc_span[0]]
                #     + "/_doc/:id"
                #     + url[doc_span[1] :]
                # )
                # Put the document ID in attributes
                doc_id = match.group(1)
            match = elasticsearch_instrument._regex_search_url.search(url)
            if match is not None:
                # op_name = span_name_prefix + "/<target>/_search"
                search_target = match.group(1)

        params = kwargs.get("params", {})
        body = kwargs.get("body", None)

        with tracer.start_as_current_span(
            op_name,
            kind=SpanKind.CLIENT,
        ) as span:
            if callable(request_hook):
                request_hook(span, method, url, kwargs)

            if span.is_recording():
                attributes = {
                    SpanAttributes.DB_SYSTEM: "elasticsearch",
                }
                if url:
                    attributes["elasticsearch.url"] = url
                if method:
                    attributes["elasticsearch.method"] = method
                if body:
                    try:
                        body = json.dumps(body)
                    except Exception:  # pylint: disable=broad-except
                        body = str(body)
                    attributes[SpanAttributes.DB_STATEMENT] = body
                if params:
                    try:
                        params = json.dumps(params)
                    except Exception:  # pylint: disable=broad-except
                        params = str(params)
                    attributes["elasticsearch.params"] = params
                if doc_id:
                    attributes["elasticsearch.id"] = doc_id
                if search_target:
                    attributes["elasticsearch.target"] = search_target
                for key, value in attributes.items():
                    span.set_attribute(key, value)

            rv = wrapped(*args, **kwargs)
            if isinstance(rv, dict) and span.is_recording():
                for member in elasticsearch_instrument._ATTRIBUTES_FROM_RESULT:
                    if member in rv:
                        span.set_attribute(
                            f"elasticsearch.{member}",
                            str(rv[member]),
                        )

            if callable(response_hook):
                response_hook(span, rv)
            return rv

    return wrapper
