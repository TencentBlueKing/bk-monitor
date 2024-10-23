# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

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
                "expected perform_request to receive two positional arguments. " "Got %d",
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
                    attributes[SpanAttributes.DB_STATEMENT] = str(body)
                if params:
                    attributes["elasticsearch.params"] = str(params)
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
