"""
Issues 模块后台数据流验证脚本

用途：在 API 层未开发前，通过 ORM 直接操作 StrategyIssueConfig，
     为测试策略快速配置 Issues 聚合规则，验证后台 Issues 处理流程。

使用方式（在 bk-monitor 项目根目录下）：

    # 进入 shell 后按需调用
    python manage.py shell

    # 注入配置（strategy_id 必填，其余可选）
    from alarm_backends.service.issue.test import *
    main(strategy_id=12345)
    main(strategy_id=12345, alert_levels=[1, 2], conditions=[{"key": "service", "method": "eq", "value": ["order"]}])

    # 清理配置
    cleanup(strategy_id=12345)

    # 验证当前状态
    verify_config(strategy_id=12345)

    # 模拟端到端流程（需要 ES 中存在该告警）
    simulate_processor(alert_id="xxx", strategy_id=12345)
"""


def _get_strategy(strategy_id: int) -> dict:
    """从 Redis 缓存读取策略快照，缓存未命中则 fallback 到 MySQL。"""
    from alarm_backends.core.cache.strategy import StrategyCacheManager

    strategy = StrategyCacheManager.get_strategy_by_id(strategy_id)
    if strategy:
        return strategy

    # fallback：直接查 MySQL Strategy 表
    from bkmonitor.models.strategy import StrategyModel

    obj = StrategyModel.objects.filter(id=strategy_id).first()
    if obj:
        return {"id": obj.id, "bk_biz_id": obj.bk_biz_id, "name": obj.name, "labels": [], "items": []}

    raise ValueError(f"strategy_id={strategy_id} 不存在（Redis 缓存与 MySQL 均未找到）")


def main(
    strategy_id: int,
    aggregate_dimensions: list = None,
    conditions: list = None,
    alert_levels: list = None,
    is_enabled: bool = True,
) -> None:
    """
    为指定策略注入 Issues 聚合配置（直接 ORM 写入，绕过 Service 层校验）。

    Args:
        strategy_id:          目标策略 ID（必填），bk_biz_id 由策略快照自动回填
        aggregate_dimensions: 聚合维度，默认 [] 表示使用策略公共维度
        conditions:           过滤条件，默认 [] 表示不过滤
        alert_levels:         生效告警级别，默认 [1, 2, 3]（1=致命, 2=预警, 3=提醒）
        is_enabled:           是否启用，默认 True
    """
    from bkmonitor.models.issue import StrategyIssueConfig
    from alarm_backends.core.cache.issue import StrategyIssueConfigCache

    if aggregate_dimensions is None:
        aggregate_dimensions = []
    if conditions is None:
        conditions = []
    if alert_levels is None:
        alert_levels = [1, 2, 3]

    strategy = _get_strategy(strategy_id)
    bk_biz_id = strategy.get("bk_biz_id", 0)
    strategy_name = strategy.get("name", "")
    print(f"[INFO] 策略: id={strategy_id}, name={strategy_name!r}, bk_biz_id={bk_biz_id}")

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

    # 显式刷新缓存（信号在 web 进程下会跳过）
    try:
        StrategyIssueConfigCache.upsert(config)
        print(f"[OK] Redis 缓存已刷新，strategy_id={strategy_id}")
    except Exception as e:
        print(f"[WARN] 缓存刷新失败（processor 会降级读 MySQL）: {e}")


def cleanup(strategy_id: int) -> None:
    """
    清理指定策略的 Issues 配置：软删除 MySQL 记录并清除 Redis 缓存。
    清理后该策略不再触发 Issue 聚合，直到重新调用 main() 注入。
    """
    from bkmonitor.models.issue import StrategyIssueConfig
    from alarm_backends.core.cache.issue import StrategyIssueConfigCache

    updated = StrategyIssueConfig.objects.filter(strategy_id=strategy_id).update(is_deleted=True, is_enabled=False)
    if updated:
        try:
            StrategyIssueConfigCache.invalidate(strategy_id)
        except Exception as e:
            print(f"[WARN] 缓存清除失败: {e}")
        print(f"[OK] strategy_id={strategy_id} 的配置已清理（软删除 + 缓存失效）")
    else:
        print(f"[WARN] 未找到 strategy_id={strategy_id} 的配置，无需清理")


def verify_config(strategy_id: int) -> None:
    """查看指定策略的 MySQL 配置及 Redis 缓存状态。"""
    from bkmonitor.models.issue import StrategyIssueConfig
    from alarm_backends.core.cache.issue import StrategyIssueConfigCache

    print(f"\n===== StrategyIssueConfig 验证（strategy_id={strategy_id}）=====")

    config = StrategyIssueConfig.objects.filter(strategy_id=strategy_id, is_deleted=False).first()
    if not config:
        print("[FAIL] MySQL 中未找到该配置（可能已清理或从未注入）")
    else:
        print("[MySQL]")
        print(f"  id                = {config.id}")
        print(f"  strategy_id       = {config.strategy_id}")
        print(f"  bk_biz_id         = {config.bk_biz_id}")
        print(f"  is_enabled        = {config.is_enabled}")
        print(f"  aggregate_dims    = {config.aggregate_dimensions}")
        print(f"  conditions        = {config.conditions}")
        print(f"  alert_levels      = {config.alert_levels}")

    try:
        cached = StrategyIssueConfigCache.get(strategy_id)
        if cached:
            print("\n[Redis 缓存] 命中")
            print(f"  is_enabled        = {cached.get('is_enabled')}")
            print(f"  aggregate_dims    = {cached.get('aggregate_dimensions')}")
            print(f"  conditions        = {cached.get('conditions')}")
            print(f"  alert_levels      = {cached.get('alert_levels')}")
        else:
            print("\n[Redis 缓存] 未命中")
    except Exception as e:
        print(f"\n[Redis 缓存] 读取失败: {e}")

    print("=" * 60)


def simulate_processor(alert_id: str, strategy_id: int) -> None:
    """
    模拟 IssueAggregationProcessor 完整流程（需 ES 和 Redis 可用）。
    用于端到端验证：配置读取 → 条件过滤 → Issue 查找/创建 → 告警关联。
    """
    from bkmonitor.documents.alert import AlertDocument
    from alarm_backends.service.fta_action.issue_processor import IssueAggregationProcessor

    print(f"\n===== 模拟 IssueAggregationProcessor（strategy_id={strategy_id}）=====")

    hits = AlertDocument.search(all_indices=True).filter("term", id=alert_id).params(size=1).execute().hits
    if not hits:
        print(f"[FAIL] AlertDocument id={alert_id} 在 ES 中不存在")
        return
    alert = AlertDocument(**hits[0].to_dict())
    print(f"[OK] 已加载告警: id={alert.id}, severity={alert.severity}")

    try:
        strategy = _get_strategy(strategy_id)
    except ValueError as e:
        print(f"[WARN] {e}，使用最小策略 dict 继续")
        strategy = {"id": strategy_id, "bk_biz_id": 0, "name": f"测试策略_{strategy_id}", "labels": [], "items": []}
    print(f"[INFO] 策略快照: name={strategy.get('name')!r}, bk_biz_id={strategy.get('bk_biz_id')}")

    processor = IssueAggregationProcessor(alert=alert, strategy=strategy)
    result = processor.process()
    print(f"[{'OK' if result else 'SKIP'}] process() 返回: {result}")
    if result:
        print(f"[OK] 告警已关联到 Issue，alert.issue_id={alert.issue_id}")
    print("=" * 60)
