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
# 统一异常层次
#
# 所有框架抛出的异常都必须继承 IamEngineError；使用方只 catch 顶层异常即可覆盖框架错误。
# 分类原则：
#   - 配置错误        ConfigError（启动阶段，无法自愈）
#   - Schema 错误     SchemaError（definitions 有误，需要开发者修）
#   - Provider 错误   ProviderError（运行时，可能可重试）
#   - Migration 错误  MigrationError（同步平台配置时）
#   - 鉴权拒绝        PermissionDenied（业务语义，非框架故障）
# ---------------------------------------------------------------------------


class IamEngineError(Exception):
    """iam_engine 所有异常的基类。"""


# ---- 配置类 ----------------------------------------------------------------


class ConfigError(IamEngineError):
    """框架配置错误（IAM_FRAMEWORK settings 缺失/非法等）。"""


class ProviderNotFound(ConfigError):
    """按名字查找 Provider 时未找到。"""


# ---- Schema 类 -------------------------------------------------------------


class SchemaError(IamEngineError):
    """Schema 定义错误的基类。"""


class SchemaConflict(SchemaError):
    """定义冲突（例如重复注册同名 action_id）。"""


class SchemaFrozenError(SchemaError):
    """Registry 已冻结，禁止再修改。"""


class ActionNotFound(SchemaError):
    """按 id 查找 ActionDef 时未找到。"""


class ResourceTypeNotFound(SchemaError):
    """按 id 查找 ResourceTypeDef 时未找到。"""


class RoleNotFound(SchemaError):
    """按 id 查找 RoleDef 时未找到。"""


# ---- Provider 类 -----------------------------------------------------------


class ProviderError(IamEngineError):
    """Provider 层错误的基类。"""


class ProviderUnavailable(ProviderError):
    """Provider 后端不可用（连不通、超时、限流等）。"""


class CapabilityNotSupported(ProviderError):
    """当前 Provider 不支持某能力（应通过 Provider.supports() 事先判断）。"""


# ---- Migration 类 ----------------------------------------------------------


class MigrationError(IamEngineError):
    """迁移相关错误基类。"""


class DestructiveMigrationBlocked(MigrationError):
    """检测到破坏性变更且未显式允许时抛出。"""


class MigrationPreCheckFailed(MigrationError):
    """apply 前置检查失败（clients 白名单缺失、仍有授权等）。"""


class MigrationFailed(MigrationError):
    """执行阶段失败。"""


# ---- 鉴权语义 --------------------------------------------------------------


class PermissionDenied(IamEngineError):
    """鉴权被拒绝。

    这不是"框架故障"，而是"业务语义"，单独一层便于上层针对性处理
    （例如生成申请 URL、返回 403 等）。
    """

    def __init__(self, action_id: str = "", apply_url: str = "", detail: dict | None = None):
        self.action_id = action_id
        self.apply_url = apply_url
        self.detail = detail or {}
        super().__init__(f"permission denied: action={action_id}")
