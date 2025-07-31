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
from datetime import datetime
from secrets import token_hex
import time
from typing import Any
from functools import partial

from apps.iam import Permission, ActionEnum, ResourceEnum
from apps.iam.exceptions import PermissionDeniedError
from apps.log_commons.models import ApiAuthToken, TokenAccessRecord
from apps.log_commons.constants import (
    TOKEN_LENGTH,
    CODECC_TOKEN_EXPIRE_SECONDS,
    DEFAULT_TOKEN_EXPIRE_SECONDS,
    CODECC_TOKEN_TYPE,
    DEFAULT_TOKEN_TYPE,
)
from apps.utils.local import get_request, get_request_username
from django.utils import timezone

# 获取logger
logger = logging.getLogger(__name__)

# 定义 codecc 权限映射
CodeccAuthMap = [
    {
        "resource": ResourceEnum.INDICES,
        "action": ActionEnum.SEARCH_LOG,
        "instance_id": "index_set_id",
    }
]


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
        if token_type == CODECC_TOKEN_TYPE:
            expire_time = int(time.time()) + CODECC_TOKEN_EXPIRE_SECONDS
            expire_period = "1d"
        else:
            expire_time = kwargs.get("expire_time", int(time.time() + DEFAULT_TOKEN_EXPIRE_SECONDS))
            expire_period = kwargs.get("expire_period", "7d")
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
    def get_or_create_token(space_uid: str, index_set_id: int, **kwargs) -> dict[str, Any]:
        """
        获取或创建 codecc 类型的令牌
        """
        token_type = kwargs.get("type", DEFAULT_TOKEN_TYPE)

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
    def _record_access_log(
        username: str, space_uid: str, index_set_id: int, action: str, result: str, error_message: str = None
    ):
        """
        记录访问日志
        """
        try:
            TokenAccessRecord.objects.create(
                created_by=username or "unknown",
                token=None,  # 这里设置为 None，因为这是权限检查记录，不是实际的 token 访问
            )
            logger.info(
                f"[CodeCC访问日志] 记录访问日志成功 - 用户: {username}, 空间ID: {space_uid}, 索引集ID: {index_set_id}, 动作: {action}, 结果: {result}"
            )
        except Exception as e:
            logger.error(
                f"[CodeCC访问日志] 记录访问日志失败 - 用户: {username}, 空间ID: {space_uid}, 索引集ID: {index_set_id}, 动作: {action}, 结果: {result}, 错误: {str(e)}"
            )

    @staticmethod
    def check_codecc_permission(space_uid: str, index_set_id: int) -> bool:
        """
        校验当前用户是否有 codecc 相关权限，并记录详细日志
        """
        request = get_request(peaceful=True)
        if not request:
            logger.error("[CodeCC权限校验] request 获取失败，直接判定无权限。")
            raise PermissionDeniedError(action_name="unknown", permission={}, apply_url="")
        username = get_request_username()
        request.token = None
        for auth_instance in CodeccAuthMap:
            resource = auth_instance["resource"]
            instance_id = index_set_id
            action = auth_instance["action"]
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
                    logger.warning(
                        f"[CodeCC权限校验] 用户 {username} 对索引集 {instance_id} 没有权限，记录访问日志。"
                        f"用户: {username}, 空间ID: {space_uid}, 索引集ID: {instance_id}, 动作: {action}"
                    )
                    # 记录无权限访问日志
                    CodeccHandler._record_access_log(username, space_uid, index_set_id, action, "denied")
                    raise PermissionDeniedError(action_name=action.name, permission={}, apply_url="")
            except Exception as e:
                logger.error(
                    f"[CodeCC权限校验] 权限校验过程中发生异常 - 用户: {username}, 索引集ID: {instance_id}, 空间ID: {space_uid}, 异常: {str(e)}"
                )
                # 记录异常访问日志
                CodeccHandler._record_access_log(username, space_uid, index_set_id, action, "error", str(e))
                raise PermissionDeniedError(action_name=action.name, permission={}, apply_url="")
        logger.info(f"[CodeCC权限校验] 用户 {username} 对索引集 {index_set_id} 权限校验通过")
        return True

    @staticmethod
    def get_codecc_token(space_uid: str, index_set_id: int, **kwargs) -> dict[str, Any]:
        """
        获取 CodeCC 令牌（包含权限校验）
        """
        try:
            CodeccHandler.check_codecc_permission(space_uid, index_set_id)
            # 有权限才生成token
            logger.info("[CodeCC权限校验] 最终结果：有权限，开始生成token。")
            token_data = CodeccHandler.get_or_create_token(space_uid, index_set_id, **kwargs)
            response_data = {
                "has_permission": True,
                "token": token_data["token"],
                "space_uid": space_uid,
                "index_set_id": index_set_id,
                "type": token_data.get("type", kwargs.get("type", DEFAULT_TOKEN_TYPE)),
                "expire_time": token_data["expire_time"],
                **{k: v for k, v in token_data.items() if k not in ["token", "expire_time", "type"]},
            }
            logger.info(f"[CodeCC权限校验] token 生成成功，返回数据: {response_data}")
            return response_data

        except PermissionDeniedError as e:
            logger.warning(
                f"[CodeCC权限校验] 最终结果：无权限，token 不生成。异常信息: {e.message}, "
                f"用户: {get_request_username()}, 空间ID: {space_uid}, 索引集ID: {index_set_id}"
            )
            params = {
                "lock_search": kwargs.get("lock_search", False),
                "start_time": kwargs.get("start_time"),
                "end_time": kwargs.get("end_time"),
                "default_time_range": kwargs.get("default_time_range", []),
                "expire_period": "1d",
                "data": kwargs.get("data", {}),
            }
            return {
                "has_permission": False,
                "token": None,
                "space_uid": space_uid,
                "index_set_id": index_set_id,
                "type": kwargs.get("type", DEFAULT_TOKEN_TYPE),
                "expire_time": None,
                **params,
            }
        except Exception as e:
            logger.error(
                f"[CodeCC权限校验] 获取token过程中发生未知异常 - 用户: {get_request_username()}, "
                f"空间ID: {space_uid}, 索引集ID: {index_set_id}, 异常: {str(e)}"
            )
            raise
