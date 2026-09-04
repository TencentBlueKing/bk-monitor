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

from apps.constants import ACTIONS_IMPLYING_LOG_SEARCH, ExternalPermissionActionEnum
from apps.log_commons.external_auth.context import ExternalRequestContext
from apps.log_commons.external_auth.decision import DecisionSource, SourceResult
from apps.log_commons.external_auth.view_mapping import resolve_resource
from apps.log_commons.models import ExternalPermission


class LegacyTicketSource:
    """基于 ExternalPermission 授权记录（旧票）的放行来源。

    判定分三步：空间下有没有票、票里的授权项能不能覆盖当前接口、请求指向的资源在不在票的实例列表里。
    拒绝文案沿用接入管道之前的原文，外部调用方和既有告警都按这些文案匹配。
    """

    name = DecisionSource.LEGACY

    def check(self, ctx: ExternalRequestContext) -> SourceResult:
        external_user = ctx.external_user
        allowed_action_id_list = self._list_allowed_action_ids(ctx)

        if not allowed_action_id_list:
            return SourceResult.deny(f"dispatch_plugin_query: external_user:{external_user} has no permission.")

        matched_action_id = self._match_action_id(ctx, allowed_action_id_list)
        if not matched_action_id:
            return SourceResult.deny(f"external_user:{external_user} has not enough permission.")

        allow_resources_result = ExternalPermission.get_resources(
            space_uid=ctx.space_uid, action_id=matched_action_id, authorized_user=external_user
        )
        if not allow_resources_result["allowed"]:
            return SourceResult.allow(
                matched_action_id=matched_action_id,
                allow_resources_result=allow_resources_result,
            )

        # 资源维度的授权项才解析实例 ID，其余能力保持「资源为空」，审计也据此不记资源
        resource_id = resolve_resource(matched_action_id, ctx.url_kwargs, ctx.json_data_str)
        if resource_id and resource_id not in allow_resources_result["resources"]:
            return SourceResult.deny(
                f"external_user:{external_user} cannot access resource(ID:{resource_id}).",
                matched_action_id=matched_action_id,
                resource_id=resource_id,
                allow_resources_result=allow_resources_result,
            )
        # 聚类设置写入必须同时具备该索引集的检索票，避免只授 log_clustering 即可改配置
        if (
            matched_action_id == ExternalPermissionActionEnum.LOG_CLUSTERING.value
            and resource_id
            and not ExternalPermission.can_access_clustering_settings(
                space_uid=ctx.space_uid, authorized_user=external_user, index_set_id=resource_id
            )
        ):
            return SourceResult.deny(
                (
                    f"external_user:{external_user} cannot access clustering settings "
                    f"without log_search on resource(ID:{resource_id})."
                ),
                matched_action_id=matched_action_id,
                resource_id=resource_id,
                allow_resources_result=allow_resources_result,
            )
        return SourceResult.allow(
            matched_action_id=matched_action_id,
            resource_id=resource_id,
            allow_resources_result=allow_resources_result,
        )

    @staticmethod
    def _list_allowed_action_ids(ctx: ExternalRequestContext) -> list[str]:
        allowed_action_id_list = ExternalPermission.get_authorizer_permission(
            space_uid=ctx.space_uid, authorizer=ctx.external_user
        ).get(ctx.space_uid, [])
        # 仅 ACTIONS_IMPLYING_LOG_SEARCH 会隐式补 log_search；log_clustering 不在其中
        if ExternalPermissionActionEnum.LOG_SEARCH.value not in allowed_action_id_list and any(
            implying_action_id in allowed_action_id_list for implying_action_id in ACTIONS_IMPLYING_LOG_SEARCH
        ):
            allowed_action_id_list.append(ExternalPermissionActionEnum.LOG_SEARCH.value)
        return allowed_action_id_list

    @staticmethod
    def _match_action_id(ctx: ExternalRequestContext, allowed_action_id_list: list[str]) -> str:
        for action_id in allowed_action_id_list:
            if ExternalPermission.is_action_valid(
                view_set=ctx.view_set, view_action=ctx.view_action, action_id=action_id
            ):
                return action_id
        return ""


LEGACY_TICKET_SOURCE = LegacyTicketSource()
