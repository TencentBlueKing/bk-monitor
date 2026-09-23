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

import datetime
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.log_databus.constants import LogPluginInfo, TargetNodeTypeEnum
from apps.log_databus.models import CollectorConfig
from apps.log_databus.nodeman_v3.constants import (
    NodeManV3OperationStatus,
    NodeManV3OperationType,
    RESOURCE_TYPE_COLLECTOR_CONFIG,
    RESOURCE_TYPE_COLLECTOR_PLUGIN,
)
from apps.log_databus.nodeman_v3.exceptions import NodeManV3CapabilityBlocked
from apps.log_databus.nodeman_v3.identity import build_plugin_resource_key, build_resource_key, build_sub_config_name
from apps.log_databus.nodeman_v3.models import (
    NodeManV3Binding,
    NodeManV3Operation,
    NodeManV3SubConfigTarget,
)
from apps.log_databus.nodeman_v3.targets import (
    collector_config_ids_by_host,
    expand_target_hosts,
    purge_removed_targets,
    reconcile_binding_targets,
)

PLUGIN_NAME = LogPluginInfo.NAME
TEMPLATE_NAME = f"{PLUGIN_NAME}.conf"
BK_BIZ_ID = 2
POLICY_ID = 1001


def make_binding(collector_config_id=8001, deploy_policy_id=POLICY_ID, **kwargs):
    defaults = {
        "resource_type": RESOURCE_TYPE_COLLECTOR_CONFIG,
        "resource_key": build_resource_key(collector_config_id),
        "bk_biz_id": BK_BIZ_ID,
        "bk_tenant_id": "system",
        "collector_config_id": collector_config_id,
        "deploy_policy_id": deploy_policy_id,
        "policy_name": f"bklog-collector-{collector_config_id}",
        "sub_config_template_names": [TEMPLATE_NAME],
        "generation": 1,
        "is_enabled": True,
    }
    defaults.update(kwargs)
    return NodeManV3Binding.objects.create(**defaults)


class ExpandTargetHostsTest(TestCase):
    """五种采集目标的主机展开"""

    def test_instance_target_uses_host_id_directly(self):
        hosts = expand_target_hosts(
            BK_BIZ_ID, TargetNodeTypeEnum.INSTANCE.value, [{"bk_host_id": 11}, {"bk_host_id": 12}]
        )
        self.assertEqual(hosts, {11, 12})

    def test_instance_target_without_host_id_fails_closed(self):
        # 与 scopes.build_scopes 同一条失败关闭线：静默少算会掩盖下发缺口，
        # 表现为「页面显示目标 3 台、实际只下发 2 台」且无人发现
        with self.assertRaises(NodeManV3CapabilityBlocked):
            expand_target_hosts(
                BK_BIZ_ID,
                TargetNodeTypeEnum.INSTANCE.value,
                [{"bk_host_id": 11}, {"ip": "127.0.0.1", "bk_cloud_id": 0}],
            )

    def test_empty_target_expands_to_empty_set(self):
        self.assertEqual(expand_target_hosts(BK_BIZ_ID, TargetNodeTypeEnum.TOPO.value, []), set())

    @patch("apps.log_databus.nodeman_v3.targets.BizHandler")
    def test_topo_target_expands_via_cmdb(self, mock_biz_handler):
        mock_biz_handler.return_value.search_host.return_value = [
            {"bk_host_id": 21},
            {"bk_host_id": 22},
            {"bk_host_id": 21},
        ]
        hosts = expand_target_hosts(
            BK_BIZ_ID,
            TargetNodeTypeEnum.TOPO.value,
            [{"bk_obj_id": "module", "bk_inst_id": 52}],
        )
        self.assertEqual(hosts, {21, 22})
        mock_biz_handler.return_value.search_host.assert_called_once_with([{"bk_obj_id": "module", "bk_inst_id": 52}])

    @patch("apps.log_databus.nodeman_v3.targets.BizHandler")
    def test_service_template_target_expands_via_cmdb(self, mock_biz_handler):
        mock_biz_handler.return_value.search_host.return_value = [{"bk_host_id": 31}]
        hosts = expand_target_hosts(
            BK_BIZ_ID,
            TargetNodeTypeEnum.SERVICE_TEMPLATE.value,
            [{"bk_obj_id": "SERVICE_TEMPLATE", "bk_inst_id": 7}],
        )
        self.assertEqual(hosts, {31})

    @patch("apps.log_databus.nodeman_v3.targets.CCApi")
    def test_dynamic_group_target_expands_via_cmdb(self, mock_cc_api):
        mock_cc_api.execute_dynamic_group.bulk_request.return_value = [
            {"bk_host_id": 41},
            {"bk_host_id": 42},
        ]
        hosts = expand_target_hosts(BK_BIZ_ID, TargetNodeTypeEnum.DYNAMIC_GROUP.value, [{"bk_inst_id": "dg-1"}])
        self.assertEqual(hosts, {41, 42})

    def test_unknown_target_type_fails_closed(self):
        with self.assertRaises(NodeManV3CapabilityBlocked):
            expand_target_hosts(BK_BIZ_ID, "WHAT_IS_THIS", [{"bk_host_id": 1}])


class TargetSnapshotTest(TestCase):
    """期望快照的增删差异"""

    def setUp(self):
        self.binding = make_binding()

    def _snapshot(self, host_ids):
        return reconcile_binding_targets(self.binding, set(host_ids), [TEMPLATE_NAME])

    def test_first_snapshot_reports_all_hosts_as_added(self):
        diff = self._snapshot([11, 12])
        self.assertEqual(diff.added, {11, 12})
        self.assertEqual(diff.removed, set())
        self.assertEqual(NodeManV3SubConfigTarget.objects.filter(binding=self.binding).count(), 2)
        self.assertEqual(
            set(NodeManV3SubConfigTarget.objects.filter(binding=self.binding).values_list("generation", flat=True)),
            {0},
        )

    def test_unchanged_target_produces_no_diff(self):
        self._snapshot([11, 12])
        diff = self._snapshot([11, 12])
        self.assertFalse(diff.changed)
        self.assertEqual(diff.unchanged, {11, 12})

    def test_added_host_is_reported_once_not_repeatedly(self):
        # 「新增主机不漏、不重复」的验收项：第二轮不能再把 13 报成新增，
        # 否则每轮定时任务都会判定目标有变化并触发一次全量重新下发
        self._snapshot([11])
        first = self._snapshot([11, 13])
        second = self._snapshot([11, 13])
        self.assertEqual(first.added, {13})
        self.assertEqual(second.added, set())

    def test_removed_host_row_is_kept_and_marked_not_desired(self):
        # 删除是异步的：行删掉就再也查不到「这台机器还残留着本采集项的配置」，
        # 而这正是「移除主机只删该采集项子配置」的验收依据
        self._snapshot([11, 12])
        diff = self._snapshot([11])
        self.assertEqual(diff.removed, {12})
        row = NodeManV3SubConfigTarget.objects.get(binding=self.binding, bk_host_id=12)
        self.assertFalse(row.is_desired)

    def test_removing_host_does_not_touch_other_collector_targets(self):
        # 同机两个采集项，其中一个移除该主机，另一个的快照行必须原样保留
        other = make_binding(collector_config_id=8002, deploy_policy_id=1002)
        reconcile_binding_targets(other, {11, 12}, [TEMPLATE_NAME])
        self._snapshot([11, 12])

        self._snapshot([11])

        self.assertTrue(NodeManV3SubConfigTarget.objects.get(binding=other, bk_host_id=12).is_desired)
        self.assertFalse(NodeManV3SubConfigTarget.objects.get(binding=self.binding, bk_host_id=12).is_desired)

    def test_config_file_name_is_scoped_by_deploy_policy(self):
        other = make_binding(collector_config_id=8002, deploy_policy_id=1002)
        self._snapshot([11])
        reconcile_binding_targets(other, {11}, [TEMPLATE_NAME])

        names = set(NodeManV3SubConfigTarget.objects.filter(bk_host_id=11).values_list("config_file_name", flat=True))
        self.assertEqual(names, {f"{PLUGIN_NAME}_deploy_1001.conf", f"{PLUGIN_NAME}_deploy_1002.conf"})

    def test_readded_host_does_not_claim_to_be_applied(self):
        # 主机移出后又加回来：is_desired 复位，但 generation 不能跟着跳到最新，
        # 否则一台从未成功下发过的主机会在状态页显示「已生效且最新」
        self._snapshot([11])
        NodeManV3SubConfigTarget.objects.filter(binding=self.binding, bk_host_id=11).update(generation=0)
        self._snapshot([])
        self.binding.generation = 5
        self.binding.save(update_fields=["generation"])

        self._snapshot([11])

        row = NodeManV3SubConfigTarget.objects.get(binding=self.binding, bk_host_id=11)
        self.assertTrue(row.is_desired)
        self.assertEqual(row.generation, 0)

    def test_renamed_template_marks_old_file_row_not_desired(self):
        # 改采集场景会换模板名，而文件名由模板名推出。旧文件名的行若一直留在 is_desired=True，
        # 状态页会把它当成「期望有但主机上没有」而永久显示缺配置，purge_removed_targets
        # 又只回收 is_desired=False 的行，于是永远清不掉
        self._snapshot([11])
        old_name = build_sub_config_name(TEMPLATE_NAME, self.binding.deploy_policy_id)

        renamed = f"{PLUGIN_NAME}_json.conf"
        reconcile_binding_targets(self.binding, {11}, [renamed])

        rows = {
            row.config_file_name: row.is_desired
            for row in NodeManV3SubConfigTarget.objects.filter(binding=self.binding, bk_host_id=11)
        }
        self.assertFalse(rows[old_name])
        self.assertTrue(rows[build_sub_config_name(renamed, self.binding.deploy_policy_id)])

    def test_renamed_template_old_row_becomes_purgeable(self):
        # 标了 is_desired=False 之后，确认主机上已无残留时要能被回收，否则表会一直涨
        self._snapshot([11])
        reconcile_binding_targets(self.binding, {11}, [f"{PLUGIN_NAME}_json.conf"])
        self.assertEqual(purge_removed_targets(self.binding, {11}), 1)
        self.assertEqual(NodeManV3SubConfigTarget.objects.filter(binding=self.binding, bk_host_id=11).count(), 1)

    def test_snapshot_skipped_before_policy_created(self):
        # 新建采集项在 create 之前跑到定时任务是正常时序，不能抛错打断整轮
        binding = make_binding(collector_config_id=8003, deploy_policy_id=None)
        diff = reconcile_binding_targets(binding, {11}, [TEMPLATE_NAME])
        self.assertFalse(diff.changed)
        self.assertEqual(NodeManV3SubConfigTarget.objects.filter(binding=binding).count(), 0)

    def test_snapshot_skipped_without_template_names(self):
        binding = make_binding(collector_config_id=8004, sub_config_template_names=[])
        diff = reconcile_binding_targets(binding, {11}, [])
        self.assertFalse(diff.changed)
        self.assertEqual(NodeManV3SubConfigTarget.objects.filter(binding=binding).count(), 0)

    def test_purge_only_removes_confirmed_clean_hosts(self):
        self._snapshot([11, 12])
        self._snapshot([11])

        # 12 还没确认摘干净，不能回收
        self.assertEqual(purge_removed_targets(self.binding, set()), 0)
        self.assertTrue(NodeManV3SubConfigTarget.objects.filter(binding=self.binding, bk_host_id=12).exists())

        purge_removed_targets(self.binding, {12})
        self.assertFalse(NodeManV3SubConfigTarget.objects.filter(binding=self.binding, bk_host_id=12).exists())

    def test_purge_never_removes_desired_hosts(self):
        self._snapshot([11, 12])
        purge_removed_targets(self.binding, {11, 12})
        self.assertEqual(NodeManV3SubConfigTarget.objects.filter(binding=self.binding).count(), 2)


class HostReverseLookupTest(TestCase):
    """主机反查采集项，替代 V2 query_host_subscriptions"""

    def setUp(self):
        self.first = make_binding(collector_config_id=8001, deploy_policy_id=1001)
        self.second = make_binding(collector_config_id=8002, deploy_policy_id=1002)
        reconcile_binding_targets(self.first, {11, 12}, [TEMPLATE_NAME])
        reconcile_binding_targets(self.second, {11}, [TEMPLATE_NAME])

    def test_same_host_reports_all_collector_configs(self):
        # V3 的 process/list 只到进程粒度，同机多采集项共用一个 bkunifylogbeat 进程，
        # 从对方根本查不出这台机器上跑着哪几个采集项
        self.assertEqual(collector_config_ids_by_host(BK_BIZ_ID, [11]), {11: [8001, 8002]})

    def test_host_with_single_collector(self):
        self.assertEqual(collector_config_ids_by_host(BK_BIZ_ID, [12]), {12: [8001]})

    def test_host_without_collector_is_absent(self):
        self.assertEqual(collector_config_ids_by_host(BK_BIZ_ID, [99]), {})

    def test_removed_host_is_not_reported(self):
        reconcile_binding_targets(self.first, {11}, [TEMPLATE_NAME])
        self.assertEqual(collector_config_ids_by_host(BK_BIZ_ID, [12]), {})

    def test_disabled_collector_is_not_reported(self):
        self.second.is_enabled = False
        self.second.save(update_fields=["is_enabled"])
        self.assertEqual(collector_config_ids_by_host(BK_BIZ_ID, [11]), {11: [8001]})

    def test_other_biz_is_not_reported(self):
        self.assertEqual(collector_config_ids_by_host(BK_BIZ_ID + 1, [11]), {})


@override_settings(NODEMAN_INTEGRATION_MODE="v3_fresh")
class PeriodicReconcileTest(TestCase):
    """定时收敛与中断恢复"""

    def setUp(self):
        self.collector_config = CollectorConfig.objects.create(
            collector_config_id=8001,
            collector_config_name="nmv3_targets",
            collector_scenario_id="row",
            bk_biz_id=BK_BIZ_ID,
            category_id="os",
            target_object_type="HOST",
            target_node_type=TargetNodeTypeEnum.INSTANCE.value,
            target_nodes=[{"bk_host_id": 11}],
            target_subscription_diff={},
            description="nmv3",
            is_active=True,
            bk_data_id=1500999,
            table_id="2_bklog.nmv3_targets",
        )
        self.binding = make_binding(collector_config_id=8001)

        installer_patcher = patch("apps.log_databus.nodeman_v3.installer.NodeManV3CollectorInstaller", autospec=True)
        self.mock_installer = installer_patcher.start()
        self.addCleanup(installer_patcher.stop)

    def _run_targets_task(self):
        from apps.log_databus.tasks.nodeman_v3 import reconcile_nodeman_v3_targets

        reconcile_nodeman_v3_targets()

    @staticmethod
    def _run_recovery(minutes_later: int = 60):
        """
        把任务侧的时钟往后拨，而不是把 operation.updated_at 往前拨。

        OperateRecordQuerySet.update() 在请求上下文里存在用户时会强制覆写 updated_at
        （apps/models.py:188-191），所以「用 .update() 把记录改成一小时前」只在单跑时成立；
        全量跑时前序用例残留的请求上下文会让回拨被静默抹掉，用例随执行顺序飘。
        """
        from apps.log_databus.tasks import nodeman_v3 as task_module

        later = timezone.now() + datetime.timedelta(minutes=minutes_later)
        with patch.object(task_module, "timezone") as mock_timezone:
            mock_timezone.now.return_value = later
            task_module.recover_nodeman_v3_operations()

    def test_target_change_triggers_redispatch(self):
        # 目标集合变了但采集项本身没被编辑过，没有任何人会去调 execute，
        # 只能靠这条定时任务发现
        self._run_targets_task()
        self.mock_installer.return_value.rerun.assert_called_once()

    def test_unchanged_target_within_heal_window_does_not_redispatch(self):
        reconcile_binding_targets(self.binding, {11}, [TEMPLATE_NAME])
        self.binding.last_heal_at = timezone.now()
        self.binding.save(update_fields=["last_heal_at"])

        self._run_targets_task()

        self.mock_installer.return_value.rerun.assert_not_called()

    def test_unchanged_target_still_replays_after_heal_window(self):
        # 采集器进程重启期间，节点管理会把该策略在这台主机上的子配置记录删掉，
        # 目标集合却完全没变。所以兜底重放是正确性必需，不是优化项
        reconcile_binding_targets(self.binding, {11}, [TEMPLATE_NAME])
        self.binding.last_heal_at = timezone.now() - datetime.timedelta(hours=3)
        self.binding.save(update_fields=["last_heal_at"])

        self._run_targets_task()

        self.mock_installer.return_value.rerun.assert_called_once()

    def test_binding_without_policy_is_skipped(self):
        self.binding.deploy_policy_id = None
        self.binding.save(update_fields=["deploy_policy_id"])

        self._run_targets_task()

        self.mock_installer.return_value.rerun.assert_not_called()

    def test_orphan_binding_does_not_squat_the_queue_head(self):
        # 采集项被硬删而 binding 残留时，若不推进 target_snapshot_at，这条记录会永远排在队首
        # （升序、NULL 最前）占着 RECONCILE_BATCH_LIMIT 的配额，攒够一批之后其余采集项
        # 再也收敛不到 —— 表现是静默漏采，没有任何报错
        CollectorConfig.objects.filter(collector_config_id=self.binding.collector_config_id).delete()
        self.assertIsNone(self.binding.target_snapshot_at)

        self._run_targets_task()

        self.binding.refresh_from_db()
        self.assertIsNotNone(self.binding.target_snapshot_at)

    def test_one_failing_collector_does_not_abort_the_round(self):
        # 一个业务的 CMDB 抖动不能让其它业务整轮收敛停摆
        other_config = CollectorConfig.objects.create(
            collector_config_id=8002,
            collector_config_name="nmv3_targets_2",
            collector_scenario_id="row",
            bk_biz_id=BK_BIZ_ID,
            category_id="os",
            target_object_type="HOST",
            target_node_type=TargetNodeTypeEnum.INSTANCE.value,
            target_nodes=[{"bk_host_id": 12}],
            target_subscription_diff={},
            description="nmv3",
            is_active=True,
            bk_data_id=1501000,
            table_id="2_bklog.nmv3_targets_2",
        )
        make_binding(collector_config_id=other_config.collector_config_id, deploy_policy_id=1002)

        self.mock_installer.return_value.rerun.side_effect = [RuntimeError("cmdb down"), None]

        self._run_targets_task()

        self.assertEqual(self.mock_installer.return_value.rerun.call_count, 2)

    @override_settings(NODEMAN_INTEGRATION_MODE="v2")
    def test_task_is_noop_in_v2_mode(self):
        self._run_targets_task()
        self.mock_installer.assert_not_called()

    def test_stuck_operation_is_recovered(self):
        NodeManV3Operation.objects.create(
            binding=self.binding,
            operation_type=NodeManV3OperationType.RECONCILE,
            generation=1,
            status=NodeManV3OperationStatus.DISPATCHING,
        )

        self._run_recovery()

        # 用 apply 而不是 rerun：rerun 的 force=True 会把已经派发成功、只是状态没回读到的
        # 动作再推一遍，白白触发一次全量插件 reload
        self.mock_installer.return_value.apply.assert_called_once()
        self.mock_installer.return_value.rerun.assert_not_called()

    def test_recent_operation_is_not_recovered(self):
        NodeManV3Operation.objects.create(
            binding=self.binding,
            operation_type=NodeManV3OperationType.RECONCILE,
            generation=1,
            status=NodeManV3OperationStatus.DISPATCHING,
        )

        self._run_recovery(minutes_later=0)

        self.mock_installer.return_value.apply.assert_not_called()

    def test_stuck_plugin_operation_is_recovered(self):
        plugin_binding = NodeManV3Binding.objects.create(
            resource_type=RESOURCE_TYPE_COLLECTOR_PLUGIN,
            resource_key=build_plugin_resource_key(PLUGIN_NAME),
            bk_biz_id=BK_BIZ_ID,
            bk_tenant_id="system",
            collector_config_id=0,
            deploy_policy_id=2001,
            policy_name=f"bklog-plugin-{PLUGIN_NAME}-{BK_BIZ_ID}",
            generation=1,
            is_enabled=True,
        )
        operation = NodeManV3Operation.objects.create(
            binding=plugin_binding,
            operation_type=NodeManV3OperationType.PLUGIN_RECONCILE,
            generation=1,
            status=NodeManV3OperationStatus.UNKNOWN,
        )

        with patch("apps.log_databus.nodeman_v3.reconciler.CollectorPluginReconciler") as mock_plugin_reconciler:
            self._run_recovery()

        mock_plugin_reconciler.assert_called_once_with(BK_BIZ_ID, plugin_name=PLUGIN_NAME)
        mock_plugin_reconciler.return_value.reconcile.assert_called_once()
        operation.refresh_from_db()
        self.assertEqual(operation.status, NodeManV3OperationStatus.FAILED)

    def test_succeeded_operation_is_not_recovered(self):
        NodeManV3Operation.objects.create(
            binding=self.binding,
            operation_type=NodeManV3OperationType.RECONCILE,
            generation=1,
            status=NodeManV3OperationStatus.SUCCESS,
        )

        self._run_recovery()

        self.mock_installer.return_value.apply.assert_not_called()

    def test_operation_of_deleted_collector_is_closed_not_reselected(self):
        # 采集项已被硬删，这条 operation 永远恢复不了。不落终态它就会一直停在
        # dispatching + 旧 updated_at 上被每轮重新选中，占着配额，
        # 攒够一批之后真正卡住的动作再也轮不到恢复
        operation = NodeManV3Operation.objects.create(
            binding=self.binding,
            operation_type=NodeManV3OperationType.RECONCILE,
            generation=1,
            status=NodeManV3OperationStatus.DISPATCHING,
        )
        CollectorConfig.objects.filter(collector_config_id=self.binding.collector_config_id).delete()

        self._run_recovery()

        operation.refresh_from_db()
        self.assertEqual(operation.status, NodeManV3OperationStatus.FAILED)
        self.mock_installer.return_value.apply.assert_not_called()

    @override_settings(NODEMAN_INTEGRATION_MODE="v2")
    def test_recovery_is_noop_in_v2_mode(self):
        NodeManV3Operation.objects.create(
            binding=self.binding,
            operation_type=NodeManV3OperationType.RECONCILE,
            generation=1,
            status=NodeManV3OperationStatus.DISPATCHING,
        )

        self._run_recovery()

        self.mock_installer.assert_not_called()


class CeleryRegistrationTest(TestCase):
    """
    守住「BKL-3 两个定时任务必须被 celery 注册」。

    直接调函数的用例已经全绿过，但 CELERY_IMPORTS 漏写时部署环境里这两个任务根本不存在：
    目标动态收敛与卡单恢复全部静默不跑，而节点管理建的是一次性 trigger，不重放就永久漏采。
    所以这里必须断言 settings + celery 注册表，不能只断言函数能 import。
    """

    MODULE = "apps.log_databus.tasks.nodeman_v3"
    TASK_NAMES = (
        "apps.log_databus.tasks.nodeman_v3.reconcile_nodeman_v3_targets",
        "apps.log_databus.tasks.nodeman_v3.recover_nodeman_v3_operations",
    )

    def test_module_is_in_celery_imports(self):
        from django.conf import settings

        self.assertIn(self.MODULE, settings.CELERY_IMPORTS)

    def test_both_tasks_are_registered_on_celery_app(self):
        from importlib import import_module

        from django.conf import settings

        from config import celery_app

        # 测试进程不会替 celery beat 预加载 CELERY_IMPORTS。这里按 beat 的加载方式
        # 从 settings 里取出模块名再 import —— 模块不在 CELERY_IMPORTS 里时这条会先失败
        self.assertIn(self.MODULE, settings.CELERY_IMPORTS)
        import_module(self.MODULE)

        registered = set(celery_app.tasks.keys())
        missing = [name for name in self.TASK_NAMES if name not in registered]
        self.assertEqual(
            missing,
            [],
            f"nodeman_v3 periodic tasks missing from celery registry: {missing}. "
            f"CELERY_IMPORTS must include {self.MODULE}",
        )
