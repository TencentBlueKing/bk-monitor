import logging
from abc import ABC, abstractmethod
from typing import Any
from datetime import timedelta

from django.utils import timezone

from apps.constants import ApiTokenAuthType
from apps.log_commons.models import ApiAuthToken, TokenAccessRecord
from apps.utils.local import get_request_username, get_request
from apps.log_commons.constants import TOKEN_REQUEST_LIMIT_SECONDS, TOKEN_REQUEST_LIMIT_COUNT
from apps.iam import Permission, ActionEnum, ResourceEnum

logger = logging.getLogger()


class BaseTokenHandler(ABC):
    """
    Token处理器抽象基类
    """

    @abstractmethod
    def get_token_type(self) -> str:
        """获取token类型"""
        pass

    @abstractmethod
    def create_token_params(self, **kwargs) -> dict[str, Any]:
        """创建token参数字典"""
        pass

    @abstractmethod
    def check_permission(self, **kwargs) -> bool:
        """检查权限"""
        pass

    def get_or_create_token(self, space_uid: str, **kwargs) -> dict[str, Any]:
        """获取或创建token"""
        username = get_request_username()

        # 查找现有令牌
        token_obj = ApiAuthToken.objects.filter(
            space_uid=space_uid,
            type=self.get_token_type(),
            params__contains=self.create_token_params(**kwargs),
            created_by=username,
        ).first()

        if token_obj:
            return {"token": token_obj.token}

        # 创建新 token
        token_obj = ApiAuthToken.objects.create(
            space_uid=space_uid,
            type=self.get_token_type(),
            params=self.create_token_params(**kwargs),
        )
        return {"token": token_obj.token}

    def check_rate_limit(self, username: str) -> bool:
        """检查频率限制"""
        current_time = timezone.now()
        limit_start_time = current_time - timedelta(seconds=TOKEN_REQUEST_LIMIT_SECONDS)

        recent_requests = TokenAccessRecord.objects.filter(
            created_by=username, created_at__gte=limit_start_time, created_at__lte=current_time
        ).count()

        return recent_requests < TOKEN_REQUEST_LIMIT_COUNT

    def record_access(self, username: str, token: str):
        """记录访问记录"""
        TokenAccessRecord.objects.create(
            created_by=username,
            token=token,
        )

    def generate_token(self, space_uid: str, **kwargs) -> dict[str, Any]:
        """生成token的完整流程"""
        username = get_request_username()

        # 检查权限
        if not self.check_permission(space_uid=space_uid, **kwargs):
            return {"token": None}

        # 检查频率限制
        if not self.check_rate_limit(username):
            logger.warning("User %s exceeded rate limit for token requests in space %s", username, space_uid)
            raise Exception(f"申请频率过高，请在 {TOKEN_REQUEST_LIMIT_SECONDS} 秒后再试")

        # 生成token
        token_data = self.get_or_create_token(space_uid, **kwargs)

        # 记录申请记录
        self.record_access(username, token_data["token"])

        return {"token": token_data["token"]}


class CodeccTokenHandler(BaseTokenHandler):
    """CodeCC Token处理器"""

    def get_token_type(self) -> str:
        return ApiTokenAuthType.CODECC.value

    def create_token_params(self, **kwargs) -> dict[str, Any]:
        index_set_id = kwargs.get("index_set_id")
        if not index_set_id:
            raise ValueError("index_set_id is required for CodeCC token")

        return {"index_set_id": index_set_id}

    def check_permission(self, **kwargs) -> bool:
        # 当前是专门对 codecc场景 鉴权，直接把要判定的操作和资源写死
        space_uid = kwargs.get("space_uid")
        index_set_id = kwargs.get("index_set_id")

        if not space_uid or not index_set_id:
            return False

        request = get_request(peaceful=True)
        if not request:
            # request获取失败默认无权限
            return False

        # 检查用户对指定索引集的检索权限
        try:
            permission = Permission(username=get_request_username())
            permission_result = permission.is_allowed(
                action=ActionEnum.SEARCH_LOG,
                resources=[ResourceEnum.INDICES.create_simple_instance(instance_id=index_set_id)],
            )
            return permission_result
        except Exception as e:
            logger.error(
                "Permission check failed for user %s on index_set %s: %s", get_request_username(), index_set_id, str(e)
            )
            return False


class TokenHandlerFactory:
    """Token处理器工厂类"""

    _handlers = {
        ApiTokenAuthType.CODECC.value: CodeccTokenHandler,
    }

    @classmethod
    def get_handler(cls, token_type: str) -> BaseTokenHandler:
        """根据token类型获取对应的处理器实例"""
        handler_class = cls._handlers.get(token_type)
        if not handler_class:
            supported_types = list(cls._handlers.keys())
            raise ValueError(f"Unsupported token type: {token_type}. Supported types: {supported_types}")

        return handler_class()

    @classmethod
    def register_handler(cls, token_type: str, handler_class: type):
        """注册新的token处理器"""
        if not issubclass(handler_class, BaseTokenHandler):
            raise ValueError("Handler class must inherit from BaseTokenHandler")

        cls._handlers[token_type] = handler_class
