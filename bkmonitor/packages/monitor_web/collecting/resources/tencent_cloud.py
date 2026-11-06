"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re
from copy import deepcopy
from hashlib import sha256
from textwrap import indent
from uuid import NAMESPACE_URL, uuid5

import yaml
from django.conf import settings
from jinja2 import TemplateError
from rest_framework import serializers

from bkmonitor.utils.request import get_request_tenant_id
from core.drf_resource.base import Resource
from core.errors.collecting import (
    CollectConfigNotExist,
    CollectConfigParamsError,
    CollectConfigVersionChanged,
    LegacyConversionFailed,
)
from monitor_web.collecting.deploy.k8s import K8sInstaller
from monitor_web.collecting.params import stored_detail
from monitor_web.collecting.tencent_cloud import ConfigLoader, load_yaml, validate_files
from monitor_web.models import CollectConfigMeta


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict) and data.keys() - self.fields.keys():
            raise serializers.ValidationError("请求包含不支持的字段")
        return super().to_internal_value(data)


class ConfigMapFileSerializer(StrictSerializer):
    uid = serializers.CharField(trim_whitespace=False)
    filename = serializers.CharField(trim_whitespace=False)
    content = serializers.CharField(allow_blank=True, trim_whitespace=False)


class ConfigMapPluginSerializer(StrictSerializer):
    config_mode = serializers.CharField()
    configmaps = ConfigMapFileSerializer(many=True, allow_empty=True)

    def validate_config_mode(self, value):
        if value != "configmap":
            raise serializers.ValidationError("配置模式必须为 configmap")
        return value


class CollectorSerializer(StrictSerializer):
    # 保留原始 JSON 类型，由静态校验返回 TIMEOUT_INVALID，禁止 bool/浮点数隐式转整数。
    period = serializers.JSONField()
    timeout = serializers.JSONField()


class ParamsSerializer(StrictSerializer):
    collector = CollectorSerializer()
    plugin = ConfigMapPluginSerializer()


def resolve_contract(collector_json, runtime=None):
    """只读识别已登记镜像。历史模板只接受唯一的静态 image，不执行用户输入或模板。"""
    if runtime is not None:
        if not isinstance(runtime, dict):
            raise LegacyConversionFailed()
        image = runtime.get("image")
    else:
        template = collector_json.get("template", "")
        if not isinstance(template, str):
            raise LegacyConversionFailed()
        candidates = re.findall(r"^\s*image:\s*([^\n]+)$", template, re.MULTILINE)
        if len(candidates) != 1 or "{{" in candidates[0] or "{%" in candidates[0]:
            raise LegacyConversionFailed()
        try:
            image = yaml.safe_load(candidates[0])
        except yaml.YAMLError:
            raise LegacyConversionFailed() from None
    if not isinstance(image, str):
        raise LegacyConversionFailed()
    contract = settings.TENCENT_CLOUD_EXPORTER_CONTRACTS.get(image)
    if (
        not isinstance(contract, dict)
        or contract.get("version") not in ("v0.21.0", "v0.22.4")
        or not isinstance(contract.get("products"), dict)
        or not contract["products"]
    ):
        raise LegacyConversionFailed()
    if any(
        not isinstance(namespace, str)
        or not isinstance(dimensions, list)
        or any(not isinstance(dimension, str) for dimension in dimensions)
        for namespace, dimensions in contract["products"].items()
    ):
        raise LegacyConversionFailed()
    if runtime is None and sha256(template.encode("utf-8")).hexdigest() not in contract.get("templates", []):
        # 不能只凭模板中某一行出现已知镜像，就将任意历史模板认作已核验契约。
        raise LegacyConversionFailed()
    if runtime is not None and runtime.get("contract") != f"qcloud-exporter-{contract['version']}":
        raise LegacyConversionFailed()
    return deepcopy(contract)


def is_tencent_cloud_config(config):
    base = settings.TENCENT_CLOUD_METRIC_PLUGIN_ID
    return config.collect_type == CollectConfigMeta.CollectType.K8S and config.plugin_id in (
        base,
        f"{base}_{config.bk_biz_id}",
    )


def form_detail(config, params_format):
    if params_format == "configmap":
        params = configmap_projection(config)
        info = config.deployment_config.plugin_version.get_plugin_version_detail()
        info.update(config_mode="configmap", config_json=configmap_form(), collector_json={})
        return params, info

    params, info = stored_detail(config)
    credential_fields = ("secret_id", "access_key", "secret_key")
    source = config.deployment_config
    defaults = source.plugin_version.config.collector_json.get("values") or {}
    stored = source.params.get("plugin", {})
    for key in credential_fields:
        if key in stored or key in defaults:
            params.setdefault("plugin", {})[key] = bool(stored.get(key, defaults.get(key)))

    # stored 视图沿用旧表单结构，插件元数据里的凭据默认值也不能随详情返回。
    collector = info["collector_json"]
    if collector.get("values"):
        values = {key: "" if key in credential_fields else value for key, value in collector["values"].items()}
        info["collector_json"] = {**collector, "values": values}
    info["config_json"] = [
        {**field, "default": ""} if field.get("key", field["name"]) in credential_fields else field
        for field in info["config_json"]
    ]
    return params, info


def prepare_edit_params(config_meta: CollectConfigMeta, params: dict) -> None:
    source = config_meta.deployment_config
    stored = source.params.get("plugin", {})
    if "config_mode" in stored:
        return
    plugin = params.setdefault("plugin", {})
    if not isinstance(plugin, dict):
        raise CollectConfigParamsError(msg="plugin 必须为对象")

    # 历史安装器以部署参数覆盖源模板默认值；仅省略字段或 true 占位时沿用该值。
    defaults = source.plugin_version.config.collector_json.get("values") or {}
    for field in ("secret_id", "secret_key"):
        value = plugin.get(field, True)
        if value is True:
            value = stored.get(field, defaults.get(field))
        if not isinstance(value, str) or not value:
            raise CollectConfigParamsError(msg=f"{field} 必须填写")
        plugin[field] = value


def configmap_form():
    return [
        {
            "name": "access_key",
            "description": "Secret ID",
            "mode": "plugin",
            "type": "password",
            "required": True,
            "default": "",
        },
        {
            "name": "secret_key",
            "description": "Secret Key",
            "mode": "plugin",
            "type": "password",
            "required": True,
            "default": "",
        },
        {
            "name": "configmaps",
            "description": "ConfigMap",
            "mode": "plugin",
            "type": "file",
            "multiple": True,
            "accept": ".yaml,.yml",
            "required": True,
            "default": [],
        },
    ]


def conversion_failed(path):
    # 路径只能来自本模块或静态校验器，不拼接源值、模板和解析异常。
    return LegacyConversionFailed(context="LEGACY_CONVERSION_FAILED：历史采集配置无法无损回填", data={"path": path})


def legacy_configmap(config):
    source = config.deployment_config
    definition = source.plugin_version.config
    plugin = source.params["plugin"]
    known = {item.get("key", item["name"]) for item in definition.config_json if item.get("mode") != "collector"}
    if plugin.keys() - known:
        raise conversion_failed("params.plugin")
    values, manifests = K8sInstaller(config).render_snapshot(source)
    maps = [
        doc
        for doc in yaml.load_all(manifests, Loader=ConfigLoader)
        if isinstance(doc, dict) and doc.get("kind") == "ConfigMap"
    ]
    if len(maps) != 1 or set(maps[0].get("data", {})) != {"config.yml"}:
        raise conversion_failed("config.yml")
    tree = load_yaml(maps[0]["data"]["config.yml"], "config.yml")
    credential = tree["credential"]
    if not isinstance(credential, dict):
        raise conversion_failed("config.yml.credential")
    access_key, secret_key = values.get("secret_id", ""), values.get("secret_key", "")
    for field, expected in (("access_key", access_key), ("secret_key", secret_key)):
        if not isinstance(expected, str) or credential.get(field, "") != expected:
            raise conversion_failed("config.yml.credential")
    tree["credential"] = {**credential, "access_key": "", "secret_key": ""}
    inner = yaml.safe_dump(tree, allow_unicode=True, sort_keys=False)
    uid = uuid5(NAMESPACE_URL, f"qcloud/{config.bk_tenant_id}/{config.bk_biz_id}/{config.id}/{source.id}/config.yml")
    header = "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: qcloud-exporter\ndata:\n  qcloud.yml: |\n"
    file = {"uid": str(uid), "filename": "legacy.yaml", "content": header + indent(inner, "    ")}
    return [file], access_key, secret_key


def configmap_projection(config):
    source = config.deployment_config
    params = source.params
    try:
        plugin = params["plugin"]
        contract = resolve_contract(source.plugin_version.config.collector_json, params.get("runtime"))
        collector = {"period": 60, "timeout": 60, **deepcopy(params.get("collector", {}))}
        if "config_mode" not in plugin and "runtime" not in params:
            files, access_key, secret_key = legacy_configmap(config)
        elif plugin.get("config_mode") == "configmap" and params.get("runtime"):
            if plugin.keys() - {"config_mode", "configmaps", "access_key", "secret_key"}:
                raise conversion_failed("params.plugin")
            files = [{key: row[key] for key in ("uid", "filename", "content")} for row in plugin["configmaps"]]
            access_key, secret_key = plugin.get("access_key", ""), plugin.get("secret_key", "")
            if not isinstance(access_key, str) or not isinstance(secret_key, str):
                raise conversion_failed("params.plugin")
        else:
            raise conversion_failed("params.plugin.config_mode")
        validated = validate_files(files, collector, contract)
        if not validated["valid"]:
            errors = validated["errors"] or next(row["errors"] for row in validated["files"] if row["errors"])
            raise conversion_failed(errors[0]["path"])
        for file, validated_file in zip(files, validated["files"]):
            preview = validated_file["preview"]
            if any(
                value and any(value in text for text in (file["filename"], file["content"], preview["qcloud_yaml"]))
                for value in (access_key, secret_key)
            ):
                raise conversion_failed("configmaps.content")
            file["preview"] = preview
        return {
            "collector": collector,
            "plugin": {
                "config_mode": "configmap",
                "access_key": bool(access_key),
                "secret_key": bool(secret_key),
                "configmaps": files,
            },
        }
    except (
        yaml.YAMLError,
        TemplateError,
        LookupError,
        TypeError,
        ValueError,
        AttributeError,
        OverflowError,
        RecursionError,
    ):
        raise conversion_failed("params.plugin") from None


class ValidateTencentCloudConfigmapResource(Resource):
    class RequestSerializer(StrictSerializer):
        bk_biz_id = serializers.IntegerField()
        id = serializers.IntegerField(required=False, min_value=1)
        deployment_id = serializers.IntegerField(required=False, min_value=1)
        params = ParamsSerializer()

        def validate(self, attrs):
            if ("id" in attrs) != ("deployment_id" in attrs):
                raise serializers.ValidationError("编辑校验必须同时提供 id 和 deployment_id")
            return attrs

    def perform_request(self, data):
        if "id" in data:
            try:
                config = CollectConfigMeta.objects.select_related("deployment_config__plugin_version__config").get(
                    id=data["id"], bk_biz_id=data["bk_biz_id"], bk_tenant_id=get_request_tenant_id()
                )
            except CollectConfigMeta.DoesNotExist:
                raise CollectConfigNotExist(msg="") from None
            if config.plugin_id not in (
                settings.TENCENT_CLOUD_METRIC_PLUGIN_ID,
                f"{settings.TENCENT_CLOUD_METRIC_PLUGIN_ID}_{data['bk_biz_id']}",
            ):
                raise CollectConfigParamsError(msg="仅支持腾讯云指标采集")
            if config.deployment_config_id != data["deployment_id"]:
                raise CollectConfigVersionChanged()
            source = config.deployment_config
            contract = resolve_contract(source.plugin_version.config.collector_json, source.params.get("runtime"))
        else:
            contract = resolve_contract(settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG.get("collector_json", {}))
        params = data["params"]
        return validate_files(params["plugin"]["configmaps"], params["collector"], contract)
