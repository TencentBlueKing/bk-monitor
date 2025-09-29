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

import json
import sys
from collections.abc import Callable

from django.conf import settings
from django.utils import translation

from apps.log_esquery.permission import EsquerySearchPermissions
from apps.utils import build_auth_args
from apps.utils.local import get_request, get_backend_username
from bkm_space.define import SpaceTypeEnum
from bkm_space.utils import bk_biz_id_to_space_uid, space_uid_to_bk_biz_id


def get_non_bkcc_space_related_bkcc_biz_id(bk_biz_id):
    """
    获取非CC业务关联的CC业务ID
    """
    from apps.log_search.models import SpaceApi

    space_uid = bk_biz_id_to_space_uid(bk_biz_id)
    related_space = SpaceApi.get_related_space(space_uid=space_uid, related_space_type=SpaceTypeEnum.BKCC.value)
    if related_space:
        return related_space.bk_biz_id
    return bk_biz_id


def get_bkcc_biz_id_related_spaces(bk_biz_id, query_type="space_uid"):
    """
    获取CC业务关联的非CC空间资源
    """
    from apps.log_search.models import SpaceApi

    space_uid = bk_biz_id_to_space_uid(bk_biz_id)
    related_space_uids = SpaceApi.get_related_space_uids(space_uid)
    if query_type == "space_uid":
        return related_space_uids
    return [space_uid_to_bk_biz_id(space_uid) for space_uid in related_space_uids]


def adapt_non_bkcc(params):
    # 非CC业务时, 查询关联的CC业务, 如果有, 替换为其关联的CC业务
    bk_biz_id = params.get("bk_biz_id", 0)
    if not bk_biz_id:
        return params
    if int(bk_biz_id) < 0:
        params["bk_biz_id"] = get_non_bkcc_space_related_bkcc_biz_id(bk_biz_id)

    return params


def adapt_non_bkcc_for_bknode(params):
    """
    适配节点管理的space_id
    """
    # 设置缓存
    _cache = {}
    # 处理蓝盾业务
    if scope_list := params.get("scope_list", []):
        for item in scope_list:
            scope_id = item["scope_id"]
            _scope_id = _cache.get(scope_id)
            if not _scope_id:
                _scope_id = get_non_bkcc_space_related_bkcc_biz_id(scope_id)
                _cache[scope_id] = _scope_id
            item["scope_id"] = _scope_id
        for item in params["host_list"]:
            meta_scope_id = item["meta"]["scope_id"]
            meta_bk_biz_id = item["meta"]["bk_biz_id"]
            _meta_scope_id = _cache.get(meta_scope_id)
            if not _meta_scope_id:
                _meta_scope_id = get_non_bkcc_space_related_bkcc_biz_id(meta_scope_id)
                _cache[meta_scope_id] = _meta_scope_id

            _meta_bk_biz_id = _cache.get(meta_bk_biz_id)
            if not _meta_bk_biz_id:
                _meta_bk_biz_id = get_non_bkcc_space_related_bkcc_biz_id(meta_bk_biz_id)
                _cache[meta_bk_biz_id] = _meta_bk_biz_id

            item["meta"]["scope_id"] = _meta_scope_id
            item["meta"]["bk_biz_id"] = _meta_bk_biz_id
        return params

    bk_biz_id = params.get("scope", {}).get("bk_biz_id", 0)
    if not bk_biz_id:
        return params
    if int(bk_biz_id) < 0:
        params["scope"]["bk_biz_id"] = get_non_bkcc_space_related_bkcc_biz_id(bk_biz_id)

    return params


def _clean_auth_info_uin(auth_info):
    if "uin" in auth_info:
        # 混合云uin去掉第一位
        if auth_info["uin"].startswith("o"):
            auth_info["uin"] = auth_info["uin"][1:]
    return auth_info


def update_bkdata_auth_info(params):
    """
    更新参数中的数据平台鉴权信息
    """
    if settings.FEATURE_TOGGLE.get("bkdata_token_auth", "off") == "on":
        # 如果使用 bkdata token 鉴权，需要设置鉴权方式，如果是用户鉴权，直接沿用原来的用户
        params["bkdata_authentication_method"] = params.get("bkdata_authentication_method") or "token"
        params["bkdata_data_token"] = settings.BKDATA_DATA_TOKEN
    else:
        # 如果是用户授权，设置为admin超级管理员
        params["bkdata_authentication_method"] = "user"
        params["bk_username"] = "admin"
        params["operator"] = "admin"
    return params


# 后台任务 & 测试任务调用 ESB 接口不需要用户权限控制
if (
    "celery" in sys.argv
    or "worker" in sys.argv
    or "shell" in sys.argv
    or "pydevconsole.py" in sys.argv[0]
    or ("runserver" not in sys.argv and sys.argv and "manage.py" in sys.argv[0])
):

    def add_app_info_before_request(params):
        params["bk_app_code"] = settings.APP_CODE
        params["X-Bk-App-Code"] = settings.APP_CODE
        return params

    def add_esb_info_before_request(params):
        if "bk_username" not in params:
            params["bk_username"] = get_backend_username(bk_tenant_id=params.get("bk_tenant_id"))

        if "operator" not in params:
            params["operator"] = params["bk_username"]
        return params

    def add_esb_info_before_request_for_bkdata_token(params):  # pylint: disable=function-name-too-long
        params = add_esb_info_before_request(params)
        params = add_app_info_before_request(params)
        params = update_bkdata_auth_info(params)
        params.setdefault("bkdata_authentication_method", "user")
        return params

    def add_esb_info_before_request_for_bkdata_user(params):  # pylint: disable=function-name-too-long
        params = add_esb_info_before_request(params)
        params = add_app_info_before_request(params)
        params.setdefault("bkdata_authentication_method", "user")
        return params


# 正常 WEB 请求所使用的函数
else:

    def add_app_info_before_request(params):
        params["bk_app_code"] = settings.APP_CODE
        params["app_code"] = settings.APP_CODE
        params["X-Bk-App-Code"] = settings.APP_CODE
        return params

    def add_esb_info_before_request(params):
        """
        通过 params 参数控制是否检查 request

        @param {Boolean} [params.no_request] 是否需要带上 request 标识
        """
        # 规范后的参数
        params["appenv"] = settings.RUN_VER

        if "no_request" in params and params["no_request"]:
            if "bk_username" not in params:
                params["bk_username"] = get_backend_username(bk_tenant_id=params.get("bk_tenant_id"))

            if "operator" not in params:
                params["operator"] = params["bk_username"]
        else:
            req = get_request()
            auth_info = build_auth_args(req)
            params.update(auth_info)
            if not params.get("auth_info"):
                auth_info = _clean_auth_info_uin(auth_info)
                params["auth_info"] = json.dumps(auth_info)
            params.update({"blueking_language": translation.get_language()})

            bk_username = getattr(req.user, "bk_username", None) or req.user.username
            if "bk_username" not in params:
                params["bk_username"] = bk_username

            if "operator" not in params:
                params["operator"] = bk_username

        # 兼容旧接口
        params["uin"] = params["bk_username"]
        return params

    def add_esb_info_before_request_for_bkdata_token(params):  # pylint: disable=function-name-too-long
        req = get_request()
        skip_check = getattr(req, "skip_check", False)
        if settings.BKAPP_IS_BKLOG_API and not skip_check:
            # 外部版请求转发 / 内嵌日志api页面 已通过日志saas鉴权逻辑，默认使用超级权限
            if (
                getattr(req, "external_user", None)
                or req.headers.get("X-SOURCE-APP-CODE", "") in settings.ESQUERY_WHITE_LIST
            ):
                params = update_bkdata_auth_info(params)
            else:
                auth_info = EsquerySearchPermissions.get_auth_info(req)
                if auth_info["bk_app_code"] in settings.ESQUERY_WHITE_LIST:
                    # 在白名单内的 app 使用超级权限
                    params = update_bkdata_auth_info(params)
        elif not settings.BKAPP_IS_BKLOG_API:
            # saas直查已通过日志鉴权逻辑，默认使用超级权限
            params = update_bkdata_auth_info(params)

        params = add_esb_info_before_request(params)
        params = add_app_info_before_request(params)
        params = adapt_non_bkcc(params)
        params.setdefault("bkdata_authentication_method", "user")
        return params

    def add_esb_info_before_request_for_bkdata_user(params):  # pylint: disable=function-name-too-long
        params = add_esb_info_before_request(params)
        params = add_app_info_before_request(params)
        params = adapt_non_bkcc(params)
        params.setdefault("bkdata_authentication_method", "user")
        return params


def get_all_user_before(params):
    params = add_esb_info_before_request(params)
    params["no_page"] = True
    params["fields"] = "username,display_name,time_zone,language"
    return params


def get_all_user_after(response_result):
    for _user in response_result.get("data", []):
        _user["chname"] = _user.pop("display_name", _user["username"])

    return response_result


def get_user_before(params):
    params = add_esb_info_before_request(params)
    params["id"] = params["bk_username"]
    return params


def get_user_after(response_result):
    if "data" in response_result:
        response_result["data"]["chname"] = response_result["data"]["display_name"]
    return response_result


def filter_abnormal_ip_hosts_topo(response_result):
    """
    对list_biz_hosts_topo 接口过滤空IP host及对异常ip进行相应处理返回处理后的response_result
    @param response_result {dict} CCAPI.list_biz_hosts_topo 返回结果
    {
        "code": 0,
        "permission": null,
        "result": true,
        "request_id": "98d1329a24004ebcbbeb398412c221f2",
        "message": "success",
        "data": {
            "count": 2,
            "info": [
                {
                    "bk_os_name": "",
                    "bk_host_id": 2000012891,
                    "bk_cloud_id": 2000000065,
                    "bk_supplier_account": "tencent",
                    "bk_host_innerip": "127.0.0.1",
                    "bk_os_type": null
                },
                {
                    "bk_os_name": "",
                    "bk_host_id": 2000012892,
                    "bk_cloud_id": 2000000065,
                    "bk_supplier_account": "tencent",
                    "bk_host_innerip": "127.0.0.1",
                    "bk_os_type": null
                }
            ]
        }
    }
    """
    host_list = response_result.get("data", {}).get("info", [])
    if not host_list:
        return response_result

    dst_host_list = []
    for host in host_list:
        if not host["host"]["bk_host_innerip"]:
            continue
        if "," in host["host"]["bk_host_innerip"]:
            host["host"]["bk_host_innerip"] = host["host"]["bk_host_innerip"].split(",")[0]
        dst_host_list.append(host)

    response_result["data"]["info"] = dst_host_list
    return response_result


def filter_abnormal_ip_hosts(response_result):
    """
    对list_biz_hosts 接口过滤空IP host及对异常ip进行相应处理返回处理后的response_result
    @param response_result {dict} CCAPI.list_biz_hosts 返回结果
    """
    host_list = response_result.get("data", {}).get("info", [])
    if not host_list:
        return response_result

    dst_host_list = []
    for host in host_list:
        if not host["bk_host_innerip"]:
            continue
        if "," in host["bk_host_innerip"]:
            host["bk_host_innerip"] = host["bk_host_innerip"].split(",")[0]
        dst_host_list.append(host)

    response_result["data"]["info"] = dst_host_list
    return response_result


def adapt_space_id_before(params):
    # 非CC业务时, 查询关联的CC业务, 如果有, 替换为其关联的CC业务
    if params.get("bk_biz_id", 0) < 0:
        from apps.log_search.models import SpaceApi

        space_uid = bk_biz_id_to_space_uid(params["bk_biz_id"])
        related_space = SpaceApi.get_related_space(space_uid=space_uid, related_space_type=SpaceTypeEnum.BKCC.value)
        if related_space:
            params["bk_biz_id"] = related_space.bk_biz_id

    return params


# 多租户函数工具集，用于 DataAPI 声明时使用
def biz_to_tenant_getter(key: Callable[[dict], str] | str = "bk_biz_id") -> Callable[[dict], str]:
    """
    通过业务获取租户ID
    :param key: 获取业务 ID 的函数，例如 lambda p: p["bk_biz_id"]，如果为 None，则默认使用 params["bk_biz_id"]
    :return: 获取租户 ID 的函数
    """
    from apps.log_search.models import Space

    def tenant_getter(params):
        """
        从请求参数中获取业务信息并转换为租户 ID
        """
        if callable(key):
            bk_biz_id = key(params)
        else:
            if key not in params:
                raise ValueError(f"failed to get tenant id from params, key `{key}` not found")
            bk_biz_id = params[key]
        return Space.get_tenant_id(bk_biz_id=bk_biz_id)

    return tenant_getter


def space_to_tenant_getter(key: Callable[[dict], str] | str = "space_uid") -> Callable[[dict], str]:
    """
    通过空间获取租户ID
    :param key: 获取空间 UID 的函数，例如 lambda p: p["space_uid"]，如果为 None，则默认使用 params["space_uid"]
    :return: 获取租户 ID 的函数
    """
    from apps.log_search.models import Space

    def tenant_getter(params):
        """
        从请求参数中获取空间信息并转换为租户 ID
        """
        if callable(key):
            space_uid = key(params)
        else:
            if key not in params:
                raise ValueError(f"failed to get tenant id from params, key `{key}` not found")
            space_uid = params[key]

        return Space.get_tenant_id(space_uid=space_uid)

    return tenant_getter
