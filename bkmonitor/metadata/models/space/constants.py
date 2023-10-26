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
import os
from enum import Enum

from django.conf import settings

# 默认 page 及 page_size 的值
DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 1000


class SpaceTypes(Enum):
    """空间类型"""

    BKCC = "bkcc"
    BCS = "bcs"
    BKCI = "bkci"
    BKSAAS = "bksaas"
    DEFAULT = "default"
    ALL = "all"

    _choices_labels = (
        (BKCC, "bkcc"),
        (BCS, "bcs"),
        (BKCI, "bkci"),
        (BKSAAS, "bksaas"),
        (DEFAULT, "default"),
        (ALL, "all"),
    )


class SpaceStatus(Enum):
    """空间状态"""

    NORMAL = "normal"
    DISABLED = "disabled"


class MeasurementType(Enum):
    """表类型"""

    BK_TRADITIONAL = "bk_traditional_measurement"
    BK_SPLIT = "bk_split_measurement"
    BK_EXPORTER = "bk_exporter"
    BK_STANDARD_V2_TIME_SERIES = "bk_standard_v2_time_series"


# 系统资源创建者，默认为 system
SYSTEM_USERNAME = getattr(settings, "COMMON_USERNAME", "system")

# 空间相关配置
# redis 中空间的 key
SPACE_REDIS_KEY = os.environ.get("SPACE_REDIS_KEY", "bkmonitorv3:spaces")
# redis 中空间详情的前缀 key
SPACE_DETAIL_REDIS_KEY_PREFIX = os.environ.get("SPACE_DETAIL_REDIS_KEY_PREFIX", "bkmonitorv3:spaces")
# 空间变动的发布频道, unify-query 监听到有变化后，会重新通过redis获取对应的数据
SPACE_CHANNEL = os.environ.get("SPACE_CHANNEL", "bkmonitorv3:spaces")

# 空间唯一标识连接符
SPACE_UID_HYPHEN = "__"


class EtlConfigs(Enum):
    # 多指标单表(system)
    BK_SYSTEM_BASEREPORT = "bk_system_basereport"
    BK_UPTIMECHECK_HEARTBEAT = "bk_uptimecheck_heartbeat"
    BK_UPTIMECHECK_HTTP = "bk_uptimecheck_http"
    BK_UPTIMECHECK_TCP = "bk_uptimecheck_tcp"
    BK_UPTIMECHECK_UDP = "bk_uptimecheck_udp"
    BK_SYSTEM_PROC_PORT = "bk_system_proc_port"
    BK_SYSTEM_PROC = "bk_system_proc"
    # 自定义多指标单表
    BK_STANDARD_V2_TIME_SERIES = "bk_standard_v2_time_series"
    # 固定指标单表(metric_name)
    BK_EXPORTER = "bk_exporter"
    BK_STANDARD = "bk_standard"

    _choices_labels = (
        (BK_SYSTEM_BASEREPORT, "bk_system_basereport"),
        (BK_UPTIMECHECK_HEARTBEAT, "bk_uptimecheck_heartbeat"),
        (BK_UPTIMECHECK_HTTP, "bk_uptimecheck_http"),
        (BK_UPTIMECHECK_TCP, "bk_uptimecheck_tcp"),
        (BK_UPTIMECHECK_UDP, "bk_uptimecheck_udp"),
        (BK_SYSTEM_PROC_PORT, "bk_system_proc_port"),
        (BK_SYSTEM_PROC, "bk_system_proc"),
        (BK_STANDARD_V2_TIME_SERIES, "bk_standard_v2_time_series"),
        (BK_EXPORTER, "bk_exporter"),
        (BK_STANDARD, "bk_standard"),
    )


# 数据源 ETL 配置
SPACE_DATASOURCE_ETL_LIST = [item[0] for item in EtlConfigs._choices_labels.value]

# bkcc 存在全业务的空间，空间 ID 为 "0"
EXCLUDED_SPACE_TYPE_ID = SpaceTypes.BKCC.value
EXCLUDED_SPACE_ID = "0"

# 枚举 0 业务，但不是 bkcc 类型的数据源ID
SKIP_DATA_ID_LIST_FOR_BKCC = [1110000]


class BCSClusterTypes(Enum):
    """bcs 集群类型"""

    SINGLE = "single"
    SHARED = "shared"


# 授权蓝盾使用的数据源 ID
BKCI_AUTHORIZED_DATA_LIST = [1001]
