"""从 BKBase 实时 VmStorage 配置发现并访问租户内的 VM 查询端点。"""

import json
import math
import re
import time
from ipaddress import IPv6Address

import requests

from core.drf_resource import api
from core.drf_resource.exceptions import CustomException
from core.errors.api import BKAPIError
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response, normalize_pagination
from metadata.models.data_link.constants import BKBASE_NAMESPACE_BK_MONITOR

FUNC_QUERY = "admin.vm_query.query_by_config"
FUNC_LIST = "admin.vm_query.storage_config_list"
HOST_FIELDS = ("selectHost", "commonSelectHost", "historySelectHost", "strategySelectHost")
MAX_QUERY_LENGTH = 65536
MAX_RANGE_SECONDS = 31 * 86400
MAX_POINTS_PER_SERIES = 11000
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_SERIES = 1000
MAX_POINTS = 100000
TIMEOUT_SECONDS = 30
ALLOWED_PARAMS = {
    "bk_tenant_id",
    "storage",
    "config",
    "query",
    "mode",
    "time",
    "start",
    "end",
    "step",
    "max_lookback",
    "nocache",
}


def _fail(code, message, **details):
    raise CustomException(message=message, data={"code": code, **details})


def _text(params, key, maximum):
    value = params.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        _fail("INVALID_ARGUMENT", f"{key} 必须是非空字符串，最多 {maximum} 字符")
    return value.strip()


def _number(params, key, *, minimum=0):
    value = params.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) or value < minimum:
        _fail("INVALID_ARGUMENT", f"{key} 必须是大于等于 {minimum} 的有限数值（秒）")
    return value


def _validate_params(params):
    unknown = set(params) - ALLOWED_PARAMS
    if unknown:
        _fail("INVALID_ARGUMENT", f"不支持的参数: {', '.join(sorted(unknown))}")
    tenant = _tenant(params)
    storage = _resource_name(params, "storage")
    config = params.get("config")
    if not isinstance(config, dict) or set(config) != {"host", "port"}:
        _fail("INVALID_ARGUMENT", "请指定 config.host 和 config.port")
    host = _text(config, "host", 253)
    port = config["port"]
    if type(port) is not int or not 1 <= port <= 65535:
        _fail("INVALID_ARGUMENT", "config.port 必须是有效端口")
    query = _text(params, "query", MAX_QUERY_LENGTH)
    mode = params.get("mode")
    api_params = {"query": query, "timeout": f"{TIMEOUT_SECONDS}s"}
    if "max_lookback" in params:
        api_params["max_lookback"] = _number(params, "max_lookback", minimum=0.001)
    if "nocache" in params:
        if not isinstance(params["nocache"], bool):
            _fail("INVALID_ARGUMENT", "nocache 必须是布尔值")
        api_params["nocache"] = "1" if params["nocache"] else "0"
    if mode == "instant":
        if {"start", "end", "step"} & params.keys():
            _fail("INVALID_ARGUMENT", "即时查询不接受 start、end 或 step")
        api_params["time"] = _number(params, "time")
    elif mode == "range":
        if "time" in params:
            _fail("INVALID_ARGUMENT", "范围查询不接受 time")
        start, end = _number(params, "start"), _number(params, "end")
        step = _number(params, "step", minimum=0.001)
        if end < start or end - start > MAX_RANGE_SECONDS:
            _fail("INVALID_ARGUMENT", "时间范围必须按先后顺序，且不超过 31 天")
        if math.floor((end - start) / step) + 1 > MAX_POINTS_PER_SERIES:
            _fail("INVALID_ARGUMENT", "单条序列超过 11000 个采样点，请增大 step")
        api_params.update(start=start, end=end, step=step)
    else:
        _fail("INVALID_ARGUMENT", "mode 必须为 instant 或 range")
    return tenant, storage, host, port, mode, api_params


def _resource_name(params, key):
    value = _text(params, key, 255)
    if not re.fullmatch(r"[\w-][\w.-]*", value):
        _fail("INVALID_ARGUMENT", f"{key} 必须为资源名称")
    return value


def _tenant(params):
    tenant = _resource_name(params, "bk_tenant_id")
    if tenant == "__all__":
        _fail("INVALID_ARGUMENT", "请选择具体租户")
    return tenant


def _query_url(host, port, mode):
    if ":" in host:
        try:
            host = f"[{IPv6Address(host)}]"
        except ValueError:
            _fail("INVALID_CLUSTER_CONFIG", "查询配置中的主机无效")
    elif not re.fullmatch(r"[a-zA-Z0-9.-]+", host):
        _fail("INVALID_CLUSTER_CONFIG", "查询配置中的主机无效")
    endpoint = "query_range" if mode == "range" else "query"
    return f"http://{host}:{port}/select/0/prometheus/api/v1/{endpoint}"


def _fetch(url, api_params):
    started = time.monotonic()
    try:
        with requests.Session() as session:
            # 该内部查询不继承代理或 .netrc，也不转发 kernel_rpc 调用者的凭据。
            session.trust_env = False
            with session.post(
                url,
                data=api_params,
                headers={"Accept": "application/json"},
                timeout=(3, TIMEOUT_SECONDS + 2),
                allow_redirects=False,
                stream=True,
            ) as response:
                status = response.status_code
                if 300 <= status < 400:
                    _fail("UPSTREAM_ERROR", "VM Query 返回重定向，已拒绝跟随", upstream_status=status)
                raw = bytearray()
                for chunk in response.iter_content(chunk_size=65536):
                    raw.extend(chunk)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        _fail("RESULT_TOO_LARGE", "查询响应超过 5 MiB，请缩小查询范围")
                    if time.monotonic() - started > TIMEOUT_SECONDS + 5:
                        _fail("UPSTREAM_TIMEOUT", "VM Query 查询超时")
                try:
                    payload = json.loads(raw)
                except (ValueError, UnicodeError):
                    _fail("UPSTREAM_ERROR", "VM Query 返回非 JSON 响应", upstream_status=status)
    except requests.Timeout:
        _fail("UPSTREAM_TIMEOUT", "VM Query 查询超时")
    except requests.RequestException:
        _fail("UPSTREAM_UNAVAILABLE", "无法连接 VM Query，请检查服务端网络与集群配置")
    if not isinstance(payload, dict):
        _fail("UPSTREAM_ERROR", "VM Query 响应不是对象", upstream_status=status)
    if status != 200 or payload.get("status") != "success":
        # 保留 PromQL 错误信息，避免把 HTML 网关错误页或底层连接详情返回前端。
        message = str(payload.get("error") or "VM Query 查询失败")[:2000]
        _fail("QUERY_FAILED", message, upstream_status=status, error_type=str(payload.get("errorType", ""))[:100])
    return payload, round((time.monotonic() - started) * 1000)


def _validate_result(payload):
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("resultType") not in {"vector", "matrix", "scalar", "string"}:
        _fail("UPSTREAM_ERROR", "VM Query 返回不支持的结果类型")
    result = data.get("result")
    if not isinstance(result, list):
        _fail("UPSTREAM_ERROR", "VM Query 结果结构无效")
    if data["resultType"] in {"scalar", "string"}:
        _validate_sample(result)
    else:
        if len(result) > MAX_SERIES:
            _fail("RESULT_TOO_LARGE", "查询超过 1000 条序列，请增加标签条件或聚合")
        points = 0
        for item in result:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("metric"), dict)
                or any(not isinstance(v, str) for v in item["metric"].values())
            ):
                _fail("UPSTREAM_ERROR", "VM Query 序列结构无效")
            samples = item.get("values") if data["resultType"] == "matrix" else [item.get("value")]
            if not isinstance(samples, list):
                _fail("UPSTREAM_ERROR", "VM Query 采样结构无效")
            points += len(samples)
            for sample in samples:
                _validate_sample(sample)
        if points > MAX_POINTS:
            _fail("RESULT_TOO_LARGE", "查询超过 100000 个采样点，请缩小范围或增大 step")


def _validate_sample(sample):
    if (
        not isinstance(sample, list)
        or len(sample) != 2
        or isinstance(sample[0], bool)
        or not isinstance(sample[0], int | float)
        or not math.isfinite(sample[0])
        or not isinstance(sample[1], str)
    ):
        _fail("UPSTREAM_ERROR", "VM Query 采样结构无效")


def _project(resource):
    if (resource.get("status") or {}).get("phase") == "Terminated":
        return None
    spec = resource["spec"]
    return {
        "name": resource["metadata"]["name"],
        "selectPort": spec["selectPort"],
        **{field: spec.get(field) or None for field in HOST_FIELDS},
    }


@KernelRPCRegistry.register(
    FUNC_LIST,
    summary="分页读取实时 VMStorage 查询配置",
    description="读取指定租户 bkmonitor 命名空间的 BKBase VmStorage，只返回查询端点和角色。",
    params_schema={"bk_tenant_id": "必填，具体租户", "page": "默认 1", "page_size": "默认 20，最大 100"},
    example_params={"bk_tenant_id": "system", "page": 1, "page_size": 20},
)
def storage_config_list(params):
    tenant = _tenant(params)
    page, page_size = normalize_pagination(params)
    resources = api.bkdata.list_data_link(bk_tenant_id=tenant, namespace=BKBASE_NAMESPACE_BK_MONITOR, kind="vmstorages")
    rows = sorted((row for resource in resources if (row := _project(resource))), key=lambda row: row["name"])
    offset = (page - 1) * page_size
    return build_response(
        operation="vm_query.storage_config_list",
        func_name=FUNC_LIST,
        bk_tenant_id=tenant,
        data={"items": rows[offset : offset + page_size], "total": len(rows), "page": page, "page_size": page_size},
    )


@KernelRPCRegistry.register(
    FUNC_QUERY,
    summary="按已发现的 VM 查询配置执行原生 PromQL",
    description="在来源 VMStorage 的当前查询端点上执行即时或范围查询。",
    params_schema={
        "bk_tenant_id": "必填，具体租户",
        "storage": "必填，提供端点的 VMStorage 名称",
        "config": "必填，host 和 port",
        "mode": "instant 或 range",
        "query": "PromQL 或 MetricsQL",
        "time": "即时查询时间，Unix 秒",
        "start": "范围开始，Unix 秒",
        "end": "范围结束，Unix 秒",
        "step": "采样间隔，秒",
        "max_lookback": "可选，回看秒数",
        "nocache": "可选，跳过 VM 缓存",
    },
    example_params={
        "bk_tenant_id": "system",
        "storage": "vm-main",
        "config": {"host": "vm-common", "port": 80},
        "mode": "instant",
        "time": 1790100000,
        "query": "vector(1)",
    },
)
def query_by_config(params):
    tenant, storage, host, port, mode, api_params = _validate_params(params)
    try:
        resource = api.bkdata.get_data_link(
            bk_tenant_id=tenant, namespace=BKBASE_NAMESPACE_BK_MONITOR, kind="vmstorages", name=storage
        )
    except BKAPIError:
        _fail("STORAGE_CONFIG_UNAVAILABLE", "无法读取来源 VMStorage 的实时配置，请刷新配置或稍后重试")
    row = _project(resource) if resource else None
    if not row or row["selectPort"] != port or not any(row[field] == host for field in HOST_FIELDS):
        _fail("TARGET_REMOVED", "该 VMStorage 已不再引用指定端点，请刷新查询配置")
    payload, elapsed_ms = _fetch(_query_url(host, port, mode), api_params)
    _validate_result(payload)
    return build_response(
        operation="vm_query.query",
        func_name=FUNC_QUERY,
        bk_tenant_id=tenant,
        data={
            "config": {"host": host, "port": port},
            "mode": mode,
            "query": api_params["query"],
            "elapsed_ms": elapsed_ms,
            "response": payload,
        },
    )
