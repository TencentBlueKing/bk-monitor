# -*- coding: utf-8 -*-
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
from typing import Any, Dict
from urllib.parse import parse_qs, urlsplit

from blueapps.account.decorators import login_exempt
from django.conf import settings
from django.contrib import auth
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.test import RequestFactory
from django.urls import Resolver404, resolve
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.response import Response

from apps.constants import (
    ExternalPermissionActionEnum,
    ViewSetAction,
    ViewSetActionEnum,
)
from apps.iam import ActionEnum
from apps.log_commons.models import (
    AuthorizerSettings,
    ExternalPermission,
    ExternalPermissionApplyRecord,
)
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
    def get_request_user_info(cls, request) -> Dict[str, Any]:
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
    def get_resource(cls, action_id: str, kwargs: Dict[str, Any], json_data_str: str):
        """获取请求中的资源"""
        if action_id == ExternalPermissionActionEnum.LOG_SEARCH.value:
            if "index_set_id" in kwargs:
                return int(kwargs.get("index_set_id", ""))
            try:
                json_data = json.loads(json_data_str)
                if "index_set_id" in json_data:
                    return int(json_data.get("index_set_id", ""))
            except json.decoder.JSONDecodeError:
                logger.exception(f"解析请求数据({json_data_str})失败")
        return None

    @classmethod
    def filter_response_resource(
        cls,
        external_user: str,
        response: Response,
        action_id: str,
        view_set: str,
        view_action: str,
        allow_resources_result: Dict[str, Any],
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
        cls, response: Response, action_id: str, view_set: str, view_action: str, allow_resources_result: Dict[str, Any]
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

    @classmethod
    def is_default_allowed(cls, view_set: str, view_action: str):
        """
        是否是默认允许的接口
        """
        for _d in ViewSetActionEnum.get_keys():
            if _d.view_set != view_set:
                continue
            if not _d.view_action or _d.view_action == view_action:
                if _d.action_id == ExternalPermissionActionEnum.LOG_COMMON.value or _d.default_permission:
                    return True
        return False


@login_exempt
def external(request):
    """
    外部入口
    """
    space_uid = request.GET.get("space_uid", "")
    external_user_info = RequestProcessor.get_request_user_info(request)
    external_user = external_user_info.get("username", "")
    space_uid_list = ExternalPermission.get_authorized_user_space_list(authorized_user=external_user)
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
        qs = ExternalPermission.objects.filter(
            authorized_user=external_user, space_uid=space_uid, expire_time__gt=timezone.now()
        )
        if not qs:
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

    external_user_permission = ExternalPermission.get_authorizer_permission(authorizer=external_user)
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
        # 内部定义的action_id, ActionEnum
        action_id = ""
        external_user_info = RequestProcessor.get_request_user_info(request)
        external_user = external_user_info.get("username", "")
        allow_resources_result = {"allowed": False, "resources": []}
        # 判断是否是默认允许的接口, 默认允许的接口不需要进行权限校验
        if not RequestProcessor.is_default_allowed(view_set=view_set, view_action=view_action):
            # transfer request.user 进行外部权限替换
            external_user_allowed_action_id_list = ExternalPermission.get_authorizer_permission(
                space_uid=space_uid, authorizer=external_user
            ).get(space_uid, [])
            # 判断接口是否在管理范围内
            if not external_user_allowed_action_id_list:
                return JsonResponse(
                    {
                        "result": False,
                        "message": f"dispatch_plugin_query: external_user:{external_user} has no permission.",
                    },
                    status=403,
                )
            is_allowed = False
            for _action_id in external_user_allowed_action_id_list:
                if ExternalPermission.is_action_valid(view_set=view_set, view_action=view_action, action_id=_action_id):
                    is_allowed = True
                    action_id = _action_id
                    break
            if not is_allowed:
                return JsonResponse(
                    {"result": False, "message": f"external_user:{external_user} has not enough permission."},
                    status=403,
                )
            allow_resources_result = ExternalPermission.get_resources(
                space_uid=space_uid, action_id=action_id, authorized_user=external_user
            )
            if allow_resources_result["allowed"]:
                allow_resources = allow_resources_result["resources"]
                resource = RequestProcessor.get_resource(
                    action_id=action_id, kwargs=kwargs, json_data_str=json_data_str
                )
                if resource and resource not in allow_resources:
                    return JsonResponse(
                        {
                            "result": False,
                            "message": f"external_user:{external_user} cannot access resource(ID:{resource}).",
                        },
                        status=403,
                    )
        setattr(fake_request, "space_uid", space_uid)
        setattr(request, "space_uid", space_uid)
        if authorizer:
            user = auth.authenticate(username=authorizer)
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
        return RequestProcessor.filter_response_resource(
            external_user=external_user,
            response=response,
            action_id=action_id,
            view_set=view_set,
            view_action=view_action,
            allow_resources_result=allow_resources_result,
        )

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
    logger.info(f"[external_callback]: external_callback with header({request.headers}), body({request.body})")
    try:
        params = json.loads(request.body)
    except json.decoder.JSONDecodeError:
        return JsonResponse({"result": False, "message": "invalid json format"}, status=400)

    result = ExternalPermissionApplyRecord.callback(params)
    if result["result"]:
        return JsonResponse(result, status=200)
