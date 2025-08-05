"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

INCIDENT_METRICS_SEARCH_MOCK_DATA = {
    "bk_biz_id": 2,
    "metrics": {
        "apm.error_count": {
            "metric_name": "apm.error_count",
            "metric_alias": "错误请求数量",
            "metric_type": "ebpf_call",
            "time_series": [
                [
                    1746682440000,  # 时间戳
                    10.0,  # 序列值
                    0,  # 是否展示异常红点
                ],
                [1746682500000, 4.0, 0],
                [1746682560000, 28.0, 0],
            ],
        },
        "apm.delay_count": {
            "metric_name": "apm.delay_count",
            "metric_alias": "慢请求数量",
            "metric_type": "ebpf_call",
            "time_series": [
                [
                    1746682440000,  # 时间戳
                    10.0,  # 序列值
                    0,  # 是否展示异常红点
                ],
                [1746682500000, 4.0, 0],
                [1746682560000, 28.0, 0],
            ],
        },
    },
}
