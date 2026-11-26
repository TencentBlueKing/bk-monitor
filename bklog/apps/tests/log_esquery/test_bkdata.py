# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import copy
import json
from unittest.mock import patch

from django.test import TestCase

from apps.log_search.models import Scenario
from apps.log_esquery.esquery.client.QueryClient import QueryClient


INDICES = ["1_Foo"]

INDICES_MAPPING = {"1_foo_2020010100": {}, "1_foo_bar_2020010100": {}}


class TestBkdata(TestCase):
    def test_filter_indices(self):
        client = QueryClient(scenario_id=Scenario.BKDATA).get_instance()
        result = client.filter_mapping(INDICES, INDICES_MAPPING)
        self.assertIn("1_foo_2020010100", result)
        self.assertNotIn("1_foo_bar_2020010100", result)
        return True

    def test_query_keeps_dsl_without_probing_cluster_version(self):
        body = {
            "aggs": {
                "hist": {"date_histogram": {"field": "ts", "fixed_interval": "1d"}},
                "group": {"terms": {"field": "host", "order": {"_key": "asc"}}},
            }
        }
        original = copy.deepcopy(body)
        with (
            patch(
                "apps.log_esquery.esquery.client.QueryClientBkData.BkDataQueryApi.query", return_value={"list": {}}
            ) as query,
            patch("apps.log_esquery.esquery.client.QueryClientBkData.BkDataMetaApi.result_tables.storages") as storages,
            patch("apps.log_esquery.esquery.client.QueryClientBkData.BkDataStorekitApi.storekit_es_route") as route,
        ):
            QueryClient(scenario_id=Scenario.BKDATA).get_instance().query("2_first_*,2_second_*", body)
            self.assertEqual(
                json.loads(query.call_args.args[0]["sql"]), {"index": "2_first_*,2_second_*", "body": original}
            )
            storages.assert_not_called()
            route.assert_not_called()
            self.assertEqual(body, original)
