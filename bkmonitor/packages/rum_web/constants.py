"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


# 告警级别常量
class AlertLevel:
    ERROR = 1
    WARN = 2
    INFO = 3


# 告警状态常量
class AlertStatus:
    ABNORMAL = "ABNORMAL"
    RECOVERED = "RECOVERED"


# 数据状态常量
class DataStatus:
    NORMAL = "normal"
    NO_DATA = "no_data"
    DISABLED = "disabled"


# 无数据告警策略配置 key
NODATA_ERROR_STRATEGY_CONFIG_KEY = "nodata_error_strategy_id"

# 无数据告警检测周期（分钟）
DEFAULT_NO_DATA_PERIOD = 10

# 默认 QPS 限制
DEFAULT_RUM_APP_QPS = 500

# 默认 Apdex 配置（单位 ms）
DEFAULT_RUM_APDEX_CONFIG = {
    "lcp": 2500,
    "fcp": 1800,
    "fid": 100,
}

# 应用列表异步指标列名
ASYNC_COLUMN_LCP_P75 = "lcp_p75"
ASYNC_COLUMN_JS_ERROR_RATE = "js_error_rate"
ASYNC_COLUMN_API_FAIL_RATE = "api_fail_rate"

# 首页应用列表异步指标列名选择
ASYNC_COLUMN_CHOICES = [ASYNC_COLUMN_LCP_P75, ASYNC_COLUMN_JS_ERROR_RATE, ASYNC_COLUMN_API_FAIL_RATE]


class DefaultSetupConfig:
    """RUM 创建应用默认配置"""

    DEFAULT_ES_RETENTION_DAYS = 7
    DEFAULT_ES_NUMBER_OF_REPLICAS = 1
    DEFAULT_ES_RETENTION_DAYS_MAX = 7
    DEFAULT_ES_NUMBER_OF_REPLICAS_MAX = 3
    PRIVATE_ES_RETENTION_DAYS_MAX = 30
    PRIVATE_ES_NUMBER_OF_REPLICAS_MAX = 10


class BizConfigKey:
    """业务级配置键名"""

    DEFAULT_ES_RETENTION_DAYS_MAX = "default_es_retention_days_max"
    PRIVATE_ES_RETENTION_DAYS_MAX = "private_es_retention_days_max"
    DEFAULT_ES_NUMBER_OF_REPLICAS_MAX = "default_es_number_of_replicas_max"
    PRIVATE_ES_NUMBER_OF_REPLICAS_MAX = "private_es_number_of_replicas_max"


RUM_WEB_CLIENT_CHOICES = [
    "web",
]
