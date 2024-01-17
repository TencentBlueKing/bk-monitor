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
DEFAULT_PROFILE_DATA_TYPE = "cpu"
DEFAULT_EXPORT_FORMAT = "pprof"

EXPORT_FORMAT_MAP = {"pprof": "pprof"}


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
