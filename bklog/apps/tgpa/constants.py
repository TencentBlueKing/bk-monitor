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
TGPA_DOWNLOAD_DIR = "/tmp/log-search/tgpa_file_download"
TASK_LIST_BATCH_SIZE = 1000
TGPA_TASK_EXE_CODE_SUCCESS = "0"  # 文件上传成功状态码
FEATURE_TOGGLE_TGPA_TASK = "tgpa_task"
FEATURE_TGPA_FILE_DOWNLOAD_MAX_SIZE = 1024 * 1024 * 10  # 10MB
TGPA_FILE_DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB

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
EXTRACT_FILE_MAX_ITERATIONS = 10  # 解压文件最大迭代次数
COS_DOWNLOAD_MAX_SIZE = 1024 * 1024 * 1024  # COS文件下载最大大小限制: 1GB
COS_DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # COS文件下载分块大小: 1MB


class TGPATaskTypeEnum(ChoicesEnum):
    """任务类型"""

    BUSINESS_LOG_V1 = 6
    SYSTEM_LOG = 7
    BUSINESS_LOG_V2 = 8

    _choices_labels = (
        (SYSTEM_LOG, _("系统日志捞取")),
        (BUSINESS_LOG_V1, _("业务日志捞取")),
        (BUSINESS_LOG_V2, _("业务日志捞取V2")),
    )

    @classmethod
    def get_business_log_task_types(cls):
        """获取业务日志捞取任务类型（逗号分隔的字符串，支持v1和v2）"""
        return ",".join([str(cls.BUSINESS_LOG_V1.value), str(cls.BUSINESS_LOG_V2.value)])


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


class TGPATaskStatusEnum(ChoicesEnum):
    """任务状态"""

    PENDING = -3
    APPROVED = -2
    DENIED = -1
    CREATED = 0
    RUNNING = 1
    STOPPED = 2
    FAILED = 3
    SUCCESS = 4
    CREATE_FAILED = 5
    CLAIM_TIMEOUT = 6
    EXECUTE_TIMEOUT = 7
    CLAIMING = 8
    DELETED = 9
    CREATING = 10
    STARTING = 11

    _choices_labels = (
        (PENDING, _("待审批")),
        (APPROVED, _("审批通过")),
        (DENIED, _("审批拒绝")),
        (CREATED, _("已创建")),
        (RUNNING, _("执行中")),
        (STOPPED, _("停止")),
        (FAILED, _("执行失败")),
        (SUCCESS, _("执行完成")),
        (CREATE_FAILED, _("创建失败")),
        (CLAIM_TIMEOUT, _("认领超时")),
        (EXECUTE_TIMEOUT, _("执行超时")),
        (CLAIMING, _("认领中")),
        (DELETED, _("已删除")),
        (CREATING, _("创建中")),
        (STARTING, _("启动中")),
    )

    @classmethod
    def get_active_statuses(cls):
        """获取进行中的任务状态（即任务还没结束）"""
        return [
            cls.PENDING.value,
            cls.APPROVED.value,
            cls.CREATED.value,
            cls.RUNNING.value,
            cls.CLAIMING.value,
            cls.CREATING.value,
            cls.STARTING.value,
        ]


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


TGPA_REPORT_FILTER_FIELDS = ["openid", "file_name"]
TGPA_REPORT_ORDER_FIELDS = ["file_size"]
TGPA_REPORT_LIST_BATCH_SIZE = 2000  # 客户端日志上报列表批量查询大小
TGPA_REPORT_SOURCE_FIELDS = [
    "openid",
    "file_name",
    "real_name",
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
    "cc_id",
]
TGPA_REPORT_OFFSET_MINUTES = -5  # 客户端日志上报同步偏移时间
TGPA_REPORT_MAX_TIME_RANGE_MINUTES = 30  # 客户端日志上报同步最大时间跨度
TGPA_UNFINISHED_TASK_CHECK_DAYS = 7  # 未完成任务的最大回溯天数
