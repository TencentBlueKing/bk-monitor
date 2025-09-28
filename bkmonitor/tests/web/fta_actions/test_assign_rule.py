# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import urllib
from unittest import skip

import mock
from django.test import Client, TestCase
from fta_web.assign.resources import BatchUpdateResource, MatchDebugResource

from api.cmdb.define import Host, Module, Set
from bkmonitor.action.serializers.assign import *  # noqa
from bkmonitor.documents import AlertDocument, EventDocument
from bkmonitor.models import AlertAssignGroup, AlertAssignRule
from bkmonitor.utils.elasticsearch.fake_elasticsearch import FakeElasticsearchBucket
from constants.alert import EventStatus

mock.patch(
    "core.drf_resource.api.bk_login.get_all_user",
    return_value={"results": [{"username": "admin", "display_name": "admin"}]},
).start()
mock.patch(
    "elasticsearch_dsl.connections.Connections.create_connection", return_value=FakeElasticsearchBucket()
).start()
mock.patch(
    "fta_web.assign.resources.MatchDebugResource.get_cmdb_attributes",
    return_value=(
        {
            "1": Host(
                bk_host_innerip="10.0.0.1",
                bk_cloud_id=1,
                bk_host_id=1,
                bk_biz_id=2,
                bk_set_ids=[2],
                bk_module_ids=[5, 6],
            )
        },
        {"2": Set(bk_set_id=2, bk_service_status="1")},
        {"5": Module(bk_module_id=5, bk_module_name="test")},
    ),
).start()


class TestAssignRuleResource(TestCase):
    def setUp(self):
        ilm = AlertDocument.get_lifecycle_manager()
        ilm.es_client.indices.delete(index=AlertDocument.Index.name)
        AlertAssignGroup.objects.all().delete()
        AlertAssignRule.objects.all().delete()

    def tearDown(self):
        AlertAssignGroup.objects.all().delete()
        AlertAssignRule.objects.all().delete()

    def test_create_group(self):
        group_info = {"bk_biz_id": 2, "name": "test alert assign group", "priority": 1}
        slz = AssignGroupSlz(data=group_info)
        slz.is_valid(raise_exception=True)
        slz.save()
        self.assertIsNotNone(AlertAssignGroup.objects.get(id=slz.instance.id))

    def test_existed_priority_group(self):
        group_info = {"bk_biz_id": 2, "name": "test alert assign group", "priority": 1}
        AlertAssignGroup.objects.create(**group_info)
        slz = AssignGroupSlz(data=group_info)
        with self.assertRaises(ValidationError):
            slz.is_valid(raise_exception=True)

    def test_upgrade_config_required(self):
        def validate(data):
            slz = UpgradeConfigSerializer(data=data)
            return slz.is_valid(raise_exception=True)

        upgrade_config = {"is_enabled": True, "user_groups": [], "upgrade_interval": 30}
        with self.assertRaises(ValidationError):
            validate(upgrade_config)

        upgrade_config = {"is_enabled": True, "user_groups": [1, 2, 3], "upgrade_interval": 0}

        with self.assertRaises(ValidationError):
            validate(upgrade_config)

        upgrade_config = {"is_enabled": True, "user_groups": [1, 2], "upgrade_interval": 30}

        self.assertTrue(validate(upgrade_config))

        upgrade_config = {"is_enabled": False}

        self.assertTrue(validate(upgrade_config))

    def test_rule_slz(self):
        assign_group = AlertAssignGroup.objects.create(name="test cache", bk_biz_id=2, priority=1)
        rule = {
            "assign_group_id": assign_group.id,
            "bk_biz_id": 2,
            "user_groups": [29],
            "conditions": [
                {"field": "is_empty_users", "value": ["true"], "method": "eq"},
                {"field": "ip", "value": [""], "method": "eq"},
            ],
            "actions": [
                {
                    "action_type": "notice",
                    "upgrade_config": {"is_enabled": True, "user_groups": [46, 47], "upgrade_interval": 30},
                },
                {"action_type": "itsm", "action_id": 4444},
            ],
            "alert_severity": 2,
            "additional_tags": [{"key": "ip123", "value": "127.0.0.1"}],
            "is_enabled": True,
        }
        rule_slz = AssignRuleSlz(data=rule)
        self.assertTrue(rule_slz.is_valid(raise_exception=True))

    def test_include_same_user_slz(self):
        assign_group = AlertAssignGroup.objects.create(name="test cache", bk_biz_id=2, priority=1)
        rule = {
            "assign_group_id": assign_group.id,
            "bk_biz_id": 2,
            "user_groups": [29],
            "conditions": [{"field": "is_empty_users", "value": ["true"], "method": "eq"}],
            "actions": [
                {
                    "action_type": "notice",
                    "upgrade_config": {"is_enabled": True, "user_groups": [29, 47], "upgrade_interval": 30},
                },
                {"action_type": "itsm", "action_id": 4444},
            ],
            "alert_severity": 2,
            "additional_tags": [{"key": "ip123", "value": "127.0.0.1"}],
            "is_enabled": True,
        }
        rule_slz = AssignRuleSlz(data=rule)
        with self.assertRaises(ValidationError):
            self.assertTrue(rule_slz.is_valid(raise_exception=True))

    def test_batch_update_all_new(self):
        group_info = {"bk_biz_id": 2, "name": "test alert assign group", "priority": 1}
        instance = AlertAssignGroup.objects.create(**group_info)

        batch_update_info = {
            "assign_group_id": instance.id,
            "bk_biz_id": 2,
            "rules": [
                {
                    "user_groups": [1],
                    "conditions": [{"field": "is_empty_users", "value": ["true"], "method": "eq"}],
                    "actions": [
                        {
                            "action_type": ActionPluginType.NOTICE,
                            "upgrade_config": {"is_enabled": True, "user_groups": [2, 3], "upgrade_interval": 30},
                        },
                        {"action_type": ActionPluginType.ITSM, "action_id": 4444},
                    ],
                    "alert_severity": 2,
                    "additional_tags": [{"key": "ip123", "value": "127.0.0.1"}],
                    "bk_biz_id": 2,
                    "is_enabled": True,
                }
            ],
        }

        r = BatchUpdateResource()

        data = r.request(request_data=batch_update_info)
        self.assertEqual(len(data["rules"]), 1)
        batch_update_info["rules"][0]["id"] = data["rules"][0]
        batch_update_info["rules"].append(
            {
                "user_groups": [1],
                "conditions": [{"field": "is_empty_users", "value": ["true"], "method": "eq"}],
                "actions": [
                    {
                        "action_type": ActionPluginType.NOTICE,
                        "upgrade_config": {"is_enabled": True, "user_groups": [2, 3], "upgrade_interval": 30},
                    },
                    {"action_type": ActionPluginType.ITSM, "action_id": 4444},
                ],
                "alert_severity": 2,
                "additional_tags": [{"key": "ip123", "value": "127.0.0.1"}],
                "bk_biz_id": 2,
                "is_enabled": True,
            }
        )
        data = r.request(request_data=batch_update_info)
        self.assertEqual(len(data["rules"]), 2)
        self.assertEqual(len(data["aborted_rules"]), 0)
        rule_actions = AlertAssignRule.objects.filter(id__in=data["rules"]).values("actions")
        self.assertTrue(rule_actions[0]["actions"])

    def test_alert_match_debug(self):
        alert = AlertDocument(
            **{
                "id": "12345",
                "alert_name": "test assign",
                "duration": 60 * 60,
                "severity": 3,
                "strategy_id": 1,
                "status": EventStatus.ABNORMAL,
                "end_time": None,
                "create_time": 1617504052,
                "begin_time": 1617504052,
                "first_anomaly_time": 1617504052,
                "latest_time": 1617504052,
                "dimensions": [{"key": "bk_target_ip", "value": "127.0.0.1"}],
                "event": EventDocument(
                    **{
                        "tags": [{"key": "target", "value": "127.0.0.1"}],
                        "metric": ["123"],
                        "description": "hello,world",
                        "bk_host_id": 1,
                        "ip": "127.0.0.1",
                        "bk_cloud_id": 0,
                        "bk_biz_id": 2,
                    }
                ),
                "extra_info": {"strategy": {}},
            }
        )
        AlertDocument.bulk_create([alert])

        assign_group = AlertAssignGroup.objects.create(name="test cache", bk_biz_id=2, priority=1)
        rule = {
            "user_groups": [1],
            "conditions": [
                {"field": "is_empty_users", "value": ["true"], "method": "eq"},
                {"field": "host.bk_host_id", "value": [1], "method": "eq"},
            ],
            "actions": [
                {
                    "action_type": ActionPluginType.NOTICE,
                    "upgrade_config": {"is_enabled": True, "user_groups": [2, 3], "upgrade_interval": 30},
                },
                {"action_type": ActionPluginType.ITSM, "action_id": 4444},
            ],
            "alert_severity": 2,
            "additional_tags": [{"key": "ip123", "value": "127.0.0.1"}],
            "is_enabled": True,
        }

        req_data = {"assign_group_id": assign_group.id, "bk_biz_id": 2, "priority": 1, "rules": [rule]}
        match_r = MatchDebugResource()
        data = match_r.request(req_data)
        self.assertEqual(len(data[0]["rules"][0]["alerts"]), 1)
        self.assertEqual(data[0]["rules"][0]["is_changed"], True)
        response_alert = data[0]["rules"][0]["alerts"][0]
        self.assertEqual(response_alert["id"], alert.id)
        self.assertEqual(response_alert["origin_severity"], alert.severity)
        self.assertEqual(response_alert["severity"], 2)

        r = BatchUpdateResource()
        data = r.request(request_data=req_data)
        rule.update({"id": data["rules"][0]})
        data = match_r.request(req_data)
        self.assertEqual(data[0]["rules"][0]["is_changed"], False)

        rule.update({"is_enabled": False})
        data = match_r.request(request_data=req_data)
        self.assertEqual(data[0]["rules"][0]["is_changed"], True)

    @skip("skipping")
    def test_rule_search_api(self):
        c = Client()
        url = urllib.parse.quote("/fta/assign/rules/?bk_biz_id=2&assign_group_ids=[1,2]")
        response = c.get(url)
        print(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["result"])
