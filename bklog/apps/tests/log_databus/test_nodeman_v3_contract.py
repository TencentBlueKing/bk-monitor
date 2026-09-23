"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.log_databus.constants import LogPluginInfo, TargetNodeTypeEnum
from apps.log_databus.nodeman_v3.constants import (
    RESOURCE_TYPE_COLLECTOR_CONFIG,
    SPEC_TYPE_SPECIFY_PLUGIN,
    SPEC_TYPE_SPECIFY_PLUGIN_SUB_CONFIG_TEMPLATE,
)
from apps.log_databus.nodeman_v3.exceptions import (
    NodeManV3APIError,
    NodeManV3CapabilityBlocked,
    NodeManV3UnknownResultError,
)
from apps.log_databus.nodeman_v3.identity import build_policy_name, build_resource_key, build_sub_config_name
from apps.log_databus.nodeman_v3.mode import is_nodeman_v3_only, should_use_nodeman_v3
from apps.log_databus.nodeman_v3.policy import (
    SubscriptionStepsTranslator,
    build_plugin_install_payload,
    build_policy_payload,
    calculate_fingerprint,
    merge_scopes,
)
from apps.log_databus.nodeman_v3.models import NodeManV3Binding, NodeManV3SubConfigTarget
from apps.log_databus.nodeman_v3.scopes import build_scopes
from apps.log_databus.nodeman_v3.versions import resolve_plugin_version
from apps.log_search.constants import CollectorScenarioEnum

PLUGIN_NAME = LogPluginInfo.NAME


def build_steps(dataid=1234, paths=None):
    """构造与 V2 订阅步骤同构的输入"""
    return [
        {
            "id": f"main:{PLUGIN_NAME}",
            "type": "PLUGIN",
            "config": {
                "job_type": "MAIN_INSTALL_PLUGIN",
                "plugin_name": PLUGIN_NAME,
                "plugin_version": "latest",
                "config_templates": [{"name": f"{PLUGIN_NAME}.conf", "version": "latest", "is_main": True}],
            },
            "params": {"context": {}},
        },
        {
            "id": PLUGIN_NAME,
            "type": "PLUGIN",
            "config": {
                "plugin_name": PLUGIN_NAME,
                "plugin_version": "latest",
                "config_templates": [{"name": f"{PLUGIN_NAME}.conf", "version": "latest"}],
            },
            "params": {"context": {"dataid": dataid, "local": [{"paths": paths or ["/var/log/a.log"]}]}},
        },
    ]


class SubConfigIdentityTest(TestCase):
    """同机多采集项的子配置隔离"""

    def test_sub_config_name_follows_nodeman_naming_rule(self):
        # NodeMan 用 <模板名去扩展名>_deploy_<策略ID><扩展名> 生成落地文件名
        self.assertEqual(
            build_sub_config_name(f"{PLUGIN_NAME}.conf", 1001),
            f"{PLUGIN_NAME}_deploy_1001.conf",
        )

    def test_sub_config_names_differ_across_collector_configs_on_same_host(self):
        # 两个采集项各自一个部署策略，落地文件名必须不同，否则后下发的会覆盖前一个，
        # 且停用其中一个会连带删掉另一个
        first = build_sub_config_name(f"{PLUGIN_NAME}.conf", 1001)
        second = build_sub_config_name(f"{PLUGIN_NAME}.conf", 1002)
        self.assertNotEqual(first, second)

    def test_sub_config_name_keeps_template_extension(self):
        self.assertTrue(build_sub_config_name(f"{PLUGIN_NAME}.conf", 7).endswith(".conf"))

    def test_policy_name_is_derivable_from_collector_config_id(self):
        # 节点管理没有 deploy_policy 删除接口，binding 丢失后要靠策略名找回既有策略
        self.assertEqual(build_policy_name(42), "bklog-collector-42")


class ScopeTranslationTest(TestCase):
    """采集目标到 V3 部署范围的映射"""

    def test_instance_scope_uses_host_id(self):
        scopes = build_scopes(2, TargetNodeTypeEnum.INSTANCE.value, [{"bk_host_id": 11}, {"bk_host_id": 12}])
        self.assertEqual(scopes[0]["type"], "instance")
        self.assertEqual(scopes[0]["scope"]["instance_ids"], [11, 12])
        self.assertEqual(scopes[0]["scope"]["granularity"], "host")

    def test_instance_scope_without_host_id_fails_closed(self):
        # 只有 ip + cloud_id 的历史目标不能静默丢弃，否则表现为「下发成功但少了几台机器」
        with self.assertRaises(NodeManV3CapabilityBlocked):
            build_scopes(2, TargetNodeTypeEnum.INSTANCE.value, [{"ip": "127.0.0.1", "bk_cloud_id": 0}])

    def test_topo_scope_maps_to_paths(self):
        scopes = build_scopes(2, TargetNodeTypeEnum.TOPO.value, [{"bk_obj_id": "module", "bk_inst_id": 33}])
        self.assertEqual(scopes[0]["scope"]["paths"], [{"topo_obj_id": "module", "topo_inst_id": 33}])

    def test_template_scopes(self):
        service = build_scopes(2, TargetNodeTypeEnum.SERVICE_TEMPLATE.value, [{"bk_inst_id": 5}])
        self.assertEqual(service[0]["scope"]["service_template_ids"], [5])

        set_template = build_scopes(2, TargetNodeTypeEnum.SET_TEMPLATE.value, [{"bk_inst_id": 6}])
        self.assertEqual(set_template[0]["scope"]["set_template_ids"], [6])

    def test_dynamic_group_ids_stay_string(self):
        scopes = build_scopes(2, TargetNodeTypeEnum.DYNAMIC_GROUP.value, [{"bk_inst_id": "abc123"}])
        self.assertEqual(scopes[0]["scope"]["dynamic_group_ids"], ["abc123"])

    def test_empty_target_nodes_produce_empty_scopes(self):
        # 停用/删除采集项就是把范围清空，交给收敛器反删子配置
        self.assertEqual(build_scopes(2, TargetNodeTypeEnum.TOPO.value, []), [])


class SpecTranslationTest(TestCase):
    """订阅步骤到部署规范的映射"""

    def test_collector_policy_carries_only_sub_config_template_spec(self):
        specs = SubscriptionStepsTranslator().build_specs(build_steps())
        self.assertEqual([spec["type"] for spec in specs], [SPEC_TYPE_SPECIFY_PLUGIN_SUB_CONFIG_TEMPLATE])

    def test_collector_policy_never_carries_specify_plugin(self):
        # 回归用例。采集项策略一旦带上 specify_plugin，策略发现就会按插件名把同插件的所有
        # enabled 策略拉进同一个冲突闭包，冲突消解再按创建时间把后建采集项的共享主机整体剔除，
        # 被剔除的主机随后命中「不在范围内」分支，把该采集项已经生效的子配置删掉。
        # 净效果是同机第二个采集项静默失效，而 execute 照常返回父 workflow_id。
        # 取证见 docs/节点管理V3适配/deploypolicy冲突消解_同机多采集项互斥_取证.md
        specs = SubscriptionStepsTranslator().build_specs(build_steps())
        self.assertNotIn(SPEC_TYPE_SPECIFY_PLUGIN, [spec["type"] for spec in specs])

    def test_main_config_template_is_excluded_from_sub_config_spec(self):
        # 把主配置模板混进子配置会让节点管理重写主配置，影响同机其它采集项
        specs = SubscriptionStepsTranslator().build_specs(build_steps())
        details = specs[0]["param"]["config_files_detail"]
        self.assertEqual([detail["template_name"] for detail in details], [f"{PLUGIN_NAME}.conf"])
        self.assertTrue(all(detail["is_main_config"] is False for detail in details))

    def test_custom_config_context_passes_through_unchanged(self):
        # Jinja2 渲染时 custom_config_context 直接合并到模板顶层，与 V2 params.context 一致，
        # 原样透传才能保证六种场景的出数口径不变
        steps = build_steps(dataid=9527, paths=["/data/log/x.log"])
        specs = SubscriptionStepsTranslator().build_specs(steps)
        context = specs[0]["param"]["custom_config_context"]
        self.assertEqual(context["dataid"], 9527)
        self.assertEqual(context["local"], [{"paths": ["/data/log/x.log"]}])

    def test_missing_dataid_fails_closed(self):
        steps = build_steps()
        steps[1]["params"]["context"].pop("dataid")
        with self.assertRaises(NodeManV3CapabilityBlocked):
            SubscriptionStepsTranslator().build_specs(steps)

    def test_single_step_scenario_is_supported(self):
        # syslog 等场景只有一个 PLUGIN 步骤
        steps = [build_steps()[1]]
        specs = SubscriptionStepsTranslator().build_specs(steps)
        self.assertEqual([spec["type"] for spec in specs], [SPEC_TYPE_SPECIFY_PLUGIN_SUB_CONFIG_TEMPLATE])


class PluginInstallPolicyTest(TestCase):
    """业务级采集器安装策略"""

    def test_install_policy_carries_only_specify_plugin(self):
        payload = build_plugin_install_payload(
            bk_biz_id=2, plugin_version="1.2.3", scopes=build_scopes(2, TargetNodeTypeEnum.TOPO.value, [])
        )
        self.assertEqual([spec["type"] for spec in payload["specs"]], [SPEC_TYPE_SPECIFY_PLUGIN])
        self.assertEqual(payload["specs"][0]["param"]["plugin_name"], PLUGIN_NAME)
        self.assertEqual(payload["specs"][0]["param"]["version"], "1.2.3")

    def test_install_policy_name_is_per_biz(self):
        # 全环境一条策略会让任一业务的目标变更改写其它业务的期望态，出问题也无法按业务定位
        first = build_plugin_install_payload(bk_biz_id=2, plugin_version="1.2.3", scopes=[])
        second = build_plugin_install_payload(bk_biz_id=3, plugin_version="1.2.3", scopes=[])
        self.assertNotEqual(first["name"], second["name"])

    def test_merge_scopes_dedups_identical_entries(self):
        # 同业务多个采集项常常指向同一个拓扑节点，不去重会让安装策略范围随采集项数量线性膨胀
        topo = build_scopes(2, TargetNodeTypeEnum.TOPO.value, [{"bk_obj_id": "biz", "bk_inst_id": 2}])
        merged = merge_scopes([topo, topo])
        self.assertEqual(merged, topo)

    def test_merge_scopes_unions_same_type_into_one_entry(self):
        # 条目数不能随采集项数量线性增长，否则一个业务几百个采集项就是几百条 scope，
        # 每轮收敛都要让节点管理把同一个范围重算几百遍
        first = build_scopes(2, TargetNodeTypeEnum.INSTANCE.value, [{"bk_host_id": 1}])
        second = build_scopes(2, TargetNodeTypeEnum.INSTANCE.value, [{"bk_host_id": 2}])
        merged = merge_scopes([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["scope"]["instance_ids"], [1, 2])

    def test_merge_scopes_keeps_different_types_separate(self):
        instance = build_scopes(2, TargetNodeTypeEnum.INSTANCE.value, [{"bk_host_id": 1}])
        topo = build_scopes(2, TargetNodeTypeEnum.TOPO.value, [{"bk_obj_id": "biz", "bk_inst_id": 2}])
        merged = merge_scopes([instance, topo])
        self.assertEqual(len(merged), 2)

    def test_merge_scopes_dedups_topo_paths(self):
        topo = build_scopes(2, TargetNodeTypeEnum.TOPO.value, [{"bk_obj_id": "biz", "bk_inst_id": 2}])
        merged = merge_scopes([topo, topo])
        self.assertEqual(merged[0]["scope"]["paths"], [{"topo_obj_id": "biz", "topo_inst_id": 2}])

    def test_merge_scopes_does_not_mutate_inputs(self):
        # 入参是各 binding 的 desired_scopes 快照，被就地改写会污染下一轮的并集基线
        first = build_scopes(2, TargetNodeTypeEnum.INSTANCE.value, [{"bk_host_id": 1}])
        second = build_scopes(2, TargetNodeTypeEnum.INSTANCE.value, [{"bk_host_id": 2}])
        merge_scopes([first, second])
        self.assertEqual(first[0]["scope"]["instance_ids"], [1])

    def test_merge_scopes_tolerates_missing_snapshot(self):
        # binding.desired_scopes 在首次收敛前是 None，不能让并集计算炸掉
        self.assertEqual(merge_scopes([None, []]), [])


class PolicyPayloadTest(TestCase):
    def test_policy_stays_enabled_even_when_scopes_are_empty(self):
        # 被 disable 的策略不再参与收敛，已下发的子配置会残留在主机上继续采集，
        # 所以停用必须用「空范围 + 保持启用」表达
        payload = build_policy_payload(
            collector_config_id=1,
            bk_biz_id=2,
            target_node_type=TargetNodeTypeEnum.TOPO.value,
            target_nodes=[],
            steps=build_steps(),
        )
        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["scopes"], [])

    def test_fingerprint_ignores_description_changes(self):
        kwargs = dict(
            collector_config_id=1,
            bk_biz_id=2,
            target_node_type=TargetNodeTypeEnum.TOPO.value,
            target_nodes=[{"bk_obj_id": "biz", "bk_inst_id": 2}],
            steps=build_steps(),
        )
        first = build_policy_payload(description="before", **kwargs)
        second = build_policy_payload(description="after", **kwargs)
        self.assertEqual(calculate_fingerprint(first), calculate_fingerprint(second))

    def test_fingerprint_changes_with_target_nodes(self):
        kwargs = dict(
            collector_config_id=1,
            bk_biz_id=2,
            target_node_type=TargetNodeTypeEnum.INSTANCE.value,
            steps=build_steps(),
        )
        first = build_policy_payload(target_nodes=[{"bk_host_id": 1}], **kwargs)
        second = build_policy_payload(target_nodes=[{"bk_host_id": 2}], **kwargs)
        self.assertNotEqual(calculate_fingerprint(first), calculate_fingerprint(second))

    def test_fingerprint_changes_with_collect_params(self):
        kwargs = dict(
            collector_config_id=1,
            bk_biz_id=2,
            target_node_type=TargetNodeTypeEnum.INSTANCE.value,
            target_nodes=[{"bk_host_id": 1}],
        )
        first = build_policy_payload(steps=build_steps(paths=["/a.log"]), **kwargs)
        second = build_policy_payload(steps=build_steps(paths=["/b.log"]), **kwargs)
        self.assertNotEqual(calculate_fingerprint(first), calculate_fingerprint(second))


class PluginVersionResolveTest(TestCase):
    class FakeClient:
        def __init__(self, items):
            self.items = items

        def list_release_plugin_brief(self, payload):
            self.payload = payload
            return {"items": self.items}

    def test_latest_is_resolved_to_default_release_version(self):
        # V3 的 specify_plugin.version 不认识 latest，透传会匹配不到插件包
        client = self.FakeClient([{"os_type": "linux", "cpu_arch": "amd64", "version": "3.1.0"}])
        self.assertEqual(resolve_plugin_version(client, PLUGIN_NAME, "latest"), "3.1.0")

    def test_explicit_version_is_kept(self):
        client = self.FakeClient([])
        self.assertEqual(resolve_plugin_version(client, PLUGIN_NAME, "2.0.0"), "2.0.0")

    def test_no_default_release_fails_closed(self):
        with self.assertRaises(NodeManV3CapabilityBlocked):
            resolve_plugin_version(self.FakeClient([]), PLUGIN_NAME, "latest")

    def test_inconsistent_platform_versions_fail_closed(self):
        # 挑错版本会把一批主机的采集器升级或降级，必须由人显式决定
        client = self.FakeClient(
            [
                {"os_type": "linux", "cpu_arch": "amd64", "version": "3.1.0"},
                {"os_type": "windows", "cpu_arch": "amd64", "version": "3.0.9"},
            ]
        )
        with self.assertRaises(NodeManV3CapabilityBlocked):
            resolve_plugin_version(client, PLUGIN_NAME, "latest")


class ClientEnvelopeTest(TestCase):
    """V3 返回体没有蓝鲸标准 result 字段，成功判定必须自己做"""

    def _client(self, envelope=None, exc=None, operation_id="op-1"):
        from apps.log_databus.nodeman_v3 import client as client_module

        def fake_api(payload, raw=False, bk_tenant_id=""):
            if exc:
                raise exc
            return envelope

        instance = client_module.NodeManV3Client(
            context=client_module.NodeManV3RequestContext(bk_biz_id=2, bk_tenant_id="system", operation_id=operation_id)
        )
        return instance, fake_api

    def test_business_error_code_is_not_treated_as_success(self):
        # DataAPI 对缺少 result 的返回默认判成功（apps/api/base.py:413-415），
        # 若不自己判 code，V3 的失败会被当成成功
        client, api = self._client({"code": 1302403, "message": "permission denied", "data": None})
        with self.assertRaises(NodeManV3APIError):
            client._call(api, "plugin/list_config_files", {}, write=False)

    def test_write_failure_is_reported_as_unknown_result(self):
        # 写请求失败无法区分「没到服务端」与「已生效但响应丢了」，必须禁止自动重放
        client, api = self._client({"code": 500, "message": "internal error"})
        with self.assertRaises(NodeManV3UnknownResultError):
            client._call(api, "deploy_policy/create", {}, write=True)

    def test_transport_failure_on_write_is_unknown_result(self):
        client, api = self._client(exc=OSError("connection reset"))
        with self.assertRaises(NodeManV3UnknownResultError):
            client._call(api, "deploy_policy/execute", {}, write=True)

    def test_transport_failure_on_read_is_transport_error(self):
        from apps.log_databus.nodeman_v3.exceptions import NodeManV3TransportError

        client, api = self._client(exc=OSError("connection reset"))
        with self.assertRaises(NodeManV3TransportError):
            client._call(api, "process/list", {}, write=False)

    def test_write_without_operation_id_is_rejected(self):
        # 没有 operation_id 就无法把本地记录与节点管理侧的动作对上，写结果未知时无从追查
        client, api = self._client({"code": 0, "data": {}}, operation_id="")
        with self.assertRaises(ValueError):
            client._call(api, "deploy_policy/create", {}, write=True)

    def test_success_returns_data_field(self):
        client, api = self._client({"code": 0, "message": "ok", "data": {"deploy_policy_id": 1001}})
        self.assertEqual(client._call(api, "deploy_policy/create", {}, write=True), {"deploy_policy_id": 1001})

    @override_settings(
        BKNODEMAN_V3_API_BASE_URL="",
        PAAS_API_HOST="https://bkapi.example.com",
        ENVIRONMENT="prod",
    )
    def test_default_v3_gateway_uses_bk_nodemgr(self):
        from apps.api.modules.bk_node_v3 import _BKNodeV3Api

        api = _BKNodeV3Api()
        self.assertEqual(
            api.list_deploy_policy_workflows.url,
            "https://bkapi.example.com/api/bk-nodemgr/prod/api/v3/deploy_policy/workflow/list",
        )


class IntegrationModeTest(TestCase):
    @override_settings(NODEMAN_INTEGRATION_MODE="v2")
    def test_default_mode_is_v2(self):
        self.assertFalse(is_nodeman_v3_only())

    @override_settings(NODEMAN_INTEGRATION_MODE="v3_fresh")
    def test_v3_fresh_mode(self):
        self.assertTrue(is_nodeman_v3_only())

    @override_settings(NODEMAN_INTEGRATION_MODE="hybrid")
    def test_hybrid_mode_is_rejected(self):
        # 混合模式会让 V3 的异常路径悄悄退回 V2，产生双写与状态分裂
        from django.core.exceptions import ImproperlyConfigured

        with self.assertRaises(ImproperlyConfigured):
            is_nodeman_v3_only()


@override_settings(NODEMAN_INTEGRATION_MODE="v3_fresh")
class GrayRolloutOwnershipTest(TestCase):
    """
    采集项级灰度归属。

    存量环境装满了带 subscription_id 的 V2 采集项，整环境打开 v3_fresh 会把它们的状态页、
    启停、删除全部指向 V3，而它们没有 V3 binding —— 表现就是老采集项集体失能。所以归属必须
    按采集项判定。

    这与被否决的 hybrid 模式的边界：归属只取自采集项的**静态身份**，不取自调用结果。
    归 V3 的采集项遇到 V3 失败仍然失败关闭，不回退 V2。
    """

    def _config(self, collector_config_id=9001, bk_biz_id=2, subscription_id=None):
        return SimpleNamespace(
            collector_config_id=collector_config_id,
            bk_biz_id=bk_biz_id,
            subscription_id=subscription_id,
        )

    @override_settings(NODEMAN_INTEGRATION_MODE="v2")
    def test_v2_mode_never_uses_v3(self):
        self.assertFalse(should_use_nodeman_v3(self._config()))

    def test_new_collector_uses_v3_when_whitelist_empty(self):
        # 白名单留空等价于原来 v3_fresh 的全量语义，不改变全新环境的行为
        self.assertTrue(should_use_nodeman_v3(self._config()))

    def test_existing_v2_collector_stays_on_v2(self):
        # 判据是 subscription_id：V3 下发的采集项这个字段恒为空（IntegerField 存不下 workflow_id）
        self.assertFalse(should_use_nodeman_v3(self._config(subscription_id=12345)))

    @override_settings(NODEMAN_V3_COLLECTOR_WHITELIST="9001,9002")
    def test_collector_whitelist_selects_targets(self):
        self.assertTrue(should_use_nodeman_v3(self._config(collector_config_id=9002)))
        self.assertFalse(should_use_nodeman_v3(self._config(collector_config_id=9003)))

    @override_settings(NODEMAN_V3_BIZ_WHITELIST="7")
    def test_biz_whitelist_selects_targets(self):
        self.assertTrue(should_use_nodeman_v3(self._config(bk_biz_id=7)))
        self.assertFalse(should_use_nodeman_v3(self._config(bk_biz_id=2)))

    @override_settings(NODEMAN_V3_COLLECTOR_WHITELIST="not-an-id, 9001 ,")
    def test_malformed_whitelist_entry_does_not_void_the_rest(self):
        # 一个笔误不能把整张白名单废掉，否则灰度会在无人察觉时退回全量
        self.assertTrue(should_use_nodeman_v3(self._config(collector_config_id=9001)))
        self.assertFalse(should_use_nodeman_v3(self._config(collector_config_id=9003)))

    @override_settings(NODEMAN_V3_COLLECTOR_WHITELIST="9999")
    def test_existing_binding_outranks_whitelist_shrink(self):
        # 白名单收窄不能把已经通过 V3 下发过的采集项踢回 V2：主机上那份 V3 子配置会失去控制面，
        # 既不会被更新也不会被删除，变成永久残留。归属只能前进
        from apps.log_databus.nodeman_v3.constants import RESOURCE_TYPE_COLLECTOR_CONFIG
        from apps.log_databus.nodeman_v3.models import NodeManV3Binding

        config = self._config(collector_config_id=9001)
        NodeManV3Binding.objects.create(
            resource_type=RESOURCE_TYPE_COLLECTOR_CONFIG,
            resource_key=build_resource_key(9001),
            bk_biz_id=2,
            bk_tenant_id="system",
            collector_config_id=9001,
            policy_name=build_policy_name(9001),
        )
        self.assertTrue(should_use_nodeman_v3(config))

    def test_v2_owned_collector_takes_v2_path_not_v3_installer(self):
        # 反向门禁：BKL-5 的 V2OutboundZeroGateTest 证明「V3 归属不出 V2」，
        # 这条证明另一半 —— 灰度外的采集项在 v3_fresh 环境下仍然走 V2，且不触碰 V3 installer
        from apps.api import NodeApi
        from apps.log_databus.handlers.collector.host import HostCollectorHandler

        handler = HostCollectorHandler.__new__(HostCollectorHandler)
        handler.data = self._config(subscription_id=12345)

        def explode(_self):
            raise AssertionError("灰度外的采集项不应触碰 NodeMan V3 installer")

        with patch.object(HostCollectorHandler, "nodeman_v3_installer", property(explode)):
            with patch.object(NodeApi, "switch_subscription") as switch:
                handler._pre_start()

        self.assertFalse(handler.use_nodeman_v3)
        switch.assert_called_once()
        self.assertEqual(switch.call_args[0][0]["action"], "enable")


class FakeNodeManV3Client:
    """记录所有出站写调用，用于断言收敛行为"""

    def __init__(self):
        self.calls = []
        self.tenant_id = "system"
        self.next_policy_id = 1001
        # deploy_policy_id -> 策略名，用于把 execute 调用归到采集项策略还是安装策略
        self.policy_names = {}

    def list_release_plugin_brief(self, payload):
        return {"items": [{"os_type": "linux", "cpu_arch": "amd64", "version": "3.1.0"}]}

    def list_deploy_policies(self, payload):
        self.calls.append(("list", payload))
        return {"items": []}

    def create_deploy_policy(self, payload):
        self.calls.append(("create", payload))
        policy_id = self.next_policy_id
        self.next_policy_id += 1
        self.policy_names[policy_id] = payload["name"]
        return {"deploy_policy_id": policy_id}

    def update_deploy_policy(self, payload):
        self.calls.append(("update", payload))
        policy = payload["deploy_policies"][0]
        self.policy_names[policy["deploy_policy_id"]] = policy["meta"]["name"]
        return {}

    def execute_deploy_policy(self, deploy_policy_id):
        self.calls.append(("execute", deploy_policy_id))
        return {"workflow_id": f"parent-workflow-{deploy_policy_id}-{len(self.calls)}"}

    def policy_name_of(self, call_name, payload):
        if call_name == "create":
            return payload["name"]
        if call_name == "update":
            return payload["deploy_policies"][0]["meta"]["name"]
        if call_name == "execute":
            return self.policy_names.get(payload, "")
        return ""

    def policy_kind_of(self, call_name, payload):
        return "plugin" if self.policy_name_of(call_name, payload).startswith("bklog-plugin-") else "collector"

    def write_calls(self, kind=None):
        """kind 为 None 时返回全部写调用，否则只返回 collector / plugin 一类"""
        return [
            name
            for name, payload in self.calls
            if name in ("create", "update", "execute") and (kind is None or self.policy_kind_of(name, payload) == kind)
        ]

    def payloads_of(self, call_name, kind=None):
        return [
            payload
            for name, payload in self.calls
            if name == call_name and (kind is None or self.policy_kind_of(name, payload) == kind)
        ]


@override_settings(NODEMAN_INTEGRATION_MODE="v3_fresh")
class ReconcileBehaviourTest(TestCase):
    def setUp(self):
        from types import SimpleNamespace

        self.collector_config = SimpleNamespace(
            collector_config_id=8001,
            bk_biz_id=2,
            target_node_type=TargetNodeTypeEnum.INSTANCE.value,
            target_nodes=[{"bk_host_id": 11}],
            description="unit test",
        )
        self.client = FakeNodeManV3Client()
        patcher = patch("apps.log_databus.nodeman_v3.reconciler.get_client", side_effect=lambda *a, **kw: self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _reconciler(self):
        from apps.log_databus.nodeman_v3.reconciler import CollectorPolicyReconciler

        return CollectorPolicyReconciler(self.collector_config)

    def test_first_reconcile_creates_policy_then_executes(self):
        from apps.log_databus.nodeman_v3.models import NodeManV3Workflow

        operation = self._reconciler().reconcile(build_steps())
        self.assertIsNotNone(operation)
        self.assertEqual(self.client.write_calls("collector"), ["create", "execute"])
        workflow = NodeManV3Workflow.objects.get(operation=operation)
        self.assertTrue(workflow.parent_workflow_id.startswith("parent-workflow-"))
        self.assertEqual(workflow.trigger_id, "")

    def test_execute_without_parent_workflow_id_fails_closed(self):
        original = self.client.execute_deploy_policy

        def missing_parent_workflow(deploy_policy_id):
            if self.client.policy_names.get(deploy_policy_id, "").startswith("bklog-plugin-"):
                return original(deploy_policy_id)
            return {"trigger_id": "legacy-trigger"}

        self.client.execute_deploy_policy = missing_parent_workflow
        with self.assertRaises(NodeManV3UnknownResultError):
            self._reconciler().reconcile(build_steps())

    def test_install_policy_is_reconciled_before_collector_policy(self):
        # 节点管理只对插件进程已 running 的主机下发子配置，安装策略必须先执行；
        # 顺序颠倒会让首次下发整轮落空，只能等下一次定时收敛补上
        self._reconciler().reconcile(build_steps())
        kinds = [
            self.client.policy_kind_of(name, payload)
            for name, payload in self.client.calls
            if name in ("create", "update", "execute")
        ]
        self.assertEqual(kinds, ["plugin", "plugin", "collector", "collector"])

    def test_created_collector_policy_carries_no_specify_plugin(self):
        # 回归用例，守的是同机多采集项互斥那条链路，见 SpecTranslationTest 里的说明
        self._reconciler().reconcile(build_steps())
        payload = self.client.payloads_of("create", "collector")[0]
        self.assertNotIn(SPEC_TYPE_SPECIFY_PLUGIN, [spec["type"] for spec in payload["specs"]])

    def test_created_install_policy_carries_specify_plugin(self):
        self._reconciler().reconcile(build_steps())
        payload = self.client.payloads_of("create", "plugin")[0]
        self.assertEqual([spec["type"] for spec in payload["specs"]], [SPEC_TYPE_SPECIFY_PLUGIN])
        self.assertEqual(payload["scopes"], self.client.payloads_of("create", "collector")[0]["scopes"])

    def test_unchanged_desired_state_is_not_redispatched(self):
        # 每次保存采集项都全量下发会造成无意义的插件 reload
        self._reconciler().reconcile(build_steps())
        before = len(self.client.write_calls())
        self.assertIsNone(self._reconciler().reconcile(build_steps()))
        self.assertEqual(len(self.client.write_calls()), before)

    def test_changed_desired_state_updates_existing_policy(self):
        self._reconciler().reconcile(build_steps())
        self.collector_config.target_nodes = [{"bk_host_id": 11}, {"bk_host_id": 12}]
        self._reconciler().reconcile(build_steps())
        # 复用已有策略而不是再建一个：重复建策略会让同机出现两份子配置，日志被采两遍
        self.assertEqual(self.client.write_calls("collector"), ["create", "execute", "update", "execute"])
        # 采集项扩了一台机器，安装策略的范围也要跟着扩，否则新机器上没有采集器进程，
        # 子配置无处落地
        self.assertEqual(self.client.write_calls("plugin"), ["create", "execute", "update", "execute"])

    def test_stop_clears_scopes_but_keeps_policy_enabled(self):
        from apps.log_databus.nodeman_v3.constants import NodeManV3OperationType

        self._reconciler().reconcile(build_steps())
        operation = self._reconciler().reconcile(
            build_steps(), target_nodes=[], operation_type=NodeManV3OperationType.REMOVE
        )
        self.assertIsNotNone(operation)

        update_payload = self.client.payloads_of("update", "collector")[-1]
        policy = update_payload["deploy_policies"][0]
        self.assertEqual(policy["scopes"], [])
        # 被 disable 的策略不再参与收敛，已下发的子配置会残留在主机上继续采集
        self.assertTrue(policy["enabled"])

    def test_repeated_stop_is_idempotent(self):
        from apps.log_databus.nodeman_v3.constants import NodeManV3OperationType

        self._reconciler().reconcile(build_steps())
        self._reconciler().reconcile(build_steps(), target_nodes=[], operation_type=NodeManV3OperationType.REMOVE)
        before = len(self.client.write_calls())
        second = self._reconciler().reconcile(
            build_steps(), target_nodes=[], operation_type=NodeManV3OperationType.REMOVE
        )
        self.assertIsNone(second)
        self.assertEqual(len(self.client.write_calls()), before)

    def test_binding_loss_recovers_policy_by_name_instead_of_creating(self):
        from apps.log_databus.nodeman_v3.models import NodeManV3Binding

        self._reconciler().reconcile(build_steps())
        binding = NodeManV3Binding.objects.get(collector_config_id=8001)
        recovered_policy_id = binding.deploy_policy_id

        # 模拟本地丢失策略 ID（例如迁移或人工清理），但节点管理侧策略仍然存在
        binding.deploy_policy_id = None
        binding.policy_fingerprint = ""
        binding.save()
        list_payloads = []

        def list_deploy_policies(payload):
            list_payloads.append(payload)
            return {"items": [{"deploy_policy_id": recovered_policy_id, "meta": {"name": binding.policy_name}}]}

        self.client.list_deploy_policies = list_deploy_policies

        self._reconciler().reconcile(build_steps(), force=True)
        # 找回后必须走 update：再 create 一条会让同机出现两份子配置，日志被采两遍
        self.assertEqual(self.client.write_calls("collector"), ["create", "execute", "update", "execute"])
        self.assertEqual(list_payloads[0]["page"], {"offset": 0, "limit": 500})
        binding.refresh_from_db()
        self.assertEqual(binding.deploy_policy_id, recovered_policy_id)

    def test_binding_recovery_fails_closed_for_duplicate_policy_names(self):
        from apps.log_databus.nodeman_v3.models import NodeManV3Binding

        self._reconciler().reconcile(build_steps())
        binding = NodeManV3Binding.objects.get(collector_config_id=8001)
        binding.deploy_policy_id = None
        binding.policy_fingerprint = ""
        binding.save()
        self.client.list_deploy_policies = lambda _payload: {
            "items": [
                {"deploy_policy_id": 4242, "meta": {"name": binding.policy_name}},
                {"deploy_policy_id": 4243, "meta": {"name": binding.policy_name}},
            ]
        }

        with self.assertRaises(NodeManV3CapabilityBlocked):
            self._reconciler().reconcile(build_steps(), force=True)

    def test_binding_recovery_follows_offset_pagination(self):
        from apps.log_databus.nodeman_v3.models import NodeManV3Binding

        self._reconciler().reconcile(build_steps())
        binding = NodeManV3Binding.objects.get(collector_config_id=8001)
        binding.deploy_policy_id = None
        binding.policy_fingerprint = ""
        binding.save()
        offsets = []

        def list_deploy_policies(payload):
            offset = payload["page"]["offset"]
            offsets.append(offset)
            if offset == 0:
                return {
                    "items": [
                        {"deploy_policy_id": 10_000 + index, "meta": {"name": f"noise-{index}"}} for index in range(500)
                    ]
                }
            return {"items": [{"deploy_policy_id": 5252, "meta": {"name": binding.policy_name}}]}

        self.client.list_deploy_policies = list_deploy_policies

        self._reconciler().reconcile(build_steps(), force=True)

        binding.refresh_from_db()
        self.assertEqual(binding.deploy_policy_id, 5252)
        self.assertEqual(offsets, [0, 500])

    def test_fingerprint_not_advanced_when_dispatch_fails(self):
        # 失败后必须保持旧指纹，否则会记成「已下发」而实际一台机器都没生效
        from apps.log_databus.nodeman_v3.models import NodeManV3Binding

        original = self.client.create_deploy_policy

        def boom(payload):
            if payload["name"].startswith("bklog-plugin-"):
                return original(payload)
            raise NodeManV3UnknownResultError("dispatch failed")

        self.client.create_deploy_policy = boom
        with self.assertRaises(NodeManV3UnknownResultError):
            self._reconciler().reconcile(build_steps())

        binding = NodeManV3Binding.objects.get(collector_config_id=8001)
        self.assertEqual(binding.policy_fingerprint, "")

    def test_install_policy_failure_blocks_collector_dispatch(self):
        # 采集器装不上时子配置无处落地，这里必须整体失败而不是把子配置策略照常推下去，
        # 否则本地记成已下发、实际零主机生效
        def boom(payload):
            raise NodeManV3UnknownResultError("install policy dispatch failed")

        self.client.create_deploy_policy = boom
        with self.assertRaises(NodeManV3UnknownResultError):
            self._reconciler().reconcile(build_steps())

        self.assertEqual(self.client.write_calls("collector"), [])

    def test_stop_is_not_blocked_by_install_policy_failure(self):
        # 停用方向必须先摘子配置。安装范围收窄只是记账（specify_plugin 只装不卸，
        # 主机移出范围不动主机），若让它的失败回滚子配置清理，
        # 采集项就会显示已停用却仍在采集
        from apps.log_databus.nodeman_v3.constants import NodeManV3OperationType

        self._reconciler().reconcile(build_steps())
        original = self.client.update_deploy_policy

        def boom(payload):
            if payload["deploy_policies"][0]["meta"]["name"].startswith("bklog-plugin-"):
                raise NodeManV3UnknownResultError("install policy dispatch failed")
            return original(payload)

        self.client.update_deploy_policy = boom
        operation = self._reconciler().reconcile(
            build_steps(), target_nodes=[], operation_type=NodeManV3OperationType.REMOVE
        )

        # 停用照常完成：子配置清理已经下发，安装范围的记账偏差留给下一次收敛
        self.assertIsNotNone(operation)
        self.assertEqual(self.client.payloads_of("update", "collector")[-1]["deploy_policies"][0]["scopes"], [])

    def test_stop_removes_sub_configs_before_shrinking_install_scope(self):
        from apps.log_databus.nodeman_v3.constants import NodeManV3OperationType

        self._reconciler().reconcile(build_steps())
        before = len(self.client.calls)
        self._reconciler().reconcile(build_steps(), target_nodes=[], operation_type=NodeManV3OperationType.REMOVE)
        kinds = [
            self.client.policy_kind_of(name, payload)
            for name, payload in self.client.calls[before:]
            if name in ("create", "update", "execute")
        ]
        self.assertEqual(kinds, ["collector", "collector", "plugin", "plugin"])


@override_settings(NODEMAN_INTEGRATION_MODE="v3_fresh")
class InstallPolicyScopeTest(TestCase):
    """安装策略的目标范围是业务内所有启用中采集项的并集"""

    def setUp(self):
        self.client = FakeNodeManV3Client()
        patcher = patch("apps.log_databus.nodeman_v3.reconciler.get_client", side_effect=lambda *a, **kw: self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _reconcile(self, collector_config_id, host_ids):
        from types import SimpleNamespace

        from apps.log_databus.nodeman_v3.reconciler import CollectorPolicyReconciler

        collector_config = SimpleNamespace(
            collector_config_id=collector_config_id,
            bk_biz_id=2,
            target_node_type=TargetNodeTypeEnum.INSTANCE.value,
            target_nodes=[{"bk_host_id": host_id} for host_id in host_ids],
            description="",
        )
        return CollectorPolicyReconciler(collector_config).reconcile(build_steps())

    def _install_scope_instance_ids(self):
        """最近一次下发给安装策略的主机集合"""
        latest = None
        for name, payload in self.client.calls:
            if self.client.policy_kind_of(name, payload) != "plugin":
                continue
            if name == "create":
                latest = payload["scopes"]
            elif name == "update":
                latest = payload["deploy_policies"][0]["scopes"]
        instance_ids = set()
        for scope in latest or []:
            instance_ids.update(scope["scope"].get("instance_ids") or [])
        return instance_ids

    def test_scope_is_union_of_all_collectors(self):
        self._reconcile(8001, [11])
        self._reconcile(8002, [12])
        self.assertEqual(self._install_scope_instance_ids(), {11, 12})

    def test_disabling_one_collector_keeps_other_collectors_hosts(self):
        # 停用采集项 8001 不能把 8002 还在用的主机从安装范围里摘掉，
        # 否则那台机器上的采集器会被移出期望态，后续升级与新采集项都会漏掉它
        self._reconcile(8001, [11])
        self._reconcile(8002, [12])
        self._reconcile(8001, [])
        self.assertEqual(self._install_scope_instance_ids(), {12})

    def test_shared_host_survives_one_collector_stop(self):
        # 两个采集项共用一台机器时，停掉其中一个不能把该机器移出安装范围，
        # 否则另一个采集项的子配置会失去落地条件
        self._reconcile(8001, [11])
        self._reconcile(8002, [11, 12])
        self._reconcile(8001, [])
        self.assertEqual(self._install_scope_instance_ids(), {11, 12})


class MigrationStateTest(TestCase):
    def test_log_databus_has_no_pending_migrations(self):
        # V3 控制面模型的迁移是手写的，这里防止模型与迁移文件长期漂移
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("makemigrations", "log_databus", check=True, dry_run=True, stdout=out, verbosity=1)


class V2ZeroImpactTest(TestCase):
    """V2 模式下不得出现任何 V3 出站调用"""

    @override_settings(NODEMAN_INTEGRATION_MODE="v2")
    def test_v2_mode_does_not_touch_v3_installer(self):
        from apps.log_databus.handlers.collector.host import HostCollectorHandler

        handler = HostCollectorHandler.__new__(HostCollectorHandler)
        handler.data = type("Data", (), {"subscription_id": None, "bk_biz_id": 2})()

        def explode(_self):
            raise AssertionError("V2 mode must not touch the NodeMan V3 installer")

        with patch.object(HostCollectorHandler, "nodeman_v3_installer", property(explode)):
            self.assertIsNone(handler._pre_start())
            self.assertIsNone(handler._pre_stop())
            self.assertIsNone(handler._pre_destroy())

    @override_settings(NODEMAN_INTEGRATION_MODE="v2")
    def test_task_id_validation_stays_numeric_in_v2(self):
        from apps.log_databus.serializers import validate_task_id_value

        self.assertTrue(validate_task_id_value("123,456"))
        self.assertFalse(validate_task_id_value("trigger-abc"))

    @override_settings(NODEMAN_INTEGRATION_MODE="v3_fresh")
    def test_task_id_validation_accepts_string_ids_in_v3(self):
        from apps.log_databus.serializers import validate_task_id_value

        self.assertTrue(validate_task_id_value("trigger-abc,trigger-def"))
        # 仍然限制字符集，避免放开后把任意内容透传给下游
        self.assertFalse(validate_task_id_value("trigger abc"))
        self.assertFalse(validate_task_id_value("../../etc/passwd"))


class ListCollectorsByHostGrayTest(TestCase):
    """
    按主机反查采集项必须把两套控制面的结果取并集。

    这个接口在视图里是 HostCollectorHandler() 无参构造，self.data 为 None，拿不到任何采集项
    身份 —— 所以不能按采集项归属分流。灰度期二选一的表现是「这台机器上的采集项凭空少了几个」。
    """

    BK_BIZ_ID = 2
    BK_HOST_ID = 77

    def setUp(self):
        from apps.log_databus.models import CollectorConfig
        from apps.log_search.models import LogIndexSet

        for index_set_id in (1, 2):
            LogIndexSet.objects.create(
                index_set_id=index_set_id,
                index_set_name=f"set-{index_set_id}",
                space_uid=f"bkcc__{self.BK_BIZ_ID}",
                scenario_id="log",
            )

        self.v2_collector = CollectorConfig.objects.create(
            collector_config_name="v2-one",
            collector_config_name_en="v2_one",
            bk_biz_id=self.BK_BIZ_ID,
            collector_scenario_id=CollectorScenarioEnum.ROW.value,
            category_id="os",
            target_object_type="HOST",
            target_node_type=TargetNodeTypeEnum.INSTANCE.value,
            subscription_id=9001,
            table_id="2_bklog.v2_one",
            index_set_id=1,
            is_active=True,
        )
        self.v3_collector = CollectorConfig.objects.create(
            collector_config_name="v3-one",
            collector_config_name_en="v3_one",
            bk_biz_id=self.BK_BIZ_ID,
            collector_scenario_id=CollectorScenarioEnum.ROW.value,
            category_id="os",
            target_object_type="HOST",
            target_node_type=TargetNodeTypeEnum.INSTANCE.value,
            subscription_id=None,
            table_id="2_bklog.v3_one",
            index_set_id=2,
            is_active=True,
        )

        binding = NodeManV3Binding.objects.create(
            resource_type=RESOURCE_TYPE_COLLECTOR_CONFIG,
            resource_key=build_resource_key(self.v3_collector.collector_config_id),
            bk_biz_id=self.BK_BIZ_ID,
            bk_tenant_id="system",
            collector_config_id=self.v3_collector.collector_config_id,
            deploy_policy_id=3001,
            policy_name=build_policy_name(self.v3_collector.collector_config_id),
            generation=1,
            is_enabled=True,
        )
        NodeManV3SubConfigTarget.objects.create(
            binding=binding,
            bk_host_id=self.BK_HOST_ID,
            config_file_name=build_sub_config_name(f"{LogPluginInfo.NAME}.conf", 3001),
            generation=1,
            is_desired=True,
        )

    def _list(self):
        from apps.log_databus.handlers.collector.host import HostCollectorHandler

        handler = HostCollectorHandler()
        with (
            patch.object(
                HostCollectorHandler,
                "_resolve_bk_host_ids",
                staticmethod(lambda params: [self.BK_HOST_ID]),
            ),
            patch(
                "apps.log_databus.handlers.collector.host.NodeApi.query_host_subscriptions",
                return_value=[{"source_id": 9001}],
            ),
            patch.object(
                HostCollectorHandler,
                "add_cluster_info",
                # 真实实现会补上 retention 等存储字段，这里只要保留原行并补齐下游必需的键
                lambda _self, rows: [{**row, "retention": 7} for row in rows],
            ),
            # 状态回读不是本用例的被测对象，桩掉避免打到真实节点管理
            patch.object(HostCollectorHandler, "get_subscription_status_by_list", lambda _self, ids: []),
        ):
            rows = handler.list_collectors_by_host({"bk_biz_id": self.BK_BIZ_ID, "bk_host_id": self.BK_HOST_ID})
        return {row["collector_config_id"] for row in rows}

    @override_settings(NODEMAN_INTEGRATION_MODE="v3_fresh")
    def test_gray_env_returns_both_v2_and_v3_collectors(self):
        self.assertEqual(
            self._list(),
            {self.v2_collector.collector_config_id, self.v3_collector.collector_config_id},
        )

    @override_settings(NODEMAN_INTEGRATION_MODE="v2")
    def test_v2_env_only_returns_v2_collectors(self):
        # V3 快照表在 V2 环境下不该被读，否则会把 V3 采集项泄漏到 V2 环境的反查结果里
        self.assertEqual(self._list(), {self.v2_collector.collector_config_id})

    @override_settings(NODEMAN_INTEGRATION_MODE="v3_fresh")
    def test_no_v2_subscription_means_no_v2_outbound_call(self):
        from apps.log_databus.handlers.collector.host import HostCollectorHandler
        from apps.log_databus.models import CollectorConfig

        # 纯 V3 环境里节点管理 V2 可能压根不存在，无条件调用会让整个接口 5xx
        CollectorConfig.objects.filter(collector_config_id=self.v2_collector.collector_config_id).update(
            subscription_id=None
        )
        handler = HostCollectorHandler()

        def explode(*args, **kwargs):
            raise AssertionError("must not call V2 query_host_subscriptions when no V2 collector exists")

        with (
            patch.object(
                HostCollectorHandler,
                "_resolve_bk_host_ids",
                staticmethod(lambda params: [self.BK_HOST_ID]),
            ),
            patch(
                "apps.log_databus.handlers.collector.host.NodeApi.query_host_subscriptions",
                side_effect=explode,
            ),
            patch.object(
                HostCollectorHandler,
                "add_cluster_info",
                # 真实实现会补上 retention 等存储字段，这里只要保留原行并补齐下游必需的键
                lambda _self, rows: [{**row, "retention": 7} for row in rows],
            ),
            # 状态回读不是本用例的被测对象，桩掉避免打到真实节点管理
            patch.object(HostCollectorHandler, "get_subscription_status_by_list", lambda _self, ids: []),
        ):
            rows = handler.list_collectors_by_host({"bk_biz_id": self.BK_BIZ_ID, "bk_host_id": self.BK_HOST_ID})
        self.assertEqual({row["collector_config_id"] for row in rows}, {self.v3_collector.collector_config_id})
