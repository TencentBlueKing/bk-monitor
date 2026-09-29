"""Audit labels must not require or replace an authenticated user."""

from types import SimpleNamespace

import pytest
from blueapps.account.models import User
from django.db import DataError

from bkmonitor.models import StrategyHistoryModel, StrategyModel
from bkmonitor.strategy.new_strategy import Item, Strategy
from monitor_web.strategies.resources.v2 import SaveStrategyV2Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def strategy_and_request(monkeypatch):
    request = SimpleNamespace(user=SimpleNamespace(username="authenticated-user", tenant_id="system"))
    monkeypatch.setattr("bkmonitor.utils.request.get_request", lambda **_kwargs: request)
    strategy = Strategy(
        bk_biz_id=2,
        name="synthetic audit strategy",
        scenario="os",
        notice={"config": {"template": []}},
        items=[
            {
                "name": "synthetic metric",
                "no_data_config": {},
                "expression": "a",
                "query_configs": [
                    {
                        "data_source_label": "prometheus",
                        "data_type_label": "time_series",
                        "alias": "a",
                        "promql": "up",
                        "agg_interval": 60,
                    }
                ],
                "algorithms": [{"type": "Threshold", "level": 2, "config": [[{"method": "gt", "threshold": 1}]]}],
            }
        ],
        detects=[
            {"level": 2, "trigger_config": {"count": 1, "check_window": 1}, "recovery_config": {"check_window": 1}}
        ],
    )
    strategy.save()
    return strategy, request


@pytest.mark.parametrize("audit_operator", [None, "audit-only-actor", "a" * 32])
def test_save_audit_label_without_user_registration(strategy_and_request, audit_operator):
    strategy, request = strategy_and_request
    user_count = User.objects.count()
    assert not User.objects.filter(username=audit_operator or "untrusted-user").exists()
    params = strategy.to_dict()
    params.update(name="updated synthetic strategy", audit_operator="untrusted-user")
    resource = SaveStrategyV2Resource()
    validated = resource.validate_request_data(params)
    assert "audit_operator" not in validated
    resource.perform_request(validated, audit_operator=audit_operator)

    expected = audit_operator or "authenticated-user"
    saved = StrategyModel.objects.get(id=strategy.id)
    history = StrategyHistoryModel.objects.filter(strategy_id=strategy.id).latest("id")
    assert saved.name == "updated synthetic strategy"
    assert saved.update_user == history.create_user == expected
    assert history.status is True
    assert saved.create_user == request.user.username == "authenticated-user"
    assert User.objects.count() == user_count
    assert not User.objects.filter(username=audit_operator or "untrusted-user").exists()


def test_failed_save_keeps_declared_operator_in_history(strategy_and_request, monkeypatch):
    strategy, request = strategy_and_request

    def fail_save(self):
        raise DataError("synthetic write failure")

    monkeypatch.setattr(Item, "save", fail_save)
    strategy.name = "failed update"
    with pytest.raises(DataError, match="synthetic write failure"):
        strategy.save(audit_operator="audit-only-actor")

    saved = StrategyModel.objects.get(id=strategy.id)
    history = StrategyHistoryModel.objects.filter(strategy_id=strategy.id).latest("id")
    assert saved.name == "synthetic audit strategy"
    assert saved.update_user == request.user.username == "authenticated-user"
    assert history.create_user == "audit-only-actor"
    assert history.status is False
    assert "synthetic write failure" in history.message
