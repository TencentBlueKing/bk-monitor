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
# Capability — 开放能力描述符
#
# 不是闭合枚举。内置能力预定义为类属性，使用者可自由创建新实例：
#   Capability("my_new_capability")  —— 无需修改框架源码。
#
# Provider 通过 supports(capability) 声明自己支持哪些能力。
# 上层代码通过 supports() 查询后做能力退化。
# ---------------------------------------------------------------------------


class Capability:
    """Provider 能力描述符——开放注册，不闭合。

    内置能力是预定义的类属性（Capability.POLICY_EXPRESSION 等），
    使用方可以直接创建新的 Capability 实例来声明框架未预设的能力。

    典型用法::

        # Provider 声明
        def supports(self, capability: Capability) -> bool:
            return capability in {Capability.ROLE_MODEL, Capability("my_thing")}


        # 调用方能力退化
        if provider.supports(Capability.POLICY_EXPRESSION):
            ast = provider.query_policy(...)
    """

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Capability):
            return self.name == other.name
        if isinstance(other, str):
            return self.name == other
        return NotImplemented

    def __repr__(self) -> str:
        return f"Capability({self.name!r})"

    def __str__(self) -> str:
        return self.name

    # ---- 以下为声明式接口：新增内置能力只需加一行 ----

    # 策略表达式查询（v3 独有）：能返回 PolicyExpression 供本地求值 / DB 下推
    POLICY_EXPRESSION: Capability

    # 批量鉴权：支持一次传入多个资源
    BATCH_AUTH: Capability

    # 无限制批量：批量鉴权无平台上限
    BATCH_AUTH_UNLIMITED: Capability

    # 角色模型：平台支持 RBAC 角色（v4 独有）
    ROLE_MODEL: Capability

    # 通配符资源授权（v4 支持 resource.id = "*"）
    WILDCARD_RESOURCE: Capability

    # 授权过期时间（v4 支持 expired_at）
    AUTH_EXPIRATION: Capability

    # 读权限缓存（v3 SDK 内置 is_allowed_with_cache）
    READ_CACHE: Capability

    # 资源创建者关联授权（v3 grant_resource_creator_actions）
    CREATOR_GRANT: Capability

    # 权限申请 URL 生成
    APPLY_URL: Capability

    # Schema 迁移（plan/apply/rollback）
    SCHEMA_MIGRATION: Capability


# 将内置能力实例化到类属性上
Capability.POLICY_EXPRESSION = Capability("policy_expression")
Capability.BATCH_AUTH = Capability("batch_auth")
Capability.BATCH_AUTH_UNLIMITED = Capability("batch_auth_unlimited")
Capability.ROLE_MODEL = Capability("role_model")
Capability.WILDCARD_RESOURCE = Capability("wildcard_resource")
Capability.AUTH_EXPIRATION = Capability("auth_expiration")
Capability.READ_CACHE = Capability("read_cache")
Capability.CREATOR_GRANT = Capability("creator_grant")
Capability.APPLY_URL = Capability("apply_url")
Capability.SCHEMA_MIGRATION = Capability("schema_migration")
