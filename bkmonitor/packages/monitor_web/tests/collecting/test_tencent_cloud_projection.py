"""腾讯云编辑与展示接口对同一历史部署的只读投影。"""

from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import yaml

from core.errors.collecting import LegacyConversionFailed
from monitor_web.collecting.resources import backend, frontend
from monitor_web.collecting.resources.tencent_cloud import K8sInstaller, configmap_projection

IMAGE = "example.com/exporter:test"
TEMPLATE = """apiVersion: v1
kind: ConfigMap
data:
  config.yml: |
    credential:
      access_key: "{{ values.secret_id }}"
      secret_key: "{{ values.secret_key }}"
      region: "{{ values.region }}"
      is_internal: true
    is_international: {{ values.is_international }}
    rate_limit: {{ values.rate_limit }}
    products:
      {%- filter indent(6) %}
{{ values.products }}
      {%- endfilter %}
---
image: example.com/exporter:test
"""
PRODUCT = {
    "namespace": "QCE/REDIS",
    "all_metrics": False,
    "only_include_metrics": [],
    "only_include_instances": ["sample-instance"],
    "reload_interval_minutes": 0,
    "metric_name_type": 0,
    "period_seconds": 60,
    "delay_seconds": 0,
    "range_seconds": 180,
    "req_params": '{\n  "Endpoint": "sample.example.com"\n}\n',
}


def sample_config(template, defaults, params):
    fields = [
        {"name": key, "type": "text", "description": key, "mode": "opt_cmd", "default": ""}
        for key in ("secret_id", "secret_key", "region", "is_international", "rate_limit", "products")
    ]
    definition = SimpleNamespace(collector_json={"template": template, "values": defaults}, config_json=fields)
    version = SimpleNamespace(version="1.0", config_version=1, config=definition)
    version.get_plugin_version_detail = lambda: {
        "plugin_id": "qcloud_exporter_2",
        "plugin_display_name": "Sample",
        "metric_json": [],
        "config_json": fields,
        "collector_json": definition.collector_json,
    }
    deployment = SimpleNamespace(
        id=4,
        params=params,
        plugin_version=version,
        target_nodes=[],
        target_node_type="CLUSTER",
        remote_collecting_host=None,
        subscription_id=None,
    )
    return SimpleNamespace(
        id=3,
        deployment_config_id=4,
        deployment_config=deployment,
        collect_type="K8S",
        bk_tenant_id="system",
        bk_biz_id=2,
        plugin_id="qcloud_exporter_2",
        plugin=SimpleNamespace(plugin_id="qcloud_exporter_2", get_release_ver_by_config_ver=Mock(return_value=version)),
        data_id=1,
        name="sample",
        label="os",
        label_info={},
        target_object_type="CLUSTER",
        create_time="",
        update_time="original",
        create_user="",
        update_user="",
    )


@pytest.fixture
def config(settings, mocker):
    settings.K8S_PLUGIN_COLLECT_CLUSTER_ID = "sample:monitoring"
    settings.TENCENT_CLOUD_EXPORTER_CONTRACTS = {
        IMAGE: {
            "version": "v0.21.0",
            "templates": [sha256(TEMPLATE.encode()).hexdigest()],
            "products": {"QCE/REDIS": []},
        }
    }
    config = sample_config(
        TEMPLATE,
        {"rate_limit": 20, "is_international": "false"},
        {
            "plugin": {
                "secret_id": "sample-access",
                "secret_key": "sample-secret",
                "region": "sample-region",
                "products": yaml.safe_dump([PRODUCT]),
                "rate_limit": "0",
            },
            "collector": {"period": 90, "timeout": 60, "metric_relabel_configs": []},
        },
    )
    mocker.patch.object(backend, "get_request_tenant_id", return_value="system")
    mocker.patch.object(backend.CollectConfigMeta.objects, "select_related").return_value.get.return_value = config
    for name in ("_get_k8s_config", "_deploy", "install"):
        mocker.patch.object(K8sInstaller, name, side_effect=AssertionError("read accessed deployment"))
    return config


def detail(**kwargs):
    resource = backend.CollectConfigDetailResource()
    return resource.perform_request(resource.validate_request_data({"id": 3, "bk_biz_id": 2, **kwargs}))


def test_edit_and_display(config, mocker):
    source = config.deployment_config
    before = deepcopy((source.params, source.plugin_version.config))
    first = detail(params_format="configmap")
    assert first == detail(params_format="configmap")
    assert first["deployment_id"] == source.id and first["update_time"] == "original"
    assert first["params"]["collector"] == before[0]["collector"]
    assert [f["type"] for f in first["plugin_info"]["config_json"]] == ["password", "password", "file"]
    plugin = first["params"]["plugin"]
    assert plugin["access_key"] is plugin["secret_key"] is True
    file = plugin["configmaps"][0]
    expected = {
        "credential": {"access_key": "", "secret_key": "", "region": "sample-region", "is_internal": True},
        "is_international": False,
        "rate_limit": 0,
        "products": [PRODUCT],
    }
    assert yaml.safe_load(yaml.safe_load(file["content"])["data"]["qcloud.yml"]) == expected
    assert yaml.safe_load(file["preview"]["qcloud_yaml"]) == expected
    assert "sample-access" not in str(first) and "sample-secret" not in str(first)
    mocker.patch.object(frontend.resource.collecting, "collect_config_detail", side_effect=detail)
    display = frontend.FrontendCollectConfigDetailResource().perform_request(
        {"id": 3, "bk_biz_id": 2, "params_format": "configmap", "with_target_info": False}
    )
    assert display["extend_info"] == first["params"]
    assert display["runtime_params"][-1]["value"] == [{"uid": file["uid"], "filename": file["filename"]}]
    stored = detail(params_format="stored")
    assert detail() == stored
    assert stored["params"]["plugin"]["secret_id"] is True and stored["params"]["plugin"]["secret_key"] is True
    assert stored["params"]["plugin"]["products"] == before[0]["plugin"]["products"]
    assert before == (source.params, source.plugin_version.config)


def test_new_format_uses_uploaded_content_and_recomputes_preview(config):
    params = configmap_projection(config)
    f = params["plugin"]["configmaps"][0]
    f["content"] = "# user comment\n" + f["content"]
    f["preview"] = {"qcloud_yaml": "obsolete"}
    params["plugin"].update(access_key="", secret_key="sample-secret")
    params["runtime"] = {"contract": "qcloud-exporter-v0.21.0", "image": IMAGE}
    config.deployment_config.params = params
    projected = configmap_projection(config)
    result = projected["plugin"]["configmaps"][0]
    assert result["content"] == f["content"] and result["uid"] == f["uid"]
    assert result["preview"] != f["preview"] and "runtime" not in projected
    assert projected["plugin"]["access_key"] is False and projected["plugin"]["secret_key"] is True


@pytest.mark.parametrize("change", ["unknown-template", "unknown-param", "invalid-products", "secret-in-product"])
def test_unconvertible_snapshot_fails_closed(config, change):
    source = config.deployment_config
    plugin = source.params["plugin"]
    if change == "unknown-template":
        source.plugin_version.config.collector_json["template"] += "# different"
    elif change == "unknown-param":
        plugin["unknown"] = "sample-secret"
    elif change == "invalid-products":
        plugin["products"] = "{namespace: QCE/REDIS}"
    else:
        plugin["products"] = yaml.safe_dump([{**PRODUCT, "req_params": plugin["secret_key"]}])
    before = deepcopy((source.params, source.plugin_version.config))
    with pytest.raises(LegacyConversionFailed) as error:
        detail(params_format="configmap")
    assert "sample-secret" not in str(error.value)
    assert before == (source.params, source.plugin_version.config)
