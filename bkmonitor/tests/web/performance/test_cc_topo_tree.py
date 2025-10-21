# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
#!/usr/bin/python
# -*- coding: utf-8 -*-


from core.drf_resource import resource
from tests.web.performance import mock_cache, mock_cc


class TestCcTopoTree(object):
    def test_instance(self, mocker):
        mock_cc(mocker)
        mock_cache(mocker)
        assert resource.performance.cc_topo_tree.request(bk_biz_id=2) == [
            {
                "bk_inst_id": 2,
                "bk_inst_name": "idle pool",
                "bk_obj_id": "set",
                "bk_obj_name": "\u96c6\u7fa4",
                "child": [
                    {
                        "bk_inst_id": 3,
                        "bk_inst_name": "idle machine",
                        "bk_obj_id": "module",
                        "bk_obj_name": "\u6a21\u5757",
                        "child": [],
                    },
                    {
                        "bk_inst_id": 4,
                        "bk_inst_name": "fault machine",
                        "bk_obj_id": "module",
                        "bk_obj_name": "\u6a21\u5757",
                        "child": [],
                    },
                ],
            },
            {
                "bk_inst_id": 7,
                "bk_inst_name": "\xe6\x95\xb0\xe6\x8d\xae\xe6\x9c\x8d\xe5\x8a\xa1\xe6\xa8\xa1\xe5\x9d\x97",
                "bk_obj_id": "set",
                "bk_obj_name": "set",
                "child": [
                    {
                        "bk_inst_id": 31,
                        "bk_inst_name": "dataapi",
                        "bk_obj_id": "module",
                        "bk_obj_name": "module",
                        "child": [],
                        "default": 0,
                    }
                ],
                "default": 0,
            },
            {
                "bk_inst_id": 8,
                "bk_inst_name": "\xe5\x85\xac\xe5\x85\xb1\xe7\xbb\x84\xe4\xbb\xb6",
                "bk_obj_id": "set",
                "bk_obj_name": "set",
                "child": [
                    {
                        "bk_inst_id": 34,
                        "bk_inst_name": "kafka",
                        "bk_obj_id": "module",
                        "bk_obj_name": "module",
                        "child": [],
                        "default": 0,
                    }
                ],
                "default": 0,
            },
            {
                "bk_inst_id": 9,
                "bk_inst_name": "\xe9\x9b\x86\xe6\x88\x90\xe5\xb9\xb3\xe5\x8f\xb0",
                "bk_obj_id": "set",
                "bk_obj_name": "set",
                "child": [
                    {
                        "bk_inst_id": 47,
                        "bk_inst_name": "paas",
                        "bk_obj_id": "module",
                        "bk_obj_name": "module",
                        "child": [],
                        "default": 0,
                    }
                ],
                "default": 0,
            },
        ]

    def test_no_data(self, mocker):
        mocker.patch("monitor.performance.resources.resource.cc.topo_tree", return_value=[])
        assert resource.performance.cc_topo_tree.request(bk_biz_id=2) == []
