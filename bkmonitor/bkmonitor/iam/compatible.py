# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
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

    def _do_policy_query(self, request, with_resources=True):
        if not self.in_compatibility_mode():
            return super(CompatibleIAM, self)._do_policy_query(request, with_resources)

        data = request.to_dict()
        logger.debug("the request: %s" % data)

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

        if not policies and not ok:
            raise AuthAPIError(message)
        return policies

    def _do_policy_query_by_actions(self, request, with_resources=True):
        if not self.in_compatibility_mode():
            return super(CompatibleIAM, self)._do_policy_query_by_actions(request, with_resources)

        data = request.to_dict()
        logger.debug("the request: %s" % data)

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
            for v1_policy in v1_action_policies:
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
