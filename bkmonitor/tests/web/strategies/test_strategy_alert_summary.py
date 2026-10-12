"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest import mock

from elasticsearch_dsl import Search
from elasticsearch_dsl.response import Response

from bkmonitor.documents import AlertDocument
from monitor_web.strategies.resources import GetStrategyAlertSummaryV2Resource, GetStrategyListV2Resource


def mock_alert_search(*pages):
    """按顺序返回 composite 聚合分页，并记录每次请求体"""
    requests = []

    class FakeSearch(Search):
        def execute(self, ignore_cache=False):
            requests.append(self.to_dict())
            return Response(self, {"aggregations": {"strategy_id": pages[len(requests) - 1]}})

    return mock.patch.object(AlertDocument, "search", return_value=FakeSearch()), requests


def bucket(strategy_id, doc_count, shielded):
    return {"key": {"strategy_id": str(strategy_id)}, "doc_count": doc_count, "shielded": {"doc_count": shielded}}


def get_filters(request_body):
    return request_body["query"]["bool"]["filter"]


def test_alert_summary_pushes_down_candidates_in_one_request():
    patcher, requests = mock_alert_search({"buckets": [bucket(1, 3, 1), bucket(2, 2, 2)]})
    with patcher:
        summary = GetStrategyListV2Resource.get_alert_summary(2, [1, 2, 3])

    # 未屏蔽数 = 未恢复总数 - 已屏蔽数，is_shielded 为 false 或缺失的告警都计入未屏蔽
    assert summary == {
        1: {"alert_count": 2, "shield_alert_count": 1},
        2: {"alert_count": 0, "shield_alert_count": 2},
    }
    assert len(requests) == 1
    filters = get_filters(requests[0])
    assert {"term": {"event.bk_biz_id": 2}} in filters
    assert {"term": {"status": "ABNORMAL"}} in filters
    assert [sorted(f["terms"]["strategy_id"]) for f in filters if "terms" in f] == [[1, 2, 3]]
    assert requests[0]["aggs"]["strategy_id"]["aggs"]["shielded"] == {"filter": {"term": {"is_shielded": True}}}


def test_alert_summary_aggregates_by_biz_and_paginates_for_many_candidates():
    patcher, requests = mock_alert_search(
        {"buckets": [bucket(1, 1, 0), bucket(9, 5, 0)], "after_key": {"strategy_id": "9"}},
        {"buckets": [bucket(2, 4, 1)]},
    )
    with (
        patcher,
        mock.patch.object(GetStrategyListV2Resource, "ALERT_SUMMARY_TERMS_LIMIT", 2),
        mock.patch.object(GetStrategyListV2Resource, "ALERT_SUMMARY_PAGE_SIZE", 2),
    ):
        summary = GetStrategyListV2Resource.get_alert_summary(2, [1, 2, 3])

    # 超过阈值时不下推 terms，按业务聚合后丢弃非候选策略 9
    assert summary == {
        1: {"alert_count": 1, "shield_alert_count": 0},
        2: {"alert_count": 3, "shield_alert_count": 1},
    }
    assert len(requests) == 2
    assert all("terms" not in f for f in get_filters(requests[0]))
    assert "after" not in requests[0]["aggs"]["strategy_id"]["composite"]
    assert requests[1]["aggs"]["strategy_id"]["composite"]["after"] == {"strategy_id": "9"}


def test_alert_summary_skips_es_without_candidates():
    patcher, requests = mock_alert_search()
    with patcher:
        assert GetStrategyListV2Resource.get_alert_summary(2, []) == {}
    assert requests == []


def test_alert_statuses_reuse_alert_summary():
    alert_summary = {
        1: {"alert_count": 2, "shield_alert_count": 0},
        2: {"alert_count": 0, "shield_alert_count": 1},
    }
    with (
        mock.patch.object(AlertDocument, "search") as search,
        mock.patch("monitor_web.strategies.resources.v2.ShieldDetectManager") as shield_manager,
    ):
        shield_manager.return_value.shield_list = []
        assert GetStrategyListV2Resource.filter_by_status("ALERT", [1, 2, 3], 2, alert_summary) == [1]
        assert GetStrategyListV2Resource.filter_by_status("SHIELDED", [1, 2, 3], 2, alert_summary) == [2]
    search.assert_not_called()


def test_status_filter_shares_one_alert_summary():
    alert_summary = {
        1: {"alert_count": 2, "shield_alert_count": 0},
        2: {"alert_count": 0, "shield_alert_count": 1},
    }
    summary_calls = []

    def get_alert_summary(bk_biz_id, strategy_ids):
        summary_calls.append((bk_biz_id, set(strategy_ids)))
        return alert_summary

    candidates = {1, 2, 3}
    context = {}
    with (
        mock.patch.object(GetStrategyListV2Resource, "get_alert_summary", side_effect=get_alert_summary),
        mock.patch("monitor_web.strategies.resources.v2.ShieldDetectManager") as shield_manager,
    ):
        shield_manager.return_value.shield_list = []
        GetStrategyListV2Resource.filter_strategy_ids_by_status(
            {"strategy_status": ["ALERT", "SHIELDED"]}, candidates, 2, context
        )

    # 两个状态只按过滤前的候选策略统计一次
    assert summary_calls == [(2, {1, 2, 3})]
    assert candidates == {1, 2}
    assert context == {"alert_summary": alert_summary}


def test_summary_resource_reuses_status_filter_summary():
    alert_summary = {1: {"alert_count": 1, "shield_alert_count": 0}, 5: {"alert_count": 3, "shield_alert_count": 0}}

    def filter_by_conditions(conditions, strategies, bk_biz_id, context):
        context["alert_summary"] = alert_summary
        return strategies

    with (
        mock.patch("monitor_web.strategies.resources.v2.StrategyModel") as strategy_model,
        mock.patch.object(GetStrategyListV2Resource, "filter_by_conditions", side_effect=filter_by_conditions),
        mock.patch.object(GetStrategyListV2Resource, "get_alert_summary") as get_summary,
        mock.patch.object(GetStrategyListV2Resource, "get_strategy_status_list", return_value=[]) as get_status_list,
    ):
        strategy_model.objects.filter.return_value.values_list.return_value.distinct.return_value = [1]
        result = GetStrategyAlertSummaryV2Resource().request(
            bk_biz_id=2, conditions=[{"key": "strategy_status", "value": ["ALERT"]}], strategy_ids=[1]
        )

    get_summary.assert_not_called()
    get_status_list.assert_called_once_with([1], 2, alert_summary)
    assert result["strategy_alert_counts"] == {1: {"alert_count": 1, "shield_alert_count": 0}}


def test_status_list_leaves_alert_statuses_unknown_without_summary():
    with mock.patch.object(GetStrategyListV2Resource, "filter_by_status", return_value=[1]) as filter_by_status:
        status_list = GetStrategyListV2Resource().get_strategy_status_list([1], 2)

    assert {status["id"]: status["count"] for status in status_list} == {
        "ALERT": None,
        "INVALID": 1,
        "OFF": 1,
        "ON": 1,
        "SHIELDED": None,
    }
    assert {call.args[0] for call in filter_by_status.call_args_list} == {"INVALID", "OFF", "ON"}


def test_summary_resource_only_returns_requested_candidates():
    alert_summary = {1: {"alert_count": 1, "shield_alert_count": 2}, 3: {"alert_count": 5, "shield_alert_count": 0}}
    with (
        mock.patch("monitor_web.strategies.resources.v2.StrategyModel") as strategy_model,
        mock.patch.object(GetStrategyListV2Resource, "get_alert_summary", return_value=alert_summary) as get_summary,
        mock.patch.object(GetStrategyListV2Resource, "get_strategy_status_list", return_value=[]),
    ):
        strategy_model.objects.filter.return_value.values_list.return_value.distinct.return_value = [1, 2, 3]
        result = GetStrategyAlertSummaryV2Resource().request(bk_biz_id=2, strategy_ids=[1, 2, 4])

    get_summary.assert_called_once_with(2, [1, 2, 3])
    assert result["strategy_alert_counts"] == {
        1: {"alert_count": 1, "shield_alert_count": 2},
        2: {"alert_count": 0, "shield_alert_count": 0},
    }
