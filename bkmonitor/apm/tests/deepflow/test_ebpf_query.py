# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import mock

from apm.core.handlers.query.ebpf_query import DeepFlowQuery
from apm_ebpf.resource import TraceQueryResource


def test_ebpf_query():

    sql = "SELECT signal_source, tap_side  FROM l7_flow_log"
    params = {"trace_id": "f8b5662793fcdc963a628405061995df", "bk_biz_id": 2, "sql": sql, "db": "flow_log"}
    mock.patch("apm_ebpf.resource.TraceQueryResource.request", return_value={}).start()
    res = TraceQueryResource().request(params)

    assert len(res) == 0


def test_ebpf_query_error_param():
    trace_id = "f8b5662793fcdc963a628405061995df"
    bk_biz_id = None
    span_ebpf = DeepFlowQuery.get_ebpf(trace_id, bk_biz_id)

    len(span_ebpf) == 0
