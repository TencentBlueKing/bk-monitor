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
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.fields import BooleanField
from rest_framework.response import Response

from apps.constants import (
    ExternalPermissionActionEnum,
    ViewSetAction,
    ViewSetActionEnum,
)
from apps.iam import ActionEnum
from apps.iam.handlers.permission import Permission
from apps.log_commons.handlers.external_permission_decision import ExternalLogSearchPermissionDecision
from apps.log_commons.models import (
    AuthorizerSettings,
    ExternalPermission,
    ExternalPermissionApplyRecord,
)
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import EXTERNAL_PERMISSION_OR_DECISION
from apps.utils.db import get_toggle_data
from apps.utils.local import set_local_param
from apps.utils.log import logger
from apps.iam.handlers.resources import ResourceEnum
from bkm_space.api import SpaceApi
from bkm_space.utils import bk_biz_id_to_space_uid, space_uid_to_bk_biz_id

# 空间列表 IAM 批量查询缓存：同一次请求中，同一个 bk_biz_id 只查一次 IAM VIEW_BUSINESS
_iam_allowed_biz_cache: set = set()


def _is_biz_enabled_for_or_decision(toggle_obj, bk_biz_id: int) -> bool:
    """
    复用已缓存的 toggle_obj 做空间级灰度判断，行为等价于 FeatureToggleObject.switch，
    但避免循环内重复调用 toggle() 触发 N 次 DB 查询。
    """
    if not toggle_obj:
        return False
    if toggle_obj.status == "off":
        return False
    if toggle_obj.status == "debug" and toggle_obj.biz_id_white_list:
        return bk_biz_id in toggle_obj.biz_id_white_list
    if toggle_obj.status == "debug" and toggle_obj.biz_id_black_list:
        return bk_biz_id not in toggle_obj.biz_id_black_list
    if toggle_obj.status == "debug" and settings.ENVIRONMENT not in ["dev", "stag"]:
        return False
    return True


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
    def get_resource(cls, action_id: str, kwargs: dict[str, Any], json_data_str: str):
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
        space_uid: str,
        response: Response,
        action_id: str,
        view_set: str,
        view_action: str,
        allow_resources_result: dict[str, Any],
    ):
        """
        过滤接口返回中的资源
        :param external_user: 外部用户（authorization_subject/audit_user，仅用于数据归属/权限口径，绝非execution_user）
        :param space_uid: 空间唯一标识
        :param response: 原始响应
        :param action_id: action_id, ActionEnum
        :param view_set: view_func对应的viewset名称
        :param view_action: view_func对应的action名称
        :param allow_resources_result: 允许访问的资源（legacy显式资源，列表场景内部还会再并入IAM批量鉴权结果）
        """
        if not allow_resources_result["allowed"]:
            return response
        if action_id == ExternalPermissionActionEnum.LOG_SEARCH.value:
            return cls.filter_log_search_response_resource(
                external_user=external_user,
                space_uid=space_uid,
                response=response,
                action_id=action_id,
                view_set=view_set,
                view_action=view_action,
                allow_resources_result=allow_resources_result,
            )

        return response

    @classmethod
    def filter_log_search_response_resource(
        cls,
        external_user: str,
        space_uid: str,
        response: Response,
        action_id: str,
        view_set: str,
        view_action: str,
        allow_resources_result: dict[str, Any],
    ):
        """
        列表接口的资源过滤。
        灰度开关关闭时：纯 legacy 资源内存过滤，与 git HEAD 老版本逐行等价。
        灰度开关开启时：legacy 显式资源(内存过滤) ∪ 对差集一次性批量 IAM 鉴权(1次HTTP调用)。
        """
        if not RequestProcessor.is_or_decision_enabled(space_uid):
            # 开关关闭：纯 legacy 过滤，与老版本逐行等价
            allow_resources = allow_resources_result["resources"]
            view_set_class = ViewSetAction(action_id=action_id, view_set=view_set, view_action=view_action)
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

        # 开关开启：legacy ∪ IAM batch
        legacy_allow_resources = {int(r) for r in allow_resources_result["resources"]}
        view_set_class: ViewSetAction = ViewSetAction(action_id=action_id, view_set=view_set, view_action=view_action)

        data = getattr(response, "data", None)
        if data is None:
            return response

        candidate_resource_ids: list = []
        if view_set_class.is_one_of(
            [
                ViewSetActionEnum.SEARCH_VIEWSET_LIST.value,
                ViewSetActionEnum.FAVORITE_VIEWSET_LIST.value,
                ViewSetActionEnum.FAVORITE_UNION_SEARCH_VIEWSET_LIST.value,
            ]
        ):
            if isinstance(data, dict) and "data" in data:
                candidate_resource_ids = [int(d["index_set_id"]) for d in data["data"]]
        elif view_set_class.eq(ViewSetActionEnum.FAVORITE_VIEWSET_LIST_BY_GROUP.value):
            if isinstance(data, dict) and "data" in data:
                candidate_resource_ids = [
                    int(f["index_set_id"]) for fg in data["data"] for f in fg.get("favorites", [])
                ]

        if candidate_resource_ids:
            # 仅对legacy未覆盖的差集触发IAM批量查询，IAM调用次数恒为1次
            iam_check_ids = [rid for rid in candidate_resource_ids if rid not in legacy_allow_resources]
            iam_allow_resources = ExternalLogSearchPermissionDecision.batch_iam_allowed_resources(
                space_uid=space_uid, external_user=external_user, resource_ids=iam_check_ids
            )
            allow_resources = legacy_allow_resources | iam_allow_resources
        else:
            allow_resources = legacy_allow_resources

        if view_set_class.is_one_of(
            [
                ViewSetActionEnum.SEARCH_VIEWSET_LIST.value,
                ViewSetActionEnum.FAVORITE_VIEWSET_LIST.value,
                ViewSetActionEnum.FAVORITE_UNION_SEARCH_VIEWSET_LIST.value,
            ]
        ):
            if isinstance(data, dict) and "data" in data:
                data["data"] = [d for d in data["data"] if int(d["index_set_id"]) in allow_resources]
                response.data = data
                return response
        if view_set_class.eq(ViewSetActionEnum.FAVORITE_VIEWSET_LIST_BY_GROUP.value):
            if isinstance(data, dict) and "data" in data:
                allowed_data = []
                for fg in data["data"]:
                    fg["favorites"] = [f for f in fg.get("favorites", []) if int(f["index_set_id"]) in allow_resources]
                    allowed_data.append(fg)
                data["data"] = allowed_data
                response.data = data
                return response
        return response

    @classmethod
    def is_or_decision_enabled(cls, space_uid: str) -> bool:
        """
        判断指定空间是否命中 PO+IAM OR 决策灰度开关。
        全局 off → 全部 False（老逻辑）；全局 on → 全部 True；debug 态 → 按名单判断。
        """
        bk_biz_id = int(space_uid_to_bk_biz_id(space_uid))
        return FeatureToggleObject.switch(EXTERNAL_PERMISSION_OR_DECISION, biz_id=bk_biz_id)

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

    @classmethod
    def get_target_action_id(cls, view_set: str, view_action: str) -> str:
        """
        从ViewSetActionEnum推断当前接口对应的action_id。
        用于用户在legacy侧完全没有该action的授权记录时（is_action_valid遍历为空），
        仍可判断该接口属于log_search范畴，从而走IAM-only判定路径，而不是直接因为"无授权记录"被拒绝。
        """
        for _d in ViewSetActionEnum.get_keys():
            if _d.view_set != view_set:
                continue
            if _d.view_action and _d.view_action != view_action:
                continue
            return _d.action_id
        return ""

    @classmethod
    def is_log_search_list_view(cls, view_set: str, view_action: str) -> bool:
        """是否是log_search资源列表类接口，用于IAM-only场景下的资源边界收敛（无资源时不整体放通非列表接口）"""
        view_set_action = ViewSetAction(
            action_id=ExternalPermissionActionEnum.LOG_SEARCH.value, view_set=view_set, view_action=view_action
        )
        return view_set_action.is_one_of(
            [
                ViewSetActionEnum.SEARCH_VIEWSET_LIST.value,
                ViewSetActionEnum.FAVORITE_VIEWSET_LIST.value,
                ViewSetActionEnum.FAVORITE_VIEWSET_LIST_BY_GROUP.value,
                ViewSetActionEnum.FAVORITE_UNION_SEARCH_VIEWSET_LIST.value,
            ]
        )


@login_exempt
def external(request):
    """
    外部入口，支持 PO OR IAM：PO 有记录或 IAM 有 VIEW_BUSINESS 权限均可进入空间。
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
        if RequestProcessor.is_or_decision_enabled(space_uid):
            # PO OR IAM：PO 有记录直接通过；无 PO 记录时用 IAM VIEW_BUSINESS 判断
            has_po = ExternalPermission.objects.filter(
                authorized_user=external_user, space_uid=space_uid, expire_time__gt=timezone.now()
            ).exists()
            has_iam = False
            if not has_po:
                try:
                    bk_biz_id = space_uid_to_bk_biz_id(space_uid)
                    has_iam = Permission(
                        username=external_user, bk_tenant_id=settings.BK_APP_TENANT_ID
                    ).is_allowed_by_biz(
                        bk_biz_id=bk_biz_id, action=ActionEnum.VIEW_BUSINESS, raise_exception=False
                    )
                except Exception:  # pylint: disable=broad-except
                    has_iam = False
            if not has_po and not has_iam:
                logger.error(
                    f"外部用户{external_user}无访问权限(空间ID:{space_uid}, PO={has_po}, IAM={has_iam})"
                )
                return HttpResponseForbidden(f"外部用户{external_user}无访问权限(空间ID:{space_uid})")
        else:
            # 开关关闭：纯 PO 判定，不走 IAM
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
    外部版本获取用户被授权的空间列表，支持 PO OR IAM。
    PO 空间：ExternalPermission 中有记录的空间。
    IAM 空间：用户有 VIEW_BUSINESS 权限但无 PO 记录的空间。
    灰度开关关闭时，回退为纯 PO 空间列表（老逻辑）。
    """
    global _iam_allowed_biz_cache
    _iam_allowed_biz_cache = set()

    from apps.log_search.models import Space

    external_user_info = RequestProcessor.get_request_user_info(request)
    external_user = external_user_info.get("username", "")
    if not external_user:
        return HttpResponseForbidden("请求缺少HTTP_USER或USER请求头")

    # 提前获取灰度开关对象，循环内复用避免 N 次 DB 查询
    toggle_obj = FeatureToggleObject.toggle(EXTERNAL_PERMISSION_OR_DECISION)

    # 开关关闭 → 纯 PO 老逻辑，不做任何 IAM 查询
    if toggle_obj and toggle_obj.status == "off":
        po_permission = ExternalPermission.get_authorizer_permission(authorizer=external_user)
        if not po_permission:
            logger.error(f"外部用户{external_user}无访问权限")
            return HttpResponseForbidden(f"外部用户{external_user}无访问权限")
        space_uid_list = list(po_permission.keys())
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
                        "external_permission": po_permission.get(space.space_uid, []),
                    }
                    for space in spaces
                ],
            }
        )

    # 开关开启或 debug 态 → PO ∪ IAM OR 决策
    po_permission = ExternalPermission.get_authorizer_permission(authorizer=external_user)
    po_space_uids = set(po_permission.keys())

    # IAM 空间：对 PO 未覆盖的空间，按 bk_biz_id 去重后 1 次 batch_is_allowed（替代逐个 is_allowed_by_biz）
    iam_space_uids = set()
    if po_space_uids:
        non_po_spaces = Space.objects.exclude(space_uid__in=po_space_uids).all()
    else:
        non_po_spaces = Space.objects.all()

    # 按 bk_biz_id 去重收集，同时筛选灰度命中的业务（名单匹配复用 toggle_obj）
    eligible_biz_ids = set()
    biz_id_to_space_uids = {}
    for space in non_po_spaces:
        bk_biz_id = space.bk_biz_id
        biz_id_to_space_uids.setdefault(bk_biz_id, []).append(space.space_uid)
        if bk_biz_id not in eligible_biz_ids and _is_biz_enabled_for_or_decision(toggle_obj, bk_biz_id):
            eligible_biz_ids.add(bk_biz_id)

    if eligible_biz_ids:
        try:
            iam_resources = [
                [ResourceEnum.BUSINESS.create_simple_instance(str(biz_id))] for biz_id in eligible_biz_ids
            ]
            perm_result = Permission(
                username=external_user, bk_tenant_id=settings.BK_APP_TENANT_ID
            ).batch_is_allowed(actions=[ActionEnum.VIEW_BUSINESS], resources=iam_resources)
            for biz_id_str, action_results in perm_result.items():
                if action_results.get(ActionEnum.VIEW_BUSINESS.id, False):
                    bk_biz_id_int = int(biz_id_str)
                    _iam_allowed_biz_cache.add(bk_biz_id_int)
                    for suid in biz_id_to_space_uids.get(bk_biz_id_int, []):
                        iam_space_uids.add(suid)
        except Exception:  # pylint: disable=broad-except
            pass

    all_space_uids = po_space_uids | iam_space_uids
    if not all_space_uids:
        logger.error(f"外部用户{external_user}无访问权限(PO和IAM均无)")
        return HttpResponseForbidden(f"外部用户{external_user}无访问权限")

    spaces = Space.objects.filter(space_uid__in=all_space_uids).all()
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
                    "external_permission": po_permission.get(space.space_uid, []),
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
        # 审计三身份字段：authorization_subject/audit_user 恒为 external_user；execution_user 为内部授权人(authorizer)
        # decision_source: legacy/iam/both/none，供审计区分"PO内部代理通过"与"IAM对外部用户放行"，避免混淆
        decision_source = "none"
        decision_warning = False
        # 判断是否是默认允许的接口, 默认允许的接口不需要进行权限校验
        if not RequestProcessor.is_default_allowed(view_set=view_set, view_action=view_action):
            # transfer request.user 进行外部权限替换（legacy侧action列表，subject为external_user）
            external_user_allowed_action_id_list = ExternalPermission.get_authorizer_permission(
                space_uid=space_uid, authorizer=external_user
            ).get(space_uid, [])
            # 拥有客户端日志权限的用户，自动拥有客户端日志索引集的日志检索权限
            if (
                ExternalPermissionActionEnum.CLIENT_LOG.value in external_user_allowed_action_id_list
                and ExternalPermissionActionEnum.LOG_SEARCH.value not in external_user_allowed_action_id_list
            ):
                external_user_allowed_action_id_list.append(ExternalPermissionActionEnum.LOG_SEARCH.value)

            is_action_valid = False
            for _action_id in external_user_allowed_action_id_list:
                if ExternalPermission.is_action_valid(view_set=view_set, view_action=view_action, action_id=_action_id):
                    is_action_valid = True
                    action_id = _action_id
                    break

            # 灰度开关控制：开启时 PO+IAM OR 决策；关闭或非 log_search 时纯 legacy 判定
            target_action_id = action_id or RequestProcessor.get_target_action_id(
                view_set=view_set, view_action=view_action
            )

            if (
                target_action_id == ExternalPermissionActionEnum.LOG_SEARCH.value
                and RequestProcessor.is_or_decision_enabled(space_uid)
            ):
                action_id = target_action_id
                resource = RequestProcessor.get_resource(action_id=action_id, kwargs=kwargs, json_data_str=json_data_str)

                # ===== PO+IAM OR 决策：subject 恒为 external_user，authorizer 从不参与本判断 =====
                legacy_result = ExternalLogSearchPermissionDecision.legacy_check(
                    space_uid=space_uid,
                    external_user=external_user,
                    view_set=view_set,
                    view_action=view_action,
                    resource_id=resource,
                )
                iam_result = ExternalLogSearchPermissionDecision.iam_check_resource(
                    space_uid=space_uid, external_user=external_user, resource_id=resource
                )
                decision_result = ExternalLogSearchPermissionDecision.decide(
                    external_user=external_user,
                    execution_user=authorizer,
                    legacy_result=legacy_result,
                    iam_result=iam_result,
                )
                decision_source = decision_result.decision_source
                decision_warning = decision_result.warning
                allow_resources_result = {"allowed": True, "resources": list(decision_result.resources)}

                # 详情接口(resource非空)与列表接口(resource为空)使用同一决策口径：
                # 有明确resource时必须命中legacy∪iam的显式集合；列表接口的资源过滤在filter_log_search_response_resource里
                # 复用同一批legacy∪iam口径完成，此处仅做"该action是否被放行"的边界判断
                is_list_view = RequestProcessor.is_log_search_list_view(view_set=view_set, view_action=view_action)
                if resource is not None and not decision_result.allowed:
                    return JsonResponse(
                        {
                            "result": False,
                            "message": f"external_user:{external_user} cannot access resource(ID:{resource}).",
                        },
                        status=403,
                    )
                if resource is None and not decision_result.allowed and not is_list_view:
                    return JsonResponse(
                        {"result": False, "message": f"external_user:{external_user} has not enough permission."},
                        status=403,
                    )
                # 内部授权人仅作代理执行身份：若最终放行来源包含iam(iam/both)且该空间未配置authorizer，
                # 则无可用execution_user，必须拒绝而非静默匿名执行(request.user停留匿名态)
                if decision_result.allowed and decision_source in ("iam", "both") and not authorizer:
                    logger.warning(
                        "iam-only allowed but no authorizer configured for space_uid=%s, external_user=%s, "
                        "reject to avoid anonymous proxy execution",
                        space_uid, external_user,
                    )
                    return JsonResponse(
                        {
                            "result": False,
                            "message": f"空间(ID:{space_uid})未配置代理执行人，暂不支持该访问方式",
                        },
                        status=403,
                    )
            else:
                # 纯 legacy 判定（灰度关闭或非 log_search 能力），与老版本逐行等价
                if not external_user_allowed_action_id_list:
                    return JsonResponse(
                        {
                            "result": False,
                            "message": f"dispatch_plugin_query: external_user:{external_user} has no permission.",
                        },
                        status=403,
                    )
                if not is_action_valid:
                    return JsonResponse(
                        {"result": False, "message": f"external_user:{external_user} has not enough permission."},
                        status=403,
                    )
                allow_resources_result = ExternalPermission.get_resources(
                    space_uid=space_uid, action_id=action_id, authorized_user=external_user
                )
                decision_source = "legacy" if allow_resources_result["allowed"] else "none"
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
        # execution_user：内部授权人代理执行身份登录，与"是否放行"判定完全独立，不因决策来源改变
        if authorizer:
            user = auth.authenticate(username=authorizer)
            auth.login(request, user)
            setattr(fake_request, "user", request.user)
        # 审计日志：三身份分离打印，避免"内部代理执行成功"被误记为"IAM主体放行"
        logger.info(
            "dispatch_plugin_query: request=%s, authorization_subject=%s, execution_user=%s, "
            "audit_user=%s, decision_source=%s, warning=%s, space_uid=%s",
            request, external_user, getattr(request.user, "username", ""), external_user,
            decision_source, decision_warning, space_uid,
        )
        # 绕过csrf鉴权
        setattr(fake_request, "csrf_processing_done", True)
        setattr(request, "csrf_processing_done", True)
        # 请求携带外部标识：external_user 的赋值时机/来源固定在决策逻辑之外，
        # 不因legacy/iam/both决策来源不同而改变，恒等于USER头解析出的原始用户名(authorization_subject=audit_user)
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
            space_uid=space_uid,
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
        logger.exception(f"dispatch_plugin_query: exception for {e}")
        raise e


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
