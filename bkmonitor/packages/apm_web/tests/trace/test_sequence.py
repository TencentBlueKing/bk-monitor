import pytest

from apm_web.trace.diagram.sequence import trace_to_mermaid_sequence_data

from .utils import read_trace_list


class TestSequence:
    @pytest.mark.parametrize(
        "case_name,expected",
        [
            (
                "simple",
                (10, 3, 2),
            ),
            # root span's kind changed to "client<3>"
            (
                "no_start",
                (10, 2, 1),
            ),
            # every span owns a service
            (
                "multiple_service",
                #  5 services + 1 start = 6
                (10, 6, 6),
            ),
        ],
    )
    def test_sequence(self, case_name, expected, group_and_parallel_virtual_return_trace_tree_config):
        """Test sequence diagram"""
        sequence_data = trace_to_mermaid_sequence_data(read_trace_list(case_name, category="sequence"))
        assert len(sequence_data["connections"]) == expected[0]
        assert len({x["name"] for x in sequence_data["participants"]}) == expected[1]
        assert len({x["component_name"] for x in sequence_data["participants"]}) == expected[2]

    def test_parallel(self):
        """Test parallel sequence diagram"""
        # 4 siblings, 1 root
        # first 2 siblings marked as parallel for execution overlapping
        # last 2 siblings marked as parallel for close start time
        sequence_data = trace_to_mermaid_sequence_data(read_trace_list("parallel"))

        # 5 spans, 5 returns
        assert len(sequence_data["connections"]) == 10
        assert sequence_data["connections"][0]["parallel_id"] is None

        # 10001,10003,10010(r),10015(r),10016,10018(r),10020,10030(r)
        assert sequence_data["connections"][1]["parallel_id"] is not None
        assert sequence_data["connections"][2]["parallel_id"] is not None
        assert sequence_data["connections"][1]["parallel_id"] == sequence_data["connections"][2]["parallel_id"]

        assert sequence_data["connections"][3]["parallel_id"] is None

        assert sequence_data["connections"][5]["parallel_id"] is not None
        assert sequence_data["connections"][7]["parallel_id"] is not None
        assert sequence_data["connections"][5]["parallel_id"] == sequence_data["connections"][7]["parallel_id"]

    def test_hyphen(self, group_and_parallel_virtual_return_trace_tree_config):
        """Test hyphen in sequence diagram"""
        sequence_data = trace_to_mermaid_sequence_data(read_trace_list("multiple_hyphens", category="sequence"))
        # pcbd29aee -) p8375d4e7: rootSpan ---> SELECT
        # pcbd29aee ->>+ p8375d4e7: rootSpan ---> SET
        # p8375d4e7 -->>- pcbd29aee: end
        # pcbd29aee ->>+ p8375d4e7: SELECT
        # p8375d4e7 -->>- pcbd29aee: end
        # pcbd29aee ->> p8375d4e7: SELECT

        # 2 connections combined into 1, no return, 1
        # 2 connections with return, 4
        # 1 internal connection, no return, 1
        assert len(sequence_data["connections"]) == 6

        assert sequence_data["connections"][0]["hyphen"] == "-)"
        assert sequence_data["connections"][1]["hyphen"] == "->>+"
        assert sequence_data["connections"][2]["hyphen"] == "-->>-"
        assert sequence_data["connections"][3]["hyphen"] == "->>+"
        assert sequence_data["connections"][4]["hyphen"] == "-->>-"
        assert sequence_data["connections"][5]["hyphen"] == "->>"
