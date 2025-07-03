import pytest
from unittest.mock import patch, MagicMock


from monitor_web.models.plugin import (
    PluginVersionHistory,
    CollectorPluginInfo,
    CollectorPluginConfig,
    CollectorPluginMeta,
)
from monitor_web.models.collecting import CollectConfigMeta, DeploymentConfigVersion
from monitor_web.collecting.resources.backend import CollectConfigListResource
from bkmonitor.utils.request import get_request_tenant_id


pytestmark = pytest.mark.django_db(databases=["default", "monitor_api"])

BK_TENANT_ID = get_request_tenant_id()
PLUGIN_ID = "test_plugin"
BK_BIZ_ID = 2


@pytest.fixture(autouse=True, scope="module")
def prepare_database():
    pass


def perform_fun_in_dict(target_dict: dict, fun_args_map: dict | list):
    """
    执行字典中的函数
    """
    if isinstance(fun_args_map, list):
        fun_args_map = {key: {} for key in fun_args_map}
    assert isinstance(fun_args_map, dict)
    for key, args in fun_args_map.items():
        assert key in target_dict
        assert callable(target_dict[key])
        target_dict[key] = target_dict[key](**args)


def update_dict(target_dict: dict, kwargs: dict, fun_args_map: dict | list = None):
    """
    更新字典
    """
    update_keys = target_dict.keys()
    target_dict.update({key: value for key, value in kwargs.items() if key in update_keys})

    if not fun_args_map:
        return
    perform_fun_in_dict(target_dict, fun_args_map)


def create_collect_plugin_info(**kwargs):
    plugin_info = {
        "plugin_display_name": "test_plugin",
        "metric_json": "",
        "description_md": "test_plugin",
        "logo": "",
        "enable_field_blacklist": True,
    }
    update_dict(plugin_info, kwargs)
    instance = CollectorPluginInfo.objects.create(**plugin_info)
    return instance


def create_plugin_config(**kwargs):
    plugin_config = {
        "config_json": "",
        "collector_json": "",
        "is_support_remote": False,
    }
    update_dict(plugin_config, kwargs)
    instance = CollectorPluginConfig.objects.create(**plugin_config)
    return instance


def create_plugin_version_history(plugin_id: str, **kwargs):
    """
    创建插件版本
    """
    plugin_version_history = {
        "bk_tenant_id": BK_TENANT_ID,
        "plugin_id": plugin_id,
        "stage": PluginVersionHistory.Stage.RELEASE,
        "config": create_plugin_config,
        "info": create_collect_plugin_info,
        "config_version": 1,
        "info_version": 1,
        "signature": "",
        "version_log": "",
        "is_packaged": False,
    }
    update_dict(plugin_version_history, kwargs, ["config", "info"])
    instance = PluginVersionHistory.objects.create(**plugin_version_history)
    return instance


def create_collect_plugin_meta(
    plugin_id: str = PLUGIN_ID, plugin_version: PluginVersionHistory = None, **kwargs
) -> dict:
    """
    创建插件元数据
    """

    plugin_version = plugin_version or create_plugin_version_history(plugin_id)
    # 确保关联的插件ID一致
    assert plugin_version.plugin_id == plugin_id

    data = {
        "bk_tenant_id": BK_TENANT_ID,
        "plugin_id": plugin_id,
        "bk_biz_id": 2,
        "bk_supplier_id": 0,
        "plugin_type": "Script",
        "tag": "",
        "label": "",
        "is_internal": False,
    }
    kwargs.pop("plugin_id", None)
    update_dict(data, kwargs)
    instance = CollectorPluginMeta.objects.create(**data)
    return {"plugin_version": plugin_version, "plugin_meta": instance}


def create_deployment_config_version(plugin_version: PluginVersionHistory, config_meta_id: int, **kwargs):
    """
    创建部署配置版本
    """

    deployment_config_version = {
        "plugin_version": plugin_version,
        "parent_id": None,
        "config_meta_id": config_meta_id,
        "subscription_id": 0,
        "target_node_type": "",
        "params": None,
        "target_nodes": None,
        "remote_collecting_host": None,
        "task_ids": None,
    }
    kwargs.pop("plugin_version", None)
    kwargs.pop("config_meta_id", None)
    update_dict(deployment_config_version, kwargs)
    return DeploymentConfigVersion.objects.create(**deployment_config_version)


def create_collect_config_meta(plugin_id, collect_plugin: CollectorPluginMeta = None, **kwargs):
    """
    创建采集元数据
    """

    if collect_plugin is None:
        collect_plugin = create_collect_plugin_meta(plugin_id)

    plugin_version = collect_plugin["plugin_version"]
    collect_plugin = collect_plugin["plugin_meta"]

    assert collect_plugin.plugin_id == plugin_id

    collect_config = {
        "bk_tenant_id": BK_TENANT_ID,
        "bk_biz_id": 2,
        "name": "测试采集",
        "collect_type": "Script",
        "plugin_id": plugin_id,
        "target_object_type": "SERVICE",
        "deployment_config": create_deployment_config_version,
        "cache_data": "",
        "last_operation": "CREATE",
        "operation_result": "SUCCESS",
        "label": "",
    }
    update_dict(
        collect_config,
        kwargs,
        {
            "deployment_config": {
                "plugin_version": plugin_version,
                "config_meta_id": collect_plugin.id,
            }
        },
    )
    return CollectConfigMeta.objects.create(**collect_config)


def create_collect(plugin_id: str = PLUGIN_ID):
    """
    创建采集
    :return:
    """
    return create_collect_config_meta(plugin_id)


@pytest.fixture
def mock_list_spaces():
    # from bkm_space.api import SpaceApi
    with patch("bkm_space.api.SpaceApi.list_spaces") as list_spaces:
        space = MagicMock()
        space.bk_biz_id = BK_BIZ_ID
        list_spaces.return_value = [space]
        yield list_spaces


@pytest.fixture
def mock_query_data_source():
    with patch("api.metadata.query_data_source_by_space_uid") as query_data_source:
        global_plugins = CollectorPluginMeta.objects.all().values("plugin_id", "plugin_type")
        query_data_source.return_value = [
            {"data_name": f"{plugin['plugin_id']}_{plugin['plugin_type']}".lower() for plugin in global_plugins}
        ]
        yield query_data_source


class TestCollectConfigList:
    def test_collect_config_list(self):
        create_collect()

        config_list = CollectConfigListResource().perform_request(
            {"bk_biz_id": 2, "refresh_status": False, "order": "-create_time", "search": {}, "page": 1, "limit": 50}
        )

        print(config_list)

        print("test_collect_config_list")
