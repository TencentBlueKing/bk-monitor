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

import logging
from datetime import datetime, timedelta
from secrets import token_hex
import time
from typing import Any
from functools import partial

from apps.iam import Permission, ActionEnum, ResourceEnum
from apps.log_commons.models import ApiAuthToken, TokenAccessRecord
from apps.log_commons.constants import (
    TOKEN_LENGTH,
    CODECC_TOKEN_EXPIRE_SECONDS,
    DEFAULT_TOKEN_EXPIRE_SECONDS,
    EXPIRE_PERIOD_ONE_DAY,
    EXPIRE_PERIOD_SEVEN_DAYS,
    TOKEN_REQUEST_LIMIT_COUNT,
    TOKEN_REQUEST_LIMIT_SECONDS,
)
from apps.constants import ApiTokenAuthType
from apps.utils.local import get_request, get_request_username
from django.utils import timezone

# 获取logger
logger = logging.getLogger(__name__)

# 定义 codecc 权限映射
CodeccAuthMap = {
    ApiTokenAuthType.CODECC.value: [
        {"action": ActionEnum.SEARCH_LOG, "resource": ResourceEnum.INDICES, "instance_id": "index_set_id"}
    ]
}


class CodeccHandler:
    """
    CodeCC 令牌处理器
    """

    @staticmethod
    def _generate_unique_token() -> str:
        """
        生成唯一的token
        """
        exist_tokens = list(ApiAuthToken.objects.all().values_list("token", flat=True).distinct())
        token = partial(token_hex, TOKEN_LENGTH)()
        while token in exist_tokens:
            token = partial(token_hex, TOKEN_LENGTH)()
        return token

    @staticmethod
    def _get_token_expire_config(token_type: str, **kwargs) -> tuple[int, str]:
        """
        获取token过期时间配置
        """
        if token_type == ApiTokenAuthType.CODECC.value:
            expire_time = int(time.time()) + CODECC_TOKEN_EXPIRE_SECONDS
            expire_period = EXPIRE_PERIOD_ONE_DAY
        else:
            expire_time = kwargs.get("expire_time", int(time.time() + DEFAULT_TOKEN_EXPIRE_SECONDS))
            expire_period = kwargs.get("expire_period", EXPIRE_PERIOD_SEVEN_DAYS)
        return expire_time, expire_period

    @staticmethod
    def _create_token_params(index_set_id: int, expire_period: str, **kwargs) -> dict[str, Any]:
        """
        创建token参数字典
        """
        return {
            "index_set_id": index_set_id,
            "lock_search": kwargs.get("lock_search", False),
            "start_time": kwargs.get("start_time"),
            "end_time": kwargs.get("end_time"),
            "default_time_range": kwargs.get("default_time_range", []),
            "expire_period": expire_period,
            "data": kwargs.get("data", {}),
            "created_by": get_request_username(),
            "created_at": datetime.now().isoformat(),
        }

    @staticmethod
    def _log_token_operation(operation: str, token: str, space_uid: str, index_set_id: int, token_type: str, **kwargs):
        """
        记录token操作日志
        """
        extra_info = kwargs.get("extra_info", "")
        logger.info(
            f"[CodeCC Token] {operation}, token={token}, space_uid={space_uid}, "
            f"index_set_id={index_set_id}, type={token_type}{extra_info}"
        )

    @staticmethod
    def _check_request_frequency_limit(username: str, space_uid: str, index_set_id: int) -> bool:
        """
        检查用户申请token的频率限制
        返回True表示未超过限制，可以继续申请；返回False表示超过限制，不能申请
        """
        current_time = timezone.now()
        limit_start_time = current_time - timedelta(seconds=TOKEN_REQUEST_LIMIT_SECONDS)

        # 查询用户在指定时间窗口内的申请记录
        recent_requests = TokenAccessRecord.objects.filter(
            created_by=username, created_at__gte=limit_start_time, created_at__lte=current_time
        ).count()

        if recent_requests >= TOKEN_REQUEST_LIMIT_COUNT:
            logger.warning(
                f"[CodeCC频率限制] 用户 {username} 在 {TOKEN_REQUEST_LIMIT_SECONDS} 秒内已申请 {recent_requests} 次token，"
                f"超过限制 {TOKEN_REQUEST_LIMIT_COUNT} 次。空间ID: {space_uid}, 索引集ID: {index_set_id}"
            )
            return False

        logger.info(
            f"[CodeCC频率限制] 用户 {username} 在 {TOKEN_REQUEST_LIMIT_SECONDS} 秒内已申请 {recent_requests} 次token，"
            f"未超过限制 {TOKEN_REQUEST_LIMIT_COUNT} 次。空间ID: {space_uid}, 索引集ID: {index_set_id}"
        )
        return True

    @staticmethod
    def get_or_create_token(space_uid: str, index_set_id: int, **kwargs) -> dict[str, Any]:
        """
        获取或创建 codecc 类型的令牌
        """
        token_type = kwargs.get("type", ApiTokenAuthType.CODECC.value)

        # 查找现有令牌
        token_obj = ApiAuthToken.objects.filter(
            space_uid=space_uid, type=token_type, params__index_set_id=index_set_id
        ).first()

        if token_obj:
            if token_obj.is_expired():
                CodeccHandler._log_token_operation(
                    "已存在但已过期", token_obj.token, space_uid, index_set_id, token_type
                )
            else:
                CodeccHandler._log_token_operation(
                    "已存在且未过期，直接复用", token_obj.token, space_uid, index_set_id, token_type
                )
                return {
                    "token": token_obj.token,
                    "expire_time": int(token_obj.expire_time.timestamp()),
                    **token_obj.params,
                }

        # 生成新 token
        token = CodeccHandler._generate_unique_token()
        expire_time, expire_period = CodeccHandler._get_token_expire_config(token_type, **kwargs)
        aware_expire_time = timezone.make_aware(datetime.fromtimestamp(expire_time))

        create_params = {
            "space_uid": space_uid,
            "type": token_type,
            "token": token,
            "expire_time": aware_expire_time,
            "params": CodeccHandler._create_token_params(index_set_id, expire_period, **kwargs),
        }

        token_obj = ApiAuthToken.objects.create(**create_params)
        CodeccHandler._log_token_operation(
            "正常新生成",
            token_obj.token,
            space_uid,
            index_set_id,
            token_type,
            extra_info=f", expire_time={aware_expire_time}",
        )
        return {"token": token_obj.token, "expire_time": int(token_obj.expire_time.timestamp()), **token_obj.params}

    @staticmethod
    def check_codecc_permission(space_uid: str, index_set_id: int) -> bool:
        """
        校验当前用户是否有 codecc 相关权限，并记录详细日志
        """
        request = get_request(peaceful=True)
        if not request:
            logger.error("[CodeCC权限校验] request 获取失败，直接判定无权限。")
            return False

        username = get_request_username()
        request.token = None
        has_permission = True

        token = getattr(request, "codecc_token_info", {}).get("token")
        token_type = ApiAuthToken.objects.get(token=token).type if token else ApiTokenAuthType.CODECC.value
        logger.info(f"[CodeCC权限校验] token 类型: {token_type}")

        for auth_instance in CodeccAuthMap[token_type]:
            resource = auth_instance["resource"]
            action = auth_instance["action"]
            instance_id = index_set_id
            attribute = {"space_uid": space_uid}

            logger.info(
                f"[CodeCC权限校验] 开始校验权限 - 用户: {username}, 索引集ID: {instance_id}, 空间ID: {space_uid}, 动作: {action}"
            )

            try:
                permission_result = Permission(username=username).is_allowed(
                    action=action,
                    resources=[resource.create_simple_instance(instance_id=instance_id, attribute=attribute)],
                )
                logger.info(f"[CodeCC权限校验] 权限校验结果: {permission_result}")

                if not permission_result:
                    has_permission = False
                    logger.warning(
                        f"[CodeCC权限校验] 用户 {username} 对索引集 {instance_id} 没有权限。"
                        f"用户: {username}, 空间ID: {space_uid}, 索引集ID: {instance_id}, 动作: {action}"
                    )
                    # 记录无权限访问日志
                    TokenAccessRecord.objects.update_or_create(
                        defaults={"updated_at": datetime.now()},
                        created_by=username or "unknown",
                        token="",
                    )
                    break
            except Exception as e:
                logger.error(
                    f"[CodeCC权限校验] 权限校验过程中发生异常 - 用户: {username}, 索引集ID: {instance_id}, 空间ID: {space_uid}, 异常: {str(e)}"
                )
                has_permission = False
                # 记录异常访问日志
                TokenAccessRecord.objects.update_or_create(
                    defaults={"updated_at": datetime.now()},
                    created_by=username or "unknown",
                    token="",
                )
                break

        if has_permission:
            logger.info(f"[CodeCC权限校验] 用户 {username} 对索引集 {index_set_id} 权限校验通过")
        else:
            logger.warning(f"[CodeCC权限校验] 用户 {username} 对索引集 {index_set_id} 权限校验失败")

        return has_permission

    @staticmethod
    def get_codecc_token(space_uid: str, index_set_id: int, **kwargs) -> dict[str, Any]:
        """
        获取 CodeCC 令牌（包含权限校验和频率限制）
        """
        username = get_request_username()
        has_permission = CodeccHandler.check_codecc_permission(space_uid, index_set_id)

        if has_permission:
            # 有权限，检查频率限制
            logger.info("[CodeCC权限校验] 最终结果：有权限，开始检查频率限制。")

            # 检查频率限制
            if not CodeccHandler._check_request_frequency_limit(username, space_uid, index_set_id):
                logger.warning(
                    f"[CodeCC频率限制] 用户 {username} 申请频率过高，拒绝生成token。"
                    f"空间ID: {space_uid}, 索引集ID: {index_set_id}"
                )
                return {"token": None, "error": f"申请频率过高，请在 {TOKEN_REQUEST_LIMIT_SECONDS} 秒后再试"}

            # 频率限制通过，生成token
            logger.info("[CodeCC频率限制] 频率限制检查通过，开始生成token。")
            token_data = CodeccHandler.get_or_create_token(space_uid, index_set_id, **kwargs)

            # 记录申请记录
            TokenAccessRecord.objects.create(
                created_by=username,
                token=token_data["token"],
            )

            response_data = {
                "token": token_data["token"],
            }
            logger.info(f"[CodeCC] token 生成成功，返回数据: {response_data}")
            return response_data
        else:
            # 无权限，不生成token
            logger.warning(
                f"[CodeCC权限校验] 最终结果：无权限，token 不生成。"
                f"用户: {username}, 空间ID: {space_uid}, 索引集ID: {index_set_id}"
            )
            return {
                "token": None,
            }
