"""Offline contract tests; no remote delegation inventory is assumed."""

import json
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from bkmonitor.iam import model_sync
from iam_engine.core.config import AuthMode
from iam_engine.model.convergence import ActualModel, V4ModelMigrator, build_plan
from iam_engine.model.definition import ModelDefinitionError, build_model_definition
from iam_engine.model.sync import ModelSyncError, ModelSyncService
from iam_engine.v4.exceptions import V4ClientError, V4ResponseError

DELEGATION = {"role_id": "space_operator", "grantee_type": "system", "grantee_id": "bk_paas3", "tenant_mode": "global"}


def log_payload():
    return json.loads(
        (Path(__file__).resolve().parents[2] / "bklog/support-files/iam/v4/0001_initial.json").read_text()
    )


def log_model(payload=None, extra_clients=()):
    return build_model_definition(
        payload or log_payload(),
        system_id="bk_log_search",
        callback_url="https://log.example/callback/",
        extra_clients=extra_clients,
    )


@pytest.mark.parametrize("factory", [log_model, model_sync.expected_v4_model])
def test_products_delegate_only_operator_and_remove_only_paas(factory):
    model = factory()
    assert [asdict(item) for item in model.role_delegations] == [DELEGATION]
    assert set(model.system.removed_clients) == {"bk_paas3", "paasv3cli"}
    assert not set(model.system.clients) & set(model.system.removed_clients)
    initial = build_plan(model, ActualModel())
    actual = ActualModel(
        system={**initial.create_system, "clients": [*model.system.clients, "bk_paas3", "paasv3cli", "manual"]},
        resource_types=initial.create_resource_types,
        actions=initial.create_actions,
        roles=initial.create_roles,
    )
    plan = build_plan(model, actual)
    assert plan.update_system == {"clients": [*model.system.clients, "manual"]}
    assert plan.ensure_role_delegations == (DELEGATION,)


def test_extra_clients_cannot_reintroduce_retired_client():
    assert "bk_paas3" not in log_model(extra_clients=["bk_paas3"]).system.clients


@pytest.mark.parametrize(
    "key,value",
    [
        ("role_id", "missing"),
        ("role_id", "*"),
        ("grantee_type", "user"),
        ("tenant_mode", "unknown"),
        ("grantee_id", ""),
    ],
)
def test_invalid_delegation_fails_before_io(key, value):
    payload = log_payload()
    payload["role_delegations"][0][key] = value
    with pytest.raises(ModelDefinitionError):
        log_model(payload)


def test_new_install_orders_role_before_delegation_and_preview_does_not_write():
    client = Mock()
    client.retrieve_system.return_value = None
    migrator = V4ModelMigrator(client, log_model())
    plan = migrator.migrate(dry_run=True)
    assert "remote existence unknown" in plan.describe()
    assert [call[0] for call in client.mock_calls] == ["retrieve_system"]
    client.reset_mock()
    migrator.migrate(dry_run=False)
    names = [call[0] for call in client.mock_calls]
    assert names.index("batch_create_roles") < names.index("batch_create_role_delegations")
    client.batch_create_role_delegations.assert_called_once_with((DELEGATION,))


def test_converged_model_reensures_delegation_and_failure_keeps_clients():
    model = log_model()
    initial = build_plan(model, ActualModel())
    actual = ActualModel(
        system=initial.create_system,
        resource_types=initial.create_resource_types,
        actions=initial.create_actions,
        roles=initial.create_roles,
    )
    client = Mock()
    migrator = V4ModelMigrator(client, model)
    migrator.fetch_actual = Mock(return_value=actual)
    migrator.migrate(dry_run=False)
    migrator.migrate(dry_run=False)
    assert client.batch_create_role_delegations.call_count == 2
    client.update_system.assert_not_called()
    migrator.fetch_actual.return_value = replace(actual, system={**actual.system, "clients": ["bk_paas3"]})
    client.batch_create_role_delegations.side_effect = RuntimeError("delegation denied")
    service = ModelSyncService(Mock(get_mode=Mock(return_value=AuthMode.V4)), {AuthMode.V4: lambda: migrator})
    with pytest.raises(ModelSyncError, match="delegation denied"):
        service.run(apply=True)
    client.update_system.assert_not_called()
    client.batch_create_role_delegations.side_effect = None
    service.run(apply=True)
    client.update_system.assert_called_once()


@pytest.mark.parametrize(
    "status,data,error",
    [(201, None, None), (200, None, V4ClientError), (201, [], V4ResponseError), (403, None, V4ClientError)],
)
def test_transport_contract_and_tenant(settings, status, data, error):
    settings.BK_IAM_V4_APIGATEWAY_URL = "https://iam.example/"
    settings.BK_IAM_V4_SYSTEM_ID = "bk_monitorv3"
    settings.BK_APP_TENANT_ID = "system"
    response = Mock(status_code=status, content=b"body")
    response.json.return_value = {"data": data}
    with patch("iam_engine.v4.client.requests.request", return_value=response) as send:
        client = model_sync.v4_migrator().client
        if error:
            with pytest.raises(error):
                client.batch_create_role_delegations([DELEGATION])
        else:
            client.batch_create_role_delegations([DELEGATION])
        call = send.call_args.kwargs
        assert call["url"] == "https://iam.example/api/v1/open/mgmt/systems/bk_monitorv3/role-delegations/"
        assert call["method"] == "POST"
        assert call["json"] == [DELEGATION]
        assert call["headers"]["X-Bk-Tenant-Id"] == "system"


def test_v3_does_not_construct_delegation_client():
    v4 = Mock(side_effect=AssertionError("V4 must not be constructed"))
    legacy = Mock()
    ModelSyncService(Mock(get_mode=Mock(return_value=AuthMode.V3)), {AuthMode.V3: lambda: legacy, AuthMode.V4: v4}).run(
        apply=True
    )
    legacy.migrate.assert_called_once_with(dry_run=False)
    v4.assert_not_called()
