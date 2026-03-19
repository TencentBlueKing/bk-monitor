"""
Issues 模块后台数据流验证脚本

用途：在 API 层未开发前，通过 ORM 直接操作 StrategyIssueConfig，
     为测试策略快速配置 Issues 聚合规则，验证后台 Issues 处理流程。

使用方式（在 bk-monitor 项目根目录下）：

    # 创建配置
    python manage.py shell < alarm_backends/service/issue/test.py

    # 或直接在 shell 中 import 使用各函数

配置参数说明（修改本文件底部 CONFIG 区域）：
    STRATEGY_ID       - 目标测试策略 ID（必填）
    BK_BIZ_ID         - 业务 ID（必填）
    AGGREGATE_DIMS    - 聚合维度（空列表表示使用策略公共维度）
    CONDITIONS        - 过滤条件（空列表表示不过滤，所有告警均触发 Issue）
    ALERT_LEVELS      - 生效告警级别（1=致命, 2=预警, 3=提醒）
"""

import sys

# ──────────────────────────────────────────────────────────────────
# 测试配置区域：按实际测试策略修改以下参数
# ──────────────────────────────────────────────────────────────────

STRATEGY_ID = 12345  # 替换为实际测试策略 ID
BK_BIZ_ID = 2  # 替换为实际业务 ID

# 聚合维度：空列表 = 使用策略运行时公共维度；非空时必须是策略公共维度的子集
AGGREGATE_DIMS = []

# 过滤条件：空列表 = 不过滤，所有满足级别的告警均触发 Issue
# 示例：[{"key": "service", "method": "eq", "value": ["order"]}]
CONDITIONS = []

# 生效告警级别：1=致命(FATAL), 2=预警(WARNING), 3=提醒(REMIND)；必须为非空子集
ALERT_LEVELS = [1, 2, 3]

# ──────────────────────────────────────────────────────────────────


def setup_issue_config(
    strategy_id: int = STRATEGY_ID,
    bk_biz_id: int = BK_BIZ_ID,
    aggregate_dimensions: list = None,
    conditions: list = None,
    alert_levels: list = None,
    is_enabled: bool = True,
):
    """
    直接通过 ORM 创建或更新 StrategyIssueConfig。

    绕过 StrategyIssueConfigService 的策略缓存校验，适合在策略可能未缓存的
    测试环境中使用。

    Returns:
        创建或更新后的 StrategyIssueConfig 实例
    """
    from bkmonitor.models.issue import StrategyIssueConfig

    if aggregate_dimensions is None:
        aggregate_dimensions = AGGREGATE_DIMS
    if conditions is None:
        conditions = CONDITIONS
    if alert_levels is None:
        alert_levels = ALERT_LEVELS

    config, created = StrategyIssueConfig.objects.update_or_create(
        strategy_id=strategy_id,
        defaults={
            "bk_biz_id": bk_biz_id,
            "aggregate_dimensions": aggregate_dimensions,
            "conditions": conditions,
            "alert_levels": alert_levels,
            "is_enabled": is_enabled,
            "is_deleted": False,
        },
    )

    action = "创建" if created else "更新"
    print(f"[OK] StrategyIssueConfig {action}成功")
    print(f"     strategy_id       = {config.strategy_id}")
    print(f"     bk_biz_id         = {config.bk_biz_id}")
    print(f"     is_enabled        = {config.is_enabled}")
    print(f"     aggregate_dims    = {config.aggregate_dimensions}")
    print(f"     conditions        = {config.conditions}")
    print(f"     alert_levels      = {config.alert_levels}")
    return config


def refresh_cache(strategy_id: int = STRATEGY_ID) -> bool:
    """
    将指定策略的配置从 MySQL 同步到 Redis 缓存。
    成功返回 True，失败返回 False。
    """
    try:
        from bkmonitor.models.issue import StrategyIssueConfig
        from alarm_backends.core.cache.issue import StrategyIssueConfigCache

        config = StrategyIssueConfig.objects.filter(strategy_id=strategy_id, is_deleted=False).first()
        if not config:
            print(f"[WARN] strategy_id={strategy_id} 的配置不存在，跳过缓存刷新")
            return False

        StrategyIssueConfigCache.upsert(config)
        print(f"[OK] Redis 缓存已刷新，strategy_id={strategy_id}")
        return True
    except Exception as e:
        print(f"[WARN] 缓存刷新失败（不影响功能，processor 会降级读 MySQL）: {e}")
        return False


def verify_config(strategy_id: int = STRATEGY_ID) -> None:
    """读取并打印当前配置，同时检查 Redis 缓存状态。"""
    from bkmonitor.models.issue import StrategyIssueConfig
    from alarm_backends.core.cache.issue import StrategyIssueConfigCache

    print(f"\n===== StrategyIssueConfig 验证（strategy_id={strategy_id}）=====")

    config = StrategyIssueConfig.objects.filter(strategy_id=strategy_id, is_deleted=False).first()
    if not config:
        print("[FAIL] MySQL 中未找到该配置")
        return

    print("[MySQL]")
    print(f"  id                = {config.id}")
    print(f"  strategy_id       = {config.strategy_id}")
    print(f"  bk_biz_id         = {config.bk_biz_id}")
    print(f"  is_enabled        = {config.is_enabled}")
    print(f"  aggregate_dims    = {config.aggregate_dimensions}")
    print(f"  conditions        = {config.conditions}")
    print(f"  alert_levels      = {config.alert_levels}")

    cached = StrategyIssueConfigCache.get(strategy_id)
    if cached:
        print("\n[Redis 缓存] 命中")
        print(f"  is_enabled        = {cached.get('is_enabled')}")
        print(f"  aggregate_dims    = {cached.get('aggregate_dimensions')}")
        print(f"  conditions        = {cached.get('conditions')}")
        print(f"  alert_levels      = {cached.get('alert_levels')}")
    else:
        print("\n[Redis 缓存] 未命中（processor 将降级读取 MySQL）")

    print("=" * 60)


def disable_issue_config(strategy_id: int = STRATEGY_ID) -> None:
    """禁用配置（不删除），方便停止 Issue 聚合而不清除记录。"""
    from bkmonitor.models.issue import StrategyIssueConfig
    from alarm_backends.core.cache.issue import StrategyIssueConfigCache

    updated = StrategyIssueConfig.objects.filter(strategy_id=strategy_id, is_deleted=False).update(is_enabled=False)
    if updated:
        StrategyIssueConfigCache.invalidate(strategy_id)
        print(f"[OK] strategy_id={strategy_id} 的配置已禁用，缓存已清除")
    else:
        print(f"[WARN] 未找到 strategy_id={strategy_id} 的配置")


def delete_issue_config(strategy_id: int = STRATEGY_ID) -> None:
    """软删除配置并清除缓存（完全移除聚合规则）。"""
    from bkmonitor.models.issue import StrategyIssueConfig
    from alarm_backends.core.cache.issue import StrategyIssueConfigCache

    updated = StrategyIssueConfig.objects.filter(strategy_id=strategy_id).update(is_deleted=True, is_enabled=False)
    if updated:
        StrategyIssueConfigCache.invalidate(strategy_id)
        print(f"[OK] strategy_id={strategy_id} 的配置已软删除，缓存已清除")
    else:
        print(f"[WARN] 未找到 strategy_id={strategy_id} 的配置")


def simulate_processor(alert_id: str, strategy_id: int = STRATEGY_ID) -> None:
    """
    模拟 IssueAggregationProcessor 的完整执行流程（使用真实 AlertDocument）。
    用于端到端验证：配置读取 → 条件过滤 → Issue 查找/创建 → 告警关联。

    注意：此函数需要 ES 和 Redis 连通，且指定的 alert_id 在 ES 中存在。
    """
    from bkmonitor.documents.alert import AlertDocument
    from alarm_backends.service.fta_action.issue_processor import IssueAggregationProcessor
    from alarm_backends.core.cache.strategy import StrategyCacheManager

    print(f"\n===== 模拟 IssueAggregationProcessor（strategy_id={strategy_id}）=====")

    hits = AlertDocument.search(all_indices=True).filter("term", id=alert_id).params(size=1).execute().hits
    if not hits:
        print(f"[FAIL] AlertDocument id={alert_id} 在 ES 中不存在")
        return
    alert = AlertDocument(**hits[0].to_dict())
    print(f"[OK] 已加载告警: id={alert.id}, severity={alert.severity}")

    strategy = StrategyCacheManager.get_strategy_by_id(strategy_id) or {
        "id": strategy_id,
        "bk_biz_id": BK_BIZ_ID,
        "name": f"测试策略_{strategy_id}",
        "labels": [],
        "items": [],
    }
    print(f"[INFO] 策略快照: name={strategy.get('name')}, bk_biz_id={strategy.get('bk_biz_id')}")

    processor = IssueAggregationProcessor(alert=alert, strategy=strategy)
    result = processor.process()
    print(f"[{'OK' if result else 'SKIP'}] process() 返回: {result}")
    if result:
        print(f"[OK] 告警已关联到 Issue，alert.issue_id={alert.issue_id}")
    print("=" * 60)


# ──────────────────────────────────────────────────────────────────
# 默认执行：创建配置 → 刷新缓存 → 验证
# 可根据需要注释/替换以下调用
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__" or "shell" in sys.argv:
    print(f"\n>>> 初始化 Issues 配置（strategy_id={STRATEGY_ID}）")
    setup_issue_config()
    refresh_cache()
    verify_config()
    print("\n提示：如需模拟端到端流程，调用 simulate_processor('<alert_id>')")
