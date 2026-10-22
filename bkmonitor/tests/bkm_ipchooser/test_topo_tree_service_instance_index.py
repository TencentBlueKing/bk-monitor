"""
TopoTool 服务实例数量统计：索引消费契约

TopoTool 不负责「索引未命中时如何取数」——该职责已下沉到 BkApi 实现方
（IpChooserApi 内部借 get_service_instance_by_biz 拉取并构建分组，该函数自带
1 小时 cron 缓存且内部顺带回写索引）。因此本层只消费索引结果：

- 索引有数据时按模块分组统计，不触发任何明细查询
- 索引为空 dict（业务确实无服务实例）时 count 为 0
- BkApi 返回 None 时 count 为 0；读取异常/未实现按原行为向上抛出，不静默降级
- 父节点 count 为子树实例 ID 并集，不是节点自身 len
- 统计主机数量时不得读取服务实例索引
"""

import pytest

from bkm_ipchooser import constants
from bkm_ipchooser.tools import topo_tool


def _build_topo_tree():
    """构造最小拓扑树：业务 -> 集群 -> 两个模块"""
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


MODULE_COUNTS = {
    # (bk_obj_id, bk_inst_id) -> 期望 count
    (constants.ObjectType.MODULE.value, 10): 3,
    (constants.ObjectType.MODULE.value, 20): 2,
    # 父节点 = 子树实例 ID 并集，模块 10 与 20 无重叠
    (constants.ObjectType.SET.value, 30): 5,
    (constants.ObjectType.BIZ.value, 2): 5,
}

ZERO_COUNTS = {
    (constants.ObjectType.MODULE.value, 10): 0,
    (constants.ObjectType.MODULE.value, 20): 0,
    (constants.ObjectType.SET.value, 30): 0,
    (constants.ObjectType.BIZ.value, 2): 0,
}


def _collect_counts(node, result):
    result[(node["bk_obj_id"], node["bk_inst_id"])] = node["count"]
    for child in node.get("child") or []:
        _collect_counts(child, result)
    return result


def _get_topo_tree_with_count(mocker, count_instance_type=constants.InstanceType.SERVICE_INSTANCE.value):
    mocker.patch.object(
        topo_tool.resource.ResourceQueryHelper,
        "get_topo_tree",
        return_value=_build_topo_tree(),
    )
    return topo_tool.TopoTool.get_topo_tree_with_count(
        bk_biz_id=2,
        count_instance_type=count_instance_type,
    )


def test_index_used_without_loading_service_instance_details(mocker):
    """索引有数据时按模块统计，且不触发任何明细查询"""
    mocker.patch.object(
        topo_tool.BkApi,
        "get_service_instance_module_index",
        return_value={10: [101, 102, 103], 20: [201, 202]},
    )
    list_detail = mocker.patch.object(topo_tool.BkApi, "list_service_instance_detail")

    topo_tree = _get_topo_tree_with_count(mocker)

    assert _collect_counts(topo_tree, {}) == MODULE_COUNTS
    list_detail.assert_not_called()


def test_index_int_keys_match_module_node(mocker):
    """
    索引键必须为 int 才能命中 node["bk_inst_id"]

    IpChooserApi 已把持久化的 str 键转为 int，此处断言 int 键路径下 count 不丢。
    """
    mocker.patch.object(
        topo_tool.BkApi,
        "get_service_instance_module_index",
        return_value={int("10"): [101, 102, 103], int("20"): [201, 202]},
    )

    counts = _collect_counts(_get_topo_tree_with_count(mocker), {})

    assert counts[(constants.ObjectType.MODULE.value, 10)] == 3
    assert counts[(constants.ObjectType.MODULE.value, 20)] == 2


def test_empty_index_yields_zero_counts(mocker):
    """索引为空 dict（业务确实无服务实例）时 count 为 0"""
    mocker.patch.object(topo_tool.BkApi, "get_service_instance_module_index", return_value={})
    list_detail = mocker.patch.object(topo_tool.BkApi, "list_service_instance_detail")

    counts = _collect_counts(_get_topo_tree_with_count(mocker), {})

    assert counts == ZERO_COUNTS
    list_detail.assert_not_called()


def test_index_unavailable_yields_zero_counts_without_full_fetch(mocker):
    """
    BkApi 返回 None 时 count 为 0，且 TopoTool 不再自行全量拉取

    明细拉取由 BkApi 实现方负责，本层重复拉取会绕开 get_service_instance_by_biz
    自带的一小时缓存与索引回写能力。
    """
    mocker.patch.object(topo_tool.BkApi, "get_service_instance_module_index", return_value=None)
    list_detail = mocker.patch.object(topo_tool.BkApi, "list_service_instance_detail")

    counts = _collect_counts(_get_topo_tree_with_count(mocker), {})

    assert counts == ZERO_COUNTS
    list_detail.assert_not_called()


def test_api_not_implemented_propagates(mocker):
    """自定义 BkApi 未提供索引能力时按原行为抛错，不静默降级为 0"""
    mocker.patch.object(
        topo_tool.BkApi,
        "get_service_instance_module_index",
        side_effect=NotImplementedError,
    )

    with pytest.raises(NotImplementedError):
        _get_topo_tree_with_count(mocker)


def test_index_read_error_propagates(mocker):
    """索引读取异常（如缓存后端故障）时向上抛出，不把故障显示成“无实例”"""
    mocker.patch.object(
        topo_tool.BkApi,
        "get_service_instance_module_index",
        side_effect=RuntimeError("cache backend down"),
    )

    with pytest.raises(RuntimeError):
        _get_topo_tree_with_count(mocker)


def test_parent_count_is_union_of_subtree(mocker):
    """父节点 count 是子树实例 ID 并集：同一实例挂多个模块时不得重复计数"""
    mocker.patch.object(
        topo_tool.BkApi,
        "get_service_instance_module_index",
        # 101 同时属于模块 10 与 20，父节点应为 2 而非 3
        return_value={10: [101, 102], 20: [101]},
    )

    counts = _collect_counts(_get_topo_tree_with_count(mocker), {})

    assert counts[(constants.ObjectType.MODULE.value, 10)] == 2
    assert counts[(constants.ObjectType.MODULE.value, 20)] == 1
    assert counts[(constants.ObjectType.SET.value, 30)] == 2
    assert counts[(constants.ObjectType.BIZ.value, 2)] == 2


def test_index_path_not_used_for_host_count(mocker):
    """统计主机数量时不应读取服务实例索引"""
    mocker.patch.object(
        topo_tool.resource.ResourceQueryHelper,
        "fetch_host_topo_relations",
        return_value=[
            {"bk_host_id": 1, "bk_module_id": 10},
            {"bk_host_id": 2, "bk_module_id": 20},
        ],
    )
    mocker.patch.object(topo_tool.cache, "get", return_value=None)
    mocker.patch.object(topo_tool.cache, "set")
    get_index = mocker.patch.object(topo_tool.BkApi, "get_service_instance_module_index")

    topo_tree = _get_topo_tree_with_count(mocker, count_instance_type=constants.InstanceType.HOST.value)

    counts = _collect_counts(topo_tree, {})
    assert counts[(constants.ObjectType.MODULE.value, 10)] == 1
    assert counts[(constants.ObjectType.MODULE.value, 20)] == 1
    get_index.assert_not_called()
