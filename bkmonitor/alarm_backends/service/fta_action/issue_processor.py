"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import hashlib
import json
import logging
import random
import time

from django.conf import settings

from alarm_backends.core.cache.key import (
    ISSUE_ACTIVE_CONTENT_KEY,
    ISSUE_ACTIVE_COUNT_KEY,
    ISSUE_FINGERPRINT_LOCK,
    ISSUE_LEGACY_MIGRATION_DONE_KEY,
)
from alarm_backends.core.control.item import gen_condition_matcher
from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.documents.issue import (
    IssueActivityDocument,
    IssueDocument,
)
from constants.issue import IssueActivityType, IssuePriority, IssueStatus
from core.prometheus import metrics

logger = logging.getLogger("fta_action.issue")


def gen_issue_fingerprint(strategy_id: int, aggregate_dimensions: list[str], alert_dims: dict) -> str | None:
    """生成 Issue 唯一指纹。

    规则：
    - aggregate_dimensions 为空 → 退化为 ``strategy:{strategy_id}``，与旧版本 1:1 行为兼容
    - 任一维度在 alert_dims 中缺失 / None / "" → 返回 None，调用方据此跳过该告警
      （决策：同策略下"维度凑不齐"的告警不进入任何 Issue 池，避免污染聚合）
    - 维度按 key 排序后参与，保证配置项顺序不影响指纹稳定性
    - 值统一 str()；md5 收口避免 Redis key 过长 / 维度值含特殊字符
    """
    if not aggregate_dimensions:
        return f"strategy:{strategy_id}"

    parts = []
    for key in sorted(aggregate_dimensions):
        value = alert_dims.get(key)
        if value is None or value == "":
            return None
        # 类型归一化：alert dim 上游应稳定，但跨数据源 / 升级窗口可能出现 int vs str 差异，
        # 统一 str(...).strip() 避免同一具体问题被切分。bool 等罕见类型由 str() 决定形态
        normalized = str(value).strip()
        if not normalized:
            return None
        parts.append(f"{key}={normalized}")

    payload = f"strategy:{strategy_id}|{'|'.join(parts)}"
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


# 维度值过长时截断阈值（避免列表展示拉宽），保留前 N 个字符 + "..."
_NAME_DIM_VALUE_MAX_LEN = 40


def build_issue_default_name(strategy_name: str, dimension_values: dict, is_regression: bool) -> str:
    """生成 Issue 默认名称。

    格式：``[回归] {strategy_name} - {v1} | {v2}``（dimension_values 非空时追加 value 后缀）
    维度值后缀按 key 排序拼接（与 fingerprint 排序口径一致），保证同 fingerprint 名称稳定。
    单值过长时截断为 ``{prefix}...``，避免列表页拉宽；用户后续可手工编辑覆盖。

    Args:
        strategy_name: 策略名称（来自 self.strategy.get("name")）
        dimension_values: 维度值快照，形如 ``{"bk_host_id": "9185731"}``；空 dict 时不追加后缀
        is_regression: 是否为回归（同 fingerprint 有 RESOLVED 历史）
    """
    base = f"[回归] {strategy_name}" if is_regression else strategy_name
    if not dimension_values:
        return base

    parts = []
    for key in sorted(dimension_values.keys()):
        value = str(dimension_values[key])
        if len(value) > _NAME_DIM_VALUE_MAX_LEN:
            value = value[: _NAME_DIM_VALUE_MAX_LEN - 3] + "..."
        parts.append(value)
    return f"{base} - {' | '.join(parts)}"


class IssueAggregationProcessor:
    """Issue 聚合处理器：在 fta_action 阶段将告警聚合到 Issue"""

    def __init__(self, alert: AlertDocument, strategy: dict):
        self.alert = alert
        self.strategy = strategy
        self.strategy_id = strategy.get("id") or (int(alert.strategy_id) if alert.strategy_id else 0)

    def process(self) -> bool:
        """主入口：配置校验 → 计算指纹 → 查找活跃 Issue → 创建 / 关联。

        指纹改造后：同策略下按 aggregate_dimensions 切分活跃 Issue。
        缺维度告警直接跳过；空 aggregate_dimensions 退化为 1 策略 1 Issue（兼容）。
        """
        if not self.strategy_id:
            return False

        config = self._get_strategy_config()
        if not config or not config.get("is_enabled"):
            return False
        if not self._check_alert_level(config):
            return False
        if not self._check_conditions(config):
            return False

        # 指纹生成：按 aggregate_dimensions 取告警维度值。缺维度直接跳过，不参与任何 Issue 关联
        alert_dims = self._get_alert_dimensions()
        aggregate_dimensions = config.get("aggregate_dimensions") or []
        fingerprint = gen_issue_fingerprint(self.strategy_id, aggregate_dimensions, alert_dims)
        if fingerprint is None:
            metrics.ISSUE_FINGERPRINT_BLOCKED.labels(
                bk_biz_id=str(self.strategy.get("bk_biz_id", 0) or 0), reason="missing_dim"
            ).inc()
            logger.debug(
                "[issue] missing aggregate dimension, skip, strategy(%s) alert(%s) dims=%s required=%s",
                self.strategy_id,
                self.alert.id,
                list(alert_dims.keys()),
                aggregate_dimensions,
            )
            return False

        # dimension_values 与 fingerprint 一对一，作为 Issue 上的展示快照与漏关联补偿反算的输入。
        # 按 sorted(aggregate_dimensions) 构建 + str(...).strip() 归一化，与 gen_issue_fingerprint 完全一致；
        # 否则 " 9185731 " 与 "9185731" 算同一 fingerprint 但 dimension_values 快照保存为不同字符串，
        # 导致 dimension_values.* 精确过滤不命中、TopN 桶分裂、Issue 名称后缀展示为带空白形态。
        dimension_values = {key: str(alert_dims[key]).strip() for key in sorted(aggregate_dimensions)}

        issue = self._find_active_issue(fingerprint)

        if issue is None:
            # 高基数采样：触达阈值时仅 metric + warning（warn-only，不阻塞新建避免丢告警）
            # 仅在"需要新建 Issue"路径采样上报，避免每条告警都打 ES count 成为热点
            self._check_active_issue_count()

            lock = self._acquire_lock(fingerprint)
            if not lock:
                logger.warning(
                    "[issue] acquire lock failed, skip, strategy(%s) fingerprint(%s) alert(%s)",
                    self.strategy_id,
                    fingerprint,
                    self.alert.id,
                )
                return False
            try:
                issue = self._find_active_issue(fingerprint)
                if issue is None:
                    issue = self._create_issue(config, fingerprint, dimension_values)
                    issue._persist_and_cache(active=True)
                    self._write_create_activity_with_retry(issue, dimension_values)
            finally:
                try:
                    lock.release()
                except Exception:
                    pass

        self._associate_alert(issue)
        return True

    def _get_strategy_config(self) -> dict | None:
        """从策略缓存 JSON 直接读取 issue_config，无需额外 Redis 查询。"""
        return self.strategy.get("issue_config")

    def _check_alert_level(self, config: dict) -> bool:
        alert_levels = config.get("alert_levels", [])
        if not alert_levels:
            return False
        severity = int(self.alert.severity) if self.alert.severity else 0
        return severity in alert_levels

    def _check_conditions(self, config: dict) -> bool:
        """复用 access 模块 gen_condition_matcher 匹配告警维度"""
        conditions = config.get("conditions", [])
        if not conditions:
            return True

        alert_dimensions = self._get_alert_dimensions()
        agg_condition = []
        for cond in conditions:
            if not isinstance(cond, dict):
                logger.warning(
                    "[issue] invalid condition type, strategy(%s) alert(%s) condition=%s",
                    self.strategy_id,
                    self.alert.id,
                    cond,
                )
                return False

            if any(k not in cond for k in ("key", "method", "value")):
                logger.warning(
                    "[issue] invalid condition format, strategy(%s) alert(%s) condition=%s",
                    self.strategy_id,
                    self.alert.id,
                    cond,
                )
                return False

            if not cond.get("key") or cond.get("value") is None:
                logger.warning(
                    "[issue] invalid condition value, strategy(%s) alert(%s) condition=%s",
                    self.strategy_id,
                    self.alert.id,
                    cond,
                )
                return False

            agg_condition.append({"key": cond["key"], "method": cond["method"], "value": cond["value"]})

        if not agg_condition:
            logger.warning(
                "[issue] conditions present but empty after parse, strategy(%s) alert(%s)",
                self.strategy_id,
                self.alert.id,
            )
            return False

        try:
            matcher = gen_condition_matcher(agg_condition)
            return matcher.is_match(alert_dimensions)
        except Exception:
            logger.warning(
                "[issue] condition match failed, strategy(%s) alert(%s)",
                self.strategy_id,
                self.alert.id,
                exc_info=True,
            )
            return False

    def _get_alert_dimensions(self) -> dict:
        """从 AlertDocument.dimensions 构建 {key: value} 映射"""
        dimensions = {}
        if not self.alert.dimensions:
            return dimensions
        for dim in self.alert.dimensions:
            if isinstance(dim, dict):
                key = dim.get("key", "")
                value = dim.get("value", "")
            else:
                key = getattr(dim, "key", "")
                value = getattr(dim, "value", "")
            if key:
                dimensions[key] = value
        return dimensions

    def _find_active_issue(self, fingerprint: str) -> IssueDocument | None:
        """按 fingerprint 查找活跃 Issue：Redis → ES → 部署窗口期 legacy 兜底。

        正常运行期：所有活跃 Issue 都有 fingerprint（部署时 post_migrate hook
        `migrate_legacy_active_issues` 已一次性 RESOLVE 旧 1:1 数据），Step 1/2 即可命中。

        部署窗口期：fta_web 的 post_migrate hook 仅在 web/api role 触发，worker pod 滚动
        部署时可能先于 web migrate 完成 → ES 中仍存在 fingerprint=null 的活跃 Issue。
        Step 3 read-only 兜底：直接关联到该旧 Issue（**不写 fingerprint、不调缓存、不抢锁**），
        部署窗口期表现等价旧 1:1 模型；migrate 跑完后旧 Issue 变 RESOLVED 不再被命中，
        无并发抢绑风险（多个 fingerprint 共绑同一旧 Issue 与旧模型语义一致）。
        """
        cache_key = ISSUE_ACTIVE_CONTENT_KEY.get_key(fingerprint=fingerprint)
        cached = ISSUE_ACTIVE_CONTENT_KEY.client.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                return IssueDocument(**data)
            except Exception:
                pass

        # Step 1: 标准路径 — 按 fingerprint 查 ES 活跃 Issue
        search = (
            IssueDocument.search(all_indices=True)
            .filter("term", fingerprint=fingerprint)
            .filter("terms", status=IssueStatus.ACTIVE_STATUSES)
            .sort("-create_time")
            .params(size=1)
        )
        hits = search.execute().hits
        if hits:
            issue = IssueDocument(**hits[0].to_dict())
            issue._update_redis_cache()
            return issue

        # Step 2: 部署窗口期 read-only 兜底 — 同 strategy_id 下 fingerprint=null 的活跃 Issue
        # 仅在迁移函数尚未完成时短期触达，迁移完成后该分支自然不再命中。
        # 性能优化：检查全局哨兵 cache（migrate_legacy_active_issues 完成时由 _mark_legacy_migration_done 设置），
        # 若标记存在 → 跳过 fallback ES 查询（避免每个新 fingerprint 的"无活跃 Issue 新建"路径
        # 多打 1-2 次 fingerprint=null 全索引查询）。Redis 故障 fail-open 走 fallback 保证正确性。
        if self._legacy_migration_done():
            return None

        legacy_search = (
            IssueDocument.search(all_indices=True)
            .filter("term", strategy_id=str(self.strategy_id))
            .filter("terms", status=IssueStatus.ACTIVE_STATUSES)
            .exclude("exists", field="fingerprint")
            .sort("-create_time")
            .params(size=1)
        )
        legacy_hits = legacy_search.execute().hits
        if legacy_hits:
            issue = IssueDocument(**legacy_hits[0].to_dict())
            # 部署窗口期 metric 上报：正常情况应分钟级回零；持续非零说明 migrate 未成功
            metrics.ISSUE_LEGACY_FALLBACK_HIT.labels(bk_biz_id=str(self.strategy.get("bk_biz_id", 0) or 0)).inc()
            logger.info(
                "[issue] legacy fallback (deploy window): assoc to fingerprint=null active issue, "
                "strategy(%s) issue(%s) alert(%s)",
                self.strategy_id,
                issue.id,
                self.alert.id,
            )
            # 关键：不调 _update_redis_cache（issue.fingerprint=None 会被 guard 跳过）
            # 也不写任何字段；调用方 process() 仅做 _associate_alert（写 alert.issue_id）
            # Trade-off：alert.issue_id 永久指向被 migrate RESOLVE 的旧 Issue（best-effort），
            # 不会被周期任务重新关联到新 fingerprint Issue。详见 fingerprint-design.md §6.4
            return issue

        return None

    @staticmethod
    def _legacy_migration_done() -> bool:
        """检查全局 legacy 迁移完成哨兵。

        True → 跳过 _find_active_issue 的 Step 2 legacy fallback ES 查询。
        Redis 故障 / key 不存在 / 异常 → False（fail-open 走 fallback，正确性优先于性能）。
        部署窗口期 cache 还未 set，processor 走 fallback；migrate 完成后 cache set，
        后续每个新 fingerprint 的"无活跃 Issue 新建"路径不再多打 fingerprint=null 全索引查询。
        """
        try:
            cache_key = ISSUE_LEGACY_MIGRATION_DONE_KEY.get_key()
            return bool(ISSUE_LEGACY_MIGRATION_DONE_KEY.client.exists(cache_key))
        except Exception:
            return False

    def _create_issue(self, config: dict, fingerprint: str, dimension_values: dict) -> IssueDocument:
        now = int(time.time())
        # 回归判断按 fingerprint：同一具体问题（同维度组合）再次发生才算 regression
        # 不再按 strategy_id，避免同策略不同维度的首次告警被错标
        is_regression = self._check_is_regression(fingerprint)

        strategy_name = self.strategy.get("name", "")
        # 默认名称含 dimension_values 后缀，提高列表辨识度（同策略下 N 个 Issue 不会同名）
        # 用户后续可手工编辑覆盖（spec.md FR-01）
        name = build_issue_default_name(strategy_name, dimension_values, is_regression)

        labels = []
        for label in self.strategy.get("labels", []):
            if isinstance(label, str):
                labels.append(label)

        issue = IssueDocument(
            strategy_id=str(self.strategy_id),
            bk_biz_id=str(self.strategy.get("bk_biz_id", "")),
            name=name,
            status=IssueStatus.PENDING_REVIEW,
            is_regression=is_regression,
            assignee=[],
            priority=IssuePriority.DEFAULT,
            alert_count=1,
            first_alert_time=self.alert.begin_time or now,
            last_alert_time=self.alert.begin_time or now,
            impact_scope={},
            strategy_name=strategy_name,
            labels=labels,
            aggregate_config={
                # 强制 None → []：保证周期任务从快照反算 fingerprint 时的退化语义与 process() 一致
                "aggregate_dimensions": config.get("aggregate_dimensions") or [],
                "conditions": config.get("conditions") or [],
                "alert_levels": config.get("alert_levels") or [],
            },
            fingerprint=fingerprint,
            dimension_values=dimension_values,
            create_time=now,
            update_time=now,
        )
        return issue

    def _check_is_regression(self, fingerprint: str) -> bool:
        """同 fingerprint 有 RESOLVED 历史则标记回归（同一具体问题再次发生）。"""
        count = (
            IssueDocument.search(all_indices=True)
            .filter("term", fingerprint=fingerprint)
            .filter("term", status=IssueStatus.RESOLVED)
            .count()
        )
        return count > 0

    def _check_active_issue_count(self) -> None:
        """单策略活跃 Issue 数采样上报（**warn-only**：仅 metric + warning，不阻塞新建）。

        历史决策：旧实现触达阈值时 return False 阻塞新建——但这会导致超阈值后该策略
        所有缺失 fingerprint 命中的告警永久失联（process return False，alert.issue_id 不写）。
        改为 warn-only：metric 上报 + warning 日志，告警仍正常创建 Issue。运维通过
        `bkmonitor_issue_fingerprint_blocked{reason=high_cardinality}` 速率告警发现高基数策略。

        ES count 加 5 min Redis cache：防御性指标对实时性要求低，避免每条告警都打 ES count
        在高 QPS 场景下成为热点（参考 alert QoS counter 的同款思路）。

        返回值统一为 None：调用方只触发副作用（metric/log），不消费返回值，避免因接口返回值
        变化遗留 dead branch（参考第三轮 review Major-1）。
        """
        threshold = getattr(settings, "ISSUE_MAX_ACTIVE_PER_STRATEGY", 0) or 0
        if threshold <= 0:
            return

        # 用 ISSUE_ACTIVE_COUNT_KEY 注册的 RedisDataKey 走 KEY_PREFIX，避免裸 key 跨环境串污
        # cache get/set 全部 fail-open：Redis 故障 → 跳过观测（warn-only 无副作用，不破坏主链路）
        cache_key = ISSUE_ACTIVE_COUNT_KEY.get_key(strategy_id=self.strategy_id)
        client = ISSUE_ACTIVE_COUNT_KEY.client
        try:
            cached = client.get(cache_key)
        except Exception:
            return  # Redis 故障 → 直接跳过 active count 观测，不打 ES count，不影响 process 主路径

        count = -1
        if cached is not None:
            try:
                count = int(cached)
            except (TypeError, ValueError):
                count = -1

        if count < 0:
            # cache miss thundering herd 防护（review M1）：高基数策略 5min TTL 失效瞬间会有
            # 多 worker 同时 miss → 同时打 ES count（峰值 ~1000 QPS）。
            # 用 SET NX EX 10s 短锁让一个 worker 探 ES，其他 worker 跳过本次观测；
            # warn-only 路径单次观测丢弃无副作用，下个周期重试。
            probe_lock_key = f"{cache_key}.probe_lock"
            try:
                acquired = client.set(probe_lock_key, "1", nx=True, ex=10)
            except Exception:
                return
            if not acquired:
                return  # 其他 worker 正在探 ES，本 worker 跳过；不主动 release（10s TTL 自然过期）

            count = (
                IssueDocument.search(all_indices=True)
                .filter("term", strategy_id=str(self.strategy_id))
                .filter("terms", status=IssueStatus.ACTIVE_STATUSES)
                .count()
            )
            try:
                # jittered TTL（±20%）打散多 worker 同时失效引发的下一次穿透：
                # 5min ±20% = 4-6 min 随机，避免周期性同步失效
                jittered_ttl = int(ISSUE_ACTIVE_COUNT_KEY.ttl * (0.8 + random.random() * 0.4))
                client.set(cache_key, str(count), ex=jittered_ttl)
            except Exception:
                # cache set 失败不影响本次观测（已经查到 ES count），下次重新查
                pass

        if count >= threshold:
            metrics.ISSUE_FINGERPRINT_BLOCKED.labels(
                bk_biz_id=str(self.strategy.get("bk_biz_id", 0) or 0),
                reason="high_cardinality",
            ).inc()
            logger.warning(
                "[issue] active count exceeds threshold (warn-only, alert NOT dropped), "
                "strategy(%s) count=%d threshold=%d alert(%s)",
                self.strategy_id,
                count,
                threshold,
                self.alert.id,
            )
        # warn-only：不返回 bool，避免调用方误以为是熔断信号

    def _write_create_activity_with_retry(self, issue: IssueDocument, dimension_values: dict | None) -> None:
        """写 CREATE 活动日志，失败重试 1 次。

        与 _persist_and_cache / _associate_alert 的双写策略保持一致；仍失败则 error log
        + metric 上报，但不阻塞主流程（活动日志缺失只影响审计完整性，不影响核心功能）。
        运维通过 `bkmonitor_issue_create_activity_lost` 速率告警发现 ES 持续异常。
        """
        activity = self._make_create_activity(issue, dimension_values)
        try:
            IssueActivityDocument.bulk_create([activity])
            return
        except Exception as e:
            logger.warning(
                "[issue] create activity write failed (retry), strategy(%s) issue(%s) error=%s",
                self.strategy_id,
                issue.id,
                e,
            )
        try:
            IssueActivityDocument.bulk_create([activity])
        except Exception as e2:
            logger.error(
                "[issue] create activity write failed permanently, strategy(%s) issue(%s) error=%s",
                self.strategy_id,
                issue.id,
                e2,
            )
            try:
                metrics.ISSUE_CREATE_ACTIVITY_LOST.labels(bk_biz_id=str(self.strategy.get("bk_biz_id", 0) or 0)).inc()
            except Exception:
                # metric 失败不影响主路径（极不可能，但兜底）
                pass

    def _make_create_activity(
        self, issue: IssueDocument, dimension_values: dict | None = None
    ) -> IssueActivityDocument:
        """构造 CREATE 活动日志。

        新模型下同策略可同时存在 N 个 Issue，活动日志补 fingerprint + dimension_values
        以便用户在活动详情区分"该 Issue 由哪个维度组合的告警触发创建"。
        dimension_values 为空（aggregate_dimensions=[] 退化路径）时 content 写空串。
        """
        now = int(time.time())
        return IssueActivityDocument(
            issue_id=issue.id,
            bk_biz_id=issue.bk_biz_id,
            activity_type=IssueActivityType.CREATE,
            operator="system",
            to_value=issue.fingerprint or "",
            content=json.dumps(dimension_values, ensure_ascii=False) if dimension_values else "",
            time=now,
            create_time=now,
        )

    def _associate_alert(self, issue: IssueDocument):
        """写入 AlertDocument.issue_id，失败重试 1 次"""
        self.alert.issue_id = issue.id
        try:
            AlertDocument.bulk_create(
                [AlertDocument(id=self.alert.id, issue_id=issue.id)],
                action=BulkActionType.UPSERT,
            )
        except Exception as e:
            logger.warning(
                "[issue] alert issue_id write failed (retry), strategy(%s) alert(%s) error=%s",
                self.strategy_id,
                self.alert.id,
                e,
            )
            try:
                AlertDocument.bulk_create(
                    [AlertDocument(id=self.alert.id, issue_id=issue.id)],
                    action=BulkActionType.UPSERT,
                )
            except Exception as e2:
                logger.error(
                    "[issue] alert issue_id write failed permanently, strategy(%s) issue(%s) alert(%s) error=%s",
                    self.strategy_id,
                    issue.id,
                    self.alert.id,
                    e2,
                )

    def _acquire_lock(self, fingerprint: str):
        """按 fingerprint 抢锁。不同 fingerprint 互不阻塞，同 fingerprint 并发只允许 1 个进入新建路径。

        一次性尝试获取，失败返回 None；使用 token 保证只释放自己持有的锁。
        """
        import uuid as _uuid

        lock_key = ISSUE_FINGERPRINT_LOCK.get_key(fingerprint=fingerprint)
        client = ISSUE_FINGERPRINT_LOCK.client
        token = _uuid.uuid4().hex
        acquired = client.set(lock_key, token, nx=True, ex=ISSUE_FINGERPRINT_LOCK.ttl)
        if acquired:
            return _TokenLock(client, lock_key, token)
        return None


class _TokenLock:
    """基于 token 的安全锁：只释放自己持有的锁，避免 TTL 过期后误删"""

    _release_script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """

    def __init__(self, client, key, token):
        self._client = client
        self._key = key
        self._token = token

    def release(self):
        self._client.eval(self._release_script, 1, self._key, self._token)
