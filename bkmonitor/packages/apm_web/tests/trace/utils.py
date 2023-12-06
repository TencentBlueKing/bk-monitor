import json
from dataclasses import dataclass, field
from typing import List

# use cache to avoid read file every time
# make unittest faster
_CACHE = {}


def read_trace_list(name: str = "simple", category: str = "") -> list:
    """read trace case by name"""
    if (name, category) in _CACHE:
        return _CACHE[(name, category)]

    cases_prefix = "packages/apm_web/tests/trace/cases"
    if category:
        cases_prefix += f"/{category}"

    with open(f"{cases_prefix}/{name}.json", "r") as f:
        trace_list = json.loads(f.read())

    _CACHE[(name, category)] = trace_list
    return trace_list


def make_a_very_deep_trace(depth: int = 1000) -> list:
    """make a very deep trace"""
    trace_list = []

    for i in range(depth, 0, -1):
        simple_span = {
            "elapsed_time": 100,
            "parent_span_id": f"span{i-1}",
            "trace_id": "fake_trace_id",
            "span_id": f"span{i}",
            "span_name": f"Span<{i}>",
            "kind": 1,
            "attributes": {},
            "resource": {"service.name": "foo"},
            "start_time": 123456,
            "end_time": 123457,
            "status": {"code": 1},
        }
        trace_list.append(simple_span)

    trace_list.append(
        {
            "elapsed_time": 100,
            "parent_span_id": "",
            "trace_id": "fake_trace_id",
            "span_id": "span0",
            "kind": 1,
            "span_name": "rootSpan",
            "attributes": {},
            "resource": {"service.name": "foo"},
            "start_time": 123456,
            "end_time": 123457,
            "status": {"code": 1},
        }
    )

    return trace_list


def make_a_very_wide_trace(width: int = 1000, reverse: bool = False, parallel: bool = False) -> list:
    """make a very wide trace"""
    trace_list = [
        {
            "elapsed_time": 100,
            "parent_span_id": "",
            "trace_id": "fake_trace_id",
            "span_id": "span0",
            "kind": 1,
            "span_name": "rootSpan",
            "attributes": {},
            "resource": {"service.name": "foo"},
            "start_time": 123456,
            "end_time": 123457,
            "status": {"code": 1},
        }
    ]

    range_params = [1, width + 1, 1]
    if reverse:
        range_params = [width, 0, -1]

    width_extra = 0
    if parallel:
        width_extra = 1

    for i in range(*range_params):
        simple_span = {
            "elapsed_time": 100,
            "parent_span_id": "span0",
            "trace_id": "fake_trace_id",
            "span_id": f"span{i}",
            "kind": 1,
            "span_name": f"Span<{i}>",
            "attributes": {},
            "resource": {"service.name": "foo"},
            # no parallel
            "start_time": 123456 + (i - 1) * 2,
            "end_time": 123456 + i * 2 + width_extra,
            "status": {"code": 1},
        }
        trace_list.append(simple_span)

    return trace_list


def make_a_very_wide_roots_trace(width: int = 1000) -> list:
    """make a very wide trace"""
    trace_list = []

    for i in range(width):
        simple_span = {
            "elapsed_time": 100,
            "parent_span_id": "",
            "trace_id": "fake_trace_id",
            "span_id": f"span{i}",
            "kind": 1,
            "span_name": f"Span<{i}>",
            "attributes": {},
            "resource": {"service.name": "foo"},
            "start_time": 123456 + i,
            "end_time": 123457,
            "status": {"code": 1},
        }
        trace_list.append(simple_span)

    return trace_list


@dataclass
class FakeSpanNode:
    """fake span node"""

    parent_span_id: str
    span_id: str
    span_name: str = ""
    elapsed_time: int = 100
    service_name: str = "fake_service_name"
    start_time: int = 100000
    children: list = None
    trace_id: str = "fake_trace_id"
    kind: int = 1
    attributes: dict = field(default_factory=dict)
    status: dict = field(default_factory=lambda: {"code": 1})
    resource: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.span_name:
            self.span_name = f"Span<{self.span_id}>"

    def to_dict(self) -> dict:
        self.resource.update({"service.name": self.service_name})
        return {
            "elapsed_time": self.elapsed_time,
            "parent_span_id": self.parent_span_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "kind": self.kind,
            "span_name": self.span_name,
            "attributes": self.attributes,
            "resource": self.resource,
            "start_time": self.start_time,
            "end_time": self.start_time + self.elapsed_time,
            "status": self.status,
        }


def dynamic_make_trace_list(relations: List[tuple]) -> list:
    """make a trace list by relations"""
    trace_list = []

    for relation in relations:
        span_node = FakeSpanNode(*relation)
        simple_span = span_node.to_dict()
        trace_list.append(simple_span)

    return trace_list
