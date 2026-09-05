"""公共 collector 多目标下发：保留业务默认部署，隔离模板、写入和清理。"""

import base64
import gzip
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from django.core.management.base import CommandError
from kubernetes import client

from apm.core.application_config import ApplicationConfig
from apm.core.platform_config import PlatformConfig
from bkmonitor.define.global_config import STANDARD_CONFIGS
from bkmonitor.utils.bk_collector_config import BkCollectorClusterConfig as ClusterConfig
from constants.bk_collector import BkCollectorComp
from metadata.management.commands.clean_disabled_config_in_global_k8s_cluster import Command
from metadata.models.bcs.cluster import BCSClusterInfo
from metadata.models.custom_report.subscription_config import CustomReportSubscription, LogSubscriptionConfig
from rum.core.application_config import RumApplicationConfig


@pytest.fixture(autouse=True)
def collector_settings(settings):
    ClusterConfig.global_deploy_targets.cache_clear()
    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = ["cluster-a"]
    settings.K8S_OPERATOR_DEPLOY_NAMESPACE = {"cluster-a": "operator-ns"}
    settings.CUSTOM_REPORT_K8S_SECRETS_CONFIG = {}
    yield
    ClusterConfig.global_deploy_targets.cache_clear()


def test_legacy_mapping_keeps_public_precedence_without_mutating_discovery():
    discovered = {"cluster-a": {1, 2}, "cluster-b": {3}}
    assert ClusterConfig.get_deploy_mapping(discovered) == {
        ("cluster-a", "operator-ns", True): [0],
        ("cluster-b", "bkmonitor-operator", False): {3},
    }
    assert discovered == {"cluster-a": {1, 2}, "cluster-b": {3}}
    assert ClusterConfig.is_global_target("cluster-a")
    assert not ClusterConfig.is_global_target(None)


def test_public_namespaces_keep_business_target_and_support_multiple_clusters(settings):
    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = [
        "cluster-a/public-1",
        "cluster-a/public-2",
        "cluster-b/public-1",
        "cluster-a/public-1",
    ]
    assert ClusterConfig.get_deploy_mapping({"cluster-a": [1]}) == {
        ("cluster-a", "operator-ns", False): [1],
        ("cluster-a", "public-1", True): [0],
        ("cluster-a", "public-2", True): [0],
        ("cluster-b", "public-1", True): [0],
    }
    assert not ClusterConfig.is_global_target("cluster-a", "operator-ns")
    assert ClusterConfig.is_global_target("cluster-a", "public-1")


def test_namespace_override_is_per_cluster_and_same_target_is_not_duplicated(settings):
    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = [
        "cluster-a",
        "cluster-a/operator-ns",
        "cluster-a/public-1",
        "cluster-b",
    ]
    assert ClusterConfig.get_deploy_mapping({"cluster-a": [1]}) == {
        ("cluster-a", "operator-ns", True): [0],
        ("cluster-a", "public-1", True): [0],
        ("cluster-b", "bkmonitor-operator", True): [0],
    }


@pytest.mark.parametrize("target", ["", "/public", "cluster-a/"])
def test_empty_public_target_parts_do_not_block_valid_or_business_targets(settings, target, caplog):
    caplog.set_level("WARNING", logger="bkmonitor.utils.bk_collector_config")
    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = [target, "cluster-b/public"]
    assert ClusterConfig.get_deploy_mapping({"cluster-a": [1]}) == {
        ("cluster-a", "operator-ns", False): [1],
        ("cluster-b", "public", True): [0],
    }
    assert "invalid public collector target" in caplog.text


@pytest.mark.parametrize("targets", ["cluster-a/public", {"cluster-a": "public"}, 1])
def test_invalid_public_target_list(settings, targets, caplog):
    caplog.set_level("WARNING", logger="bkmonitor.utils.bk_collector_config")
    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = targets
    assert ClusterConfig.global_deploy_targets() == []
    assert ClusterConfig.get_deploy_mapping({"cluster-a": [1]}) == {("cluster-a", "operator-ns", False): [1]}
    assert "CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER must be a list" in caplog.text


def test_public_targets_are_cached_for_60_seconds_then_read_current_settings(settings, mocker):
    clock = mocker.patch("bkmonitor.utils.cache.monotonic", return_value=1000)
    namespace = mocker.spy(ClusterConfig, "bk_collector_namespace")
    assert ClusterConfig.global_deploy_targets() == [("cluster-a", "operator-ns")]
    assert ClusterConfig.is_global_target("cluster-a", "operator-ns")
    namespace.assert_called_once_with("cluster-a")

    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = ["cluster-b/public"]
    clock.return_value = 1059
    assert ClusterConfig.global_deploy_targets() == [("cluster-a", "operator-ns")]
    clock.return_value = 1061
    assert ClusterConfig.global_deploy_targets() == [("cluster-b", "public")]


def test_public_targets_reuse_existing_global_config():
    field = STANDARD_CONFIGS["CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER"]
    assert field.get_default() == []
    value = ["cluster-a/public-1", "cluster-a/public-2", "cluster-b"]
    assert field.run_validation(value) == value


@pytest.mark.parametrize("targets", [[], None])
def test_no_public_targets_keeps_business_delivery(settings, targets):
    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = targets
    assert ClusterConfig.get_deploy_mapping({"cluster-a": [1]}) == {("cluster-a", "operator-ns", False): [1]}


@pytest.mark.parametrize("namespace,expected", [(None, "operator-ns"), ("public-1", "public-1")])
@pytest.mark.parametrize("platform", [False, True])
def test_templates_are_read_from_selected_namespace(mocker, namespace, expected, platform):
    kube = mocker.patch("bkmonitor.utils.bk_collector_config.BcsKubeClient").return_value
    template_name = (
        BkCollectorComp.CONFIG_MAP_PLATFORM_TPL_NAME if platform else BkCollectorComp.CONFIG_MAP_APPLICATION_TPL_NAME
    )
    kube.client_request.return_value = SimpleNamespace(
        items=[SimpleNamespace(data={template_name: base64.b64encode(b"template").decode()})]
    )
    if platform:
        content = ClusterConfig.platform_config_tpl("cluster-a", namespace=namespace)
    else:
        content = ClusterConfig.sub_config_tpl("cluster-a", template_name, namespace=namespace)
    assert content == "template"
    assert kube.client_request.call_args.kwargs["namespace"] == expected


def _encode(content):
    return base64.b64encode(gzip.compress(content.encode())).decode()


def test_secret_write_and_duplicate_cleanup_use_same_namespace_and_are_idempotent(mocker):
    kube = mocker.patch("bkmonitor.utils.bk_collector_config.BcsKubeClient").return_value
    secrets = {}

    def request(method, **kwargs):
        assert kwargs["namespace"] == "public-1"
        if method is kube.core_api.list_namespaced_secret:
            return SimpleNamespace(items=list(secrets.values()))
        secret = kwargs["body"]
        secrets[secret.metadata.name] = secret
        return secret

    kube.client_request.side_effect = request
    clean = mocker.patch.object(ClusterConfig, "clean_dup_secrets")
    ClusterConfig.deploy_to_k8s_with_hash("cluster-a", {101: "first"}, "apm", namespace="public-1")
    secret = next(iter(secrets.values()))
    secret.data["application-999.conf"] = _encode("unrelated")
    clean.assert_called_once_with("cluster-a", "apm", namespace="public-1")

    kube.client_request.reset_mock()
    ClusterConfig.deploy_to_k8s_with_hash("cluster-a", {101: "first"}, "apm", namespace="public-1")
    assert kube.client_request.call_count == 1  # 内容未变，仅查询，不写入。
    assert "application-999.conf" in secret.data

    ClusterConfig.deploy_to_k8s_with_hash("cluster-a", {101: "updated"}, "apm", namespace="public-1")
    assert gzip.decompress(base64.b64decode(secret.data["application-101.conf"])) == b"updated"
    assert "application-999.conf" in secret.data


def test_duplicate_cleanup_does_not_fall_back_to_business_namespace(mocker):
    kube = mocker.patch("bkmonitor.utils.bk_collector_config.BcsKubeClient").return_value
    now = datetime.now(timezone.utc)
    older = client.V1Secret(
        metadata=client.V1ObjectMeta(name="old", creation_timestamp=now - timedelta(days=1)),
        data={"application-1.conf": "old", "application-2.conf": "keep"},
    )
    newer = client.V1Secret(
        metadata=client.V1ObjectMeta(name="new", creation_timestamp=now), data={"application-1.conf": "new"}
    )
    kube.client_request.return_value = SimpleNamespace(items=[older, newer])
    ClusterConfig.clean_dup_secrets("cluster-a", "apm", namespace="public-1")
    assert {call.kwargs["namespace"] for call in kube.client_request.call_args_list} == {"public-1"}
    assert older.data == {"application-2.conf": "keep"}
    assert kube.client_request.call_args.args[0] is kube.core_api.replace_namespaced_secret


@pytest.mark.parametrize("list_result", [None, RuntimeError("list failed")])
def test_secret_list_failure_keeps_existing_fallback_behavior(mocker, list_result):
    kube = mocker.patch("bkmonitor.utils.bk_collector_config.BcsKubeClient").return_value
    kube.client_request.side_effect = [list_result, None]
    clean = mocker.patch.object(ClusterConfig, "clean_dup_secrets")
    ClusterConfig.deploy_to_k8s_with_hash("cluster-a", {101: "first"}, "apm", namespace="public-1")
    assert kube.client_request.call_args.args[0] is kube.core_api.create_namespaced_secret
    clean.assert_called_once_with("cluster-a", "apm", namespace="public-1")


@pytest.mark.parametrize("platform", [False, True])
def test_missing_template_response_keeps_existing_skip_behavior(mocker, platform):
    kube = mocker.patch("bkmonitor.utils.bk_collector_config.BcsKubeClient").return_value
    kube.client_request.return_value = None
    if platform:
        assert ClusterConfig.platform_config_tpl("cluster-a", namespace="public-1") is None
    else:
        assert ClusterConfig.sub_config_tpl("cluster-a", "application", namespace="public-1") is None


def test_platform_secret_is_written_to_explicit_namespace(mocker):
    kube = mocker.patch("apm.core.platform_config.BcsKubeClient").return_value
    kube.client_request.side_effect = [SimpleNamespace(items=[]), object()]
    PlatformConfig.deploy_to_k8s("cluster-a", "platform", namespace="public-1")
    assert {call.kwargs["namespace"] for call in kube.client_request.call_args_list} == {"public-1"}
    secret = kube.client_request.call_args.kwargs["body"]
    assert secret.metadata.namespace == "public-1"
    assert gzip.decompress(base64.b64decode(secret.data["platform.conf"])) == b"platform"


def test_application_dimension_fill_is_scoped_to_deployment(settings):
    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = ["cluster-a/public-1"]
    enabled = {"1": ["app"]}
    assert ApplicationConfig.is_resource_filter_enabled("cluster-a", 1, "app", enabled, namespace="operator-ns")
    assert not ApplicationConfig.is_resource_filter_enabled("cluster-a", 1, "app", enabled, namespace="public-1")
    assert not ApplicationConfig.is_resource_filter_enabled(None, 1, "app", enabled)


def test_platform_default_application_and_dimensions_keep_business_semantics(settings, mocker):
    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = ["cluster-a/public-1"]
    relation = mocker.patch("apm.core.platform_config.BcsClusterDefaultApplicationRelation.objects.filter")
    relation.return_value.first.return_value = SimpleNamespace(application=object())
    mocker.patch.object(PlatformConfig, "get_dataids_config_from_application", return_value={"fixed_token": "business"})
    mocker.patch("apm.core.platform_config.get_bk_data_token_aes_key", return_value="test-key")
    assert "fixed_token" not in PlatformConfig.get_token_checker_config("cluster-a", namespace="public-1")
    relation.assert_not_called()
    assert PlatformConfig.get_token_checker_config("cluster-a", namespace="operator-ns")["fixed_token"] == "business"
    kube = mocker.patch("apm.core.platform_config.BcsKubeClient").return_value
    assert PlatformConfig.get_resource_fill_dimensions_config("cluster-a", namespace="public-1") == {}
    kube.client_request.assert_not_called()
    kube.client_request.return_value = SimpleNamespace(
        items=[SimpleNamespace(metadata=SimpleNamespace(name="operator"))]
    )
    assert PlatformConfig.get_resource_fill_dimensions_config("cluster-a", namespace="operator-ns")
    assert kube.client_request.call_args.kwargs["namespace"] == "operator-ns"


@pytest.fixture
def multi_target_delivery(settings, mocker):
    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = ["cluster-a/public-1", "cluster-a/public-2"]
    mocker.patch.object(ClusterConfig, "get_cluster_mapping", return_value={"cluster-a": [1]})
    mocker.patch.object(BCSClusterInfo.objects, "all").return_value.only.return_value = [
        SimpleNamespace(cluster_id="cluster-a", bk_biz_id=1)
    ]
    for module in [
        "apm.core.application_config",
        "apm.core.platform_config",
        "metadata.models.custom_report.subscription_config",
    ]:
        mocker.patch(f"{module}.is_biz_id_need_managed", return_value=True)
    mocker.patch.object(
        ClusterConfig, "sub_config_tpl", side_effect=lambda cluster_id, template, namespace: namespace + ":{{ biz }}"
    )
    return mocker.patch.object(ClusterConfig, "deploy_to_k8s_with_hash")


@pytest.mark.parametrize("protocol", ["apm", "rum", "log"])
@pytest.mark.parametrize("extra_cluster", [False, True])
@pytest.mark.parametrize("business_public_target", [None, "cluster-a", "cluster-a/operator-ns"])
def test_application_delivery_keeps_business_scope_and_fans_out_public_configs(
    protocol, extra_cluster, business_public_target, multi_target_delivery, mocker, settings
):
    targets = mocker.spy(ClusterConfig, "global_deploy_targets")
    role_lookup = mocker.spy(ClusterConfig, "is_global_target")
    if extra_cluster:
        settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER += ["cluster-b/public-1"]
    if business_public_target:
        settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER += [business_public_target]
    applications = [
        SimpleNamespace(id=biz, bk_biz_id=biz, bk_tenant_id="system", app_name=f"app-{biz}", token=f"token-{biz}")
        for biz in [1, 2]
    ]
    if protocol == "apm":
        mocker.patch.object(ApplicationConfig, "get_application_config", lambda self: {"biz": self.bk_biz_id})
        ApplicationConfig.refresh_k8s(applications)
    elif protocol == "rum":
        mocker.patch.object(
            RumApplicationConfig, "get_application_config", lambda self: {"biz": self._application.bk_biz_id}
        )
        RumApplicationConfig.refresh_k8s(applications)
    else:
        groups = [
            SimpleNamespace(bk_biz_id=biz, bk_data_id=biz, is_need_deploy_collector_config=True) for biz in [1, 2]
        ]
        mocker.patch.object(LogSubscriptionConfig, "get_log_config", side_effect=lambda group: {"biz": group.bk_biz_id})
        LogSubscriptionConfig.refresh_k8s(groups)
    actual = {(call.args[0], call.kwargs["namespace"]): call.args[1] for call in multi_target_delivery.call_args_list}
    expected = {
        ("cluster-a", "operator-ns"): {1: "operator-ns:1"},
        ("cluster-a", "public-1"): {1: "public-1:1", 2: "public-1:2"},
        ("cluster-a", "public-2"): {1: "public-2:1", 2: "public-2:2"},
    }
    if extra_cluster:
        expected[("cluster-b", "public-1")] = {1: "public-1:1", 2: "public-1:2"}
    if business_public_target:
        expected[("cluster-a", "operator-ns")] = {1: "operator-ns:1", 2: "operator-ns:2"}
    assert actual == expected
    assert multi_target_delivery.call_count == len(expected)
    assert all(call.args[2] == protocol for call in multi_target_delivery.call_args_list)
    targets.assert_called_once_with()
    role_lookup.assert_not_called()


def test_platform_refresh_renders_each_target_and_continues_after_one_failure(multi_target_delivery, mocker):
    targets = mocker.spy(ClusterConfig, "global_deploy_targets")
    mocker.patch.object(ClusterConfig, "platform_config_tpl", side_effect=lambda cluster_id, namespace: "{{ ns }}")

    def context(cluster_id, namespace, is_global):
        assert is_global is (namespace != "operator-ns")
        return {"ns": namespace}

    mocker.patch.object(PlatformConfig, "get_platform_config", side_effect=context)

    def deploy(cluster_id, content, namespace):
        assert content == namespace
        if namespace == "public-1":
            raise RuntimeError("unavailable target")

    delivery = mocker.patch.object(PlatformConfig, "deploy_to_k8s", side_effect=deploy)
    PlatformConfig.refresh_k8s()
    assert [call.kwargs["namespace"] for call in delivery.call_args_list] == ["operator-ns", "public-1", "public-2"]
    targets.assert_called_once_with()


@pytest.mark.parametrize("is_global", [False, True])
def test_application_context_uses_target_role_without_reading_global_settings(settings, mocker, is_global):
    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = ["cluster-a"] if is_global else []
    [(cluster_id, namespace, target_is_global)] = ClusterConfig.get_deploy_mapping({"cluster-a": [1]})
    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = [] if is_global else ["cluster-a"]
    ClusterConfig.global_deploy_targets.cache_clear()
    targets = mocker.spy(ClusterConfig, "global_deploy_targets")
    settings.APM_RESOURCE_FILTER_LOGS_ENABLED_APPS = {"1": ["app"]}
    settings.APM_RESOURCE_FILTER_METRICS_ENABLED_APPS = {"1": ["app"]}
    mocker.patch.object(ApplicationConfig, "get_application_config", return_value={})
    application = SimpleNamespace(id=1, bk_biz_id=1, bk_tenant_id="system", app_name="app")
    context = ApplicationConfig(application).get_cluster_application_config(
        cluster_id, namespace=namespace, is_global=target_is_global
    )
    for key in ["resource_filter_config_logs", "resource_filter_config_metrics"]:
        assert ("from_cache" in context[key]) is not is_global
    targets.assert_not_called()


@pytest.mark.parametrize("is_global", [False, True])
def test_platform_context_uses_target_role_without_reading_global_settings(settings, mocker, is_global):
    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = ["cluster-a"] if is_global else []
    [(cluster_id, namespace, target_is_global)] = ClusterConfig.get_deploy_mapping({"cluster-a": [1]})
    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = [] if is_global else ["cluster-a"]
    ClusterConfig.global_deploy_targets.cache_clear()
    targets = mocker.spy(ClusterConfig, "global_deploy_targets")
    for method in [
        "get_apdex_config",
        "get_sampler_config",
        "get_resource_filter_config",
        "get_qps_config",
        "list_metric_config",
        "get_license_config",
        "get_attribute_config",
        "get_field_normalizer_config",
    ]:
        mocker.patch.object(PlatformConfig, method, return_value={})
    relation = mocker.patch("apm.core.platform_config.BcsClusterDefaultApplicationRelation.objects.filter")
    relation.return_value.first.return_value = SimpleNamespace(application=object())
    mocker.patch.object(PlatformConfig, "get_dataids_config_from_application", return_value={"fixed_token": "business"})
    mocker.patch("apm.core.platform_config.get_bk_data_token_aes_key", return_value="test-key")
    kube = mocker.patch("apm.core.platform_config.BcsKubeClient").return_value
    kube.client_request.return_value = SimpleNamespace(
        items=[SimpleNamespace(metadata=SimpleNamespace(name="operator"))]
    )

    context = PlatformConfig.get_platform_config(cluster_id, namespace=namespace, is_global=target_is_global)
    assert ("fixed_token" in context["token_checker_config"]) is not is_global
    assert ("resource_fill_dimensions_config" in context) is not is_global
    assert relation.call_count == kube.client_request.call_count == (0 if is_global else 1)
    targets.assert_not_called()


@pytest.mark.parametrize("protocol", ["json", "prometheus"])
@pytest.mark.parametrize("business_is_public", [False, True])
def test_custom_report_global_batch_and_business_batch_are_separate(
    protocol, business_is_public, multi_target_delivery, mocker, settings
):
    targets = mocker.spy(ClusterConfig, "global_deploy_targets")
    if business_is_public:
        settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER += ["cluster-a/operator-ns"]
    public_namespaces = ["operator-ns", "public-1", "public-2"] if business_is_public else ["public-1", "public-2"]
    clean = mocker.patch.object(ClusterConfig, "clean_dup_secrets_in_multi_protocol")
    result = CustomReportSubscription._refresh_k8s_custom_config_by_biz(0, [({"bk_data_id": 10, "biz": 1}, protocol)])
    assert result["cluster_count"] == 1
    assert result["target_count"] == len(public_namespaces)
    assert [record["namespace"] for record in result["clusters"]] == public_namespaces
    assert [call.kwargs["namespace"] for call in clean.call_args_list] == public_namespaces
    targets.assert_called_once_with()
    targets.reset_mock()
    multi_target_delivery.reset_mock()
    result = CustomReportSubscription._refresh_k8s_custom_config_by_biz(1, [({"bk_data_id": 10, "biz": 1}, protocol)])
    business_namespaces = [] if business_is_public else ["operator-ns"]
    assert [record["namespace"] for record in result["clusters"]] == business_namespaces
    targets.assert_called_once_with()


def test_failed_target_does_not_clean_or_block_other_targets(multi_target_delivery, mocker):
    def deploy(cluster_id, configs, protocol, namespace):
        if namespace == "public-1":
            raise RuntimeError("unavailable target")

    multi_target_delivery.side_effect = deploy
    clean = mocker.patch.object(ClusterConfig, "clean_dup_secrets_in_multi_protocol")
    result = CustomReportSubscription._refresh_k8s_custom_config_by_biz(0, [({"bk_data_id": 10}, "json")])
    assert result["result"] is False
    assert result["failed_count"] == 1
    assert len(result["clusters"]) == 2
    assert [call.kwargs["namespace"] for call in clean.call_args_list] == ["public-2"]


def test_cleanup_command_defaults_to_public_targets_and_remains_dry_run(settings, mocker):
    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = [
        "cluster-a/public-1",
        "cluster-a/public-2",
        "cluster-b/public-1",
        "cluster-a/public-1",
    ]
    command = Command()
    mocker.patch.object(
        command,
        "_get_disabled_configs",
        return_value={
            "json": [
                {
                    "bk_data_id": 1,
                    "bk_biz_id": 1,
                    "bk_tenant_id": "system",
                    "type": "event",
                    "group_id": 1,
                    "group_name": "event",
                }
            ]
        },
    )
    clean = mocker.patch.object(ClusterConfig, "clean_sub_configs", return_value=[])
    command.handle(bk_tenant_id="system", type="all", execute=False)
    assert [(call.kwargs["cluster_id"], call.kwargs["namespace"]) for call in clean.call_args_list] == [
        ("cluster-a", "public-1"),
        ("cluster-a", "public-2"),
        ("cluster-b", "public-1"),
    ]
    assert all(call.kwargs["dry_run"] for call in clean.call_args_list)
    clean.reset_mock()
    command.handle(bk_tenant_id="system", type="all", execute=False, cluster_id=["cluster-a"])
    assert [call.kwargs["namespace"] for call in clean.call_args_list] == ["public-1", "public-2"]
    clean.reset_mock()
    command.handle(bk_tenant_id="system", type="all", execute=False, cluster_id=["cluster-a"], namespace="old-public")
    assert clean.call_args.kwargs["namespace"] == "old-public"


def test_cleanup_invalid_public_target_is_logged_and_skipped(settings, caplog, capsys):
    caplog.set_level("WARNING", logger="bkmonitor.utils.bk_collector_config")
    settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER = ["cluster-a/"]
    Command().handle(bk_tenant_id="system", type="all", execute=False)
    assert "invalid public collector target" in caplog.text
    assert "no target k8s cluster configured, skip" in capsys.readouterr().out


def test_cleanup_explicit_non_public_cluster_uses_its_business_namespace(mocker):
    command = Command()
    configs = mocker.patch.object(command, "_get_disabled_configs", return_value={"apm": []})
    assert command._get_target_cluster_ids(["cluster-b", "cluster-b"]) == [("cluster-b", "bkmonitor-operator")]
    with pytest.raises(CommandError, match="invalid collector namespace"):
        command.handle(bk_tenant_id="system", type="all", execute=True, cluster_id=["cluster-a"], namespace="*")
    configs.assert_not_called()


@pytest.mark.parametrize("cluster_ids", [[], ["cluster-a", "cluster-b"]])
def test_cleanup_explicit_namespace_requires_one_explicit_cluster(cluster_ids):
    with pytest.raises(CommandError):
        Command().handle(
            bk_tenant_id="system", type="all", execute=False, cluster_id=cluster_ids, namespace="old-public"
        )
