"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from bkmonitor.utils.db import JsonField
from bkmonitor.utils.model_manager import AbstractRecordModel

__all__ = ["StrategyIssueConfig", "StrategyIssueConfigService", "IssueMergeRelation"]


class IssueMergeRelation(AbstractRecordModel):
    """Issue 合并/拆分关系表（独立映射层，与 IssueDocument 完全解耦）。

    设计要点：
    - 复用 AbstractRecordModel.create_time / create_user 表示合并发生时间 / 合并操作人；
    - status='split' 时，update_time / update_user 即为拆分时间 / 拆分操作人；
    - merge_reasons 与 split_reasons 单独保留，便于审计追溯；
    - 索引全部为普通索引，无 UNIQUE 强约束；唯一性由应用层 SELECT 校验保证，
      极小概率 race window 通过 bkm-cli list_conflicts 发现 + management command 修复。
    """

    STATUS_ACTIVE = "active"
    STATUS_SPLIT = "split"

    # 仅保留 MANUAL：主状态变更不再触发"拆分"，而是走 _cascade_follow_status 同步 ES status
    # 历史数据中可能存在 by_main_resolve / by_main_archive 值（旧 cascade_split 路径写入），
    # models 字段无 choices 约束可正常读出；新写入只用 MANUAL。
    SPLIT_KIND_MANUAL = "manual"

    class Meta:
        db_table = "bkmonitor_issue_merge_relation"
        verbose_name = "Issue 合并关系"
        indexes = [
            models.Index(fields=["bk_biz_id", "status", "main_issue_id"], name="idx_imr_biz_status_main"),
            models.Index(fields=["main_issue_id", "status"], name="idx_imr_main_status"),
            models.Index(fields=["member_issue_id", "status"], name="idx_imr_member_status"),
        ]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(main_issue_id=models.F("member_issue_id")),
                name="ck_imr_main_ne_member",
            ),
        ]

    bk_biz_id = models.IntegerField(verbose_name="业务 ID")
    main_issue_id = models.CharField(max_length=64, verbose_name="主 Issue ID")
    member_issue_id = models.CharField(max_length=64, verbose_name="并入 Issue ID")
    status = models.CharField(max_length=16, default=STATUS_ACTIVE, verbose_name="关系状态")
    merge_reasons = JsonField(default=list, verbose_name="合并依据")
    split_reasons = JsonField(default=None, null=True, blank=True, verbose_name="拆分依据")
    split_kind = models.CharField(max_length=16, default=None, null=True, blank=True, verbose_name="拆分触发类型")


class StrategyIssueConfig(AbstractRecordModel):
    """策略 Issue 聚合配置（唯一 MySQL 表）"""

    class Meta:
        db_table = "bkmonitor_strategy_issue_config"
        verbose_name = "策略 Issue 聚合配置"

    strategy_id = models.IntegerField(unique=True, db_index=True, verbose_name="策略 ID")
    bk_biz_id = models.IntegerField(db_index=True, verbose_name="业务 ID")
    aggregate_dimensions = JsonField(default=list, blank=True, verbose_name="聚合维度")
    conditions = JsonField(default=list, blank=True, verbose_name="过滤条件")
    alert_levels = JsonField(default=list, verbose_name="生效告警级别")

    VALID_CONDITION_METHODS = {"eq", "neq", "include", "exclude", "reg", "nreg"}

    @classmethod
    def _validate_condition_item(cls, cond: dict, effective_dimensions: set | None = None):
        if not isinstance(cond, dict):
            raise ValidationError({"conditions": f"conditions 条目必须为 dict，当前为 {type(cond)}"})

        required_keys = {"key", "method", "value"}
        missing = required_keys - set(cond.keys())
        if missing:
            raise ValidationError({"conditions": f"conditions 条目缺少字段: {sorted(missing)}"})

        key = cond.get("key")
        method = cond.get("method")
        value = cond.get("value")

        if not isinstance(key, str) or not key:
            raise ValidationError({"conditions": "conditions.key 必须为非空字符串"})
        if method not in cls.VALID_CONDITION_METHODS:
            raise ValidationError({"conditions": f"不支持的 method: {method}"})
        if value is None:
            raise ValidationError({"conditions": "conditions.value 不能为空"})
        if effective_dimensions is not None and key not in effective_dimensions:
            raise ValidationError({"conditions": f"conditions.key={key} 不在可用维度集合中"})

    def clean(self):
        if not self.alert_levels or not set(self.alert_levels).issubset({1, 2, 3}):
            raise ValidationError({"alert_levels": "alert_levels 必须为 [1,2,3] 的非空子集"})

        for cond in self.conditions:
            self._validate_condition_item(cond, set(self.aggregate_dimensions) if self.aggregate_dimensions else None)


class StrategyIssueConfigService:
    """StrategyIssueConfig 的创建 / 更新入口，含跨模型校验"""

    VALID_CONDITION_METHODS = {"eq", "neq", "include", "exclude", "reg", "nreg"}

    @classmethod
    def validate_aggregate_dimensions(cls, aggregate_dimensions: list, strategy_dimensions: set):
        if not aggregate_dimensions:
            return

        invalid = set(aggregate_dimensions) - strategy_dimensions
        if invalid:
            raise ValueError(
                f"aggregate_dimensions 包含当前策略公共维度之外的字段: {invalid}，"
                f"当前策略 Strategy.public_dimensions 为: {strategy_dimensions}"
            )

    @classmethod
    def validate_conditions(cls, conditions: list, effective_dimensions: set):
        for cond in conditions:
            try:
                StrategyIssueConfig._validate_condition_item(cond, effective_dimensions)
            except ValidationError as e:
                raise ValueError(e.message_dict.get("conditions", [str(e)])[0])

    @classmethod
    def save(cls, strategy_id: int, config_data: dict) -> StrategyIssueConfig:
        """
        创建或更新配置。
        校验顺序：跨模型子集校验 → Model.clean() 格式校验 → 全部通过后才落库。
        """
        from bkmonitor.models.strategy import StrategyModel
        from bkmonitor.strategy.new_strategy import Strategy

        strategies = Strategy.from_models(StrategyModel.objects.filter(id=strategy_id))
        if not strategies:
            raise ValueError(f"strategy_id={strategy_id} 不存在")
        strategy_obj = strategies[0]

        aggregate_dimensions = config_data.get("aggregate_dimensions", [])
        conditions = config_data.get("conditions", [])

        strategy_dimensions = set(strategy_obj.public_dimensions)
        cls.validate_aggregate_dimensions(aggregate_dimensions, strategy_dimensions)
        effective_dimensions = set(aggregate_dimensions) if aggregate_dimensions else strategy_dimensions
        if conditions:
            cls.validate_conditions(conditions, effective_dimensions)
        config_data["bk_biz_id"] = strategy_obj.bk_biz_id

        temp = StrategyIssueConfig(strategy_id=strategy_id, **config_data)
        temp.full_clean()

        config, _ = StrategyIssueConfig.objects.update_or_create(
            strategy_id=strategy_id,
            defaults=config_data,
        )
        return config


def _has_cache_role() -> bool:
    """仅 api / worker 进程具备缓存写入能力；web 进程无缓存配置，跳过。"""
    from django.conf import settings

    return settings.ROLE in ("api", "worker")


@receiver(post_save, sender=StrategyIssueConfig)
@receiver(post_delete, sender=StrategyIssueConfig)
def refresh_strategy_cache_on_issue_config_change(sender, instance, **kwargs):
    """issue_config 变更时精准更新策略缓存中的 issue_config 字段。

    不调用全量 StrategyCacheManager.refresh()，而是直接读取当前策略的 Redis 缓存 key，
    更新其中的 issue_config 子字段后写回，避免全量刷新开销。
    缓存未命中时静默跳过，等待后台 smart_refresh 任务重建。

    此 handler 主要兜底"直接操作 StrategyIssueConfig"的场景（如紧急运维），
    正常 SaveStrategyV2Resource 路径下 web 进程不具备缓存写入能力（_has_cache_role() = False），
    handler 会提前返回，缓存由后台任务异步重建。
    """
    import json

    if not _has_cache_role():
        return
    try:
        from alarm_backends.core.cache.strategy import StrategyCacheManager

        strategy_id = instance.strategy_id
        cache_key = StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=strategy_id)
        cached_str = StrategyCacheManager.cache.get(cache_key)
        if not cached_str:
            return

        strategy_dict = json.loads(cached_str)
        # 重新查 MySQL 获取最新 issue_config：
        # - post_save 后返回当前有效记录；post_delete 后返回 None（对应关闭 Issues）
        cfg = StrategyIssueConfig.objects.filter(strategy_id=strategy_id).first()
        strategy_dict["issue_config"] = (
            {
                "is_enabled": cfg.is_enabled,
                "aggregate_dimensions": cfg.aggregate_dimensions,
                "conditions": cfg.conditions,
                "alert_levels": cfg.alert_levels,
            }
            if cfg
            else None
        )
        StrategyCacheManager.cache.set(cache_key, json.dumps(strategy_dict), StrategyCacheManager.CACHE_TIMEOUT)
    except Exception:
        pass


class IssueTapdRelation(AbstractRecordModel):
    """
    Issue 与 TAPD 单据关联关系
    """

    bk_biz_id = models.IntegerField(verbose_name="业务 ID")
    issue_id = models.CharField(max_length=64, verbose_name="Issue ID")
    workspace_id = models.IntegerField(verbose_name="TAPD 项目 ID")
    tapd_id = models.IntegerField(verbose_name="TAPD 单据 ID")
    tapd_type = models.CharField(
        max_length=16,
        verbose_name="TAPD 单据类型",
        choices=[
            ("story", "需求"),
            ("bug", "缺陷"),
        ],
    )
    tapd_title = models.CharField(max_length=255, verbose_name="TAPD 单据标题", default="")
    link_mode = models.CharField(
        max_length=16,
        verbose_name="关联模式",
        choices=[
            ("create", "新建单据"),
            ("link", "关联已有"),
        ],
        default="create",
    )
    sync_status = models.BooleanField(default=False, verbose_name="是否同步单据状态")

    class Meta:
        db_table = "bkmonitor_issue_tapd_relation"
        verbose_name = "Issue TAPD 关联关系"
        constraints = [
            models.UniqueConstraint(fields=["bk_biz_id", "issue_id", "workspace_id", "tapd_id"], name="uniq_issue_tapd")
        ]
