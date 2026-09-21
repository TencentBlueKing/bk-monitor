from copy import deepcopy

from api.cmdb import default as cmdb
from api.cmdb import define


def raw_tree(module_count=100):
    return {
        "bk_obj_id": "biz",
        "bk_inst_id": 2,
        "bk_inst_name": "Business",
        "child": [
            {
                "bk_obj_id": "set",
                "bk_inst_id": 1,
                "bk_inst_name": "Set",
                "child": [
                    {"bk_obj_id": "module", "bk_inst_id": str(i), "bk_inst_name": str(i), "child": []}
                    for i in range(module_count)
                ],
            },
            {"bk_obj_id": "set", "bk_inst_id": 3, "bk_inst_name": None, "child": []},
        ],
    }


def test_target_paths_equal_complete_tree_without_constructing_unrelated_nodes(mocker):
    tree = raw_tree()
    # 重复叶子的最后路径及自定义层级与完整树保持一致。
    tree["child"].append(
        {
            "bk_obj_id": "custom",
            "bk_inst_id": 4,
            "bk_inst_name": "Custom",
            "child": [{"bk_obj_id": "module", "bk_inst_id": 5, "bk_inst_name": None, "child": []}],
        }
    )
    original = deepcopy(tree)
    all_links = define.TopoTree(deepcopy(tree)).convert_to_topo_link()
    build_node = mocker.patch.object(define, "TopoNode", wraps=define.TopoNode)
    links = define.TopoTree.module_links_from_raw(tree, [5, 5, "20", "030", 999])
    assert {key: [node.to_dict() for node in value] for key, value in links.items()} == {
        key: [node.to_dict() for node in value] for key, value in all_links.items() if key in {"module|5", "module|20"}
    }
    assert build_node.call_count == 9
    assert tree == original
    assert define.TopoTree.module_links_from_raw(tree, []) == {}
    assert build_node.call_count == 9


def test_topology_resource_raw_mode_skips_tree_construction(mocker):
    tree = raw_tree()
    original = deepcopy(tree)
    mocker.patch.object(cmdb, "_get_topo_tree", return_value=tree)
    build_tree = mocker.patch.object(cmdb, "TopoTree", wraps=define.TopoTree)
    assert cmdb.GetTopoTreeResource().perform_request({"bk_biz_id": 2, "raw": True}) is tree
    build_tree.assert_not_called()
    assert tree == original
    assert isinstance(cmdb.GetTopoTreeResource().perform_request({"bk_biz_id": 2}), define.TopoTree)
    assert build_tree.call_count == 1
