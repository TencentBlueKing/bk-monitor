"""
IpChooserApi.get_service_instance_module_index 契约测试

该方法是 bkm_ipchooser 与 api.cmdb 的解耦入口：
- 索引存在时把 str 模块 ID 键统一转换为 int（否则上层按 int 的 bk_inst_id 查不到）
- 索引未命中时借 get_service_instance_by_biz 拉明细并构建分组
  （该函数自带 1 小时缓存且顺带写索引，故回退通常不是冷请求）
- 本方法不自行写索引，索引回写由 get_service_instance_by_biz 内部完成
- 空索引返回 {}（业务确实无服务实例），不得误判为未命中而重复拉取
"""

from api.cmdb.default import ServiceInstanceModuleIndex
from api.cmdb.ipchooser import IpChooserApi


def test_index_hit_converts_str_keys_to_int(mocker):
    mocker.patch.object(
        ServiceInstanceModuleIndex,
        "get",
        return_value={"10": [101, 102], "20": [201]},
    )
    set_index = mocker.patch.object(ServiceInstanceModuleIndex, "set")

    result = IpChooserApi.get_service_instance_module_index(2)

    assert result == {10: [101, 102], 20: [201]}
    # 键类型必须是 int，上层以 node["bk_inst_id"]（int）直接查找
    assert all(isinstance(module_id, int) for module_id in result)
    set_index.assert_not_called()


def test_index_missing_builds_from_service_instance_by_biz(mocker):
    """索引未命中时不得返回 None，而应借 get_service_instance_by_biz 构建分组"""
    mocker.patch.object(ServiceInstanceModuleIndex, "get", return_value=None)
    get_by_biz = mocker.patch(
        "api.cmdb.ipchooser.api.cmdb.get_service_instance_by_biz",
        return_value=[
            {"id": 101, "bk_module_id": 10},
            {"id": 102, "bk_module_id": 10},
            {"id": 201, "bk_module_id": 20},
        ],
    )
    set_index = mocker.patch.object(ServiceInstanceModuleIndex, "set")

    result = IpChooserApi.get_service_instance_module_index(2)

    get_by_biz.assert_called_once_with(2)
    # build() 产出 str 键，经统一转换后为 int
    assert result == {10: [101, 102], 20: [201]}
    # 索引回写由 get_service_instance_by_biz 内部完成，本方法不得自行写入
    set_index.assert_not_called()


def test_empty_index_returns_empty_dict_without_fetching(mocker):
    """空索引（业务无服务实例）不能被误判为未就绪，否则会白白触发一次全量拉取"""
    mocker.patch.object(ServiceInstanceModuleIndex, "get", return_value={})
    get_by_biz = mocker.patch("api.cmdb.ipchooser.api.cmdb.get_service_instance_by_biz")

    assert IpChooserApi.get_service_instance_module_index(2) == {}
    get_by_biz.assert_not_called()


def test_delegates_to_index_with_bk_biz_id(mocker):
    get_index = mocker.patch.object(ServiceInstanceModuleIndex, "get", return_value={})

    IpChooserApi.get_service_instance_module_index(100864)

    get_index.assert_called_once_with(100864)
