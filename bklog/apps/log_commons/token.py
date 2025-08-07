import logging
from abc import ABC, abstractmethod
from typing import Any
from apps.constants import ApiTokenAuthType
from apps.log_commons.models import ApiAuthToken, TokenAccessRecord
from apps.utils.local import get_request_username
from apps.iam import Permission, ActionEnum, ResourceEnum

logger = logging.getLogger()


class BaseTokenHandler(ABC):
    """
    Token处理器抽象基类
    """

    @abstractmethod
    def get_token_type(self) -> str:
        """获取token类型"""
        raise NotImplementedError

    @abstractmethod
    def create_token_params(self, **kwargs) -> dict[str, Any]:
        """创建token参数字典"""
        raise NotImplementedError

    def get_or_create_token(self, space_uid: str, **kwargs) -> str:
        """获取或创建token"""
        username = get_request_username()
        token_params = self.create_token_params(**kwargs)

        # 查找现有令牌
        token_obj = ApiAuthToken.objects.filter(
            space_uid=space_uid,
            type=self.get_token_type(),
            params__contains=token_params,
            created_by=username,
        ).first()

        if token_obj:
            return token_obj.token

        # 创建新 token
        token_obj = ApiAuthToken.objects.create(
            space_uid=space_uid,
            type=self.get_token_type(),
            params=token_params,
            created_by=username,
        )
        return token_obj.token

    def record_access(self, username: str, token: str):
        """记录访问记录"""
        TokenAccessRecord.objects.update_or_create(
            created_by=username,
            token=token,
        )

    def generate_token(self, space_uid: str, **kwargs) -> str:
        """生成token的完整流程"""
        username = get_request_username()
        # 生成token
        token = self.get_or_create_token(space_uid, **kwargs)
        # 记录申请记录
        self.record_access(username, token)
        return token


class CodeccTokenHandler(BaseTokenHandler):
    """CodeCC Token处理器"""

    def get_token_type(self) -> str:
        return ApiTokenAuthType.CODECC.value

    def create_token_params(self, **kwargs) -> dict[str, Any]:
        index_set_id = kwargs.get("index_set_id")
        if not index_set_id:
            raise ValueError("index_set_id is required for CodeCC token")
        return {"index_set_id": index_set_id}

    @classmethod
    def check_index_set_search_permission(cls, username: str, index_set_id: int) -> None:
        """
        检查用户对指定索引集的检索权限
        参数:
            username: 用户名
            index_set_id: 索引集ID
        """
        permission = Permission(username=username)
        permission.is_allowed(
            action=ActionEnum.SEARCH_LOG,
            resources=[ResourceEnum.INDICES.create_simple_instance(instance_id=index_set_id)],
            raise_exception=True,
        )

    def generate_token(self, space_uid: str, **kwargs) -> str:
        """生成token的完整流程"""
        username = get_request_username()
        index_set_id = kwargs.get("index_set_id")
        # 检查当前用户对指定索引集的检索权限
        self.check_index_set_search_permission(username, index_set_id)
        # 调用父类的generate_token方法
        return super().generate_token(space_uid, **kwargs)


class TokenHandlerFactory:
    """Token处理器工厂类"""

    _HANDLERS = {
        ApiTokenAuthType.CODECC.value: CodeccTokenHandler,
    }

    @classmethod
    def get_handler(cls, token_type: str) -> BaseTokenHandler:
        """根据token类型获取对应的处理器实例"""
        handler_class = cls._HANDLERS.get(token_type)
        if not handler_class:
            supported_types = list(cls._HANDLERS.keys())
            raise ValueError(f"Unsupported token type: {token_type}. Supported types: {supported_types}")

        return handler_class()
