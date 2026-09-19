"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkapi_client_core.apigateway import APIGatewayClient, Operation, OperationGroup, bind_property


class SourceAnalysisOperationGroup(OperationGroup):
    ensure_scene = bind_property(
        Operation,
        name="ensure_scene",
        method="POST",
        path="/incident/issue_analysis/ensure_scene/",
    )
    get_scene_status = bind_property(
        Operation,
        name="get_scene_status",
        method="GET",
        path="/incident/issue_analysis/get_scene_status/",
    )
    trigger = bind_property(
        Operation,
        name="trigger",
        method="POST",
        path="/incident/issue_analysis/trigger/",
    )
    get_task = bind_property(
        Operation,
        name="get_task",
        method="GET",
        path="/incident/issue_analysis/get_task/",
    )


class BKFaraClient(APIGatewayClient):
    """BKFara API Gateway 客户端。"""

    _api_name = "bkfara"

    source_analysis = bind_property(SourceAnalysisOperationGroup, name="source_analysis")
