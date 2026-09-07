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

from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.log_databus.constants import LogPluginInfo, TargetNodeTypeEnum
from apps.log_databus.nodeman_v3.constants import (
    SPEC_TYPE_SPECIFY_PLUGIN,
    SPEC_TYPE_SPECIFY_PLUGIN_SUB_CONFIG_TEMPLATE,
)
from apps.log_databus.nodeman_v3.exceptions import (
    NodeManV3APIError,
    NodeManV3CapabilityBlocked,
    NodeManV3UnknownResultError,
)
from apps.log_databus.nodeman_v3.identity import build_policy_name, build_sub_config_name
from apps.log_databus.nodeman_v3.mode import is_nodeman_v3_only
from apps.log_databus.nodeman_v3.policy import (
    SubscriptionStepsTranslator,
    build_policy_payload,
    calculate_fingerprint,
)
from apps.log_databus.nodeman_v3.scopes import build_scopes
from apps.log_databus.nodeman_v3.versions import resolve_plugin_version

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

    def test_specs_contain_plugin_and_sub_config_template(self):
        specs = SubscriptionStepsTranslator().build_specs(build_steps(), "1.2.3")
        self.assertEqual(
            [spec["type"] for spec in specs], [SPEC_TYPE_SPECIFY_PLUGIN, SPEC_TYPE_SPECIFY_PLUGIN_SUB_CONFIG_TEMPLATE]
        )

    def test_specify_plugin_spec_is_required_for_sub_config_to_land(self):
        # 节点管理只对插件进程 running 的主机下发子配置，缺了 specify_plugin
        # 会出现「策略执行成功但没有一台主机生效」
        specs = SubscriptionStepsTranslator().build_specs(build_steps(), "1.2.3")
        plugin_spec = specs[0]
        self.assertEqual(plugin_spec["param"]["plugin_name"], PLUGIN_NAME)
        self.assertEqual(plugin_spec["param"]["version"], "1.2.3")

    def test_main_config_template_is_excluded_from_sub_config_spec(self):
        # 把主配置模板混进子配置会让节点管理重写主配置，影响同机其它采集项
        specs = SubscriptionStepsTranslator().build_specs(build_steps(), "1.2.3")
        details = specs[1]["param"]["config_files_detail"]
        self.assertEqual([detail["template_name"] for detail in details], [f"{PLUGIN_NAME}.conf"])
        self.assertTrue(all(detail["is_main_config"] is False for detail in details))

    def test_custom_config_context_passes_through_unchanged(self):
        # Jinja2 渲染时 custom_config_context 直接合并到模板顶层，与 V2 params.context 一致，
        # 原样透传才能保证六种场景的出数口径不变
        steps = build_steps(dataid=9527, paths=["/data/log/x.log"])
        specs = SubscriptionStepsTranslator().build_specs(steps, "1.2.3")
        context = specs[1]["param"]["custom_config_context"]
        self.assertEqual(context["dataid"], 9527)
        self.assertEqual(context["local"], [{"paths": ["/data/log/x.log"]}])

    def test_missing_dataid_fails_closed(self):
        steps = build_steps()
        steps[1]["params"]["context"].pop("dataid")
        with self.assertRaises(NodeManV3CapabilityBlocked):
            SubscriptionStepsTranslator().build_specs(steps, "1.2.3")

    def test_single_step_scenario_is_supported(self):
        # syslog 等场景只有一个 PLUGIN 步骤
        steps = [build_steps()[1]]
        specs = SubscriptionStepsTranslator().build_specs(steps, "1.2.3")
        self.assertEqual(len(specs), 2)


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
            plugin_version="1.2.3",
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
            plugin_version="1.2.3",
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
            plugin_version="1.2.3",
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
            plugin_version="1.2.3",
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


class FakeNodeManV3Client:
    """记录所有出站写调用，用于断言收敛行为"""

    def __init__(self):
        self.calls = []
        self.tenant_id = "system"
        self.next_policy_id = 1001

    def list_release_plugin_brief(self, payload):
        return {"items": [{"os_type": "linux", "cpu_arch": "amd64", "version": "3.1.0"}]}

    def list_deploy_policies(self, payload):
        self.calls.append(("list", payload))
        return {"items": []}

    def create_deploy_policy(self, payload):
        self.calls.append(("create", payload))
        policy_id = self.next_policy_id
        self.next_policy_id += 1
        return {"deploy_policy_id": policy_id}

    def update_deploy_policy(self, payload):
        self.calls.append(("update", payload))
        return {}

    def execute_deploy_policy(self, deploy_policy_id):
        self.calls.append(("execute", deploy_policy_id))
        return {"trigger_id": f"trigger-{deploy_policy_id}-{len(self.calls)}"}

    def write_calls(self):
        return [name for name, _payload in self.calls if name in ("create", "update", "execute")]


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
        patcher = patch(
            "apps.log_databus.nodeman_v3.reconciler.get_client", side_effect=lambda *a, **kw: self.client
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _reconciler(self):
        from apps.log_databus.nodeman_v3.reconciler import CollectorPolicyReconciler

        return CollectorPolicyReconciler(self.collector_config)

    def test_first_reconcile_creates_policy_then_executes(self):
        operation = self._reconciler().reconcile(build_steps())
        self.assertIsNotNone(operation)
        self.assertEqual(self.client.write_calls(), ["create", "execute"])

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
        self.assertEqual(self.client.write_calls(), ["create", "execute", "update", "execute"])

    def test_stop_clears_scopes_but_keeps_policy_enabled(self):
        from apps.log_databus.nodeman_v3.constants import NodeManV3OperationType

        self._reconciler().reconcile(build_steps())
        operation = self._reconciler().reconcile(
            build_steps(), target_nodes=[], operation_type=NodeManV3OperationType.REMOVE
        )
        self.assertIsNotNone(operation)

        update_payload = [payload for name, payload in self.calls_of("update")][-1]
        policy = update_payload["deploy_policies"][0]
        self.assertEqual(policy["scopes"], [])
        # 被 disable 的策略不再参与收敛，已下发的子配置会残留在主机上继续采集
        self.assertTrue(policy["enabled"])

    def test_repeated_stop_is_idempotent(self):
        from apps.log_databus.nodeman_v3.constants import NodeManV3OperationType

        self._reconciler().reconcile(build_steps())
        self._reconciler().reconcile(
            build_steps(), target_nodes=[], operation_type=NodeManV3OperationType.REMOVE
        )
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
        self.client.list_deploy_policies = lambda payload: {
            "items": [{"deploy_policy_id": recovered_policy_id, "meta": {"name": binding.policy_name}}]
        }

        self._reconciler().reconcile(build_steps(), force=True)
        self.assertNotIn("create", self.client.write_calls()[2:])
        binding.refresh_from_db()
        self.assertEqual(binding.deploy_policy_id, recovered_policy_id)

    def test_fingerprint_not_advanced_when_dispatch_fails(self):
        # 失败后必须保持旧指纹，否则会记成「已下发」而实际一台机器都没生效
        from apps.log_databus.nodeman_v3.models import NodeManV3Binding

        def boom(payload):
            raise NodeManV3UnknownResultError("dispatch failed")

        self.client.create_deploy_policy = boom
        with self.assertRaises(NodeManV3UnknownResultError):
            self._reconciler().reconcile(build_steps())

        binding = NodeManV3Binding.objects.get(collector_config_id=8001)
        self.assertEqual(binding.policy_fingerprint, "")

    def calls_of(self, name):
        return [(call_name, payload) for call_name, payload in self.client.calls if call_name == name]


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
