"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from rum_web.handlers.level.span import SpanLevelHandler
from rum_web.handlers.query.sorting import VirtualSortDataSource
from rum_web.handlers.query.span import SpanQuery
from rum_web.query.serializers import RumRecordsRequestSerializer


@pytest.mark.parametrize("same_version", [False, True])
def test_descending_browser_merge_uses_remaining_members_and_stable_tiebreak(mocker, same_version):
    """每个来源内部已排序，跨来源归并仍须比较浏览器版本和时间兜底。"""
    handler = SpanLevelHandler(
        [
            TraceDatasourceTarget.build(bk_biz_id=2, app_name="test", table_id=table)
            for table in ("bk_rum.a.span", "bk_rum.b.span")
        ]
    )
    rows = [
        {"span_id": "a", "end_time": 10, "resource.user_agent.name": "Chrome", "resource.user_agent.version": "131"},
        {
            "span_id": "b",
            "end_time": 20,
            "resource.user_agent.name": "Chrome",
            "resource.user_agent.version": "131" if same_version else "132",
        },
    ]
    mocker.patch("bkmonitor.data_source.data_source.bk_biz_id_to_bk_tenant_id", return_value="system")
    mocker.patch.object(VirtualSortDataSource, "query_log", side_effect=[([rows[0]], 1), ([rows[1]], 1)])
    result = handler.list_records(1, 2, 0, 2, sort=["-virtual.browser"])
    assert [row["span_id"] for row in result] == ["b", "a"]


@pytest.mark.parametrize(
    "field,row",
    [
        ("virtual.browser", {"resource.user_agent.name": "Chrome", "resource.user_agent.version": "131 "}),
        ("virtual.span_kind", {"attributes.span_type": " action "}),
    ],
)
def test_storage_request_preserves_canonical_virtual_value_whitespace(field, row):
    query = SpanQuery([])
    value = query.virtual_fields[field].format(row)
    serializer = RumRecordsRequestSerializer(
        data={
            "bk_biz_id": 2,
            "app_name": "test",
            "mode": "span",
            "start_time": 1,
            "end_time": 2,
            "filters": [{"key": field, "operator": "equal", "value": [value]}],
        }
    )
    serializer.is_valid(raise_exception=True)
    assert serializer.validated_data["filters"][0]["value"] == [value]
