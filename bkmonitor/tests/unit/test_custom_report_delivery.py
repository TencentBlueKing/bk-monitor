from collections import Counter
from functools import partial
from threading import Event, current_thread, main_thread
from types import SimpleNamespace

import pytest
from kubernetes import client

from bkmonitor.utils.bk_collector_config import BkCollectorClusterConfig
from constants.bk_collector import BkCollectorComp
from core.errors.alarm_backends import CronLeaseLost
from metadata.models.custom_report import subscription_config
from metadata.models.custom_report.subscription_config import CustomReportSubscription


@pytest.mark.parametrize(
    ("phase", "method"),
    [
        ("deploy", "create"),
        ("deploy", "patch"),
        ("same_protocol", "delete"),
        ("same_protocol", "replace"),
        ("cross_protocol", "delete"),
        ("cross_protocol", "replace"),
    ],
)
def test_k8s_refresh_checks_lease_before_each_secret_write(mocker, phase, method):
    mocker.patch.object(BkCollectorClusterConfig, "get_cluster_mapping", return_value={("test", "test", False): {2}})
    mocker.patch.object(BkCollectorClusterConfig, "sub_config_tpl", return_value="config")
    mocker.patch.object(
        BkCollectorComp,
        "get_secrets_config_map_by_protocol",
        side_effect=lambda cluster, protocol: {
            "secret_hash_ring_bucket_count": 2,
            "secret_hash_ring_bucket_name_tpl": "bucket-{}-{}",
            "secret_data_key_tpl": "{}.conf",
            "secret_extra_label": f"protocol={protocol}",
        },
    )
    lost = Event()
    reads = Counter()
    writes_after_loss = []
    checked_in_worker = []

    def check_lease():
        if lost.is_set():
            checked_in_worker.append(current_thread() is not main_thread())
            raise CronLeaseLost

    def secret(name, data, timestamp=0):
        return SimpleNamespace(metadata=SimpleNamespace(name=name, creation_timestamp=timestamp), data=data)

    def list_secrets(**kwargs):
        protocol = kwargs["label_selector"].split("protocol=")[1]
        reads[protocol] += 1
        items = []
        if phase == "deploy" and method == "patch":
            items = [secret("bucket-0-2", {}), secret("bucket-1-2", {})]
        elif (phase == "same_protocol" and reads[protocol] == 2) or (
            phase == "cross_protocol" and reads[protocol] == 3
        ):
            stale_ids = [102, 106] if protocol == "json" else [101, 105]
            keys = [f"{data_id}.conf" for data_id in stale_ids]
            for key in keys:
                data = {key: "old"}
                if method == "replace":
                    data[f"keep-{key}"] = "unrelated"
                items.append(secret(f"old-{key}", data))
            if phase == "same_protocol":
                items.append(secret("current", dict.fromkeys(keys, "current"), timestamp=1))
        return SimpleNamespace(items=items)

    def write(operation, **kwargs):
        if lost.is_set():
            writes_after_loss.append(operation)
        if operation == method:
            lost.set()

    mocker.patch.object(client.CoreV1Api, "list_namespaced_secret", side_effect=list_secrets)
    for operation in ("create", "patch", "delete", "replace"):
        mocker.patch.object(client.CoreV1Api, f"{operation}_namespaced_secret", side_effect=partial(write, operation))

    # 101/105 落入两个不同的桶。跨协议清理也需要另一个协议的两个 DataID。
    configs = [({"bk_data_id": 101}, "json"), ({"bk_data_id": 105}, "json")]
    if phase == "cross_protocol":
        configs.extend([({"bk_data_id": 102}, "prometheus"), ({"bk_data_id": 106}, "prometheus")])
    with pytest.raises(CronLeaseLost):
        CustomReportSubscription._refresh_k8s_custom_config_by_biz(2, configs, check_lease)
    assert writes_after_loss == []
    assert checked_in_worker == [True]


@pytest.mark.parametrize("v3", [False, True], ids=["v2", "v3"])
def test_item_failure_is_reported_and_remaining_configs_reach_business_and_public_proxy(mocker, v3):
    configs = [({"bk_data_id": data_id}, "json") for data_id in (101, 102, 103)]
    mocker.patch.object(CustomReportSubscription, "get_custom_event_config", return_value={2: configs})
    mocker.patch.object(CustomReportSubscription, "get_custom_time_series_config", return_value={})
    mocker.patch.object(subscription_config, "is_biz_id_in_black_list", return_value=False)
    mocker.patch.object(subscription_config, "bk_biz_id_to_space_uid", return_value="bkcc__2")
    mocker.patch.object(
        subscription_config.host_queries, "business_proxies", return_value=[{"bk_cloud_id": 1, "bk_biz_id": 2}]
    )
    mocker.patch.object(subscription_config.api.cmdb, "get_host_by_ip", return_value=[{"bk_host_id": 11}])
    mocker.patch.object(
        subscription_config.api.cmdb,
        "get_host_without_biz",
        return_value={"hosts": [{"bk_cloud_id": 0, "bk_host_id": 12}]},
    )
    mocker.patch.object(subscription_config.BkCollectorDeployPolicy, "is_enabled", return_value=v3)
    owner, method = (
        (subscription_config.BkCollectorDeployPolicy, "deploy")
        if v3
        else (CustomReportSubscription, "create_or_update_config")
    )
    deploy = mocker.patch.object(
        owner,
        method,
        side_effect=[None, RuntimeError("deploy failed"), 3, 4, 5, 6],
    )
    report = CustomReportSubscription.refresh_collector_custom_conf("system", 2, deploy_targets="node_man")
    assert [
        (call.kwargs["bk_biz_id"], call.kwargs["context"]["bk_data_id"] if v3 else call.kwargs["bk_data_id"])
        for call in deploy.call_args_list
    ] == [(2, 101), (2, 102), (2, 103), (0, 101), (0, 102), (0, 103)]
    business, public = report["details"]
    business_target = business["targets"]["node_man"]
    assert business_target["result"] is False
    assert business_target["failed_data_ids"] == [102]
    assert business_target["proxy_host_ids"] == [11]
    assert public["targets"]["node_man"]["result"] is True
    assert public["data_ids"] == [101, 102, 103]
    assert report["summary"]["failed_count"] == report["summary"]["succeeded_count"] == 1
