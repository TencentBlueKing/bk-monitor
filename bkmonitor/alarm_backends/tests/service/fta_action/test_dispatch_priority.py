"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fakeredis import FakeRedis

from alarm_backends.core.cache.assign import AssignCacheManager
from alarm_backends.service.alert.manager.checker.upgrade import UpgradeChecker
from alarm_backends.service.fta_action.tasks.alert_assign import AlertAssigneeManager, BackendAssignMatchManager
from bkmonitor.action.alert_assign import AlertAssignMatchManager
from bkmonitor.models import AlertAssignGroup, AlertAssignRule
from bkmonitor.utils.cache import InstanceCache
from bkmonitor.utils.local import local
from constants.action import AssignMode


def rule(rule_id, priority, *actions, **fields):
    return {
        "id": rule_id,
        "assign_group_id": priority,
        "priority": priority,
        "group_name": str(priority),
        "conditions": [],
        "actions": list(actions),
        "is_enabled": True,
        "user_groups": [],
        **fields,
    }


def action(kind, **options):
    return {"action_type": kind, "is_enabled": True, **options}


def alert():
    return SimpleNamespace(
        id="alert",
        alert_name="test",
        severity=3,
        strategy=None,
        labels=[],
        dimensions=[],
        origin_alarm=None,
        extra_info={},
        assign_tags=[],
        duration=600,
        event=SimpleNamespace(bk_biz_id=2, metric=[], tags=[], bk_host_id=7),
    )


def run_preview(tiers, **options):
    manager = AlertAssignMatchManager(alert(), group_rules=tiers, **options)
    manager.run_match()
    return manager


def cache_rules(monkeypatch, tiers):
    cache = Mock()
    manager = AssignCacheManager
    priorities = [rules[0]["priority"] for rules in tiers]
    values = {manager.BIZ_CACHE_KEY_TEMPLATE.format(bk_biz_id=2): json.dumps(priorities)}
    for priority, rules in zip(priorities, tiers):
        values[manager.PRIORITY_CACHE_KEY_TEMPLATE.format(bk_biz_id=2, priority=priority)] = json.dumps([priority])
        values[manager.GROUP_CACHE_KEY_TEMPLATE.format(bk_biz_id=2, group_id=priority)] = json.dumps(rules)
    cache.get.side_effect = values.get
    cache.mget.side_effect = lambda keys: [values.get(key) for key in keys]
    monkeypatch.setattr(local, "assign_cache", {})
    monkeypatch.setattr(manager, "cache", cache)
    return cache, values


@pytest.mark.parametrize("runtime", [False, True])
def test_each_type_wins_its_own_tier(monkeypatch, runtime):
    tiers = [
        [
            rule(1, 100, action("notice"), user_groups=[1], alert_severity=2),
            rule(2, 100, action("notice"), user_type="follower", user_groups=[2]),
            rule(3, 100, action("noise")),
        ],
        [
            rule(
                4, 90, action("ai_analysis", user_groups=[5, 6]), action("notice"), user_groups=[90], alert_severity=1
            ),
            rule(5, 90, action("ai_analysis", user_groups=[6, 7])),
        ],
        [
            rule(
                6,
                80,
                action("ai_analysis", user_groups=[8]),
                action("notice"),
                {"action_type": "itsm", "action_id": 42},
                user_groups=[4],
            )
        ],
        [rule(7, 70, action("noise"))],
    ]
    if runtime:
        cache, _ = cache_rules(monkeypatch, tiers)
        manager = BackendAssignMatchManager(alert(), cmdb_attrs={})
        manager.run_match()
        assert cache.mget.call_count == 4  # 首层和后续批次各读一次目录、一次规则。
    else:
        manager = run_preview(tiers, explain=True)
    result = manager.matched_rule_info
    assert result["notice_appointees"] == [1]
    assert result["follow_groups"] == [2]
    assert result["itsm_actions"] == {42: [4]}
    assert result["dispatch_result"] == {"ai_analysis": {"user_groups": [5, 6, 7]}, "noise": False}
    assert result["severity"] == 2
    assert set(result["rule_snaps"]) == {"1", "2", "4", "5", "6"}
    audit = {hit["rule_id"]: hit for hit in result["matched_rules"]}
    assert audit[3]["suppressed_actions"] == {"noise": "ordinary_at_same_priority"}
    assert audit[6]["action_types"] == ["itsm"]
    assert audit[6]["suppressed_actions"] == {
        "ai_analysis": "higher_priority_same_type",
        "notice": "higher_priority_same_type",
    }
    if not runtime:
        assert audit[7]["suppressed_actions"] == {"noise": "higher_priority_ordinary"}


def test_high_noise_stops_runtime_and_explains_lower_candidates_in_preview(monkeypatch):
    tiers = [
        [rule(1, 100, action("noise")), rule(2, 100, action("itsm", action_id=7, is_enabled=False))],
        [rule(3, 90, action("notice"), action("ai_analysis", user_groups=[4]), user_groups=[3])],
    ]
    cache, _ = cache_rules(monkeypatch, tiers)
    runtime = BackendAssignMatchManager(alert(), cmdb_attrs={})
    runtime.run_match()
    assert cache.mget.call_count == 2
    assert not any("priority_2_90" in key for call in cache.mget.call_args_list for key in call.args[0])
    preview = run_preview(tiers, explain=True)
    for manager in (runtime, preview):
        assert [match.rule_id for match in manager.matched_rules] == [1]
        assert manager.matched_rule_info["dispatch_result"] == {"ai_analysis": None, "noise": True}
        assert not manager.get_notice_user_groups() and not manager.get_itsm_actions()
    assert preview.matched_rule_info["matched_rules"][-1]["suppressed_actions"] == {
        "notice": "noise_won",
        "ai_analysis": "noise_won",
    }


def test_cold_tiers_use_bulk_reads_and_warm_alert_reuses_global_and_business_rules(monkeypatch):
    tiers = [[rule(n, n, action("notice"), user_groups=[n])] for n in range(5, 0, -1)]
    cache, values = cache_rules(monkeypatch, tiers)
    config = AssignCacheManager
    values[config.BIZ_CACHE_KEY_TEMPLATE.format(bk_biz_id=0)] = "[1]"
    values[config.PRIORITY_CACHE_KEY_TEMPLATE.format(bk_biz_id=0, priority=1)] = "[91]"
    global_rule = rule(91, 1, action("ai_analysis", user_groups=[9]))
    values[config.GROUP_CACHE_KEY_TEMPLATE.format(bk_biz_id=0, group_id=91)] = json.dumps([global_rule])
    for _ in range(2):
        manager = BackendAssignMatchManager(alert(), cmdb_attrs={})
        manager.run_match()
        assert manager.matched_rule_info["notice_appointees"] == [5]
        assert manager.matched_rule_info["dispatch_result"]["ai_analysis"] == {"user_groups": [9]}
        assert config.get_assign_groups_by_priority(2, 1) == {1, 91}
        assert config.get_assign_rules_by_group(2, 91) == [global_rule]
    assert cache.get.call_count == 3  # 全局优先级一次，业务优先级按既有契约每条告警读一次。
    assert cache.mget.call_count == 4  # 首条告警两批各两次；第二条告警全量复用。


def test_in_process_cache_supports_the_same_bulk_lookup(monkeypatch):
    _, values = cache_rules(monkeypatch, [[rule(1, 10, action("noise"))]])
    cache = InstanceCache()
    for key, value in values.items():
        cache.set(key, value)
    monkeypatch.setattr(AssignCacheManager, "cache", cache)
    manager = BackendAssignMatchManager(alert(), cmdb_attrs={})
    manager.run_match()
    assert manager.matched_rule_info["dispatch_result"]["noise"]


@pytest.mark.parametrize("notice_actions", [[], [action("notice", is_enabled=False)]])
def test_legacy_itsm_requires_enabled_notice_to_use_rule_groups(notice_actions):
    itsm = rule(1, 20, {"action_type": "itsm", "action_id": 42}, *notice_actions, user_groups=[1])
    manager = run_preview([[itsm]])
    assert manager.matched_rules[0].overrides_notice
    assert not manager.get_notice_user_groups()
    assert manager.get_itsm_actions() == {42: []}

    manager = run_preview([[itsm], [rule(2, 10, action("notice"), user_groups=[2])]])
    assert manager.get_notice_user_groups() == {2}
    assert manager.get_itsm_actions() == {42: []}


def test_pure_ai_does_not_override_strategy_notice_or_claim_legacy_attributes():
    ai = rule(1, 30, action("ai_analysis", user_groups=[]), user_groups=[8])
    manager = run_preview([[ai]])
    assert manager.matched_rule_info["dispatch_result"] == {"ai_analysis": {"user_groups": []}, "noise": False}
    assert not manager.matched_rules[0].overrides_notice
    assert manager.matched_rule_info["severity"] == 0
    assert not manager.get_notice_user_groups()
    receiver = AlertAssigneeManager.__new__(AlertAssigneeManager)
    receiver.is_matched = True
    receiver.overrides_notice = manager.matched_rules[0].overrides_notice
    receiver.origin_notice_users_object = Mock()
    receiver.origin_notice_users_object.get_assignee_by_user_groups.return_value = ["strategy-owner"]
    assert receiver.get_assignees() == ["strategy-owner"]

    tag = {"key": "team", "value": "storage"}
    manager = run_preview(
        [[ai], [rule(2, 20, additional_tags=[tag, {"key": "is_noise", "value": "true"}], alert_severity=1)]]
    )
    assert manager.matched_rule_info["additional_tags"] == [tag]
    assert manager.matched_rule_info["severity"] == 1


def test_ai_result_uses_groups_from_effective_ai_rules_only():
    manager = run_preview(
        [
            [rule(1, 100, action("notice"), user_groups=[1])],
            [
                rule(2, 90, action("ai_analysis"), user_groups=[2, 3]),
                rule(3, 90, action("ai_analysis", user_groups=[3, 4]), user_groups=[5]),
                rule(4, 90, action("ai_analysis", user_groups=[]), user_groups=[6]),
                rule(5, 90, action("ai_analysis")),
            ],
            [rule(6, 80, action("ai_analysis"), user_groups=[7])],
        ]
    )
    assert manager.get_notice_user_groups() == {1}
    assert manager.matched_rule_info["dispatch_result"]["ai_analysis"] == {"user_groups": [2, 3, 4]}


def test_skips_disabled_or_unmatched_types_and_reuses_dynamic_groups(monkeypatch):
    condition = {"field": "dynamic_group", "method": "eq", "value": ["group"]}
    tiers = [
        [
            rule(1, 30, action("noise"), conditions=[{"field": "bk_host_id", "method": "eq", "value": ["999"]}]),
            rule(2, 30, action("noise"), is_enabled=False),
        ],
        [rule(3, 20, action("ai_analysis", user_groups=[4]), conditions=[condition])],
    ]
    resolve = Mock(return_value=[7])
    monkeypatch.setattr(AlertAssignMatchManager, "get_host_ids_by_dynamic_groups", resolve)
    shared = {}
    for _ in range(2):
        manager = run_preview(tiers, explain=True, dynamic_group_hosts=shared)
        assert [hit.rule_id for hit in manager.matched_rules] == [3]
        snapshot = manager.new_rule_snaps["3"]
        assert snapshot["configured_conditions"] == [condition]
        assert snapshot["conditions"] == [{"field": "bk_host_id", "method": "eq", "value": [7]}]
    resolve.assert_called_once_with(["group"])
    assert condition["field"] == "dynamic_group"
    assert not run_preview(tiers, assign_mode=[AssignMode.ONLY_NOTICE]).matched_rules


@pytest.mark.django_db
def test_refresh_keeps_configured_dynamic_groups_separate_from_host_conditions(monkeypatch):
    group = AlertAssignGroup.objects.create(name="test", bk_biz_id=2, priority=10)
    dynamic = {"field": "dynamic_group", "method": "eq", "value": ["group-a"]}
    static = {"field": "alert.name", "method": "eq", "value": ["test"]}
    saved = AlertAssignRule.objects.create(
        bk_biz_id=2,
        assign_group_id=group.id,
        conditions=[dynamic, static],
        is_enabled=True,
        actions=[action("noise")],
    )
    monkeypatch.setattr(AssignCacheManager, "cache", FakeRedis())
    monkeypatch.setattr(local, "assign_cache", {})
    monkeypatch.setattr("alarm_backends.core.cache.assign.BusinessManager.all", lambda: [SimpleNamespace(bk_biz_id=2)])
    monkeypatch.setattr("alarm_backends.core.cache.assign.bk_biz_id_to_bk_tenant_id", lambda biz: "tenant")
    lookup = Mock(return_value={"group-a": {"bk_obj_id": "host", "bk_inst_ids": [7]}})
    monkeypatch.setattr("alarm_backends.core.cache.assign.DynamicGroupManager.mget", lookup)
    AssignCacheManager.refresh()
    manager = BackendAssignMatchManager(alert(), cmdb_attrs={})
    manager.run_match()
    snapshot = manager.new_rule_snaps[str(saved.id)]
    assert snapshot["configured_conditions"] == [dynamic, static]
    assert snapshot["conditions"] == [{"field": "bk_host_id", "method": "eq", "value": [7]}, static]
    lookup.assert_called_once_with(bk_tenant_id="tenant", dynamic_group_ids=["group-a"])

    saved.conditions = [static]
    saved.save()
    AssignCacheManager.refresh()
    AssignCacheManager.clear()
    updated = BackendAssignMatchManager(alert(), cmdb_attrs={})
    updated.rule_snaps = manager.new_rule_snaps
    updated.run_match()
    assert updated.new_rule_snaps[str(saved.id)]["conditions"] == [static]
    assert "configured_conditions" not in updated.new_rule_snaps[str(saved.id)]


def test_tagged_noise_skips_upgrade_check():
    noise = Mock(is_dispatch_noise=True)
    UpgradeChecker.__new__(UpgradeChecker).check(noise)
    noise.to_document.assert_not_called()


def test_ai_only_match_preserves_strategy_upgrade(monkeypatch):
    cache_rules(monkeypatch, [[rule(1, 10, action("ai_analysis", user_groups=[31]))]])
    monkeypatch.setattr("alarm_backends.service.fta_action.tasks.alert_assign.get_backend_cmdb_attrs", lambda _: {})
    doc = alert()
    doc.strategy = {"id": 1, "scenario": "os", "notice": {"options": {}}}
    doc.strategy_id = 1
    doc.status = "ABNORMAL"
    alarm = Mock(is_dispatch_noise=False, bk_biz_id=2, id=doc.id, top_event={})
    alarm.to_document.return_value = doc
    checker = UpgradeChecker.__new__(UpgradeChecker)
    checker.need_origin_upgrade = Mock(return_value=True)
    send = Mock()
    monkeypatch.setattr("alarm_backends.service.alert.manager.checker.upgrade.create_actions.delay", send)
    checker.check(alarm)
    checker.need_origin_upgrade.assert_called_once_with(doc, {})
    send.assert_called_once()


@pytest.mark.parametrize("kind", [None, "ai_analysis", "noise"])
def test_legacy_ai_tag_yields_to_explicit_dispatch_without_inventing_receivers(kind):
    tag = {"key": "is_ai_analyze", "value": "true"}
    tiers = [[rule(1, 20, additional_tags=[tag])]]
    if kind:
        tiers.append([rule(2, 10, action(kind))])
    manager = run_preview(tiers)
    result = manager.matched_rule_info
    assert result["additional_tags"] == ([] if kind else [tag])
    assert result["dispatch_result"] == {
        "ai_analysis": {"user_groups": []} if kind == "ai_analysis" else None,
        "noise": kind == "noise",
    }


def test_only_winning_notice_rule_can_upgrade_and_cached_rules_are_immutable():
    notice = action("notice", upgrade_config={"is_enabled": True, "user_groups": [31], "upgrade_interval": 1})
    tiers = [
        [rule(1, 20, notice, user_groups=[30])],
        [rule(2, 10, notice, action("ai_analysis", user_groups=[32]), user_groups=[33])],
    ]
    manager = run_preview(tiers, notice_type="upgrade")
    assert manager.matched_rule_info["notice_appointees"] == [31]
    assert manager.new_rule_snaps["1"]["last_group_index"] == 0
    assert "last_group_index" not in manager.new_rule_snaps["2"]
    assert "last_group_index" not in tiers[0][0]
