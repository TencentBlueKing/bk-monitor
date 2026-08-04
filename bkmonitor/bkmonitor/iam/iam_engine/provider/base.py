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
# PermissionProvider —— 权限平台接入的唯一扩展契约
#
# 分层设计：
#   * 高层能力（必选）：所有 Provider 必须实现，框架保证上层调用永远可用
#       - is_allowed / batch_by_resource / batch_by_action / get_apply_url
#   * 低层能力（可选）：通过 supports(Capability) 声明
#       - query_policy / query_policy_by_actions
#         （v3 独有；不支持则返回 None，业务层按需退化）
#   * 迁移能力（必选）：所有 Provider 必须支持 plan/apply
#   * 运维能力（必选）：health_check
#
# 契约要点：
#   1. 平台约束由 Provider 内部透明处理，不允许泄漏到调用方
#   2. 明确拒绝返回 False；异常代表系统失败（ProviderUnavailable / ...）
#   3. 批量方法的分片、重试由 Provider 自行完成
#   4. "反向查询用户有哪些资源权限"走 query_policy 拿 AST，禁止用批量鉴权
#      枚举全量候选池（父资源级授权会造成"展开为几十万子资源"的性能陷阱）
# ---------------------------------------------------------------------------

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from ..core.types import (
    ApplyURLRequest,
    AuthRequest,
    BatchAuthResult,
    BatchByActionRequest,
    BatchByResourceRequest,
    Subject,
    to_action_id,
)

from ..schema.registry import SchemaRegistry

if TYPE_CHECKING:
    from ..policy.expression import PolicyExpression
    from ..schema.definitions import ActionDef
    from ..schema.diff import MigrationPlan, MigrationReport


class PermissionProvider(ABC):
    """权限服务抽象接口 —— 唯一的扩展契约。

    新增权限平台 = 新增本类子类；框架其余部分无需改动。

    构造约定：
        Provider 只吃两样东西：
          - schema：框架统一构建的冻结 SchemaRegistry（跨 Provider 共享）
          - options：settings.IAM_FRAMEWORK.PROVIDERS[*].options 原样透传的字典

        options 里的结构（含 credentials、system 等）**完全由 Provider 自己决定**，
        框架不做任何解析。推荐 Provider 在自己的 config.py 里用 dataclass 声明
        契约类（如 V4Options），并在 __init__ 里调用 XxxOptions.from_dict(options)
        完成校验。

        Provider 内部日志用模块级 logging.getLogger(__name__) 即可；缓存策略
        （如需要）也应由 Provider 自持，不通过框架注入。
    """

    #: Provider 标识，用于日志/监控/命令行 --provider 参数。
    #: 子类必须覆盖为非空字符串（如 "v4"、"v3"）。
    name: ClassVar[str] = ""

    def __init__(self, schema: SchemaRegistry, **options: Any) -> None:
        self.schema = schema
        self.options = options

    # ==================== 系统信息（供命令行/诊断使用） ====================

    def get_system_info(self) -> Any | None:
        """返回 Provider 的系统信息对象（结构由 Provider 自己决定）。

        命令行工具（如 iam_generate_config）以 duck typing 消费 ``.id`` / ``.name``
        / ``.description`` / ``.managers`` / ``.clients`` / ``.callback_url`` 等字段。
        Provider 若无系统概念可返回 None。
        """
        return None

    # ==================== 能力声明 ====================

    # ==================== 高层能力（必选） ====================

    @abstractmethod
    def is_allowed(self, request: AuthRequest) -> bool:
        """单次鉴权。allowed=False 代表业务语义拒绝，非系统错误。"""

    @abstractmethod
    def batch_by_resource(self, request: BatchByResourceRequest) -> BatchAuthResult:
        """同 action、多 resource 的批量鉴权。

        Provider 内部完成分片（如 v4 每批 20），调用方不应感知。
        """

    @abstractmethod
    def batch_by_action(self, request: BatchByActionRequest) -> BatchAuthResult:
        """多 action、同一 resource（或无 resource）的批量鉴权。"""

    @abstractmethod
    def get_apply_url(self, request: ApplyURLRequest) -> str:
        """生成"跳转到权限申请页"的 URL。"""

    # ==================== 低层能力（可选） ====================
    #
    # query_policy / query_policy_by_actions 用于"反向查询"：
    # 不给候选池、直接问"用户对该 action 有哪些资源的权限"，返回中立的
    # PolicyExpression AST。
    #
    # 不支持的 Provider 应保持默认返回 None，且 supports(POLICY_EXPRESSION)
    # 也返回 False；组合策略与业务层按 None 做能力退化。

    def query_policy(
        self,
        subject: Subject,
        action_id: ActionDef | str,
    ) -> PolicyExpression | None:
        """查询单个 action 的策略 AST。

        默认返回 None（不支持）；子类支持时须同时让
        supports(Capability.POLICY_EXPRESSION) 返回 True。
        """
        return None

    def query_policy_by_actions(
        self,
        subject: Subject,
        action_ids: list[ActionDef | str],
    ) -> dict[str, PolicyExpression | None]:
        """批量查询多个 action 的策略 AST。

        默认走"逐个调 query_policy"的兜底实现；子类若有更高效的一次性接口
        （如 v3 的 policy_query_by_actions）应覆盖本方法。

        返回值：dict[action_id(str) -> PolicyExpression | None]
            * 该 Provider 不支持 POLICY_EXPRESSION 时，所有 value 都是 None
            * 部分 action 无策略（例如用户无任何权限）时，对应 value 是 None
        """
        return {to_action_id(aid): self.query_policy(subject, aid) for aid in action_ids}

    # ==================== 迁移契约 ====================

    @abstractmethod
    def plan_migration(self, schema: SchemaRegistry) -> MigrationPlan:
        """比对本地 schema 与远端 IAM 平台，生成变更计划（不执行）。"""

    @abstractmethod
    def apply_migration(
        self,
        plan: MigrationPlan,
        *,
        dry_run: bool = False,
        allow_destructive: bool = False,
    ) -> MigrationReport:
        """应用变更计划。

        Args:
            plan: plan_migration 的产物
            dry_run: 只演练，不真正提交
            allow_destructive: 是否允许破坏性变更（默认禁止）
        """

    # ==================== 运维 ====================

    @abstractmethod
    def health_check(self) -> dict:
        """探活。返回形如 {"status": "ok"|"error", "provider": self.name, ...}。"""
