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

from django.test import TestCase

from apps.log_databus.constants import LogPluginInfo
from apps.log_databus.nodeman_v3.config_files import (
    check_sub_config_name_contract,
    read_host_config_facts,
    verify_host_targets,
)
from apps.log_databus.nodeman_v3.constants import RESOURCE_TYPE_COLLECTOR_CONFIG
from apps.log_databus.nodeman_v3.identity import build_policy_name, build_resource_key, build_sub_config_name
from apps.log_databus.nodeman_v3.models import NodeManV3Binding, NodeManV3SubConfigTarget
from apps.tests.log_databus.nodeman_v3_test_utils import nodeman_v3_toggle

PLUGIN_NAME = LogPluginInfo.NAME
TEMPLATE_NAME = f"{PLUGIN_NAME}.conf"
BK_BIZ_ID = 2
COLLECTOR_CONFIG_ID = 8301
POLICY_ID = 2001
BK_HOST_ID = 11


class FakeConfigFilesClient:
    """按 Plugin_ListPluginConfigFiles.md 的真实返回结构造桩"""

    def __init__(self):
        self.tenant_id = "system"
        self.calls = []
        self.items = []

    def list_config_files(self, bk_host_id, plugin_name):
        self.calls.append((bk_host_id, plugin_name))
        return {"items": self.items}


@nodeman_v3_toggle("on")
class HostConfigFactsTest(TestCase):
    def setUp(self):
        self.binding = NodeManV3Binding.objects.create(
            resource_type=RESOURCE_TYPE_COLLECTOR_CONFIG,
            resource_key=build_resource_key(COLLECTOR_CONFIG_ID),
            bk_biz_id=BK_BIZ_ID,
            bk_tenant_id="system",
            collector_config_id=COLLECTOR_CONFIG_ID,
            deploy_policy_id=POLICY_ID,
            policy_name=build_policy_name(COLLECTOR_CONFIG_ID),
            sub_config_template_names=[TEMPLATE_NAME],
            generation=1,
        )
        self.config_file_name = build_sub_config_name(TEMPLATE_NAME, POLICY_ID)

        self.client = FakeConfigFilesClient()
        patcher = patch("apps.log_databus.nodeman_v3.config_files.get_client", side_effect=lambda *a, **kw: self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _add_row(self, is_desired=True, applied_md5=""):
        return NodeManV3SubConfigTarget.objects.create(
            binding=self.binding,
            bk_host_id=BK_HOST_ID,
            config_file_name=self.config_file_name,
            generation=1,
            is_desired=is_desired,
            applied_md5=applied_md5,
        )

    def _serve(self, name=None, md5="abc123", template_name=TEMPLATE_NAME):
        self.client.items = [
            {
                "name": name or self.config_file_name,
                "template_name": template_name,
                "process_name": PLUGIN_NAME,
                "bk_host_id": BK_HOST_ID,
                "set": f"policy_{POLICY_ID}",
                "is_main_config": False,
                "content": "path: /data/log/a.log\n",
                "md5": md5,
                "file_path": f"etc/{name or self.config_file_name}",
                "custom_config_context": {"dataid": 1001},
            }
        ]

    # ------------------------------------------------------------------
    # 回读
    # ------------------------------------------------------------------
    def test_facts_index_by_name_and_template(self):
        self._serve()
        facts = read_host_config_facts(BK_BIZ_ID, BK_HOST_ID)
        self.assertEqual(facts.md5_of(self.config_file_name), "abc123")
        self.assertEqual(facts.context_of(self.config_file_name), {"dataid": 1001})
        self.assertEqual(facts.name_by_template[TEMPLATE_NAME], self.config_file_name)

    # ------------------------------------------------------------------
    # 文件名契约
    # ------------------------------------------------------------------
    def test_contract_holds_when_name_matches_rule(self):
        self._serve()
        facts = read_host_config_facts(BK_BIZ_ID, BK_HOST_ID)
        self.assertEqual(check_sub_config_name_contract(self.binding, facts), [])

    def test_contract_mismatch_is_reported(self):
        # 节点管理单方面改了命名规则时，本地对账会全面失配，而表现只是「状态页永远显示待下发」。
        # 这条断言就是留档 §1.4 一直缺的在线信号
        self._serve(name=f"{PLUGIN_NAME}_policy_{POLICY_ID}.conf")
        facts = read_host_config_facts(BK_BIZ_ID, BK_HOST_ID)
        self.assertEqual(check_sub_config_name_contract(self.binding, facts), [TEMPLATE_NAME])

    def test_absent_template_is_not_a_contract_mismatch(self):
        # 模板压根没下发属于「没下发」，不是「命名规则变了」，混在一起会把告警打成噪音
        self.client.items = []
        facts = read_host_config_facts(BK_BIZ_ID, BK_HOST_ID)
        self.assertEqual(check_sub_config_name_contract(self.binding, facts), [])

    # ------------------------------------------------------------------
    # 精确对账
    # ------------------------------------------------------------------
    def test_verify_records_actual_md5(self):
        row = self._add_row()
        self._serve(md5="deadbeef")

        result = verify_host_targets(self.binding, BK_HOST_ID)

        self.assertTrue(result["checked"])
        self.assertEqual(result["present"], [self.config_file_name])
        self.assertEqual(result["missing"], [])
        row.refresh_from_db()
        self.assertEqual(row.applied_md5, "deadbeef")

    def test_verify_skips_write_when_md5_unchanged(self):
        self._add_row(applied_md5="deadbeef")
        self._serve(md5="deadbeef")

        with patch.object(NodeManV3SubConfigTarget, "save") as save:
            verify_host_targets(self.binding, BK_HOST_ID)

        # 每次点开详情都写一次库是纯浪费，而且会把 updated_at 刷成现在
        save.assert_not_called()

    def test_verify_reports_missing_file(self):
        self._add_row()
        self.client.items = []

        result = verify_host_targets(self.binding, BK_HOST_ID)

        self.assertEqual(result["missing"], [self.config_file_name])
        self.assertEqual(result["present"], [])

    def test_verify_without_local_rows_makes_no_request(self):
        result = verify_host_targets(self.binding, BK_HOST_ID)
        self.assertFalse(result["checked"])
        self.assertEqual(self.client.calls, [])

    # ------------------------------------------------------------------
    # 移出主机的残留判定
    # ------------------------------------------------------------------
    def test_pending_removal_clean_only_when_nothing_left(self):
        self._add_row(is_desired=False)
        self.client.items = []

        self.assertTrue(verify_host_targets(self.binding, BK_HOST_ID)["pending_removal_clean"])

    def test_pending_removal_not_clean_while_file_remains(self):
        # 删除是异步的。标了移出但文件还在，就还不能回收本地行 ——
        # 行删了就再也查不到「这台机器上还残留着本采集项的配置」
        self._add_row(is_desired=False)
        self._serve()

        self.assertFalse(verify_host_targets(self.binding, BK_HOST_ID)["pending_removal_clean"])

    def test_desired_row_never_counts_as_removal_clean(self):
        self._add_row(is_desired=True)
        self.client.items = []

        result = verify_host_targets(self.binding, BK_HOST_ID)
        self.assertFalse(result["pending_removal_clean"])
        self.assertEqual(result["missing"], [self.config_file_name])
