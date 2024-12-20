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

from django.utils.translation import gettext_lazy as _

from apps.utils import ChoicesEnum

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
PLUS_OPERATOR = "+"
PROHIBIT_OPERATOR = "-"

LOW_CHAR = {True: "[", False: "{"}
HIGH_CHAR = {True: "]", False: "}"}

WORD_RANGE_OPERATORS = r"<=|>=|<|>"

BRACKET_DICT = {"[": "]", "(": ")", "{": "}"}

# 最大语法修复次数
MAX_RESOLVE_TIMES = 10

# Lucene数值类字段操作符
LUCENE_NUMERIC_OPERATORS = ["<", "<=", ">", ">=", "="]
# Lucene数值类类型列表
LUCENE_NUMERIC_TYPES = ["long", "integer", "short", "double", "float"]


class LuceneReservedLogicOperatorEnum(ChoicesEnum):
    """
    Lucene保留逻辑操作符枚举
    """

    AND = "AND"
    OR = "OR"
    NOT = "NOT"

    _choices_keys = (AND, OR, NOT)


# Lucene保留字符
LUCENE_RESERVED_CHARS = ["+", "-", "=", "&", "&&", ">", "<", "!", "(", ")", "}", "[", "]", '"', "~", "*", "?", ":", "/"]
# 全角冒号
FULL_WIDTH_COLON = "："
# 全角字符转半角字符
FULL_WIDTH_CHAR_MAP = {
    "（": "(",
    "）": ")",
    "【": "[",
    "】": "]",
    "］": "]",
    "［": "[",
    "｛": "{",
    "｝": "}",
    "＋": "+",
    "－": "-",
    "＝": "=",
    "＆": "&",
    "＜": "<",
    "＞": ">",
    "！": "!",
    "＂": '"',
    "～": "~",
    "＊": "*",
    "？": "?",
    "：": ":",
    "／": "/",
    "”": '"',
    "“": '"',
    "‘": "'",
    "’": "'",
    "，": ",",
    "。": ".",
    "、": "\\",
    "；": ";",
    "·": ".",
    "《": "<",
    "》": ">",
}

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


class ExternalPermissionActionEnum(ChoicesEnum):
    LOG_SEARCH = "log_search"
    LOG_EXTRACT = "log_extract"
    LOG_COMMON = "log_common"

    _choices_labels = (
        (LOG_SEARCH, _("日志检索")),
        (LOG_EXTRACT, _("日志提取")),
    )


@dataclass
class ViewSetAction:
    """
    定义一个行为, 用于权限校验
    action_id: 外部版授权的操作合集ID, 枚举ExternalPermissionActionEnum
    view_set: 视图
    action_id: 视图下的方法, 当action为空时, 代表这个view_set下所有接口
    """

    view_set: str
    action_id: str = ExternalPermissionActionEnum.LOG_COMMON.value
    view_action: str = ""
    default_permission: bool = False

    def __post_init__(self):
        if self.action_id == ExternalPermissionActionEnum.LOG_COMMON.value:
            self.default_permission = True

    def eq(self, other):
        return self.view_set == other.view_set and self.view_action == other.view_action

    def is_one_of(self, others):
        for other in others:
            if self.eq(other):
                return True
        return False


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


class ViewSetActionEnum(ChoicesEnum):
    """
    定义一个行为, 用于权限校验
    """

    # ======================================= 检索-SearchViewSet =======================================
    SEARCH_VIEWSET_LIST = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="list"
    )
    SEARCH_VIEWSET_BIZS = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="bizs"
    )
    SEARCH_VIEWSET_SEARCH = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="search"
    )
    SEARCH_VIEWSET_FIELDS = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="fields"
    )
    SEARCH_VIEWSET_CONTEXT = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="context"
    )
    SEARCH_VIEWSET_TAILF = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="tailf"
    )
    SEARCH_VIEWSET_EXPORT = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="export"
    )
    SEARCH_VIEWSET_ASYNC_EXPORT = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="async_export"
    )
    SEARCH_VIEWSET_GET_EXPORT_HISTORY = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
        view_set="SearchViewSet",
        view_action="get_export_history",
    )
    SEARCH_VIEWSET_HISTORY = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="history"
    )
    SEARCH_VIEWSET_OPTION_HISTORY = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="option_history"
    )
    SEARCH_VIEWSET_CONFIG = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="config"
    )
    SEARCH_VIEWSET_CREATE_CONFIG = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="create_config"
    )
    SEARCH_VIEWSET_UPDATE_CONFIG = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="update_config"
    )
    SEARCH_VIEWSET_RETRIEVE_CONFIG = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="retrieve_config"
    )
    SEARCH_VIEWSET_LIST_CONFIG = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="list_config"
    )
    SEARCH_VIEWSET_DELETE_CONFIG = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="SearchViewSet", view_action="delete_config"
    )
    # ======================================= 聚合-AggsViewSet =======================================
    AGGS_VIEWSET_TERMS = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="AggsViewSet", view_action="terms"
    )
    AGGS_VIEWSET_DATE_HISTOGRAM = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="AggsViewSet", view_action="date_histogram"
    )
    # ======================================= 字段分析-FieldViewSet =======================================
    FIELD_VIEWSET_TOTAL = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
        view_set="FieldViewSet",
        view_action="fetch_statistics_total",
    )
    FIELD_VIEWSET_GRAPH = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
        view_set="FieldViewSet",
        view_action="fetch_statistics_graph",
    )
    FIELD_VIEWSET_INFO = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
        view_set="FieldViewSet",
        view_action="fetch_statistics_info",
    )
    FIELD_VIEWSET_TOPK = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="FieldViewSet", view_action="fetch_topk_list"
    )
    # ======================================= 日志聚类-FieldViewSet =======================================
    CLUSTERING_CONFIG_VIEWSET_STATUS = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
        view_set="ClusteringConfigViewSet",
        view_action="access_status",
    )
    CLUSTERING_CONFIG_VIEWSET_CONFIG = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
        view_set="ClusteringConfigViewSet",
        view_action="get_config",
    )
    PATTERN_VIEWSET_SEARCH = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="PatternViewSet", view_action="search"
    )
    # ======================================= 收藏-IndexSetViewSet =======================================
    INDEX_SET_VIEWSET_MARK_FAVORITE = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="IndexSetViewSet", view_action="mark_favorite"
    )
    INDEX_SET_VIEWSET_CANCEL_FAVORITE = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
        view_set="IndexSetViewSet",
        view_action="cancel_favorite",
    )
    # ======================================= 收藏-FavoriteViewSet =======================================
    FAVORITE_VIEWSET_RETRIEVE = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="FavoriteViewSet", view_action="retrieve"
    )
    FAVORITE_VIEWSET_LIST = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="FavoriteViewSet", view_action="list"
    )
    FAVORITE_VIEWSET_LIST_BY_GROUP = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="FavoriteViewSet", view_action="list_by_group"
    )
    FAVORITE_VIEWSET_CREATE = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="FavoriteViewSet", view_action="create"
    )
    FAVORITE_VIEWSET_UPDATE = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="FavoriteViewSet", view_action="update"
    )
    FAVORITE_VIEWSET_BATCH_UPDATE = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="FavoriteViewSet", view_action="batch_update"
    )
    FAVORITE_VIEWSET_DESTROY = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="FavoriteViewSet", view_action="destroy"
    )
    FAVORITE_VIEWSET_BATCH_DELETE = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="FavoriteViewSet", view_action="batch_delete"
    )
    FAVORITE_VIEWSET_GET_SEARCH_FIELDS = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
        view_set="FavoriteViewSet",
        view_action="get_search_fields",
        default_permission=True,
    )
    FAVORITE_VIEWSET_GENERATE_QUERY = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
        view_set="FavoriteViewSet",
        view_action="generate_query",
        default_permission=True,
    )
    FAVORITE_VIEWSET_INSPECT = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
        view_set="FavoriteViewSet",
        view_action="inspect",
        default_permission=True,
    )
    # ======================================= 收藏组-FavoriteGroupViewSet =======================================
    FAVORITE_GROUP_VIEWSET_LIST = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="FavoriteGroupViewSet", view_action="list"
    )
    FAVORITE_GROUP_VIEWSET_CREATE = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="FavoriteGroupViewSet", view_action="create"
    )
    FAVORITE_GROUP_VIEWSET_UPDATE = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="FavoriteGroupViewSet", view_action="update"
    )
    FAVORITE_GROUP_VIEWSET_DESTROY = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="FavoriteGroupViewSet", view_action="destroy"
    )
    # ======================================= IP选择器 =======================================
    # IpChooserConfigViewSet,IpChooserHostViewSet,IpChooserTemplateViewSet,IpChooserDynamicGroupViewSet
    IP_CHOOSER_TOPO_VIEWSET = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="IpChooserTopoViewSet"
    )
    IP_CHOOSER_HOST_VIEWSET = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="IpChooserHostViewSet"
    )
    IP_CHOOSER_TEMPLATE_VIEWSET = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="IpChooserTemplateViewSet"
    )
    IP_CHOOSER_DYNAMIC_GROUP_VIEWSET = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set="IpChooserDynamicGroupViewSet"
    )
    # IpChooserConfigViewSet, 默认允许
    IP_CHOOSER_CONFIG_VIEWSET = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
        view_set="IpChooserConfigViewSet",
        default_permission=True,
    )
    # ======================================= 收藏联合查询-FavoriteUnionSearchViewSet =======================================
    FAVORITE_UNION_SEARCH_VIEWSET_LIST = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_SEARCH.value,
        view_set="FavoriteUnionSearchViewSet",
        view_action="list",
    )
    # ======================================= BizsViewSet =======================================
    # BizsViewSet, get_display_name 默认允许
    BIZS_VIEWSET_HOST_DISPLAY_NAME = ViewSetAction(
        view_set="BizsViewSet", view_action="get_display_name", default_permission=True
    )
    # ======================================= 日志提取-ExplorerViewSet =======================================
    EXPLORER_VIEWSET = ViewSetAction(
        action_id=ExternalPermissionActionEnum.LOG_EXTRACT.value, view_set="ExplorerViewSet"
    )

    # ======================================= 日志提取-TaskViewSet =======================================
    TASKS_VIEWSET = ViewSetAction(action_id=ExternalPermissionActionEnum.LOG_EXTRACT.value, view_set="TasksViewSet")
    #  ======================================= META-MetaViewSet =======================================
    # MetaViewSet, LanguageViewSet，MenuViewSet，get_docs_link 默认允许
    META_VIEWSET = ViewSetAction(view_set="MetaViewSet", default_permission=True)
    LANGUAGE_VIEWSET = ViewSetAction(view_set="LanguageViewSet", default_permission=True)
    MENU_VIEWSET = ViewSetAction(view_set="MenuViewSet", default_permission=True)
    GET_DOCS_LINK = ViewSetAction(view_set="get_docs_link", default_permission=True)

    _choices_keys = (
        # ======================================= 检索-SearchViewSet =======================================
        SEARCH_VIEWSET_LIST,
        SEARCH_VIEWSET_BIZS,
        SEARCH_VIEWSET_SEARCH,
        SEARCH_VIEWSET_FIELDS,
        SEARCH_VIEWSET_CONTEXT,
        SEARCH_VIEWSET_TAILF,
        SEARCH_VIEWSET_EXPORT,
        SEARCH_VIEWSET_ASYNC_EXPORT,
        SEARCH_VIEWSET_HISTORY,
        SEARCH_VIEWSET_OPTION_HISTORY,
        SEARCH_VIEWSET_GET_EXPORT_HISTORY,
        SEARCH_VIEWSET_CONFIG,
        SEARCH_VIEWSET_CREATE_CONFIG,
        SEARCH_VIEWSET_UPDATE_CONFIG,
        SEARCH_VIEWSET_RETRIEVE_CONFIG,
        SEARCH_VIEWSET_LIST_CONFIG,
        SEARCH_VIEWSET_DELETE_CONFIG,
        # ======================================= 聚合-AggsViewSet =======================================
        AGGS_VIEWSET_TERMS,
        AGGS_VIEWSET_DATE_HISTOGRAM,
        # ======================================= 字段分析-FieldViewSet =======================================
        FIELD_VIEWSET_INFO,
        FIELD_VIEWSET_TOTAL,
        FIELD_VIEWSET_GRAPH,
        FIELD_VIEWSET_TOPK,
        # ======================================= 字段分析-FieldViewSet =======================================
        CLUSTERING_CONFIG_VIEWSET_STATUS,
        CLUSTERING_CONFIG_VIEWSET_CONFIG,
        PATTERN_VIEWSET_SEARCH,
        # ======================================= 收藏-IndexSetViewSet =======================================
        INDEX_SET_VIEWSET_MARK_FAVORITE,
        INDEX_SET_VIEWSET_CANCEL_FAVORITE,
        # ======================================= 收藏-FavoriteViewSet =======================================
        FAVORITE_VIEWSET_RETRIEVE,
        FAVORITE_VIEWSET_LIST,
        FAVORITE_VIEWSET_LIST_BY_GROUP,
        FAVORITE_VIEWSET_CREATE,
        FAVORITE_VIEWSET_UPDATE,
        FAVORITE_VIEWSET_BATCH_UPDATE,
        FAVORITE_VIEWSET_DESTROY,
        FAVORITE_VIEWSET_BATCH_DELETE,
        FAVORITE_VIEWSET_GET_SEARCH_FIELDS,
        FAVORITE_VIEWSET_GENERATE_QUERY,
        FAVORITE_VIEWSET_INSPECT,
        # ======================================= 收藏组-FavoriteGroupViewSet =======================================
        FAVORITE_GROUP_VIEWSET_LIST,
        FAVORITE_GROUP_VIEWSET_CREATE,
        FAVORITE_GROUP_VIEWSET_UPDATE,
        FAVORITE_GROUP_VIEWSET_DESTROY,
        # =================================== 收藏联合查询-FavoriteUnionSearchViewSet ==================================
        FAVORITE_UNION_SEARCH_VIEWSET_LIST,
        # ======================================= IP选择器 =======================================
        IP_CHOOSER_TOPO_VIEWSET,
        IP_CHOOSER_HOST_VIEWSET,
        IP_CHOOSER_TEMPLATE_VIEWSET,
        IP_CHOOSER_DYNAMIC_GROUP_VIEWSET,
        IP_CHOOSER_CONFIG_VIEWSET,
        # ======================================= 日志提取-TasksViewSet =======================================
        TASKS_VIEWSET,
        # ======================================= 日志提取-ExplorerViewSet =======================================
        EXPLORER_VIEWSET,
        # ======================================= BizsViewSet =======================================
        BIZS_VIEWSET_HOST_DISPLAY_NAME,
        # ======================================= META-MetaViewSet =======================================
        META_VIEWSET,
        LANGUAGE_VIEWSET,
        MENU_VIEWSET,
        GET_DOCS_LINK,
    )


# 与权限中心的action_id对应关系
ACTION_ID_MAP = {
    ExternalPermissionActionEnum.LOG_SEARCH.value: "search_log_v2",
    ExternalPermissionActionEnum.LOG_EXTRACT.value: "manage_extract_config_v2",
}

ITEM_EXTERNAL_PERMISSION_LOG_ASSESSMENT = _("日志平台外部用户授权")

# 一次性拉取的空间数量
BATCH_SYNC_SPACE_COUNT = 500
