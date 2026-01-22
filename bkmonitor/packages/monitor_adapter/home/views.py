"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import json
from urllib import parse
from urllib.parse import urlsplit

from blueapps.account import ConfFixture
from blueapps.account.decorators import login_exempt
from blueapps.account.handlers.response import ResponseHandler
from django.conf import settings
from django.contrib import auth
from django.contrib.auth import logout
from django.http import HttpResponseForbidden, HttpResponseNotFound, JsonResponse
from django.shortcuts import redirect, render
from django.test import RequestFactory
from django.urls import Resolver404, resolve
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkm_space.api import SpaceApi
from bkmonitor.models.external_iam import ExternalPermission
from bkmonitor.utils.common_utils import safe_int
from bkmonitor.utils.local import local
from common.decorators import timezone_exempt, track_site_visit
from common.log import logger
from constants.alert import AlertRedirectType
from constants.common import DEFAULT_TENANT_ID
from core.errors.api import BKAPIError
from monitor.models import GlobalConfig
from monitor_adapter.home.alert_redirect import (
    generate_apm_rpc_url,
    generate_apm_trace_url,
    generate_data_retrieval_url,
    generate_event_explore_url,
    generate_log_search_url,
)
from monitor_web.iam.resources import CallbackResource
from packages.monitor_web.new_report.resources import ReportCallbackResource


def user_exit(request):
    def add_logout_slug():
        return {"is_from_logout": "1"}

    # 退出登录
    logout(request)
    # 验证不通过，需要跳转至统一登录平台
    request.path = request.path.replace("logout", "")
    handler = ResponseHandler(ConfFixture, settings)
    handler._build_extra_args = add_logout_slug
    return handler.build_401_response(request)


@login_exempt
@timezone_exempt
@track_site_visit
def home(request):
    """统一入口 ."""

    response = render(request, "monitor/index.html", {"cc_biz_id": 0})
    return response


def event_center_proxy(request):
    rio_url = "/weixin/?bizId={bk_biz_id}&collectId={collect_id}"
    pc_url = "/?bizId={bk_biz_id}&routeHash=event-center/?collectId={collect_id}"
    collect_id = request.GET.get("collectId")
    bk_biz_id = request.GET.get("bizId")
    proxy_type = request.GET.get("type", "event")
    batch_action = request.GET.get("batchAction")
    if not (collect_id and bk_biz_id):
        return HttpResponseNotFound(_("无效的告警事件链接"))

    if not request.is_mobile():
        generate_url_func_map = {
            # 指标检索
            AlertRedirectType.QUERY.value: generate_data_retrieval_url,
            # 日志检索
            AlertRedirectType.LOG_SEARCH.value: generate_log_search_url,
            # 调用分析
            AlertRedirectType.APM_RPC.value: generate_apm_rpc_url,
            # Tracing 检索
            AlertRedirectType.APM_TRACE.value: generate_apm_trace_url,
            # 事件检索
            AlertRedirectType.EVENT_EXPLORE.value: generate_event_explore_url,
        }
        # 根据跳转类型获取对应的 URL 生成函数，生成跳转链接并返回重定向响应
        if (generate_url_func := generate_url_func_map.get(proxy_type)) and (
            explore_url := generate_url_func(bk_biz_id, collect_id)
        ):
            return redirect(explore_url)

    redirect_url = rio_url if request.is_mobile() else pc_url
    if batch_action:
        redirect_url = f"{redirect_url}&batchAction={batch_action}"
    return redirect(redirect_url.format(bk_biz_id=bk_biz_id, collect_id=collect_id))


def path_route_proxy(request):
    route_path = base64.b64decode(request.GET.get("route_path", "")).decode("utf8")
    bk_biz_id = request.GET.get("bizId")
    redirect_url = "/?bizId={bk_biz_id}{route_path}"
    return redirect(redirect_url.format(bk_biz_id=bk_biz_id, route_path=route_path))


@timezone_exempt
def service_worker(request):
    return render(request, "monitor/service-worker.js", content_type="application/javascript")


@login_exempt
@timezone_exempt
def manifest(request):
    return render(request, "monitor/manifest.json", content_type="application/json")


@login_exempt
def external(request):
    """外部监控入口 ."""
    cc_biz_id = 0
    external_user = request.META.get("HTTP_USER", "") or request.META.get("USER", "")
    biz_id_list = (
        ExternalPermission.objects.filter(authorized_user=external_user, expire_time__gt=timezone.now())
        .values_list("bk_biz_id", flat=True)
        .distinct()
    )
    # 新增space_uid的支持
    if request.GET.get("space_uid", None):
        try:
            space = SpaceApi.get_space_detail(request.GET["space_uid"])
            cc_biz_id = space.bk_biz_id
        except BKAPIError as e:
            logger.exception(f"获取空间信息({request.GET['space_uid']})失败：{e}")
    else:
        cc_biz_id = request.GET.get("bizId") or request.session.get("bk_biz_id") or request.COOKIES.get("bk_biz_id")
        if not cc_biz_id:
            if biz_id_list:
                cc_biz_id = biz_id_list[0]
            else:
                logger.error(f"外部用户{external_user}无任何业务访问权限")
                return HttpResponseForbidden(f"外部用户{external_user}无任何业务访问权限")
        else:
            cc_biz_id = safe_int(cc_biz_id.strip("/"), dft=None)

    request.biz_id = cc_biz_id
    if request.biz_id and external_user:
        qs = ExternalPermission.objects.filter(
            authorized_user=external_user, bk_biz_id=request.biz_id, expire_time__gt=timezone.now()
        )
        if not qs:
            logger.error(f"外部用户{external_user}无访问权限(业务id: {request.biz_id})")
            return HttpResponseForbidden(f"外部用户{external_user}无访问权限(业务id: {request.biz_id})")
        authorizer_map, _ = GlobalConfig.objects.get_or_create(key="EXTERNAL_AUTHORIZER_MAP", defaults={"value": {}})
        if not authorizer_map.value.get(str(request.biz_id)):
            logger.error(f"业务{request.biz_id}无对应授权人")
            return HttpResponseForbidden(f"业务{request.biz_id}无对应授权人")
        user = auth.authenticate(username=authorizer_map.value[str(request.biz_id)], tenant_id=DEFAULT_TENANT_ID)
        auth.login(request, user)
        setattr(request, "COOKIES", {k: v for k, v in request.COOKIES.items() if k != "bk_token"})
    else:
        logger.error(f"外部用户({external_user})或业务id({request.biz_id})不存在, request.META: {request.META}")
    response = render(
        request,
        "external/index.html",
        {"cc_biz_id": cc_biz_id, "external_user": external_user, "BK_BIZ_IDS": list(biz_id_list)},
    )
    response.set_cookie("bk_biz_id", str(cc_biz_id))
    return response


@login_exempt
@method_decorator(csrf_exempt)
@require_POST
def dispatch_external_proxy(request):
    """
    转发外部监控渲染资源请求，暂时仅考虑GET/POST请求
    body = {
        "url": 被转发资源请求url, 比如：/rest/v2/grafana/dashboards/?bk_biz_id=2
        "method": 'GET|POST',
        "data": data, POST请求的数据
    }
    """

    try:
        params = json.loads(request.body)
    except Exception:
        return JsonResponse({"result": False, "message": "invalid json format"}, status=400)

    # proxy: url/method/data
    url = params.get("url")
    method = params.get("method", "GET")
    json_data = params.get("data", {})

    try:
        parsed = urlsplit(url)

        if method.lower() == "get":
            fake_request = RequestFactory().get(url, content_type="application/json")
            params_dict = dict(parse.parse_qsl(parse.urlparse(url).query))
            bk_biz_id = params_dict.get("bk_biz_id", None)
        elif method.lower() == "post":
            fake_request = RequestFactory().post(url, data=json_data, content_type="application/json")
            data = json.loads(json_data)
            bk_biz_id = data.get("bk_biz_id", None)
        else:
            return JsonResponse(
                {"result": False, "message": "dispatch_plugin_query: only support get and post method."}, status=400
            )

        # transfer request.user 进行外部权限替换
        external_user = request.META.get("HTTP_USER", "") or request.META.get("USER", "")

        # 如果参数不带 bk_biz_id，尝试从有权限的业务列表里选一个
        if not bk_biz_id:
            biz_id_list = (
                ExternalPermission.objects.filter(authorized_user=external_user, expire_time__gt=timezone.now())
                .values_list("bk_biz_id", flat=True)
                .distinct()
            )
            if biz_id_list:
                bk_biz_id = biz_id_list[0]

        if bk_biz_id:
            setattr(fake_request, "biz_id", bk_biz_id)
            setattr(request, "biz_id", bk_biz_id)
            authorizer_map, _ = GlobalConfig.objects.get_or_create(
                key="EXTERNAL_AUTHORIZER_MAP", defaults={"value": {}}
            )
            user = auth.authenticate(username=authorizer_map.value[str(bk_biz_id)], tenant_id=DEFAULT_TENANT_ID)
            auth.login(request, user)
            setattr(fake_request, "user", request.user)
        logger.info(
            f"dispatch_plugin_query: request:{request}, user:{request.user},"
            f" external_user: {external_user}, bk_biz_id: {bk_biz_id}"
        )
        # 处理grafana接口请求头，TC适配腾讯云数据源，DS适配数据源鉴权参数
        meta_prefixs = ["HTTP_X_TC", "HTTP_X_DS", "HTTP_X_GRAFANA"]
        for key, value in request.META.items():
            key = key.upper()
            if any(key.startswith(prefix) for prefix in meta_prefixs):
                fake_request.META[key] = value

        # 绕过csrf鉴权
        setattr(fake_request, "csrf_processing_done", True)
        setattr(request, "csrf_processing_done", True)
        # 请求携带外部标识
        setattr(fake_request, "external_user", external_user)
        setattr(request, "external_user", external_user)
        setattr(fake_request, "session", request.session)
        # use in get_core_context
        setattr(fake_request, "LANGUAGE_CODE", request.LANGUAGE_CODE)
        setattr(local, "current_request", fake_request)

        # resolve view_func
        match = resolve(parsed.path, urlconf=None)
        view_func, kwargs = match.func, match.kwargs

        # call view_func
        return view_func(fake_request, **kwargs)

    except Resolver404:
        logger.warning(f"dispatch_plugin_query: resolve view func 404 for: {url}")
        return JsonResponse(
            {"result": False, "message": f"dispatch_plugin_query: resolve view func 404 for: {url}"}, status=404
        )

    except Exception as e:
        logger.exception(f"dispatch_plugin_query: exception for {e}")
        raise e


@login_exempt
@method_decorator(csrf_exempt)
@require_POST
def external_callback(request):
    try:
        params = json.loads(request.body)
    except Exception:
        return JsonResponse({"result": False, "message": "invalid json format"}, status=400)

    logger.info(
        "[{}]: dispatch_grafana with header({}) and params({})".format("external_callback", request.META, params)
    )
    result = CallbackResource().perform_request(params)
    if result["result"]:
        return JsonResponse(result, status=200)


@login_exempt
@method_decorator(csrf_exempt)
@require_POST
def report_callback(request):
    try:
        params = json.loads(request.body)
    except Exception:  # pylint: disable=broad-except
        return JsonResponse({"result": False, "message": "invalid json format"}, status=400)

    result = ReportCallbackResource().perform_request(params)
    if result["result"]:
        return JsonResponse(result, status=200)
