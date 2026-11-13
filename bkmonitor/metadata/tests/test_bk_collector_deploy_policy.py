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
from types import SimpleNamespace
from unittest import mock

import pytest
from django.test import override_settings

from apm.core.application_config import ApplicationConfig
from apm.core.platform_config import PlatformConfig
from bkmonitor.utils import nodeman
from core.drf_resource import api
from metadata.models.bk_collector import BkCollectorDeployPolicy, BkCollectorDeployScene
from metadata.models.custom_report.subscription_config import CustomReportSubscription, LogSubscriptionConfig
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


def test_deploy_keeps_last_scopes_when_deployed_host_temporarily_missing(nodeman_v3):
    """期望仍是两台，但节点管理暂时只查到一台：保留上次范围，不能让节点管理删掉缺失主机上的子配置"""
    _deploy(host_ids=(101, 102))

    BkCollectorDeployPolicy._host_biz_cache.clear()
    with mock.patch.dict(HOST_BIZ):
        del HOST_BIZ[102]
        assert _deploy(context={"token": "y"}, host_ids=(101, 102)) == 9001

    nodeman_v3["update_deploy_policy"].assert_not_called()
    assert nodeman_v3["execute_deploy_policy"].call_count == 1
    record = BkCollectorDeployPolicy.objects.get(scene=BkCollectorDeployScene.APM_PLATFORM)
    assert record.bk_host_ids == [101, 102]

    # 主机重新查到后，本轮变更正常下发
    BkCollectorDeployPolicy._host_biz_cache.clear()
    _deploy(context={"token": "y"}, host_ids=(101, 102))
    policy = nodeman_v3["update_deploy_policy"].call_args.kwargs["deploy_policies"][0]
    assert policy["scopes"] == [
        {"type": "instance", "scope": {"granularity": "host", "bk_biz_id": 2, "instance_ids": [101, 102]}}
    ]
    assert policy["specs"][0]["param"]["custom_config_context"] == {"token": "y"}


def _remote_policy(deploy_policy_id, instance_ids):
    return {
        "total": 1,
        "items": [
            {
                "deploy_policy_id": deploy_policy_id,
                "meta": {"name": "bkmonitor-collector-apm_platform-platform"},
                "scopes": [
                    {
                        "type": "instance",
                        "scope": {"granularity": "host", "bk_biz_id": 2, "instance_ids": list(instance_ids)},
                    }
                ],
            }
        ],
    }


def test_deploy_keeps_remote_scopes_when_binding_lost_and_host_missing(nodeman_v3):
    """本地绑定丢失、按名称找回既有策略时，本轮目标未解析完整也不能缩小远端范围"""
    nodeman_v3["list_deploy_policies"].return_value = _remote_policy(7, [101, 102])

    with mock.patch.dict(HOST_BIZ):
        del HOST_BIZ[102]
        assert _deploy(host_ids=(101, 102)) == 7

    nodeman_v3["update_deploy_policy"].assert_not_called()
    nodeman_v3["create_deploy_policy"].assert_not_called()
    nodeman_v3["execute_deploy_policy"].assert_not_called()
    record = BkCollectorDeployPolicy.objects.get(scene=BkCollectorDeployScene.APM_PLATFORM)
    assert record.deploy_policy_id == 7  # 找回的策略 ID 写回本地绑定

    # 下一轮两台都可解析：复用同一策略 ID 正常同步
    BkCollectorDeployPolicy._host_biz_cache.clear()
    assert _deploy(host_ids=(101, 102)) == 7
    nodeman_v3["create_deploy_policy"].assert_not_called()
    policy = nodeman_v3["update_deploy_policy"].call_args.kwargs["deploy_policies"][0]
    assert policy["deploy_policy_id"] == 7
    assert policy["scopes"] == [
        {"type": "instance", "scope": {"granularity": "host", "bk_biz_id": 2, "instance_ids": [101, 102]}}
    ]
    nodeman_v3["execute_deploy_policy"].assert_called_once_with(bk_tenant_id=TENANT, deploy_policy_id=7)
    record.refresh_from_db()
    assert record.bk_host_ids == [101, 102]


def test_deploy_keeps_remote_scopes_after_previous_execute_failed(nodeman_v3):
    """上次更新范围后执行失败、本地 bk_host_ids 未记录新范围时，以远端范围判断已下发主机"""
    nodeman_v3["execute_deploy_policy"].side_effect = ValueError("boom")
    with pytest.raises(ValueError):
        _deploy(host_ids=(101, 102))
    nodeman_v3["execute_deploy_policy"].side_effect = None
    record = BkCollectorDeployPolicy.objects.get(scene=BkCollectorDeployScene.APM_PLATFORM)
    assert record.bk_host_ids == []

    # 远端策略已是 [101, 102]（节点管理每小时自动执行可能已按此范围下发）
    nodeman_v3["list_deploy_policies"].return_value = _remote_policy(9001, [101, 102])
    BkCollectorDeployPolicy._host_biz_cache.clear()
    with mock.patch.dict(HOST_BIZ):
        del HOST_BIZ[102]
        assert _deploy(host_ids=(101, 102)) == 9001

    nodeman_v3["update_deploy_policy"].assert_not_called()


def test_deploy_shrinks_when_target_hosts_explicitly_reduced(nodeman_v3):
    """业务明确把目标从两台减为一台：正常收缩范围"""
    _deploy(host_ids=(101, 102))

    BkCollectorDeployPolicy._host_biz_cache.clear()
    _deploy(host_ids=(101,))

    policy = nodeman_v3["update_deploy_policy"].call_args.kwargs["deploy_policies"][0]
    assert policy["scopes"] == [
        {"type": "instance", "scope": {"granularity": "host", "bk_biz_id": 2, "instance_ids": [101]}}
    ]
    record = BkCollectorDeployPolicy.objects.get(scene=BkCollectorDeployScene.APM_PLATFORM)
    assert record.bk_host_ids == [101]


def test_deploy_records_only_resolved_hosts_for_new_unresolved_host(nodeman_v3):
    """从未下发过的主机查不到时先下发可解析主机，本地只记录实际下发的主机"""
    assert _deploy(host_ids=(101, 999)) == 9001

    assert nodeman_v3["create_deploy_policy"].call_args.kwargs["scopes"] == [
        {"type": "instance", "scope": {"granularity": "host", "bk_biz_id": 2, "instance_ids": [101]}}
    ]
    record = BkCollectorDeployPolicy.objects.get(scene=BkCollectorDeployScene.APM_PLATFORM)
    assert record.bk_host_ids == [101]

    # 999 仍查不到，不会被当作已下发主机丢失而阻塞，也不会重复变更
    _deploy(host_ids=(101, 999))
    nodeman_v3["update_deploy_policy"].assert_not_called()


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


def test_host_queries_follow_collector_switch(nodeman_v3):
    with override_settings(ENABLE_NODEMAN_V3=False, ENABLE_BK_COLLECTOR_NODEMAN_V3=True):
        assert nodeman.get_host_queries() is nodeman._v3_hosts
    with override_settings(ENABLE_NODEMAN_V3=False, ENABLE_BK_COLLECTOR_NODEMAN_V3=False):
        assert nodeman.get_host_queries() is nodeman._v2_hosts


class _V2NodeManCalled(BaseException):
    """继承 BaseException，避免被业务代码里的 except Exception 吞掉"""


class _ForbiddenV2NodeMan:
    def __getattr__(self, name):
        raise _V2NodeManCalled(f"api.node_man.{name} (NodeMan V2) must not be used when bk-collector V3 is enabled")


def test_v3_delivery_never_touches_v2_nodeman_api(nodeman_v3):
    """开启 V3 后，五个下发场景都不能再访问节点管理 V2 接口（含查询类接口）"""
    with mock.patch.object(api, "node_man", new=_ForbiddenV2NodeMan()):
        PlatformConfig.deploy_to_nodeman(TENANT, {"token": "x"}, [101])

        application = ApplicationConfig.__new__(ApplicationConfig)
        application._application = SimpleNamespace(bk_biz_id=2, app_name="app")
        application.deploy(TENANT, {"token": "x"}, [101])

        CustomReportSubscription.create_subscription(
            bk_tenant_id=TENANT, bk_biz_id=2, data_id_configs=[({"bk_data_id": 1001}, "json")], bk_host_ids=[101]
        )
        LogSubscriptionConfig.deploy(
            TENANT, SimpleNamespace(bk_biz_id=2, log_group_name="log_group"), {"log_data_id": 1}, [101]
        )
        PingServerSubscriptionConfig.create_subscription(
            TENANT,
            0,
            {101: [{"target_ip": "127.0.0.1", "target_cloud_id": 0}]},
            [{"bk_host_id": 101, "bk_biz_id": 2, "ip": "127.0.0.1", "ipv6": ""}],
            "bk-collector",
        )

    scenes = set(BkCollectorDeployPolicy.objects.values_list("scene", flat=True))
    assert scenes == {
        BkCollectorDeployScene.APM_PLATFORM,
        BkCollectorDeployScene.APM_APPLICATION,
        BkCollectorDeployScene.CUSTOM_REPORT,
        BkCollectorDeployScene.CUSTOM_LOG,
        BkCollectorDeployScene.PING_SERVER,
    }


def _policy(scene, resource_key, deploy_policy_id, last_workflow_id=""):
    return BkCollectorDeployPolicy.objects.create(
        bk_tenant_id=TENANT,
        scene=scene,
        resource_key=resource_key,
        policy_name=BkCollectorDeployPolicy.build_policy_name(scene, resource_key),
        deploy_policy_id=deploy_policy_id,
        last_workflow_id=last_workflow_id,
    )


@pytest.fixture
def refresh_entries():
    with ExitStack() as stack:
        yield {
            "list_tenant": stack.enter_context(
                mock.patch.object(api.bk_login, "list_tenant", return_value=[{"id": TENANT}])
            ),
            "platform": stack.enter_context(mock.patch.object(PlatformConfig, "refresh")),
            "custom_report": stack.enter_context(
                mock.patch.object(CustomReportSubscription, "refresh_collector_custom_conf")
            ),
            "ping_server": stack.enter_context(mock.patch("metadata.task.ping_server.refresh_ping_conf")),
        }


def test_command_refresh_runs_scenes_and_only_executes_unchanged_policies(nodeman_v3, refresh_entries):
    from django.core.management import call_command

    unchanged = _policy(BkCollectorDeployScene.APM_APPLICATION, "2-app", 1, "wf-a")
    refreshed = _policy(BkCollectorDeployScene.APM_PLATFORM, "platform", 2, "wf-b")
    _policy(BkCollectorDeployScene.CUSTOM_LOG, "2-log", None)  # 历史失败留下的空记录

    def refresh_platform(bk_tenant_id):
        BkCollectorDeployPolicy.objects.filter(id=refreshed.id).update(last_workflow_id="wf-b2")

    def refresh_custom_report(**kwargs):
        _policy(BkCollectorDeployScene.CUSTOM_REPORT, "0-1001", 3, "wf-c")

    refresh_entries["platform"].side_effect = refresh_platform
    refresh_entries["custom_report"].side_effect = refresh_custom_report

    call_command("execute_bk_collector_deploy_policies", "--refresh")

    refresh_entries["platform"].assert_called_once_with(TENANT)
    refresh_entries["custom_report"].assert_called_once_with(bk_tenant_id=TENANT, deploy_targets=("node_man",))
    refresh_entries["ping_server"].assert_called_once_with("bk-collector", bk_tenant_id=None)
    # 刷新中已执行（refreshed）和新建（custom_report）的策略不重复执行，只补执行未变化的策略
    nodeman_v3["execute_deploy_policy"].assert_called_once_with(bk_tenant_id=TENANT, deploy_policy_id=1)
    unchanged.refresh_from_db()
    assert unchanged.last_workflow_id == "wf-1"


def test_command_refresh_scene_filter(nodeman_v3, refresh_entries):
    from django.core.management import call_command

    call_command("execute_bk_collector_deploy_policies", "--refresh", "--scene", BkCollectorDeployScene.CUSTOM_REPORT)

    refresh_entries["custom_report"].assert_called_once()
    refresh_entries["platform"].assert_not_called()
    refresh_entries["ping_server"].assert_not_called()


def test_command_without_refresh_only_executes_existing(nodeman_v3, refresh_entries):
    from django.core.management import call_command

    _policy(BkCollectorDeployScene.APM_PLATFORM, "platform", 2, "wf-b")

    call_command("execute_bk_collector_deploy_policies")

    refresh_entries["platform"].assert_not_called()
    nodeman_v3["execute_deploy_policy"].assert_called_once_with(bk_tenant_id=TENANT, deploy_policy_id=2)


def test_command_refuses_when_v3_disabled(nodeman_v3):
    from django.core.management import CommandError, call_command

    with override_settings(ENABLE_BK_COLLECTOR_NODEMAN_V3=False), pytest.raises(CommandError):
        call_command("execute_bk_collector_deploy_policies", "--refresh")
    nodeman_v3["execute_deploy_policy"].assert_not_called()


def test_command_refresh_ping_server_only_touches_given_tenant(nodeman_v3):
    """指定租户 A 刷新 PingServer 时，不能创建、更新或撤回租户 B 的策略"""
    from django.core.management import call_command

    from api.cmdb.define import Host
    from metadata.task.ping_server import refresh_ping_conf

    def host(bk_host_id, bk_biz_id, ip):
        return Host({"bk_host_id": bk_host_id, "bk_biz_id": bk_biz_id, "bk_cloud_id": 0, "bk_host_innerip": ip})

    tenant_hosts = {"tenant_a": [host(1, 2, "127.0.0.1")], "tenant_b": [host(2, 3, "127.0.0.2")]}
    # 租户 B 已有一条策略，刷新 A 时不能被改动
    tenant_b_policy = BkCollectorDeployPolicy.objects.create(
        bk_tenant_id="tenant_b",
        scene=BkCollectorDeployScene.PING_SERVER,
        resource_key="biz3-cloud0-host2",
        policy_name="bkmonitor-collector-ping_server-biz3-cloud0-host2",
        deploy_policy_id=88,
        last_workflow_id="wf-b",
    )

    def refresh_by_cloud(bk_tenant_id, bk_cloud_id, plugin_name, target_ips):
        # 模拟按云区域下发：为传入租户写一条策略
        BkCollectorDeployPolicy.objects.update_or_create(
            bk_tenant_id=bk_tenant_id,
            scene=BkCollectorDeployScene.PING_SERVER,
            resource_key=f"cloud{bk_cloud_id}-{bk_tenant_id}",
            defaults={"policy_name": f"ping-{bk_tenant_id}", "deploy_policy_id": 99, "last_workflow_id": "wf-new"},
        )

    with (
        override_settings(ENABLE_PING_ALARM=True),
        mock.patch.object(
            api.bk_login, "list_tenant", return_value=[{"id": "tenant_a"}, {"id": "tenant_b"}]
        ) as list_tenant,
        mock.patch(
            "alarm_backends.core.cache.cmdb.host.HostManager.all",
            side_effect=lambda bk_tenant_id: tenant_hosts[bk_tenant_id],
        ) as all_hosts,
        mock.patch("metadata.task.ping_server._refresh_ping_conf_by_cloud_id", side_effect=refresh_by_cloud),
    ):
        call_command(
            "execute_bk_collector_deploy_policies",
            "--refresh",
            "--scene",
            BkCollectorDeployScene.PING_SERVER,
            "--bk_tenant_id",
            "tenant_a",
        )

        list_tenant.assert_not_called()
        assert [c.kwargs["bk_tenant_id"] for c in all_hosts.call_args_list] == ["tenant_a"]
        assert set(BkCollectorDeployPolicy.objects.values_list("bk_tenant_id", flat=True)) == {"tenant_a", "tenant_b"}
        assert BkCollectorDeployPolicy.objects.filter(bk_tenant_id="tenant_b").count() == 1
        tenant_b_policy.refresh_from_db()
        assert tenant_b_policy.last_workflow_id == "wf-b"
        nodeman_v3["execute_deploy_policy"].assert_not_called()

        # 定时任务不传租户，仍遍历全部租户
        all_hosts.reset_mock()
        refresh_ping_conf("bk-collector")
        assert [c.kwargs["bk_tenant_id"] for c in all_hosts.call_args_list] == ["tenant_a", "tenant_b"]


def test_execute_in_batches_waits_between_batches(nodeman_v3):
    policies = [_policy(BkCollectorDeployScene.CUSTOM_REPORT, f"0-{i}", 100 + i) for i in range(5)]
    waits = []

    with mock.patch("metadata.models.bk_collector.time.sleep") as sleep:
        with BkCollectorDeployPolicy.execute_in_batches(2, 5, on_wait=lambda n, s: waits.append((n, s))):
            for policy in policies:
                policy.execute()
        # 上下文外不分批
        policies[0].execute()

    # 5 条分 3 批：第 3、5 条执行前各等待一次，最后一批之后不再等待
    assert sleep.call_args_list == [mock.call(5), mock.call(5)]
    assert waits == [(2, 5), (4, 5)]
    assert nodeman_v3["execute_deploy_policy"].call_count == 6


def test_execute_in_batches_disabled_when_batch_size_zero(nodeman_v3):
    policies = [_policy(BkCollectorDeployScene.CUSTOM_REPORT, f"0-{i}", 100 + i) for i in range(3)]

    with mock.patch("metadata.models.bk_collector.time.sleep") as sleep:
        with BkCollectorDeployPolicy.execute_in_batches(0, 5):
            for policy in policies:
                policy.execute()

    sleep.assert_not_called()
    assert nodeman_v3["execute_deploy_policy"].call_count == 3


def test_command_batches_refresh_and_final_executions(nodeman_v3, refresh_entries):
    from django.core.management import call_command

    for i in range(3):
        _policy(BkCollectorDeployScene.APM_APPLICATION, f"2-app{i}", 10 + i, f"wf-{i}")

    def refresh_platform(bk_tenant_id):
        # 刷新中新建策略的立即执行同样计入分批
        _deploy()

    refresh_entries["platform"].side_effect = refresh_platform

    with mock.patch("metadata.models.bk_collector.time.sleep") as sleep:
        call_command("execute_bk_collector_deploy_policies", "--refresh", "--batch_size", "2", "--batch_interval", "3")

    # 刷新中新建 1 条 + 补执行未变化的 3 条，共 4 次执行分 2 批
    assert nodeman_v3["execute_deploy_policy"].call_count == 4
    assert sleep.call_args_list == [mock.call(3)]


def test_command_rejects_negative_batch_args(nodeman_v3):
    from django.core.management import CommandError, call_command

    with pytest.raises(CommandError):
        call_command("execute_bk_collector_deploy_policies", "--batch_size", "-1")
    nodeman_v3["execute_deploy_policy"].assert_not_called()
