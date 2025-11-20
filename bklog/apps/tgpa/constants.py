"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from django.utils.translation import gettext as _

from apps.utils import ChoicesEnum


TGPA_BASE_DIR = "/tmp/log-search/tgpa"
TASK_LIST_BATCH_SIZE = 200
TGPA_TASK_EXE_CODE_SUCCESS = "0"  # 文件上传成功状态码
FEATURE_TOGGLE_TGPA_TASK = "tgpa_task"
TEXT_FILE_EXTENSIONS = [
    ".log",
    ".txt",
    ".json",
    ".csv",
    ".xml",
    ".yaml",
    ".yml",
    ".conf",
    ".config",
    ".ini",
    ".properties",
    ".sql",
    ".md",
    ".rst",
    ".cfg",
]


class TGPATaskTypeEnum(ChoicesEnum):
    """任务类型"""

    SYSTEM_LOG = 7
    BUSINESS_LOG_V2 = 8

    _choices_labels = (
        (SYSTEM_LOG, _("系统日志捞取")),
        (BUSINESS_LOG_V2, _("业务日志捞取V2")),
    )


class TGPATaskPlatformEnum(ChoicesEnum):
    """客户端类型"""

    IOS = "ios"
    ANDROID = "android"
    MACOS = "macos"
    WINDOWS = "windows"
    HARMONY = "harmony"

    _choices_labels = (
        (IOS, _("iOS")),
        (ANDROID, _("安卓")),
        (MACOS, _("macOS")),
        (WINDOWS, _("Windows")),
        (HARMONY, _("Harmony")),
    )


class TGPATaskSceneEnum(ChoicesEnum):
    """任务阶段"""

    BEFORE_LOGIN = 1
    AFTER_LOGIN = 4

    _choices_labels = (
        (BEFORE_LOGIN, _("登录前")),
        (AFTER_LOGIN, _("登录后")),
    )


class TGPATaskFrequencyEnum(ChoicesEnum):
    """触发频率"""

    SINGLE = "single"
    SUSTAIN = "sustain"

    _choices_labels = (
        (SINGLE, _("单次触发")),
        (SUSTAIN, _("持续触发")),
    )


class TGPATaskProcessStatusEnum(ChoicesEnum):
    """任务处理状态"""

    PENDING = "pending"
    PROCESSING = "running"
    SUCCESS = "success"
    FAILED = "failed"

    _choices_labels = (
        (PENDING, _("待处理")),
        (PROCESSING, _("处理中")),
        (SUCCESS, _("成功")),
        (FAILED, _("失败")),
    )
