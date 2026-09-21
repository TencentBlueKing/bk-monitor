import json
import logging
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

import requests

from bk_monitor_base.config.all import get_config
from bk_monitor_base.infras.constant import DEFAULT_BK_BIZ_ID, DEFAULT_TENANT_ID
from bk_monitor_base.infras.third_party_api.errors import BkApiError

logger = logging.getLogger(__name__)

"""
由于获取用户管理相关信息的接口比较基础，所以直接使用 requests 库进行请求，避免循环依赖。
"""


def request_user_api(
    bk_tenant_id: str, method: str, path: str, username: str | None = None, params: Mapping[str, Any] | None = None
) -> Any:
    """请求用户API"""
    config = get_config()

    method = method.upper()
    base_url = str(config.blueking.api_url).rstrip("/")
    path = path.lstrip("/")
    url = f"{base_url}/api/bk-user/prod/{path}"

    # 构建请求头
    headers = {
        "Content-Type": "application/json",
        "X-Bk-Tenant-Id": bk_tenant_id,
        "X-Bkapi-Authorization": json.dumps(
            {
                "bk_app_code": config.blueking.app_code,
                "bk_app_secret": config.blueking.app_secret,
                "bk_username": username or "admin",
            }
        ),
    }

    request_kwargs: dict[str, Any] = {
        "url": url,
        "method": method,
        "headers": headers,
        "verify": False,
    }

    # 根据请求方法设置请求参数
    if params:
        if method == "GET":
            request_kwargs["params"] = params
        elif method == "POST":
            request_kwargs["json"] = params
        else:
            raise ValueError(f"不支持的请求方法: {method}")

    # 发送请求
    response = requests.request(**request_kwargs)

    # 检查响应状态
    try:
        response.raise_for_status()
    except requests.HTTPError:
        logger.error(
            f"BkApiError [Module: user][Action: {path}][Status Code: {response.status_code}] get error: {response.text}",
            extra=dict(bk_tenant_id=bk_tenant_id, method=method, path=path, username=username, params=params),
        )
        raise BkApiError(
            module="user",
            action=path,
            method=method,
            url=url,
            message=response.text,
            status_code=response.status_code,
        )

    return response.json()


def list_tenant() -> list[dict[str, Any]]:
    """查询租户列表"""
    # 如果使用esb，则直接返回默认租户
    if not get_config().blueking.enable_multi_tenancy:
        return [{"id": "system", "name": "Blueking", "status": "enabled"}]

    return request_user_api(bk_tenant_id=DEFAULT_TENANT_ID, method="GET", path="api/v3/open/tenants/", username="admin")


def list_tenant_variables(bk_tenant_id: str) -> list[dict[str, Any]]:
    """查询租户变量列表"""
    # todo check response
    return request_user_api(
        bk_tenant_id=DEFAULT_TENANT_ID,
        method="GET",
        path="/api/v3/open/tenant/common-variables/",
        params={"bk_tenant_id": bk_tenant_id},
        username="admin",
    )


@lru_cache(maxsize=1024)
def get_tenant_admin_username(bk_tenant_id: str) -> str:
    """获取租户管理员用户名

    Note:
        正常情况下相关信息不会变化，所以直接缓存结果。
    """

    # 非多租户模式下，直接返回默认管理员用户名
    if not get_config().blueking.enable_multi_tenancy:
        return "admin"

    result = request_user_api(
        bk_tenant_id=bk_tenant_id,
        method="GET",
        path="api/v3/open/tenant/virtual-users/-/lookup/",
        username="admin",
        params={"lookup_field": "login_name", "lookups": "bk_admin"},
    )
    return result["data"][0]["bk_username"]


@lru_cache(maxsize=1024)
def get_tenant_default_bk_biz_id(bk_tenant_id: str) -> int:
    """获取租户默认业务ID

    Note:
        正常情况下相关信息不会变化，所以直接缓存结果。
    """

    # 非多租户模式下，直接返回默认业务ID
    if not get_config().blueking.enable_multi_tenancy:
        return DEFAULT_BK_BIZ_ID

    result = request_user_api(
        bk_tenant_id=bk_tenant_id,
        method="GET",
        path="api/v3/open/tenant/common-variables/",
        username=get_tenant_admin_username(bk_tenant_id=bk_tenant_id),
        params={"name": "default_bk_biz_id"},
    )

    for variable in result["data"]:
        if variable["name"] == "default_bk_biz_id":
            return int(variable["value"])

    raise ValueError(f"租户 {bk_tenant_id} 没有默认业务ID")


@lru_cache(maxsize=1024)
def get_user_display_info(bk_tenant_id: str, bk_username: str) -> dict[str, str]:
    """查询用户展示信息

    Note:
        正常情况下相关信息不会变化，所以直接缓存结果。
    """

    # 非多租户模式下，直接返回默认管理员用户名
    if not get_config().blueking.enable_multi_tenancy:
        return {"bk_username": bk_username, "display_name": bk_username}

    result = request_user_api(
        bk_tenant_id=bk_tenant_id,
        method="GET",
        path="api/v3/open/tenant/virtual-users/-/lookup/",
        username="admin",
        params={"bk_usernames": bk_username},
    )
    return {"bk_username": result["data"][0]["bk_username"], "display_name": result["data"][0]["display_name"]}


def list_tenant_users(
    bk_tenant_id: str,
    page: int = 1,
    page_size: int = 100,
    username: str | None = None,
) -> dict[str, Any]:
    """查询租户用户列表

    :param bk_tenant_id: 租户ID
    :param page: 页码，默认为1
    :param page_size: 每页数量，默认为100
    :param username: 请求用户名，默认使用租户管理员
    :return: 包含 count 和 results 的字典，results 中每个用户包含：
        - bk_username: 蓝鲸用户名
        - login_name: 登录名
        - full_name: 全名
        - display_name: 显示名
        - status: 用户状态
    """
    # request_username = username or get_tenant_admin_username(bk_tenant_id=bk_tenant_id)

    result = request_user_api(
        bk_tenant_id=bk_tenant_id,
        method="GET",
        path="api/v3/open/tenant/users/",
        username="admin",
        params={"page": page, "page_size": page_size},
    )

    return result["data"]


def list_department(
    bk_tenant_id: str,
    page: int = 1,
    page_size: int = 100,
    username: str | None = None,
) -> dict[str, Any]:
    """查询部门列表

    :param bk_tenant_id: 租户ID
    :param page: 页码，默认为1
    :param page_size: 每页数量，默认为100
    :param username: 请求用户名，默认使用租户管理员
    :return: 包含 count 和 results 的字典，results 中每个部门包含：
        - name: 部门名
        - parent_id: 父部门ID，顶级部门为null或0
    """
    # request_username = username or get_tenant_admin_username(bk_tenant_id=bk_tenant_id)

    result = request_user_api(
        bk_tenant_id=bk_tenant_id,
        method="GET",
        path="api/v3/open/tenant/departments/",
        username="admin",
        params={"page": page, "page_size": page_size},
    )

    return result["data"]


def list_department_descendant(
    bk_tenant_id: str,
    department_id: int,
    page: int = 1,
    page_size: int = 100,
    max_level: int = 1,
    username: str | None = None,
) -> dict[str, Any]:
    """根据部门 ID 查询子部门列表信息

    :param bk_tenant_id: 租户ID
    :param department_id: 部门唯一标识，若为 0 则查询根部门
    :param page: 页码，默认为1
    :param page_size: 每页数量，默认为100
    :param max_level: 递归子部门的最大相对 Level 层级，默认为 1，即直接子部门
    :param username: 请求用户名，默认使用租户管理员
    :return: 包含 count 和 results 的字典，results 中每个部门包含：
        - name: 部门名
        - parent_id: 父部门ID，顶级部门为null或0
    """
    # request_username = username or get_tenant_admin_username(bk_tenant_id=bk_tenant_id)

    result = request_user_api(
        bk_tenant_id=bk_tenant_id,
        method="GET",
        path=f"/api/v3/open/tenant/departments/{department_id}/descendants/",
        username="admin",
        params={"page": page, "page_size": page_size, "max_level": max_level},
    )

    return result["data"]


def list_department_user(
    bk_tenant_id: str,
    department_id: int,
    page: int = 1,
    page_size: int = 100,
    username: str | None = None,
) -> dict[str, Any]:
    """根据部门 ID 查询部门下的用户列表

    :param bk_tenant_id: 租户ID
    :param department_id: 部门唯一标识，若为 0 则查询根部门
    :param page: 页码，默认为1
    :param page_size: 每页数量，默认为100
    :param username: 请求用户名，默认使用租户管理员
    :return: 包含 count 和 results 的字典，results 中每个部门包含：
        - bk_username: 唯一用户名
        - login_name: 蓝鲸用户名
        - full_name: 全名
        - display_name: 显示名
        - status: 用户状态
    """
    # request_username = username or get_tenant_admin_username(bk_tenant_id=bk_tenant_id)

    result = request_user_api(
        bk_tenant_id=bk_tenant_id,
        method="GET",
        path=f"/api/v3/open/tenant/departments/{department_id}/users/",
        username="admin",
        params={"page": page, "page_size": page_size},
    )

    return result["data"]


def list_user_department(
    bk_username: str,
    with_ancestors: bool = False,
    bk_tenant_id: str = None,
) -> dict[str, Any]:
    """根据部门 ID 查询部门下的用户列表

    :param bk_username: 蓝鲸用户唯一标识
    :param with_ancestors: 是否查询祖先部门
    :param bk_tenant_id: 租户ID
    :return: 包含 count 和 results 的字典，results 中每个部门包含：
        - id: 部门ID
        - name: 部门名称
        - ancestors: 祖先部门列表，列表中的每个元素为用户部门的祖先部门信息，默认以降序排列（从根部门 -> 直接上级部门），例如：若用户部门为
            小组AAA，父部门为中心AA，那么祖先部门列表中的顺序可以为公司 -> 部门A -> 中心AA。
            - id: 部门ID
            - name: 部门名称
            - ancestors: 祖先部门列表
    """
    # request_username = username or get_tenant_admin_username(bk_tenant_id=bk_tenant_id)

    result = request_user_api(
        bk_tenant_id=bk_tenant_id,
        method="GET",
        path=f"/api/v3/open/tenant/users/{bk_username}/departments/",
        username="admin",
        params={"with_ancestors": with_ancestors},
    )

    return result["data"]


def batch_query_user_sensitive_info(
    bk_tenant_id: str,
    bk_usernames: list[str],
    username: str | None = None,
) -> list[dict[str, Any]]:
    """批量查询用户敏感信息

    :param bk_tenant_id: 租户ID
    :param bk_usernames: 蓝鲸用户名列表
    :param username: 请求用户名，默认使用admin
    :return: 用户敏感信息列表，每个用户包含：
        - bk_username: 蓝鲸用户名
        - phone: 手机号
        - phone_country_code: 手机国家区号
        - email: 邮箱
        - wx_userid: 微信用户ID
    """
    result = request_user_api(
        bk_tenant_id=bk_tenant_id,
        method="GET",
        path="api/v3/open/tenant/users/-/sensitive-infos/",
        username=username or "admin",
        params={"bk_usernames": ",".join(bk_usernames)},
    )

    return result["data"]


def list_departments(
    bk_tenant_id: str,
    page: int = 1,
    page_size: int = 100,
    username: str | None = None,
) -> dict[str, Any]:
    """查询部门列表

    :param bk_tenant_id: 租户ID
    :param page: 页码，默认为1
    :param page_size: 每页数量，默认为100
    :param username: 请求用户名，默认使用admin
    :return: 包含 count 和 results 的字典，results 中每个部门包含：
        - id: 部门ID
        - name: 部门名称
        - parent_id: 父部门ID，顶级部门为null
    """
    result = request_user_api(
        bk_tenant_id=bk_tenant_id,
        method="GET",
        path="api/v3/open/tenant/departments/",
        username=username or "admin",
        params={"page": page, "page_size": page_size},
    )

    return result["data"]


def batch_lookup_departments(
    bk_tenant_id: str,
    department_ids: list[int],
    with_organization_path: bool = False,
    username: str | None = None,
) -> list[dict[str, Any]]:
    """批量查询部门信息

    :param bk_tenant_id: 租户ID
    :param department_ids: 部门ID列表
    :param with_organization_path: 是否返回组织路径，默认为False
    :param username: 请求用户名，默认使用admin
    :return: 部门信息列表，每个部门包含：
        - id: 部门ID
        - name: 部门名称
        - organization_path: 组织路径（当with_organization_path为True时）
    """
    params: dict[str, Any] = {
        "department_ids": ",".join(str(dept_id) for dept_id in department_ids),
    }
    if with_organization_path:
        params["with_organization_path"] = "true"

    result = request_user_api(
        bk_tenant_id=bk_tenant_id,
        method="GET",
        path="api/v3/open/tenant/departments/-/lookup/",
        username=username or "admin",
        params=params,
    )

    return result["data"]


def list_department_users(
    bk_tenant_id: str,
    department_id: int,
    page: int = 1,
    page_size: int = 100,
    username: str | None = None,
) -> dict[str, Any]:
    """查询部门用户列表

    :param bk_tenant_id: 租户ID
    :param department_id: 部门ID
    :param page: 页码，默认为1
    :param page_size: 每页数量，默认为100
    :param username: 请求用户名，默认使用admin
    :return: 包含 count 和 results 的字典，results 中每个用户包含：
        - bk_username: 蓝鲸用户名
        - login_name: 登录名
        - full_name: 全名
        - display_name: 显示名
        - status: 用户状态
    """
    result = request_user_api(
        bk_tenant_id=bk_tenant_id,
        method="GET",
        path=f"api/v3/open/tenant/departments/{department_id}/users/",
        username=username or "admin",
        params={"page": page, "page_size": page_size},
    )

    return result["data"]


def get_user_info(bk_tenant_id: str, bk_username: str) -> dict[str, Any]:
    """
    获取用户信息，兼容 ESB bk_login.get_user 的返回格式。

    APIGW 需要组合两个接口：
    1. api/v3/open/tenant/users/-/lookup/ - 获取基础信息
    2. api/v3/open/tenant/users/-/sensitive-infos/ - 获取敏感信息（phone, email, wx_userid）

    :param bk_tenant_id: 租户ID
    :param bk_username: 要查询的用户名
    :return: 用户信息字典，格式与 ESB bk_login.get_user 兼容：
        - bk_username: 蓝鲸用户名
        - chname: 中文名（display_name）
        - phone: 手机号
        - email: 邮箱
        - wx_userid: 微信用户ID
        - language: 语言（默认 zh-cn）
        - time_zone: 时区（默认 Asia/Shanghai）
    """
    user_info: dict[str, Any] = {
        "bk_username": bk_username,
        "chname": "",
        "phone": "",
        "email": "",
        "wx_userid": "",
        "language": "zh-cn",
        "time_zone": "Asia/Shanghai",
    }

    try:
        basic_result = request_user_api(
            bk_tenant_id=bk_tenant_id,
            method="GET",
            path="api/v3/open/tenant/users/-/lookup/",
            username="admin",
            params={"lookup_field": "bk_username", "lookups": bk_username},
        )
        if basic_result.get("data"):
            basic_info = basic_result["data"][0]
            user_info["chname"] = basic_info.get("display_name", "")
    except Exception:
        logger.warning(f"Failed to get basic user info for {bk_username}")

    try:
        sensitive_result = request_user_api(
            bk_tenant_id=bk_tenant_id,
            method="GET",
            path="api/v3/open/tenant/users/-/sensitive-infos/",
            username="admin",
            params={"bk_usernames": bk_username},
        )
        if sensitive_result.get("data"):
            sensitive_info = sensitive_result["data"][0]
            user_info["phone"] = sensitive_info.get("phone", "")
            user_info["email"] = sensitive_info.get("email", "")
            user_info["wx_userid"] = sensitive_info.get("wx_userid", "")
    except Exception:
        logger.warning(f"Failed to get sensitive user info for {bk_username}")

    return user_info
