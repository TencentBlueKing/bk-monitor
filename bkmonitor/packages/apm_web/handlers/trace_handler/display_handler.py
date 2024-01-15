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
from opentelemetry.semconv.resource import ResourceAttributes

from apm_web.constants import EbpfSignalSourceType, SpanSourceCategory
from constants.apm import OtlpKey, TraceWaterFallDisplayKey


class CategoryEbpfFilter:
    NAME = TraceWaterFallDisplayKey.SOURCE_CATEGORY_EBPF

    EBPF_SDK_NAMES = ["deepflow"]

    @classmethod
    def is_match(cls, span):
        return span[OtlpKey.RESOURCE].get(ResourceAttributes.TELEMETRY_SDK_NAME) in cls.EBPF_SDK_NAMES


class CategoryOpentelemetryFilter:
    NAME = TraceWaterFallDisplayKey.SOURCE_CATEGORY_OPENTELEMETRY

    @classmethod
    def is_match(cls, span):
        # 目前来源只有Ebpf/OT
        return not CategoryEbpfFilter.is_match(span)


class DisplayProcessorContainer:
    processors = {
        CategoryEbpfFilter.NAME: CategoryEbpfFilter,
        CategoryOpentelemetryFilter.NAME: CategoryOpentelemetryFilter,
    }

    @classmethod
    def get(cls, display_key):
        return cls.processors[display_key]


class DisplayHandler:
    @classmethod
    def is_match(cls, span, displays):
        return any(DisplayProcessorContainer.get(i).is_match(span) for i in displays)

    @classmethod
    def get_source_category(cls, span):
        # EBPF or OT
        if CategoryEbpfFilter.is_match(span):
            source = span[OtlpKey.RESOURCE].get("df.capture_info.signal_source")
            if source in [EbpfSignalSourceType.SIGNAL_SOURCE_PACKET, EbpfSignalSourceType.SIGNAL_SOURCE_XFLOW]:
                return SpanSourceCategory.EBPF_NETWORK
            elif source == EbpfSignalSourceType.SIGNAL_SOURCE_EBPF:
                return SpanSourceCategory.EBPF_SYSTEM

        return SpanSourceCategory.OPENTELEMETRY
