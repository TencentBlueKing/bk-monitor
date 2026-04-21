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
from unittest.mock import patch

from django.test import TestCase

from apps.exceptions import ApiResultError
from apps.log_esquery.exceptions import EsClientSearchException
from apps.log_search.models import Scenario
from apps.log_esquery.esquery.client.QueryClient import QueryClient
from apps.log_esquery.esquery.client.QueryClientBkData import QueryClientBkData


INDICES = ["1_Foo"]

INDICES_MAPPING = {"1_foo_2020010100": {}, "1_foo_bar_2020010100": {}}


class MissingMessageApiResultError(ApiResultError):
    def __getattribute__(self, item):
        if item == "message":
            raise AttributeError("message missing")
        return super().__getattribute__(item)

    def __str__(self):
        return "missing message"


class TestBkdata(TestCase):
    def test_filter_indices(self):
        client = QueryClient(scenario_id=Scenario.BKDATA).get_instance()
        result = client.filter_mapping(INDICES, INDICES_MAPPING)
        self.assertIn("1_foo_2020010100", result)
        self.assertNotIn("1_foo_bar_2020010100", result)
        return True

    @patch("apps.api.BkDataQueryApi.query")
    def test_query_uses_fallback_error_message(self, mock_query):
        mock_query.side_effect = MissingMessageApiResultError("bkdata failed", code="123")

        with self.assertRaises(EsClientSearchException) as ctx:
            QueryClientBkData().query(index="1_foo", body={})

        self.assertEqual(ctx.exception.code, "123")
        self.assertEqual(ctx.exception.message, "missing message")
