"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""腾讯云 ConfigMap 的纯静态处理。不得在此调用云 API 或修改部署状态。"""

import re
from copy import deepcopy
from hashlib import sha256
from math import isfinite
from uuid import UUID

import yaml
from django.conf import settings


class ConfigError(ValueError):
    """错误只携带固定文案和受控路径，不携带用户输入。"""

    def __init__(self, code, path, message):
        self.detail = {"code": code, "path": path, "message": message}
        super().__init__(message)


class ConfigLoader(yaml.SafeLoader):
    def construct_scalar(self, node):
        value = super().construct_scalar(node)
        # 上传原文可编码不代表 YAML 解码转义后的字符串仍是合法 UTF-8。
        try:
            value.encode("utf-8")
        except UnicodeError:
            raise ConfigError("FILE_ENCODING_INVALID", "", "YAML 文本必须是有效 UTF-8 字符串") from None
        return value

    def construct_mapping(self, node, deep=False):
        if not isinstance(node, yaml.MappingNode):
            raise ConfigError("YAML_INVALID", "", "YAML 格式无效")
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise ConfigError("YAML_INVALID", "", "YAML 对象键必须是字符串")
            if key in result:
                raise ConfigError("YAML_DUPLICATE_KEY", "", "YAML 存在重复键")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def load_yaml(content, path, outer=False):
    try:
        loader = ConfigLoader(content)
        try:
            data = loader.get_data() if loader.check_data() else None
            if loader.check_data():
                raise ConfigError(
                    "CONFIGMAP_COUNT_INVALID" if outer else "QCLOUD_CONFIG_INVALID", path, "必须且只能包含一个文档"
                )
            return data
        finally:
            loader.dispose()
    except ConfigError as exc:
        if not exc.detail["path"]:
            exc.detail["path"] = path
        raise
    except (yaml.YAMLError, ValueError, TypeError, LookupError, AttributeError, OverflowError, RecursionError):
        # SafeLoader 构造显式类型时也会抛出 Python 原生异常，异常文本可能包含上传内容。
        raise ConfigError("YAML_INVALID", path, "YAML 格式无效") from None


def integer(value):
    return type(value) is int and -(2**63) <= value < 2**63


def number(value):
    if type(value) not in (int, float):
        return False
    try:
        return isfinite(value)
    except OverflowError:
        return False


def int32(value):
    return integer(value) and -(2**31) <= value < 2**31


def string_map(value):
    return isinstance(value, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())


def string_list(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


PRODUCT_FIELDS = {
    "namespace": lambda v: isinstance(v, str),
    **dict.fromkeys(("all_metrics", "all_instances", "project_label"), lambda v: type(v) is bool),
    **dict.fromkeys(
        (
            "extra_labels",
            "only_include_metrics",
            "exclude_metrics",
            "only_include_instances",
            "exclude_instances",
            "statistics_types",
            "dimension_level",
        ),
        string_list,
    ),
    **dict.fromkeys(("instance_filters", "tag_key_replace"), string_map),
    "req_params": lambda v: isinstance(v, str),
    "custom_query_dimensions": lambda v: isinstance(v, list),
    "extra_period_seconds": lambda v: isinstance(v, list) and all(integer(item) for item in v),
    **dict.fromkeys(
        (
            "period_seconds",
            "range_seconds",
            "delay_seconds",
            "metric_name_type",
            "reload_interval_minutes",
            "metric_query_batch_size",
            "tag_key_operation",
        ),
        integer,
    ),
}
PRODUCT_FIELDS["metric_name_type"] = int32
CONFIG_FIELDS = {
    "credential": lambda v: isinstance(v, dict),
    "products": lambda v: isinstance(v, list) and bool(v),
    "metrics": lambda v: isinstance(v, list),
    "filename": lambda v: isinstance(v, str),
    "tag_filters": lambda v: isinstance(v, list),
    "rate_limit": number,
    **dict.fromkeys(("metric_query_batch_size", "cache_interval", "collect_timeout", "tag_key_operation"), integer),
    **dict.fromkeys(("is_international", "project_label"), lambda v: type(v) is bool),
    "tag_key_replace": string_map,
}
METRIC_FIELDS = {
    **dict.fromkeys(("tc_namespace", "tc_metric_name", "tc_metric_rename"), lambda v: isinstance(v, str)),
    **dict.fromkeys(("tc_labels", "tc_statistics"), string_list),
    **dict.fromkeys(("tc_myself_dimensions", "tc_filters"), string_map),
    **dict.fromkeys(("tc_metric_name_type", "period_seconds", "range_seconds", "delay_seconds"), integer),
    "extra_period_seconds": PRODUCT_FIELDS["extra_period_seconds"],
}
METRIC_FIELDS["tc_metric_name_type"] = int32
CREDENTIAL_FIELDS = {
    **dict.fromkeys(
        ("region", "access_key", "secret_key", "uin", "role", "cross_account_role", "cross_account_uin", "token"),
        lambda v: isinstance(v, str),
    ),
    "expired_time": integer,
    "is_internal": lambda v: type(v) is bool,
}


def unique_entries(items):
    """仅去重校验工作，保留首次出现的位置，配置和预览仍保留所有条目。"""
    seen = set()
    for index, item in enumerate(items):
        if id(item) not in seen:
            seen.add(id(item))
            yield index, item


def check_fields(value, fields, path, checked):
    if not isinstance(value, dict) or value.keys() - fields.keys():
        raise ConfigError("QCLOUD_CONFIG_INVALID", path, "配置包含未知字段或对象结构无效")
    for key, item in value.items():
        rule = fields[key]
        cache_key = (id(item), rule)
        if cache_key in checked:
            continue
        if not rule(item):
            code = "TIMEOUT_INVALID" if key == "collect_timeout" else "QCLOUD_CONFIG_INVALID"
            raise ConfigError(code, f"{path}.{key}", "字段类型无效")
        if isinstance(item, dict | list):
            checked.add(cache_key)


def check_dimensions(dimensions, path, checked):
    if id(dimensions) in checked:
        return
    for item in dimensions:
        if not isinstance(item, dict) or not item:
            raise ConfigError("QCLOUD_CONFIG_INVALID", path, "查询维度必须是非空字符串映射")
        if id(item) in checked:
            continue
        if not string_map(item):
            raise ConfigError("QCLOUD_CONFIG_INVALID", path, "查询维度必须是非空字符串映射")
        checked.add(id(item))
    checked.add(id(dimensions))


def effective_config(config, collector):
    """保留显式值和缺省状态；预览和未来部署均消费本函数返回的树。"""
    checked = set()
    checked_dimensions = set()
    check_fields(config, CONFIG_FIELDS, "qcloud.yml", checked)
    credential = config.get("credential")
    check_fields(credential, CREDENTIAL_FIELDS, "qcloud.yml.credential", checked)
    for key in ("access_key", "secret_key", "token"):
        if credential.get(key, "") != "":
            raise ConfigError("CREDENTIAL_IN_CONFIGMAP", f"qcloud.yml.credential.{key}", "凭据必须由平台注入")
    if not credential.get("region", "").strip():
        raise ConfigError("QCLOUD_CONFIG_INVALID", "qcloud.yml.credential.region", "必须指定地域")
    if not config.get("products"):
        raise ConfigError("QCLOUD_CONFIG_INVALID", "qcloud.yml.products", "至少配置一个产品")
    for index, product in unique_entries(config["products"]):
        path = f"qcloud.yml.products[{index}]"
        check_fields(product, PRODUCT_FIELDS, path, checked)
        namespace = product.get("namespace")
        if not namespace or namespace == "QCE/ETCD":
            raise ConfigError("PRODUCT_NOT_SUPPORTED", f"{path}.namespace", "必须指定产品，本期不支持 etcd")
        if "custom_query_dimensions" in product:
            check_dimensions(
                product["custom_query_dimensions"],
                f"{path}.custom_query_dimensions",
                checked_dimensions,
            )
    for index, metric in unique_entries(config.get("metrics", [])):
        path = f"qcloud.yml.metrics[{index}]"
        check_fields(metric, METRIC_FIELDS, path, checked)
        if not metric.get("tc_namespace") or metric["tc_namespace"] == "QCE/ETCD":
            raise ConfigError("PRODUCT_NOT_SUPPORTED", f"{path}.tc_namespace", "必须指定产品，本期不支持 etcd")
    for index, tag_filter in unique_entries(config.get("tag_filters", [])):
        check_fields(
            tag_filter,
            {"tag_key": lambda v: isinstance(v, str), "tag_value": string_list},
            f"qcloud.yml.tag_filters[{index}]",
            checked,
        )
    raw_timeout = config.get("collect_timeout", 60)
    timeout, period = collector.get("timeout"), collector.get("period")
    if not all(integer(v) and v > 0 for v in (raw_timeout, timeout, period)):
        raise ConfigError("TIMEOUT_INVALID", "collector", "超时和周期必须为正整数秒")
    budget = raw_timeout - 3 if raw_timeout > 3 else raw_timeout
    if not 0 < budget < timeout <= period:
        raise ConfigError("TIMEOUT_INVALID", "collector", "应满足 exporter 实际预算 < 采集超时 ≤ 采集周期")
    result = deepcopy(config)
    # deepcopy 保留 YAML 别名共享关系；凭据修改必须与其他字段隔离。
    result["credential"] = dict(result["credential"])
    result["credential"]["access_key"] = ""
    result["credential"]["secret_key"] = ""
    return result


def render_config(config):
    ordered = {"credential": config["credential"], **config}
    text = yaml.safe_dump(ordered, allow_unicode=True, sort_keys=False)
    # credential 固定排在首行，行尾可能携带 YAML 锚点。
    header, body = text.split("\n", 1)
    return f"{header}\n  # 凭据由平台通过 Secret 注入，无需在配置文件中填写\n{body}"


def validate_files(files, collector):
    result = {"valid": True, "errors": [], "files": []}
    if not files:
        result["errors"].append({"code": "CONFIGMAP_REQUIRED", "path": "configmaps", "message": "至少上传一个配置文件"})
    seen_uids, seen_content = {}, {}
    for index, file in enumerate(files):
        item = {
            "uid": file["uid"],
            "filename": file["filename"],
            "valid": False,
            "summary": None,
            "preview": None,
            "errors": [],
        }
        result["files"].append(item)
        try:
            try:
                uid = str(UUID(file["uid"]))
            except (ValueError, AttributeError):
                raise ConfigError("QCLOUD_CONFIG_INVALID", "uid", "uid 必须是 UUID") from None
            if uid in seen_uids:
                raise ConfigError("UID_DUPLICATED", "uid", "文件 uid 重复")
            seen_uids[uid] = index
            if not file["filename"].lower().endswith((".yml", ".yaml")):
                raise ConfigError("FILE_TYPE_INVALID", "filename", "仅支持 .yaml 或 .yml 文件")
            try:
                content = file["content"].encode("utf-8")
            except UnicodeError:
                raise ConfigError("FILE_ENCODING_INVALID", "content", "文件必须是有效 UTF-8 文本") from None
            digest = sha256(content).digest()
            if digest in seen_content:
                error = ConfigError("DUPLICATE_FILE", "content", "文件全文重复")
                error.detail["related_uid"] = seen_content[digest]
                raise error
            seen_content[digest] = file["uid"]
            outer = load_yaml(file["content"], "content", outer=True)
            if not isinstance(outer, dict) or outer.get("apiVersion") != "v1" or outer.get("kind") != "ConfigMap":
                raise ConfigError("CONFIGMAP_KIND_INVALID", "content", "必须是 v1 ConfigMap")
            data = outer.get("data")
            if (
                not isinstance(data, dict)
                or set(data) != {"qcloud.yml"}
                or not isinstance(data["qcloud.yml"], str)
                or "binaryData" in outer
            ):
                raise ConfigError("CONFIGMAP_DATA_INVALID", "data", "data 必须只包含 qcloud.yml 文本")
            if len(data["qcloud.yml"].encode("utf-8")) > 1024 * 1024:
                raise ConfigError("CONFIGMAP_DATA_INVALID", "data", "配置超过 ConfigMap 的 1 MiB 限制")
            config = effective_config(load_yaml(data["qcloud.yml"], "qcloud.yml"), collector)
            preview_yaml = render_config(config)
            if len(preview_yaml.encode("utf-8")) + len("qcloud.yml") > 1024 * 1024:
                raise ConfigError("CONFIGMAP_DATA_INVALID", "data", "有效配置超过 ConfigMap 的 1 MiB 限制")
            item.update(
                valid=True,
                summary={
                    "region": config["credential"]["region"],
                    "products": [p["namespace"] for p in config["products"]],
                },
                preview={"qcloud_yaml": preview_yaml, "credential_source": "secret_env"},
            )
        except ConfigError as exc:
            item["errors"].append(exc.detail)
    result["valid"] = not result["errors"] and all(item["valid"] for item in result["files"])
    return result


def configmap_form():
    return [
        {
            "name": "access_key",
            "description": "Secret ID",
            "mode": "env",
            "type": "password",
            "required": True,
            "default": "",
        },
        {
            "name": "secret_key",
            "description": "Secret Key",
            "mode": "env",
            "type": "password",
            "required": True,
            "default": "",
        },
        {
            "name": "configmaps",
            "description": "ConfigMap",
            "mode": "opt_cmd",
            "type": "file",
            "multiple": True,
            "accept": ".yaml,.yml",
            "required": True,
            "default": [],
        },
    ]


def configmap_description():
    url = settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG.get("skill_repository_url", "")
    title = "### 如何获取 ConfigMap"
    credentials = "腾讯云密钥请填写在采集表单中，勿写入 YAML。"
    # 地址同时进入终端命令和 Markdown 链接，只接受无凭据的 HTTPS 仓库路径。
    if not isinstance(url, str) or not re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]+)?/[A-Za-z0-9._~/-]+", url):
        return f"{title}\n\n上传已有的 ConfigMap YAML 文件，校验通过后可预览有效配置。\n\n{credentials}"

    return f"""{title}

通用安装命令会自动识别本机已安装的 Agent，并安装 ConfigMap 生成 Skill。

在终端执行以下命令，将 Skill 全局安装到本机检测到的 Agent。

**安装命令**

```bash
npx skills add {url} -g -s bk-tencentcloud-configmap -a '*' -y
```

安装完成后，重启对应 Agent 或新建会话。提供已有 exporter 的部署名、Kubernetes 命名空间，以及云产品、地域、实例和指标范围，即可生成 ConfigMap。

需 Node.js 22.20+、Git 与 Skill 仓库访问权限。{credentials}

[查看 Skill 仓库]({url})"""


def new_form_definition(detail):
    detail.update(
        config_mode="configmap",
        collector_json={},
        config_json=configmap_form(),
        description_md=configmap_description(),
    )
    return detail


def is_qcloud_plugin(plugin_id, biz_id):
    base = settings.TENCENT_CLOUD_METRIC_PLUGIN_ID
    return plugin_id == base or plugin_id == f"{base}_{biz_id}"


def file_contains_credential(file, preview, credentials):
    return any(
        value and any(value in text for text in (file["filename"], file["content"], preview["qcloud_yaml"]))
        for value in credentials
    )
