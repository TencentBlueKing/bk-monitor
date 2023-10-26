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
from apm_web.constants import CategoryEnum
from apm_web.icon import TraceIcon
from opentelemetry.semconv.trace import SpanAttributes

from constants.apm import OtlpKey, SpanKind


class SpanInference:
    """服务推断"""

    @classmethod
    def infer(cls, span):
        # 兜底类
        return True

    @classmethod
    def category(cls):
        return CategoryEnum.OTHER

    @classmethod
    def icon(cls):
        return TraceIcon.OTHER


class HttpEndpointInference(SpanInference):
    """
    HTTP接口
    """

    predicate_keys = [
        SpanAttributes.HTTP_METHOD,
        SpanAttributes.HTTP_URL,
        SpanAttributes.HTTP_ROUTE,
        SpanAttributes.HTTP_SCHEME,
        SpanAttributes.HTTP_TARGET,
        SpanAttributes.HTTP_FLAVOR,
        SpanAttributes.HTTP_HOST,
        SpanAttributes.HTTP_STATUS_CODE,
    ]

    @classmethod
    def infer(cls, span):
        if span[OtlpKey.KIND] != SpanKind.SPAN_KIND_SERVER:
            return None

        return any(bool(span[OtlpKey.ATTRIBUTES].get(i)) for i in cls.predicate_keys)

    @classmethod
    def category(cls):
        return CategoryEnum.HTTP

    @classmethod
    def icon(cls):
        return TraceIcon.HTTP


class HttpCallerInference(SpanInference):
    """
    HTTP调用
    """

    predicate_keys = [
        SpanAttributes.HTTP_HOST,
        SpanAttributes.HTTP_URL,
        SpanAttributes.NET_PEER_NAME,
        SpanAttributes.PEER_SERVICE,
    ]

    @classmethod
    def infer(cls, span):
        if span[OtlpKey.KIND] != SpanKind.SPAN_KIND_CLIENT:
            return None

        return any(bool(span[OtlpKey.ATTRIBUTES].get(i)) for i in cls.predicate_keys)

    @classmethod
    def category(cls):
        return CategoryEnum.HTTP

    @classmethod
    def icon(cls):
        return TraceIcon.HTTP


class RpcEndpointInference(SpanInference):
    """
    RPC接口
    """

    predicate_keys = [
        SpanAttributes.RPC_SYSTEM,
    ]

    @classmethod
    def infer(cls, span):
        if span[OtlpKey.KIND] != SpanKind.SPAN_KIND_SERVER:
            return None

        return any(bool(span[OtlpKey.ATTRIBUTES].get(i)) for i in cls.predicate_keys)

    @classmethod
    def category(cls):
        return CategoryEnum.RPC

    @classmethod
    def icon(cls):
        return TraceIcon.RPC


class RpcCallerInference(SpanInference):
    """
    RPC调用
    """

    predicate_keys = [
        SpanAttributes.RPC_SYSTEM,
    ]

    @classmethod
    def infer(cls, span):
        if span[OtlpKey.KIND] != SpanKind.SPAN_KIND_CLIENT:
            return None

        return any(bool(span[OtlpKey.ATTRIBUTES].get(i)) for i in cls.predicate_keys)

    @classmethod
    def category(cls):
        return CategoryEnum.RPC

    @classmethod
    def icon(cls):
        return TraceIcon.RPC


class DatabaseInference(SpanInference):
    """
    DB(不区分主被调)
    """

    predicate_keys = [
        SpanAttributes.DB_SYSTEM,
        SpanAttributes.DB_NAME,
        SpanAttributes.DB_STATEMENT,
        "db.type",
        "db.instance",
    ]

    @classmethod
    def infer(cls, span):
        return any(bool(span[OtlpKey.ATTRIBUTES].get(i)) for i in cls.predicate_keys)

    @classmethod
    def category(cls):
        return CategoryEnum.DB

    @classmethod
    def icon(cls):
        return TraceIcon.DB


class MessageSenderInference(SpanInference):
    """
    消息发送者
    """

    predicate_keys = [
        SpanAttributes.MESSAGING_RABBITMQ_ROUTING_KEY,
        SpanAttributes.MESSAGING_KAFKA_MESSAGE_KEY,
    ]

    @classmethod
    def infer(cls, span):
        if span[OtlpKey.KIND] != SpanKind.SPAN_KIND_PRODUCER:
            return None

        return any(bool(span[OtlpKey.ATTRIBUTES].get(i)) for i in cls.predicate_keys)

    @classmethod
    def category(cls):
        return CategoryEnum.MESSAGING

    @classmethod
    def icon(cls):
        return TraceIcon.MESSAGE


class MessageReceiverInference(SpanInference):
    """
    消息接收者
    """

    predicate_keys = [
        SpanAttributes.MESSAGING_RABBITMQ_ROUTING_KEY,
        SpanAttributes.MESSAGING_KAFKA_MESSAGE_KEY,
    ]

    @classmethod
    def infer(cls, span):
        if span[OtlpKey.KIND] != SpanKind.SPAN_KIND_CONSUMER:
            return None

        return any(bool(span[OtlpKey.ATTRIBUTES].get(i)) for i in cls.predicate_keys)

    @classmethod
    def category(cls):
        return CategoryEnum.MESSAGING

    @classmethod
    def icon(cls):
        return TraceIcon.MESSAGE


class ConsumerInference(SpanAttributes):
    predicate_keys = [
        SpanAttributes.MESSAGING_DESTINATION,
        SpanAttributes.MESSAGING_SYSTEM,
        "celery.action",
    ]

    @classmethod
    def infer(cls, span):
        if span[OtlpKey.KIND] != SpanKind.SPAN_KIND_CONSUMER:
            return None

        return any(bool(span[OtlpKey.ATTRIBUTES].get(i)) for i in cls.predicate_keys)

    @classmethod
    def category(cls):
        return CategoryEnum.ASYNC_BACKEND

    @classmethod
    def icon(cls):
        return TraceIcon.ASYNC_BACKEND


class ProducerInference(SpanAttributes):
    predicate_keys = [
        SpanAttributes.MESSAGING_DESTINATION,
        SpanAttributes.MESSAGING_SYSTEM,
        "celery.action",
        "celery.state",
    ]

    @classmethod
    def infer(cls, span):
        if span[OtlpKey.KIND] != SpanKind.SPAN_KIND_PRODUCER:
            return None

        return any(bool(span[OtlpKey.ATTRIBUTES].get(i)) for i in cls.predicate_keys)

    @classmethod
    def category(cls):
        return CategoryEnum.ASYNC_BACKEND

    @classmethod
    def icon(cls):
        return TraceIcon.ASYNC_BACKEND


class InferenceHandler:

    infers = [
        HttpEndpointInference,
        HttpCallerInference,
        RpcEndpointInference,
        RpcCallerInference,
        DatabaseInference,
        MessageSenderInference,
        MessageReceiverInference,
        ConsumerInference,
        ProducerInference,
        SpanInference,
    ]

    @classmethod
    def infer(cls, span):
        return next(i.category() for i in cls.infers if i.infer(span))

    @classmethod
    def list_category(cls):
        categories = {i.category() for i in cls.infers}
        return [{"value": i, "text": CategoryEnum.get_label_by_key(i)} for index, i in enumerate(categories, 1)]

    @classmethod
    def get_icon(cls, infer_category):
        return next((i.icon() for i in cls.infers if i.category() == infer_category), SpanInference.icon())
