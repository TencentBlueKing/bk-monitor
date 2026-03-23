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


def _update_strategy_cache_issue_config(strategy_id: int) -> bool:
    """将 MySQL 最新 issue_config 精准写回策略 Redis 缓存。

    不调用全量 StrategyCacheManager.refresh()（该方法无参数，会触发全量刷新），
    而是直接更新指定策略 key 中的 issue_config 字段。
    Returns True 表示成功更新，False 表示缓存未命中（等待后台任务重建）。
    """
    import json

    from alarm_backends.core.cache.strategy import StrategyCacheManager
    from bkmonitor.models.issue import StrategyIssueConfig

    cache_key = StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=strategy_id)
    cached_str = StrategyCacheManager.cache.get(cache_key)
    if not cached_str:
        return False

    strategy_dict = json.loads(cached_str)
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
    return True


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

    # 精准更新策略缓存中的 issue_config 字段
    try:
        updated = _update_strategy_cache_issue_config(strategy_id)
        if updated:
            print(f"[OK] 策略缓存已更新（含 issue_config），strategy_id={strategy_id}")
        else:
            print(f"[WARN] 策略缓存未命中，等待后台 smart_refresh 任务重建，strategy_id={strategy_id}")
    except Exception as e:
        print(f"[WARN] 策略缓存更新失败: {e}")


def cleanup(strategy_id: int) -> None:
    """
    清理指定策略的 Issues 配置：软删除 MySQL 记录并更新 Redis 缓存。
    清理后该策略不再触发 Issue 聚合，直到重新调用 main() 注入。
    """
    from bkmonitor.models.issue import StrategyIssueConfig

    updated = StrategyIssueConfig.objects.filter(strategy_id=strategy_id).update(is_deleted=True, is_enabled=False)
    if updated:
        try:
            # .update() 不触发 Django 信号，需手动更新策略缓存中的 issue_config 字段
            cache_updated = _update_strategy_cache_issue_config(strategy_id)
            if cache_updated:
                print(f"[OK] strategy_id={strategy_id} 的配置已清理（软删除 + 策略缓存已更新）")
            else:
                print(f"[OK] strategy_id={strategy_id} 的配置已清理（软删除；缓存未命中，等待后台重建）")
        except Exception as e:
            print(f"[WARN] 策略缓存更新失败: {e}")
            print(f"[OK] strategy_id={strategy_id} 的 MySQL 配置已清理（软删除）")
    else:
        print(f"[WARN] 未找到 strategy_id={strategy_id} 的配置，无需清理")


def verify_config(strategy_id: int) -> None:
    """查看指定策略的 MySQL 配置及策略缓存中的 issue_config 状态。"""
    from alarm_backends.core.cache.strategy import StrategyCacheManager
    from bkmonitor.models.issue import StrategyIssueConfig

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
        strategy_snapshot = StrategyCacheManager.get_strategy_by_id(strategy_id)
        if strategy_snapshot:
            cached = strategy_snapshot.get("issue_config")
            if cached:
                print("\n[策略缓存 issue_config] 命中")
                print(f"  is_enabled        = {cached.get('is_enabled')}")
                print(f"  aggregate_dims    = {cached.get('aggregate_dimensions')}")
                print(f"  conditions        = {cached.get('conditions')}")
                print(f"  alert_levels      = {cached.get('alert_levels')}")
            else:
                print("\n[策略缓存 issue_config] 未配置（issue_config=null）")
        else:
            print("\n[策略缓存] 未命中（策略可能已失效或缓存未建）")
    except Exception as e:
        print(f"\n[策略缓存] 读取失败: {e}")

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
