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

from apps.generic import APIViewSet
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from bkm_space.serializers import SpaceUIDField
from bkm_space.utils import space_uid_to_bk_biz_id
from apps.log_databus.serializers import (
    LogCollectorSerializer,
    GetCollectorFieldEnumsSerializer,
    GetCollectorStatusSerializer,
)

from apps.utils.drf import list_route
from apps.log_databus.handlers.collector_handler.log import LogCollectorHandler
from apps.log_databus.models import CollectorConfig

from apps.iam.handlers.drf import IAMPermission, insert_permission_field
from apps.iam import ActionEnum, ResourceEnum


class LogAccessViewSet(APIViewSet):
    def get_permissions(self):
        if self.action == "get_collector_status":
            data = self.params_valid(GetCollectorStatusSerializer)
            # 状态查询可能跨业务，须按采集项实际归属分别鉴权。
            bk_biz_ids = set(
                CollectorConfig.objects.filter(collector_config_id__in=data["collector_config_id_list"]).values_list(
                    "bk_biz_id", flat=True
                )
            )
        else:
            # 列表按 space_uid 查询，鉴权也须基于该空间，避免伪造 bk_biz_id 绕过校验。
            params = self.request.query_params if self.request.method == "GET" else self.request.data
            space_uid = SpaceUIDField().run_validation(params.get("space_uid"))
            bk_biz_id = space_uid_to_bk_biz_id(space_uid)
            if not bk_biz_id:
                raise ValidationError("无效的空间")
            bk_biz_ids = {bk_biz_id}

        return [
            IAMPermission(
                [ActionEnum.VIEW_BUSINESS],
                [ResourceEnum.BUSINESS.create_instance(bk_biz_id)],
            )
            for bk_biz_id in sorted(bk_biz_ids)
        ]

    @insert_permission_field(
        id_field=lambda d: d.get("collector_config_id"),
        data_field=lambda d: d["list"],
        actions=[ActionEnum.VIEW_COLLECTION, ActionEnum.MANAGE_COLLECTION],
        resource_meta=ResourceEnum.COLLECTION,
    )
    @insert_permission_field(
        id_field=lambda d: d["index_set_id"],
        data_field=lambda d: d["list"],
        actions=[ActionEnum.SEARCH_LOG, ActionEnum.MANAGE_INDICES],
        resource_meta=ResourceEnum.INDICES,
    )
    @list_route(methods=["POST"], url_path="collector")
    def collector(self, request):
        data = self.params_valid(LogCollectorSerializer)
        result = LogCollectorHandler(data["space_uid"]).get_log_collectors(data)
        return Response(result)

    @list_route(methods=["GET"], url_path="collector_field_enums")
    def get_collector_field_enums(self, request):
        data = self.params_valid(GetCollectorFieldEnumsSerializer)
        result = LogCollectorHandler(data["space_uid"]).get_collector_field_enums(
            data.get("include_related_spaces", False)
        )
        return Response(result)

    @list_route(methods=["POST"], url_path="collector_status")
    def get_collector_status(self, request):
        data = self.params_valid(GetCollectorStatusSerializer)
        result = LogCollectorHandler.get_collector_status(data["collector_config_id_list"])
        return Response(result)
