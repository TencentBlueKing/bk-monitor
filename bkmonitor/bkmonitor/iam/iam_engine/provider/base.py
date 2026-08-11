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
# PermissionProvider —— 权限平台接入的唯一扩展契约（模板方法模式）
#
# 分层设计：
#   * 接口层（业务规范化命名）：所有 public 方法。基类实现，子类通常不覆盖。
#       - is_allowed / batch_by_resource / batch_by_action / get_apply_url
#     基类职责：
#       1. 通过 NameCodec 把 core.types 结构编码成 Dialect* 结构（出站 encode）
#       2. 完成批量分片 + 串/并行调用
#       3. 委托给子类实现的"方言层"抽象方法
#       4. 把方言层返回的方言 ID 解码回业务 ID（入站 decode）
#
#   * 方言层（平台方言命名，abstract）：子类必须实现。
#       - _is_allowed_dialect
#       - _batch_by_resource_dialect_page
#       - _batch_by_action_dialect_page
#       - _get_apply_url_dialect
#     子类职责：只做"打平台 API"这一件事。入参出参都已经是方言 ID，
#     子类不需要感知 codec。
#
#   * 迁移能力（必选）：所有 Provider 必须支持 plan/apply（不走方言层，
#     Provider 自己组织 Migrator 时若涉及方言，可从 self.codec 拿到）。
#
#   * 运维能力（必选）：health_check
#
#   * 低层能力（可选）：query_policy / query_policy_by_actions
#
# 契约要点：
#   1. 平台约束（方言 ID / 特殊字段拼接）由 Provider 内部透明处理，不允许
#      泄漏到调用方；上层永远只见业务规范化命名。
#   2. 明确拒绝返回 False；异常代表系统失败（ProviderUnavailable / ...）
#   3. 批量方法的分片、并发由基类自动完成；子类只关心"一页方言请求"。
#   4. "反向查询用户有哪些资源权限"走 query_policy 拿 AST，禁止用批量鉴权
#      枚举全量候选池（父资源级授权会造成"展开为几十万子资源"的性能陷阱）
# ---------------------------------------------------------------------------

from abc import ABC, abstractmethod
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

from ..core.exceptions import ActionNotFound, ProviderUnavailable
from ..core.types import (
    ApplyURLRequest,
    AuthRequest,
    BatchAuthResult,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceAuthResult,
    ResourceInstance,
    Subject,
    to_action_id,
    to_resource_type_id,
)
from ..core.utils import chunked, import_class
from ..schema.registry import SchemaRegistry
from .codec import IdentityCodec, NameCodec
from .dialect_types import (
    DialectApplyURLRequest,
    DialectAuthRequest,
    DialectBatchByActionRequest,
    DialectBatchByResourceRequest,
    DialectResource,
)

if TYPE_CHECKING:
    from ..policy.expression import PolicyExpression
    from ..schema.definitions import ActionDef
    from ..schema.diff import MigrationPlan, MigrationReport


class PermissionProvider(ABC):
    """权限服务抽象接口 —— 唯一的扩展契约。

    新增权限平台 = 新增本类子类 + 实现方言层方法；框架其余部分无需改动。

    构造约定：
        Provider 只吃两样东西：
          - schema：框架统一构建的冻结 SchemaRegistry（跨 Provider 共享，
            使用业务规范化命名）
          - options：settings.IAM_FRAMEWORK.PROVIDERS[*].options 原样透传的字典

        options 里的结构（含 credentials、system 等）**完全由 Provider 自己决定**，
        框架不做任何解析。推荐 Provider 在自己的 config.py 里用 dataclass 声明
        契约类（如 V4Options），并在 __init__ 里调用 XxxOptions.from_dict(options)
        完成校验。

        Provider 内部日志用模块级 logging.getLogger(__name__) 即可；缓存策略
        （如需要）也应由 Provider 自持，不通过框架注入。

    NameCodec 装配：
        options.codec_class 配置 codec 类的 dotted path，由基类在 __init__ 中实例化：
            IAM_FRAMEWORK = {
                "PROVIDERS": [{
                    "options": {
                        "codec_class": "myapp.iam.codec.MyCodec",
                        "codec_kwargs": {"prefix": "v2_"},   # 可选，透传给 codec 构造器
                    },
                }],
            }
        未配置时默认使用 IdentityCodec（业务命名与平台方言完全一致）。
    """

    #: Provider 标识，用于日志/监控/命令行 --provider 参数。
    #: 子类必须覆盖为非空字符串（如 "v4"、"v3"）。
    name: str = ""

    # -------- 批量分片/并发参数（子类可覆盖）--------
    #: 单次批量调用的最大条目数
    CHUNK_SIZE: int = 20
    #: 并发 worker 数。1 = 串行，>1 = ThreadPoolExecutor 并行
    MAX_WORKERS: int = 1

    def __init__(self, schema: SchemaRegistry, **options: Any) -> None:
        self.schema = schema
        self.options = options
        codec_cls_path: str = options.get("codec_class", "")
        codec_kwargs: dict = options.get("codec_kwargs", {})
        if codec_cls_path:
            self.codec: NameCodec = import_class(codec_cls_path)(**codec_kwargs)
        else:
            self.codec = IdentityCodec()

    # ==================== 系统信息（供命令行/诊断使用） ====================

    def get_system_info(self) -> Any | None:
        """返回 Provider 的系统信息对象（结构由 Provider 自己决定）。

        命令行工具（如 iam_generate_config）以 duck typing 消费 ``.id`` / ``.name``
        / ``.description`` / ``.managers`` / ``.clients`` / ``.callback_url`` 等字段。
        Provider 若无系统概念可返回 None。
        """
        return None

    # ==================== 接口层（业务命名，final）====================

    def is_allowed(self, request: AuthRequest) -> bool:
        """单次鉴权。allowed=False 代表业务语义拒绝，非系统错误。"""
        dialect_req = DialectAuthRequest(
            subject=request.subject,
            action_id=self.codec.encode_action(to_action_id(request.action_id)),
            resource=self._encode_resource(request.resource) if request.resource else None,
            environment=request.environment,
        )
        return self._is_allowed_dialect(dialect_req)

    def batch_by_resource(self, request: BatchByResourceRequest) -> BatchAuthResult:
        """同 action、多 resource 的批量鉴权。基类完成分片 + 并发；子类只处理单页。"""
        action_id_biz = to_action_id(request.action_id)
        dialect_action = self.codec.encode_action(action_id_biz)

        if not request.resources:
            return BatchAuthResult(items=())

        # 假设一批同类型（框架契约）；type 取第一个即可
        rt_biz = to_resource_type_id(request.resources[0].type)
        dialect_rt = self.codec.encode_resource_type(rt_biz)

        # 出站 encode：业务 ID → 方言 ID（保留原业务 ID 用于 decode 回填）
        pairs: list[tuple[str, str]] = [(r.id, self.codec.encode_resource_id(rt_biz, r.id)) for r in request.resources]
        chunks = [list(c) for c in chunked(pairs, self.CHUNK_SIZE)]

        def run_chunk(chunk: list[tuple[str, str]]) -> list[tuple[str, bool]]:
            page_req = DialectBatchByResourceRequest(
                subject=request.subject,
                action_id=dialect_action,
                resource_type=dialect_rt,
                resource_ids=tuple(d_rid for _, d_rid in chunk),
                environment=request.environment,
            )
            return self._batch_by_resource_dialect_page(page_req)

        raw_items = self._run_chunked(chunks, run_chunk)

        # 入站 decode：方言 ID → 业务 ID
        items = tuple(
            ResourceAuthResult(
                action_id=action_id_biz,
                resource_type=rt_biz,
                resource_id=self.codec.decode_resource_id(rt_biz, d_rid),
                allowed=allowed,
            )
            for d_rid, allowed in raw_items
        )
        return BatchAuthResult(items=items)

    def batch_by_action(self, request: BatchByActionRequest) -> BatchAuthResult:
        """多 action、同一 resource（或无 resource）的批量鉴权。"""
        action_ids_biz = [to_action_id(a) for a in request.action_ids]
        pairs: list[tuple[str, str]] = [(aid_biz, self.codec.encode_action(aid_biz)) for aid_biz in action_ids_biz]

        dialect_resource = self._encode_resource(request.resource) if request.resource else None
        rt_biz = to_resource_type_id(request.resource.type) if request.resource else ""
        rid_biz = request.resource.id if request.resource else ""

        if not pairs:
            return BatchAuthResult(items=())

        chunks = [list(c) for c in chunked(pairs, self.CHUNK_SIZE)]

        def run_chunk(chunk: list[tuple[str, str]]) -> list[tuple[str, bool]]:
            page_req = DialectBatchByActionRequest(
                subject=request.subject,
                action_ids=tuple(d_aid for _, d_aid in chunk),
                resource=dialect_resource,
                environment=request.environment,
            )
            return self._batch_by_action_dialect_page(page_req)

        raw_items = self._run_chunked(chunks, run_chunk)

        # 入站 decode：方言 action_id → 业务 action_id
        items = tuple(
            ResourceAuthResult(
                action_id=self.codec.decode_action(d_aid),
                resource_type=rt_biz,
                resource_id=rid_biz,
                allowed=allowed,
            )
            for d_aid, allowed in raw_items
        )
        return BatchAuthResult(items=items)

    def get_apply_url(self, request: ApplyURLRequest) -> str:
        """生成"跳转到权限申请页"的 URL。

        apply_url 的特殊性：action 和 resource 是"交叉配对"的，resource 的
        type 可能未填（业务侧只给 id），需要从 schema 反查 action 的
        resource_type 才能确定。因此使用 _encode_resource_for_action。
        """
        # 编码 action_ids
        action_ids_biz: list[str] = [to_action_id(a) for a in request.action_ids]
        dialect_action_ids = tuple(self.codec.encode_action(a) for a in action_ids_biz)

        # 编码 resources：type 优先从对应 action 反查（apply_url 常见场景）
        # 若有多个 action，取第一个 action 的 resource_type 作为回退线索
        primary_action_biz = action_ids_biz[0] if action_ids_biz else ""
        dialect_resources = tuple(self._encode_resource_for_action(r, primary_action_biz) for r in request.resources)

        dialect_req = DialectApplyURLRequest(
            subject=request.subject,
            action_ids=dialect_action_ids,
            resources=dialect_resources,
        )
        return self._get_apply_url_dialect(dialect_req)

    # ==================== 方言层（子类必须实现）====================

    @abstractmethod
    def _is_allowed_dialect(self, request: DialectAuthRequest) -> bool:
        """子类实现：使用方言 ID 直接调平台 API，返回是否允许。"""

    @abstractmethod
    def _batch_by_resource_dialect_page(
        self,
        request: DialectBatchByResourceRequest,
    ) -> list[tuple[str, bool]]:
        """子类实现：处理"同 action、多 resource"的单页请求（≤ CHUNK_SIZE）。

        Returns:
            list[(dialect_resource_id, allowed)]
        """

    @abstractmethod
    def _batch_by_action_dialect_page(
        self,
        request: DialectBatchByActionRequest,
    ) -> list[tuple[str, bool]]:
        """子类实现：处理"多 action、同 resource"的单页请求（≤ CHUNK_SIZE）。

        Returns:
            list[(dialect_action_id, allowed)]
        """

    @abstractmethod
    def _get_apply_url_dialect(self, request: DialectApplyURLRequest) -> str:
        """子类实现：根据编码后的 apply_url 请求组装平台 payload 并返回 URL。"""

    # ==================== 内部工具 ====================

    def _encode_resource(self, r: ResourceInstance) -> DialectResource:
        """常规资源编码：resource_type 直接从 r.type 拿。

        用于 is_allowed / batch_by_action 等业务侧已明确填好 type 的场景。
        """
        rt = to_resource_type_id(r.type)
        return DialectResource(
            type=self.codec.encode_resource_type(rt),
            id=self.codec.encode_resource_id(rt, r.id),
            ancestors=tuple(self._encode_resource(a) for a in r.ancestor_chain),
        )

    def _encode_resource_for_action(
        self,
        r: ResourceInstance,
        action_id_biz: str,
    ) -> DialectResource:
        """apply_url 场景资源编码：resource_type 优先从 action 定义反查。

        业务侧调 get_apply_url 时，resource 的 type 字段可能没填（因为
        action 唯一决定 resource_type），此时需要用规范化 action_id 查
        schema 反推。schema 查不到时退化到 r.type。
        """
        rt = ""
        if action_id_biz:
            try:
                rt = self.schema.get_action(action_id_biz).resource_type
            except ActionNotFound:
                rt = ""
        if not rt:
            rt = to_resource_type_id(r.type or "")
        return DialectResource(
            type=self.codec.encode_resource_type(rt),
            id=self.codec.encode_resource_id(rt, r.id),
            ancestors=tuple(self._encode_resource(a) for a in r.ancestor_chain),
        )

    def _run_chunked(
        self,
        chunks: list,
        fn: Callable[[list], list[tuple[str, bool]]],
    ) -> list[tuple[str, bool]]:
        """串行或并行执行分片，按 chunk 原始顺序合并结果。

        MAX_WORKERS <= 1 或只有一片 → 串行；否则 ThreadPoolExecutor 并行。
        部分 chunk 失败时聚合所有异常并抛出 ProviderUnavailable。
        """
        if not chunks:
            return []
        if self.MAX_WORKERS <= 1 or len(chunks) <= 1:
            items: list[tuple[str, bool]] = []
            for chunk in chunks:
                items.extend(fn(chunk))
            return items

        max_workers = min(self.MAX_WORKERS, len(chunks))
        results_by_idx: dict[int, list[tuple[str, bool]]] = {}
        errors: list[tuple[int, Exception]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fn, chunk): i for i, chunk in enumerate(chunks)}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results_by_idx[idx] = future.result()
                except Exception as e:
                    errors.append((idx, e))
        if errors:
            raise ProviderUnavailable(
                f"{type(self).__name__}: {len(errors)}/{len(chunks)} chunks failed: "
                + "; ".join(f"[{i}] {e}" for i, e in errors[:3])
            )
        items = []
        for idx in sorted(results_by_idx):
            items.extend(results_by_idx[idx])
        return items

    # ==================== 低层能力（可选） ====================
    #
    # query_policy / query_policy_by_actions 用于"反向查询"：
    # 不给候选池、直接问"用户对该 action 有哪些资源的权限"，返回中立的
    # PolicyExpression AST（业务命名）。
    #
    # 不支持的 Provider 应保持默认返回 None，且 supports(POLICY_EXPRESSION)
    # 也返回 False；组合策略与业务层按 None 做能力退化。
    #
    # 注意：子类实现时，AST 里的字面量 ID 也必须通过 codec.decode_* 还原
    # 成业务命名再返回；否则上层会拿到方言 ID 与业务对不上。

    # ==================== 权限申请数据（可选） ====================

    def get_apply_data(
        self,
        action_ids: list[str],
        resources: list[ResourceInstance],
        subject: Subject,
    ) -> dict | None:
        """生成 IAM Application 格式的权限申请数据（前端 "permission" 字段）。

        入参全部为业务命名。Provider 自己负责：
          - 通过 codec 将 ID 编码为平台方言
          - 通过 callback / 数据库补全资源展示名称
          - 组装为 IAM 标准 Application 结构

        默认返回 None（不支持）；子类覆盖即可启用。

        Args:
            action_ids: 业务 action_id 列表
            resources: 被拒的资源实例列表（ResourceInstance）
            subject: 鉴权主体

        Returns:
            IAM Application 格式的 dict，或 None
        """
        return None

    # ==================== 低层能力（可选） ====================

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
    def plan_migration(self, schema: SchemaRegistry, *, scope: str = "full") -> MigrationPlan:
        """从本地 definitions + Provider 配置生成迁移计划（不查远端）。

        输出的是"本地期望状态"的 Change 列表，供 apply_migration 消费。
        apply_migration 负责查远端、reconcile、执行。

        Args:
            schema: 冻结的 SchemaRegistry。
            scope: "system" 只生成系统注册的 Change；
                   "full" 生成系统+操作+资源类型+角色的全量 Change。
        """

    @abstractmethod
    def apply_migration(
        self,
        plan: MigrationPlan,
        *,
        dry_run: bool = False,
        allow_destructive: bool = False,
    ) -> MigrationReport:
        """应用变更计划（查远端 + reconcile + 执行）。

        Provider 内部必须：
          1. 根据 plan 中的 Change 类型决定查询远端哪些数据
          2. 将每个 Change 与远端实际状态做 reconcile：
             CREATE + 远端已有 → 跳过
             UPDATE + 远端没有 → 降级为 CREATE
             DELETE + 远端没有 → 跳过
          3. 执行 reconcile 后的实际操作

        Args:
            plan: plan_migration 或迁移文件产出的 Change 列表。
            dry_run: 只演练，不真正提交。
            allow_destructive: 是否允许破坏性变更（默认禁止）。
        """

    # ==================== 运维 ====================

    @abstractmethod
    def health_check(self) -> dict:
        """探活。返回形如 {"status": "ok"|"error", "provider": self.name, ...}。"""
