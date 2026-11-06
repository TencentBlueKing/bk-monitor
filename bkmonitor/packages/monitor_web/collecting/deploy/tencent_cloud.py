"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import json
import re
from copy import deepcopy
from hashlib import sha256
from uuid import UUID

import yaml
from django.conf import settings
from django.utils.crypto import salted_hmac
from jinja2 import TemplateError
from kubernetes import client as k8s_client

from bkmonitor.utils.template import jinja_render
from constants.common import DEFAULT_TENANT_ID
from core.errors.collecting import CollectConfigParamsError, LegacyConversionFailed
from monitor_web.collecting.deploy.k8s import (
    DATA_ID_TEMPLATE,
    SERVICE_MONITOR_TEMPLATE,
    K8sInstaller,
    collector_release_name,
)
from monitor_web.collecting.tencent_cloud import (
    ConfigLoader,
    file_contains_credential,
    resolve_contract,
    template_image,
    validate_files,
)

LABEL = "app.kubernetes.io/"
APP = "qcloud-exporter-managed"
ENV_KEYS = {"access_key": "TENCENTCLOUD_SECRET_ID", "secret_key": "TENCENTCLOUD_SECRET_KEY"}


def runtime_contract(runtime):
    """实际部署只接受受控仓库的不可变镜像和冻结的资源规格。"""
    if not isinstance(runtime, dict) or set(runtime) != {"image", "contract", "resources"}:
        raise LegacyConversionFailed()
    contract = resolve_contract({}, runtime)
    if not re.fullmatch(r"[^@\s]+@sha256:[0-9a-f]{64}", runtime["image"]):
        raise LegacyConversionFailed()
    resources = runtime["resources"]
    if not isinstance(resources, dict) or resources.keys() - {"limits", "requests"}:
        raise LegacyConversionFailed()
    if any(not isinstance(group, dict) for group in resources.values()):
        raise LegacyConversionFailed()
    return contract


def freeze_runtime(config=None, source=None):
    """首次编辑从原插件部署模板提取实际规格，新建使用平台登记的规格。"""
    if config is None:
        definition = settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG.get("collector_json", {})
    else:
        source = source or config.deployment_config
        if "runtime" in source.params:
            runtime = deepcopy(source.params["runtime"])
            runtime_contract(runtime)
            return runtime
        definition = source.plugin_version.config.collector_json

    contract = resolve_contract(definition)
    image = template_image(definition["template"])
    if config is None:
        resources = contract.get("resources")
    else:
        try:
            _, rendered = K8sInstaller(config).render_snapshot(source)
            deployments = [
                doc
                for doc in yaml.load_all(rendered, Loader=ConfigLoader)
                if isinstance(doc, dict) and doc.get("kind") == "Deployment"
            ]
            if len(deployments) != 1:
                raise LegacyConversionFailed()
            containers = deployments[0]["spec"]["template"]["spec"]["containers"]
            if len(containers) != 1 or containers[0]["image"] != image:
                raise LegacyConversionFailed()
            resources = containers[0].get("resources", {})
        except (yaml.YAMLError, TemplateError, ValueError, LookupError, TypeError, AttributeError, RecursionError):
            raise LegacyConversionFailed() from None

    if "@" not in image:
        digest = contract.get("digest", "")
        if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise LegacyConversionFailed()
        # 只替换最后路径分段的 tag，保留 registry 端口。
        repository = image.rsplit("/", 1)[-1].split(":", 1)[0]
        prefix = image.rpartition("/")[0]
        image = f"{prefix + '/' if prefix else ''}{repository}@{digest}"
    runtime = {"image": image, "contract": f"qcloud-exporter-{contract['version']}", "resources": deepcopy(resources)}
    if runtime_contract(runtime)["products"] != contract["products"]:
        raise LegacyConversionFailed()
    return runtime


def validated_files(params):
    contract = runtime_contract(params["runtime"])
    plugin = params["plugin"]
    if plugin.get("config_mode") != "configmap" or any(
        not isinstance(plugin.get(k), str) or not plugin[k] for k in ENV_KEYS
    ):
        raise CollectConfigParamsError(msg="ConfigMap 部署需要已配置的腾讯云凭据")
    result = validate_files(plugin["configmaps"], params["collector"], contract)
    if not result["valid"]:
        errors = result["errors"] or next(row["errors"] for row in result["files"] if row["errors"])
        raise CollectConfigParamsError(
            msg=f"{errors[0]['code']} ({errors[0]['path']})",
            data={**result, "files": [{k: row[k] for k in ("uid", "valid", "errors")} for row in result["files"]]},
        )
    for file, row in zip(plugin["configmaps"], result["files"]):
        if file_contains_credential(file, row["preview"], (plugin["access_key"], plugin["secret_key"])):
            raise CollectConfigParamsError(msg="配置文件包含页面凭据")
    return result["files"]


def resource_name(name):
    """保留旧命名的可读前缀；仅在超长或不符合 Service 名称约束时缩短。"""
    if len(name) <= 63 and re.fullmatch(r"[a-z][a-z0-9-]*[a-z0-9]", name):
        return name
    prefix = re.sub(r"[^a-z0-9-]", "-", name.lower())[:46].rstrip("-")
    return f"{prefix}-{sha256(name.encode()).hexdigest()[:16]}"


def release_name(config):
    env = settings.BCS_CLUSTER_BK_ENV_LABEL or ""
    release = collector_release_name(config.id, env)
    if config.bk_tenant_id != DEFAULT_TENANT_ID:
        # 同一个公共 namespace 下仍需区分不同租户的同号配置。
        release += "-t" + sha256(config.bk_tenant_id.encode()).hexdigest()[:16]
    return release


def ownership_labels(config):
    return {
        LABEL + "name": APP,
        LABEL + "managed-by": "bk-monitor",
        LABEL + "instance": resource_name(release_name(config)),
        LABEL + "plugin-id": config.plugin_id,
        LABEL + "bk-env": settings.BCS_CLUSTER_BK_ENV_LABEL or "",
        LABEL + "collect-config-id": str(config.id),
    }


def file_resources(config, files, labels):
    release = release_name(config)
    for file in files:
        uid = UUID(file["uid"])
        yield file, resource_name(f"{release}-qcloud-exporter-{uid.hex}"), {**labels, LABEL + "file-uid": str(uid)}


def render_resources(config, params, cluster_id, namespace):
    numeric_data_id = config.data_id
    if not config.id or not numeric_data_id:
        raise CollectConfigParamsError(msg="部署前需要有效的采集配置 ID 和 DataID")
    files = validated_files(params)
    env = settings.BCS_CLUSTER_BK_ENV_LABEL or ""
    release = release_name(config)
    name = resource_name(f"{release}-qcloud-exporter")
    labels = ownership_labels(config)

    def resource(api, kind, resource_name, owner, **fields):
        return {
            "apiVersion": api,
            "kind": kind,
            "metadata": {"name": resource_name, "namespace": namespace, "labels": owner},
            **fields,
        }

    credentials = {k: base64.b64encode(params["plugin"][k].encode()).decode("ascii") for k in ENV_KEYS}
    secret = resource("v1", "Secret", name, labels, type="Opaque", data=credentials)
    # 避免把可离线猜测的凭据摘要暴露到 Pod 注解。
    secret_revision = salted_hmac(
        "qcloud-exporter.secret", json.dumps(credentials, sort_keys=True), algorithm="sha256"
    ).hexdigest()
    dependencies = [secret]
    workloads = []
    for file, file_name, selector in file_resources(config, files, labels):
        content = file["preview"]["qcloud_yaml"]
        dependencies.append(resource("v1", "ConfigMap", file_name, selector, data={"qcloud.yml": content}))
        port = {"name": "http", "port": 9123, "targetPort": "http"}
        dependencies.append(
            resource("v1", "Service", file_name, selector, spec={"selector": selector.copy(), "ports": [port]})
        )
        container = {
            "name": "exporter",
            "image": params["runtime"]["image"],
            "command": ["qcloud_exporter", "--config.file=/etc/qcloud/qcloud.yml"],
            "ports": [{"name": "http", "containerPort": 9123}],
            "resources": deepcopy(params["runtime"]["resources"]),
            "env": [
                {"name": var, "valueFrom": {"secretKeyRef": {"name": name, "key": key}}}
                for key, var in ENV_KEYS.items()
            ],
            "volumeMounts": [{"name": "config", "mountPath": "/etc/qcloud", "readOnly": True}],
        }
        pod = {
            "metadata": {
                "labels": selector,
                "annotations": {
                    "monitor.bk.tencent.com/config-sha256": sha256(content.encode()).hexdigest(),
                    "monitor.bk.tencent.com/secret-revision": secret_revision,
                },
            },
            "spec": {
                "automountServiceAccountToken": False,
                "containers": [container],
                "volumes": [{"name": "config", "configMap": {"name": file_name}}],
            },
        }
        workloads.append(
            resource(
                "apps/v1",
                "Deployment",
                file_name,
                selector,
                spec={
                    "replicas": 1,
                    "strategy": {"type": "Recreate"},
                    "selector": {"matchLabels": selector},
                    "template": pod,
                },
            )
        )

    # 沿用平台现有 DataID 路由、抓取参数和归属 relabel，只收窄对象身份及选择器。
    context = {
        "plugin_release_name": name,
        "bk_env": env,
        "namespace": namespace,
        "cluster_id": cluster_id,
        "bk_biz_id": config.bk_biz_id,
        "collect": params["collector"],
        "plugin": {"id": config.plugin_id, "data_id": numeric_data_id},
    }
    data_id = yaml.safe_load(jinja_render(DATA_ID_TEMPLATE, context))
    monitor = yaml.safe_load(jinja_render(SERVICE_MONITOR_TEMPLATE, context))
    for obj in (data_id, monitor):
        obj["metadata"]["namespace"] = namespace
        obj["metadata"]["labels"].update(labels)
    monitor["spec"]["selector"]["matchLabels"] = labels
    monitor["spec"]["namespaceSelector"]["any"] = False
    return [*dependencies, data_id, *workloads, monitor]


def matches_desired(current, desired):
    """允许 API server 补上的字段；顺序有语义的容器、环境变量等列表逐项比对。"""
    if isinstance(desired, dict):
        return isinstance(current, dict) and all(
            key in current and matches_desired(current[key], value) for key, value in desired.items()
        )
    if isinstance(desired, list):
        return (
            isinstance(current, list)
            and len(current) == len(desired)
            and all(matches_desired(a, b) for a, b in zip(current, desired))
        )
    return current == desired


def apply_resource(client, manifest):
    """按归属和 resourceVersion 原地更新，冲突或部分失败交由上层重试。"""
    metadata = manifest["metadata"]
    kind = manifest["kind"]
    name = metadata["name"]
    namespace = metadata["namespace"]
    try:
        api = client.resources.get(api_version=manifest["apiVersion"], kind=kind)
        try:
            current = api.get(name=name, namespace=namespace).to_dict()
        except k8s_client.exceptions.ApiException as error:
            if error.status != 404:
                raise
            api.create(body=manifest, namespace=namespace)
            return
        owner = current["metadata"].get("labels", {})
        if any(owner.get(k) != v for k, v in metadata["labels"].items() if k.startswith(LABEL)):
            raise CollectConfigParamsError(msg=f"{kind}/{name} 资源归属不匹配")
        patch = deepcopy(manifest)
        # JSON merge patch 默认保留额外的键。配置内容和抓取选择器必须精确匹配。
        if kind in {"Secret", "ConfigMap"}:
            extra = (current.get("data") or {}).keys() - patch["data"].keys()
            patch["data"].update(dict.fromkeys(extra))
        elif kind in {"Service", "ServiceMonitor"}:
            selector = patch["spec"]["selector"]
            existing = current["spec"].get("selector") or {}
            if kind == "ServiceMonitor":
                extra = (existing.get("matchLabels") or {}).keys() - selector["matchLabels"].keys()
                selector["matchLabels"].update(dict.fromkeys(extra))
            selector.update(dict.fromkeys(existing.keys() - selector.keys()))
        if matches_desired(current, patch):
            return
        patch["metadata"]["resourceVersion"] = current["metadata"]["resourceVersion"]
        api.patch(name=name, namespace=namespace, body=patch, content_type="application/merge-patch+json")
    except k8s_client.exceptions.ApiException as error:
        # Kubernetes 的错误 body 可能含 Secret 或用户配置，只上报资源身份和状态码。
        raise CollectConfigParamsError(msg=f"{kind}/{name} 资源更新失败（HTTP {error.status}）") from None
