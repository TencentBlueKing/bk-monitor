"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.contrib import auth
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.test import RequestFactory
from django.urls import Resolver404, resolve
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.fields import BooleanField
from rest_framework.response import Response

from apps.constants import ExternalPermissionActionEnum, ViewSetAction, ViewSetActionEnum
from apps.iam import ActionEnum
from apps.log_audit.external import ExternalAuditRecorder, resolve_exception_status_code
from apps.log_commons.external_auth import (
    ExternalRequestContext,
    IdentityContext,
    authorize,
    has_space_access,
    list_authorized_space_actions,
    list_authorized_space_uids,
    resolve_declared_action_id,
)
from apps.log_commons.models import AuthorizerSettings, ExternalPermissionApplyRecord
from apps.utils.db import get_toggle_data
from apps.utils.local import set_local_param
from apps.utils.log import logger
from bkm_space.api import SpaceApi
from bkm_space.utils import bk_biz_id_to_space_uid


class RequestProcessor:
    """
    请求处理器
    """

    @classmethod
    def get_space_uid(cls, request) -> str:
        """
        获取空间ID
        """
        try:
            params = json.loads(request.body)
        except json.decoder.JSONDecodeError:
            return ""
        # 先从external_proxy参数中获取
        if params.get("space_uid"):
            return params.get("space_uid")
        url: str = params.get("url")
        # 这里是字符串
        json_data_str: str = params.get("data", "")
        parsed = urlsplit(url)
        query_string = parsed.query
        # 使用parse_qs解析查询参数
        kwargs = parse_qs(query_string)
        # 从URL中获取
        if "space_uid" in kwargs:
            return kwargs["space_uid"][0]
        if "bk_biz_id" in kwargs:
            return bk_biz_id_to_space_uid(kwargs["bk_biz_id"][0])
        # 从请求参数中获取
        try:
            json_data = json.loads(json_data_str)
            if "space_uid" in json_data:
                return json_data["space_uid"]
            if "bk_biz_id" in json_data:
                return bk_biz_id_to_space_uid(json_data["bk_biz_id"])
        except json.decoder.JSONDecodeError:
            return ""
        return ""

    @classmethod
    def copy_request_to_fake_request(cls, request, fake_request):
        """
        复制请求内容到fake_request
        """
        request_meta = getattr(request, "META", {})
        fake_request_meta = getattr(fake_request, "META", {})
        if request_meta.get("HTTP_X_BK_APP_CODE", ""):
            request_meta["HTTP_BK_APP_CODE"] = request_meta["HTTP_X_BK_APP_CODE"]
            fake_request_meta["HTTP_BK_APP_CODE"] = request_meta["HTTP_X_BK_APP_CODE"]
            setattr(request, "META", request_meta)
            setattr(fake_request, "META", fake_request_meta)
        return fake_request

    @classmethod
    def get_request_user_info(cls, request) -> dict[str, Any]:
        external_user = request.META.get("HTTP_USER", "") or request.META.get("USER", "")
        try:
            external_user = json.loads(external_user)
        except json.decoder.JSONDecodeError:
            logger.error(f"解析外部用户信息失败({external_user})")
            external_user = {"username": external_user}
        return external_user

    @classmethod
    def get_view_set(cls, view_func):
        """获取view_func对应的viewset名称, 如果是viewset则返回viewset名称, 否则返回view_func名称"""
        if hasattr(view_func, "cls"):
            return view_func.cls.__name__
        return view_func.__name__

    @classmethod
    def get_view_action(cls, view_func, method):
        """获取view_func对应的action名称"""
        if hasattr(view_func, "actions"):
            return view_func.actions.get(method, "")
        return ""

    @classmethod
    def filter_response_resource(
        cls,
        external_user: str,
        response: Response,
        action_id: str,
        view_set: str,
        view_action: str,
        allow_resources_result: dict[str, Any],
    ):
        """
        过滤接口返回中的资源
        :param external_user: 外部用户
        :param response: 原始响应
        :param action_id: action_id, ActionEnum
        :param view_set: view_func对应的viewset名称
        :param view_action: view_func对应的action名称
        :param allow_resources_result: 允许访问的资源
        """
        if not allow_resources_result["allowed"]:
            return response
        if action_id == ExternalPermissionActionEnum.LOG_SEARCH.value:
            return cls.filter_log_search_response_resource(
                response=response,
                action_id=action_id,
                view_set=view_set,
                view_action=view_action,
                allow_resources_result=allow_resources_result,
            )

        return response

    @classmethod
    def filter_log_search_response_resource(
        cls, response: Response, action_id: str, view_set: str, view_action: str, allow_resources_result: dict[str, Any]
    ):
        allow_resources = allow_resources_result["resources"]
        view_set_class: ViewSetAction = ViewSetAction(action_id=action_id, view_set=view_set, view_action=view_action)
        if view_set_class.is_one_of(
            [ViewSetActionEnum.SEARCH_VIEWSET_LIST.value, ViewSetActionEnum.FAVORITE_VIEWSET_LIST.value]
        ):
            data = response.data
            if isinstance(data, dict) and "data" in data:
                data["data"] = [d for d in data["data"] if d["index_set_id"] in allow_resources]
                response.data = data
                return response
        if view_set_class.eq(ViewSetActionEnum.FAVORITE_VIEWSET_LIST_BY_GROUP.value):
            data = response.data
            if isinstance(data, dict) and "data" in data:
                allowed_data = []
                for fg in data["data"]:
                    fg["favorites"] = [f for f in fg["favorites"] if f["index_set_id"] in allow_resources]
                    allowed_data.append(fg)
                data["data"] = allowed_data
                response.data = data
                return response
        return response


@login_exempt
def external(request):
    """
    外部入口
    """
    space_uid = request.GET.get("space_uid", "")
    external_user_info = RequestProcessor.get_request_user_info(request)
    external_user = external_user_info.get("username", "")
    # 页面入口只判断能进哪些空间，此时还没有确定授权人，执行身份留空
    identity = IdentityContext.for_external_request(external_user=external_user, authorizer="")
    space_uid_list = list_authorized_space_uids(identity)
    if space_uid:
        try:
            SpaceApi.get_space_detail(space_uid)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(f"获取空间信息({space_uid})失败：{e}")
    else:
        if not space_uid_list:
            logger.error(f"外部用户{external_user}无访问权限")
            return HttpResponseForbidden(f"外部用户{external_user}无访问权限")
        space_uid = space_uid_list[0]
    request.space_uid = space_uid
    if request.space_uid and external_user:
        if not has_space_access(identity, space_uid):
            logger.error(f"外部用户{external_user}无访问权限(空间ID:{space_uid})")
            return HttpResponseForbidden(f"外部用户{external_user}无访问权限(空间ID:{space_uid})")
        authorizer = AuthorizerSettings.get_authorizer(space_uid=space_uid)
        if not authorizer:
            logger.error(f"空间ID:{space_uid}无对应授权人")
            return HttpResponseForbidden(f"空间ID:{space_uid}无对应授权人")
        user = auth.authenticate(username=authorizer)
        auth.login(request, user)
        setattr(request, "COOKIES", {k: v for k, v in request.COOKIES.items() if k != "bk_token"})
    else:
        logger.error(f"外部用户({external_user})或空间(ID:{space_uid})不存在, request.META: {request.META}")
    response = render(request, settings.VUE_INDEX, get_toggle_data(request))
    response.set_cookie("space_uid", space_uid)
    response.set_cookie("external_user", external_user)
    return response


@login_exempt
def dispatch_list_user_spaces(request):
    """
    外部版本获取用户被授权的空间列表
    """
    from apps.log_search.models import Space

    external_user_info = RequestProcessor.get_request_user_info(request)
    external_user = external_user_info.get("username", "")
    if not external_user:
        return HttpResponseForbidden("请求缺少HTTP_USER或USER请求头")

    identity = IdentityContext.for_external_request(external_user=external_user, authorizer="")
    external_user_permission = list_authorized_space_actions(identity)
    if not external_user_permission:
        logger.error(f"外部用户{external_user}无访问权限")
        return HttpResponseForbidden(f"外部用户{external_user}无访问权限")
    space_uid_list = list(external_user_permission.keys())
    spaces = Space.objects.filter(space_uid__in=space_uid_list).all()
    return JsonResponse(
        {
            "result": True,
            "message": f"list external_user:{external_user} spaces success",
            "data": [
                {
                    "id": space.id,
                    "space_type_id": space.space_type_id,
                    "space_type_name": _(space.space_type_name),
                    "space_id": space.space_id,
                    "space_name": space.space_name,
                    "space_uid": space.space_uid,
                    "space_code": space.space_code,
                    "bk_biz_id": space.bk_biz_id,
                    "time_zone": space.properties.get("time_zone", "Asia/Shanghai"),
                    "is_sticky": False,
                    "permission": {ActionEnum.VIEW_BUSINESS.id: True},
                    "external_permission": external_user_permission.get(space.space_uid, []),
                }
                for space in spaces
            ],
        }
    )


@login_exempt
@method_decorator(csrf_exempt)
@require_POST
def dispatch_external_proxy(request):
    """
    转发请求，暂时仅考虑GET/POST请求
    body = {
        "url": 被转发资源请求url, 比如：/api/v1/search/index_set/?space_uid=bkcc__2
        "space_uid": "空间ID",
        "method": 'GET|POST',
        "data": data, POST请求的数据
    }
    """

    try:
        params = json.loads(request.body)
    except json.decoder.JSONDecodeError:
        return JsonResponse({"result": False, "message": "invalid json format"}, status=400)

    # proxy: url/method/data
    url: str = params.get("url")
    space_uid: str = RequestProcessor.get_space_uid(request=request)
    method: str = params.get("method", "GET")
    # 这里是字符串
    json_data_str: str = params.get("data", "")
    authorizer = AuthorizerSettings.get_authorizer(space_uid=space_uid)
    audit_recorder = ExternalAuditRecorder(request)
    audit_recorder.space_uid = space_uid
    audit_recorder.authorizer = authorizer or ""
    try:
        parsed = urlsplit(url)
        if method.lower() == "get":
            fake_request = RequestFactory().get(url, content_type="application/json")
        elif method.lower() == "post":
            fake_request = RequestFactory().post(url, data=json_data_str, content_type="application/json")
        elif method.lower() == "put":
            fake_request = RequestFactory().put(url, data=json_data_str, content_type="application/json")
        elif method.lower() == "delete":
            fake_request = RequestFactory().delete(url, content_type="application/json")
        else:
            return JsonResponse(
                {"result": False, "message": f"dispatch_plugin_query, method: {method.lower()} is not allowed"},
                status=400,
            )
        fake_request = RequestProcessor.copy_request_to_fake_request(request=request, fake_request=fake_request)
        # resolve view_func
        match = resolve(parsed.path, urlconf=None)
        view_func, kwargs = match.func, match.kwargs
        # 获取对应的视图集和视图函数
        view_set = RequestProcessor.get_view_set(view_func=view_func)
        view_action = RequestProcessor.get_view_action(view_func=view_func, method=method.lower())
        external_user_info = RequestProcessor.get_request_user_info(request)
        external_user = external_user_info.get("username", "")
        # 判权用外部用户、执行用内部授权人、审计记外部用户，三者从这里开始就分开取
        identity = IdentityContext.for_external_request(external_user=external_user, authorizer=authorizer or "")
        audit_recorder.external_user = identity.audit_user
        audit_recorder.view_set = view_set
        audit_recorder.view_action = view_action
        audit_recorder.action_id = resolve_declared_action_id(view_set=view_set, view_action=view_action)

        decision = authorize(
            ExternalRequestContext(
                identity=identity,
                space_uid=space_uid,
                view_set=view_set,
                view_action=view_action,
                declared_action_id=audit_recorder.action_id,
                url_kwargs=kwargs,
                json_data_str=json_data_str,
            )
        )
        if decision.matched_action_id:
            audit_recorder.action_id = decision.matched_action_id
        audit_recorder.resource = decision.resource_id
        if not decision.allowed:
            audit_recorder.set_result(403, decision.reject_reason)
            return JsonResponse({"result": False, "message": decision.reject_reason}, status=403)
        # 命中的授权项，默认放行的接口没有授权项，保持为空
        action_id = decision.matched_action_id
        allow_resources_result = decision.allow_resources_result

        setattr(fake_request, "space_uid", space_uid)
        setattr(request, "space_uid", space_uid)
        # 鉴权已经用外部用户判完，这里才把请求登录成内部授权人去执行下游视图
        if identity.execution_user:
            user = auth.authenticate(username=identity.execution_user)
            auth.login(request, user)
            setattr(fake_request, "user", request.user)
        logger.info(
            f"dispatch_plugin_query: request:{request}, user:{request.user}, "
            f"external_user: {external_user}, space_uid: {space_uid}"
        )
        # 绕过csrf鉴权
        setattr(fake_request, "csrf_processing_done", True)
        setattr(request, "csrf_processing_done", True)
        # 请求携带外部标识
        setattr(fake_request, "external_user", external_user)
        setattr(request, "external_user", external_user)
        setattr(request, "external_user_info", external_user_info)
        setattr(fake_request, "session", request.session)
        set_local_param("current_request", fake_request)
        if external_user_info:
            set_local_param("time_zone", external_user_info.get("time_zone", settings.TIME_ZONE))

        # call view_func
        response = view_func(fake_request, **kwargs)
        # 视图内部的鉴权失败不会命中上面的分支，按响应码补记审计结果
        status_code = getattr(response, "status_code", 0)
        if status_code >= 400:
            audit_recorder.set_result(status_code, f"view_func response status: {status_code}")
        return RequestProcessor.filter_response_resource(
            external_user=external_user,
            response=response,
            action_id=action_id,
            view_set=view_set,
            view_action=view_action,
            allow_resources_result=allow_resources_result,
        )

    except Resolver404:
        logger.warning(f"dispatch_plugin_query: resolve view func 404 for: {url}")
        return JsonResponse(
            {"result": False, "message": f"dispatch_plugin_query: resolve view func 404 for: {url}"}, status=404
        )

    except Exception as e:
        audit_recorder.set_result(resolve_exception_status_code(e), str(e))
        logger.exception(f"dispatch_plugin_query: exception for {e}")
        raise e

    finally:
        # 转发入口有多个鉴权提前返回分支，统一在这里上报，避免漏埋拒绝事件
        audit_recorder.push()


@login_exempt
@method_decorator(csrf_exempt)
@require_POST
def external_callback(request):
    logger.info("[external_callback]: external_callback with body keys present")
    try:
        params = json.loads(request.body)
    except json.decoder.JSONDecodeError:
        return JsonResponse({"result": False, "message": "invalid json format"}, status=400)

    if not isinstance(params, dict):
        return JsonResponse({"result": False, "message": "invalid payload"}, status=400)

    if not params.get("token"):
        logger.warning("[external_callback]: missing token")
        return JsonResponse({"result": False, "message": "missing token"}, status=401)

    missing = [key for key in ("sn", "title", "updated_by") if not params.get(key)]
    if missing or "approve_result" not in params:
        if "approve_result" not in params:
            missing.append("approve_result")
        logger.warning("[external_callback]: missing required fields: %s", missing)
        return JsonResponse({"result": False, "message": f"missing required fields: {','.join(missing)}"}, status=400)

    try:
        params["approve_result"] = BooleanField().to_internal_value(params["approve_result"])
    except Exception:
        return JsonResponse({"result": False, "message": "invalid approve_result"}, status=400)

    result = ExternalPermissionApplyRecord.callback(params)
    if result.get("result"):
        return JsonResponse(result, status=200)
    return JsonResponse(result, status=400)
