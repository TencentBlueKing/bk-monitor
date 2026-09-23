"""通过租户内的 VmQueryCluster 镜像执行有界、只读的原生 PromQL 查询。"""

import json
import math
import re
import time
from urllib.parse import urlsplit

import requests

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response
from metadata.models.data_link.vm_query_cluster import VmQueryClusterConfig

FUNC_QUERY = "admin.vm_query.query"
MAX_QUERY_LENGTH = 65536
MAX_RANGE_SECONDS = 31 * 86400
MAX_POINTS_PER_SERIES = 11000
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_SERIES = 1000
MAX_POINTS = 100000
TIMEOUT_SECONDS = 30
ALLOWED_PARAMS = {"bk_tenant_id", "namespace", "name", "query", "mode", "time", "start", "end", "step"}


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
    identity = {
        key: _text(params, key, maximum) for key, maximum in (("bk_tenant_id", 256), ("namespace", 64), ("name", 255))
    }
    if identity["bk_tenant_id"] == "__all__":
        _fail("INVALID_ARGUMENT", "执行查询前必须选择具体租户")
    query = _text(params, "query", MAX_QUERY_LENGTH)
    mode = params.get("mode")
    api_params = {"query": query, "timeout": f"{TIMEOUT_SECONDS}s"}
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
    return identity, mode, api_params


def _query_url(domain, mode):
    """仅接受数据库中的域名/authority，查询 path 和 VM account 固定。"""
    if not isinstance(domain, str) or not domain or re.search(r"[\s\\]", domain):
        _fail("INVALID_CLUSTER_CONFIG", "VM Query 域名配置为空或格式无效")
    has_scheme = "://" in domain
    try:
        parsed = urlsplit(domain if has_scheme else f"http://{domain}")
        port = parsed.port
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or not re.fullmatch(r"[a-zA-Z0-9.:-]+", parsed.hostname)
        ):
            raise ValueError("invalid authority")
    except ValueError:
        _fail("INVALID_CLUSTER_CONFIG", "VM Query 配置只允许 HTTP(S) 域名及端口，不接受路径或凭据")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    # BKBase VmQueryCluster 的裸域名使用 vmselect 的 8481 端口；显式 scheme 遵循 HTTP(S) 默认端口。
    port = port if port is not None else (None if has_scheme else 8481)
    authority = f"{host}:{port}" if port is not None else host
    endpoint = "query_range" if mode == "range" else "query"
    return f"{parsed.scheme}://{authority}/select/0/prometheus/api/v1/{endpoint}"


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


@KernelRPCRegistry.register(
    FUNC_QUERY,
    summary="Admin VM Query 原生 PromQL 查询",
    description="只读查询；按租户、namespace、name 解析 VmQueryCluster 域名，不接受 URL、路径、请求头或凭据。",
    params_schema={
        "bk_tenant_id": "必填，明确租户，不支持全租户",
        "namespace": "必填，VmQueryCluster namespace",
        "name": "必填，VmQueryCluster metadata.name",
        "query": "必填，PromQL/MetricsQL，最多 65536 字符",
        "mode": "必填，instant 或 range",
        "time": "instant 必填，Unix 秒",
        "start": "range 必填，Unix 秒",
        "end": "range 必填，Unix 秒，跨度最多 31 天",
        "step": "range 必填，秒；每序列最多 11000 点",
    },
    example_params={
        "bk_tenant_id": "system",
        "namespace": "bkmonitor",
        "name": "vm-query-primary",
        "query": "up",
        "mode": "range",
        "start": 1790100000,
        "end": 1790103600,
        "step": 60,
    },
)
def query(params):
    identity, mode, api_params = _validate_params(params)
    try:
        cluster = VmQueryClusterConfig.objects.get(**identity)
    except VmQueryClusterConfig.DoesNotExist:
        _fail("CLUSTER_NOT_FOUND", "当前租户和 namespace 下未找到指定 VM Query 集群")
    if cluster.status == "Terminated":
        _fail("CLUSTER_TERMINATED", "该 VM Query 集群已失效，请选择其他集群")
    payload, elapsed_ms = _fetch(_query_url(cluster.cluster_domain, mode), api_params)
    _validate_result(payload)
    return build_response(
        operation="vm_query.query",
        func_name=FUNC_QUERY,
        bk_tenant_id=identity["bk_tenant_id"],
        data={
            "cluster": identity,
            "mode": mode,
            "query": api_params["query"],
            "elapsed_ms": elapsed_ms,
            "response": payload,
        },
    )
