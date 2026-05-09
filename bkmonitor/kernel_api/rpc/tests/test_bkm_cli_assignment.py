from types import SimpleNamespace

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.resource.bkm_cli import BkmCliOpCallResource
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.registry import KernelRPCRegistry


class FakeQuerySet:
    def __init__(self, rows):
        self.rows = list(rows)
        self.filter_calls = []
        self.order_by_args = None

    def filter(self, **kwargs):
        self.filter_calls.append(kwargs)
        return self

    def order_by(self, *args):
        self.order_by_args = args
        return self

    def __iter__(self):
        return iter(self.rows)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return self.rows[item]
        return self.rows[item]


class FakeManager:
    def __init__(self, rows=None, detail=None, missing_exc=Exception):
        self.queryset = FakeQuerySet(rows or [])
        self.detail = detail
        self.get_kwargs = None
        self.missing_exc = missing_exc

    def filter(self, **kwargs):
        self.queryset.filter_calls.append(kwargs)
        return self.queryset

    def get(self, **kwargs):
        self.get_kwargs = kwargs
        if self.detail is None:
            raise self.missing_exc()
        return self.detail


def test_assignment_ops_registered():
    for op_id, func_name in [
        ("inspect-action-detail", "bkm_cli.inspect_action_detail"),
        ("inspect-assign-config", "bkm_cli.inspect_assign_config"),
        ("inspect-notice-target", "bkm_cli.inspect_notice_target"),
        ("replay-assign-match", "bkm_cli.replay_assign_match"),
    ]:
        op = BkmCliOpRegistry.resolve(op_id)
        function_detail = KernelRPCRegistry.get_function_detail(func_name)
        assert op.func_name == func_name
        assert op.capability_level == "inspect"
        assert op.risk_level == "low"
        assert function_detail is not None


def test_inspect_action_detail_by_action_id(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import assignment

    action = SimpleNamespace(
        id=6885950371,
        bk_biz_id="-4220780",
        strategy_id=227784,
        strategy_relation_id=133676,
        signal="abnormal",
        status="success",
        real_status="success",
        failure_type=None,
        alert_level=2,
        alerts=["1778250641315430329"],
        action_config_id=1,
        is_parent_action=False,
        parent_action_id=6885950367,
        sub_actions=[],
        assignee=[],
        inputs={"notice_way": "wxwork-bot", "notice_receiver": "chatid", "debug_set": {"z", "a"}},
        outputs={},
        create_time="2026-05-09 06:34:20",
        update_time="2026-05-09 06:34:30",
        end_time=None,
        is_polled=False,
        need_poll=False,
        execute_times=0,
        generate_uuid="abc",
    )
    from bkmonitor.models import ActionInstance

    monkeypatch.setattr(ActionInstance, "objects", FakeManager(detail=action, missing_exc=ActionInstance.DoesNotExist))

    result = assignment.inspect_action_detail({"action_id": 6885950371})

    assert result["lookup_mode"] == "action_id"
    assert result["source_state"] == "current_db_state"
    assert result["exists"] is True
    assert result["action"]["id"] == 6885950371
    assert result["action"]["inputs"]["notice_receiver"] == "chatid"
    assert result["action"]["inputs"]["debug_set"] == ["a", "z"]


def test_inspect_action_detail_rejects_alert_id_without_action_id():
    from kernel_api.rpc.functions.bkm_cli import assignment

    with pytest.raises(CustomException, match="action_id is required"):
        assignment.inspect_action_detail({"alert_id": "alert-a"})


def test_inspect_assign_config_returns_db_groups_rules_and_user_groups(monkeypatch):
    from bkmonitor.models import AlertAssignGroup, AlertAssignRule, UserGroup
    from kernel_api.rpc.functions.bkm_cli import assignment

    group = SimpleNamespace(
        id=1595,
        bk_biz_id=-4220780,
        name="MLAI告警分派",
        priority=105,
        is_builtin=False,
        is_enabled=True,
        settings={},
        source="bkmonitor",
        update_user="admin",
        update_time="2026-05-09 14:45:20",
    )
    rule = SimpleNamespace(
        id=133699,
        bk_biz_id=-4220780,
        assign_group_id=1595,
        is_enabled=True,
        user_groups=[95671],
        user_type="main",
        conditions=[],
        actions=[],
        alert_severity=0,
        additional_tags=[],
    )
    user_group = SimpleNamespace(
        id=95671,
        bk_biz_id=-4220780,
        name="garycgzheng",
        timezone="Asia/Shanghai",
        need_duty=False,
        channels=["user"],
        mention_list=[],
        alert_notice=[],
        action_notice=[],
        duty_notice={},
        duty_rules=[],
        update_user="admin",
        update_time="2026-05-09 14:45:20",
    )
    monkeypatch.setattr(AlertAssignGroup, "objects", FakeManager(rows=[group]))
    monkeypatch.setattr(AlertAssignRule, "objects", FakeManager(rows=[rule]))
    monkeypatch.setattr(UserGroup, "objects", FakeManager(rows=[user_group]))

    result = assignment.inspect_assign_config({"bk_biz_id": -4220780, "assign_group_id": 1595})

    assert result["source_state"] == "current_db_state"
    assert result["groups"][0]["id"] == 1595
    assert result["rules"][0]["id"] == 133699
    assert result["user_groups"][0]["id"] == 95671


def test_inspect_assign_config_honors_enabled_and_global_filters(monkeypatch):
    from bkmonitor.models import AlertAssignGroup, AlertAssignRule, UserGroup
    from kernel_api.rpc.functions.bkm_cli import assignment

    group = SimpleNamespace(
        id=1595,
        bk_biz_id=-4220780,
        name="MLAI告警分派",
        priority=105,
        is_builtin=False,
        is_enabled=True,
        settings={},
        source="bkmonitor",
        update_user="admin",
        update_time="2026-05-09 14:45:20",
    )
    rule = SimpleNamespace(
        id=133699,
        bk_biz_id=-4220780,
        assign_group_id=1595,
        is_enabled=True,
        user_groups=[95671],
        user_type="main",
        conditions=[],
        actions=[],
        alert_severity=0,
        additional_tags=[],
    )
    group_manager = FakeManager(rows=[group])
    rule_manager = FakeManager(rows=[rule])
    monkeypatch.setattr(AlertAssignGroup, "objects", group_manager)
    monkeypatch.setattr(AlertAssignRule, "objects", rule_manager)
    monkeypatch.setattr(UserGroup, "objects", FakeManager(rows=[]))

    result = assignment.inspect_assign_config({"bk_biz_id": -4220780, "include_global": False, "only_enabled": True})

    assert result["include_global"] is False
    assert group_manager.queryset.filter_calls[0] == {"bk_biz_id__in": [-4220780]}
    assert {"is_enabled": True} in group_manager.queryset.filter_calls
    assert rule_manager.queryset.filter_calls[0] == {"bk_biz_id__in": [-4220780]}
    assert {"is_enabled": True} in rule_manager.queryset.filter_calls


def test_inspect_assign_config_reports_missing_user_group_ids(monkeypatch):
    from bkmonitor.models import AlertAssignGroup, AlertAssignRule, UserGroup
    from kernel_api.rpc.functions.bkm_cli import assignment

    group = SimpleNamespace(
        id=1595,
        bk_biz_id=-4220780,
        name="MLAI告警分派",
        priority=105,
        is_builtin=False,
        is_enabled=True,
        settings={},
        source="bkmonitor",
        update_user="admin",
        update_time="2026-05-09 14:45:20",
    )
    rule = SimpleNamespace(
        id=133699,
        bk_biz_id=-4220780,
        assign_group_id=1595,
        is_enabled=True,
        user_groups=[95671, 99999],
        user_type="main",
        conditions=[],
        actions=[],
        alert_severity=0,
        additional_tags=[],
    )
    user_group = SimpleNamespace(
        id=95671,
        bk_biz_id=-4220780,
        name="garycgzheng",
        timezone="Asia/Shanghai",
        need_duty=False,
        channels=["user"],
        mention_list=[],
        alert_notice=[],
        action_notice=[],
        duty_notice={},
        duty_rules=[],
        update_user="admin",
        update_time="2026-05-09 14:45:20",
    )
    monkeypatch.setattr(AlertAssignGroup, "objects", FakeManager(rows=[group]))
    monkeypatch.setattr(AlertAssignRule, "objects", FakeManager(rows=[rule]))
    monkeypatch.setattr(UserGroup, "objects", FakeManager(rows=[user_group]))

    result = assignment.inspect_assign_config({"bk_biz_id": -4220780})

    assert result["missing_user_group_ids"] == [99999]


def test_inspect_notice_target_returns_duty_arranges(monkeypatch):
    from bkmonitor.models import DutyArrange, UserGroup
    from kernel_api.rpc.functions.bkm_cli import assignment

    group = SimpleNamespace(
        id=94872,
        bk_biz_id=-4220780,
        name="AI-bot",
        timezone="Asia/Shanghai",
        need_duty=True,
        channels=["wxwork-bot"],
        mention_list=[],
        alert_notice=[{"notice_ways": [{"name": "wxwork-bot", "receivers": ["chatid"]}]}],
        action_notice=[],
        duty_notice={},
        duty_rules=[],
        update_user="admin",
        update_time="2026-05-09 14:45:20",
    )
    duty = SimpleNamespace(
        id=1,
        user_group_id=94872,
        duty_rule_id=10,
        work_time="always",
        users={"users": ["admin"]},
        duty_users={},
        group_type="specified",
        group_number=1,
        need_rotation=False,
        effective_time=None,
        handoff_time={},
        duty_time={},
        order=1,
        backups={},
    )
    monkeypatch.setattr(UserGroup, "objects", FakeManager(rows=[group]))
    monkeypatch.setattr(DutyArrange, "objects", FakeManager(rows=[duty]))

    result = assignment.inspect_notice_target({"user_group_ids": [94872]})

    assert result["exists"] is True
    assert result["user_groups"][0]["channels"] == ["wxwork-bot"]
    assert result["user_groups"][0]["duty_arranges"][0]["user_group_id"] == 94872


def test_inspect_notice_target_can_skip_duty_lookup(monkeypatch):
    from bkmonitor.models import DutyArrange, UserGroup
    from kernel_api.rpc.functions.bkm_cli import assignment

    group = SimpleNamespace(
        id=94872,
        bk_biz_id=-4220780,
        name="AI-bot",
        timezone="Asia/Shanghai",
        need_duty=True,
        channels=["wxwork-bot"],
        mention_list=[],
        alert_notice=[],
        action_notice=[],
        duty_notice={},
        duty_rules=[],
        update_user="admin",
        update_time="2026-05-09 14:45:20",
    )
    duty_manager = FakeManager(rows=[SimpleNamespace(id=1, user_group_id=94872)])
    monkeypatch.setattr(UserGroup, "objects", FakeManager(rows=[group]))
    monkeypatch.setattr(DutyArrange, "objects", duty_manager)

    result = assignment.inspect_notice_target({"user_group_ids": [94872], "include_duty": False})

    assert result["user_groups"][0]["duty_arranges"] == []
    assert duty_manager.queryset.filter_calls == []


def test_replay_assign_match_labels_current_runtime_state(monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import assignment

    alert = SimpleNamespace(id="alert-a", assignee=[], severity=2)
    manager = SimpleNamespace(
        matched_rules=[SimpleNamespace(rule_id=133699)],
        matched_rule_info={"notice_appointees": [95671]},
        dimensions={"tags.pod": "pod-a"},
        run_match=lambda: None,
    )

    monkeypatch.setattr("bkmonitor.documents.AlertDocument.mget", lambda ids: [alert])
    monkeypatch.setattr(
        "alarm_backends.service.fta_action.tasks.alert_assign.BackendAssignMatchManager",
        lambda *args, **kwargs: manager,
    )

    result = assignment.replay_assign_match({"alert_id": "alert-a"})

    assert result["source_state"] == "current_runtime_state"
    assert result["history_guarantee"] == "current_cache_only_not_historical"
    assert result["matched"] is True
    assert result["matched_rule_ids"] == [133699]


def test_replay_assign_match_requires_alert_id():
    from kernel_api.rpc.functions.bkm_cli.assignment import replay_assign_match

    with pytest.raises(CustomException, match="alert_id is required"):
        replay_assign_match({})


def test_action_detail_works_through_service_bridge(monkeypatch):
    from bkmonitor.models import ActionInstance

    action = SimpleNamespace(id=1, bk_biz_id="2")
    monkeypatch.setattr(ActionInstance, "objects", FakeManager(detail=action, missing_exc=ActionInstance.DoesNotExist))

    result = BkmCliOpCallResource().perform_request({"op_id": "inspect-action-detail", "params": {"action_id": 1}})

    assert result["op_id"] == "inspect-action-detail"
    assert result["func_name"] == "bkm_cli.inspect_action_detail"
    assert result["result"]["action"]["id"] == 1
