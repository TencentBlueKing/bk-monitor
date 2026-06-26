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
import hashlib
import hmac
import json
import logging
import secrets
import time
from urllib.parse import urlencode, quote

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import ValidationError

from bkm_space.utils import bk_biz_id_to_space_uid
from bkmonitor.models import TapdWorkspaceBinding
from bkmonitor.utils.cipher import AESCipher
from bkmonitor.utils.request import get_request_username, get_request
from fta_web.constants import TapdOauthEndpoint

logger = logging.getLogger("root")


def normalize_redirect_url(url: str, request=None) -> str:
    """将前端传入的重定向 URL 补全为绝对 URL。

    - 全 URL（以 http 开头）直接返回
    - 路径自动补 / 前缀（防 build_absolute_uri 基于当前请求路径拼接）
    - 有 request 时补域名，无 request 时仅补 / 前缀
    """
    if not url:
        return url
    if url.startswith("http"):
        return url
    # 路径必须以 / 开头，否则 build_absolute_uri 会基于当前请求路径拼接
    if not url.startswith("/"):
        url = "/" + url
    if request:
        url = request.build_absolute_uri(url)
    return url


def _get_cipher() -> AESCipher:
    return AESCipher(settings.SECRET_KEY)


def _make_token_key(tenant_id: str, username: str) -> str:
    """Redis key: tapd_uat:{tenant_id}:{username}"""
    return f"tapd_uat:{tenant_id}:{username}"


def _make_oauth_session_key(bk_biz_id) -> str:
    """Session key: tapd_oauth_state_{bk_biz_id}"""
    return f"tapd_oauth_state_{bk_biz_id}"


def _hmac_sign(data: bytes) -> str:
    """HMAC-SHA256 签名，截断 hex 16 字符。"""
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), data, hashlib.sha256).hexdigest()[:16]


def save_tapd_token(
    tenant_id: str,
    username: str,
    token_data: dict,
    expires_in: int = 7200,
    cipher: AESCipher | None = None,
) -> None:
    """加密并存储 TAPD 用户态 access_token 到 Redis。

    :param tenant_id: 蓝鲸租户 ID
    :param username: 请求用户名
    :param token_data: TAPD 原始 token 响应 {"access_token", "user_id", "type", ...}
    :param expires_in: 过期秒数（默认 7200）
    :param cipher: AESCipher 实例（可选，默认新构造）
    """
    if not tenant_id or not username:
        logger.warning("save_tapd_token rejected: tenant_id=%s username=%s", tenant_id, username)
        return

    cipher = cipher or _get_cipher()
    access_token = token_data.get("access_token", "")
    if not access_token:
        logger.warning("save_tapd_token rejected: empty access_token")
        return

    payload = {
        "access_token": access_token,
        "type": token_data.get("type", ""),
        "user_id": token_data.get("user_id", ""),
        "expires_at": int(time.time()) + expires_in,
    }

    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    encrypted = cipher.encrypt(raw).decode("utf-8")

    key = _make_token_key(tenant_id, username)
    cache.set(key, encrypted, timeout=expires_in)
    logger.info("Saved TAPD user-auth token to cache, key=%s, ttl=%s", key, expires_in)


def get_tapd_token(bk_tenant_id: str, username: str) -> dict:
    """从 Redis 取出并解密 TAPD 用户态 token。

    :return: {"access_token": str, "type": str, "user_id": str, "expires_at": int, ...}
             未找到或解密失败返回 {}
    """
    key = _make_token_key(bk_tenant_id, username)
    encrypted = cache.get(key)
    if not encrypted:
        return {}

    cipher = _get_cipher()
    try:
        raw = cipher.decrypt(encrypted)
        payload = json.loads(raw)
        return payload
    except Exception as e:
        logger.warning("Failed to decrypt TAPD token, key=%s, error=%s", key, e)
        # 清理脏数据，避免下次读取重复失败
        cache.delete(key)
        return {}


def delete_tapd_token(tenant_id: str, username: str) -> None:
    """删除 Redis 中的 TAPD 用户态 token（解绑/重新授权时调用）。"""
    key = _make_token_key(tenant_id, username)
    cache.delete(key)
    logger.info("Deleted TAPD user-auth token from cache, key=%s", key)


def generate_signed_state(payload: dict) -> str:
    """生成 signed_state 字符串：base64url(json).hex16(hmac_sha256)

    签名截断至 hex 16 字符，兼顾安全性与 URL 长度。
    payload 必须包含 exp（Unix 时间戳，建议 TTL = 15min）。
    """
    json_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(json_bytes).rstrip(b"=").decode("ascii")

    sig = _hmac_sign(b64_payload.encode("ascii"))
    return f"{b64_payload}.{sig}"


def verify_signed_state(signed_state: str) -> dict:
    """验证 signed_state，返回 payload dict；失败 raise ValidationError。

    此函数同时被 tapd_callbacks.py（B-03）复用。
    """
    try:
        b64_payload, signature = signed_state.rsplit(".", 1)
    except ValueError:
        raise ValidationError("invalid_signed_state_format")

    expected = _hmac_sign(b64_payload.encode("ascii"))
    if not hmac.compare_digest(expected, signature):
        raise ValidationError("invalid_signed_state_signature")

    # base64url decode
    pad = 4 - len(b64_payload) % 4
    if pad != 4:
        b64_payload += "=" * pad
    payload = json.loads(base64.urlsafe_b64decode(b64_payload.encode("ascii")))

    if payload.get("exp", 0) < time.time():
        raise ValidationError("signed_state_expired")

    # 校验必需字段
    required = (
        "bk_tenant_id",
        "space_uid",
        "bk_biz_id",
        "initiator",
        "exp",
        "success_url",
        "error_url",
    )
    missing = [k for k in required if k not in payload]
    if missing:
        raise ValidationError({"detail": f"missing_fields: {missing}"})
    return payload


def generate_install_url(
    bk_biz_id: int,
    bk_tenant_id: str,
    space_uid: str,
    initiator: str,
    success_url: str,
    error_url: str,
    backend_callback: str,
) -> str:
    """构建 open_app_install URL（B-01 install_url 模板）。

    :param bk_biz_id: 蓝鲸业务 ID
    :param bk_tenant_id: 租户 ID
    :param space_uid: 空间 UID
    :param initiator: 发起授权的用户
    :param success_url: 含 # 的真实前端地址，回调成功后 302 重定向目标
    :param error_url: 含 # 的前端错误页面地址，回调失败后 302 重定向目标
    :param backend_callback: 后端应用安装回调地址（由调用方通过 reverse + build_absolute_uri 构建）
    """
    if not backend_callback:
        raise ValidationError("backend_callback is empty")

    # 生成 signed_state（应用态），nonce 写入 session 供 B-03 回调校验
    nonce = secrets.token_urlsafe(8)
    payload = {
        "bk_biz_id": bk_biz_id,
        "bk_tenant_id": bk_tenant_id,
        "space_uid": space_uid,
        "initiator": initiator,
        "nonce": nonce,
        "exp": int(time.time()) + 900,  # 15min TTL
        "success_url": success_url,
        "error_url": error_url,
    }
    signed_state = generate_signed_state(payload)
    # cb 内嵌 signed_state，urlencode 会自动处理特殊字符编码
    cb = f"{backend_callback.rstrip('/')}?signed_state={signed_state}"
    params = {
        "client_id": settings.TAPD_APP_ID,
        # test=1 测试应用（未上架），test=0 正式应用（已上架）
        # 仅生产环境（prod）传 0，dev/stag 传 1
        "test": 0 if settings.ENVIRONMENT == "prod" else 1,
        # state 为 TAPD 协议必选参数，应用态回调不消费它（signed_state 已嵌在 cb 中）
        # 传 nonce 仅满足协议要求
        "state": nonce,
        # show_installed=1（显示已授权项目，便于管理员查看/重新授权）
        "show_installed": 1,
        "cb": cb,
    }
    url = TapdOauthEndpoint.open_app_install()
    return f"{url}?{urlencode(params)}#selected_workspace_id={{workspace_id}}"


def generate_auth_url(
    bk_biz_id: int,
    bk_tenant_id: str,
    success_url: str,
    error_url: str,
    backend_callback: str,
) -> str:
    """生成 TAPD 用户态 OAuth 授权 URL，state 使用 Session 存储的 nonce。

    :param bk_biz_id: 蓝鲸业务 ID
    :param issue_id: 需求 ID
    :param bk_tenant_id: 租户 ID
    :param success_url: 含 # 的真实前端地址，B-05 回调成功后 302 重定向目标
    :param error_url: 含 # 的前端错误页面地址，B-05 回调失败后 302 重定向目标
    :param backend_callback: 后端 OAuth 回调地址（由调用方通过 build_absolute_uri 构建）
    """
    if not backend_callback:
        raise ValidationError("backend_callback is empty")

    # state 使用随机 nonce，写入 Session 供 B-05 回调校验
    request = get_request()
    if not request:
        raise ValidationError("request context is empty")

    nonce = secrets.token_urlsafe(16)
    state = f"{nonce}:{bk_biz_id}"
    # backend_callback 统一去掉末尾斜杠，确保 authorize 和 exchange token 时完全一致
    backend_callback = backend_callback.rstrip("/")
    request.session[_make_oauth_session_key(bk_biz_id)] = {
        "nonce": nonce,
        "bk_biz_id": bk_biz_id,
        "bk_tenant_id": bk_tenant_id,
        "username": get_request_username(),
        "success_url": success_url,
        "error_url": error_url,
        "backend_callback": backend_callback,
        "exp": int(time.time()) + 900,  # 15min TTL
    }

    backend_callback = quote(backend_callback, safe="")
    scope = quote("story#read story#write bug#read bug#write", safe="")
    state = quote(state, safe="")
    return (
        f"{TapdOauthEndpoint.authorize()}"
        f"?response_type=code"
        f"&client_id={settings.TAPD_APP_ID}"
        f"&redirect_uri={backend_callback}"
        f"&scope={scope}"
        f"&state={state}"
        f"&auth_by=user"
    )


def try_bind_importable(
    workspace_id: str,
    bk_biz_id: int,
    bk_tenant_id: str,
    create_user: str,
) -> bool:
    """尝试为 importable 状态的项目创建本地 binding。

    成功 → 返回 True，is_bound 最终显示为 bound
    失败 → 返回 False，is_bound 保持 importable（静默失败）
    """
    try:
        TapdWorkspaceBinding.objects.get_or_create(
            bk_tenant_id=bk_tenant_id,
            space_uid=bk_biz_id_to_space_uid(bk_biz_id),
            tapd_workspace_id=workspace_id,
            defaults={
                "bk_biz_id": bk_biz_id,
                "tapd_workspace_name": "",
                "create_user": create_user,
                "update_user": create_user,
            },
        )
        return True
    except Exception as e:
        logger.warning("try_bind_importable failed: ws=%s biz=%s error=%s", workspace_id, bk_biz_id, e)
        return False
