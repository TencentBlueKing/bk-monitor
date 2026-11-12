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

import pytest

from monitor_web.search.handlers import strategy as strategy_handler_module
from monitor_web.search.handlers.base import SearchResultItem, SearchScope
from monitor_web.search.handlers.strategy import StrategySearchHandler

ALLOWED_BIZ_ID = 1
DENIED_BIZ_ID = 2


def _filter_biz_ids(action, bk_biz_ids):
    return [bk_biz_id for bk_biz_id in bk_biz_ids if bk_biz_id == ALLOWED_BIZ_ID]


@pytest.fixture(autouse=True)
def permission():
    with mock.patch("monitor_web.search.handlers.base.Permission") as perm_cls, mock.patch(
        "monitor_web.search.handlers.base.api.cmdb.get_business", return_value=[]
    ):
        perm_cls.return_value.filter_biz_ids_by_action.side_effect = _filter_biz_ids
        yield perm_cls


class _StrategyValues(list):
    def filter(self, bk_biz_id):
        return _StrategyValues(item for item in self if item["bk_biz_id"] == bk_biz_id)


@pytest.mark.parametrize(
    "scope,expected",
    [
        (SearchScope.GLOBAL, [(ALLOWED_BIZ_ID, "repro-strategy-allowed")]),
        # 搜索接口不校验请求业务，BIZ 范围指定无权业务时也不能返回该业务的数据
        (SearchScope.BIZ, []),
    ],
)
def test_strategy_search_drops_denied_business_results(scope, expected):
    strategies = _StrategyValues(
        [
            {"id": 11, "bk_biz_id": ALLOWED_BIZ_ID, "name": "repro-strategy-allowed"},
            {"id": 22, "bk_biz_id": DENIED_BIZ_ID, "name": "repro-strategy-denied"},
        ]
    )

    with mock.patch.object(strategy_handler_module.StrategyModel.objects, "filter") as model_filter:
        model_filter.return_value.values.return_value = strategies
        handler = StrategySearchHandler(bk_biz_id=DENIED_BIZ_ID, scope=scope, username="tester")
        result = handler.handle(query="repro-strategy", limit=100).to_dict()

    assert [(item["bk_biz_id"], item["title"]) for item in result["results"]] == expected
    assert all(item["is_allowed"] for item in result["results"])


def test_string_business_id_is_compared_as_integer():
    handler = StrategySearchHandler(bk_biz_id=ALLOWED_BIZ_ID, scope=SearchScope.GLOBAL, username="tester")
    items = [
        SearchResultItem(bk_biz_id=str(ALLOWED_BIZ_ID), title="allowed", view="event-center-detail"),
        SearchResultItem(bk_biz_id=str(DENIED_BIZ_ID), title="denied", view="event-center-detail"),
        SearchResultItem(bk_biz_id="invalid", title="invalid", view="event-center-detail"),
    ]

    handler.add_permission_for_results(items, action=None)

    assert [item.title for item in handler.filter_allowed_results(items)] == ["allowed"]


def test_mixed_business_id_types_are_sorted_as_integer():
    class MixedHandler(StrategySearchHandler):
        def search(self, query, limit=10):
            # 汇总项业务 ID 为整数，ES 明细项为字符串
            items = [
                SearchResultItem(bk_biz_id=ALLOWED_BIZ_ID, title="collected", view="event-center", is_collected=True),
                SearchResultItem(bk_biz_id=str(ALLOWED_BIZ_ID), title="detail", view="event-center-detail"),
            ]
            self.add_permission_for_results(items, action=None)
            return items

    handler = MixedHandler(bk_biz_id=ALLOWED_BIZ_ID, scope=SearchScope.GLOBAL, username="tester")
    result = handler.handle(query="repro", limit=100).to_dict()

    assert [item["bk_biz_id"] for item in result["results"]] == [ALLOWED_BIZ_ID, ALLOWED_BIZ_ID]


def test_no_business_does_not_query_all_biz(permission):
    handler = StrategySearchHandler(bk_biz_id=ALLOWED_BIZ_ID, scope=SearchScope.GLOBAL, username="tester")
    items = [SearchResultItem(bk_biz_id=None, title="unknown", view="event-center-detail")]

    handler.add_permission_for_results(items, action=None)

    permission.return_value.filter_biz_ids_by_action.assert_not_called()
    assert handler.filter_allowed_results(items) == []
