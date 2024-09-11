# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http:#opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import copy
import time

import mock as _mock
import pytest
from django.conf import settings

from alarm_backends.core.alert import Alert
from alarm_backends.core.cache.action_config import ActionConfigCacheManager
from alarm_backends.core.cache.key import ALERT_SNAPSHOT_KEY
from alarm_backends.service.alert.builder.processor import AlertBuilder
from alarm_backends.service.alert.manager.checker.upgrade import UpgradeChecker
from alarm_backends.service.fta_action.tasks import create_actions
from alarm_backends.tests.service.access.data.config import (
    STRATEGY_CONFIG_V3,
    USER_GROUP_DATA,
    USER_GROUP_WXBOT_DATA,
)
from constants.action import ActionPluginType, AssignMode, UserGroupType
from constants.alert import EventStatus

pytestmark = pytest.mark.django_db

from alarm_backends.core.cache.assign import AssignCacheManager
from alarm_backends.service.fta_action.tasks.alert_assign import (
    AlertAssigneeManager,
    AssignRuleMatch,
    BackendAssignMatchManager,
)
from api.cmdb.define import Business, Host
from bkmonitor.documents import AlertDocument, AlertLog, EventDocument
from bkmonitor.models import (
    ActionConfig,
    ActionInstance,
    ActionPlugin,
    AlertAssignGroup,
    AlertAssignRule,
    ConvergeInstance,
    ConvergeRelation,
    DutyArrange,
    UserGroup,
)

_mock.patch("alarm_backends.service.fta_action.utils.run_converge.delay", return_value=11111).start()
_mock.patch("alarm_backends.service.fta_action.tasks.run_action.apply_async", return_value=11111).start()
_mock.patch("alarm_backends.service.fta_action.tasks.run_webhook_action.apply_async", return_value=11111).start()
_mock.patch("alarm_backends.service.fta_action.tasks.run_action.delay", return_value=11111).start()
_mock.patch("alarm_backends.service.converge.tasks.run_converge.apply_async", return_value=11111).start()
_mock.patch("alarm_backends.service.fta_action.tasks.run_noise_reduce_task.apply_async", return_value=11111).start()


@pytest.fixture()
def biz_mock(mocker):
    return mocker.patch(
        "alarm_backends.core.cache.cmdb.business.BusinessManager.all", return_value=[Business(bk_biz_id=2)]
    )


@pytest.fixture()
def host_mock(mocker):
    return mocker.patch(
        "alarm_backends.core.cache.cmdb.host.HostManager.get",
        return_value=Host(
            bk_host_id=1,
            bk_module_ids=[],
            bk_attr_test="123",
            bk_set_ids=[],
            bk_cloud_id=0,
            bk_biz_id=2,
            topo_link={},
            operator=[],
            bak_operator=[],
            bk_host_innerip="127.0.0.1",
        ),
    )


@pytest.fixture()
def save_alert_snapshot(mocker):
    return mocker.patch("alarm_backends.core.alert.AlertCache.save_alert_snapshot", return_value=(1, 2))


@pytest.fixture()
def save_alert_to_cache(mocker):
    return mocker.patch("alarm_backends.core.alert.AlertCache.save_alert_to_cache", return_value=1)


@pytest.fixture()
def setup():
    ActionInstance.objects.all().delete()
    AlertAssignGroup.objects.all().delete()
    AlertAssignRule.objects.all().delete()
    ConvergeRelation.objects.all().delete()

    assign_group = AlertAssignGroup.objects.create(name="test cache", bk_biz_id=2, priority=1)
    rule = {
        "assign_group_id": assign_group.id,
        "user_groups": [1],
        "conditions": [],
        "actions": [
            {
                "action_type": ActionPluginType.NOTICE,
                "is_enabled": True,
                "upgrade_config": {"is_enabled": True, "user_groups": [2, 1], "upgrade_interval": 30},
            },
            {"action_type": ActionPluginType.ITSM, "action_id": 4444},
        ],
        "alert_severity": 2,
        "additional_tags": [{"key": "ip123", "value": "127.0.0.1"}],
        "bk_biz_id": 2,
        "is_enabled": True,
    }
    yield AlertAssignRule.objects.create(**rule)


@pytest.fixture()
def follow_setup():
    ActionInstance.objects.all().delete()
    AlertAssignGroup.objects.all().delete()
    AlertAssignRule.objects.all().delete()
    ConvergeRelation.objects.all().delete()

    assign_group = AlertAssignGroup.objects.create(name="test cache", bk_biz_id=2, priority=1)
    rule = {
        "assign_group_id": assign_group.id,
        "user_groups": [1],
        "conditions": [],
        "user_type": UserGroupType.FOLLOWER,
        "actions": [
            {
                "action_type": ActionPluginType.NOTICE,
                "is_enabled": True,
                "upgrade_config": {"is_enabled": True, "user_groups": [2, 1], "upgrade_interval": 30},
            },
            {"action_type": ActionPluginType.ITSM, "action_id": 4444},
        ],
        "alert_severity": 2,
        "additional_tags": [{"key": "ip123", "value": "127.0.0.1"}],
        "bk_biz_id": 2,
        "is_enabled": True,
    }
    yield AlertAssignRule.objects.create(**rule)


@pytest.fixture()
def condition_rule():
    ActionInstance.objects.all().delete()
    AlertAssignGroup.objects.all().delete()
    AlertAssignRule.objects.all().delete()
    ConvergeRelation.objects.all().delete()

    assign_group = AlertAssignGroup.objects.create(name="test cache", bk_biz_id=2, priority=1)
    rule = {
        "assign_group_id": assign_group.id,
        "user_groups": [3],
        "conditions": [
            {
                "field": "ip",
                "value": "127.0.0.1",
                "method": "eq",
            }
        ],
        "actions": [
            {
                "action_type": ActionPluginType.NOTICE,
                "is_enabled": True,
                "upgrade_config": {"is_enabled": True, "user_groups": [2, 1], "upgrade_interval": 30},
            },
            {"action_type": ActionPluginType.ITSM, "action_id": 4444},
        ],
        "alert_severity": 1,
        "additional_tags": [{"key": "ip123", "value": "127.0.0.1"}],
        "bk_biz_id": 2,
        "is_enabled": True,
    }
    yield AlertAssignRule.objects.create(**rule)


@pytest.fixture()
def empty_setup():
    ActionInstance.objects.all().delete()
    AlertAssignGroup.objects.all().delete()
    AlertAssignRule.objects.all().delete()
    ConvergeRelation.objects.all().delete()

    assign_group = AlertAssignGroup.objects.create(name="test cache", bk_biz_id=2, priority=1)
    rule = {
        "assign_group_id": assign_group.id,
        "user_groups": [1],
        "conditions": [
            {
                "field": "is_empty_users",
                "value": "true",
                "method": "eq",
            }
        ],
        "actions": [
            {
                "action_type": ActionPluginType.NOTICE,
                "is_enabled": True,
                "upgrade_config": {"is_enabled": True, "user_groups": [2, 1], "upgrade_interval": 30},
            },
            {"action_type": ActionPluginType.ITSM, "action_id": 4444},
        ],
        "alert_severity": 2,
        "additional_tags": [{"key": "ip123", "value": "127.0.0.1"}],
        "bk_biz_id": 2,
        "is_enabled": True,
    }
    yield AlertAssignRule.objects.create(**rule)

    AlertAssignGroup.objects.all().delete()
    AlertAssignRule.objects.all().delete()
    ActionInstance.objects.all().delete()
    ConvergeInstance.objects.all().delete()
    ConvergeRelation.objects.all().delete()


def clear_index():
    for doc in [AlertDocument, AlertLog]:
        ilm = doc.get_lifecycle_manager()
        ilm.es_client.indices.delete(index=doc.Index.name)


@pytest.fixture()
def alert():
    yield AlertDocument(
        **{
            "id": "12345",
            "alert_name": "test assign",
            "dedupe_md5": "68e9f0598d72a4b6de2675d491e5b922",
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
                    "ip": "127.0.0.1",
                    "bk_cloud_id": 0,
                    "bk_biz_id": 2,
                }
            ),
            "extra_info": {"strategy": get_strategy_dict()},
        }
    )


@pytest.fixture()
def user_group_setup():
    UserGroup.objects.all().delete()
    DutyArrange.objects.all().delete()
    duty_arranges = [
        DutyArrange(
            **{
                "user_group_id": 1,
                "order": 1,
                "users": [{"id": "lisa", "display_name": "lisa", "logo": "", "type": "user"}],
            }
        ),
        DutyArrange(
            **{
                "user_group_id": 2,
                "order": 1,
                "users": [{"id": "admin", "display_name": "管理员", "logo": "", "type": "user"}],
            }
        ),
        DutyArrange(
            **{
                "user_group_id": 3,
                "order": 1,
                "users": [
                    {"id": "lisa", "display_name": "lisa", "logo": "", "type": "user"},
                    {"id": "lisa1", "display_name": "lisa1", "logo": "", "type": "user"},
                ],
            }
        ),
    ]
    DutyArrange.objects.bulk_create(duty_arranges)
    group_data = copy.deepcopy(USER_GROUP_DATA)
    for group_id in [1, 2, 3]:
        group_data["id"] = group_id
        user_groups = UserGroup.objects.create(**group_data)
    yield user_groups
    UserGroup.objects.all().delete()
    DutyArrange.objects.all().delete()


@pytest.fixture()
def wxbot_user_group_setup():
    UserGroup.objects.all().delete()
    DutyArrange.objects.all().delete()
    duty_arranges = [
        DutyArrange(
            **{
                "user_group_id": 1,
                "order": 1,
                "users": [{"id": "lisa", "display_name": "lisa", "logo": "", "type": "user"}],
            }
        ),
        DutyArrange(
            **{
                "user_group_id": 2,
                "order": 1,
                "users": [{"id": "admin", "display_name": "管理员", "logo": "", "type": "user"}],
            }
        ),
    ]
    DutyArrange.objects.bulk_create(duty_arranges)
    group_data = copy.deepcopy(USER_GROUP_WXBOT_DATA)
    for group_id in [1, 2]:
        group_data["id"] = group_id
        user_groups = UserGroup.objects.create(**group_data)
    yield user_groups


def init_action_plugin():
    ActionPlugin.objects.all().delete()
    ActionConfig.objects.all().delete()
    ActionPlugin.objects.bulk_create(
        [
            ActionPlugin(
                **{
                    "id": 1,
                    "name": "通知告警",
                    "is_enabled": True,
                    "is_builtin": True,
                    "is_deleted": False,
                    "is_peripheral": False,
                    "plugin_type": "notice",
                    "plugin_key": "notice",
                    "plugin_source": "builtin",
                    "description": "告警通知是平台内置的套餐类型，由平台自身实现。可以对告警信息基于人进行收敛，可以对接不同的告警通知渠道。 "
                    "\n\n* 基于人进行收敛\n* 有告警风暴控制能力\n* 可以定制不同的告警模版\n* 内置基于不同的通知渠道显示的变量\n* "
                    "可以自定义各种通知渠道[查看文档]()\n\n更多[查看文档]()",
                    "config_schema": {
                        "content_template": "发送{{notice_way_display}}告警通知给{{notice_receiver}}{{status_display}}",
                        "content_template_with_url": "达到通知告警的执行条件【{{action_signal}}】，已触发告警通知",
                        "content_template_without_assignee": "达到通知告警的执行条件【{{action_signal}}】，当前通知人员为空",
                        "content_template_shielded": "达到通知告警的执行条件【{{action_signal}}】，因告警已被全局屏蔽或不在通知时间段，忽略通知发送",
                        "content_template_shielded_with_url": "达到通知告警的执行条件【{{action_signal}}】，因告警已被屏蔽忽略通知发送，点击$查看屏蔽策略$",
                    },
                    "backend_config": [{"function": "execute_notify", "name": "发送通知"}],
                }
            ),
            ActionPlugin(
                **{
                    "id": 5,
                    "name": "流程服务",
                    "is_builtin": True,
                    "is_deleted": False,
                    "is_peripheral": True,
                    "plugin_source": "peripheral",
                    "plugin_type": "common",
                    "plugin_key": "itsm",
                    "has_child": True,
                    "description": "",
                    "config_schema": {
                        "template": {
                            "resource_class": "CommonBaseResource",
                            "name": "服务名称",
                            "init_kwargs": {"url": "{{bk_paas_inner_host}}/api/c/compapi/v2/itsm/get_services/"},
                            "request_data_mapping": {"display_role": "BK_FTA"},
                            "resource_module": "api.common.default",
                            "resource_data": "response[*]",
                            "mapping": {
                                "id": "{{id}}",
                                "name": "{{name}}",
                                "url": "{{itsm_site_url}}/#/ticket/create?service_id={{id}}",
                            },
                        },
                        "plugin_url": {
                            "mapping": {
                                "url": "{{itsm_site_url}}/#/project/service/new/basic?project_id=0",
                                "tips": "前往流程服务",
                            }
                        },
                        "detail": {
                            "name": "提单信息",
                            "resource_class": "CommonBaseResource",
                            "resource_module": "api.common.default",
                            "init_kwargs": {"url": "{{bk_paas_inner_host}}/api/c/compapi/v2/itsm/get_service_detail/"},
                            "request_data_mapping": {"service_id": "{{template_id}}"},
                            "resource_data": "response.fields[*]",
                            "mapping": {
                                "key": "{{key}}",
                                "name": "{{name}}",
                                "value": "{{default or ''}}",
                                "placeholder": "{{desc}}",
                            },
                        },
                        "content_template_with_url": "故障工单套餐【{{action_name}}】成功创建单据[{{sn}}]，点击$查看工单详情$",
                        "content_template": "故障工单套餐【{{action_name}}】处理{{status_display}}, 请关注！！",
                    },
                    "backend_config": [
                        {
                            "function": "create_task",
                            "name": "创建单据",
                            "resource_class": "CommonBaseResource",
                            "resource_module": "api.common.default",
                            "init_kwargs": {
                                "url": "{{bk_paas_inner_host}}/api/c/compapi/v2/itsm/create_ticket/",
                                "method": "POST",
                            },
                            "inputs": [
                                {
                                    "key": "service_id",
                                    "value": "execute_config.template_id",
                                    "type": "int",
                                    "format": "jmespath",
                                },
                                {
                                    "key": "fields",
                                    "value": "execute_config.template_detail[].{key: key, value: value}",
                                    "type": "list",
                                    "format": "jmespath",
                                },
                                {"key": "creator", "value": "operator", "type": "string", "format": "jmespath"},
                            ],
                            "outputs": [
                                {"key": "sn", "value": "response.sn", "format": "jmespath"},
                                {"key": "id", "value": "response.id", "format": "jmespath"},
                                {
                                    "key": "url",
                                    "value": "{{itsm_site_url}}#/ticket/detail?id={{id}}",
                                    "format": "jinja2",
                                },
                            ],
                            "need_insert_log": True,
                            "log_template": "流程服务套餐【{{action_name}}】已成功创建工单[{{sn}}]，点击$查看工单详情$",
                        }
                    ],
                }
            ),
        ]
    )
    notice_action_config = {
        "execute_config": {
            "template_detail": {
                "interval_notify_mode": "standard",  # 间隔模式
                "notify_interval": 7200,  # 通知间隔
                "template": [  # 通知模板配置
                    {
                        "signal": "abnormal",
                    }
                ],
            }
        },
        "id": 55555,
        "plugin_id": 1,
        "is_enabled": True,
        "bk_biz_id": 2,
        "name": "test_notice",
    }

    itsm_config = {
        "execute_config": {
            "template_id": 1000043,
            "template_detail": {"title": "123", "name": "test itsm"},
            "timeout": 60,
        },
        "name": "test itsm",
        "desc": "这是描述，这是描述",
        "is_enabled": True,
        "plugin_id": 5,
        "bk_biz_id": 2,
        "id": 4444,
    }

    ActionConfig.objects.bulk_create([ActionConfig(**notice_action_config), ActionConfig(**itsm_config)])


class TestAlertAssignRule:
    def test_assign_cache(self, biz_mock, setup):
        AssignCacheManager.refresh()
        rule = AlertAssignRule.objects.filter(id=setup.id).values()[0]
        rule["group_name"] = "test cache"
        assert biz_mock.call_count == 1
        assert AssignCacheManager.get_assign_priority_by_biz_id(2), [1]
        assert AssignCacheManager.get_assign_groups_by_priority(2, 1) == {setup.assign_group_id}
        assert AssignCacheManager.get_assign_rules_by_group(2, setup.assign_group_id) == [rule]

        # 默认的规则配置的用户类型都是负责人
        assert (
            AssignCacheManager.get_assign_rules_by_group(2, setup.assign_group_id)[0]["user_type"] == UserGroupType.MAIN
        )

    def test_host_cmdb_dimension_matched(self, alert, host_mock):
        rule = {
            "conditions": [
                {
                    "field": "host.bk_cloud_id",
                    "value": "0",
                    "method": "eq",
                },
                {
                    "field": "host.bk_attr_test",
                    "value": "123",
                    "method": "eq",
                },
            ]
        }

        match_obj = AssignRuleMatch(rule, alert=alert)
        m = BackendAssignMatchManager(alert=alert)
        dimensions = m.get_match_dimensions()
        assert match_obj.is_matched(dimensions)
        assert host_mock.call_count == 1

    def test_assign_tags_dimension_not_matched(self, alert):
        rule = {
            "conditions": [
                {
                    "field": "tags.target_1",
                    "value": "127.0.0.1",
                    "method": "eq",
                }
            ]
        }
        match_obj = AssignRuleMatch(rule, alert=alert)
        m = BackendAssignMatchManager(alert=alert)
        dimensions = m.get_match_dimensions()
        assert match_obj.is_matched(dimensions) is False

    def test_assign_alert_name_matched(self, alert):
        rule = {
            "conditions": [
                {
                    "field": "alert.name",
                    "value": "test assign",
                    "method": "eq",
                }
            ]
        }
        match_obj = AssignRuleMatch(rule, alert=alert)
        m = BackendAssignMatchManager(alert=alert)
        dimensions = m.get_match_dimensions()
        assert match_obj.is_matched(dimensions)

    def test_assign_alert_metric_matched(self, alert):
        rule = {
            "conditions": [
                {
                    "field": "alert.metric",
                    "value": ["123"],
                    "method": "eq",
                }
            ]
        }
        match_obj = AssignRuleMatch(rule, alert=alert)
        m = BackendAssignMatchManager(alert=alert)
        dimensions = m.get_match_dimensions()
        assert match_obj.is_matched(dimensions)

    def test_assign_or_condition_matched(self, alert):
        rule = {
            "conditions": [
                {
                    "field": "tags.target",
                    "value": "127.0.0.1",
                    "method": "eq",
                },
                {"field": "tags.target", "value": "127.0.0.2", "method": "eq", "condition": "or"},
            ]
        }
        match_obj = AssignRuleMatch(rule, alert=alert)
        m = BackendAssignMatchManager(alert=alert)
        assert match_obj.is_matched(m.dimensions) is True

    def test_assign_composite_condition_matched(self, alert):
        rule = {
            "conditions": [
                {
                    "field": "tags.target",
                    "value": "127.0.0.2",
                    "method": "eq",
                },
                {"field": "tags.target", "value": "127.0.0.1", "method": "eq", "condition": "or"},
                {"field": "alert_name", "value": "test", "method": "eq", "condition": "and"},
            ]
        }
        match_obj = AssignRuleMatch(rule, alert=alert)
        m = BackendAssignMatchManager(alert=alert)
        assert match_obj.is_matched(m.dimensions) is False

    def test_ip_matched(self, alert):
        rule = {
            "conditions": [
                {
                    "field": "bk_target_ip",
                    "value": "127.0.0.1",
                    "method": "eq",
                }
            ]
        }
        match_obj = AssignRuleMatch(rule, alert=alert)
        m = BackendAssignMatchManager(alert=alert)
        assert match_obj.is_matched(m.dimensions) is True

    def test_host_attr_matched(self, alert):
        rule = {
            "conditions": [
                {
                    "field": "host.bk_target_ip",
                    "value": ["127.0.0.1"],
                    "method": "eq",
                }
            ]
        }
        match_obj = AssignRuleMatch(rule, alert=alert)
        assert match_obj.is_matched({"host.bk_target_ip": ["127.0.0.1", "127.0.0.2"]}) is True

        rule = {
            "conditions": [
                {
                    "field": "host.bk_host_id",
                    "value": ["1"],
                    "method": "eq",
                }
            ]
        }
        match_obj = AssignRuleMatch(rule, alert=alert)
        assert match_obj.is_matched({"host.bk_host_id": [1, 2]}) is True

    def test_is_changed(self):
        rule = {
            "id": 1,
            "user_groups": [1, 2],
            "conditions": [
                {
                    "field": "bk_target_ip",
                    "value": "127.0.0.1",
                    "method": "eq",
                }
            ],
        }
        snap_rule = copy.deepcopy(rule)
        # no_changed
        snap_rule["user_groups"] = [2, 1]
        assert AssignRuleMatch(rule, assign_rule_snap=snap_rule).is_changed is False

        # new
        assert AssignRuleMatch(rule).is_changed
        assert AssignRuleMatch(rule).is_new

        # changed
        snap_rule["user_groups"] = [1]
        assert AssignRuleMatch(rule, assign_rule_snap=snap_rule).is_changed

    def test_is_upgrade(self, alert):
        rule = {
            "id": 1,
            "user_groups": [1, 2],
            "conditions": [],
            "actions": [
                {
                    "action_type": ActionPluginType.NOTICE,
                    "is_enabled": True,
                    "upgrade_config": {"is_enabled": True, "user_groups": [3, 4, 5], "upgrade_interval": 30},
                }
            ],
        }

        assert AssignRuleMatch(rule, assign_rule_snap=rule).upgrade_rule.is_upgrade_enable
        assert AssignRuleMatch(rule, assign_rule_snap=rule).is_changed is False
        assert AssignRuleMatch(rule, assign_rule_snap=rule).get_upgrade_user_group() == []

    def test_empty_notice_group_true(self, alert):
        rule = {
            "conditions": [
                {
                    "field": "is_empty_users",
                    "value": "true",
                    "method": "eq",
                }
            ]
        }
        rule_obj = AssignRuleMatch(rule)
        m = BackendAssignMatchManager(alert=alert)
        assert rule_obj.is_matched(m.get_match_dimensions())

    def test_empty_notice_group_false_with_chat_id(self, alert, wxbot_user_group_setup):
        rule = {
            "conditions": [
                {
                    "field": "is_empty_users",
                    "value": "false",
                    "method": "eq",
                }
            ]
        }
        rule_obj = AssignRuleMatch(rule)
        m = AlertAssigneeManager(
            alert=alert,
            notice_user_groups=[wxbot_user_group_setup.id],
            assign_mode=[AssignMode.BY_RULE, AssignMode.ONLY_NOTICE],
        )
        assert rule_obj.is_matched(m.match_manager.get_match_dimensions())

    def test_empty_value_false(self, alert):
        rule = {
            "conditions": [
                {
                    "field": "ip",
                    "value": [""],
                    "method": "eq",
                }
            ]
        }
        rule_obj = AssignRuleMatch(rule)
        m = BackendAssignMatchManager(alert=alert)
        assert not rule_obj.is_matched(m.get_match_dimensions())

    def test_empty_value_true(self, alert):
        rule = {
            "conditions": [
                {
                    "field": "ip",
                    "value": [""],
                    "method": "eq",
                }
            ]
        }
        rule_obj = AssignRuleMatch(rule)
        alert.event.ip = ""
        m = BackendAssignMatchManager(alert=alert)

        assert rule_obj.is_matched(m.get_match_dimensions())

    def test_empty_notice_group_false(self, alert):
        rule = {
            "conditions": [
                {
                    "field": "is_empty_users",
                    "value": "true",
                    "method": "eq",
                }
            ]
        }
        rule_obj = AssignRuleMatch(rule)
        m = BackendAssignMatchManager(alert=alert)
        assert rule_obj.is_matched(m.get_match_dimensions())

        m = BackendAssignMatchManager(alert=alert, notice_users=["admin"])
        assert rule_obj.is_matched(m.get_match_dimensions()) is False


def get_strategy_dict():
    strategy_dict = copy.deepcopy(STRATEGY_CONFIG_V3)
    strategy_dict["notice"]["options"]["assign_mode"] = [AssignMode.BY_RULE]
    strategy_dict["notice"]["options"]["noise_reduce_config"] = {}
    return strategy_dict


@pytest.fixture()
def init_configs():
    clear_index()
    init_action_plugin()
    ALERT_SNAPSHOT_KEY.client.flushall()
    AssignCacheManager.refresh()
    AssignCacheManager.clear()
    ActionConfigCacheManager.refresh()


class TestAssignManager:
    def test_by_assign(self, alert):
        rule = {
            "id": 1,
            "user_groups": [1],
            "conditions": [],
            "actions": [
                {
                    "action_type": ActionPluginType.NOTICE,
                    "is_enabled": True,
                    "upgrade_config": {"is_enabled": True, "user_groups": [1], "upgrade_interval": 30},
                },
                {"action_type": ActionPluginType.ITSM, "action_id": 4444},
            ],
            "alert_severity": 2,
            "additional_tags": [{"key": "ip", "value": "127.0.0.1"}],
        }
        rule_obj = AssignRuleMatch(rule)
        assert rule_obj.itsm_action == {"action_type": ActionPluginType.ITSM, "action_id": 4444}
        assert rule_obj.alert_severity == 2
        assert rule_obj.additional_tags == [{"key": "ip", "value": "127.0.0.1"}]
        assert rule_obj.user_type == UserGroupType.MAIN

    def test_change_alert_severity(self, setup, alert, user_group_setup, biz_mock, init_configs):
        assert ActionConfigCacheManager.get_action_config_by_id(4444)

        AlertDocument.bulk_create([alert])
        assert biz_mock.call_count == 1
        actions0 = create_actions(0, "abnormal", alerts=[alert])

        new_alert = AlertDocument.get(id=alert.id)
        assert len(actions0) == 3
        assert new_alert.severity == 2
        assert new_alert.extra_info.severity_source == AssignMode.BY_RULE

    def test_notice_upgrade(self, setup, alert, user_group_setup, biz_mock, init_configs):
        """
        测试告警分派的告警升级
        :param setup:
        :param alert:
        :param biz_mock:
        :param init_configs:
        :return:
        """
        alert.duration = 50 * 60
        alert.extra_info["rule_snaps"] = {
            setup.id: {"user_groups": setup.user_groups, "conditions": setup.conditions, "id": setup.id}
        }
        print(alert.extra_info["rule_snaps"])
        AlertDocument.bulk_create([alert])
        actions = create_actions(0, "abnormal", alerts=[alert], notice_type="upgrade")
        new_alert = AlertDocument.get(id=alert.id)
        assert len(actions) == 2
        p_ai = ActionInstance.objects.get(is_parent_action=True, id__in=actions)
        p_ai.inputs["notify_info"].pop("wxbot_mention_users", None)
        assert p_ai.inputs["notify_info"] == {'mail': ['admin']}
        assert new_alert.severity == 2
        assert new_alert.extra_info.severity_source == AssignMode.BY_RULE
        assert p_ai.get_content()["text"], '达到通知告警的执行条件【告警升级】，已出发告警'

        alert.extra_info = new_alert.extra_info
        alert.supervisor = new_alert.supervisor
        alert.extra_info["rule_snaps"][str(setup.id)]["last_upgrade_time"] = int(time.time()) - 31 * 60
        AlertDocument.bulk_create([alert], action="update")
        ActionInstance.objects.all().delete()
        new_actions = create_actions(0, "abnormal", alerts=[alert], notice_type="upgrade")
        assert len(new_actions) == 2
        p_ai = ActionInstance.objects.get(is_parent_action=True, id__in=new_actions)
        assert set(p_ai.inputs["notify_info"]["mail"]) == {"lisa"}
        assert p_ai.inputs["notice_type"] == "upgrade"
        assert p_ai.need_poll is False

        new_alert = AlertDocument.get(id=alert.id)
        assert len(new_alert.supervisor) == 2

    def test_notice_reupgrade(self, setup, alert, user_group_setup, biz_mock, init_configs):
        """
        分派规则下的再次升级测试
        :param setup:
        :param alert:
        :param biz_mock:
        :param init_configs:
        :return:
        """
        alert.duration = 50 * 60
        alert.extra_info["rule_snaps"] = {
            setup.id: {
                "user_groups": setup.user_groups,
                "conditions": setup.conditions,
                "id": setup.id,
                "last_group_index": 0,
                "last_upgrade_time": int(time.time()) - 31 * 60,
            }
        }
        AlertDocument.bulk_create([alert])
        assert biz_mock.call_count == 1
        actions = create_actions(0, "abnormal", alerts=[alert], notice_type="upgrade")
        new_alert = AlertDocument.get(id=alert.id)
        assert len(actions) == 2
        p_ai = ActionInstance.objects.get(is_parent_action=True, id__in=actions)
        p_ai.inputs["notify_info"].pop("wxbot_mention_users", None)
        assert p_ai.inputs["notify_info"] == {'mail': ['lisa']}
        assert new_alert.severity == 2
        assert new_alert.extra_info.severity_source == AssignMode.BY_RULE

        # 升级结束，后面不再继续发通知了
        alert.extra_info = new_alert.extra_info
        alert.appointee = new_alert.appointee
        AlertDocument.bulk_create([alert], action="update")
        ActionInstance.objects.all().delete()
        new_actions = create_actions(0, "abnormal", alerts=[alert], notice_type="upgrade")
        assert len(new_actions) == 0

    def test_normal_notice(self, setup, alert, user_group_setup, biz_mock, init_configs):
        """
        原生测试
        """
        alert.extra_info.strategy.notice["options"]["assign_mode"] = [AssignMode.ONLY_NOTICE]
        AlertDocument.bulk_create([alert])
        assert biz_mock.call_count == 1
        actions = create_actions(alert.extra_info.strategy["id"], "abnormal", alerts=[alert])
        assert len(actions) == 2
        p_ai = ActionInstance.objects.get(is_parent_action=True, id__in=actions)
        p_ai.inputs["notify_info"].pop("wxbot_mention_users", None)
        assert p_ai.inputs["notify_info"] == {'weixin': ['lisa']}
        assert alert.severity == 3

    def test_ignore_origin_notice(self, condition_rule, alert, user_group_setup, biz_mock, init_configs):
        """
        测试适配到告警条件之后原来的告警不会产生
        """
        alert.extra_info.strategy.notice["options"]["assign_mode"] = [AssignMode.ONLY_NOTICE, AssignMode.BY_RULE]
        alert.severity = 1
        alert.appointee = ['lisa', 'lisa1']
        AlertDocument.bulk_create([alert])
        assert biz_mock.call_count == 1
        actions = create_actions(0, "abnormal", alerts=[alert])
        assert len(actions) == 4
        p_ai = ActionInstance.objects.get(is_parent_action=True, id__in=actions)
        p_ai.inputs["notify_info"].pop("wxbot_mention_users", None)
        assert p_ai.inputs["notify_info"]['voice'] == [['lisa', 'lisa1']]
        new_alert = AlertDocument.get(id=alert.id)
        assert new_alert.appointee == ["lisa", "lisa1"]
        assert new_alert.severity == 1

    def test_default_assign_notice(self, setup, alert, user_group_setup, biz_mock, init_configs):
        """
        原生测试
        """
        alert.extra_info.strategy = {}
        AlertDocument.bulk_create([alert])
        assert biz_mock.call_count == 1
        actions = create_actions(0, "abnormal", alerts=[alert])
        assert len(actions) == 3
        p_ai = ActionInstance.objects.get(is_parent_action=True, id__in=actions)
        p_ai.inputs["notify_info"].pop("wxbot_mention_users", None)
        assert p_ai.inputs["notify_info"] == {'mail': ['lisa']}
        new_alert = AlertDocument.get(id=alert.id)
        assert new_alert.severity == 2
        assert new_alert.assign_tags == setup.additional_tags

    def test_default_assign_follower_notice(self, follow_setup, alert, user_group_setup, biz_mock, init_configs):
        """
        原生测试
        """
        alert.extra_info.strategy = {}
        AlertDocument.bulk_create([alert])
        assert biz_mock.call_count == 1
        actions = create_actions(0, "abnormal", alerts=[alert])
        assert len(actions) == 3
        p_ai = ActionInstance.objects.get(is_parent_action=True, id__in=actions)
        p_ai.inputs["notify_info"].pop("wxbot_mention_users", None)
        p_ai.inputs["follow_notify_info"].pop("wxbot_mention_users", None)
        assert p_ai.inputs["follow_notify_info"] == {'mail': ['lisa']}
        new_alert = AlertDocument.get(id=alert.id)
        assert new_alert.severity == 2
        assert new_alert.assign_tags == follow_setup.additional_tags
        assert new_alert.follower == ["lisa"]

    def test_assign_follower_with_appointee_notice(self, follow_setup, alert, user_group_setup, biz_mock, init_configs):
        """
        原生测试
        """
        alert.extra_info.strategy = {}
        alert.appointee = ["admin1", "admin2"]
        AlertDocument.bulk_create([alert])
        assert biz_mock.call_count == 1
        actions = create_actions(0, "abnormal", alerts=[alert])
        # 5个人通知，两个负责人需要通知， 一个lisa的邮件通知，两个企业微信通知
        assert len(actions) == 5
        p_ai = ActionInstance.objects.get(is_parent_action=True, id__in=actions)
        p_ai.inputs["notify_info"].pop("wxbot_mention_users", None)
        p_ai.inputs["follow_notify_info"].pop("wxbot_mention_users", None)
        assert p_ai.inputs["follow_notify_info"] == {'mail': ['lisa']}
        assert p_ai.inputs["notify_info"] == {'mail': ['admin1', "admin2"]}
        new_alert = AlertDocument.get(id=alert.id)
        assert new_alert.severity == 2
        assert new_alert.assign_tags == follow_setup.additional_tags
        assert new_alert.follower == ["lisa"]
        assert new_alert.appointee == ["admin1", "admin2"]

    def test_default_assign_without_notice(self, alert, user_group_setup, biz_mock, init_configs):
        """
        原生测试
        """
        alert.extra_info.strategy = {}
        AlertDocument.bulk_create([alert])
        assert biz_mock.call_count == 1
        actions = create_actions(0, "abnormal", alerts=[alert])
        assert len(actions) == 0

    def test_enrich_rule_info(self, setup, alert, biz_mock, init_configs):
        processor = AlertBuilder()
        alert_obj = Alert(data=alert.to_dict())
        alert_obj._is_new = True
        enriched_alerts = processor.enrich_alerts([alert_obj])
        enriched_alert = enriched_alerts[0].to_document()
        assert enriched_alert.severity == 2
        assert alert_obj.severity_source == AssignMode.BY_RULE
        assert enriched_alert.assign_tags == setup.additional_tags
        assert len(enriched_alerts[0].top_event["tags"]) == 2

    def test_enrich_rule_info_by_empty_setup_false(self, empty_setup, alert, biz_mock, user_group_setup, init_configs):
        """
        告警通知人不为空适配
        """
        processor = AlertBuilder()
        alert_obj = Alert(data=alert.to_dict())
        alert_obj._is_new = True
        alert.strategy["notice"]["options"]["assign_mode"] = [AssignMode.ONLY_NOTICE, AssignMode.BY_RULE]
        alert.strategy.get("notice", {}).update(user_groups=[user_group_setup.id])
        enriched_alerts = processor.enrich_alerts([alert_obj])
        enriched_alert = enriched_alerts[0].to_document()
        assert enriched_alert.severity == 3
        assert not alert_obj.severity_source

    def test_enrich_rule_info_by_empty_wxbot_setup_false(
        self, empty_setup, alert, biz_mock, wxbot_user_group_setup, init_configs
    ):
        """
        告警通知人不为空适配(机器人)
        """
        processor = AlertBuilder()
        alert_obj = Alert(data=alert.to_dict())
        alert_obj._is_new = True
        # 测试通知人为空，首先需要有通知配置
        alert.strategy["notice"]["options"]["assign_mode"] = [AssignMode.ONLY_NOTICE, AssignMode.BY_RULE]
        alert.strategy.get("notice", {}).update(user_groups=[wxbot_user_group_setup.id])
        enriched_alerts = processor.enrich_alerts([alert_obj])
        enriched_alert = enriched_alerts[0].to_document()
        assert enriched_alert.severity == 3
        assert not alert_obj.severity_source

    def test_enrich_rule_info_by_empty_setup(self, empty_setup, alert, biz_mock, init_configs):
        """
        告警通知组为空
        """
        processor = AlertBuilder()
        alert_obj = Alert(data=alert.to_dict())
        alert_obj._is_new = True
        alert.strategy.get("notice", {}).update(user_groups=[])
        enriched_alerts = processor.enrich_alerts([alert_obj])
        enriched_alert = enriched_alerts[0].to_document()
        assert enriched_alert.severity == 2
        assert alert_obj.severity_source == AssignMode.BY_RULE

    def test_enrich_rule_info_default(self, setup, alert, biz_mock, init_configs):
        processor = AlertBuilder()
        alert.extra_info.strategy.notice["options"]["assign_mode"] = [AssignMode.BY_RULE]
        alert_obj = Alert(data=alert.to_dict())
        alert_obj._is_new = True
        enriched_alerts = processor.enrich_alerts([alert_obj])
        enriched_alert = enriched_alerts[0].to_document()
        assert enriched_alert.severity == 2
        assert alert_obj.severity_source == AssignMode.BY_RULE

    def test_enrich_rule_info_without_rule(self, setup, alert):
        processor = AlertBuilder()
        alert.extra_info.strategy.notice["options"]["assign_mode"] = [AssignMode.ONLY_NOTICE]
        alert_obj = Alert(data=alert.to_dict())
        alert_obj._is_new = True
        enriched_alerts = processor.enrich_alerts([alert_obj])
        enriched_alert = enriched_alerts[0].to_document()
        assert enriched_alert.severity == 3
        assert alert_obj.severity_source == ""


@pytest.fixture()
def create_actions_delay(mocker):
    return mocker.patch("alarm_backends.service.fta_action.tasks.create_actions.delay", return_value=(1, 2))


class TestUpgradeChecker:
    def test_origin_notice_upgrade(
        self, setup, alert, biz_mock, init_configs, create_actions_delay, save_alert_snapshot, save_alert_to_cache
    ):
        """
        测试告警升级
        :param setup:
        :param alert:
        :param biz_mock:
        :param init_configs:
        :return:
        """
        # 没有升级的情况
        alert.strategy["notice"]["options"]["assign_mode"] = [AssignMode.ONLY_NOTICE]
        alert.strategy["notice"]["options"].update(
            {"upgrade_config": {"is_enabled": True, "user_groups": [2, 1], "upgrade_interval": 30}}
        )
        AlertDocument.bulk_create([alert])
        # 没有升级的情况
        UpgradeChecker(alerts=[Alert(alert.to_dict())]).check_all()
        assert create_actions_delay.call_count == 0

        # 第一次升级
        alert.duration = 50 * 60
        alert.first_anomaly_time = int(time.time()) - alert.duration
        alert.latest_time = int(time.time())
        alert.extra_info["upgrade_notice"] = {}
        UpgradeChecker(alerts=[Alert(alert.to_dict())]).check_all()
        assert create_actions_delay.call_count == 1

        create_actions(alert.strategy_id, "abnormal", alerts=[alert], notice_type="upgrade")

        new_alert = AlertDocument.get(alert.id)
        assert new_alert.extra_info.upgrade_notice["last_group_index"] == 0

        # 第二次升级
        alert.extra_info = new_alert.extra_info
        alert.latest_time = int(time.time())
        alert.extra_info.upgrade_notice["last_upgrade_time"] = alert.latest_time - 30 * 60
        AlertDocument.bulk_create([alert], action="update")

        UpgradeChecker(alerts=[Alert(alert.to_dict())]).check_all()
        assert create_actions_delay.call_count == 2
        create_actions(alert.strategy_id, "abnormal", alerts=[alert], notice_type="upgrade")
        new_alert = AlertDocument.get(alert.id)
        assert new_alert.extra_info.upgrade_notice["last_group_index"] == 1

        # 时间间隔, 检测不会推送任务
        alert.extra_info = new_alert.extra_info
        alert.latest_time = int(time.time())
        alert.extra_info.upgrade_notice["last_upgrade_time"] = alert.latest_time - 30 * 60
        UpgradeChecker(alerts=[Alert(alert.to_dict())]).check_all()
        assert create_actions_delay.call_count == 2

        AlertDocument.bulk_create([alert], action="update")
        new_actions = create_actions(alert.strategy_id, "abnormal", alerts=[alert], notice_type="upgrade")
        assert len(new_actions) == 0

    def test_rule_upgrade(self, setup, alert, user_group_setup, biz_mock, init_configs, create_actions_delay):
        """
        再次升级测试
        :param setup:
        :param alert:
        :param biz_mock:
        :param init_configs:
        :return:
        """
        alert.duration = 50 * 60
        alert.extra_info["rule_snaps"] = {
            str(setup.id): {
                "user_groups": setup.user_groups,
                "conditions": setup.conditions,
                "id": setup.id,
                "last_group_index": 0,
                "last_upgrade_time": int(time.time()) - 31 * 60,
            }
        }
        AlertDocument.bulk_create([alert])
        assert biz_mock.call_count == 1
        # 再次升级
        UpgradeChecker(alerts=[Alert(alert.to_dict())]).check_all()
        assert create_actions_delay.call_count == 1
        create_actions(0, "abnormal", alerts=[alert], notice_type="upgrade")
        new_alert = AlertDocument.get(id=alert.id)
        assert new_alert.extra_info.rule_snaps[str(setup.id)]["last_group_index"] == 1

        # 不升级
        alert.extra_info = new_alert.extra_info
        alert.latest_time = int(time.time())
        alert.extra_info.rule_snaps[str(setup.id)]["last_upgrade_time"] = alert.latest_time - 30 * 60
        AlertDocument.bulk_create([alert], action="update")
        UpgradeChecker(alerts=[Alert(alert.to_dict())]).check_all()
        assert create_actions_delay.call_count == 1
        new_actions = create_actions(alert.strategy_id, "abnormal", alerts=[alert], notice_type="upgrade")
        assert len(new_actions) == 0

    def test_rule_upgrade_qos(self, setup, alert, user_group_setup, biz_mock, init_configs, create_actions_delay):
        """
        再次升级测试
        :param setup:
        :param alert:
        :param biz_mock:
        :param init_configs:
        :return:
        """
        alert.duration = 50 * 60
        alert.first_anomaly_time = int(time.time()) - alert.duration
        alert.latest_time = int(time.time())
        AlertDocument.bulk_create([alert])
        assert biz_mock.call_count == 1
        # 第一次升级
        UpgradeChecker(alerts=[Alert(alert.to_dict())]).check_all()
        assert create_actions_delay.call_count == 1
        create_actions(0, "abnormal", alerts=[alert], notice_type="upgrade")
        new_alert = AlertDocument.get(id=alert.id)
        assert new_alert.extra_info.rule_snaps[str(setup.id)]["last_group_index"] == 0

        # 第二次升级被QOS
        alert.extra_info = new_alert.extra_info
        alert.latest_time = int(time.time())
        alert.extra_info.rule_snaps[str(setup.id)]["last_upgrade_time"] = alert.latest_time - 30 * 60
        AlertDocument.bulk_create([alert], action="update")
        settings.QOS_DROP_ACTION_THRESHOLD = 1
        UpgradeChecker(alerts=[Alert(alert.to_dict())]).check_all()
        assert create_actions_delay.call_count == 2
        time.sleep(1)
        new_actions = create_actions(0, "abnormal", alerts=[alert], notice_type="upgrade")
        new_alert = AlertDocument.get(id=alert.id)
        assert new_alert.extra_info.rule_snaps[str(setup.id)]["last_group_index"] == 1
        assert len(new_actions) == 0
        log_search_object = (
            AlertLog.search(all_indices=True).filter("term", alert_id=alert.id).filter("term", op_type="ACTION")
        )
        assert len(log_search_object.execute().hits) == 2
        settings.QOS_DROP_ACTION_THRESHOLD = 100
