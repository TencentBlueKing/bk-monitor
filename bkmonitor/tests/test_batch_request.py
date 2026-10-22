import pytest

from bkmonitor.commons.tools import batch_request


def fake_api(total, page_key):
    calls = []

    def func(params):
        calls.append(params)
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
