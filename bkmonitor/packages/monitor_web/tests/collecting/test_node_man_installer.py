from types import SimpleNamespace

from monitor_web.collecting.constant import OperationResult, OperationType
from monitor_web.collecting.deploy import node_man
from monitor_web.collecting.deploy.node_man import NodeManInstaller


class FakeDeploymentConfig:
    def __init__(self, subscription_id):
        self.subscription_id = subscription_id
        self.task_ids = []
        self.save_called = 0

    def save(self):
        self.save_called += 1


class FakeCollectConfig:
    def __init__(self, subscription_id=123):
        self.bk_tenant_id = "tenant-a"
        self.plugin = SimpleNamespace(plugin_type="Script")
        self.deployment_config = FakeDeploymentConfig(subscription_id)
        self.operation_result = OperationResult.SUCCESS
        self.last_operation = OperationType.START
        self.save_called = 0

    def save(self):
        self.save_called += 1


def test_stop_uses_existing_subscription_steps_without_deploy_params(monkeypatch):
    collect_config = FakeCollectConfig()
    installer = NodeManInstaller(collect_config)
    calls = []

    def raise_if_called(*args, **kwargs):
        raise AssertionError("stop should not rebuild deploy params")

    def fake_run_subscription(**kwargs):
        calls.append(("run", kwargs))
        return {"task_id": 456}

    def fake_subscription_info(**kwargs):
        calls.append(("info", kwargs))
        return [{"steps": [{"id": "plugin_step"}, {"id": "bkmonitorbeat"}]}]

    monkeypatch.setattr(installer, "_get_deploy_params", raise_if_called)
    monkeypatch.setattr(
        node_man.api.node_man,
        "switch_subscription",
        lambda **kwargs: calls.append(("switch", kwargs)),
    )
    monkeypatch.setattr(
        node_man.api.node_man,
        "subscription_info",
        fake_subscription_info,
    )
    monkeypatch.setattr(node_man.api.node_man, "run_subscription", fake_run_subscription)

    installer.stop()

    assert calls == [
        ("switch", {"bk_tenant_id": "tenant-a", "subscription_id": 123, "action": "disable"}),
        ("info", {"bk_tenant_id": "tenant-a", "subscription_id_list": [123]}),
        (
            "run",
            {
                "bk_tenant_id": "tenant-a",
                "subscription_id": 123,
                "actions": {"plugin_step": "STOP", "bkmonitorbeat": "STOP"},
            },
        ),
    ]
    assert collect_config.operation_result == OperationResult.PREPARING
    assert collect_config.last_operation == OperationType.STOP
    assert collect_config.deployment_config.task_ids == [456]
    assert collect_config.save_called == 1
    assert collect_config.deployment_config.save_called == 1
