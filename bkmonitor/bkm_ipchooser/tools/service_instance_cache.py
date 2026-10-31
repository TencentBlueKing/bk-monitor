"""
业务全量服务实例明细缓存（树统计与实例列表共用）

历史行为：TopoTool 统计服务实例数量时把业务全量明细拉下来，顺手写入该缓存，
紧随其后的根节点实例列表请求直接复用，一次打开只需拉一轮。

改为读取模块索引后，树统计不再持有明细，若无人回填，同一次打开会把同一份全量
明细拉两轮（1 万实例约 51 -> 73 次 CMDB 请求）。因此把缓存键与读写集中到这里：

- 列表侧（TopoHandler）读，未命中时自行拉取并回写
- 索引回退侧（IpChooserApi）在已经拿到全量明细时顺带回填

缓存键只有一份定义，避免两侧各写一份字面量后再次脱钩。
"""

import logging

from django.core.cache import cache

logger = logging.getLogger("bkm_ipchooser")

# 列表侧自行拉取的明细缓存时效：与历史行为保持一致
DETAIL_CACHE_TIMEOUT = 5 * 60

# 回填缓存只在「同一次打开」的两次请求之间复用，时效刻意远短于 DETAIL_CACHE_TIMEOUT。
# 回填来源是 get_service_instance_by_biz，其新鲜度由两层决定：TTL 是 1 小时
# （CacheType.CC_CACHE_ALWAYS），而 alarm_backends 的 cache_cmdb_resource 每分钟
# 跑一次、按业务分环（RING_NODES，默认 10），单个业务通常陈旧 ≤RING_NODES 分钟，
# 只有 cron 停摆时才会退化到 TTL 上限。也就是说回填拿到的是几分钟前的快照。
# 用 60 秒而不用列表侧的 5 分钟：副本只服务本次打开的紧邻请求，
# 之后让「下一次独立打开」重新取数，而不是继续吃这份旧快照。
BACKFILL_CACHE_TIMEOUT = 60


def detail_cache_key(bk_biz_id: int) -> str:
    """业务全量服务实例明细的缓存键"""
    return f"all_service_instance_detail:{bk_biz_id}"


def get_details(bk_biz_id: int) -> list[dict] | None:
    """
    读取业务全量服务实例明细

    返回 None 表示未缓存（需要拉取），返回空列表表示已缓存且业务确实没有服务实例。
    调用方必须用 is None 判断未命中：用 falsy 判断会把「空业务」当成「未拉取」，
    导致空业务每次打开都重跑一轮全量分页请求。
    """
    return cache.get(detail_cache_key(bk_biz_id))


def set_details(bk_biz_id: int, service_instances: list[dict] | None, timeout: int = DETAIL_CACHE_TIMEOUT) -> None:
    """
    写入业务全量服务实例明细

    空列表必须写入：业务确实没有任何服务实例时，缓存空结果是唯一能避免「每次打开
    都重跑一轮全量分页请求」的方式，否则列表侧永远不命中。

    只有 None 不写入：None 表示调用方没有拿到有效结果，写入会让读侧把「取数失败」
    误判成「业务确实无实例」。
    """
    if service_instances is None:
        return

    cache.set(detail_cache_key(bk_biz_id), service_instances, timeout)


def backfill_details(bk_biz_id: int, service_instances: list[dict]) -> None:
    """
    用调用方已取得的全量明细回填列表侧缓存，避免同一次打开再全量拉取一遍

    这里只做「已有数据的复用」，不发起任何请求。缓存只是复用机会而非前置依赖，
    写入失败不能让树统计整体失败，故吞掉异常只记日志。

    两条回填前置条件：
    - 空结果也回填：空列表代表「业务确实没有服务实例」，写入它才能让列表侧命中并
      停止反复全量拉取；只有 None（调用方没拿到有效结果）不回填，由 set_details 守卫
    - 已有缓存不回填：列表侧刚拉过的数据必然比索引回退路径的来源更新鲜，
      回填会把新鲜数据覆盖成陈旧数据，故只补空缺不覆盖已有值
    """
    try:
        if get_details(bk_biz_id) is not None:
            return
        # 写入前先拷贝，属防御性冗余：内置缓存后端（DatabaseCache / LocMemCache 走
        # pickle，Redis 走 pickle 或 JSON）在 set 时都会序列化，实测 LocMemCache 回读
        # 也是新对象，正常配置下两个键不会共享结构。保留拷贝是为了不把「后端一定
        # 会序列化」当成正确性前提：自定义 CACHES 后端若直接保存引用，任一侧就地
        # 修改都会静默污染另一侧，且现象随请求顺序变化、极难排查。
        # 代价是一次 O(n) 的顶层 dict 构造，远低于排查成本。
        # 只做「列表 + 顶层字典」的浅拷贝：结构增删（append/pop/字段赋值）已被隔离，
        # 嵌套值（labels / process_instances）仍共享，读侧必须按只读使用、不得就地修改。
        # 该约束由 test_backfill_isolates_cached_copy_from_source_object 用「不序列化的假缓存」守住。
        set_details(bk_biz_id, [dict(instance) for instance in service_instances], timeout=BACKFILL_CACHE_TIMEOUT)
    except Exception:
        logger.exception("[ipchooser] 回填服务实例明细缓存失败, bk_biz_id: %s", bk_biz_id)
