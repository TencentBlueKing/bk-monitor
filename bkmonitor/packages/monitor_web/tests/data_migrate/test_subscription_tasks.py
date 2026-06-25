from types import SimpleNamespace

from bkmonitor.utils.local import local
from monitor_web.collecting.constant import OperationType
from monitor_web.data_migrate import subscription_tasks
from monitor_web.plugin.constant import PluginType


def _task(task_id, bk_biz_id=2, status="running"):
    return SimpleNamespace(
        id=task_id,
        bk_biz_id=bk_biz_id,
        name=f"uptime-{task_id}",
        status=SimpleNamespace(value=status),
    )


def _collect_config(config_id, *, subscription_id, collect_type=PluginType.SCRIPT, last_operation=OperationType.START):
    return SimpleNamespace(
        pk=config_id,
        id=config_id,
        bk_biz_id=2,
        name=f"collect-{config_id}",
        collect_type=collect_type,
        plugin_id=f"plugin-{config_id}",
        last_operation=last_operation,
        operation_result="SUCCESS",
        deployment_config=SimpleNamespace(subscription_id=subscription_id),
    )


def test_stop_biz_subscription_tasks_dry_run_lists_target_tasks(monkeypatch):
    plugin_config = _collect_config(1, subscription_id=101)
    no_subscription_config = _collect_config(2, subscription_id=0)
    k8s_config = _collect_config(3, subscription_id=0, collect_type=PluginType.K8S)

    monkeypatch.setattr(subscription_tasks, "_list_uptime_tasks", lambda **kwargs: [(_task(11), [201])])
    monkeypatch.setattr(
        subscription_tasks,
        "_list_collect_configs",
        lambda **kwargs: [plugin_config, no_subscription_config, k8s_config],
    )
    monkeypatch.setattr(
        subscription_tasks,
        "_get_plugin_type_map",
        lambda **kwargs: {
            plugin_config.plugin_id: PluginType.SCRIPT,
            no_subscription_config.plugin_id: PluginType.SCRIPT,
            k8s_config.plugin_id: PluginType.K8S,
        },
    )
    monkeypatch.setattr(
        subscription_tasks,
        "control_task",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("dry-run should not stop uptime task")),
    )
    monkeypatch.setattr(
        subscription_tasks,
        "get_collect_installer",
        lambda config: (_ for _ in ()).throw(AssertionError("dry-run should not stop collect config")),
    )

    result = subscription_tasks.stop_biz_subscription_tasks(
        bk_tenant_id="system", bk_biz_ids=[2], operator="admin", dry_run=True
    )

    assert result["summary"]["total"] == {
        "matched_count": 3,
        "planned_count": 3,
        "stopped_count": 0,
        "skipped_count": 0,
        "failed_count": 0,
    }
    assert len(result["details"][subscription_tasks.UPTIME_CHECK]) == 1
    assert len(result["details"][subscription_tasks.PLUGIN_COLLECT]) == 1
    assert len(result["details"][subscription_tasks.K8S_COLLECT]) == 1


def test_stop_biz_subscription_tasks_executes_and_records_failures(monkeypatch):
    plugin_config = _collect_config(1, subscription_id=101)
    k8s_config = _collect_config(2, subscription_id=0, collect_type=PluginType.K8S)
    calls = []

    def fake_control_task(**kwargs):
        calls.append(("uptime", kwargs["task_id"]))
        if kwargs["task_id"] == 12:
            raise RuntimeError("stop failed")

    class FakeInstaller:
        def __init__(self, config):
            self.config = config

        def stop(self):
            calls.append(("collect", self.config.id))

    monkeypatch.setattr(
        subscription_tasks,
        "_list_uptime_tasks",
        lambda **kwargs: [(_task(11), [201]), (_task(12), [202])],
    )
    monkeypatch.setattr(subscription_tasks, "_list_collect_configs", lambda **kwargs: [plugin_config, k8s_config])
    monkeypatch.setattr(
        subscription_tasks,
        "_get_plugin_type_map",
        lambda **kwargs: {plugin_config.plugin_id: PluginType.SCRIPT, k8s_config.plugin_id: PluginType.K8S},
    )
    monkeypatch.setattr(subscription_tasks, "control_task", fake_control_task)
    monkeypatch.setattr(subscription_tasks, "get_collect_installer", lambda config: FakeInstaller(config))

    local.username = "origin"
    local.bk_tenant_id = "origin_tenant"
    result = subscription_tasks.stop_biz_subscription_tasks(
        bk_tenant_id="system", bk_biz_ids=[2], operator="admin", dry_run=False
    )

    assert calls == [("uptime", 11), ("uptime", 12), ("collect", 1), ("collect", 2)]
    assert result["summary"]["total"] == {
        "matched_count": 4,
        "planned_count": 0,
        "stopped_count": 3,
        "skipped_count": 0,
        "failed_count": 1,
    }
    assert result["details"][subscription_tasks.UPTIME_CHECK][1]["message"] == "stop failed"
    assert local.username == "origin"
    assert local.bk_tenant_id == "origin_tenant"


def test_stop_biz_subscription_tasks_skips_stopped_k8s_collect(monkeypatch):
    k8s_config = _collect_config(
        1,
        subscription_id=0,
        collect_type=PluginType.K8S,
        last_operation=OperationType.STOP,
    )

    monkeypatch.setattr(subscription_tasks, "_list_uptime_tasks", lambda **kwargs: [])
    monkeypatch.setattr(subscription_tasks, "_list_collect_configs", lambda **kwargs: [k8s_config])
    monkeypatch.setattr(
        subscription_tasks,
        "_get_plugin_type_map",
        lambda **kwargs: {k8s_config.plugin_id: PluginType.K8S},
    )
    monkeypatch.setattr(
        subscription_tasks,
        "get_collect_installer",
        lambda config: (_ for _ in ()).throw(AssertionError("stopped k8s config should be skipped")),
    )

    result = subscription_tasks.stop_biz_subscription_tasks(
        bk_tenant_id="system", bk_biz_ids=[2], operator="admin", dry_run=False
    )

    assert result["summary"][subscription_tasks.K8S_COLLECT] == {
        "matched_count": 1,
        "planned_count": 0,
        "stopped_count": 0,
        "skipped_count": 1,
        "failed_count": 0,
    }


def test_stop_biz_subscription_tasks_skips_negative_biz_ids_without_query(monkeypatch):
    monkeypatch.setattr(
        subscription_tasks,
        "_list_uptime_tasks",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("negative biz should not query uptime tasks")),
    )
    monkeypatch.setattr(
        subscription_tasks,
        "_list_collect_configs",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("negative biz should not query collect configs")),
    )

    result = subscription_tasks.stop_biz_subscription_tasks(
        bk_tenant_id="system", bk_biz_ids=[-4759], operator="admin", dry_run=False
    )

    assert result["skipped_biz_ids"] == [{"bk_biz_id": -4759, "reason": subscription_tasks.NEGATIVE_BIZ_SKIP_REASON}]
    assert result["summary"]["total"] == {
        "matched_count": 0,
        "planned_count": 0,
        "stopped_count": 0,
        "skipped_count": 0,
        "failed_count": 0,
    }


def test_stop_biz_subscription_tasks_filters_negative_biz_ids(monkeypatch):
    seen_biz_ids = []

    def fake_list_uptime_tasks(**kwargs):
        seen_biz_ids.append(("uptime", kwargs["bk_biz_ids"]))
        return []

    def fake_list_collect_configs(**kwargs):
        seen_biz_ids.append(("collect", kwargs["bk_biz_ids"]))
        return []

    monkeypatch.setattr(subscription_tasks, "_list_uptime_tasks", fake_list_uptime_tasks)
    monkeypatch.setattr(subscription_tasks, "_list_collect_configs", fake_list_collect_configs)
    monkeypatch.setattr(subscription_tasks, "_get_plugin_type_map", lambda **kwargs: {})

    result = subscription_tasks.stop_biz_subscription_tasks(
        bk_tenant_id="system", bk_biz_ids=[-4759, 2], operator="admin", dry_run=True
    )

    assert seen_biz_ids == [("uptime", [2]), ("collect", [2])]
    assert result["skipped_biz_ids"] == [{"bk_biz_id": -4759, "reason": subscription_tasks.NEGATIVE_BIZ_SKIP_REASON}]
