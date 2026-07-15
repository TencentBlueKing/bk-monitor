import pytest

from api.cmdb.define import Host
from metadata import models
from metadata.models.ping_server import PingServerSubscriptionConfig
from metadata.task.ping_server import (
    _create_multi_tenant_ping_subscription,
    _refresh_ping_conf_by_cloud_id,
    refresh_biz_ping_conf,
    refresh_ping_conf,
)

pytestmark = pytest.mark.django_db(databases="__all__")


def make_host(bk_biz_id: int, bk_host_id: int, bk_cloud_id: int, ip: str) -> Host:
    return Host(
        {
            "bk_biz_id": bk_biz_id,
            "bk_host_id": bk_host_id,
            "bk_cloud_id": bk_cloud_id,
            "bk_host_innerip": ip,
        }
    )


def test_refresh_ping_conf_filters_new_env_biz_black_list(settings, mocker):
    settings.ENABLE_PING_ALARM = True
    settings.NEW_ENV_BIZ_BLACK_LIST = [2, 0]

    mocker.patch("metadata.task.ping_server.api.bk_login.list_tenant", return_value=[{"id": "system"}])
    mocker.patch(
        "alarm_backends.core.cache.cmdb.host.HostManager.all",
        return_value=[
            make_host(bk_biz_id=0, bk_host_id=4, bk_cloud_id=100, ip="127.0.0.1"),
            make_host(bk_biz_id=2, bk_host_id=1, bk_cloud_id=100, ip="127.0.0.1"),
            make_host(bk_biz_id=3, bk_host_id=2, bk_cloud_id=100, ip="127.0.0.2"),
            make_host(bk_biz_id=2, bk_host_id=3, bk_cloud_id=101, ip="127.0.0.3"),
        ],
    )
    refresh_by_cloud_id = mocker.patch("metadata.task.ping_server._refresh_ping_conf_by_cloud_id")

    refresh_ping_conf("bk-collector")

    refresh_by_cloud_id.assert_called_once_with(
        "system",
        100,
        "bk-collector",
        [
            {"ip": "127.0.0.1", "bk_cloud_id": 100, "bk_biz_id": 0, "bk_host_id": 4},
            {"ip": "127.0.0.2", "bk_cloud_id": 100, "bk_biz_id": 3, "bk_host_id": 2},
        ],
    )


def test_refresh_biz_ping_conf_only_refreshes_related_clouds_with_all_cloud_hosts(mocker):
    mocker.patch(
        "alarm_backends.core.cache.cmdb.host.HostManager.all",
        return_value=[
            make_host(bk_biz_id=2, bk_host_id=1, bk_cloud_id=100, ip="127.0.0.1"),
            make_host(bk_biz_id=3, bk_host_id=2, bk_cloud_id=100, ip="127.0.0.2"),
            make_host(bk_biz_id=3, bk_host_id=3, bk_cloud_id=101, ip="127.0.0.3"),
        ],
    )
    refresh_by_cloud_id = mocker.patch("metadata.task.ping_server._refresh_ping_conf_by_cloud_id")

    refresh_biz_ping_conf(bk_tenant_id="system", bk_biz_ids=[2], plugin_name="bk-collector")

    refresh_by_cloud_id.assert_called_once_with(
        "system",
        100,
        "bk-collector",
        [
            {"ip": "127.0.0.1", "bk_cloud_id": 100, "bk_biz_id": 2, "bk_host_id": 1},
            {"ip": "127.0.0.2", "bk_cloud_id": 100, "bk_biz_id": 3, "bk_host_id": 2},
        ],
    )


def _create_ping_data_source(bk_tenant_id: str, bk_biz_id: int, bk_data_id: int):
    return models.DataSource.objects.create(
        bk_data_id=bk_data_id,
        bk_tenant_id=bk_tenant_id,
        data_name=f"base_{bk_biz_id}_pingserver",
        etl_config="bk_standard_v2_time_series",
        source_label="bk_monitor",
        type_label="time_series",
        mq_cluster_id=1,
        mq_config_id=1,
        transfer_cluster_id="default",
        is_custom_source=False,
    )


def test_multi_tenant_ping_subscription_split_by_target_biz(settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.SPACE_BUILTIN_DATA_LINK_MODE = "biz"
    _create_ping_data_source("system", 11, 210011)
    _create_ping_data_source("system", 12, 210012)
    create_subscription = mocker.patch("metadata.task.ping_server.PingServerSubscriptionConfig.create_subscription")

    _create_multi_tenant_ping_subscription(
        bk_tenant_id="system",
        bk_cloud_id=100,
        plugin_name="bk-collector",
        target_hosts=[
            {"bk_host_id": 101, "bk_biz_id": 2, "ip": "127.0.0.101", "ipv6": "", "bk_cloud_id": 100},
            {"bk_host_id": 102, "bk_biz_id": 2, "ip": "127.0.0.102", "ipv6": "", "bk_cloud_id": 100},
        ],
        items={
            101: [
                {"target_ip": "127.0.0.11", "target_cloud_id": 100, "target_biz_id": 11},
                {"target_ip": "127.0.0.12", "target_cloud_id": 100, "target_biz_id": 12},
            ],
            102: [{"target_ip": "127.0.0.13", "target_cloud_id": 100, "target_biz_id": 11}],
        },
    )

    assert create_subscription.call_count == 2
    calls = {call.kwargs["bk_biz_id"]: call.kwargs for call in create_subscription.call_args_list}
    assert calls[11]["bk_data_id"] == 210011
    assert calls[12]["bk_data_id"] == 210012
    assert {host["bk_host_id"] for host in calls[11]["target_hosts"]} == {101, 102}
    assert {host["bk_host_id"] for host in calls[12]["target_hosts"]} == {101}
    assert set(calls[11]["items"]) == {101, 102}
    assert set(calls[12]["items"]) == {101}


def test_multi_tenant_ping_subscription_tenant_mode_uses_default_biz_data_id(settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.SPACE_BUILTIN_DATA_LINK_MODE = "tenant"
    _create_ping_data_source("system", 99, 210099)
    mocker.patch("metadata.task.ping_server.get_tenant_default_biz_id", return_value=99)
    create_subscription = mocker.patch("metadata.task.ping_server.PingServerSubscriptionConfig.create_subscription")

    _create_multi_tenant_ping_subscription(
        bk_tenant_id="system",
        bk_cloud_id=100,
        plugin_name="bk-collector",
        target_hosts=[{"bk_host_id": 101, "bk_biz_id": 2, "ip": "127.0.0.101", "ipv6": "", "bk_cloud_id": 100}],
        items={
            101: [
                {"target_ip": "127.0.0.11", "target_cloud_id": 100, "target_biz_id": 11},
                {"target_ip": "127.0.0.12", "target_cloud_id": 100, "target_biz_id": 12},
            ]
        },
    )

    assert create_subscription.call_count == 2
    assert {call.kwargs["bk_biz_id"] for call in create_subscription.call_args_list} == {11, 12}
    assert {call.kwargs["bk_data_id"] for call in create_subscription.call_args_list} == {210099}


def test_multi_tenant_ping_subscription_skips_missing_data_id(settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = True
    settings.SPACE_BUILTIN_DATA_LINK_MODE = "biz"
    create_subscription = mocker.patch("metadata.task.ping_server.PingServerSubscriptionConfig.create_subscription")

    _create_multi_tenant_ping_subscription(
        bk_tenant_id="system",
        bk_cloud_id=100,
        plugin_name="bk-collector",
        target_hosts=[{"bk_host_id": 101, "bk_biz_id": 2, "ip": "127.0.0.101", "ipv6": "", "bk_cloud_id": 100}],
        items={101: [{"target_ip": "127.0.0.11", "target_cloud_id": 100, "target_biz_id": 11}]},
    )

    create_subscription.assert_not_called()


def test_single_tenant_ping_subscription_keeps_fixed_data_id_and_refreshes_proxy_biz(settings, mocker):
    settings.PING_SERVER_DATAID = 1100005
    mocker.patch("metadata.models.ping_server.api.cmdb.get_host_without_biz", return_value={"hosts": []})
    mocker.patch(
        "metadata.models.ping_server.api.node_man.create_subscription", return_value={"subscription_id": 12345}
    )
    mocker.patch("metadata.models.ping_server.api.node_man.run_subscription")
    mocker.patch("metadata.models.ping_server.api.node_man.switch_subscription")

    PingServerSubscriptionConfig.create_subscription(
        bk_tenant_id="system",
        bk_cloud_id=100,
        items={101: []},
        target_hosts=[{"bk_host_id": 101, "bk_biz_id": 77, "ip": "127.0.0.101", "ipv6": "", "bk_cloud_id": 100}],
        plugin_name="bk-collector",
    )

    config = PingServerSubscriptionConfig.objects.get(subscription_id=12345)
    assert config.bk_biz_id == 77
    assert config.config["steps"][0]["params"]["context"]["dataid"] == 1100005


def test_refresh_ping_conf_by_cloud_id_single_tenant_uses_original_subscription(settings, mocker):
    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.ENABLE_PING_ALARM = True
    settings.ENABLE_DIRECT_AREA_PING_COLLECT = True
    mocker.patch(
        "metadata.task.ping_server.api.node_man.get_proxies",
        return_value=[
            {"bk_host_id": 101, "bk_biz_id": 77, "bk_cloud_id": 100, "inner_ip": "127.0.0.101", "status": "RUNNING"}
        ],
    )
    create_subscription = mocker.patch("metadata.task.ping_server.PingServerSubscriptionConfig.create_subscription")

    _refresh_ping_conf_by_cloud_id(
        "system",
        100,
        "bk-collector",
        [{"ip": "127.0.0.11", "bk_cloud_id": 100, "bk_biz_id": 11, "bk_host_id": 201}],
    )

    create_subscription.assert_called_once()
    args = create_subscription.call_args.args
    assert args[0] == "system"
    assert args[1] == 100
    assert args[4] == "bk-collector"
    assert create_subscription.call_args.kwargs == {}
