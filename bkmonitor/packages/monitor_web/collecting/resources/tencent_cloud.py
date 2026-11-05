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

import yaml
from django.conf import settings
from rest_framework import serializers

from bkmonitor.utils.request import get_request_tenant_id
from core.drf_resource.base import Resource
from core.errors.collecting import (
    CollectConfigNotExist,
    CollectConfigParamsError,
    CollectConfigVersionChanged,
    LegacyConversionFailed,
)
from monitor_web.collecting.tencent_cloud import validate_files
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
