"""
完整调用链回归：冷启动打开选择器只应拉取一轮全量明细

背景：树统计改为读取模块索引后，树与列表不再共享同一份明细缓存。若索引回退
路径拿到的明细不回填，同一次打开会把同一份全量明细拉两轮（1 万实例约
51 -> 73 次 CMDB 请求，+43%）。

本文件不改动内部实现细节，只沿真实调用链断言取数次数：
1. 冷启动 + 索引缺失：先树查询、再根节点实例列表查询，全量明细只拉一轮
2. 索引命中：树统计不加载任何明细
3. 回填失败：树统计不因缓存写入失败而失败（缓存只是复用机会）
4. 空明细：同样回填，避免列表侧把「空业务」当成「未拉取」反复重跑分页请求
5. 缓存键契约：树回填写入的键与列表侧读取的键必须一致
6. 口径一致：树只读索引，一致性由列表取数后刷新索引保证

树统计在明细缓存命中时也不读明细（1 万实例约 30MB，读一次就退化成整份反序列化），
因此「树与列表数字一致」不靠读同一份明细，而靠列表侧取数后立即刷新索引。

测试环境的默认缓存是 DatabaseCache，用例中统一替换为内存假缓存，
这样跨两次调用的复用行为才是可验证的。
"""

import pytest

from api.cmdb.default import ServiceInstanceModuleIndex
from api.cmdb.ipchooser import IpChooserApi
from bkm_ipchooser import constants
from bkm_ipchooser.handlers.topo_handler import TopoHandler
from bkm_ipchooser.tools import service_instance_cache, topo_tool

SERVICE_INSTANCES = [
    {
        "id": 101,
        "bk_module_id": 10,
        "bk_host_id": 1,
        "name": "service-101",
        "labels": {},
        "service_template_id": 1,
        "process_instances": [{"id": 1}],
    },
    {
        "id": 201,
        "bk_module_id": 20,
        "bk_host_id": 2,
        "name": "service-201",
        "labels": {},
        "service_template_id": 2,
        "process_instances": [{"id": 2}],
    },
]


class FakeCache:
    """内存假缓存，替代测试环境默认的 DatabaseCache"""

    def __init__(self):
        self.store = {}
        self.timeouts = {}

    def get(self, key, default=None):
        return self.store.get(key, default)

    def set(self, key, value, timeout=None):
        self.store[key] = value
        self.timeouts[key] = timeout
        return True


@pytest.fixture
def fake_detail_cache(mocker):
    """把明细缓存后端换成内存字典，跨调用可观察写入与命中"""
    fake = FakeCache()
    mocker.patch.object(service_instance_cache, "cache", fake)
    return fake


def _build_topo_tree():
    return {
        "bk_obj_id": constants.ObjectType.BIZ.value,
        "bk_inst_id": 2,
        "bk_inst_name": "biz-2",
        "child": [
            {
                "bk_obj_id": constants.ObjectType.SET.value,
                "bk_inst_id": 30,
                "bk_inst_name": "set-30",
                "child": [
                    {
                        "bk_obj_id": constants.ObjectType.MODULE.value,
                        "bk_inst_id": 10,
                        "bk_inst_name": "module-10",
                        "child": [],
                    },
                    {
                        "bk_obj_id": constants.ObjectType.MODULE.value,
                        "bk_inst_id": 20,
                        "bk_inst_name": "module-20",
                        "child": [],
                    },
                ],
            }
        ],
    }


def _collect_counts(node, result):
    result[(node["bk_obj_id"], node["bk_inst_id"])] = node["count"]
    for child in node.get("child") or []:
        _collect_counts(child, result)
    return result


def _run_tree_query(mocker):
    """执行树统计查询（服务实例口径）"""
    mocker.patch.object(topo_tool.resource.ResourceQueryHelper, "get_topo_tree", return_value=_build_topo_tree())
    return topo_tool.TopoTool.get_topo_tree_with_count(
        bk_biz_id=2,
        count_instance_type=constants.InstanceType.SERVICE_INSTANCE.value,
    )


def _run_list_query():
    """执行根节点实例列表查询（打开选择器后自动选中根节点的请求）"""
    return TopoHandler.query_service_instance(
        scope_list=[{"scope_type": "biz", "scope_id": 2, "bk_biz_id": 2}],
        readable_node_list=[],
        start=0,
        page_size=10,
    )


def test_cold_start_full_open_fetches_details_only_once(mocker, fake_detail_cache):
    """
    冷启动完整打开：树查询 + 根节点列表查询，全量明细只拉一轮

    这是本次修复要锁住的核心回归。树查询在索引缺失时已经拿到全量明细并回填，
    列表查询应直接复用，不再对 CMDB 发起第二轮全量拉取。
    """
    mocker.patch.object(ServiceInstanceModuleIndex, "get", return_value=None)
    mocker.patch.object(ServiceInstanceModuleIndex, "set")
    get_by_biz = mocker.patch(
        "api.cmdb.ipchooser.api.cmdb.get_service_instance_by_biz",
        return_value=SERVICE_INSTANCES,
    )
    # 列表侧若真去拉明细，这里会抛错；断言它一次都没被调用
    list_detail = mocker.patch(
        "bkm_ipchooser.handlers.topo_handler.BkApi.list_service_instance_detail",
        side_effect=AssertionError("list must reuse backfilled details"),
    )

    topo_tree = _run_tree_query(mocker)
    result = _run_list_query()

    # 树统计正确：模块 10 / 20 各 1 个实例，父节点为并集 2
    counts = _collect_counts(topo_tree, {})
    assert counts[(constants.ObjectType.MODULE.value, 10)] == 1
    assert counts[(constants.ObjectType.MODULE.value, 20)] == 1
    assert counts[(constants.ObjectType.BIZ.value, 2)] == 2

    # 全量明细只拉一轮
    get_by_biz.assert_called_once_with(2)
    list_detail.assert_not_called()

    # 列表侧数据可用
    assert result["total"] == 2
    assert {item["id"] for item in result["data"]} == {101, 201}


def test_index_hit_does_not_load_details(mocker, fake_detail_cache):
    """索引命中时树统计只读 ID，不拉明细，也不触发明细缓存写入"""
    mocker.patch.object(ServiceInstanceModuleIndex, "get", return_value={"10": [101], "20": [201]})
    get_by_biz = mocker.patch("api.cmdb.ipchooser.api.cmdb.get_service_instance_by_biz")
    list_detail = mocker.patch.object(IpChooserApi, "list_service_instance_detail")

    counts = _collect_counts(_run_tree_query(mocker), {})

    assert counts[(constants.ObjectType.MODULE.value, 10)] == 1
    assert counts[(constants.ObjectType.MODULE.value, 20)] == 1
    get_by_biz.assert_not_called()
    list_detail.assert_not_called()
    # 轻量路径不应产生明细缓存写入
    assert fake_detail_cache.store == {}


def test_backfill_failure_does_not_break_tree_query(mocker, fake_detail_cache):
    """回填缓存失败不应让树统计整体失败：缓存只是复用机会，不是前置依赖"""
    mocker.patch.object(ServiceInstanceModuleIndex, "get", return_value=None)
    mocker.patch.object(ServiceInstanceModuleIndex, "set")
    mocker.patch(
        "api.cmdb.ipchooser.api.cmdb.get_service_instance_by_biz",
        return_value=SERVICE_INSTANCES,
    )
    mocker.patch.object(
        service_instance_cache,
        "set_details",
        side_effect=RuntimeError("cache backend down"),
    )

    counts = _collect_counts(_run_tree_query(mocker), {})

    assert counts[(constants.ObjectType.MODULE.value, 10)] == 1
    assert counts[(constants.ObjectType.MODULE.value, 20)] == 1


def test_empty_details_are_backfilled(mocker, fake_detail_cache):
    """
    空明细也要回填：空列表代表「业务确实没有服务实例」

    读侧以 is None 判断未命中，写入空列表才能让列表侧命中并停止反复全量拉取；
    若这里不回填，空业务每次打开都会重跑一轮全量分页请求。
    """
    mocker.patch.object(ServiceInstanceModuleIndex, "get", return_value=None)
    mocker.patch.object(ServiceInstanceModuleIndex, "set")
    mocker.patch("api.cmdb.ipchooser.api.cmdb.get_service_instance_by_biz", return_value=[])

    assert IpChooserApi.get_service_instance_module_index(2) == {}
    # 空列表已写入，且读侧能区分「空」与「未缓存」
    assert fake_detail_cache.store == {"all_service_instance_detail:2": []}
    assert service_instance_cache.get_details(2) == []
    assert service_instance_cache.get_details(2) is not None


def test_none_details_are_not_backfilled(mocker, fake_detail_cache):
    """
    None 不回填：它表示调用方没拿到有效结果

    写入 None 会让读侧把取数失败误判成业务无实例。
    """
    service_instance_cache.set_details(2, None)

    assert fake_detail_cache.store == {}


def test_detail_cache_key_shared_between_tree_and_list(mocker, fake_detail_cache):
    """
    树回填写入的键必须与列表侧读取的键一致

    缓存键只有一份定义（service_instance_cache）。此处从两侧分别观察：
    回填写入的键，与列表侧未命中判断所用的键是同一个。
    """
    mocker.patch.object(ServiceInstanceModuleIndex, "get", return_value=None)
    mocker.patch.object(ServiceInstanceModuleIndex, "set")
    mocker.patch(
        "api.cmdb.ipchooser.api.cmdb.get_service_instance_by_biz",
        return_value=SERVICE_INSTANCES,
    )

    IpChooserApi.get_service_instance_module_index(2)

    assert service_instance_cache.detail_cache_key(2) == "all_service_instance_detail:2"
    assert fake_detail_cache.store == {"all_service_instance_detail:2": SERVICE_INSTANCES}

    # 列表侧直接命中回填的缓存
    assert service_instance_cache.get_details(2) == SERVICE_INSTANCES


def test_backfill_does_not_overwrite_existing_fresh_details(mocker, fake_detail_cache):
    """
    已有缓存时不回填，避免用更旧的快照覆盖列表刚拉到的数据

    回填来源是 get_service_instance_by_biz，虽由 cron 分环刷新，但单业务仍有几分钟
    滞后；列表侧缓存是当前请求刚拉到的实时结果。若盲目回填，反而把实时数据降级成
    滞后快照。因此回填只补空缺、不覆盖已有值。
    """
    fresh_instances = [{"id": 999, "bk_module_id": 10, "name": "fresh"}]
    fake_detail_cache.store["all_service_instance_detail:2"] = fresh_instances

    mocker.patch.object(ServiceInstanceModuleIndex, "get", return_value=None)
    mocker.patch.object(ServiceInstanceModuleIndex, "set")
    mocker.patch(
        "api.cmdb.ipchooser.api.cmdb.get_service_instance_by_biz",
        return_value=SERVICE_INSTANCES,
    )

    IpChooserApi.get_service_instance_module_index(2)

    # 新鲜数据未被回填来源（cron 分环刷新，单业务约 10 分钟滞后）覆盖
    assert fake_detail_cache.store["all_service_instance_detail:2"] == fresh_instances


def test_backfill_uses_short_timeout(mocker, fake_detail_cache):
    """
    回填必须使用远短于列表侧自拉的时效

    回填来源是 get_service_instance_by_biz：TTL 1 小时，但由每分钟一次、按业务分环的
    cron 刷新，单业务通常只有几分钟旧。60 秒时效的意义不是「压缩陈旧窗口」（cron 正常
    时它本来就不太旧），而是让这份副本只服务本次打开的紧邻请求；超过 60 秒就重新取数，
    不去吃一份「看起来还新鲜」的缓存。
    """
    mocker.patch.object(ServiceInstanceModuleIndex, "get", return_value=None)
    mocker.patch.object(ServiceInstanceModuleIndex, "set")
    mocker.patch(
        "api.cmdb.ipchooser.api.cmdb.get_service_instance_by_biz",
        return_value=SERVICE_INSTANCES,
    )

    IpChooserApi.get_service_instance_module_index(2)

    key = service_instance_cache.detail_cache_key(2)
    assert fake_detail_cache.timeouts[key] == service_instance_cache.BACKFILL_CACHE_TIMEOUT
    assert service_instance_cache.BACKFILL_CACHE_TIMEOUT < service_instance_cache.DETAIL_CACHE_TIMEOUT


def test_list_side_write_uses_detail_timeout(mocker, fake_detail_cache):
    """列表侧自行拉取的明细仍按 5 分钟时效缓存，不因回填的短时效一起变短"""
    mocker.patch(
        "bkm_ipchooser.handlers.topo_handler.BkApi.list_service_instance_detail",
        return_value={"info": SERVICE_INSTANCES, "count": len(SERVICE_INSTANCES)},
    )

    _run_list_query()

    key = service_instance_cache.detail_cache_key(2)
    assert fake_detail_cache.timeouts[key] == service_instance_cache.DETAIL_CACHE_TIMEOUT


def test_set_details_writes_empty_list_but_skips_none(mocker, fake_detail_cache):
    """
    空列表写入、None 不写入：读侧靠 is None 区分「空业务」与「未缓存」

    空列表是「业务确实没有服务实例」的合法结果，必须写入，否则空业务每次打开都会
    重跑一轮全量分页请求；None 表示取数失败，写入会被误判成业务无实例。
    """
    service_instance_cache.set_details(2, [])
    assert fake_detail_cache.store == {"all_service_instance_detail:2": []}

    fake_detail_cache.store.clear()
    service_instance_cache.set_details(2, None)
    assert fake_detail_cache.store == {}


def test_tree_reads_index_only_even_when_detail_cache_is_warm(mocker, fake_detail_cache):
    """
    明细缓存命中时，树统计仍然只读索引

    明细缓存是给列表侧复用的（1 万实例约 30MB），树统计若读它，每次打开选择器都要
    整份反序列化，抵掉「拓扑树改读索引」的全部收益。因此这里必须读索引。
    """
    cached_details = [
        {"id": 101, "bk_module_id": 10, "name": "cached-101"},
        {"id": 102, "bk_module_id": 10, "name": "cached-102"},
        {"id": 201, "bk_module_id": 20, "name": "cached-201"},
    ]
    fake_detail_cache.store[service_instance_cache.detail_cache_key(2)] = cached_details
    mocker.patch.object(
        topo_tool.BkApi,
        "get_service_instance_module_index",
        return_value={10: [101], 20: [201]},
    )

    counts = _collect_counts(_run_tree_query(mocker), {})

    # 以索引为准：模块 10 记为 1 个，而不是明细缓存里的 2 个
    assert counts[(constants.ObjectType.MODULE.value, 10)] == 1
    assert counts[(constants.ObjectType.MODULE.value, 20)] == 1
    assert counts[(constants.ObjectType.BIZ.value, 2)] == 2


def test_list_refresh_makes_tree_see_same_snapshot(mocker, fake_detail_cache):
    """
    口径一致性的真实保证：列表取数后刷新索引，树随即读到同一份快照

    这是「树上显示 N 个实例，点进去只有 M 条」的修复点。列表自拉明细后同步写索引，
    下一次树请求读到的就是刚拉到的快照，而不是 cron 上次刷新的旧数据。
    """
    refreshed: dict = {}

    def _fake_set(bk_biz_id, service_instances):
        refreshed["index"] = ServiceInstanceModuleIndex.build(service_instances)

    mocker.patch.object(ServiceInstanceModuleIndex, "set", side_effect=_fake_set)
    mocker.patch(
        "bkm_ipchooser.handlers.topo_handler.BkApi.list_service_instance_detail",
        return_value={"info": SERVICE_INSTANCES, "count": len(SERVICE_INSTANCES)},
    )
    mocker.patch.object(
        ServiceInstanceModuleIndex,
        "get",
        side_effect=lambda bk_biz_id: refreshed.get("index"),
    )

    # 列表先取数并刷新索引
    result = _run_list_query()
    assert result["total"] == 2

    # 树读到的索引就是列表刚拉到的快照，两端口径一致
    counts = _collect_counts(_run_tree_query(mocker), {})

    assert refreshed["index"] == {"10": [101], "20": [201]}
    assert counts[(constants.ObjectType.MODULE.value, 10)] == 1
    assert counts[(constants.ObjectType.MODULE.value, 20)] == 1
    assert counts[(constants.ObjectType.BIZ.value, 2)] == 2


def test_tree_falls_back_to_index_without_cached_details(mocker, fake_detail_cache):
    """明细缓存未命中时读索引轻量路径，且不产生任何明细缓存写入"""
    mocker.patch.object(
        topo_tool.BkApi,
        "get_service_instance_module_index",
        return_value={10: [101, 102], 20: [201]},
    )

    counts = _collect_counts(_run_tree_query(mocker), {})

    assert counts[(constants.ObjectType.MODULE.value, 10)] == 2
    assert counts[(constants.ObjectType.MODULE.value, 20)] == 1
    assert fake_detail_cache.store == {}


def test_empty_biz_list_query_reuses_cached_empty_result(mocker, fake_detail_cache):
    """
    空业务：列表侧命中缓存的空列表，不再重跑一轮全量分页请求

    这是「缓存能否区分空业务与未拉取」的回归。若读侧用 falsy 判断未命中，空业务每次
    打开都会对 CMDB 发起一轮必然返回空的全量分页请求，且结果永远写不进缓存。
    """
    service_instance_cache.set_details(2, [])
    list_detail = mocker.patch(
        "bkm_ipchooser.handlers.topo_handler.BkApi.list_service_instance_detail",
        side_effect=AssertionError("empty biz must not refetch details"),
    )

    result = _run_list_query()

    assert result["total"] == 0
    assert result["data"] == []
    list_detail.assert_not_called()


def test_empty_biz_tree_counts_zero_without_falling_back_to_details(mocker, fake_detail_cache):
    """空业务：树统计按索引计数为 0，且不读取明细缓存（空业务也无明细可读）"""
    service_instance_cache.set_details(2, [])
    get_details = mocker.patch.object(
        service_instance_cache,
        "get_details",
        side_effect=AssertionError("tree count must not read detail cache"),
    )
    mocker.patch.object(topo_tool.BkApi, "get_service_instance_module_index", return_value={})

    counts = _collect_counts(_run_tree_query(mocker), {})

    assert counts[(constants.ObjectType.MODULE.value, 10)] == 0
    assert counts[(constants.ObjectType.MODULE.value, 20)] == 0
    assert counts[(constants.ObjectType.BIZ.value, 2)] == 0
    get_details.assert_not_called()


def test_list_fetch_refreshes_module_index(mocker, fake_detail_cache):
    """
    列表侧自拉明细后必须刷新模块索引

    树统计在明细缓存未命中时读的就是这份索引。若列表只写明细不写索引，索引会停在
    cron 最后一次刷新的状态（cache_cmdb_resource 每分钟跑、按业务分环，单业务约
    10 分钟一轮）；明细缓存一过期，树就回落到旧索引计数，
    与列表刚展示的条数对不上。刷新索引不产生任何额外的 CMDB 请求。
    """
    mocker.patch(
        "bkm_ipchooser.handlers.topo_handler.BkApi.list_service_instance_detail",
        return_value={"info": SERVICE_INSTANCES, "count": len(SERVICE_INSTANCES)},
    )
    refresh = mocker.patch.object(IpChooserApi, "refresh_service_instance_module_index")

    _run_list_query()

    refresh.assert_called_once_with(2, SERVICE_INSTANCES)


def test_index_refresh_failure_does_not_break_list_query(mocker, fake_detail_cache):
    """索引刷新失败不能让列表请求失败：数据已拉到，索引最迟由 cron 兜底刷新"""
    mocker.patch(
        "bkm_ipchooser.handlers.topo_handler.BkApi.list_service_instance_detail",
        return_value={"info": SERVICE_INSTANCES, "count": len(SERVICE_INSTANCES)},
    )
    mocker.patch.object(
        IpChooserApi,
        "refresh_service_instance_module_index",
        side_effect=RuntimeError("index write failed"),
    )

    result = _run_list_query()

    assert result["total"] == 2


def test_backfill_isolates_cached_copy_from_source_object(mocker, fake_detail_cache):
    """
    回填写入的是独立副本，不与来源对象共享引用

    来源是 get_service_instance_by_biz，其一级内存缓存在同一进程内可能把同一份
    对象返回给多个调用方。若把引用直接写进另一个缓存键，任一侧就地修改都会静默
    污染另一侧。
    """
    source = [dict(instance) for instance in SERVICE_INSTANCES]
    mocker.patch.object(ServiceInstanceModuleIndex, "get", return_value=None)
    mocker.patch.object(ServiceInstanceModuleIndex, "set")
    mocker.patch("api.cmdb.ipchooser.api.cmdb.get_service_instance_by_biz", return_value=source)

    IpChooserApi.get_service_instance_module_index(2)

    cached = fake_detail_cache.store[service_instance_cache.detail_cache_key(2)]
    assert cached == source
    assert cached is not source
    assert all(cached_item is not source_item for cached_item, source_item in zip(cached, source))

    # 改动来源对象不影响已缓存内容
    source.append({"id": 999, "bk_module_id": 30, "name": "appended"})
    source[0]["name"] = "mutated"

    assert len(cached) == len(SERVICE_INSTANCES)
    assert cached[0]["name"] == "service-101"
