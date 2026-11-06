"""已授权业务中指定仪表盘的当前已保存配置，只读单 GET。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from django.conf import settings

from bk_dataview.models import Org
from core.drf_resource import api

from ._authorization import authorize_business
from ._catalog import OperationSpec, ParamsGuardRejected, PlatformSourceCatalog, ProviderResponseRejected

UID_PATTERN = r"^[A-Za-z0-9_-]{1,40}$"
MAX_CONFIG_BYTES = 10 * 1024 * 1024
ALLOWED_KEYS = frozenset({"bk_biz_id", "dashboard_uid"})
SAFE_META_FIELDS = ("folderId", "folderUid", "folderTitle", "created", "updated")
REDACTED_VALUE = "[REDACTED]"
SENSITIVE_KEY_PATTERN = re.compile(
    r"password|passwd|passphrase|secret|credential|token|authorization|cookie|bearer"
    r"|api[_-]?key|access[_-]?key|private[_-]?key|app[_-]?key|basicAuthUser|username"
    r"|secureJsonData|httpHeaderValue\d+",
    re.IGNORECASE,
)
CREDENTIAL_TEXT_PATTERN = re.compile(
    r"://[^/\s@]+@"
    r"|\b(?:Bearer|Basic)\s+[A-Za-z0-9+/_=.-]+"
    r"|(?:password|passwd|passphrase|secret|token|credential|cookie|authorization|"
    r"api[_-]?key|access[_-]?key|private[_-]?key)[\"']?\s*[=:]\s*[\"']?[^\s,;\"'}\]\n]+",
    re.IGNORECASE,
)


def guard_get_dashboard(params: Any) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise ParamsGuardRejected("get_dashboard 参数必须是对象")
    if any(key not in ALLOWED_KEYS for key in params):
        raise ParamsGuardRejected("get_dashboard 拒绝未声明参数")
    bk_biz_id = params.get("bk_biz_id")
    if type(bk_biz_id) is not int or bk_biz_id <= 0:
        raise ParamsGuardRejected("bk_biz_id 必须是正整数")
    uid = params.get("dashboard_uid")
    if not isinstance(uid, str) or re.fullmatch(UID_PATTERN, uid) is None:
        raise ParamsGuardRejected("dashboard_uid 必须为 1～40 位字母、数字、下划线或连字符")
    tenant = authorize_business(bk_biz_id, query_name="Grafana")
    try:
        configured_url = getattr(settings, "GRAFANA_URL", None)
        base_url = urlsplit(configured_url) if isinstance(configured_url, str) else None
        if not base_url or base_url.scheme not in {"http", "https"} or not base_url.hostname:
            raise ParamsGuardRejected("Grafana 服务地址未配置", code="provider_unavailable")
        org = Org.objects.filter(name=str(bk_biz_id)).values("id").first()
    except ParamsGuardRejected:
        raise
    except Exception as error:
        raise ParamsGuardRejected("无法读取 Grafana 组织", code="provider_unavailable") from error
    if org is None:
        raise ParamsGuardRejected("目标业务的 Grafana 组织不存在", code="target_not_found")
    if not isinstance(org, dict) or type(org.get("id")) is not int or org["id"] <= 0:
        raise ParamsGuardRejected("Grafana 组织身份无效", code="provider_unavailable")
    # Resource 的 RequestSerializer 仅传 uid / org_id；其余字段供结果投影回显已授权身份。
    return {"uid": uid, "org_id": org["id"], "bk_biz_id": bk_biz_id, "bk_tenant_id": tenant}


def _redact_config(value: Any, path: str, redacted_paths: list[str], *, credential_value: bool = False) -> Any:
    if isinstance(value, dict):
        named_secret = isinstance(value.get("name"), str) and SENSITIVE_KEY_PATTERN.search(value["name"])
        result = {}
        for key, item in value.items():
            item_path = f"{path}/{key.replace('~', '~0').replace('/', '~1')}"
            if (SENSITIVE_KEY_PATTERN.search(key) or (key == "value" and named_secret)) and not isinstance(item, bool):
                result[key] = REDACTED_VALUE
                redacted_paths.append(item_path)
            else:
                result[key] = _redact_config(
                    item,
                    item_path,
                    redacted_paths,
                    credential_value=credential_value or bool(named_secret and key in {"query", "current", "options"}),
                )
        return result
    if isinstance(value, list):
        return [
            _redact_config(item, f"{path}/{index}", redacted_paths, credential_value=credential_value)
            for index, item in enumerate(value)
        ]
    if credential_value and value is not None and not isinstance(value, bool):
        redacted_paths.append(path)
        return REDACTED_VALUE
    if isinstance(value, str) and CREDENTIAL_TEXT_PATTERN.search(value):
        redacted_paths.append(path)
        return REDACTED_VALUE
    return value


def _validate_panels(panels: Any) -> None:
    if not isinstance(panels, list):
        raise ProviderResponseRejected("Grafana 仪表盘 panels 类型无效")
    pending = list(panels)
    while pending:
        panel = pending.pop()
        if not isinstance(panel, dict):
            raise ProviderResponseRejected("Grafana 仪表盘 panel 类型无效")
        if "panels" in panel:
            if not isinstance(panel["panels"], list):
                raise ProviderResponseRejected("Grafana 仪表盘 panels 类型无效")
            pending.extend(panel["panels"])


def _check_config_size(config: Any) -> None:
    try:
        # r.json() 后的配置输出门禁，不是 HTTP 传输或解析内存硬上限。
        size = len(json.dumps(config, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8"))
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ProviderResponseRejected("Grafana 仪表盘配置不是有效 JSON") from error
    if size > MAX_CONFIG_BYTES:
        raise ProviderResponseRejected("Grafana 仪表盘配置超过 10 MiB，整包拒绝", code="unsafe_action_blocked")


def project_get_dashboard(raw: Any, _fields: list[str] | None, params: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict) or type(raw.get("code")) is not int:
        raise ProviderResponseRejected("Grafana 响应 envelope 无效")
    if raw.get("result") is False:
        if raw["code"] == 404:
            raise ProviderResponseRejected("指定 Grafana 仪表盘不存在", code="target_not_found")
        if raw["code"] in {401, 403}:
            raise ProviderResponseRejected("Grafana 拒绝仪表盘读取授权", code="unauthorized")
    if raw.get("result") is not True or raw["code"] != 200:
        raise ProviderResponseRejected("Grafana 仪表盘读取失败")
    data = raw.get("data")
    dashboard = data.get("dashboard") if isinstance(data, dict) else None
    if not isinstance(dashboard, dict) or dashboard.get("uid") != params["uid"]:
        raise ProviderResponseRejected("Grafana 仪表盘身份无效或与请求 UID 不一致")
    if type(dashboard.get("id")) is not int or dashboard["id"] <= 0:
        raise ProviderResponseRejected("Grafana 仪表盘 id 无效")
    if type(dashboard.get("version")) is not int or dashboard["version"] <= 0:
        raise ProviderResponseRejected("Grafana 仪表盘 version 无效")
    _validate_panels(dashboard.get("panels"))
    meta = data.get("meta", {})
    if not isinstance(meta, dict):
        raise ProviderResponseRejected("Grafana 仪表盘 meta 类型无效")
    safe_meta = {}
    for key in SAFE_META_FIELDS:
        if key not in meta:
            continue
        value = meta[key]
        if (key == "folderId" and type(value) is not int) or (key != "folderId" and not isinstance(value, str)):
            raise ProviderResponseRejected("Grafana 仪表盘 meta 字段类型无效")
        safe_meta[key] = value
    _check_config_size(data)
    redacted_paths: list[str] = []
    try:
        config = _redact_config({"dashboard": dashboard, "meta": safe_meta}, "", redacted_paths)
    except (TypeError, AttributeError, RecursionError) as error:
        raise ProviderResponseRejected("Grafana 仪表盘配置不是有效 JSON") from error
    result = {
        "configuration_scope": "current_saved",
        "source": {
            "bk_biz_id": params["bk_biz_id"],
            "bk_tenant_id": params["bk_tenant_id"],
            "org_id": params["org_id"],
            "dashboard_uid": params["uid"],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        },
        **config,
        "redacted": bool(redacted_paths),
        "redacted_paths": redacted_paths,
    }
    # 脱敏路径和来源字段同样占输出预算，不能靠大量短凭据放大返回包。
    _check_config_size(result)
    return result


def register() -> None:
    PlatformSourceCatalog.register_domain(
        id="grafana",
        summary="已授权业务的 Grafana 仪表盘配置只读查询",
        audit_tags=["readonly", "grafana"],
        operations=[
            OperationSpec(
                id="get_dashboard",
                summary="读取指定 UID 仪表盘的当前已保存完整配置",
                handler=api.grafana.get_dashboard_by_uid,
                params_guard=guard_get_dashboard,
                response_postprocess=project_get_dashboard,
                response_postprocess_needs_params=True,
                required_params=["bk_biz_id", "dashboard_uid"],
                params_schema_override={
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["bk_biz_id", "dashboard_uid"],
                    "properties": {
                        "bk_biz_id": {"type": "integer", "minimum": 1},
                        "dashboard_uid": {"type": "string", "minLength": 1, "maxLength": 40, "pattern": UID_PATTERN},
                    },
                },
                example_params={"bk_biz_id": 2, "dashboard_uid": "example-dashboard"},
                audit_tags=["readonly", "grafana", "business-scoped"],
                notes=(
                    "授权后只读解析业务组织，固定一次 GET；不创建组织或用户，不展开数据源凭据。"
                    "configuration_scope=current_saved，仅返回当前已保存配置，保留递归 panels、禁用 targets、"
                    "templating、transformations、时间与展示配置；不发起指标查询。"
                    "凭据键、凭据 URL/文本及敏感名称的 name/value 条目脱敏，返回 redacted 和 JSON Pointer 路径。"
                    "请求链接的时间和变量覆盖需由调用方独立保留；未保存编辑和历史版本不在本接口范围。"
                    "连接/读取超时固定为 3/10 秒；解析后的配置超过 10 MiB 整包拒绝，不截断。"
                ),
            )
        ],
    )


register()
