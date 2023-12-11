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
from django.utils.translation import ugettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bkm_space.api import SpaceApi
from bkmonitor.models import ActionConfig
from bkmonitor.models.external_iam import ExternalPermission
from bkmonitor.utils.common_utils import safe_int
from bkmonitor.utils.local import local
from common.log import logger
from core.drf_resource import resource
from core.errors.api import BKAPIError
from fta_web.tasks import run_init_builtin_action_config
from monitor.models import GlobalConfig
from monitor_web.iam.resources import CallbackResource
from monitor_web.strategies.built_in import run_build_in


def user_exit(request):
    logout(request)
    # 验证不通过，需要跳转至统一登录平台
    request.path = request.path.replace("logout", "")
    handler = ResponseHandler(ConfFixture, settings)
    return handler.build_401_response(request)


def home(request):
    """统一入口 ."""
    cc_biz_id = 0
    # 新增space_uid的支持
    if request.GET.get("space_uid", None):
        try:
            space = SpaceApi.get_space_detail(request.GET["space_uid"])
            cc_biz_id = space.bk_biz_id
        except BKAPIError as e:
            logger.exception(f"获取空间信息({request.GET['space_uid']})失败：{e}")
            if settings.DEMO_BIZ_ID:
                cc_biz_id = settings.DEMO_BIZ_ID
    else:
        cc_biz_id = request.GET.get("bizId") or request.session.get("bk_biz_id") or request.COOKIES.get("bk_biz_id")
        if not cc_biz_id:
            biz_id_list = [s["bk_biz_id"] for s in resource.commons.list_spaces()]
            if biz_id_list:
                cc_biz_id = biz_id_list[0]
        else:
            cc_biz_id = safe_int(cc_biz_id.strip("/"), dft=None)

    if cc_biz_id is not None and settings.ENVIRONMENT != "development":
        # 创建默认内置策略
        run_build_in(int(cc_biz_id))

        # 创建k8s内置策略
        run_build_in(int(cc_biz_id), mode="k8s")
        if (
            settings.ENABLE_DEFAULT_STRATEGY
            and int(cc_biz_id) > 0
            and not ActionConfig.origin_objects.filter(bk_biz_id=cc_biz_id, is_builtin=True).exists()
        ):
            logger.warning("home run_init_builtin_action_config")
            # 如果当前页面没有出现内置套餐，则会进行快捷套餐的初始化
            try:
                run_init_builtin_action_config.delay(cc_biz_id)
            except Exception as error:
                # 直接忽略
                logger.exception("run_init_builtin_action_config failed ", str(error))
        # TODO 先关闭，后面稳定了直接打开
        # if not AlertAssignGroup.origin_objects.filter(bk_biz_id=cc_biz_id, is_builtin=True).exists():
        #     # 如果当前页面没有出现内置的规则组
        #     run_init_builtin_assign_group(cc_biz_id)

    request.biz_id = cc_biz_id
    response = render(request, "monitor/index.html", {"cc_biz_id": cc_biz_id})
    response.set_cookie("bk_biz_id", str(cc_biz_id))
    return response


def event_center_proxy(request):
    rio_url = "/weixin/?bizId={bk_biz_id}&collectId={collect_id}"
    pc_url = "/?bizId={bk_biz_id}&routeHash=event-center/?collectId={collect_id}"
    collect_id = request.GET.get("collectId")
    bk_biz_id = request.GET.get("bizId")
    batch_action = request.GET.get("batchAction")
    if not (collect_id and bk_biz_id):
        return HttpResponseNotFound(_("无效的告警事件链接"))
    redirect_url = rio_url if request.is_mobile() else pc_url
    if batch_action:
        redirect_url = f"{redirect_url}&batchAction={batch_action}"
    return redirect(redirect_url.format(bk_biz_id=bk_biz_id, collect_id=collect_id))


def path_route_proxy(request):
    route_path = base64.b64decode(request.GET.get("route_path", "")).decode("utf8")
    bk_biz_id = request.GET.get("bizId")
    redirect_url = "/?bizId={bk_biz_id}{route_path}"
    return redirect(redirect_url.format(bk_biz_id=bk_biz_id, route_path=route_path))


def service_worker(request):
    return render(request, "monitor/service-worker.js", content_type="application/javascript")


def manifest(request):
    return render(request, "monitor/manifest.json", content_type="application/json")


@login_exempt
def external(request):
    """外部监控入口 ."""
    cc_biz_id = 0
    external_user = request.META.get("HTTP_USER", "") or request.META.get("USER", "")
    biz_id_list = (
        ExternalPermission.objects.filter(authorized_user=external_user, expire_time__gt=timezone.now())
        .values_list("bk_biz_id", flat=1)
        .distinct()
    )
    # 新增space_uid的支持
    if request.GET.get("space_uid", None):
        try:
            space = SpaceApi.get_space_detail(request.GET["space_uid"])
            cc_biz_id = space.bk_biz_id
        except BKAPIError as e:
            logger.exception(f"获取空间信息({request.GET['space_uid']})失败：{e}")
            if settings.DEMO_BIZ_ID:
                cc_biz_id = settings.DEMO_BIZ_ID
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
        user = auth.authenticate(username=authorizer_map.value[str(request.biz_id)])
        auth.login(request, user)
        setattr(request, "COOKIES", {k: v for k, v in request.COOKIES.items() if k != "bk_token"})
    else:
        logger.error(f"外部用户({external_user})或业务id({request.biz_id})不存在, request.META: {request.META}")
    response = render(
        request,
        "external/index.html",
        {
            "cc_biz_id": cc_biz_id,
            "SPACE_LIST": [s for s in SpaceApi.list_spaces() if s.bk_biz_id in biz_id_list],
            "external_user": external_user,
        },
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
        if bk_biz_id:
            setattr(fake_request, "biz_id", bk_biz_id)
            setattr(request, "biz_id", bk_biz_id)
            authorizer_map, _ = GlobalConfig.objects.get_or_create(
                key="EXTERNAL_AUTHORIZER_MAP", defaults={"value": {}}
            )
            user = auth.authenticate(username=authorizer_map.value[str(bk_biz_id)])
            auth.login(request, user)
            setattr(fake_request, "user", request.user)
        logger.info(
            f"dispatch_plugin_query: request:{request}, user:{request.user},"
            f" external_user: {external_user}, bk_biz_id: {bk_biz_id}"
        )
        # 处理grafana接口请求头携带组织ID
        if request.META.get("HTTP_X_GRAFANA_ORG_ID"):
            fake_request.META["HTTP_X_GRAFANA_ORG_ID"] = request.META["HTTP_X_GRAFANA_ORG_ID"]
        # 绕过csrf鉴权
        setattr(fake_request, "csrf_processing_done", True)
        setattr(request, "csrf_processing_done", True)
        # 请求携带外部标识
        setattr(fake_request, "external_user", external_user)
        setattr(request, "external_user", external_user)
        setattr(fake_request, "session", request.session)
        setattr(local, "current_request", fake_request)

        # resolve view_func
        match = resolve(parsed.path, urlconf=None)
        view_func, kwargs = match.func, match.kwargs

        # call view_func
        return view_func(fake_request, **kwargs)

    except Resolver404:
        logger.warning("dispatch_plugin_query: resolve view func 404 for: {}".format(url))
        return JsonResponse(
            {"result": False, "message": "dispatch_plugin_query: resolve view func 404 for: {}".format(url)}, status=404
        )

    except Exception as e:
        logger.exception("dispatch_plugin_query: exception for {}".format(e))
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
