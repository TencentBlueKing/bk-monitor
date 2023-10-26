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

DEFAULT_QUERY_TIME_RANGE = 60 * 5
DEFAULT_QUERY_ANOMALY_TIME_RANGE = 60 * 60 * 24
BKDATA_MIN_INTERVAL = 60

QUERY_METRIC_FIELDS = ["is_anomaly", "extra_info", "anomaly_sort", "metrics_json"]
GROUP_BY_METRIC_FIELDS = ["bk_cloud_id", "ip"]

NO_ACCESS_METRIC_ANOMALY_RANGE_COLOR = "rgba(234, 54, 54, 0.1)"
ACCESS_METRIC_ANOMALY_RANGE_COLOR = "rgba(234, 54, 54, 0.4)"


class NoAccessException(Exception):
    pass
