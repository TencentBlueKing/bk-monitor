from types import SimpleNamespace

import pytest
from elasticsearch_dsl import Search

from fta_web.alert import resources
from fta_web.alert.resources import AlertEventCountResource


class CaptureSearch(Search):
    body = None

    def execute(self, ignore_cache=False):
        CaptureSearch.body = self.to_dict()
        buckets = {name: SimpleNamespace(doc_count=3) for name in CaptureSearch.body["aggs"]}
        return SimpleNamespace(aggs=SimpleNamespace(**buckets))


@pytest.fixture
def search_kwargs(monkeypatch):
    captured = {}

    def fake_search(**kwargs):
        captured.update(kwargs)
        return CaptureSearch(index="bkfta_event_*_read")

    monkeypatch.setattr(resources.EventDocument, "search", fake_search)
    monkeypatch.setattr(resources.time, "time", lambda: 3000)
    return captured


def test_event_count_query_has_top_level_time_range(search_kwargs):
    alerts = [
        SimpleNamespace(id="1", dedupe_md5="a", begin_time=1000, latest_time=1500),
        SimpleNamespace(id="2", dedupe_md5="b", begin_time=2000, latest_time=None),
    ]

    result = AlertEventCountResource.cal_simple_event_count(alerts)

    assert search_kwargs == {"all_indices": True}
    filters = CaptureSearch.body["query"]["bool"]["filter"]
    assert {"terms": {"dedupe_md5": ["a", "b"]}} in filters
    assert {"range": {"time": {"gte": 1000, "lte": 3000}}} in filters
    for alert in alerts:
        bucket_range = CaptureSearch.body["aggs"][alert.id]["filter"]["bool"]["must"][0]["range"]["time"]
        assert bucket_range["gte"] >= 1000 and bucket_range["lte"] <= 3000
    assert result == {"1": 3, "2": 3}


def test_event_count_missing_begin_time_has_no_lower_bound(search_kwargs):
    alerts = [
        SimpleNamespace(id="1", dedupe_md5="a", begin_time=None, latest_time=1500),
        SimpleNamespace(id="2", dedupe_md5="b", begin_time=2000, latest_time=2500),
    ]

    AlertEventCountResource.cal_simple_event_count(alerts)

    assert {"range": {"time": {"gte": 0, "lte": 2500}}} in CaptureSearch.body["query"]["bool"]["filter"]
