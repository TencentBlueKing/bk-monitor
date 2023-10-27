# -*- coding: utf-8 -*-
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
from dataclasses import dataclass
from typing import List

from apps.utils import ChoicesEnum
from django.utils.translation import ugettext_lazy as _

DEFAULT_MAX_WORKERS = 5


class NotifyType(ChoicesEnum):
    """
    支持的通知方式
    """

    EMAIL = "email"

    _choices_labels = ((EMAIL, _("邮件")),)

    @classmethod
    def get_choice_label(cls, key: str) -> dict:
        # 获取提醒方式，默认值为email
        choice_dict = dict(cls.get_choices())
        return choice_dict.get(key, choice_dict[cls.EMAIL.value])


class RemoteStorageType(ChoicesEnum):
    """
    支持的远程存储方式
    """

    COS = "cos"
    NFS = "nfs"
    BKREPO = "bkrepo"

    _choices_labels = ((COS, _("腾讯云对象存储")), (NFS, _("远程文件系统")), (BKREPO, _("蓝鲸文件存储服务")))

    @classmethod
    def get_choice_label(cls, key: str) -> dict:
        # 获取提醒方式，默认值为nfs
        choice_dict = dict(cls.get_choices())
        return choice_dict.get(key, choice_dict[cls.NFS.value])


class UserOperationTypeEnum(ChoicesEnum):
    COLLECTOR = "collector"
    COLLECTOR_PLUGIN = "collector_plugin"
    STORAGE = "storage"
    INDEX_SET = "index_set"
    INDEX_SET_CONFIG = "index_set_config"
    SEARCH = "search"
    ETL = "etl"
    EXPORT = "export"
    LOG_EXTRACT_STRATEGY = "log_extract_strategy"
    LOG_EXTRACT_LINKS = "log_extract_links"
    LOG_EXTRACT_TASKS = "log_extract_tasks"

    _choices_labels = (
        (COLLECTOR, _("采集项")),
        (STORAGE, _("存储集群")),
        (INDEX_SET, _("索引集")),
        (INDEX_SET_CONFIG, _("索引集配置")),
        (SEARCH, _("检索配置")),
        (ETL, _("清洗配置")),
        (EXPORT, _("导出")),
        (LOG_EXTRACT_STRATEGY, _("日志提取策略")),
        (LOG_EXTRACT_LINKS, _("日志提取链路")),
        (LOG_EXTRACT_TASKS, _("日志提取任务")),
    )


class UserOperationActionEnum(ChoicesEnum):
    CREATE = "create"
    UPDATE = "update"
    DESTROY = "destroy"
    RETRY = "retry"
    START = "start"
    STOP = "stop"
    REPLACE_CREATE = "replace_create"
    REPLACE_UPDATE = "replace_update"
    CONFIG = "config"

    _choices_labels = (
        (CREATE, _("创建")),
        (UPDATE, _("更新")),
        (DESTROY, _("删除")),
        (RETRY, _("任务重试")),
        (START, _("启动")),
        (STOP, _("停止")),
        (REPLACE_CREATE, _("新建并替换")),
        (REPLACE_UPDATE, _("替换")),
        (CONFIG, _("配置")),
    )


class LuceneSyntaxEnum(object):
    """Lucene语法枚举"""

    UNKNOWN = "UnknownOperation"
    SEARCH_FIELD = "SearchField"
    OR_OPERATION = "OrOperation"
    AND_OPERATION = "AndOperation"
    WORD = "Word"
    PHRASE = "Phrase"
    PROXIMITY = "Proximity"
    RANGE = "Range"
    FUZZY = "Fuzzy"
    REGEX = "Regex"
    GROUP = "Group"
    FIELD_GROUP = "FieldGroup"
    # Unary operator
    NOT = "Not"
    PLUS = "Plus"
    PROHIBIT = "Prohibit"


FULL_TEXT_SEARCH_FIELD_NAME = _("全文检索")

DEFAULT_FIELD_OPERATOR = "~="
FIELD_GROUP_OPERATOR = "()"
NOT_OPERATOR = "NOT"
PLUS_OPERATOR = "+"
PROHIBIT_OPERATOR = "-"

LOW_CHAR = {True: "[", False: "{"}
HIGH_CHAR = {True: "]", False: "}"}

WORD_RANGE_OPERATORS = r"<=|>=|<|>"

BRACKET_DICT = {"[": "]", "(": ")", "{": "}"}

# 最大语法修复次数
MAX_RESOLVE_TIMES = 10

# 默认JOB执行脚本超时时间
DEFAULT_EXECUTE_SCRIPT_TIMEOUT = 600


class ScriptType(ChoicesEnum):
    SHELL = 1
    BAT = 2
    PERL = 3
    PYTHON = 4
    POWERSHELL = 5

    _choices_labels = (
        (SHELL, _("shell")),
        (BAT, _("bat")),
        (PERL, _("perl")),
        (PYTHON, _("python")),
        (POWERSHELL, _("powershell")),
    )


class SpacePropertyEnum(ChoicesEnum):
    """
    空间属性枚举
    """

    SPACE_TYPE = "space_type"

    _choices_labels = (SPACE_TYPE, _("空间类型"))


class ApiTokenAuthType(ChoicesEnum):
    """
    API Token鉴权类型
    """

    GRAFANA = "Grafana"

    _choices_labels = ((GRAFANA, _("Grafana")),)


class TokenStatusEnum(ChoicesEnum):
    AVAILABLE = "available"
    INVALID = "invalid"
    EXPIRED = "expired"

    _choices_labels = (
        (AVAILABLE, _("有效")),
        (INVALID, _("无效")),
        (EXPIRED, _("过期")),
    )


class ITSMStatusChoicesEnum(ChoicesEnum):
    NO_STATUS = "no_status"
    APPROVAL = "approval"
    SUCCESS = "success"
    FAILED = "failed"

    _choices_labels = (
        (NO_STATUS, _("无状态")),
        (APPROVAL, _("审批中")),
        (SUCCESS, _("成功")),
        (FAILED, _("失败")),
    )


@dataclass
class Action:
    """
    定义一个行为, 用于权限校验
    view_set: 视图
    action_id: 视图下的方法, 当action为空时, 代表这个view_set下所有接口
    """

    view_set: str
    action_id: str = ""


class ViewTypeEnum(ChoicesEnum):
    USER = "user"
    RESOURCE = "resource"

    _choices_labels = (
        (USER, _("用户视角")),
        (RESOURCE, _("资源视角")),
    )


class OperateEnum(ChoicesEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

    _choices_labels = (
        (CREATE, _("创建")),
        (UPDATE, _("更新")),
        (DELETE, _("删除")),
    )


class ActionEnum(ChoicesEnum):
    LOG_SEARCH = "log_search"
    LOG_EXTRACT = "log_extract"

    _choices_labels = (
        (LOG_SEARCH, _("日志检索")),
        (LOG_EXTRACT, _("日志提取")),
    )


# 默认允许的action
DEFAULT_ALLOW_ACTIONS: List[Action] = [
    Action(view_set="MetaViewSet", action_id="list_spaces_mine"),
]

ACTION_MAP = {
    ActionEnum.LOG_SEARCH.value: [
        Action(view_set="MetaViewSet", action_id="list_spaces_mine"),
        Action(view_set="SearchViewSet", action_id="list"),
        Action(view_set="SearchViewSet", action_id="bizs"),
        Action(view_set="SearchViewSet", action_id="search"),
        Action(view_set="SearchViewSet", action_id="fields"),
        Action(view_set="SearchViewSet", action_id="context"),
        Action(view_set="SearchViewSet", action_id="tailf"),
        Action(view_set="SearchViewSet", action_id="export"),
        Action(view_set="AggsViewSet", action_id="terms"),
        Action(view_set="AggsViewSet", action_id="date_histogram"),
        Action(view_set="FavoriteViewSet"),
    ],
    ActionEnum.LOG_EXTRACT.value: [
        Action(view_set="ExplorerViewSet"),
        Action(view_set="TasksViewSet"),
        Action(view_set="StrategiesViewSet"),
    ],
}

# 与权限中心的action_id对应关系
ACTION_ID_MAP = {
    ActionEnum.LOG_SEARCH.value: "search_log_v2",
    ActionEnum.LOG_EXTRACT.value: "manage_extract_config_v2",
}
