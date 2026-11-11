"""Trace / Span 详情补充 llm_detail 的回归测试。"""

from __future__ import annotations

from unittest import TestCase, mock

from django.test import override_settings

from apm_web.llm.builders.detail import attach_llm_detail, prepare_llm_spans

DETAIL_MODULE = "apm_web.llm.builders.detail"


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
    def test_trace_topology_failure_is_not_retried_by_lazy_helpers(self):
        from apm_web.trace.resources import TraceDetailResource

        source = raw_span("1" * 16, "chat")
        source.update({"kind": 1, "trace_state": "", "links": []})
        with (
            mock.patch(f"{DETAIL_MODULE}.EntitySet", side_effect=ValueError("topology unavailable")) as topology,
            mock.patch(
                "apm_web.trace.resources.api.apm_api.query_trace_detail",
                return_value={"trace_data": [source], "relation_mapping": {}, "options": {}},
            ),
            mock.patch("apm_web.trace.diagram.config.DiagramConfigController.read", return_value=None),
        ):
            serializer = TraceDetailResource.RequestSerializer(
                data={"bk_biz_id": 11, "app_name": "agent-app", "trace_id": source["trace_id"]}
            )
            serializer.is_valid(raise_exception=True)
            result = TraceDetailResource().perform_request(serializer.validated_data)
        topology.assert_called_once()
        self.assertEqual(len(result["trace_tree"]["spans"]), 1)
        self.assertNotIn("lazy", result["trace_tree"]["spans"][0])

    @override_settings(LLM_BIZ_LIST=[11])
    def test_trace_resource_is_lean_and_span_resource_returns_complete_content(self):
        import json

        from django.core.serializers.json import DjangoJSONEncoder

        from apm_web.trace.resources import SpanDetailResource, TraceDetailResource

        source = raw_span("1" * 16, "chat")
        source.update({"kind": 1, "trace_state": "", "links": []})
        text = "大正文🦋" * 100_000
        source["attributes"]["gen_ai.input.messages"] = [{"role": "user", "parts": [{"type": "text", "content": text}]}]
        source["attributes"]["gen_ai.output.messages"] = [
            {"role": "assistant", "parts": [{"type": "text", "content": text}]}
        ]
        with (
            mock.patch(f"{DETAIL_MODULE}.EntitySet", return_value=entity_set("agent-service")) as topology,
            mock.patch(
                "apm_web.trace.resources.api.apm_api.query_trace_detail",
                return_value={"trace_data": [source], "relation_mapping": {}, "options": {}},
            ),
            mock.patch("apm_web.trace.resources.api.apm_api.query_span_detail", return_value=source),
            mock.patch("apm_web.trace.diagram.config.DiagramConfigController.read", return_value=None),
        ):
            serializer = TraceDetailResource.RequestSerializer(
                data={"bk_biz_id": 11, "app_name": "agent-app", "trace_id": source["trace_id"]}
            )
            serializer.is_valid(raise_exception=True)
            trace = TraceDetailResource().perform_request(serializer.validated_data)
            topology.assert_called_once()
            detail = SpanDetailResource().perform_request(
                {"bk_biz_id": 11, "app_name": "agent-app", "span_id": source["span_id"]}
            )
        payload = json.dumps(trace, cls=DjangoJSONEncoder, ensure_ascii=False)
        self.assertLess(len(payload), 20_000)
        self.assertNotIn("gen_ai.input.messages", payload)
        self.assertNotIn(text[:1000], payload)
        self.assertNotIn("lazy", trace["trace_tree"]["spans"][0])
        self.assertEqual(trace["trace_tree"]["spans"][0]["attributes"], [])
        self.assertEqual(
            detail["origin_data"]["attributes"]["gen_ai.input.messages"], source["attributes"]["gen_ai.input.messages"]
        )
        self.assertEqual(
            detail["trace_tree"]["spans"][0]["llm_detail"]["attributes"]["gen_ai.input.messages"],
            source["attributes"]["gen_ai.input.messages"],
        )

    @override_settings(LLM_BIZ_LIST=[11])
    def test_lazy_trace_removes_all_copies_of_content_and_span_detail_stays_complete(self):
        import json

        original = raw_span("1" * 16, "chat")
        original["attributes"]["gen_ai.input.messages"] = [
            {"role": "user", "parts": [{"type": "text", "content": "大输入" * 100_000}]}
        ]
        original["attributes"]["gen_ai.output.messages"] = [
            {"role": "assistant", "parts": [{"type": "text", "content": "大输出" * 100_000}]}
        ]
        tree = trace_tree("1" * 16)
        with mock.patch(f"{DETAIL_MODULE}.EntitySet", return_value=entity_set("agent-service")):
            reduced = prepare_llm_spans(11, "agent-app", [original])
            attach_llm_detail(11, "agent-app", tree, reduced, compact=True)
            complete = trace_tree("1" * 16)
            attach_llm_detail(11, "agent-app", complete, [original])

        self.assertLess(len(json.dumps({"raw": reduced, "tree": tree})), 1000)
        self.assertEqual(tree["spans"][0]["llm_detail"], {"span_type": "LLM"})
        self.assertNotIn("lazy", tree["spans"][0])
        self.assertIn("gen_ai.input.messages", original["attributes"])
        self.assertEqual(
            complete["spans"][0]["llm_detail"]["attributes"]["gen_ai.input.messages"],
            original["attributes"]["gen_ai.input.messages"],
        )
        self.assertNotIn("lazy", complete["spans"][0])

    @override_settings(LLM_BIZ_LIST=[11])
    def test_langfuse_lazy_classification_does_not_parse_large_input(self):
        source = raw_span("1" * 16, "")
        source["attributes"] = {
            "langfuse.observation.type": "generation",
            "langfuse.observation.input": "输入" * 1_000_000,
        }
        topology = entity_set("agent-service")
        topology.get_system = lambda _: {"is_support_llm": True, "product": "langfuse"}
        with mock.patch(f"{DETAIL_MODULE}.EntitySet", return_value=topology):
            result = prepare_llm_spans(11, "agent-app", [source])
        self.assertEqual(result[0]["llm_detail"]["span_type"], "LLM")
        self.assertNotIn("langfuse.observation.input", result[0]["attributes"])

    @override_settings(LLM_BIZ_LIST=[11])
    def test_dynamic_product_trace_uses_same_compact_path(self):
        source = raw_span("1" * 16, "chat")
        source["attributes"]["gen_ai.prompts.0.content"] = "keep me"
        topology = entity_set("agent-service")
        topology.get_system = lambda _: {"is_support_llm": True, "product": "agentlens"}
        with mock.patch(f"{DETAIL_MODULE}.EntitySet", return_value=topology):
            result = prepare_llm_spans(11, "agent-app", [source])
        self.assertEqual(result[0]["llm_detail"], {"span_type": "LLM"})
        self.assertNotIn("gen_ai.prompts.0.content", result[0]["attributes"])

    @override_settings(LLM_BIZ_LIST=[11])
    def test_partial_aidev_and_galileo_spans_use_normal_adapter_and_compact_details(self):
        for product, attributes in [
            ("aidev", {"llm.request.type": "chat", "llm.input": "large input"}),
            ("galileo", {"gen_ai.operation.name": "chat", "gen_ai.input.messages": "large input"}),
        ]:
            with self.subTest(product=product):
                source = raw_span("1" * 16, "")
                source["attributes"] = attributes
                topology = entity_set("agent-service")
                topology.get_system = lambda _, product=product: {"is_support_llm": True, "product": product}
                result = prepare_llm_spans(11, "agent-app", [source], entity_set=topology)
                tree = trace_tree(source["span_id"])
                attach_llm_detail(11, "agent-app", tree, result, compact=True, entity_set=topology)
                self.assertEqual(tree["spans"][0]["llm_detail"], {"span_type": "LLM"})
                self.assertNotIn("lazy", result[0])
                self.assertNotIn("large input", str(result[0]))

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
