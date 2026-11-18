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
from copy import copy, deepcopy
from hashlib import sha256
from uuid import UUID

import yaml
from django.conf import settings
from django.utils.crypto import salted_hmac
from jinja2 import TemplateError
from kubernetes import client as k8s_client

from bkmonitor.utils.template import jinja_render
from constants.common import DEFAULT_TENANT_ID
from core.errors.collecting import CollectConfigParamsError
from monitor_web.collecting.deploy.k8s import (
    DATA_ID_TEMPLATE,
    SERVICE_MONITOR_TEMPLATE,
    K8sInstaller,
    collector_release_name,
)
from monitor_web.collecting.tencent_cloud import (
    ConfigLoader,
    file_contains_credential,
    validate_files,
)

LABEL = "app.kubernetes.io/"
APP = "qcloud-exporter-managed"
ENV_KEYS = {"access_key": "TENCENTCLOUD_SECRET_ID", "secret_key": "TENCENTCLOUD_SECRET_KEY"}


def freeze_runtime(config=None):
    """保留源版本的模板覆盖值；镜像及资源定义继续由该插件版本负责。"""
    if config is None:
        return {"values": {}}
    params = config.deployment_config.params
    if "runtime" in params:
        # 兼容已保存的早期 ConfigMap 快照，沿用其镜像、配额，不再依赖镜像登记。
        runtime = params["runtime"]
        return {key: deepcopy(runtime[key]) for key in ("values", "image", "resources") if key in runtime}
    return {
        "values": {
            key: deepcopy(value)
            for key, value in params.get("plugin", {}).items()
            if key not in ("secret_id", "secret_key", "access_key")
        }
    }


def validated_files(params):
    plugin = params["plugin"]
    if plugin.get("config_mode") != "configmap" or any(
        not isinstance(plugin.get(k), str) or not plugin[k] for k in ENV_KEYS
    ):
        raise CollectConfigParamsError(msg="ConfigMap 部署需要已配置的腾讯云凭据")
    result = validate_files(plugin["configmaps"], params["collector"])
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


def render_resources(config, params, cluster_id, namespace, version=None):
    runtime = params["runtime"]
    source = copy(version or config.deployment_config)
    source.params = {"collector": params["collector"], "plugin": deepcopy(runtime.get("values", {}))}
    context = K8sInstaller(config)._get_context(source)
    numeric_data_id = context["plugin"]["data_id"]
    if not config.id or not numeric_data_id:
        raise CollectConfigParamsError(msg="部署前需要有效的采集配置 ID 和 DataID")
    files = validated_files(params)
    env = settings.BCS_CLUSTER_BK_ENV_LABEL or ""
    name = resource_name(f"{release_name(config)}-qcloud-exporter")
    labels = ownership_labels(config)
    credentials = {k: base64.b64encode(params["plugin"][k].encode()).decode("ascii") for k in ENV_KEYS}
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": name, "namespace": namespace, "labels": labels},
        "type": "Opaque",
        "data": credentials,
    }
    secret_revision = salted_hmac(
        "qcloud-exporter.secret", json.dumps(credentials, sort_keys=True), algorithm="sha256"
    ).hexdigest()
    dependencies = [secret]
    workloads = []
    context["values"].update(secret_id="", secret_key="", access_key="")
    template = source.plugin_version.config.collector_json["template"]
    for file, file_name, selector in file_resources(config, files, labels):
        content = file["preview"]["qcloud_yaml"]
        tree = yaml.safe_load(content)
        context["values"].update(
            region=tree["credential"]["region"],
            products=yaml.safe_dump(tree["products"], allow_unicode=True, sort_keys=False),
        )
        try:
            docs = [doc for doc in yaml.load_all(jinja_render(template, context), Loader=ConfigLoader) if doc]
            groups = {}
            for doc in docs:
                groups.setdefault(doc["kind"], []).append(doc)
            if (
                set(groups) - {"ConfigMap", "Service", "Deployment", "ServiceAccount"}
                or any(len(groups.get(kind, [])) != 1 for kind in ("ConfigMap", "Service", "Deployment"))
                or len(groups.get("ServiceAccount", [])) > 1
            ):
                raise ValueError("template structure")
            configmap, service, deployment = (groups[k][0] for k in ("ConfigMap", "Service", "Deployment"))
            if len(configmap["data"]) != 1:
                raise ValueError("config file")
            old_map_name = configmap["metadata"]["name"]
            config_key = next(iter(configmap["data"]))
            configmap["data"] = {config_key: content}
            pod = deployment["spec"]["template"]
            containers = pod["spec"]["containers"]
            if len(containers) != 1:
                raise ValueError("exporter container")
            container = containers[0]
            # 早期快照独立保存的镜像与配额优先；新快照完整沿用插件模板。
            for key in ("image", "resources"):
                if key in runtime:
                    container[key] = deepcopy(runtime[key])
            container["env"] = [
                entry for entry in container.get("env", []) if entry["name"] not in ENV_KEYS.values()
            ] + [
                {"name": var, "valueFrom": {"secretKeyRef": {"name": name, "key": key}}}
                for key, var in ENV_KEYS.items()
            ]
            for volume in pod["spec"].get("volumes", []):
                if volume.get("configMap", {}).get("name") == old_map_name:
                    volume["configMap"]["name"] = file_name
            if groups.get("ServiceAccount"):
                account = groups["ServiceAccount"][0]
                old_account_name = account["metadata"]["name"]
                account["metadata"].update(name=file_name, namespace=namespace)
                account["metadata"].setdefault("labels", {}).update(selector)
                if pod["spec"].get("serviceAccountName") == old_account_name:
                    pod["spec"]["serviceAccountName"] = file_name
                dependencies.append(account)
            for doc in (configmap, service, deployment):
                doc["metadata"].update(name=file_name, namespace=namespace)
                doc["metadata"].setdefault("labels", {}).update(selector)
            service["spec"].setdefault("selector", {}).update(selector)
            deployment["spec"]["selector"].setdefault("matchLabels", {}).update(selector)
            pod.setdefault("metadata", {}).setdefault("labels", {}).update(selector)
            pod["metadata"].setdefault("annotations", {}).update(
                {
                    "monitor.bk.tencent.com/config-sha256": sha256(content.encode()).hexdigest(),
                    "monitor.bk.tencent.com/secret-revision": secret_revision,
                }
            )
            # 文件和凭据更新时让同一采集的旧实例先退出，避免滚动更新期间重复采集。
            deployment["spec"]["strategy"] = {"type": "Recreate"}
        except (yaml.YAMLError, TemplateError, ValueError, LookupError, TypeError, AttributeError, RecursionError):
            raise CollectConfigParamsError(msg="插件模板必须包含单个 exporter Deployment、Service 和配置文件") from None
        dependencies.extend((configmap, service))
        workloads.append(deployment)
    context.update(
        plugin_release_name=name,
        namespace=namespace,
        cluster_id=cluster_id,
        bk_biz_id=config.bk_biz_id,
        bk_env=env,
        collect=params["collector"],
        plugin={"id": config.plugin_id, "data_id": numeric_data_id},
    )
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
