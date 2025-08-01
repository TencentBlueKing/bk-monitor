"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings


def qos_set_bk_data_ts(interval=3):
    settings.QOS_DATASOURCE_LABELS = settings.QOS_DATASOURCE_LABELS = [["bk_data", "time_series"]]
    settings.QOS_INTERVAL_EXPAND = interval


def qos_set_bk_log_ts(interval=3):
    settings.QOS_DATASOURCE_LABELS = settings.QOS_DATASOURCE_LABELS = [
        ["bk_log_search", "log"],
        ["bk_log_search", "time_series"],
    ]
    settings.QOS_INTERVAL_EXPAND = interval


def qos_clear_access():
    settings.QOS_DATASOURCE_LABELS = settings.QOS_DATASOURCE_LABELS = []
