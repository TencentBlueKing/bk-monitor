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

from django.core.exceptions import ValidationError

from bkmonitor.iam import Permission
from bkmonitor.iam.action import ActionEnum
from bkmonitor.utils.request import get_request, get_request_tenant_id
from bkmonitor.views import serializers
from core.drf_resource import Resource

logger = logging.getLogger(__name__)


class BusinessListByActions(Resource):
    class RequestSerializer(serializers.Serializer):
        """
        actions_id 参考
        >>>from bkmonitor.iam.action import ActionEnum
        """

        action_ids = serializers.ListField(required=False, label="权限id列表", default=[ActionEnum.VIEW_BUSINESS])
        username = serializers.CharField(required=False, label="用户名", allow_null=True, default="")

    def validate_username(self, username):
        if not username:
            try:
                request = get_request()
                return request.user
            except Exception:
                raise ValidationError("can't get username in request")
        return username

    def perform_request(self, validated_request_data):
        biz_dict = {}
        perm_client = Permission(validated_request_data["username"], bk_tenant_id=get_request_tenant_id())
        perm_client.skip_check = False
        for action_id in validated_request_data["action_ids"]:
            # 根据权限中心的【业务访问】权限，对业务列表进行过滤
            business_list = perm_client.filter_space_list_by_action(action_id)
            for business in business_list:
                biz_dict.setdefault(
                    business["bk_biz_id"], {"id": business["bk_biz_id"], "text": business["display_name"]}
                )
        return list(biz_dict.values())
