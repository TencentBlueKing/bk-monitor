"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor)
available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from apm.core.handlers.query.trace_query import TraceQuery


def test_query_by_trace_ids_enables_es_batch(mocker):
    query = mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", return_value=[])

    result = TraceQuery.query_by_trace_ids(
        result_table_ids=["2_bkmonitor_trace_1.__default__", "2_bkmonitor_trace_2.__default__"],
        trace_ids=["trace-id"],
        retention=7,
        start_time=100,
        end_time=200,
    )

    assert result == []
    assert query.call_args.kwargs["query_body"]["is_es_batch"] is True
