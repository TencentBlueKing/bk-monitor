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

from typing import List

from django.conf import settings
from iam.api.http import http_post
from iam.auth.models import Action
from iam.auth.models import ApiBatchAuthRequest as OldApiBatchAuthRequest
from iam.auth.models import ApiBatchAuthResourceWithPath, Subject
from iam.exceptions import AuthAPIError

from bkmonitor.iam import Permission, ResourceEnum
from bkmonitor.iam.action import ActionMeta


class ApiBatchAuthRequest(OldApiBatchAuthRequest):
    def __init__(self, *args, expired_at=None, **kwargs):
        super(ApiBatchAuthRequest, self).__init__(*args, **kwargs)
        self.expired_at = expired_at

    def to_dict(self):
        request_dict = super(ApiBatchAuthRequest, self).to_dict()
        if self.expired_at is not None:
            request_dict["expired_at"] = self.expired_at
        return request_dict


class PolicyMigrator:
    def __init__(self, username: str = ""):
        self.iam_client = Permission.get_iam_client()
        self.system_id = settings.BK_IAM_SYSTEM_ID
        self.username = username

    def query_polices_by_action_id(self, action_id: str):
        """
        查询指定操作ID的权限策略列表
        """
        page_size = 500
        page = 1

        policies = []

        query_result = self.iam_client.query_polices_with_action_id(
            self.system_id, {"action_id": action_id, "page": page, "page_size": page_size}
        )
        if not query_result["results"]:
            return policies

        policies.extend(query_result["results"])

        total = query_result["count"]

        while page * page_size < total:
            page += 1
            query_result = self.iam_client.query_polices_with_action_id(
                self.system_id, {"action_id": action_id, "page": page, "page_size": page_size}
            )
            policies.extend(query_result["results"])

        if self.username:
            policies = [policy for policy in policies if policy["subject"]["id"] == self.username]
        return policies

    def grant_resource_chunked(self, resource, paths):
        request = ApiBatchAuthRequest(
            system=resource["system"],
            subject=Subject(
                type=resource["subject"]["type"],
                id=resource["subject"]["id"],
            ),
            actions=[Action(id=action["id"]) for action in resource["actions"]],
            resources=[
                ApiBatchAuthResourceWithPath(system=r["system"], type=r["type"], paths=paths)
                for r in resource["resources"]
            ],
            operate=resource["operate"],
            asynchronous=resource["asynchronous"],
            expired_at=resource["expired_at"],
        )
        result = self._batch_path_authorization(request, bk_username="admin")
        return result

    def grant_resource(self, resource):
        paths = resource["resources"][0]["paths"]
        size = 1000

        results = []
        try:
            if not paths:
                # path 为空，则为无限制授权
                results.append(self.grant_resource_chunked(resource, []))
            else:
                chunked_paths = [paths[pos : pos + size] for pos in range(0, len(paths), size)]
                for chunk in chunked_paths:
                    results.append(self.grant_resource_chunked(resource, chunk))
        except Exception as e:  # pylint: disable=broad-except
            print(
                "grant permission error for action[%s], subject[%s]: %s"
                % (resource["actions"][0]["id"], resource["subject"], e)
            )
        return results

    def _batch_path_authorization(self, request, bk_token=None, bk_username=None):
        data = request.to_dict()
        path = "/api/c/compapi/v2/iam/authorization/batch_path/"
        ok, message, _data = self.iam_client._client._call_esb_api(http_post, path, data, bk_token, bk_username)
        if not ok:
            raise AuthAPIError(message)
        return _data

    def expression_to_resource_paths(self, expression, paths: List):
        """
        将权限表达式转换为资源路径
        """
        if expression["op"] == "OR":
            for sub_expr in expression["content"]:
                self.expression_to_resource_paths(sub_expr, paths)
        elif expression["op"] == "eq":
            # example: indices.id => indices
            resource_type = expression["field"].split(".")[0]
            if resource_type == "biz":
                # biz => space
                resource_type = ResourceEnum.BUSINESS.id
            resource_id = expression["value"]
            paths.append(
                [
                    {
                        "type": resource_type,
                        "id": resource_id,
                        "name": resource_id,
                    },
                ]
            )
        elif expression["op"] == "in":
            # example: indices.id => indices
            resource_type = expression["field"].split(".")[0]
            if resource_type == "biz":
                # biz => space
                resource_type = ResourceEnum.BUSINESS.id
            for resource_id in expression["value"]:
                paths.append(
                    [
                        {
                            "type": resource_type,
                            "id": resource_id,
                            "name": resource_id,
                        },
                    ]
                )
        elif expression["op"] == "starts_with":
            # example: {'field': 'indices._bk_iam_path_',
            #      'op': 'starts_with',
            #      'value': '/biz,5/'}
            resource_type = ResourceEnum.BUSINESS.id
            resource_id = expression["value"][1:-1].split(",")[1]
            paths.append(
                [
                    {
                        "type": resource_type,
                        "id": resource_id,
                        "name": resource_id,
                    },
                ]
            )
        elif expression["op"] == "any":
            # 拥有全部权限
            paths.append([])

    def policy_to_resource(self, action: ActionMeta, policy):
        """
        :param action: action to upgrade
        :param policy: example
        {
            'version': '1',
            'id': 392,
            'subject': {'type': 'group', 'id': '1', 'name': '运维组'},
            'expression': {'field': 'indices._bk_iam_path_',
            'op': 'starts_with',
            'value': '/biz,2/'},
            'expired_at': 4102444800
        }
        """
        paths = []
        self.expression_to_resource_paths(policy["expression"], paths)

        has_any_policy = False
        for path in paths:
            if not path:
                has_any_policy = True
                break
        if has_any_policy:
            # 拥有any全部权限，直接置空
            paths = []

        resource = {
            "asynchronous": False,
            "operate": "grant",
            "system": self.system_id,
            "actions": [{"id": action.id}],
            "subject": policy["subject"],
            "resources": [
                {
                    "system": action.related_resource_types[0]["system_id"],
                    "type": action.related_resource_types[0]["id"],
                    "paths": paths,
                }
            ],
            "expired_at": policy["expired_at"],
        }
        return resource
