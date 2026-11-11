"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from copy import deepcopy
from textwrap import indent
from uuid import NAMESPACE_URL, uuid4, uuid5

import yaml
from django.conf import settings
from django.db import transaction
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
from monitor_web.collecting.constant import OperationResult, OperationType
from monitor_web.collecting.deploy import get_collect_installer
from monitor_web.collecting.deploy.k8s import K8sInstaller
from monitor_web.collecting.deploy.tencent_cloud import freeze_runtime, validated_files
from monitor_web.collecting.params import stored_detail
from monitor_web.collecting.tencent_cloud import (
    ConfigLoader,
    configmap_description,
    new_form_definition,
    load_yaml,
    file_contains_credential,
    is_qcloud_plugin,
    validate_files,
)
from monitor_web.models import CollectConfigMeta


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict) and data.keys() - self.fields.keys():
            raise serializers.ValidationError({"non_field_errors": ["请求包含不支持的字段"]})
        return super().to_internal_value(data)


class ConfigMapFileSerializer(StrictSerializer):
    uid = serializers.CharField(trim_whitespace=False)
    filename = serializers.CharField(trim_whitespace=False)
    content = serializers.CharField(allow_blank=True, trim_whitespace=False)


class ConfigMapPluginSerializer(StrictSerializer):
    access_key = serializers.JSONField(required=False)
    secret_key = serializers.JSONField(required=False)
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


def is_tencent_cloud_config(config):
    return config.collect_type == CollectConfigMeta.CollectType.K8S and is_qcloud_plugin(
        config.plugin_id, config.bk_biz_id
    )


def is_legacy_snapshot(params):
    plugin = params.get("plugin")
    return isinstance(plugin, dict) and "config_mode" not in plugin and "runtime" not in params


def source_credential(source, key):
    defaults = source.plugin_version.config.collector_json.get("values") or {}
    return source.params.get("plugin", {}).get(key, defaults.get(key))


def form_detail(config, params_format):
    if params_format == "configmap" or "runtime" in config.deployment_config.params:
        params = configmap_projection(config)
        info = config.deployment_config.plugin_version.get_plugin_version_detail()
        new_form_definition(info)
        return params, info

    params, info = stored_detail(config)
    info["description_md"] = configmap_description()
    credential_fields = ("secret_id", "access_key", "secret_key")
    source = config.deployment_config
    plugin = params.setdefault("plugin", {})
    fields = ("secret_id", "secret_key") if is_legacy_snapshot(source.params) else ("access_key", "secret_key")
    for key in credential_fields:
        if key in fields or key in plugin:
            value = source_credential(source, key)
            plugin[key] = isinstance(value, str) and bool(value)

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
    if not is_legacy_snapshot(source.params):
        # 使用与详情相同的文件和结构校验；残缺的快照不能进入新版分支。
        configmap_projection(config_meta)
        return
    plugin = params.setdefault("plugin", {})
    if not isinstance(plugin, dict):
        raise CollectConfigParamsError(msg="plugin 必须为对象")

    if "config_mode" in plugin or "runtime" in params:
        raise CollectConfigParamsError(msg="旧表单不支持提交 config_mode 或 runtime")

    for field in ("secret_id", "secret_key"):
        value = plugin.get(field, True)
        if value is True:
            value = source_credential(source, field)
        if not isinstance(value, str) or not value:
            raise CollectConfigParamsError(msg=f"{field} 必须填写")
        plugin[field] = value


def prepare_configmap_snapshot(params, source_config=None):
    """生成供安装器使用的版本参数；调用方负责源版本并发校验与持久化。"""
    serializer = ParamsSerializer(data=params)
    if not serializer.is_valid():
        raise CollectConfigParamsError(msg="配置参数格式无效", data={"errors": serializer.errors})
    params = serializer.validated_data
    plugin = params["plugin"]
    snapshot = deepcopy(params)
    if source_config is not None:
        if not is_tencent_cloud_config(source_config):
            raise CollectConfigParamsError(msg="源配置必须属于腾讯云指标采集")
        previous = configmap_projection(source_config)
        snapshot["collector"] = {**previous["collector"], **snapshot["collector"]}
    for key in ("access_key", "secret_key"):
        value = plugin.get(key, True)
        if value is True and source_config is not None:
            source = source_config.deployment_config
            if is_legacy_snapshot(source.params):
                value = source_credential(source, "secret_id" if key == "access_key" else key)
            else:
                value = source.params["plugin"].get(key)
        if not isinstance(value, str) or not value:
            raise CollectConfigParamsError(msg=f"{key} 必须填写")
        snapshot["plugin"][key] = value
    snapshot["runtime"] = freeze_runtime(source_config)
    validated_files(snapshot)
    return snapshot


def uses_configmap_request(data, config):
    plugin = data["params"].get("plugin")
    requested = isinstance(plugin, dict) and plugin.get("config_mode") == "configmap"
    if config is not None and not is_tencent_cloud_config(config):
        return False
    if config is None and data.get("collect_type") != CollectConfigMeta.CollectType.K8S:
        return False
    if not requested and (config is None or "runtime" not in config.deployment_config.params):
        if config is None and ("runtime" in data["params"] or isinstance(plugin, dict) and "config_mode" in plugin):
            raise CollectConfigParamsError(msg="不支持客户端指定的运行参数")
        return False
    if not requested and config is not None:
        configmap_projection(config)
    if not requested or (config is not None and "deployment_id" not in data):
        raise CollectConfigParamsError(msg="ConfigMap 编辑需提交 config_mode 和源 deployment_id")
    return True


def save_configmap(data, config, get_plugin=None):
    """保存和升级共用快照校验、版本临界区和部署路径。"""
    upgrading = get_plugin is None
    if not upgrading:
        if (
            not is_qcloud_plugin(data["plugin_id"], data["bk_biz_id"])
            or data["collect_type"] != CollectConfigMeta.CollectType.K8S
        ):
            raise CollectConfigParamsError(msg="腾讯云采集插件不匹配")
        if data["target_node_type"] != "CLUSTER" or data["target_object_type"] != "CLUSTER" or data["target_nodes"]:
            raise CollectConfigParamsError(msg="腾讯云采集使用平台集群")
    with transaction.atomic():
        if config is None:
            if "deployment_id" in data:
                raise CollectConfigVersionChanged()
            # 创建业务插件有写入，先完成文件和凭据校验。
            snapshot = prepare_configmap_snapshot(data["params"])
            plugin = get_plugin(data)
            config = CollectConfigMeta(
                bk_tenant_id=get_request_tenant_id(),
                bk_biz_id=data["bk_biz_id"],
                collect_type=data["collect_type"],
                plugin_id=plugin.plugin_id,
                label=data["label"],
                target_object_type=data["target_object_type"],
                name=data["name"],
            )
            installer = get_collect_installer(config)
            recover = False
            operation = OperationType.CREATE
        else:
            installer = get_collect_installer(config)
            installer.lock_current()
            config = installer.collect_config
            if config.deployment_config_id != data.get("deployment_id"):
                raise CollectConfigVersionChanged()
            snapshot = prepare_configmap_snapshot(data["params"], config)
            legacy = is_legacy_snapshot(config.deployment_config.params)
            if legacy:
                installer.legacy_manifests(config.deployment_config, installer._get_default_cluster()[1])
            recover = legacy or config.operation_result != OperationResult.SUCCESS
            operation = OperationType.UPGRADE if upgrading else data["operation"]
            if not upgrading:
                config.name = data["name"]
        version = installer.record_install(
            {"params": snapshot, **({"plugin_version": config.deployment_config.plugin_version} if config.pk else {})},
            operation,
        )
    # 先保留可重试的版本身份，再对最新版本执行外部操作。
    installer.apply_current(operation, recover)
    return config, {"id": config.pk, "deployment_id": version.pk, "can_rollback": bool(version.parent_id)}


def clone_snapshot(config):
    """克隆只准备停用的新配置；保留源模板并生成独立的文件 UID，须补齐凭据才能部署。"""
    projected = configmap_projection(config)
    projected["runtime"] = freeze_runtime(config)
    plugin = projected["plugin"]
    plugin.update(access_key="", secret_key="")
    for row in plugin["configmaps"]:
        row.pop("preview")
        row["uid"] = str(uuid4())
    result = validate_files(plugin["configmaps"], projected["collector"])
    if not result["valid"]:
        raise CollectConfigParamsError(msg="克隆文件配置无效")
    return projected


def clone_config(source, name):
    snapshot = clone_snapshot(source)
    clone = CollectConfigMeta(
        name=name,
        bk_tenant_id=source.bk_tenant_id,
        bk_biz_id=source.bk_biz_id,
        plugin_id=source.plugin_id,
        collect_type=source.collect_type,
        target_object_type=source.target_object_type,
        label=source.label,
        cache_data={},
    )
    installer = get_collect_installer(clone)
    installer.record_install(
        {"params": snapshot, "plugin_version": source.deployment_config.plugin_version}, OperationType.STOP
    )
    clone.operation_result = OperationResult.SUCCESS
    clone.save(update_fields=["operation_result"])


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
        collector = {"period": 60, "timeout": 60, **deepcopy(params.get("collector", {}))}
        if is_legacy_snapshot(params):
            files, access_key, secret_key = legacy_configmap(config)
        elif plugin.get("config_mode") == "configmap" and params.get("runtime"):
            if plugin.keys() != {"config_mode", "configmaps", "access_key", "secret_key"}:
                raise conversion_failed("params.plugin")
            files = [{key: row[key] for key in ("uid", "filename", "content")} for row in plugin["configmaps"]]
            access_key, secret_key = plugin["access_key"], plugin["secret_key"]
            if not isinstance(access_key, str) or not isinstance(secret_key, str):
                raise conversion_failed("params.plugin")
        else:
            raise conversion_failed("params.plugin.config_mode")
        validated = validate_files(files, collector)
        if not validated["valid"]:
            errors = validated["errors"] or next(row["errors"] for row in validated["files"] if row["errors"])
            raise conversion_failed(errors[0]["path"])
        for file, validated_file in zip(files, validated["files"]):
            preview = validated_file["preview"]
            if file_contains_credential(file, preview, (access_key, secret_key)):
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
            if {"access_key", "secret_key"} & attrs["params"]["plugin"].keys():
                raise serializers.ValidationError("预览接口不接收凭据")
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
        params = data["params"]
        return validate_files(params["plugin"]["configmaps"], params["collector"])
