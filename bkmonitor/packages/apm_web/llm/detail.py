"""Trace / Span 详情的 LLM 观测字段补充。"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from opentelemetry.semconv.resource import ResourceAttributes

from constants.apm import OtlpKey

from apm_web.llm.adapter import adapt_spans
from apm_web.llm.adapter.fields import resolve_product
from apm_web.strategy.dispatch.entity import EntitySet
from bkmonitor.utils.request import get_request_username

logger = logging.getLogger(__name__)


def attach_llm_detail(
    bk_biz_id: int,
    app_name: str,
    trace_tree: dict[str, Any],
    raw_spans: list[dict[str, Any]],
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
    try:
        entity_set: EntitySet = EntitySet(bk_biz_id=bk_biz_id, app_name=app_name)
    except Exception:
        # LLM 观测是详情接口的附加信息，拓扑取不到时跳过即可，不能让整个详情不可用
        logger.exception("[LLM] 拓扑查询失败，跳过 llm_detail: %s/%s", bk_biz_id, app_name)
        return

    llm_raw_spans: list[dict[str, Any]] = [
        span
        for span in raw_spans
        if resolve_product(entity_set, span.get(OtlpKey.RESOURCE, {}).get(ResourceAttributes.SERVICE_NAME, ""))
    ]
    details: dict[str, dict[str, Any]] = {
        span[OtlpKey.SPAN_ID]: span for span in adapt_spans(llm_raw_spans, entity_set) if "span_type" in span
    }
    for span in trace_tree.get("spans") or []:
        if detail := details.get(span.get("spanID")):
            span["llm_detail"] = detail
