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

from bkmonitor.data_source import DataQuery
from bkmonitor.data_source.handler.elastic_search import ESDataQuery
from bkmonitor.data_source.handler.log_search import LogSearchDataQuery
from bkmonitor.data_source.handler.time_series import TSDataQuery
from constants.data_source import DataSourceLabel, DataTypeLabel

__all__ = ["DataQueryHandler", "HandlerType"]


class DataQueryHandler(object):
    def __new__(cls, data_source_label, data_type_label):
        if (data_source_label, data_type_label) in [
            (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.LOG),
            (DataSourceLabel.CUSTOM, DataTypeLabel.EVENT),
            (DataSourceLabel.BK_APM, DataTypeLabel.LOG),
            (DataSourceLabel.BK_APM, DataTypeLabel.TIME_SERIES),
        ]:
            q = ESDataQuery((data_source_label, data_type_label))
        elif data_source_label == DataSourceLabel.BK_LOG_SEARCH and data_type_label == DataTypeLabel.LOG:
            q = LogSearchDataQuery((data_source_label, data_type_label))
        elif data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR and data_type_label == DataTypeLabel.TIME_SERIES:
            q = TSDataQuery((data_source_label, data_type_label))
        else:
            q = DataQuery((data_source_label, data_type_label))
        return q


class HandlerType(object):
    KEYWORDS = "keywords"
    LOG_SEARCH = "log_search"
    TIME_SERIES = "time_series"
    CUSTOM_EVENT = "custom_event"
    BASE = "base"
