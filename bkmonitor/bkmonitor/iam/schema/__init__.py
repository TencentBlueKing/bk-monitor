"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# iam.schema — 平台无关的权限模型定义
#
# Action / ResourceType / Role 的定义不绑定任何 IAM 版本（v3/v4），
# 各版本 Provider 共用同一套 schema。
#
# 使用方式（在 IAM_FRAMEWORK 配置中）：
#   "ACTIONS": "bkmonitor.iam.schema.actions.Actions",
#   "RESOURCE_TYPES": "bkmonitor.iam.schema.resource_types.ResourceTypes",
#   "ROLES": "bkmonitor.iam.schema.roles.Roles",
# ---------------------------------------------------------------------------

from .actions import Actions
from .resource_types import ResourceTypes
from .roles import Roles

__all__ = ["Actions", "ResourceTypes", "Roles"]
