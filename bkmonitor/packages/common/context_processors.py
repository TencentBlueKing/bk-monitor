"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import os
from typing import Any

from django.conf import settings
from django.utils.translation import get_language
from django.utils.translation import gettext as _

from bkm_space.api import SpaceApi
from bkm_space.define import Space
from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.utils import time_tools
from bkmonitor.utils.common_utils import fetch_biz_id_from_request, safe_int
from bkmonitor.utils.request import get_request_tenant_id
from common.log import logger
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api, resource
from core.errors.api import BKAPIError


class Platform:
    """
    平台信息
    """

    te = settings.BKAPP_DEPLOY_PLATFORM == "ieod"
    ee = settings.BKAPP_DEPLOY_PLATFORM == "enterprise"
    ce = settings.BKAPP_DEPLOY_PLATFORM == "community"

    @classmethod
    def to_dict(cls) -> dict[str, str]:
        return {"te": cls.te, "ee": cls.ee, "ce": cls.ce}


def get_default_biz_id(request, biz_list: list[dict[str, Any]] | None = None, id_key: str | None = None) -> int:
    if getattr(request, "biz_id", None):
        # 如果 request 存在业务缓存字段，优先返回
        biz_id = request.biz_id
    else:
        # 从请求参数中获取业务 ID
        biz_id = fetch_biz_id_from_request(request, {})

        # 优先级：参数(bk_biz_id) -> 参数(bizId) = Cookie(bk_biz_id) -> biz_list -> -1
        if not biz_id:
            # bizId 是前端业务选择器选中业务后会携带的参数
            # Cookie(bk_biz_id) 请求前端环境变量时，会 set：bkmonitor/packages/monitor_web/commons/context/views.py
            biz_id_or_none: str | None = request.session.get("bk_biz_id") or request.COOKIES.get("bk_biz_id")
            if biz_id_or_none:
                biz_id = safe_int(str(biz_id_or_none).strip("/"), dft=None)
            elif biz_list:
                sorted(biz_list, key=lambda biz: biz[id_key])
                biz_id = biz_list[0]["bk_biz_id"]
            else:
                biz_id = -1

    # 检查业务ID是否合法
    try:
        biz_id = int(biz_id)
    except (TypeError, ValueError):
        biz_id = -1

    return biz_id


def field_formatter(context: dict[str, Any]):
    # 字段大小写标准化
    standard_context = {
        key.upper(): context[key]
        for key in context
        if key
        in [
            "is_superuser",
            "uin",
        ]
    }
    context.update(standard_context)


def json_formatter(context: dict[str, Any]):
    # JSON 返回预处理
    context["PLATFORM"] = Platform.to_dict()
    context["LANGUAGES"] = dict(context["LANGUAGES"])

    for key in ["gettext", "_"]:
        context.pop(key, None)

    bool_context: dict[str, bool] = {}
    for key, value in context.items():
        if isinstance(value, str) and value in ["false", "False", "true", "True"]:
            bool_context[key] = True if value in {"True", "true"} else False

    context.update(bool_context)


def get_core_context(request):
    username = request.user.username
    try:
        user_time_zone = api.bk_login.get_user_info(id=username).get("time_zone", "")
    except Exception as e:
        logger.error(f"Get user {username} time zone failed: {e}")
        user_time_zone = ""

    return {
        # healthz 自监控引用
        "PLATFORM": Platform,
        "SITE_URL": settings.SITE_URL,
        # 静态资源
        "STATIC_URL": settings.STATIC_URL,
        # 当前页面，主要为了 login_required 做跳转用
        "APP_PATH": request.get_full_path(),
        "CSRF_COOKIE_NAME": settings.CSRF_COOKIE_NAME,
        # 默认开启APM
        "ENABLE_APM": "true",
        "ENABLE_APM_PROFILING": "true" if settings.APM_PROFILING_ENABLED else "false",
        "BK_JOB_URL": settings.JOB_URL,
        "BK_CC_URL": settings.BK_CC_URL,
        "BK_CI_URL": settings.BK_CI_URL,
        "BK_BCS_URL": settings.BK_BCS_HOST,
        # 蓝鲸平台URL
        "BK_URL": settings.BK_URL,
        "BK_PAAS_HOST": settings.BK_PAAS_HOST,
        # bkchat 用户管理接口
        "BKCHAT_MANAGE_URL": settings.BKCHAT_MANAGE_URL,
        "CE_URL": settings.CE_URL,
        "BKLOGSEARCH_HOST": settings.BKLOGSEARCH_HOST,
        "BK_NODEMAN_HOST": settings.BK_NODEMAN_HOST,
        # 用户管理站点（用于个人中心跳转等）
        "BK_USER_SITE_URL": settings.BK_USER_SITE_URL,
        "TAM_ID": settings.TAM_ID,
        # 用于切换中英文用户管理 cookie
        "BK_COMPONENT_API_URL": settings.BK_COMPONENT_API_URL_FRONTEND,
        "BK_DOMAIN": os.getenv("BK_DOMAIN", ""),
        # 登录跳转链接
        "LOGIN_URL": settings.LOGIN_URL,
        # 用于文档链接跳转
        "BK_DOCS_SITE_URL": settings.BK_DOCS_SITE_URL,
        # 国际化
        "gettext": _,
        "_": _,
        "USER_TIME_ZONE": user_time_zone,
        "LANGUAGE_CODE": request.LANGUAGE_CODE,
        "LANGUAGES": settings.LANGUAGES,
        # 页面title
        # todo 后续弃用(使用：全局配置资源链接）
        "PAGE_TITLE": (
            settings.HEADER_FOOTER_CONFIG["header"][0]["en"]
            if get_language() == "en"
            else settings.HEADER_FOOTER_CONFIG["header"][0]["zh-cn"]
        ),
        # 全局配置资源链接
        "BK_SHARED_RES_URL": settings.BK_SHARED_RES_URL,
        "FOOTER_VERSION": settings.VERSION,
    }


def get_basic_context(request, space_list: list[dict[str, Any]], bk_biz_id: int) -> dict[str, Any]:
    context: dict[str, Any] = get_core_context(request)
    context.update(
        {
            "uin": request.user.username,
            "is_superuser": str(request.user.is_superuser).lower(),
            "SPACE_LIST": space_list,
            "BK_BIZ_ID": bk_biz_id,
            "BK_TENANT_ID": get_request_tenant_id(peaceful=True) or DEFAULT_TENANT_ID,
            "ENABLE_MULTI_TENANT_MODE": settings.ENABLE_MULTI_TENANT_MODE,
            # 服务拨测设置最大 duration
            "MAX_AVAILABLE_DURATION_LIMIT": settings.MAX_AVAILABLE_DURATION_LIMIT,
            # 所有图表渲染必须
            "GRAPH_WATERMARK": settings.GRAPH_WATERMARK,
            # 是否开启前端视图部分，按拓扑聚合的能力。（不包含对监控策略部分的功能）
            "ENABLE_CMDB_LEVEL": settings.IS_ACCESS_BK_DATA and settings.IS_ENABLE_VIEW_CMDB_LEVEL,
            # 事件中心一键拉取功能展示
            "ENABLE_CREATE_CHAT_GROUP": settings.ENABLE_CREATE_CHAT_GROUP,
            # 用于全局设置蓝鲸监控机器人发送图片是否开启
            "WXWORK_BOT_SEND_IMAGE": settings.WXWORK_BOT_SEND_IMAGE,
            # 用于策略是否展示实时查询
            "SHOW_REALTIME_STRATEGY": settings.SHOW_REALTIME_STRATEGY,
            # APM 是否开启 EBPF 功能
            "APM_EBPF_ENABLED": "true" if settings.APM_EBPF_ENABLED else "false",
            # K8s v2 是否开启
            "K8S_V2_BIZ_LIST": settings.K8S_V2_BIZ_LIST,
            # 是否开启AI助手
            "ENABLE_AI_ASSISTANT": "true" if settings.AIDEV_API_BASE_URL else "false",
            # APM 日志转发接口 Url
            "APM_LOG_FORWARD_URL_PREFIX": "/apm_log_forward/bklog/",
            # 是否开启事件中心AIOps功能
            "ENABLE_AIOPS_EVENT_CENTER_BIZ_LIST": settings.ENABLE_AIOPS_EVENT_CENTER_BIZ_LIST,
            # 用户管理网关接口
            "BK_USER_WEB_API_URL": settings.BK_USER_WEB_API_URL,
        }
    )

    allow_biz_ids: set[int] = {space["bk_biz_id"] for space in space_list}
    # 为什么不直接调用接口检查？相比起 CPU 运算，接口请求耗时更不可控，考虑到大部分场景下 bk_biz_id in allow_biz_ids
    # 故利用该条件进行兼枝
    if bk_biz_id not in allow_biz_ids:
        try:
            SpaceApi.get_space_detail(bk_biz_id=bk_biz_id)
        except BKAPIError:
            try:
                # 空间不存在，有权限的业务里挑一个
                context["BK_BIZ_ID"] = space_list[0]["bk_biz_id"]
            except IndexError:
                # 什么权限都没有
                context["BK_BIZ_ID"] = -1

    # 用于主机详情渲染
    context["HOST_DATA_FIELDS"] = (
        ["bk_host_id"] if is_ipv6_biz(context["BK_BIZ_ID"]) else ["bk_target_ip", "bk_target_cloud_id"]
    )

    # 智能配置页面渲染
    context["ENABLE_AIOPS"] = "false"
    try:
        # 判断是否在白名单中
        if settings.IS_ACCESS_BK_DATA and (
            not settings.AIOPS_BIZ_WHITE_LIST
            or {-1, safe_int(context["BK_BIZ_ID"])} & set(settings.AIOPS_BIZ_WHITE_LIST)
        ):
            context["ENABLE_AIOPS"] = "true"
    except Exception as e:
        logger.error(f"Get AIOPS_BIZ_WHITE_LIST Failed: {e}")

    # 根因故障定位页面渲染
    context["ENABLE_AIOPS_INCIDENT"] = "false"
    try:
        # 判断是否在白名单中
        if settings.IS_ACCESS_BK_DATA and (
            not settings.AIOPS_INCIDENT_BIZ_WHITE_LIST
            or {-1, safe_int(context["BK_BIZ_ID"])} & set(settings.AIOPS_INCIDENT_BIZ_WHITE_LIST)
        ):
            context["ENABLE_AIOPS_INCIDENT"] = "true"
    except Exception as e:
        logger.error(f"Get AIOPS_INCIDENT_BIZ_WHITE_LIST Failed: {e}")

    # RUM功能
    if settings.RUM_ENABLED:
        context["RUM_ACCESS_URL"] = settings.RUM_ACCESS_URL

    return context


def get_extra_context(request, space: Space | None) -> dict[str, Any]:
    context = {
        # 首页跳转到文档配置页面需要
        "AGENT_SETUP_URL": settings.AGENT_SETUP_URL,
        # 用于导入导出配置
        "COLLECTING_CONFIG_FILE_MAXSIZE": settings.COLLECTING_CONFIG_FILE_MAXSIZE,
        # 用于仪表盘迁移
        "MIGRATE_GUIDE_URL": settings.MIGRATE_GUIDE_URL,
        # 用于 healthz 判断是否容器化部署
        "IS_CONTAINER_MODE": settings.IS_CONTAINER_MODE,
        # 用于新增空间是否展示其他
        "MONITOR_MANAGERS": settings.MONITOR_MANAGERS,
        "CLUSTER_SETUP_URL": f"{settings.BK_BCS_HOST.rstrip('/')}/bcs/",
        "BK_DOC_VERSION": settings.BK_DOC_VERSION,
    }

    # 用于新增容器空间地址
    if space and space.space_code:
        context["CLUSTER_SETUP_URL"] = f"{settings.BK_BCS_HOST.rstrip('/')}/bcs/{space.space_uid}/cluster"

    return context


def _get_full_monitor_context(request) -> dict[str, Any]:
    """
    渲染APP基础信息
    :param request:
    :return:
    """

    context: dict[str, Any] = {
        # 基础信息
        "RUN_MODE": settings.RUN_MODE,
        "APP_CODE": settings.APP_CODE,
        "SPACE_LIST": [],
        "STATIC_VERSION": settings.STATIC_VERSION,
        "BK_BCS_URL": settings.BK_BCS_HOST,
        # 当前页面，主要为了login_required做跳转用
        "APP_PATH": request.get_full_path(),
        "NOW": time_tools.localtime(time_tools.now()),
        "NICK": request.session.get("nick", ""),
        "AVATAR": request.session.get("avatar", ""),
        "MEDIA_URL": settings.MEDIA_URL,
        "REMOTE_STATIC_URL": settings.REMOTE_STATIC_URL,
        "WEIXIN_STATIC_URL": settings.WEIXIN_STATIC_URL,
        "WEIXIN_SITE_URL": settings.WEIXIN_SITE_URL,
        "RT_TABLE_PREFIX_VALUE": settings.RT_TABLE_PREFIX_VALUE,
        # "DOC_HOST": settings.DOC_HOST,
        # 首页跳转到文档配置页面需要
        "AGENT_SETUP_URL": settings.AGENT_SETUP_URL,
        # 用于仪表盘迁移
        "MIGRATE_GUIDE_URL": settings.MIGRATE_GUIDE_URL,
        # 用于导入导出配置
        "COLLECTING_CONFIG_FILE_MAXSIZE": settings.COLLECTING_CONFIG_FILE_MAXSIZE,
        # 用于 healthz 判断是否容器化部署
        "IS_CONTAINER_MODE": settings.IS_CONTAINER_MODE,
        # 用于新增空间是否展示其他
        "MONITOR_MANAGERS": settings.MONITOR_MANAGERS,
    }

    # 有权限的空间列表
    try:
        context["SPACE_LIST"] = resource.commons.list_spaces()
    except:  # noqa
        pass

    default_biz_id = get_default_biz_id(request, context["SPACE_LIST"], "id")

    context.update(get_basic_context(request, context["SPACE_LIST"], default_biz_id))

    # 用于新增容器空间地址
    context["CLUSTER_SETUP_URL"] = f"{settings.BK_BCS_HOST.rstrip('/')}/bcs/"
    for space in context["SPACE_LIST"]:
        if context["BK_BIZ_ID"] == space["bk_biz_id"] and space["space_code"]:
            context["CLUSTER_SETUP_URL"] = f"{settings.BK_BCS_HOST.rstrip('/')}/bcs/{space['space_id']}/cluster"

    field_formatter(context)
    return context


def _get_full_fta_context(request) -> dict[str, Any]:
    context: dict[str, Any] = _get_full_monitor_context(request)
    # context["SITE_URL"] = f'{context["SITE_URL"]}fta/'
    context["PAGE_TITLE"] = _("故障自愈 | 蓝鲸智云")
    return context


def get_full_context(request) -> dict[str, Any]:
    # 如果 old，仍走老路由
    if "fta" in request.get_full_path().split("/"):
        # 针对自愈的页面，进行特殊处理
        return _get_full_fta_context(request)
    else:
        return _get_full_monitor_context(request)


def get_fta_core_context(request) -> dict[str, Any]:
    context: dict[str, Any] = get_core_context(request)
    context["PAGE_TITLE"] = _("故障自愈 | 蓝鲸智云")
    return context


def get_weixin_core_context(request) -> dict[str, Any]:
    context: dict[str, Any] = get_core_context(request)
    context.update(
        {
            "WEIXIN_STATIC_URL": settings.WEIXIN_STATIC_URL,
            "WEIXIN_SITE_URL": settings.WEIXIN_SITE_URL,
            "UIN": request.user.username,
            "IS_SUPERUSER": str(request.user.is_superuser).lower(),
            "TAM_ID": settings.TAM_ID,
            # 所有图表渲染必须
            "GRAPH_WATERMARK": settings.GRAPH_WATERMARK,
            "BK_BIZ_ID": get_default_biz_id(request),
        }
    )
    return context


def get_context(request) -> dict[str, Any]:
    try:
        # 背景：原来的 context 集成了全量业务列表拉取、用户有权限业务拉取，导致首屏打开耗时较长
        # 改造：前端仅拉取基础 context，待页面初始化后再拉取剩余 context
        req_path: str = request.get_full_path().split("/")
        if "fta" in req_path:
            return get_fta_core_context(request)
        elif "weixin" in req_path:
            return get_weixin_core_context(request)
        else:
            return get_core_context(request)
    except Exception as e:
        logger.exception(f"get_context error: {e}")
        raise e
