"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from contextlib import ExitStack
from unittest import mock

import pytest
from django.test import override_settings

from core.drf_resource import api
from metadata.models.bk_collector import BkCollectorDeployPolicy, BkCollectorDeployScene
from metadata.models.custom_report.subscription_config import CustomReportSubscription
from metadata.models.ping_server import PingServerSubscriptionConfig

pytestmark = pytest.mark.django_db(databases="__all__")

TENANT = "system"
HOST_BIZ = {101: 2, 102: 2, 201: 3}


def _list_hosts(**kwargs):
    host_ids = kwargs["exact_include_conditions"]["bk_host_id"]
    items = [{"bk_host_id": h, "info": {"bk_biz_id": HOST_BIZ[h]}} for h in host_ids if h in HOST_BIZ]
    return {"total": len(items), "items": items}


@pytest.fixture
def nodeman_v3():
    BkCollectorDeployPolicy._host_biz_cache.clear()
    with ExitStack() as stack:
        mocks = {
            "list_hosts": stack.enter_context(
                mock.patch.object(api.node_man_v3, "list_hosts", side_effect=_list_hosts)
            ),
            "list_deploy_policies": stack.enter_context(
                mock.patch.object(api.node_man_v3, "list_deploy_policies", return_value={"total": 0, "items": []})
            ),
            "create_deploy_policy": stack.enter_context(
                mock.patch.object(api.node_man_v3, "create_deploy_policy", return_value={"deploy_policy_id": 9001})
            ),
            "update_deploy_policy": stack.enter_context(
                mock.patch.object(api.node_man_v3, "update_deploy_policy", return_value={})
            ),
            "execute_deploy_policy": stack.enter_context(
                mock.patch.object(api.node_man_v3, "execute_deploy_policy", return_value={"workflow_id": "wf-1"})
            ),
            "v2_create": stack.enter_context(mock.patch.object(api.node_man, "create_subscription")),
            "v2_update": stack.enter_context(mock.patch.object(api.node_man, "update_subscription")),
            "v2_run": stack.enter_context(mock.patch.object(api.node_man, "run_subscription")),
            "v2_switch": stack.enter_context(mock.patch.object(api.node_man, "switch_subscription")),
        }
        with override_settings(ENABLE_BK_COLLECTOR_NODEMAN_V3=True):
            yield mocks


def _deploy(context=None, host_ids=(101, 102, 201)):
    return BkCollectorDeployPolicy.deploy(
        bk_tenant_id=TENANT,
        scene=BkCollectorDeployScene.APM_PLATFORM,
        resource_key="platform",
        template_name="bk-collector-platform.conf",
        context=context or {"token": "x"},
        bk_host_ids=list(host_ids),
    )


def test_deploy_creates_policy_with_biz_grouped_scopes(nodeman_v3):
    assert _deploy() == 9001

    kwargs = nodeman_v3["create_deploy_policy"].call_args.kwargs
    assert kwargs["bk_tenant_id"] == TENANT
    assert kwargs["name"] == "bkmonitor-collector-apm_platform-platform"
    assert kwargs["specs"] == [
        {
            "type": "specify_plugin_sub_config_template",
            "param": {
                "plugin_name": "bk-collector",
                "config_files_detail": [{"template_name": "bk-collector-platform.conf", "is_main_config": False}],
                "custom_config_context": {"token": "x"},
            },
        }
    ]
    assert kwargs["scopes"] == [
        {"type": "instance", "scope": {"granularity": "host", "bk_biz_id": 2, "instance_ids": [101, 102]}},
        {"type": "instance", "scope": {"granularity": "host", "bk_biz_id": 3, "instance_ids": [201]}},
    ]
    nodeman_v3["execute_deploy_policy"].assert_called_once_with(bk_tenant_id=TENANT, deploy_policy_id=9001)
    nodeman_v3["v2_create"].assert_not_called()

    record = BkCollectorDeployPolicy.objects.get(scene=BkCollectorDeployScene.APM_PLATFORM)
    assert record.deploy_policy_id == 9001
    assert record.bk_host_ids == [101, 102, 201]
    assert record.last_workflow_id == "wf-1"
    assert record.fingerprint


def test_deploy_unchanged_does_not_call_nodeman_again(nodeman_v3):
    _deploy()
    _deploy()

    assert nodeman_v3["create_deploy_policy"].call_count == 1
    nodeman_v3["update_deploy_policy"].assert_not_called()
    assert nodeman_v3["execute_deploy_policy"].call_count == 1
    # 主机所属业务命中缓存
    assert nodeman_v3["list_hosts"].call_count == 1


def test_deploy_updates_when_context_or_hosts_change(nodeman_v3):
    _deploy()
    _deploy(context={"token": "y"})
    _deploy(context={"token": "y"}, host_ids=(101,))

    assert nodeman_v3["update_deploy_policy"].call_count == 2
    last = nodeman_v3["update_deploy_policy"].call_args.kwargs
    assert last["fields"] == {"meta": True, "scopes": True, "enabled": True, "specs": True}
    policy = last["deploy_policies"][0]
    assert policy["deploy_policy_id"] == 9001
    assert policy["specs"][0]["param"]["custom_config_context"] == {"token": "y"}
    assert policy["scopes"] == [
        {"type": "instance", "scope": {"granularity": "host", "bk_biz_id": 2, "instance_ids": [101]}}
    ]
    assert nodeman_v3["execute_deploy_policy"].call_count == 3


def test_deploy_recovers_existing_policy_by_name(nodeman_v3):
    nodeman_v3["list_deploy_policies"].return_value = {
        "total": 1,
        "items": [{"deploy_policy_id": 7, "meta": {"name": "bkmonitor-collector-apm_platform-platform"}}],
    }
    assert _deploy() == 7

    nodeman_v3["create_deploy_policy"].assert_not_called()
    assert nodeman_v3["update_deploy_policy"].call_args.kwargs["deploy_policies"][0]["deploy_policy_id"] == 7


def test_deploy_skips_without_target_hosts(nodeman_v3):
    assert _deploy(host_ids=()) is None
    assert _deploy(host_ids=(999,)) is None  # 节点管理里查不到的主机

    nodeman_v3["create_deploy_policy"].assert_not_called()
    nodeman_v3["execute_deploy_policy"].assert_not_called()


def test_execute_failure_keeps_policy_id_and_retries(nodeman_v3):
    nodeman_v3["execute_deploy_policy"].side_effect = ValueError("boom")
    with pytest.raises(ValueError):
        _deploy()

    record = BkCollectorDeployPolicy.objects.get(scene=BkCollectorDeployScene.APM_PLATFORM)
    assert record.deploy_policy_id == 9001
    assert record.fingerprint == ""

    nodeman_v3["execute_deploy_policy"].side_effect = None
    _deploy()
    assert nodeman_v3["create_deploy_policy"].call_count == 1
    assert nodeman_v3["update_deploy_policy"].call_count == 1


def test_withdraw_clears_scopes_and_keeps_specs(nodeman_v3):
    _deploy()
    record = BkCollectorDeployPolicy.objects.get(scene=BkCollectorDeployScene.APM_PLATFORM)
    record.withdraw()
    record.withdraw()

    assert nodeman_v3["update_deploy_policy"].call_count == 1
    kwargs = nodeman_v3["update_deploy_policy"].call_args.kwargs
    assert kwargs["fields"]["specs"] is False
    assert "specs" not in kwargs["deploy_policies"][0]
    assert kwargs["deploy_policies"][0]["scopes"] == []
    record.refresh_from_db()
    assert record.bk_host_ids == []


def test_custom_report_uses_v3_per_data_id(nodeman_v3):
    with mock.patch.object(BkCollectorDeployPolicy, "deploy") as deploy:
        CustomReportSubscription.create_subscription(
            bk_tenant_id=TENANT,
            bk_biz_id=2,
            data_id_configs=[({"bk_data_id": 1001, "token": "a"}, "json"), ({"bk_data_id": 1002}, "prometheus")],
            bk_host_ids=[101],
        )

    assert [call.kwargs["resource_key"] for call in deploy.call_args_list] == ["2-1001", "2-1002"]
    assert [call.kwargs["template_name"] for call in deploy.call_args_list] == [
        "bk-collector-report-v2.conf",
        "bk-collector-application.conf",
    ]
    assert deploy.call_args_list[0].kwargs["context"] == {"bk_biz_id": 2, "bk_data_id": 1001, "token": "a"}
    nodeman_v3["v2_create"].assert_not_called()
    assert not CustomReportSubscription.objects.exists()


def test_ping_server_v3_deploys_per_proxy_and_withdraws_unused(nodeman_v3):
    target_hosts = [{"bk_host_id": 101, "bk_biz_id": 2, "ip": "127.0.0.1", "ipv6": ""}]
    items = {101: [{"target_ip": "127.0.0.1", "target_cloud_id": 0}]}
    PingServerSubscriptionConfig.create_subscription(TENANT, 0, items, target_hosts, "bk-collector")

    kwargs = nodeman_v3["create_deploy_policy"].call_args.kwargs
    assert kwargs["name"] == "bkmonitor-collector-ping_server-cloud0-host101"
    param = kwargs["specs"][0]["param"]
    assert param["config_files_detail"] == [{"template_name": "bkmonitorproxy_ping.conf", "is_main_config": False}]
    context = param["custom_config_context"]
    assert context["server_host_id"] == "{{ cmdb_instance.host.bk_host_id }}"
    assert context["ip_to_items"] == {"101": items[101]}
    assert not PingServerSubscriptionConfig.objects.exists()

    # Proxy 下线后清空该策略范围
    PingServerSubscriptionConfig.create_subscription(TENANT, 0, {}, [], "bk-collector")
    withdraw = nodeman_v3["update_deploy_policy"].call_args.kwargs["deploy_policies"][0]
    assert withdraw["scopes"] == []
    nodeman_v3["v2_create"].assert_not_called()
    nodeman_v3["v2_run"].assert_not_called()


def test_v2_chain_untouched_when_disabled(nodeman_v3):
    nodeman_v3["v2_create"].return_value = {"subscription_id": 1}
    with override_settings(ENABLE_BK_COLLECTOR_NODEMAN_V3=False):
        CustomReportSubscription.create_subscription(
            bk_tenant_id=TENANT, bk_biz_id=2, data_id_configs=[({"bk_data_id": 1001}, "json")], bk_host_ids=[101]
        )

    nodeman_v3["v2_create"].assert_called_once()
    nodeman_v3["create_deploy_policy"].assert_not_called()
    assert not BkCollectorDeployPolicy.objects.exists()


def test_custom_report_task_skips_v2_version_gate(nodeman_v3):
    from metadata.task import custom_report

    with (
        mock.patch.object(api.node_man, "plugin_info") as plugin_info,
        mock.patch.object(api.bk_login, "list_tenant", return_value=[{"id": TENANT}]),
        mock.patch.object(CustomReportSubscription, "refresh_collector_custom_conf") as refresh,
    ):
        custom_report.refresh_custom_report_2_node_man()

    plugin_info.assert_not_called()
    refresh.assert_called_once_with(bk_tenant_id=TENANT, bk_biz_id=None)
