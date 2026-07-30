"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Provider 能力声明常量
#
# 不同 IAM 平台能力差异很大
# 上层代码通过 Provider.supports(capability) 查询，做能力退化。
# 这些常量是"契约"，禁止各 Provider 自己拼字符串。
# ---------------------------------------------------------------------------

from enum import Enum


class Capability(str, Enum):
    """Provider 支持的能力枚举。"""

    # 策略表达式查询（v3 独有）：能返回 PolicyExpression 供本地求值 / DB 下推
    POLICY_EXPRESSION = "policy_expression"

    # 批量鉴权：支持一次传入多个资源
    BATCH_AUTH = "batch_auth"

    # 无限制批量：批量鉴权无平台上限
    BATCH_AUTH_UNLIMITED = "batch_auth_unlimited"

    # 角色模型：平台支持 RBAC 角色（v4 独有）
    ROLE_MODEL = "role_model"

    # 通配符资源授权（v4 支持 resource.id = "*"）
    WILDCARD_RESOURCE = "wildcard_resource"

    # 授权过期时间（v4 支持 expired_at）
    AUTH_EXPIRATION = "auth_expiration"

    # 读权限缓存（v3 SDK 内置 is_allowed_with_cache）
    READ_CACHE = "read_cache"

    # 资源创建者关联授权（v3 grant_resource_creator_actions）
    CREATOR_GRANT = "creator_grant"

    # 权限申请 URL 生成
    APPLY_URL = "apply_url"

    # Schema 迁移（plan/apply/rollback）
    SCHEMA_MIGRATION = "schema_migration"
