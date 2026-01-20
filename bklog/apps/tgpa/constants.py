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
TASK_LIST_BATCH_SIZE = 500
TGPA_TASK_EXE_CODE_SUCCESS = "0"  # 文件上传成功状态码
FEATURE_TOGGLE_TGPA_TASK = "tgpa_task"

TGPA_TASK_COLLECTOR_CONFIG_NAME = "客户端日志"
TGPA_TASK_COLLECTOR_CONFIG_NAME_EN = "tgpa_task_client_log"

TGPA_TASK_ETL_PARAMS = {
    "retain_original_text": False,
    "retain_extra_json": False,
    "enable_retain_content": True,
    "record_parse_failure": False,
}

TGPA_TASK_ETL_FIELDS = [
    {
        "field_name": "message",
        "field_type": "string",
        "is_dimension": False,
        "is_analyzed": True,
        "is_time": False,
        "description": "message",
        "is_delete": False,
    },
    {
        "field_name": "task_id",
        "field_type": "int",
        "is_dimension": True,
        "is_analyzed": False,
        "is_time": False,
        "description": "task_id",
        "is_delete": False,
    },
    {
        "field_name": "task_name",
        "field_type": "string",
        "is_dimension": True,
        "is_analyzed": False,
        "is_time": False,
        "description": "task_name",
        "is_delete": False,
    },
    {
        "field_name": "file",
        "field_type": "string",
        "is_dimension": True,
        "is_analyzed": False,
        "is_time": False,
        "description": "file",
        "is_delete": False,
    },
    {
        "field_name": "openid",
        "field_type": "string",
        "is_dimension": True,
        "is_analyzed": False,
        "is_time": False,
        "description": "openid",
        "is_delete": False,
    },
    {
        "field_name": "lineno",
        "field_type": "int",
        "is_dimension": True,
        "is_analyzed": False,
        "is_time": False,
        "description": "lineno",
        "is_delete": False,
    },
    {
        "field_name": "manufacturer",
        "field_type": "string",
        "is_dimension": True,
        "is_analyzed": False,
        "is_time": False,
        "description": "manufacturer",
        "is_delete": False,
    },
    {
        "field_name": "sdk_version",
        "field_type": "string",
        "is_dimension": True,
        "is_analyzed": False,
        "is_time": False,
        "description": "sdk_version",
        "is_delete": False,
    },
    {
        "field_name": "os_type",
        "field_type": "string",
        "is_dimension": True,
        "is_analyzed": False,
        "is_time": False,
        "description": "os_type",
        "is_delete": False,
    },
    {
        "field_name": "os_version",
        "field_type": "string",
        "is_dimension": True,
        "is_analyzed": False,
        "is_time": False,
        "description": "os_version",
        "is_delete": False,
    },
    {
        "field_name": "model",
        "field_type": "string",
        "is_dimension": True,
        "is_analyzed": False,
        "is_time": False,
        "description": "model",
        "is_delete": False,
    },
    {
        "field_name": "cos_file_name",
        "field_type": "string",
        "is_dimension": True,
        "is_analyzed": False,
        "is_time": False,
        "description": "cos_file_name",
        "is_delete": False,
    },
]

TGPA_TASK_SORT_FIELDS = ["lineno", "dtEventTimeStamp"]
TGPA_TASK_TARGET_FIELDS = ["cos_file_name", "file"]

CLIENT_LOG_UNIQUE_FIELD_LIST = ["task_id", "file", "lineno", "cos_file_name"]
LOG_FILE_EXPIRE_DAYS = 3


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

    ALL = "all"
    IOS = "ios"
    ANDROID = "android"
    MACOS = "macos"
    WINDOWS = "windows"
    HARMONY = "harmony"

    _choices_labels = (
        (ALL, _("默认")),
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

    INIT = "init"
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

    _choices_labels = (
        (INIT, _("初始化")),
        (PENDING, _("待处理")),
        (RUNNING, _("处理中")),
        (SUCCESS, _("成功")),
        (FAILED, _("失败")),
    )


class TGPAReportSyncStatusEnum(ChoicesEnum):
    """客户端日志上报同步状态"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

    _choices_labels = (
        (PENDING, _("未上传")),
        (RUNNING, _("上传中")),
        (SUCCESS, _("上传成功")),
        (FAILED, _("上传失败")),
    )


TGPA_REPORT_SELECT_FIELDS = [
    "openid",
    "file_name",
    "real_name as file_path",
    "file_size",
    "md5",
    "report_time",
    "xid",
    "extend_info",
    "manufacturer",
    "model",
    "os_version",
    "os_sdk",
    "os_type",
    "cc_id as bk_biz_id",
]
TGPA_REPORT_FILTER_FIELDS = ["openid", "file_name"]
TGPA_REPORT_ORDER_FIELDS = ["file_size"]
TGPA_REPORT_LIST_BATCH_SIZE = 500  # 客户端日志上报列表批量查询大小
