from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace

import pytest
import yaml

from core.errors.collecting import CollectConfigVersionChanged, LegacyConversionFailed
from monitor_web.collecting.resources import tencent_cloud as api
from monitor_web.collecting.tencent_cloud import effective_config, render_config, validate_files


CONTRACT = {"version": "v0.21.0", "products": {"QCE/CVM": ["InstanceId"], "QCE/COS": ["appid", "bucket"]}}
UID = "e6cc3fa6-302f-4fdd-966c-306547b48339"
IMAGE = "example.com/collector@sha256:" + "a" * 64


@pytest.fixture
def config():
    return {
        "credential": {"region": "ap-guangzhou", "is_internal": False},
        "rate_limit": 20,
        "products": [
            {
                "namespace": "QCE/CVM",
                "all_instances": True,
                "all_metrics": True,
                "delay_seconds": 0,
                "exclude_instances": [],
            }
        ],
    }


def upload(config, uid=UID, filename="example.yaml"):
    return {
        "uid": uid,
        "filename": filename,
        "content": yaml.safe_dump(
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {"name": "user-name"},
                "data": {"qcloud.yml": yaml.safe_dump(config)},
            }
        ),
    }


def validate(config, **collector):
    return validate_files([upload(config)], {"period": 60, "timeout": 60, **collector}, CONTRACT)


def test_preview_preserves_semantics_and_input(config):
    before = deepcopy(config)
    result = validate(config)
    assert result["valid"]
    preview = result["files"][0]["preview"]
    tree = yaml.safe_load(preview["qcloud_yaml"])
    expected = deepcopy(config)
    expected["credential"].update(access_key="", secret_key="")
    assert tree == expected
    assert tree == effective_config(config, {"period": 60, "timeout": 60}, CONTRACT)
    assert config == before
    assert "Secret 注入" in preview["qcloud_yaml"]
    assert preview["credential_source"] == "secret_env"
    assert "collect_timeout" not in tree
    assert "metric_name_type" not in tree["products"][0]
    assert "warnings" not in result
    assert result["files"][0]["summary"] == {"region": "ap-guangzhou", "products": ["QCE/CVM"]}


@pytest.mark.parametrize(
    "raw,timeout,period,valid",
    [
        (None, 60, 60, True),
        (60, 60, 60, True),
        (45, 50, 60, True),
        (50, 50, 60, True),
        (53, 50, 60, False),
        (None, 50, 60, False),
        (45, 61, 60, False),
        (3, 4, 4, True),
        (3, 3, 4, False),
        (4, 2, 4, True),
        (0, 60, 60, False),
        (True, 60, 60, False),
        (1.5, 60, 60, False),
        (60, True, 60, False),
        (60, 60, "60", False),
    ],
)
def test_timeout_budget(config, raw, timeout, period, valid):
    if raw is not None:
        config["collect_timeout"] = raw
    assert validate(config, timeout=timeout, period=period)["valid"] is valid


@pytest.mark.parametrize("secret_key", ["access_key", "secret_key", "token"])
def test_credentials_rejected_without_echo(config, secret_key):
    config["credential"][secret_key] = "fixture-secret-never-echo"
    result = validate(config)
    assert not result["valid"]
    assert result["files"][0]["preview"] is None
    assert result["files"][0]["errors"][0]["code"] == "CREDENTIAL_IN_CONFIGMAP"
    assert "fixture-secret-never-echo" not in str(result)


@pytest.mark.parametrize(
    "content,code",
    [
        ("kind: ConfigMap\nkind: Secret", "YAML_DUPLICATE_KEY"),
        ("a: b\n---\na: b", "CONFIGMAP_COUNT_INVALID"),
        ("!!python/object/apply:os.system ['echo unsafe']", "YAML_INVALID"),
        ("a: &a [*a]", "CONFIGMAP_KIND_INVALID"),
        ("? [secret]\n: value", "YAML_INVALID"),
        ("[unterminated-secret", "YAML_INVALID"),
        ("apiVersion: v1\nkind: Secret", "CONFIGMAP_KIND_INVALID"),
        ("apiVersion: v1\nkind: ConfigMap\ndata: {qcloud.yml: {}}", "CONFIGMAP_DATA_INVALID"),
        ("apiVersion: v1\nkind: ConfigMap\ndata: {qcloud.yml: '', script.sh: ''}", "CONFIGMAP_DATA_INVALID"),
    ],
)
def test_unsafe_outer_yaml(config, content, code):
    file = upload(config)
    file["content"] = content
    result = validate_files([file], {"period": 60, "timeout": 60}, CONTRACT)
    assert result["files"][0]["errors"][0]["code"] == code
    assert result["files"][0]["preview"] is None
    assert "unterminated-secret" not in str(result)


@pytest.mark.parametrize(
    "inner,code",
    [
        ("credential: {}\ncredential: {}", "YAML_DUPLICATE_KEY"),
        ("a: b\n---\na: b", "QCLOUD_CONFIG_INVALID"),
        ("[]", "QCLOUD_CONFIG_INVALID"),
        ("credential: &c [*c]", "QCLOUD_CONFIG_INVALID"),
    ],
)
def test_inner_yaml(config, inner, code):
    file = upload(config)
    outer = yaml.safe_load(file["content"])
    outer["data"]["qcloud.yml"] = inner
    file["content"] = yaml.safe_dump(outer)
    result = validate_files([file], {"period": 60, "timeout": 60}, CONTRACT)
    assert result["files"][0]["errors"][0]["code"] == code


@pytest.mark.parametrize("layer", ["outer", "inner"])
@pytest.mark.parametrize(
    "tagged_value",
    [
        "!!bool private-marker",
        '!!int ""',
        "!!timestamp private-marker",
        "!unknown private-marker",
        "!!python/object/apply:builtins.input [private-marker]",
    ],
)
def test_invalid_yaml_tag_is_isolated_to_file(config, layer, tagged_value, mocker):
    injected_call = mocker.patch("builtins.input")
    bad = upload(config)
    if layer == "outer":
        bad["content"] += f"extra: {tagged_value}\n"
    else:
        outer = yaml.safe_load(bad["content"])
        outer["data"]["qcloud.yml"] += f"extra: {tagged_value}\n"
        bad["content"] = yaml.safe_dump(outer)
    good = upload(config, uid="e6cc3fa6-302f-4fdd-966c-306547b48340")
    result = validate_files([bad, good], {"period": 60, "timeout": 60}, CONTRACT)
    failed, success = result["files"]
    assert not result["valid"] and not failed["valid"]
    assert failed["preview"] is None
    assert failed["errors"] == [
        {"code": "YAML_INVALID", "path": "content" if layer == "outer" else "qcloud.yml", "message": "YAML 格式无效"}
    ]
    assert "private-marker" not in str(result)
    injected_call.assert_not_called()
    assert success["valid"]
    assert yaml.safe_load(success["preview"]["qcloud_yaml"])["products"] == config["products"]


def test_dedup_is_full_text_and_uid(config):
    first = upload(config)
    second = upload(config, uid="e6cc3fa6-302f-4fdd-966c-306547b48340", filename="other.yml")
    result = validate_files([first, second], {"period": 60, "timeout": 60}, CONTRACT)
    assert result["files"][1]["errors"][0]["related_uid"] == UID
    second["content"] += "\n# distinct text\n"
    assert validate_files([first, second], {"period": 60, "timeout": 60}, CONTRACT)["valid"]
    second["uid"] = UID.upper()
    result = validate_files([first, second], {"period": 60, "timeout": 60}, CONTRACT)
    assert result["files"][1]["errors"][0]["code"] == "UID_DUPLICATED"


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c["products"][0].update(namespace="QCE/ETCD"),
        lambda c: c["products"][0].update(namespace="QCE/UNKNOWN"),
        lambda c: c["products"][0].update(all_instances="false"),
        lambda c: c["products"][0].update(custom_query_dimensions=[{"wrong": "id"}]),
        lambda c: c.update(unknown="hidden-secret"),
        lambda c: c.update(rate_limit=float("nan")),
        lambda c: c["credential"].update(region=""),
        lambda c: c.update(products=[]),
        lambda c: c.update(project_label=True),
    ],
)
def test_invalid_config(config, change):
    change(config)
    result = validate(config)
    assert not result["valid"]
    assert result["files"][0]["preview"] is None
    assert "hidden-secret" not in str(result)


def test_new_contract_fields(config):
    config.update(project_label=False, tag_filters=[{"tag_key": "team", "tag_value": ["a"]}])
    config["products"][0]["project_label"] = True
    result = validate_files([upload(config)], {"period": 60, "timeout": 60}, {**CONTRACT, "version": "v0.22.4"})
    assert result["valid"]
    assert yaml.safe_load(result["files"][0]["preview"]["qcloud_yaml"])["tag_filters"] == config["tag_filters"]


@pytest.fixture
def request_data(config, settings):
    settings.TENCENT_CLOUD_EXPORTER_CONTRACTS = {
        IMAGE: {**CONTRACT, "templates": [sha256(f"image: {IMAGE}".encode()).hexdigest()]}
    }
    settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG = {"collector_json": {"template": f"image: {IMAGE}"}}
    return {
        "bk_biz_id": 2,
        "params": {
            "collector": {"period": 60, "timeout": 60},
            "plugin": {"config_mode": "configmap", "configmaps": [upload(config)]},
        },
    }


def test_create_validation_without_model_calls(request_data, mocker):
    manager = mocker.patch.object(api.CollectConfigMeta, "objects")
    resource = api.ValidateTencentCloudConfigmapResource()
    assert resource.request(request_data)["valid"]
    assert not manager.mock_calls


@pytest.mark.parametrize("extra", [{"runtime": {}}, {"image": "unknown"}, {"deployment_id": 1}])
def test_request_rejects_client_runtime_and_incomplete_edit(request_data, extra):
    request_data.update(extra)
    with pytest.raises(Exception):
        api.ValidateTencentCloudConfigmapResource().validate_request_data(request_data)


def test_edit_checks_version_tenant_and_readonly(request_data, mocker, settings):
    request_data.update(id=10, deployment_id=20)
    deployment = SimpleNamespace(
        params={"plugin": {"secret_key": "fixture-secret"}},
        plugin_version=SimpleNamespace(
            config=SimpleNamespace(
                collector_json=deepcopy(settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG["collector_json"])
            )
        ),
    )
    config = SimpleNamespace(plugin_id="qcloud_exporter_2", deployment_config_id=20, deployment_config=deployment)
    before = deepcopy(deployment.params)
    manager = mocker.patch.object(api.CollectConfigMeta.objects, "select_related")
    manager.return_value.get.return_value = config
    mocker.patch.object(api, "get_request_tenant_id", return_value="tenant-a")
    resource = api.ValidateTencentCloudConfigmapResource()
    assert resource.request(request_data)["valid"]
    manager.return_value.get.assert_called_once_with(id=10, bk_biz_id=2, bk_tenant_id="tenant-a")
    assert deployment.params == before
    config.deployment_config_id = 21
    with pytest.raises(CollectConfigVersionChanged):
        resource.request(request_data)


def test_unknown_image_fails_closed(settings):
    settings.TENCENT_CLOUD_EXPORTER_CONTRACTS = {
        IMAGE: {**CONTRACT, "templates": [sha256(f"image: {IMAGE}".encode()).hexdigest()]}
    }
    for template in ("image: unknown", "image: {{ values.image }}", "", "image: a\nimage: b"):
        with pytest.raises(LegacyConversionFailed):
            api.resolve_contract({"template": template})
    with pytest.raises(LegacyConversionFailed):
        api.resolve_contract({}, {"image": IMAGE, "contract": "qcloud-exporter-v0.22.4"})


def test_validate_is_manage_permission():
    from bkmonitor.iam import ActionEnum
    from monitor_web.collecting.views import CollectingConfigViewSet

    view = CollectingConfigViewSet()
    view.request = SimpleNamespace(method="POST")
    view.action = "validate_tencent_cloud_configmap"
    assert view.action not in view.query_post_actions
    assert view.iam_write_actions == ActionEnum.MANAGE_COLLECTION
    assert view.get_permissions()[0].actions == [ActionEnum.MANAGE_COLLECTION]


def test_empty_and_independent_file_results(config):
    assert validate_files([], {"period": 60, "timeout": 60}, CONTRACT)["errors"][0]["code"] == "CONFIGMAP_REQUIRED"
    bad = upload(config, "e6cc3fa6-302f-4fdd-966c-306547b48340", "bad.txt")
    result = validate_files([upload(config), bad], {"period": 60, "timeout": 60}, CONTRACT)
    assert not result["valid"]
    assert result["files"][0]["valid"]
    assert result["files"][1]["errors"][0]["code"] == "FILE_TYPE_INVALID"


def test_unicode_and_size_boundary(config):
    file = upload(config)
    file["content"] = "\ud800"
    assert (
        validate_files([file], {"period": 60, "timeout": 60}, CONTRACT)["files"][0]["errors"][0]["code"]
        == "FILE_ENCODING_INVALID"
    )
    config["filename"] = "a" * (1024 * 1024)
    result = validate(config)
    assert result["files"][0]["errors"][0]["code"] == "CONFIGMAP_DATA_INVALID"


def test_advanced_fields_are_preserved(config):
    config.update(
        tag_key_operation=0,
        tag_key_replace={},
        cache_interval=0,
        metrics=[
            {
                "tc_namespace": "QCE/CVM",
                "tc_metric_name": "CPUUsage",
                "tc_metric_name_type": 2,
                "tc_myself_dimensions": {"InstanceId": "ins-example"},
                "tc_statistics": ["max"],
            }
        ],
    )
    config["products"][0].update(
        period_seconds=0,
        range_seconds=0,
        metric_name_type=2,
        extra_period_seconds=[],
        instance_filters={},
        req_params="{}",
        tag_key_operation=0,
    )
    result = validate(config)
    assert result["valid"]
    tree = yaml.safe_load(result["files"][0]["preview"]["qcloud_yaml"])
    assert tree["products"] == config["products"]
    assert tree["metrics"] == config["metrics"]


@pytest.mark.parametrize("field,value", [("rate_limit", 10**1000), ("collect_timeout", 2**64)])
def test_numeric_overflow_is_a_safe_error(config, field, value):
    config[field] = value
    assert not validate(config)["valid"]


def test_metric_int32_overflow(config):
    config["products"][0]["metric_name_type"] = 2**32
    assert not validate(config)["valid"]


def test_known_image_in_unknown_template_is_not_trusted(request_data, settings):
    with pytest.raises(LegacyConversionFailed):
        api.resolve_contract({"template": f"image: {IMAGE}\nunknown: template"})


def test_live_source_contract_wins_over_global(request_data, mocker, settings):
    request_data.update(id=10, deployment_id=20)
    runtime = {"image": IMAGE, "contract": "qcloud-exporter-v0.21.0"}
    source = SimpleNamespace(
        params={"runtime": runtime}, plugin_version=SimpleNamespace(config=SimpleNamespace(collector_json={}))
    )
    meta = SimpleNamespace(plugin_id="qcloud_exporter_2", deployment_config_id=20, deployment_config=source)
    mocker.patch.object(api.CollectConfigMeta.objects, "select_related").return_value.get.return_value = meta
    settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG = {"collector_json": {"template": "image: unknown"}}
    assert api.ValidateTencentCloudConfigmapResource().request(request_data)["valid"]
    assert runtime == {"image": IMAGE, "contract": "qcloud-exporter-v0.21.0"}


def test_edit_not_found_does_not_resolve_or_validate(request_data, mocker):
    from core.errors.collecting import CollectConfigNotExist

    request_data.update(id=10, deployment_id=20)
    mocker.patch.object(
        api.CollectConfigMeta.objects, "select_related"
    ).return_value.get.side_effect = api.CollectConfigMeta.DoesNotExist
    resolver = mocker.patch.object(api, "resolve_contract")
    with pytest.raises(CollectConfigNotExist):
        api.ValidateTencentCloudConfigmapResource().request(request_data)
    resolver.assert_not_called()


def test_endpoint_registration():
    from monitor_web.collecting.views import CollectingConfigViewSet

    route = next(r for r in CollectingConfigViewSet.resource_routes if r.endpoint == "validate_tencent_cloud_configmap")
    assert route.method == "POST"
    assert route.resource_class is api.ValidateTencentCloudConfigmapResource


@pytest.mark.parametrize("escape", [r"\uD800", r"\uDFFF"])
@pytest.mark.parametrize("layer", ["outer", "inner"])
def test_escaped_surrogate_is_a_file_error_and_batch_continues(config, escape, layer):
    bad = upload(config)
    if layer == "outer":
        bad["content"] = f'apiVersion: v1\nkind: ConfigMap\ndata:\n  qcloud.yml: "{escape}"\n'
    else:
        outer = yaml.safe_load(bad["content"])
        outer["data"]["qcloud.yml"] += f'filename: "private-marker-{escape}"\n'
        bad["content"] = yaml.safe_dump(outer)
    good = upload(config, uid="e6cc3fa6-302f-4fdd-966c-306547b48340")
    # 原始上传内容可编码；错误只在 YAML 解码转义序列后出现。
    bad["content"].encode("utf-8")
    result = validate_files([bad, good], {"period": 60, "timeout": 60}, CONTRACT)
    assert not result["valid"]
    assert result["files"][0]["preview"] is None
    assert result["files"][0]["errors"] == [
        {
            "code": "FILE_ENCODING_INVALID",
            "path": "content" if layer == "outer" else "qcloud.yml",
            "message": "YAML 文本必须是有效 UTF-8 字符串",
        }
    ]
    assert "private-marker" not in str(result)
    assert result["files"][1]["valid"]
    assert result["files"][1]["preview"] is not None


def test_credential_alias_does_not_change_other_fields(config):
    config["credential"] = {"region": "ap-guangzhou"}
    config["tag_key_replace"] = config["credential"]
    config["products"][0]["tag_key_replace"] = config["credential"]
    original = deepcopy(config)
    file = upload(config)
    assert "&id001" in yaml.safe_load(file["content"])["data"]["qcloud.yml"]
    effective = effective_config(config, {"period": 60, "timeout": 60}, CONTRACT)
    result = validate_files([file], {"period": 60, "timeout": 60}, CONTRACT)
    assert result["valid"]
    preview = result["files"][0]["preview"]["qcloud_yaml"]
    tree = yaml.safe_load(preview)
    expected = deepcopy(original)
    expected["credential"] = {**expected["credential"], "access_key": "", "secret_key": ""}
    assert tree == effective == expected
    assert config == original
    assert "# 凭据由平台通过 Secret 注入，无需在配置文件中填写" in preview


def test_preview_comment_preserves_anchored_mapping(config):
    config["credential"] = {"region": "ap-guangzhou", "access_key": "", "secret_key": ""}
    config["tag_key_replace"] = config["credential"]
    preview = render_config(config)
    assert preview.startswith("credential: &")
    assert preview.splitlines()[1] == "  # 凭据由平台通过 Secret 注入，无需在配置文件中填写"
    assert yaml.safe_load(preview) == config
