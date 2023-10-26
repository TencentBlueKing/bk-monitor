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

# environment
CONST_PROD = "production"
CONST_TEST = "testing"
CONST_DEV = "development"

# time
CONST_SECOND = 1
CONST_HALF_MINUTE = 30 * CONST_SECOND
CONST_MINUTES = 60 * CONST_SECOND
CONST_ONE_HOUR = 60 * CONST_MINUTES
CONST_ONE_DAY = 24 * CONST_ONE_HOUR
CONST_ONE_WEEK = 7 * CONST_ONE_DAY

# time format
STD_ARROW_FORMAT = "YYYY-MM-DD HH:mm:ss"  # 2019-01-01 10:18:06
STD_LOG_DT_FORMAT = "%Y-%m-%d %H:%M:%S%z"  # 2019-01-01 03:15:03+0000

# Fields that standard data must have
StandardDataFields = (
    "time",  # timstamp(unit:s)
    "value",  # float, Keep two decimals
    "values",  # list
    "dimensions",  # list
    "record_id",  # md5
    "dimension_fields",  # list
)

# Fields that standard anomaly must have
StandardAnomalyFields = (
    "anomaly_id",  # md5
    "anomaly_time",  # timestamp
    "anomaly_message",  # str, message
)

# Fields that standard event must have
StandardEventFields = (
    "data",
    "anomaly",
    "strategy_snapshot_key",
)

# Fields that standard alert must have
StandardAlertFields = ()

# key of latest_point_with_all
LATEST_POINT_WITH_ALL_KEY = "__ALL__"

# nodata constants

# alarm level of no data
NO_DATA_LEVEL = 2

# no data record value
NO_DATA_VALUE = None

# nodata dimension tag
NO_DATA_TAG_DIMENSION = "__NO_DATA_DIMENSION__"

# key of nodata latest check point
LATEST_NO_DATA_CHECK_POINT = "__NO_DATA_CHECK_POINT__"

# fta constants

# event default dedupe fields
DEFAULT_DEDUPE_FIELDS = ["alert_name", "strategy_id", "target_type", "target", "bk_biz_id"]

METRIC_VALUE_FIELD = "__value__"
