# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


from rest_framework import serializers

from bkmonitor.models import ApiAuthToken
from bkmonitor.utils.request import get_request_tenant_id
from core.drf_resource import Resource


class GetApiTokenResource(Resource):
    """
    获取API鉴权令牌
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        type = serializers.ChoiceField(label="Token类型", default="as_code", choices=("as_code", "grafana"))

    def perform_request(self, params):
        # 获取当前租户
        bk_tenant_id = get_request_tenant_id()
        token = ApiAuthToken.objects.filter(
            namespaces__contains=f"biz#{params['bk_biz_id']}",
            type=params["type"],
            bk_tenant_id=bk_tenant_id,
        )

        if token:
            return token[0].token

        token = ApiAuthToken.objects.create(
            name=f"{params['bk_biz_id']}_{params['type']}",
            type=params["type"],
            namespaces=[f"biz#{params['bk_biz_id']}"],
            bk_tenant_id=bk_tenant_id,
        )
        return token.token
