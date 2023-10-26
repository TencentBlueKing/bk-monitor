import pytest
from apm_web.trace.diagram.sequence import trace_to_mermaid_sequence


class TestTraceSequenceDiagram:
    @pytest.mark.parametrize(
        "trace_data, expected_result",
        [
            ([], "sequenceDiagram\n"),
            (
                [{"span_name": "server_span", "parent_span_id": None, "span_id": "1", "kind": 2}],
                "sequenceDiagram\nserver_span\n",
            ),
            (
                [
                    {"span_name": "client_span", "parent_span_id": "1", "span_id": "2", "kind": 3},
                    {"span_name": "server_span", "parent_span_id": None, "span_id": "1", "kind": 2},
                ],
                "sequenceDiagram\nserver_span ->> client_span: client_span\n",
            ),
            (
                [
                    {"span_name": "client_span_1", "parent_span_id": "1", "span_id": "2", "kind": 3},
                    {"span_name": "client_span_2", "parent_span_id": "1", "span_id": "3", "kind": 3},
                    {"span_name": "server_span", "parent_span_id": None, "span_id": "1", "kind": 2},
                ],
                "sequenceDiagram\nserver_span ->> client_span_1: client_span_1"
                "\nserver_span ->> client_span_2: client_span_2\n",
            ),
        ],
    )
    def test_trace_to_mermaid_sequence(self, trace_data, expected_result):
        assert trace_to_mermaid_sequence(trace_data) == expected_result
