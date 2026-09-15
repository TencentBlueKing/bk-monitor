"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial portions of
the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from django.test import SimpleTestCase

from apps.tgpa.handlers.report import TGPAReportHandler


class TestTGPAReportHandler(SimpleTestCase):
    def test_keyword_matches_extend_info_without_changing_existing_prefix_filters(self):
        query = TGPAReportHandler._build_es_query(
            bk_biz_id=100231,
            keyword="PeopleUnVisible",
            start_time=1716000000000,
            end_time=1716600000000,
        )

        keyword_query = query["bool"]["must"][1]["bool"]

        self.assertEqual(keyword_query["minimum_should_match"], 1)
        self.assertEqual(
            keyword_query["should"],
            [
                {"prefix": {"openid": "PeopleUnVisible"}},
                {"prefix": {"file_name": "PeopleUnVisible"}},
                {
                    "wildcard": {
                        "extend_info": {
                            "value": "*PeopleUnVisible*",
                        }
                    }
                },
            ],
        )

    def test_keyword_escapes_wildcard_operators(self):
        query = TGPAReportHandler._build_es_query(
            bk_biz_id=100231,
            keyword=r"foo*bar?",
            start_time=1716000000000,
            end_time=1716600000000,
        )

        wildcard_query = query["bool"]["must"][1]["bool"]["should"][2]
        self.assertEqual(wildcard_query["wildcard"]["extend_info"]["value"], r"*foo\*bar\?*")
