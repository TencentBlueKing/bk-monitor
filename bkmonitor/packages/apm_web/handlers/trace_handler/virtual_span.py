# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2022 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""
import functools
from dataclasses import asdict, dataclass, field

from opentelemetry import trace
from opentelemetry.semconv.trace import SpanAttributes as Attributes
from opentelemetry.trace import StatusCode

from constants.apm import OtlpKey, SpanKind

tracer = trace.get_tracer(__name__)


@dataclass
class Span:
    # 由API侧获取为字典 所以直接用dataclass替换sdk创建
    attributes: dict
    kind: int
    parent_span_id: str
    resource: dict
    status: dict
    span_id: str
    trace_id: str
    span_name: str
    elapsed_time: int
    start_time: int
    end_time: int
    trace_state: str = ""
    time: str = ""
    links: list = field(default_factory=list)
    events: list = field(default_factory=list)
    is_virtual: bool = True


class SpanInfer:
    @classmethod
    def any_contain(cls, span, fields):
        match_field = next((i for i in fields if i in span[OtlpKey.ATTRIBUTES]), None)

        return bool(match_field)

    @classmethod
    def is_contain(cls, span, field):
        return field in span[OtlpKey.ATTRIBUTES]

    @classmethod
    def create_span(cls, origin_span):
        return functools.partial(
            Span,
            parent_span_id=origin_span[OtlpKey.SPAN_ID],
            resource=origin_span[OtlpKey.RESOURCE],
            status={"code": StatusCode.OK.value, "message": ""},
            span_id=f"{origin_span[OtlpKey.SPAN_ID]}-virtual",
            trace_id=origin_span[OtlpKey.TRACE_ID],
            time="",
            elapsed_time=origin_span[OtlpKey.ELAPSED_TIME],
            start_time=origin_span[OtlpKey.START_TIME],
            end_time=origin_span[OtlpKey.END_TIME],
        )

    @classmethod
    def match(cls, span):
        raise NotImplementedError

    @classmethod
    def generate(cls, origin_span):
        raise NotImplementedError


class HttpVirtualSpan(SpanInfer):

    attributes_prefix = "http."

    CHARACTERISTIC_FIELDS = [Attributes.HTTP_HOST, Attributes.HTTP_URL, Attributes.NET_PEER_NAME]

    @classmethod
    def match(cls, span):

        if span[OtlpKey.KIND] == SpanKind.SPAN_KIND_CLIENT and cls.is_contain(span, Attributes.PEER_SERVICE):
            if cls.any_contain(span, cls.CHARACTERISTIC_FIELDS):
                return True

        return False

    @classmethod
    def generate(cls, origin_span):
        attributes = {}

        for k, v in origin_span[OtlpKey.ATTRIBUTES].items():
            if k.startswith(cls.attributes_prefix):
                attributes[k] = v

        return cls.create_span(origin_span)(
            attributes=attributes,
            kind=SpanKind.SPAN_KIND_SERVER,
            span_name=origin_span[OtlpKey.ATTRIBUTES][Attributes.PEER_SERVICE],
        )


class RpcVirtualSpan(SpanInfer):

    attributes_prefix = "rpc."

    CHARACTERISTIC_FIELDS = [Attributes.RPC_SERVICE, Attributes.NET_PEER_NAME, Attributes.RPC_SYSTEM]

    @classmethod
    def match(cls, span):
        if span[OtlpKey.KIND] == SpanKind.SPAN_KIND_CLIENT and cls.is_contain(span, Attributes.RPC_SYSTEM):
            return True

        return False

    @classmethod
    def generate(cls, origin_span):
        attributes = {}
        for k, v in origin_span[OtlpKey.ATTRIBUTES].items():
            if k.startswith(cls.attributes_prefix):
                attributes[k] = v

        span_name = next(
            origin_span[OtlpKey.ATTRIBUTES][i]
            for i in cls.CHARACTERISTIC_FIELDS
            if i in origin_span[OtlpKey.ATTRIBUTES]
        )

        return cls.create_span(origin_span)(attributes=attributes, kind=SpanKind.SPAN_KIND_SERVER, span_name=span_name)


class GenericServiceVirtualSpan(SpanInfer):
    @classmethod
    def match(cls, span):
        if span[OtlpKey.KIND] == SpanKind.SPAN_KIND_CLIENT and cls.is_contain(span, Attributes.PEER_SERVICE):
            return True

        return False

    @classmethod
    def generate(cls, origin_span):
        span_name = origin_span[OtlpKey.ATTRIBUTES][Attributes.PEER_SERVICE]

        return cls.create_span(origin_span)(attributes={}, kind=SpanKind.SPAN_KIND_SERVER, span_name=span_name)


class MessagePubVirtualSpan(SpanInfer):

    attributes_prefix = "messaging."

    @classmethod
    def match(cls, span):
        if span[OtlpKey.KIND] == SpanKind.SPAN_KIND_PRODUCER and cls.is_contain(span, Attributes.MESSAGING_DESTINATION):
            return True

        return False

    @classmethod
    def generate(cls, origin_span):
        attributes = {}

        for k, v in origin_span[OtlpKey.ATTRIBUTES].items():
            if k.startswith(cls.attributes_prefix):
                attributes[k] = v

        return cls.create_span(origin_span)(
            attributes=attributes,
            kind=SpanKind.SPAN_KIND_CONSUMER,
            span_name=origin_span[OtlpKey.ATTRIBUTES][Attributes.MESSAGING_DESTINATION],
        )


class DatabaseVirtualSpan(SpanInfer):

    attributes_prefix = "db."

    CHARACTERISTIC_FIELDS = [Attributes.DB_SYSTEM, Attributes.DB_NAME, "db.type", "db.instance"]

    @classmethod
    def match(cls, span):
        if span[OtlpKey.KIND] == SpanKind.SPAN_KIND_CLIENT and cls.any_contain(span, cls.CHARACTERISTIC_FIELDS):
            return True

        return False

    @classmethod
    def generate(cls, origin_span):
        attributes = {}

        for k, v in origin_span[OtlpKey.ATTRIBUTES].items():
            if k.startswith(cls.attributes_prefix):
                attributes[k] = v

        span_name = next(
            origin_span[OtlpKey.ATTRIBUTES][i]
            for i in cls.CHARACTERISTIC_FIELDS
            if i in origin_span[OtlpKey.ATTRIBUTES]
        )

        return cls.create_span(origin_span)(attributes=attributes, kind=SpanKind.SPAN_KIND_SERVER, span_name=span_name)


class SpanInferContainer:
    infers = [
        HttpVirtualSpan,
        RpcVirtualSpan,
        GenericServiceVirtualSpan,
        MessagePubVirtualSpan,
        DatabaseVirtualSpan,
    ]

    @classmethod
    def list(cls):
        return cls.infers


class VirtualSpanHandler:
    @classmethod
    def generate(cls, spans):

        virtual_spans = []

        for span in spans:
            match_processor = next((i for i in SpanInferContainer.list() if i.match(span)), None)
            if not match_processor:
                continue

            virtual_spans.append(asdict(match_processor.generate(span)))

        return virtual_spans
