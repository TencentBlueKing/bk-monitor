"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import timedelta
from typing import Any, cast

from django.utils import timezone
from rest_framework import serializers

from bkmonitor.models import ApiAuthToken
from bkmonitor.models.token import AuthType
from bkmonitor.utils.serializers import TenantIdField
from bkmonitor.utils.user import get_request_username
from core.drf_resource import Resource


class GetApiTokenResource(Resource):
    """
    获取API鉴权令牌
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
        type = serializers.ChoiceField(
            label="Token类型", default="as_code", choices=("as_code", "grafana", "entity", "user")
        )

    @staticmethod
    def get_or_create_user_token(bk_tenant_id: str, username: str):
        """
        获取或创建用户令牌，半年有效
        """

        # 先查询是否存在用户令牌
        auth_token = ApiAuthToken.objects.filter(
            create_user=username,
            type=AuthType.User,
            bk_tenant_id=bk_tenant_id,
        ).last()

        # 如果存在，检查是否过期
        if auth_token:
            if auth_token.expire_time and auth_token.expire_time < timezone.now():
                auth_token.delete()
                auth_token = None
            else:
                return auth_token.token

        # 如果不存在，则创建用户令牌
        return ApiAuthToken.objects.create(
            name=f"{bk_tenant_id}_{username}_user_token",
            create_user=username,
            type=AuthType.User,
            bk_tenant_id=bk_tenant_id,
            namespaces=["biz#all"],
            expire_time=timezone.now() + timedelta(days=180),
        ).token

    def perform_request(self, validated_request_data: dict[str, Any]):
        # 获取当前租户
        username = cast(str, get_request_username())
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        token_type = validated_request_data["type"]

        # 用户权限模式：创建用户令牌
        if token_type == "user":
            return self.get_or_create_user_token(bk_tenant_id=bk_tenant_id, username=username)

        # 其他权限模式：创建业务令牌
        bk_biz_id = validated_request_data.get("bk_biz_id")
        if not bk_biz_id:
            raise serializers.ValidationError("业务ID不能为空")

        token = ApiAuthToken.objects.filter(
            namespaces__contains=f"biz#{validated_request_data['bk_biz_id']}",
            type=validated_request_data["type"],
            bk_tenant_id=bk_tenant_id,
        ).last()

        if not token:
            token = ApiAuthToken.objects.create(
                create_user=username,
                name=f"{validated_request_data['bk_biz_id']}_{validated_request_data['type']}",
                type=validated_request_data["type"],
                namespaces=[f"biz#{validated_request_data['bk_biz_id']}"],
                bk_tenant_id=bk_tenant_id,
            )

        return token.token
