"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from opentelemetry.semconv.resource import ResourceAttributes

from constants.apm import OtlpKey

from apm_web.llm.adapter import adapt_spans
from apm_web.llm.adapter.fields import flow_attribute_fields, resolve_product
from apm_web.strategy.dispatch.entity import EntitySet
from bkmonitor.utils.request import get_request_username

logger = logging.getLogger(__name__)


def get_llm_entity_set(bk_biz_id: int, app_name: str) -> EntitySet | None:
    if not (0 in settings.LLM_BIZ_LIST or bk_biz_id in settings.LLM_BIZ_LIST):
        return None
    try:
        return EntitySet(bk_biz_id=bk_biz_id, app_name=app_name)
    except Exception:
        logger.exception("[LLM] 拓扑查询失败，跳过 LLM 详情: %s/%s", bk_biz_id, app_name)
        return None


def prepare_llm_spans(
    bk_biz_id: int,
    app_name: str,
    raw_spans: list[dict[str, Any]],
    entity_set: EntitySet | None = None,
) -> list[dict[str, Any]]:
    """用必要字段经过正常 Adapter 识别类型，所有产品统一延后加载详情。"""
    entity_set = entity_set or get_llm_entity_set(bk_biz_id, app_name)
    if not raw_spans or entity_set is None:
        return raw_spans
    fields: set[str] = flow_attribute_fields()
    result: list[dict[str, Any]] = []
    for source in raw_spans:
        service: str = (source.get(OtlpKey.RESOURCE) or {}).get(ResourceAttributes.SERVICE_NAME, "")
        if not resolve_product(entity_set, service):
            result.append(source)
            continue
        projected = {
            **source,
            OtlpKey.ATTRIBUTES: {
                key: value for key, value in (source.get(OtlpKey.ATTRIBUTES) or {}).items() if key in fields
            },
            OtlpKey.EVENTS: [],
        }
        converted = adapt_spans([projected], entity_set)
        if converted and (span_type := converted[0].get("span_type")):
            projected["llm_detail"] = {"span_type": span_type}
            result.append(projected)
        else:
            result.append(source)
    return result


def attach_llm_detail(
    bk_biz_id: int,
    app_name: str,
    trace_tree: dict[str, Any],
    raw_spans: list[dict[str, Any]],
    compact: bool = False,
    entity_set: EntitySet | None = None,
) -> None:
    """给瀑布列表的 Span 挂上标准 LLM Span。

    未开灰度、非 LLM 服务、或识别不出语义层级的 Span 都不带 `llm_detail` 字段。
    """
    if not raw_spans or not (0 in settings.LLM_BIZ_LIST or bk_biz_id in settings.LLM_BIZ_LIST):
        return

    logger.info(
        "[LLM] attach_detail bk_biz_id=%s app_name=%s username=%s",
        bk_biz_id,
        app_name,
        get_request_username() or "",
    )
    entity_set = entity_set or get_llm_entity_set(bk_biz_id, app_name)
    if entity_set is None:
        return

    if compact:
        details = {span[OtlpKey.SPAN_ID]: span["llm_detail"] for span in raw_spans if span.get("llm_detail")}
    else:
        llm_raw_spans = [
            span
            for span in raw_spans
            if resolve_product(entity_set, (span.get(OtlpKey.RESOURCE) or {}).get(ResourceAttributes.SERVICE_NAME, ""))
        ]
        details = {
            span[OtlpKey.SPAN_ID]: span for span in adapt_spans(llm_raw_spans, entity_set) if "span_type" in span
        }
    for span in trace_tree.get("spans") or []:
        if detail := details.get(span.get("spanID")):
            span["llm_detail"] = detail
