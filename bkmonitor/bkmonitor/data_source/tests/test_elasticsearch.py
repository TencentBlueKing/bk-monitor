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
from bkmonitor.data_source import dict_to_q
from bkmonitor.data_source.backends.elastic_search.compiler import SQLCompiler


class TestParseFilter:
    def test_or_parse(self):
        filter_dict = {
            "bk_target_ip": ["127.0.0.1", "127.0.0.2"],
            "host": [
                {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 0},
                {"bk_target_ip": "127.0.0.2", "bk_target_cloud_id": 0},
                {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 1},
                {"bk_target_ip": "127.0.0.2", "bk_target_cloud_id": 2},
            ],
            "bk_target_cloud_id": 0,
        }

        q = dict_to_q(filter_dict)
        c = SQLCompiler(1, 2, 3)
        result = c._parser_filter(q)
        assert result == {
            "bool": {
                "must": [
                    {"bool": {"must": [{"terms": {"bk_target_ip": ["127.0.0.1", "127.0.0.2"]}}]}},
                    {
                        "bool": {
                            "should": [
                                {
                                    "bool": {
                                        "must": [
                                            {"terms": {"bk_target_cloud_id": [0]}},
                                            {"terms": {"bk_target_ip": ["127.0.0.1"]}},
                                        ]
                                    }
                                },
                                {
                                    "bool": {
                                        "must": [
                                            {"terms": {"bk_target_cloud_id": [0]}},
                                            {"terms": {"bk_target_ip": ["127.0.0.2"]}},
                                        ]
                                    }
                                },
                                {
                                    "bool": {
                                        "must": [
                                            {"terms": {"bk_target_cloud_id": [1]}},
                                            {"terms": {"bk_target_ip": ["127.0.0.1"]}},
                                        ]
                                    }
                                },
                                {
                                    "bool": {
                                        "must": [
                                            {"terms": {"bk_target_cloud_id": [2]}},
                                            {"terms": {"bk_target_ip": ["127.0.0.2"]}},
                                        ]
                                    }
                                },
                            ]
                        }
                    },
                    {"terms": {"bk_target_cloud_id": [0]}},
                ]
            }
        }
