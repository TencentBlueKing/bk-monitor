"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import re
from collections.abc import Iterable
from functools import lru_cache
from typing import Any

import requests
from django.conf import settings
from django.utils.translation import gettext as _

from bkmonitor.utils.common_utils import chunks
from bkmonitor.utils.local import local
from bkmonitor.utils.request import get_request, get_request_tenant_id
from constants.common import DEFAULT_TENANT_ID
from core.errors.common import UserInfoMissing

logger = logging.getLogger(__name__)


LOGIN_NAME_WITH_DISPLAY_NAME_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9._-]*)\(")
LOGIN_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")


def get_request_user():
    """
    获取请求中的用户对象
    :return:
    """
    request = get_request(peaceful=True)
    if request:
        return request.user


def get_request_username():
    """基于request获取用户信息（web）"""
    user = get_request_user()
    if user:
        return user.username


def get_local_username():
    """从local对象中获取用户信息（celery）"""
    for user_key in ["bk_username", "username", "operator"]:
        username = getattr(local, user_key, None)
        if username is not None:
            return username


def set_local_username(username):
    local.username = username


@lru_cache(maxsize=1000)
def get_admin_username(bk_tenant_id: str) -> str | None:
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return getattr(settings, "COMMON_USERNAME", None)

    login_name = settings.BK_ADMIN_USERNAME
    return _lookup_admin_username(bk_tenant_id, "bk_admin" if login_name is None else login_name)


def single_tenant_backend_username(fallback):
    """单租户仅在显式配置登录名时解析系统调用身份。"""
    login_name = (settings.BK_ADMIN_USERNAME or "").strip()
    if settings.ENABLE_MULTI_TENANT_MODE or not login_name:
        return fallback
    return _lookup_admin_username("default", login_name)


@lru_cache(maxsize=1000)
def _lookup_admin_username(bk_tenant_id: str, login_name: str) -> str:
    from core.drf_resource import api

    # 获取管理员用户
    result = api.bk_login.batch_lookup_virtual_user(
        bk_tenant_id=bk_tenant_id, lookup_field="login_name", lookups=login_name, bk_username="admin"
    )
    if result and (username := result[0].get("bk_username")):
        return username
    raise ValueError(_("get_admin_username: 获取管理员用户失败"))


def get_backend_username(peaceful=True, bk_tenant_id: str = "") -> str | None:
    """从配置中获取用户信息"""

    if settings.ENABLE_MULTI_TENANT_MODE:
        if not bk_tenant_id:
            bk_tenant_id = get_request_tenant_id(peaceful=peaceful)

        if not bk_tenant_id:
            if not peaceful:
                raise ValueError(_("get_backend_username: 获取租户ID失败"))
            return None

        return get_admin_username(bk_tenant_id)
    return single_tenant_backend_username(getattr(settings, "COMMON_USERNAME", None))


def get_global_user(peaceful=True, bk_tenant_id: str = ""):
    # 1. 用户信息： 获取顺序：
    # 1.1 用户访问的request对象中的用户凭证
    # 1.2 local获取用户名
    # 1.3 系统配置的后台用户

    username = (
        get_request_username()
        or get_local_username()
        or get_backend_username(peaceful=peaceful, bk_tenant_id=bk_tenant_id)
    )

    if username:
        return username

    if not peaceful:
        raise UserInfoMissing


def make_userinfo(bk_tenant_id: str = DEFAULT_TENANT_ID):
    username = get_global_user(bk_tenant_id=bk_tenant_id)
    if username:
        return {"bk_username": username}

    raise ValueError(_("make_userinfo: 获取用户信息失败"))


def extract_login_name_from_display_name(display_name: str) -> str | None:
    """从用户展示名中提取可用于企业微信提醒的英文登录名。"""

    if not display_name:
        return None

    matched = LOGIN_NAME_WITH_DISPLAY_NAME_PATTERN.match(display_name)
    if matched:
        return matched.group(1)

    if LOGIN_NAME_PATTERN.fullmatch(display_name):
        return display_name

    return None


def resolve_biz_tenant_id(bk_biz_id: Any, context_label: str = "") -> str | None:
    """
    按业务 ID 解析所属租户 ID（面向无请求/无线程本地租户的后台动作链路）

    契约：
    1. 单租户模式返回 None（调用方不做跨系统展示名查询）；
    2. 非零业务 ID 优先走 bk_biz_id_to_bk_tenant_id：成功返回非空租户 ID，
       若业务 ID 非法、空间不存在或查询异常则记录 warning 并返回 None（由调用方直接回退原标识，
       不回落 DEFAULT_TENANT_ID 以杜绝跨租户同名账号串值）；
    3. 全局业务（0 / "0" / 空 / 未绑定业务）跳过 SpaceApi 查询，回退当前请求/本地租户或 DEFAULT_TENANT_ID。
    """
    if not settings.ENABLE_MULTI_TENANT_MODE:
        return None

    if isinstance(bk_biz_id, int | str) and not isinstance(bk_biz_id, bool) and bk_biz_id != "":
        try:
            biz_id = int(bk_biz_id)
        except (TypeError, ValueError) as error:
            logger.warning(
                "invalid bk_biz_id(%s) when resolving bk_tenant_id%s: %s",
                bk_biz_id,
                f" for {context_label}" if context_label else "",
                error,
            )
            return None

        if biz_id != 0:
            from bkmonitor.utils import tenant as tenant_utils

            try:
                tenant_id = tenant_utils.bk_biz_id_to_bk_tenant_id(biz_id)
            except Exception as error:
                logger.warning(
                    "resolve bk_tenant_id by bk_biz_id(%s) failed%s: %s",
                    bk_biz_id,
                    f" for {context_label}" if context_label else "",
                    error,
                )
                return None
            return tenant_id if isinstance(tenant_id, str) and tenant_id else None

    return get_request_tenant_id(peaceful=True) or DEFAULT_TENANT_ID


def _is_upstream_unavailable_error(error: BaseException) -> bool:
    """判断是否属网络超时/连接不可达类故障，用于中止后续分块叠加等待"""
    if isinstance(error, TimeoutError | requests.exceptions.Timeout | requests.exceptions.ConnectionError):
        return True

    error_text = str(error).lower()
    if "timeout" in error_text or "timed out" in error_text:
        return True

    # APIResource 捕获 ReadTimeout 后会转换成 BKAPIError，文本为中文「接口返回结果超时」，
    # 上面的英文关键词匹配不到。若只按英文判定，网络超时时分块中止逻辑不生效，
    # 后续分块会各自再等满一次超时，叠加放大等待时间，因此补中文判定。
    return "超时" in error_text


def batch_get_user_display_names(
    usernames: Iterable[Any],
    bk_tenant_id: str | None = None,
    *,
    strict_tenant: bool = False,
    upstream_state: dict[str, bool] | None = None,
) -> dict[str, str]:
    """
    批量获取用户展示名映射（{bk_username: display_name_or_raw}）

    - 单租户模式下恒等返回原用户名映射，不触发远端调用；
    - 多租户下按 100 人分批调用 batch_query_user_display_info 并固定传入 bk_tenant_id 隔离 CacheType.USER；
    - strict_tenant=True 时要求传入有效非空 bk_tenant_id，缺失时直接回退原值而不查默认租户；
    - 每个分块独立捕获异常防止单块脏数据连坐后续分块，遇到超时/连接不可达则提前中止后续分块；
    - upstream_state 为可选出参：本函数吞掉异常后调用方无从判断上游是否故障，
      需要跨租户批量调用时传入同一个 dict，函数会把「上游是否不可用」写入
      upstream_state["unavailable"]，调用方据此跳过后续调用方不再等待。
    """
    unique_usernames = list(dict.fromkeys(u for u in usernames if isinstance(u, str) and u))
    if not unique_usernames:
        return {}

    if not settings.ENABLE_MULTI_TENANT_MODE:
        return {u: u for u in unique_usernames}

    if strict_tenant:
        if not isinstance(bk_tenant_id, str) or not bk_tenant_id:
            return {u: u for u in unique_usernames}
        resolved_tenant_id = bk_tenant_id
    else:
        resolved_tenant_id = bk_tenant_id or get_request_tenant_id(peaceful=True) or DEFAULT_TENANT_ID

    from core.drf_resource import api

    display_map: dict[str, str] = {}
    for username_chunk in chunks(unique_usernames, 100):
        query_params: dict[str, Any] = {
            "bk_usernames": username_chunk,
            "bk_tenant_id": resolved_tenant_id,
        }
        try:
            for user_info in api.bk_login.batch_query_user_display_info(**query_params) or []:
                if not isinstance(user_info, dict):
                    continue
                username = user_info.get("bk_username")
                display_name = user_info.get("display_name")
                if isinstance(username, str) and username and isinstance(display_name, str) and display_name:
                    display_map[username] = display_name
        except Exception as error:
            logger.warning(
                "batch query user display info failed for tenant(%s), chunk_size(%s): %s",
                resolved_tenant_id,
                len(username_chunk),
                error,
            )
            if _is_upstream_unavailable_error(error):
                if upstream_state is not None:
                    upstream_state["unavailable"] = True
                break

    return {u: display_map.get(u, u) for u in unique_usernames}


def get_wxwork_mention_names(usernames: list[str], bk_tenant_id: str | None = None) -> dict[str, str]:
    """将多租户用户 ID 转换为企业微信提醒使用的英文登录名。"""

    if not settings.ENABLE_MULTI_TENANT_MODE:
        return {username: username for username in usernames}

    unique_usernames = [username for username in dict.fromkeys(usernames) if username and username != "all"]
    if not unique_usernames:
        return {}

    from core.drf_resource import api

    # 不复用 batch_get_user_display_names：两者的「查不到」契约相反——后者保证每个用户名都有值
    # （查不到回落原 UID），而企业微信 @ 的入参必须是英文登录名（见 extract_login_name_from_display_name
    # 的两个正则），UID 不保证符合该字符集，直接复用会把非法登录名混进名单。因此本函数只收录接口
    # 真实返回且能提取出登录名的用户，查不到的键直接缺席。
    # 注意：调用方 send.py 仍按 mention_map.get(user, user) 回退原标识，该回退是既有测试锁定的行为，
    # 由本函数返回值保证不了「一定不 @ 错人」，不要据此认为风险已消除。
    resolved_tenant_id = bk_tenant_id or get_request_tenant_id(peaceful=True) or DEFAULT_TENANT_ID
    user_display_info: list[dict[str, Any]] = []
    for username_chunk in chunks(unique_usernames, 100):
        query_params: dict[str, Any] = {
            "bk_usernames": username_chunk,
            "bk_tenant_id": resolved_tenant_id,
        }
        try:
            user_display_info.extend(api.bk_login.batch_query_user_display_info(**query_params) or [])
        except Exception as error:
            logger.warning(
                "batch query user display info for wxwork mention failed for tenant(%s), chunk_size(%s): %s",
                resolved_tenant_id,
                len(username_chunk),
                error,
            )
            if _is_upstream_unavailable_error(error):
                break

    mention_names: dict[str, str] = {}
    missing_login_names: list[str] = []
    for user_info in user_display_info:
        if not isinstance(user_info, dict):
            continue
        username = user_info.get("bk_username")
        mention_name = extract_login_name_from_display_name(user_info.get("display_name") or "")
        if isinstance(username, str) and username and mention_name:
            mention_names[username] = mention_name
        elif isinstance(username, str) and username:
            # 提取不到英文登录名（如纯中文展示名）时该用户会从 @ 名单中静默缺席，
            # 调用方按 mention_map.get(user, user) 回退成 UID，企微不会真正 @ 到人。
            # 这条日志是现场「@ 了但没提醒」的唯一线索，不要删。
            missing_login_names.append(username)

    if missing_login_names:
        logger.warning(
            "wxwork mention skip %d user(s) without extractable login_name for tenant(%s): %s",
            len(missing_login_names),
            resolved_tenant_id,
            missing_login_names[:20],
        )

    return mention_names


def get_user_display_name(username: str, bk_tenant_id: str | None = None) -> str:
    """
    获取用户展示名
    """
    if not isinstance(username, str) or not username:
        return username

    if "," in username:
        parts = [part for part in username.split(",") if part]
        if not parts:
            return ""
        if not settings.ENABLE_MULTI_TENANT_MODE:
            return ",".join(parts)
        # 与 _batch_convert_receivers 保持同一口径：无有效租户时回退原值，不查默认租户
        display_map = batch_get_user_display_names(parts, bk_tenant_id=bk_tenant_id, strict_tenant=True)
        return ",".join(display_map.get(part, part) for part in parts)

    if settings.ROLE == "web":
        request = get_request(peaceful=True)
        if request:
            # 仅当查询的是当前请求用户自身且租户一致时，才使用请求上下文避免额外远程查询
            if getattr(request.user, "username", None) == username and (
                bk_tenant_id is None or getattr(request.user, "tenant_id", None) == bk_tenant_id
            ):
                display_name = getattr(request.user, "display_name", None)
                if isinstance(display_name, str) and display_name:
                    return display_name

    if not settings.ENABLE_MULTI_TENANT_MODE:
        return username

    return batch_get_user_display_names([username], bk_tenant_id=bk_tenant_id).get(username, username)
