"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy

from common.log import logger
from django.conf import settings
from iam.exceptions import AuthAPIError

from iam import IAM


# 动作语义兼容别名：键动作在后端不单独鉴权，可由值中任一等价的"空间级"管理动作放行。
# 典型场景 new_dashboard（新建仪表盘）：后端创建仪表盘按仪表盘管理角色
# （manage_dashboard_v2 / manage_datasource_v2）放行，但前端会单独查询 new_dashboard 权限，
# 导致已拥有管理权限的用户（如"业务运维"推荐权限）在界面被误判为无权限。这里让 new_dashboard
# 的鉴权查询可被等价的管理动作满足，使前端判定与后端实际放行保持一致。
# 注意：仅允许别名到同为空间级（SPACE）资源的动作，保证策略表达式与原查询资源同构、可直接 OR 合并；
# 不要别名到实例级动作（如 edit_single_dashboard）。
ACTION_COMPATIBLE_ALIASES = {
    "new_dashboard": ["manage_dashboard_v2", "manage_datasource_v2"],
}


class CompatibleIAM(IAM):
    """
    兼容模式的IAM客户端
    """

    def _has_v1_actions(self):
        """
        是否存在V1的操作ID
        """
        ok, message, data = self._client.query(settings.BK_IAM_SYSTEM_ID)
        if not ok:
            return False
        return "view_business" in [action["id"] for action in data["actions"]]

    def in_compatibility_mode(self):
        if hasattr(CompatibleIAM, "__compatibility_mode"):
            return getattr(CompatibleIAM, "__compatibility_mode")

        try:
            from monitor.models import GlobalConfig

            # 存在V1操作时，通过开关去判断是否开启兼容模式
            compatibility_mode = GlobalConfig.objects.get(key="IAM_V1_COMPATIBLE").value
        except Exception:  # pylint: disable=broad-except
            # 配置不存在时，默认打开兼容模式
            compatibility_mode = True

        setattr(CompatibleIAM, "__compatibility_mode", compatibility_mode)
        return compatibility_mode

    def _patch_policy_expression(self, expression):
        """
        将业务资源表达式转换为空间
        """
        if not expression:
            return
        if expression["op"] == "OR":
            for sub_expr in expression["content"]:
                self._patch_policy_expression(sub_expr)
        else:
            if expression["field"] == "biz.id":
                expression["field"] = "space.id"
            if "biz" in expression["value"]:
                expression["value"] = expression["value"].replace("biz", "space")

    def _merge_alias_policies(self, request, policies, with_resources=True):
        """
        动作兼容别名：用等价管理动作的策略补充当前动作的鉴权策略（OR 合并）。

        某些动作在后端不单独鉴权、实际由等价的管理动作放行，但前端会单独查询该动作权限。
        这里在策略查询阶段把等价动作的策略并入，避免前端对已有管理权限的用户误报无权限。
        别名仅限同为空间级资源的动作，详见 ACTION_COMPATIBLE_ALIASES 说明。

        别名动作复用 _do_policy_query 查询，确保与主查询走相同的 v1/v2 分派及兼容逻辑，
        不绕过 SDK 的 API 版本调度；某个别名查询失败时记录日志并按"无该动作策略"处理，
        既不静默吞掉错误，也不因补充查询失败而影响主动作鉴权。
        """
        from bkmonitor.iam.action import get_action_by_id

        for alias_action_id in ACTION_COMPATIBLE_ALIASES.get(request.action.id, []):
            alias_request = copy.copy(request)
            alias_request.action = get_action_by_id(alias_action_id)
            try:
                alias_policies = self._do_policy_query(alias_request, with_resources)
            except AuthAPIError:
                logger.exception("[CompatibleIAM] 查询别名动作策略失败, action_id=%s", alias_action_id)
                continue
            if not alias_policies:
                continue
            policies = alias_policies if not policies else {"op": "OR", "content": [policies, alias_policies]}
        return policies

    def _do_policy_query(self, request, with_resources=True):
        # 动作兼容别名与 V1 兼容模式无关（它是 new_dashboard 等动作的语义补偿，而非 V1->V2 桥接），
        # 即便完成 v2 升级、关闭了 V1 兼容模式（IAM_V1_COMPATIBLE=False），也要继续生效。
        if not self.in_compatibility_mode():
            policies = super()._do_policy_query(request, with_resources)
            return self._merge_alias_policies(request, policies, with_resources)

        data = request.to_dict()
        logger.debug(f"the request: {data}")

        # NOTE: 不向服务端传任何resource, 用于统一类资源的批量鉴权
        # 将会返回所有策略, 然后遍历资源列表和策略列表, 逐一计算
        if not with_resources:
            data["resources"] = []

        ok, message, policies = self._client.policy_query(data)
        if data["action"]["id"].endswith("_v2"):
            v1_data = copy.deepcopy(data)

            # 替换action_id
            v1_data["action"]["id"] = v1_data["action"]["id"].replace("_v2", "")

            # 替换资源名称
            for resource in v1_data["resources"]:
                if resource["type"] == "space":
                    resource["system"] = "bk_cmdb"
                    resource["type"] = "biz"
                iam_path = resource.get("attribute", {}).get("_bk_iam_path_", "")
                if "space" in iam_path:
                    resource["attribute"]["_bk_iam_path_"] = iam_path.replace("space", "biz")

            v1_ok, v1_message, v1_policies = self._client.policy_query(v1_data)
            self._patch_policy_expression(v1_policies)

            if v1_policies:
                if not policies:
                    policies = v1_policies
                else:
                    # 将两个版本的 action 的策略组合起来
                    policies = {
                        "op": "OR",
                        "content": [policies, v1_policies],
                    }

        # 动作兼容别名：用等价管理动作的策略补充当前动作（OR 合并），详见 ACTION_COMPATIBLE_ALIASES
        policies = self._merge_alias_policies(request, policies, with_resources)

        if not policies and not ok:
            raise AuthAPIError(message)
        return policies

    def _do_policy_query_by_actions(self, request, with_resources=True):
        if not self.in_compatibility_mode():
            return super()._do_policy_query_by_actions(request, with_resources)

        data = request.to_dict()
        logger.debug(f"the request: {data}")

        # NOTE: 不向服务端传任何resource, 用于统一类资源的批量鉴权
        # 将会返回所有策略, 然后遍历资源列表和策略列表, 逐一计算
        if not with_resources:
            data["resources"] = []

        ok, message, action_policies = self._client.policy_query_by_actions(data)

        # v2的action需要查一下v1的action是否有权限
        v2_actions = [action["id"] for action in data["actions"] if action["id"].endswith("_v2")]

        if v2_actions:
            v1_data = copy.deepcopy(data)

            # 替换action_id
            v1_data["actions"] = [{"id": action_id.replace("_v2", "")} for action_id in v2_actions]

            v1_ok, v1_message, v1_action_policies = self._client.policy_query_by_actions(v1_data)
            for v1_policy in v1_action_policies or []:
                v1_policy["action"]["id"] += "_v2"
                # 替换资源名称
                self._patch_policy_expression(v1_policy["condition"])

                for policy in action_policies:
                    # 与V2的策略做比对，如果V2是空，就用V1的
                    if v1_policy["action"]["id"] != policy["action"]["id"]:
                        continue

                    if not v1_policy["condition"]:
                        continue

                    if not policy["condition"]:
                        policy["condition"] = v1_policy["condition"]
                    else:
                        policy["condition"] = {
                            "op": "OR",
                            "content": [policy["condition"], v1_policy["condition"]],
                        }

        if not ok:
            raise AuthAPIError(message)
        return action_policies
