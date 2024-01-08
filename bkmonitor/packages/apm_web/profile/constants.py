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


class InputType(Enum):
    PPROF = "pprof"
    PERF_SCRIPT = "perf_script"
    JFR = "jfr"
    DORIS = "doris"

    @classmethod
    def choices(cls):
        return tuple((i.name, i.value) for i in cls)


class UploadedFileStatus:
    # 已上传
    UPLOADED = "uploaded"
    # 解析失败
    PARSING_FAILED = "parsing_failed"
    # 解析成功
    PARSING_SUCCEED = "parsing_succeed"

    UNKNOWN = "unknown"

    status_map = {"uploaded": "已上传", "parsing_failed": "解析失败", "parsing_succeed": "解析成功", "unknown": "未知"}

    @classmethod
    def choices(cls):
        return [
            (cls.UPLOADED, "uploaded"),
            (cls.PARSING_FAILED, "parsing_failed"),
            (cls.PARSING_SUCCEED, "parsing_succeed"),
        ]

    @classmethod
    def get_display_name(cls, name):
        return cls.status_map.get(name, cls.status_map["unknown"])


class CallGraphResponseDataMode:
    # 图片数据模式
    IMAGE_DATA_MODE = "image_data_mode"
    # 纯数据模式 Pure data mode
    PURE_DATA_MODE = "pure_data_mode"


PROFILE_UPLOAD_RECORD_NEW_FILE_NAME = "Profile-{}.pprof"
