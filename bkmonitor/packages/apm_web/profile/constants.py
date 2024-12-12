"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from enum import Enum

DEFAULT_SERVICE_NAME = "default"
DEFAULT_PROFILE_DATA_TYPE = "cpu/nanoseconds"
DEFAULT_EXPORT_FORMAT = "pprof"

EXPORT_FORMAT_MAP = {"pprof": "pprof"}

# builtin app name in global storage
# may fetch from apm API in the future
BUILTIN_APP_NAME = "builtin_profile_app"

CPU_DESCRIBING_SAMPLE_TYPE = "samples/count"
DESCRIBING_SAMPLE_UNIT = "count"

# 大应用 profile 服务最大可以查询 5000条 sample 数据
LARGE_SERVICE_MAX_QUERY_SIZE = 5000
# 普通 profile 服务最大可以查询 10000条 sample 数据
NORMAL_SERVICE_MAX_QUERY_SIZE = 10000
# grafana 查询的 label 最大数量
GRAFANA_LABEL_MAX_SIZE = 1000


class InputType(Enum):
    PPROF = "pprof"
    PERF_SCRIPT = "perf_script"
    JFR = "jfr"
    DORIS = "doris"

    @classmethod
    def choices(cls):
        return tuple((i.name, i.value) for i in cls)


class CallGraphResponseDataMode:
    # 图片数据模式
    IMAGE_DATA_MODE = "image_data_mode"
    # 纯数据模式 Pure data mode
    PURE_DATA_MODE = "pure_data_mode"


PROFILE_UPLOAD_RECORD_NEW_FILE_NAME = "Profile-{}.pprof"

PROFILE_EXPORT_FILE_NAME = "{app_name}-{data_type}-{time}.{format}"


class CallGraph:
    BASE_SIZE = 0.5
    MAX_SIZE = 2
    MIN_SIZE = 0.2
