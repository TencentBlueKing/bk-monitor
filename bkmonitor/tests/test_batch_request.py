import copy

import pytest

from bkmonitor.commons.tools import batch_request


def fake_api(total, page_key):
    calls = []

    def func(params):
        calls.append(copy.deepcopy(params))
        if page_key == "cmdb":
            start, limit = params["page"]["start"], params["page"]["limit"]
        else:
            start, limit = (params["page"] - 1) * params["page_size"], params["page_size"]
        return {"count": total, "info": list(range(total))[start : start + limit]}

    return func, calls


@pytest.mark.parametrize("app", ["cmdb", "metadata"])
@pytest.mark.parametrize("total,requests", [(0, 1), (1, 1), (10, 1), (11, 2), (20, 2), (21, 3)])
def test_pages_are_requested_once_without_probe(app, total, requests):
    func, calls = fake_api(total, app)

    assert batch_request(func, {}, limit=10, app=app, thread_num=2) == list(range(total))
    assert len(calls) == requests


def test_cmdb_page_keeps_caller_sort():
    func, calls = fake_api(25, "cmdb")

    batch_request(func, {"page": {"sort": "bk_host_id"}}, limit=10, thread_num=2)

    assert sorted((c["page"]["start"], c["page"]["sort"]) for c in calls) == [
        (0, "bk_host_id"),
        (10, "bk_host_id"),
        (20, "bk_host_id"),
    ]


def test_job_offset_params():
    calls = []

    def func(params):
        calls.append(params.copy())
        return {"count": 15, "info": [params["start"]]}

    assert sorted(batch_request(func, {}, limit=10, app="job", thread_num=2)) == [0, 10]
    assert sorted(c["length"] for c in calls) == [10, 10]


def test_count_none_returns_first_page():
    calls = []

    def func(params):
        calls.append(params)
        return {"count": None, "info": ["a"]}

    assert batch_request(func, {}, limit=10, app="nodeman") == ["a"]
    assert calls == [{"page": 1, "pagesize": 10}]
