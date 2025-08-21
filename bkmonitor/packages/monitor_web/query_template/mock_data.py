"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from copy import deepcopy

from bkmonitor.query_template import mock_data

CALLEE_SUCCESS_RATE_QUERY_TEMPLATE_DETAIL = {"id": 1, **deepcopy(mock_data.CALLEE_SUCCESS_RATE_QUERY_TEMPLATE)}

CALLEE_P99_QUERY_TEMPLATE_DETAIL = {"id": 2, **deepcopy(mock_data.CALLEE_P99_QUERY_TEMPLATE)}

QUERY_TEMPLATE_LIST = {
    "total": 2,
    "list": [
        {
            "id": CALLEE_SUCCESS_RATE_QUERY_TEMPLATE_DETAIL["id"],
            "name": CALLEE_SUCCESS_RATE_QUERY_TEMPLATE_DETAIL["name"],
            "description": "模板说明",
            "create_user": "admin",
            "create_time": "2025-08-04 17:43:26+0800",
            "update_user": "admin",
            "update_time": "2025-08-04 17:43:26+0800",
        },
        {
            "id": CALLEE_P99_QUERY_TEMPLATE_DETAIL["id"],
            "name": CALLEE_P99_QUERY_TEMPLATE_DETAIL["name"],
            "description": "模板演示数据",
            "create_user": "admin",
            "create_time": "2025-08-04 17:43:26+0800",
            "update_user": "admin",
            "update_time": "2025-08-04 17:43:26+0800",
        },
    ],
}

# 查询模板列表关联资源数量
QUERY_TEMPLATE_RELATIONS = [
    {"query_template_id": CALLEE_SUCCESS_RATE_QUERY_TEMPLATE_DETAIL["id"], "relation_config_count": 2},
    {"query_template_id": CALLEE_P99_QUERY_TEMPLATE_DETAIL["id"], "relation_config_count": 1},
]

CALLEE_P99_QUERY_TEMPLATE_RELATION = [
    {
        "url": "https://bkmonitor.paas3-dev.bktencent.com/?bizId=2#/strategy-config/detail/64924",
        "name": "资源名称",
        "type": "ALERT_POLICY",
    },
]

CALLEE_SUCCESS_RATE_QUERY_TEMPLATE_PREVIEW = mock_data.CALLEE_SUCCESS_RATE_QUERY_INSTANCE
