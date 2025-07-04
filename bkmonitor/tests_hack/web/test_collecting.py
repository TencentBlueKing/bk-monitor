import pytest
from unittest.mock import patch, MagicMock
from django.db.models import Q, Model

from monitor_web.models.plugin import (
    PluginVersionHistory,
    CollectorPluginInfo,
    CollectorPluginConfig,
    CollectorPluginMeta,
)
from monitor_web.models.collecting import CollectConfigMeta, DeploymentConfigVersion
from bkmonitor.utils.request import get_request_tenant_id
from monitor_web.collecting.deploy.k8s import K8sInstaller

pytestmark = pytest.mark.django_db

BK_TENANT_ID = get_request_tenant_id()
BK_BIZ_ID = 2


@pytest.mark.order(1)
@pytest.fixture(autouse=True)
def prepare_data():
    CollectConfigMeta.objects.all().delete()
    CollectorPluginMeta.objects.all().delete()
    DeploymentConfigVersion.objects.all().delete()
    CollectorPluginInfo.objects.all().delete()
    PluginVersionHistory.objects.all().delete()
    CollectorPluginConfig.objects.all().delete()

    # 创建Script插件
    create_collect("cpu_usage", "采集CPU使用率")
    create_collect("memory_usage", "采集内存使用率")
    create_collect("disk_usage", "采集磁盘使用率")
    create_collect("net_usage", "采集网络使用率")

    # 升级插件
    upgrade_plugin("cpu_usage", 2, 2)  # CPU使用率升级到2版本
    upgrade_collect_config(plugin_id="cpu_usage")  # 升级配置

    upgrade_plugin("cpu_usage", 3, 3)  # CPU使用率升级到3版本
    upgrade_collect_config(plugin_id="cpu_usage")

    upgrade_plugin("cpu_usage", 4, 4)  # CPU使用率升级到4版本
    upgrade_collect_config(plugin_id="cpu_usage")

    upgrade_plugin("memory_usage", 2, 2)  # 内存使用率升级到2版本
    upgrade_collect_config("memory_usage")

    # 创建K8s采集配置
    plugin_id = "k8s_cpu_load"
    create_collect(
        plugin_id,
        "k8sCPU负载",
        collect_plugin=create_collect_plugin_meta(plugin_id, plugin_type="K8S"),
        collect_type="K8S",
    )
    upgrade_plugin(plugin_id, 2, 2)

    plugin_id = "k8s_memory_load"
    create_collect(
        plugin_id,
        "k8s内存负载",
        collect_plugin=create_collect_plugin_meta(plugin_id, plugin_type="K8S"),
        collect_type="K8S",
    )
    upgrade_plugin(plugin_id, 2, 2)


@pytest.fixture(autouse=True)
def mock_collect_config_meta():
    new_attr = property(lambda self: f"{self.plugin_id}_{self.name}")
    with patch.object(CollectConfigMeta, "label_info", new=new_attr):
        yield


def perform_fun_in_dict(target_dict: dict, fun_args_map: dict | list):
    """
    执行字典中的函数
    """
    if isinstance(fun_args_map, list):
        fun_args_map = {key: {} for key in fun_args_map}
    assert isinstance(fun_args_map, dict)
    for key, args in fun_args_map.items():
        assert key in target_dict
        if isinstance(target_dict[key], Model):
            continue
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
        "config_json": {},
        "collector_json": {},
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


def create_collect_plugin_meta(plugin_id: str, plugin_version: PluginVersionHistory = None, **kwargs) -> dict:
    """
    创建插件元数据
    """

    assert not CollectorPluginMeta.objects.filter(plugin_id=plugin_id).exists()

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
        "subscription_id": config_meta_id,
        "target_node_type": "",
        "params": {},
        "target_nodes": [],
        "remote_collecting_host": None,
        "task_ids": None,
    }
    kwargs.pop("plugin_version", None)
    kwargs.pop("config_meta_id", None)
    update_dict(deployment_config_version, kwargs)
    return DeploymentConfigVersion.objects.create(**deployment_config_version)


def create_collect_config_meta(plugin_id, name, collect_plugin: CollectorPluginMeta = None, **kwargs):
    """
    创建采集元数据
    """

    assert not CollectConfigMeta.objects.filter(Q(plugin_id=plugin_id) | Q(name=name)).exists()

    if collect_plugin is None:
        collect_plugin = create_collect_plugin_meta(plugin_id)

    plugin_version = collect_plugin["plugin_version"]
    collect_plugin = collect_plugin["plugin_meta"]

    assert collect_plugin.plugin_id == plugin_id

    collect_config = {
        "bk_tenant_id": BK_TENANT_ID,
        "bk_biz_id": 2,
        "name": name,
        "collect_type": "Script",
        "plugin_id": plugin_id,
        "target_object_type": "SERVICE",
        "deployment_config": create_deployment_config_version,
        "cache_data": {"total_instance_count": 10},
        "last_operation": "CREATE",
        "operation_result": "DEPLOYING",
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


def create_collect(*args, **kwargs):
    """
    创建采集
    :return:
    """
    return create_collect_config_meta(*args, **kwargs)


def upgrade_plugin(plugin_id, info_version: int, config_version: int):
    """
    升级插件
    """
    plugin_versions = PluginVersionHistory.objects.filter(plugin_id=plugin_id)
    max_info_version = max(set(plugin_versions.values_list("info_version", flat=True)))
    max_config_version = max(set(plugin_versions.values_list("config_version", flat=True)))
    assert info_version > max_info_version
    assert config_version > max_config_version

    create_plugin_version_history(plugin_id=plugin_id, info_version=info_version, config_version=config_version)


def upgrade_collect_config(plugin_id):
    """
    升级采集配置
    """
    last_plugin_version = PluginVersionHistory.objects.filter(plugin_id=plugin_id).last()

    config_meta_id = CollectConfigMeta.objects.filter(plugin_id=plugin_id).last().id
    create_deployment_config_version(last_plugin_version, config_meta_id)


@pytest.fixture()
def mock_list_spaces():
    with patch("bkm_space.api.SpaceApi.list_spaces") as list_spaces:
        space = MagicMock()
        space.bk_biz_id = BK_BIZ_ID
        space.space_name = "test_space"
        space.type_name = "test_type"
        list_spaces.return_value = [space]
        yield list_spaces


@pytest.fixture()
def mock_query_data_source():
    with patch("core.drf_resource.api.metadata.query_data_source_by_space_uid") as query_data_source:
        global_plugins = CollectorPluginMeta.objects.all().values("plugin_id", "plugin_type")
        query_data_source.return_value = [
            {"data_name": f"{plugin['plugin_id']}_{plugin['plugin_type']}".lower() for plugin in global_plugins}
        ]
        yield query_data_source


# @pytest.fixture()
# def mock_fetch_sub_statistics():
#     with patch("monitor_web.collecting.utils.fetch_sub_statistics") as fetch_sub_statistics:
#         subscription_id_config_map = {config.id: config for config in CollectConfigMeta.objects.exclude(plugin_id__icontains="k8s")}
#         statistics_data = []
#
#         for subscription_id in subscription_id_config_map:
#             statistics_data.append({"subscription_id": subscription_id, "status": []})
#         fetch_sub_statistics.return_value = subscription_id_config_map, statistics_data
#         yield


@pytest.mark.order(2)
@pytest.fixture()
def mock_fetch_subscription_statistic():
    with patch("core.drf_resource.api.node_man.fetch_subscription_statistic.bulk_request") as fetch:
        config_ids = (
            CollectConfigMeta.objects.exclude(plugin_id__icontains="k8s")
            .select_related("deployment_config")
            .values_list("deployment_config__subscription_id", flat=True)
        )
        statistics_data = [{"subscription_id": _id, "status": []} for _id in config_ids]
        fetch.return_value = [statistics_data]
        yield


@pytest.fixture()
def mock_k8s_install_status():
    with patch.object(
        K8sInstaller,
        "status",
        new=lambda self: (
            [
                {
                    "child": [
                        {
                            "instance_id": "default",
                            "instance_name": "公共采集集群",
                            "status": "FAILED",
                            "plugin_version": self.collect_config.deployment_config.plugin_version.version,
                            "log": "",
                            "action": "",
                            "steps": {},
                        }
                    ],
                    "node_path": "集群",
                    "label_name": "",
                    "is_label": False,
                }
            ]
        ),
    ):
        yield


class TestCollectConfigList:
    def test_collect_config_list(
        self, mock_list_spaces, mock_query_data_source, mock_fetch_subscription_statistic, mock_k8s_install_status
    ):
        from monitor_web.collecting.resources.backend import CollectConfigListResource

        operation_results = CollectConfigMeta.objects.values_list("operation_result", flat=True)
        assert all(result == "DEPLOYING" for result in operation_results)

        config_list_instance = CollectConfigListResource()
        config_list = config_list_instance.perform_request(
            {"bk_biz_id": 2, "refresh_status": True, "order": "-create_time", "search": {}, "page": 1, "limit": 50}
        )

        for config in config_list["config_list"]:
            config.pop("update_time")
            config.pop("id")

        config_list["config_list"] = sorted(config_list["config_list"], key=lambda x: x["name"])
        assert len(config_list["config_list"]) == 6
        assert config_list["total"] == 6

        not_k8s_plugin_ids = ("cpu_usage", "memory_usage", "disk_usage", "net_usage")
        operation_results = CollectConfigMeta.objects.filter(plugin_id__in=not_k8s_plugin_ids).values_list(
            "operation_result", flat=True
        )
        assert len(operation_results) == len(not_k8s_plugin_ids)
        assert all(result == "SUCCESS" for result in operation_results)

        k8s_plugin_ids = ("k8s_cpu_load", "k8s_memory_load")
        operation_results = CollectConfigMeta.objects.filter(plugin_id__in=k8s_plugin_ids).values_list(
            "operation_result", flat=True
        )
        assert len(operation_results) == len(k8s_plugin_ids)
        assert all(result == "FAILED" for result in operation_results)

        assert CollectConfigMeta.objects.get(plugin_id="cpu_usage").plugin.packaged_release_version.config_version == 4
        assert (
            CollectConfigMeta.objects.get(plugin_id="memory_usage").plugin.packaged_release_version.config_version == 2
        )
        assert CollectConfigMeta.objects.get(plugin_id="disk_usage").plugin.packaged_release_version.config_version == 1
        assert CollectConfigMeta.objects.get(plugin_id="net_usage").plugin.packaged_release_version.config_version == 1
        assert (
            CollectConfigMeta.objects.get(plugin_id="k8s_cpu_load").plugin.packaged_release_version.config_version == 2
        )
        assert (
            CollectConfigMeta.objects.get(plugin_id="k8s_memory_load").plugin.packaged_release_version.config_version
            == 2
        )

        import json

        print(json.dumps(config_list, ensure_ascii=False))
