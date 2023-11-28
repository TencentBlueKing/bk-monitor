from apm_web.trace.diagram.diff import DiffMark
from apm_web.trace.diagram.statistics import trace_diff_to_statistics

from .utils import read_trace_list


class TestStatistics:
    """Test Statistics"""

    def test_diff(self):
        """Test statistics diff"""
        trace_list = read_trace_list("simple")
        trace_list2 = read_trace_list("diff_simple")
        statistics_data = trace_diff_to_statistics(
            trace_list, trace_list2, ["resource.sdk.name", "resource.service.name"], {}
        )

        assert statistics_data[0]["mark"] == DiffMark.CHANGED.value
