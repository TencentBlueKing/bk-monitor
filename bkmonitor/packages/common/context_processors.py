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

from django.conf import settings
from django.utils.translation import get_language
from django.utils.translation import ugettext as _

from bkmonitor.commons.tools import is_ipv6_biz
from bkmonitor.utils import time_tools
from bkmonitor.utils.common_utils import fetch_biz_id_from_request, safe_int
from common.log import logger
from core.drf_resource import resource


class Platform(object):
    """
    平台信息
    """

    te = settings.BKAPP_DEPLOY_PLATFORM == "ieod"
    ee = settings.BKAPP_DEPLOY_PLATFORM == "enterprise"
    ce = settings.BKAPP_DEPLOY_PLATFORM == "community"


def _get_monitor_context(request):
    """
    渲染APP基础信息
    :param request:
    :return:
    """

    context = {
        # 基础信息
        "RUN_MODE": settings.RUN_MODE,
        "APP_CODE": settings.APP_CODE,
        "SITE_URL": settings.SITE_URL,
        "BK_PAAS_HOST": settings.BK_PAAS_HOST,
        "BK_CC_URL": settings.BK_CC_URL,
        "BK_JOB_URL": settings.JOB_URL,
        "BK_BCS_URL": settings.BK_BCS_HOST,
        "BKLOGSEARCH_HOST": settings.BKLOGSEARCH_HOST,
        "BK_NODEMAN_HOST": settings.BK_NODEMAN_HOST,
        "GRAPH_WATERMARK": settings.GRAPH_WATERMARK,
        "MAIL_REPORT_BIZ": int(settings.MAIL_REPORT_BIZ),
        # 静态资源
        "STATIC_URL": settings.STATIC_URL,
        "STATIC_VERSION": settings.STATIC_VERSION,
        # 登录跳转链接
        "LOGIN_URL": settings.LOGIN_URL,
        # 当前页面，主要为了login_required做跳转用
        "APP_PATH": request.get_full_path(),
        "NOW": time_tools.localtime(time_tools.now()),
        "NICK": request.session.get("nick", ""),  # 用户昵称
        "AVATAR": request.session.get("avatar", ""),
        "MEDIA_URL": settings.MEDIA_URL,  # MEDIA_URL
        "BK_URL": settings.BK_URL,  # 蓝鲸平台URL
        "gettext": _,  # 国际化
        "_": _,  # 国际化
        "LANGUAGE_CODE": request.LANGUAGE_CODE,  # 国际化
        "LANGUAGES": settings.LANGUAGES,  # 国际化
        "REMOTE_STATIC_URL": settings.REMOTE_STATIC_URL,
        "WEIXIN_STATIC_URL": settings.WEIXIN_STATIC_URL,
        "WEIXIN_SITE_URL": settings.WEIXIN_SITE_URL,
        "RT_TABLE_PREFIX_VALUE": settings.RT_TABLE_PREFIX_VALUE,
        "uin": request.user.username,
        "is_superuser": str(request.user.is_superuser).lower(),
        "CSRF_COOKIE_NAME": settings.CSRF_COOKIE_NAME,
        "PLATFORM": Platform,
        "DOC_HOST": settings.DOC_HOST,
        "BK_DOCS_SITE_URL": settings.BK_DOCS_SITE_URL,
        "MIGRATE_GUIDE_URL": settings.MIGRATE_GUIDE_URL,
        "AGENT_SETUP_URL": settings.AGENT_SETUP_URL,
        "UTC_OFFSET": time_tools.utcoffset_in_seconds() // 60,
        "ENABLE_MESSAGE_QUEUE": "true" if settings.MESSAGE_QUEUE_DSN else "false",
        "MESSAGE_QUEUE_DSN": settings.MESSAGE_QUEUE_DSN,
        "CE_URL": settings.CE_URL,
        # 拨测前端校验参数
        "MAX_AVAILABLE_DURATION_LIMIT": settings.MAX_AVAILABLE_DURATION_LIMIT,
        "ENABLE_GRAFANA": bool(settings.GRAFANA_URL),
        # 页面title
        "PAGE_TITLE": (
            settings.HEADER_FOOTER_CONFIG["header"][0]["en"]
            if get_language() == "en"
            else settings.HEADER_FOOTER_CONFIG["header"][0]["zh-cn"]
        ),
        "TAM_ID": settings.TAM_ID,
        "COLLECTING_CONFIG_FILE_MAXSIZE": settings.COLLECTING_CONFIG_FILE_MAXSIZE,
        "ENABLE_CREATE_CHAT_GROUP": settings.ENABLE_CREATE_CHAT_GROUP,
        "IS_CONTAINER_MODE": settings.IS_CONTAINER_MODE,
        "UPTIMECHECK_OUTPUT_FIELDS": settings.UPTIMECHECK_OUTPUT_FIELDS,
        "WXWORK_BOT_SEND_IMAGE": settings.WXWORK_BOT_SEND_IMAGE,
        "BK_COMPONENT_API_URL": settings.BK_COMPONENT_API_URL_FRONTEND,
        "BK_DOMAIN": os.getenv("BK_DOMAIN", ""),
        "SHOW_REALTIME_STRATEGY": settings.SHOW_REALTIME_STRATEGY,
        # bkchat 用户管理接口
        "BKCHAT_MANAGE_URL": settings.BKCHAT_MANAGE_URL,
        # APM是否开启EBPF功能
        "APM_EBPF_ENABLED": "true" if settings.APM_EBPF_ENABLED else "false",
    }

    # 字段大小写标准化
    standard_context = {
        key.upper(): context[key]
        for key in context
        if key
        in [
            "APP_CODE",
            "SITE_URL",
            "STATIC_URL",
            "DOC_HOST",
            "BK_DOCS_SITE_URL",
            "MIGRATE_GUIDE_URL",
            "BK_JOB_URL",
            "CSRF_COOKIE_NAME",
            "UTC_OFFSET",
            "is_superuser",
            "STATIC_VERSION",
            "AGENT_SETUP_URL",
            "RT_TABLE_PREFIX_VALUE",
            "NICK",
            "uin",
            "AVATAR",
            "APP_PATH",
            "BK_URL",
        ]
    }

    context.update(standard_context)

    # 格式化业务列表并排序
    try:
        context["BK_BIZ_LIST"] = [
            {"id": biz.bk_biz_id, "text": biz.display_name, "is_demo": biz.bk_biz_id == int(settings.DEMO_BIZ_ID)}
            for biz in resource.cc.get_app_by_user(request.user)
        ]
    except:  # noqa
        context["BK_BIZ_LIST"] = []
    context["BK_BIZ_LIST"].sort(key=lambda biz: biz["id"])
    if hasattr(request, "biz_id"):
        context["BK_BIZ_ID"] = request.biz_id
    else:
        biz_id = fetch_biz_id_from_request(request, {})
        if biz_id:
            context["BK_BIZ_ID"] = biz_id
        elif context["BK_BIZ_LIST"]:
            context["BK_BIZ_ID"] = context["BK_BIZ_LIST"][0]["id"]
        else:
            context["BK_BIZ_ID"] = -1

    # 检查业务ID是否合法
    try:
        context["BK_BIZ_ID"] = int(context["BK_BIZ_ID"])
    except (TypeError, ValueError):
        context["BK_BIZ_ID"] = -1

    # 是否开启前端视图部分，按拓扑聚合的能力。（不包含对监控策略部分的功能）
    context["ENABLE_CMDB_LEVEL"] = settings.IS_ACCESS_BK_DATA and settings.IS_ENABLE_VIEW_CMDB_LEVEL
    # 当前业务是否在AIOPS白名单中
    context["ENABLE_AIOPS"] = "false"
    try:
        if settings.IS_ACCESS_BK_DATA and (
            not settings.AIOPS_BIZ_WHITE_LIST
            or {-1, safe_int(context["BK_BIZ_ID"])} & set(settings.AIOPS_BIZ_WHITE_LIST)
        ):
            context["ENABLE_AIOPS"] = "true"
    except Exception as e:
        logger.error(f"Get AIOPS_BIZ_WHITE_LIST Failed: {e}")

    # 默认开启APM
    context["ENABLE_APM"] = "true"
    context["ENABLE_APM_PROFILING"] = "true" if settings.APM_PROFILING_ENABLED else "false"
    # 有权限的空间列表
    context["SPACE_LIST"] = []
    try:
        context["SPACE_LIST"] = resource.commons.list_spaces()
    except:  # noqa
        pass

    context["SPACE_INTRODUCE"] = {}
    context["MONITOR_MANAGERS"] = settings.MONITOR_MANAGERS
    context["CLUSTER_SETUP_URL"] = f"{settings.BK_BCS_HOST.rstrip('/')}/bcs/"
    for space in context["SPACE_LIST"]:
        if context["BK_BIZ_ID"] == space["bk_biz_id"] and space["space_code"]:
            context["CLUSTER_SETUP_URL"] = f"{settings.BK_BCS_HOST.rstrip('/')}/bcs/{space['space_id']}/cluster"
    context["HOST_DATA_FIELDS"] = (
        ["bk_host_id"] if is_ipv6_biz(context["BK_BIZ_ID"]) else ["bk_target_ip", "bk_target_cloud_id"]
    )
    return context


def _get_fta_context(request):
    context = _get_monitor_context(request)
    # context["SITE_URL"] = f'{context["SITE_URL"]}fta/'
    context["PAGE_TITLE"] = _("故障自愈 | 蓝鲸智云")
    return context


def get_context(request):
    try:
        if "fta" in request.get_full_path().split("/"):
            # 针对自愈的页面，进行特殊处理
            return _get_fta_context(request)
        else:
            return _get_monitor_context(request)
    except Exception as e:
        logger.exception(f"get_context error: {e}")
        raise e
