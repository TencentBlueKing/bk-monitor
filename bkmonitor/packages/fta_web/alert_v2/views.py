"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.permission import Permission
from bkmonitor.models import ApiAuthToken, AuthType
from bkmonitor.share.handler import get_shared_alert_id
from bkmonitor.utils.request import get_request_tenant_id
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute
from core.errors.share import TokenValidatedError

# 复用原有alert模块的ViewSet实现
from fta_web.alert.views import (
    AlertViewSet as _BaseAlertViewSet,
    QuickAlertHandleViewSet as _BaseQuickAlertHandleViewSet,
    SearchFavoriteViewSet as _BaseSearchFavoriteViewSet,
)


class AlertV2ViewSet(_BaseAlertViewSet):
    """
    告警模块V2版本 - 复用原有实现
    新版本可以在这里添加特定的业务逻辑或覆盖原有方法
    """

    def check_permissions(self, request):
        token = getattr(request, "token", None)
        if self.action == "alert/detail" and request.method == "GET" and token and not request.user.is_authenticated:
            self.check_shared_alert_detail(request, token)
            return
        super().check_permissions(request)

    @staticmethod
    def check_shared_alert_detail(request, token):
        biz_id = request.biz_id
        if not biz_id or request.query_params.get("bk_biz_id") != str(biz_id):
            raise TokenValidatedError
        try:
            tenant_id = bk_biz_id_to_bk_tenant_id(biz_id)
        except (TypeError, ValueError):
            raise TokenValidatedError from None
        request_tenant_id = get_request_tenant_id(peaceful=True)
        if not tenant_id or (request_tenant_id and request_tenant_id != tenant_id):
            raise TokenValidatedError

        try:
            share = ApiAuthToken.objects.get(token=token, type=AuthType.Event, bk_tenant_id=tenant_id, is_enabled=True)
        except ApiAuthToken.DoesNotExist:
            raise TokenValidatedError from None
        if share.is_expired() or f"biz#{biz_id}" not in share.namespaces:
            raise TokenValidatedError

        shared_alert_id = get_shared_alert_id(share.params.get("data"))
        if not shared_alert_id or request.query_params.get("id") != shared_alert_id:
            raise TokenValidatedError

        # 已签发令牌的 data 可以被更新，匿名读取只接受由签发人最后保存的配置。
        if not share.create_user or share.create_user == "unknown" or share.update_user != share.create_user:
            raise TokenValidatedError
        permission = Permission(username=share.create_user, bk_tenant_id=tenant_id)
        permission.skip_check = False
        if not permission.is_allowed_by_biz(bk_biz_id=biz_id, action=ActionEnum.VIEW_EVENT):
            raise TokenValidatedError
        # DRF 会替换未登录用户对象，详情读取使用校验后的租户上下文。
        request.user.tenant_id = tenant_id

    resource_routes = [
        ResourceRoute("GET", resource.alert_v2.alert_detail, endpoint="alert/detail"),
        ResourceRoute("POST", resource.alert_v2.alert_events, endpoint="alert/events"),
        ResourceRoute("GET", resource.alert_v2.alert_event_total, endpoint="alert/event_total"),
        ResourceRoute("POST", resource.alert_v2.alert_event_ts, endpoint="alert/event_ts"),
        ResourceRoute("POST", resource.alert_v2.alert_event_tag_detail, endpoint="alert/event_tag_detail"),
        ResourceRoute("GET", resource.alert_v2.alert_k8s_target, endpoint="alert/k8s_target"),
        ResourceRoute("GET", resource.alert_v2.alert_host_target, endpoint="alert/host_target"),
        ResourceRoute("POST", resource.alert_v2.alert_traces, endpoint="alert/traces"),
        ResourceRoute("GET", resource.alert_v2.alert_log_relation_list, endpoint="alert/log_relation_list"),
        ResourceRoute("POST", resource.scene_view.graph_drill_down, endpoint="alert/graph_drill_down"),
    ]


class QuickAlertHandleV2ViewSet(_BaseQuickAlertHandleViewSet):
    """
    快捷告警处理V2版本 - 复用原有实现
    """

    pass


class SearchFavoriteV2ViewSet(_BaseSearchFavoriteViewSet):
    """
    搜索收藏V2版本 - 复用原有实现
    """

    pass
