"""Trace / Span 详情补充 llm_detail 的回归测试。"""

from __future__ import annotations

from unittest import TestCase, mock

from django.test import override_settings

from apm_web.llm.detail import attach_llm_detail

DETAIL_MODULE = "apm_web.llm.detail"


def raw_span(span_id: str, operation_name: str, *, service_name: str = "agent-service") -> dict:
    return {
        "trace_id": "a" * 32,
        "span_id": span_id,
        "parent_span_id": "",
        "span_name": f"{operation_name} demo",
        "start_time": 1_700_000_000_000_000,
        "end_time": 1_700_000_001_000_000,
        "elapsed_time": 1_000_000,
        "status": {"code": 1, "message": ""},
        "resource": {"service.name": service_name},
        "attributes": {"gen_ai.operation.name": operation_name},
        "events": [],
    }


def trace_tree(*span_ids: str) -> dict:
    return {"spans": [{"spanID": span_id} for span_id in span_ids]}


def entity_set(*llm_service_names: str) -> mock.Mock:
    return mock.Mock(
        service_names=list(llm_service_names),
        get_system=lambda service_name: {"is_support_llm": True, "product": "default"},
    )


class AttachLLMDetailTests(TestCase):
    @override_settings(LLM_BIZ_LIST=[11])
    def test_attaches_span_type_to_matching_waterfall_spans(self):
        tree = trace_tree("1" * 16, "2" * 16)
        spans = [raw_span("1" * 16, "invoke_agent"), raw_span("2" * 16, "execute_tool")]

        with mock.patch(f"{DETAIL_MODULE}.EntitySet", return_value=entity_set("agent-service")):
            attach_llm_detail(11, "agent-app", tree, spans)

        self.assertEqual([span["llm_detail"]["span_type"] for span in tree["spans"]], ["AGENT", "TOOL"])

    @override_settings(LLM_BIZ_LIST=[11])
    def test_skips_unclassified_and_non_llm_spans(self):
        tree = trace_tree("1" * 16, "2" * 16)
        spans = [
            # 暂不支持的语义层级
            raw_span("1" * 16, "retrieval"),
            # 非 LLM 服务
            raw_span("2" * 16, "chat", service_name="other-service"),
        ]

        with mock.patch(f"{DETAIL_MODULE}.EntitySet", return_value=entity_set("agent-service")):
            attach_llm_detail(11, "agent-app", tree, spans)

        self.assertNotIn("llm_detail", tree["spans"][0])
        self.assertNotIn("llm_detail", tree["spans"][1])

    @override_settings(LLM_BIZ_LIST=[22])
    def test_grayscale_gate_skips_topology_query(self):
        tree = trace_tree("1" * 16)

        with (
            mock.patch(f"{DETAIL_MODULE}.EntitySet") as entity_set_cls,
            mock.patch(f"{DETAIL_MODULE}.logger") as logger,
        ):
            attach_llm_detail(11, "agent-app", tree, [raw_span("1" * 16, "invoke_agent")])

        entity_set_cls.assert_not_called()
        logger.info.assert_not_called()
        self.assertNotIn("llm_detail", tree["spans"][0])

    @override_settings(LLM_BIZ_LIST=[11])
    def test_logs_biz_app_and_username(self):
        tree = trace_tree("1" * 16)

        with (
            mock.patch(f"{DETAIL_MODULE}.EntitySet", return_value=entity_set("agent-service")),
            mock.patch(f"{DETAIL_MODULE}.get_request_username", return_value="alice"),
            mock.patch(f"{DETAIL_MODULE}.logger") as logger,
        ):
            attach_llm_detail(11, "agent-app", tree, [raw_span("1" * 16, "invoke_agent")])

        logger.info.assert_called_once_with(
            "[LLM] attach_detail bk_biz_id=%s app_name=%s username=%s",
            11,
            "agent-app",
            "alice",
        )

    @override_settings(LLM_BIZ_LIST=[11])
    def test_topology_failure_does_not_break_detail(self):
        tree = trace_tree("1" * 16)

        with mock.patch(f"{DETAIL_MODULE}.EntitySet", side_effect=ValueError("topo unavailable")):
            attach_llm_detail(11, "agent-app", tree, [raw_span("1" * 16, "invoke_agent")])

        self.assertNotIn("llm_detail", tree["spans"][0])
