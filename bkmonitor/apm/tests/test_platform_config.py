from apm.core.platform_config import PlatformConfig
from bkmonitor.utils.bk_collector_config import BkCollectorConfig
from constants.common import DEFAULT_TENANT_ID


def test_get_target_host_ids_by_tenant_excludes_blacklisted_biz(settings, mocker):
    settings.NEW_ENV_BIZ_BLACK_LIST = [12]
    mocker.patch(
        "bkmonitor.utils.bk_collector_config.api.cmdb.search_cloud_area",
        return_value=[{"bk_cloud_id": 0}, {"bk_cloud_id": -1}, {"bk_cloud_id": 1}],
    )
    get_proxies = mocker.patch(
        "bkmonitor.utils.bk_collector_config.api.node_man.get_proxies",
        return_value=[
            {"bk_host_id": 101, "bk_biz_id": 11, "status": "RUNNING"},
            {"bk_host_id": 102, "bk_biz_id": 12, "status": "RUNNING"},
            {"bk_host_id": 103, "bk_biz_id": 13, "status": "TERMINATED"},
        ],
    )

    host_ids = BkCollectorConfig.get_target_host_ids_by_bk_tenant_id("tenant-1")

    assert host_ids == [101]
    get_proxies.assert_called_once_with(bk_tenant_id="tenant-1", bk_cloud_id=1)


def test_refresh_excludes_blacklisted_biz_and_keeps_default_hosts(mocker):
    platform_config = {"config": "value"}
    mocker.patch.object(PlatformConfig, "get_platform_config", return_value=platform_config)
    get_target_hosts = mocker.patch.object(PlatformConfig, "get_target_host_ids_by_bk_tenant_id", return_value=[101])
    mocker.patch.object(PlatformConfig, "get_target_host_in_default_cloud_area", return_value=[201])
    deploy_to_nodeman = mocker.patch.object(PlatformConfig, "deploy_to_nodeman")

    PlatformConfig.refresh(DEFAULT_TENANT_ID)

    get_target_hosts.assert_called_once_with(DEFAULT_TENANT_ID)
    deploy_to_nodeman.assert_called_once_with(DEFAULT_TENANT_ID, platform_config, [101, 201])
