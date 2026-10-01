"""Read-only, tenant-scoped evidence for the BKLog data-link control plane."""

from __future__ import annotations

import re

from apps.api import TransferApi
from apps.api.modules.bkdata_datalink import BkDataDataLinkApi
from apps.api.modules.gse import GseApi
from apps.exceptions import PermissionError as BklogPermissionError
from apps.log_admin_resource.handlers.inspection import (
    call_bkdata,
    probe_failure,
    probe_skipped,
    reject_identity_params,
    require_biz_in_request_tenant,
    require_positive_int,
    require_request_tenant_id,
    sanitize_json,
    sanitize_sensitive_text,
)
from apps.log_databus.constants import DEFAULT_BK_USERNAME, DEFAULT_GSE_API_PLAT_NAME


FUNC_NAME = "bklog.datalink.control_plane.snapshot"
MAX_BRANCHES = 5
MAX_GSE_ROUTES = 20
SAFE_RESOURCE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
RESOURCE_PATHS = {
    "ResultTable": "resulttables",
    "Databus": "databuses",
    "DataId": "dataids",
    "KafkaChannel": "kafkachannels",
    "ElasticSearchBinding": "elasticsearchbindings",
    "DorisBinding": "dorisbindings",
    "ElasticSearch": "elasticsearchs",
    "Doris": "dorises",
}

PARAMS_SCHEMA = {
    "type": "object",
    "properties": {"bk_data_id": {"type": "integer", "minimum": 1}},
    "required": ["bk_data_id"],
    "additionalProperties": False,
}

RESPONSE_SCHEMA = {
    "type": "object",
    "required": [
        "bk_data_id",
        "bk_tenant_id",
        "metadata",
        "kafka_cluster",
        "gse_route",
        "gse_stream_to",
        "v4_metadata",
        "v4_branches",
        "warnings",
    ],
    "properties": {
        "bk_data_id": {"type": "integer"},
        "bk_tenant_id": {"type": "string"},
        "metadata": {"type": "object"},
        "kafka_cluster": {"type": "object"},
        "gse_route": {"type": "object"},
        "gse_stream_to": {"type": "array", "items": {"type": "object"}},
        "v4_metadata": {"type": "object"},
        "v4_branches": {"type": "array", "maxItems": MAX_BRANCHES, "items": {"type": "object"}},
        "warnings": {"type": "array", "items": {"type": "object"}},
    },
}


def get_datalink_control_plane_snapshot(params):
    params = params or {}
    reject_identity_params(params)
    data_id = require_positive_int(params, "bk_data_id")
    tenant = require_request_tenant_id()
    result = {
        "bk_data_id": data_id,
        "bk_tenant_id": tenant,
        "warnings": [],
        "v4_branches": [],
        "gse_stream_to": [],
    }

    metadata = _call(TransferApi.get_data_id, {"bk_data_id": data_id, "no_request": True}, tenant, _metadata)
    result["metadata"] = metadata
    if metadata["probe_status"] != "success":
        _skip_downstream(result, "Metadata data ID evidence is unavailable")
        return result

    data = metadata["data"]
    if data["bk_data_id"] != data_id:
        raise ValueError("Metadata returned a different Data ID")
    if data["bk_tenant_id"] != tenant:
        raise BklogPermissionError("Data ID does not belong to the Resource Call tenant")
    if data["bk_biz_id"] != 0:
        require_biz_in_request_tenant(data["bk_biz_id"])

    cluster_id = data["mq_cluster_id"]
    result["kafka_cluster"] = (
        _call(
            TransferApi.get_cluster_info,
            {"cluster_id": cluster_id, "no_request": True},
            tenant,
            lambda rows: _cluster(rows, cluster_id),
        )
        if cluster_id
        else probe_skipped("RESOURCE_NOT_CONFIGURED", "Metadata has no Kafka cluster ID")
    )

    route = _call(
        GseApi.query_route,
        {"condition": {"channel_id": data_id}, "operation": {"operator_name": DEFAULT_BK_USERNAME}, "no_request": True},
        tenant,
        lambda rows: _routes(rows, data_id),
    )
    result["gse_route"] = route
    if route["probe_status"] == "success":
        if route["data"]["truncated"]:
            result["warnings"].append({"code": "GSE_ROUTE_LIMIT", "message": "Additional GSE routes were not returned"})
        if not route["data"]["routes"]:
            result["warnings"].append(
                {"code": "GSE_ROUTE_EMPTY", "message": "No matching route was returned for this Data ID"}
            )
        stream_ids = sorted({item["stream_to_id"] for item in route["data"]["routes"] if item["stream_to_id"]})
        for stream_id in stream_ids[:MAX_BRANCHES]:
            stream = _call(
                GseApi.query_stream_to,
                {
                    "condition": {"stream_to_id": stream_id, "plat_name": DEFAULT_GSE_API_PLAT_NAME},
                    "operation": {"operator_name": DEFAULT_BK_USERNAME},
                    "no_request": True,
                },
                tenant,
                lambda rows, expected=stream_id: _stream_to(rows, expected),
            )
            result["gse_stream_to"].append({"stream_to_id": stream_id, "probe": stream})
            if stream["probe_status"] == "success" and not stream["data"]["items"]:
                result["warnings"].append({"code": "GSE_STREAM_EMPTY", "message": "No matching stream_to was returned"})
        if len(stream_ids) > MAX_BRANCHES:
            result["warnings"].append(
                {"code": "GSE_STREAM_LIMIT", "message": "Additional stream_to IDs were not queried"}
            )

    v4_meta = _call(BkDataDataLinkApi.metadata, {"bk_data_id": data_id, "no_request": True}, tenant, _v4_metadata)
    result["v4_metadata"] = v4_meta
    if v4_meta["probe_status"] == "success":
        branches = v4_meta["data"]["branches"]
        if not branches:
            result["warnings"].append(
                {"code": "V4_BRANCHES_EMPTY", "message": "No V4 branch was returned for this Data ID"}
            )
        for branch in branches[:MAX_BRANCHES]:
            result["v4_branches"].append(_v4_branch(branch, data_id, tenant))
        if v4_meta["data"]["truncated"]:
            result["warnings"].append({"code": "V4_BRANCH_LIMIT", "message": "Additional V4 branches were not queried"})

    _compare_evidence(result)
    result["warnings"].append(
        {"code": "CONTROL_PLANE_ONLY", "message": "Resource phase and configuration do not prove data ingestion"}
    )
    return result


def _skip_downstream(result, reason):
    for key in ("kafka_cluster", "gse_route", "v4_metadata"):
        result[key] = probe_skipped("DEPENDENCY_UNAVAILABLE", reason)


def _call(api, params, tenant, projector, *, not_found_codes=None):
    probe = call_bkdata(api, {**params, "bk_tenant_id": tenant}, not_found_codes=not_found_codes)
    if probe["probe_status"] != "success":
        return probe
    try:
        return {**probe, "data": sanitize_json(projector(probe["data"]), redact_text=True)}
    except (TypeError, ValueError, KeyError, AttributeError) as error:
        return probe_failure(ValueError(f"invalid response: {error}"))


def _metadata(data):
    if not isinstance(data, dict) or not data.get("bk_tenant_id") or not data.get("bk_data_id"):
        raise ValueError("missing Data ID identity or tenant")
    mq = data.get("mq_config") or {}
    if not isinstance(mq, dict):
        raise ValueError("invalid mq_config")
    cluster = mq.get("cluster_config") or {}
    storage = mq.get("storage_config") or {}
    if not isinstance(cluster, dict) or not isinstance(storage, dict):
        raise ValueError("invalid mq_config")
    return {
        "bk_data_id": int(data["bk_data_id"]),
        "bk_tenant_id": str(data["bk_tenant_id"]),
        "bk_biz_id": int(data["bk_biz_id"]),
        "data_name": str(data.get("data_name") or "")[:256],
        "mq_cluster_id": cluster.get("cluster_id"),
        "mq_cluster_name": cluster.get("cluster_name"),
        "mq_host": cluster.get("domain_name"),
        "mq_port": cluster.get("port"),
        "topic": storage.get("topic"),
    }


def _cluster(rows, cluster_id):
    if not isinstance(rows, list):
        raise ValueError("cluster list is invalid")
    item = next((row for row in rows if isinstance(row, dict) and str(row.get("cluster_id")) == str(cluster_id)), None)
    if item is None:
        raise ValueError("requested Kafka cluster is missing from response")
    config = item.get("cluster_config") or {}
    return {
        "cluster_id": item["cluster_id"],
        "cluster_name": item.get("cluster_name"),
        "cluster_type": item.get("cluster_type"),
        "host": config.get("domain_name"),
        "port": config.get("port"),
        "extranet_host": config.get("extranet_domain_name"),
        "extranet_port": config.get("extranet_port"),
        "gse_stream_to_id": item.get("gse_stream_to_id"),
    }


def _routes(rows, data_id):
    if not isinstance(rows, list):
        raise ValueError("route list is invalid")
    routes = []
    truncated = False
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("route item is invalid")
        channel_id = (item.get("metadata") or {}).get("channel_id", item.get("channel_id"))
        if str(channel_id) != str(data_id):
            continue
        for route in item.get("route") or []:
            if len(routes) >= MAX_GSE_ROUTES:
                truncated = True
                break
            stream = route.get("stream_to") or {}
            routes.append(
                {
                    "channel_id": channel_id,
                    "name": route.get("name"),
                    "stream_to_id": stream.get("stream_to_id"),
                    "topic": (stream.get("kafka") or {}).get("topic_name"),
                }
            )
    return {"channel_id": data_id, "routes": routes, "truncated": truncated}


def _stream_to(rows, stream_id):
    if not isinstance(rows, list):
        raise ValueError("stream_to list is invalid")
    items = []
    for item in rows[:MAX_GSE_ROUTES]:
        if not isinstance(item, dict):
            raise ValueError("stream_to item is invalid")
        # GSE installations return either a flat object or a metadata/stream_to wrapper.
        detail = item.get("stream_to") or item
        actual_id = detail.get("stream_to_id", (item.get("metadata") or {}).get("stream_to_id"))
        if str(actual_id) != str(stream_id):
            continue
        kafka = detail.get("kafka") or {}
        items.append(
            {
                "stream_to_id": actual_id,
                "name": detail.get("name"),
                "report_mode": detail.get("report_mode"),
                "kafka_addresses": [
                    {"ip": addr.get("ip"), "port": addr.get("port")}
                    for addr in (kafka.get("storage_address") or [])[:MAX_GSE_ROUTES]
                    if isinstance(addr, dict)
                ],
                "security_protocol": kafka.get("security_protocol"),
                "sasl_mechanisms": kafka.get("sasl_mechanisms"),
                "sasl_configured": bool(kafka.get("sasl_username") and kafka.get("sasl_passwd")),
                "ssl_configured": bool(kafka.get("ssl_ca") or kafka.get("ssl_cert") or kafka.get("ssl_key")),
                "compression": kafka.get("compression"),
                "req_acks": kafka.get("req_acks"),
            }
        )
    return {"items": items, "truncated": len(rows) > MAX_GSE_ROUTES}


def _v4_metadata(data):
    if not isinstance(data, dict) or not isinstance(data.get("branches"), list):
        raise ValueError("V4 metadata branches are missing")
    if any(not isinstance(branch, dict) for branch in data["branches"]):
        raise ValueError("V4 metadata contains an invalid branch")
    return {
        "branches": [
            {
                key: branch.get(key)
                for key in (
                    "result_table_id",
                    "kafka_host",
                    "dispatch_cluster",
                    "dispatch_cluster_count",
                    "dispatch_cluster_task_name",
                    "dispatch_task_count",
                    "kafka_shipper_cluster_name",
                    "kafka_shipper_host",
                    "kafka_shipper_topic_name",
                    "doris_cluster_domain",
                    "doris_table_name",
                )
            }
            for branch in data["branches"][:MAX_BRANCHES]
        ],
        "truncated": len(data["branches"]) > MAX_BRANCHES,
    }


def _resource(kind, name, tenant, namespace="bklog"):
    if kind not in RESOURCE_PATHS or not SAFE_RESOURCE_NAME.fullmatch(str(name or "")):
        return probe_skipped("UNSUPPORTED_REFERENCE", "Resource kind or name is not supported by this snapshot")
    if namespace != "bklog":
        return probe_skipped("UNSUPPORTED_NAMESPACE", "Resource reference is outside the BKLog namespace")
    return _call(
        BkDataDataLinkApi.resource,
        {"tenant": tenant, "namespace": namespace, "kind": RESOURCE_PATHS[kind], "name": name, "no_request": True},
        tenant,
        lambda value: _project_resource(value, kind, name, namespace, tenant),
        not_found_codes={"1558025"},
    )


def _project_resource(value, kind, name, namespace, tenant):
    if not isinstance(value, dict):
        raise ValueError("V4 resource is not an object")
    metadata = value.get("metadata") or {}
    if value.get("kind") != kind or metadata.get("name") != name or metadata.get("namespace") != namespace:
        raise ValueError("V4 resource identity does not match requested reference")
    if metadata.get("tenant") and metadata["tenant"] != tenant:
        raise ValueError("V4 resource tenant does not match requested tenant")
    status = value.get("status") or {}
    spec = value.get("spec") or {}
    result = {
        "kind": kind,
        "metadata": {"namespace": namespace, "name": name},
        "status": {key: status.get(key) for key in ("phase", "start_time", "update_time", "version")},
    }
    if status.get("message"):
        result["status"]["message"] = sanitize_sensitive_text(status["message"], maximum=256)
    if kind == "ResultTable":
        result["spec"] = {"bizId": spec.get("bizId")}
    elif kind == "Databus":
        result["spec"] = {"sources": _refs(spec.get("sources")), "sinks": _refs(spec.get("sinks"))}
    elif kind == "DataId":
        predefined = spec.get("predefined") or {}
        result["spec"] = {
            "predefined": {
                "dataId": predefined.get("dataId"),
                "topic": predefined.get("topic"),
                "channel": _ref(predefined.get("channel")),
            }
        }
    elif kind in {"ElasticSearchBinding", "DorisBinding"}:
        result["spec"] = {"data": _ref(spec.get("data")), "storage": _ref(spec.get("storage"))}
    elif kind == "KafkaChannel":
        result["spec"] = {
            key: spec.get(key) for key in ("host", "port", "role", "streamToId", "v3ChannelId", "version")
        }
    elif kind in {"ElasticSearch", "Doris"}:
        result["spec"] = {"host": spec.get("host"), "port": spec.get("port")}
    return result


def _ref(value):
    if not isinstance(value, dict):
        return None
    return {key: value.get(key) for key in ("kind", "namespace", "name", "tenant") if value.get(key) is not None}


def _refs(value):
    if not isinstance(value, list):
        return []
    return [_ref(item) for item in value[:MAX_BRANCHES] if isinstance(item, dict)]


def _v4_branch(branch, data_id, tenant):
    rt_id = branch.get("result_table_id") or ""
    if not isinstance(rt_id, str) or "_" not in rt_id:
        return {"result_table_id": rt_id, "association_status": "unknown", "reason": "Invalid result table ID"}
    biz_id, rt_name = rt_id.split("_", 1)
    if not biz_id.isdecimal() or not SAFE_RESOURCE_NAME.fullmatch(rt_name):
        return {"result_table_id": rt_id, "association_status": "unknown", "reason": "Invalid result table name"}
    result = {"result_table_id": rt_id, "association_status": "unknown", "resources": {}}
    resources = result["resources"]
    resources["result_table"] = _resource("ResultTable", rt_name, tenant)
    # BKLog composes the Databus with the RT name. This is only a lookup candidate;
    # the source DataId and sink Binding references below decide association.
    resources["databus"] = _resource("Databus", rt_name, tenant)
    bus = _data(resources["databus"])
    if not bus:
        return result
    sources = bus["spec"]["sources"]
    sinks = bus["spec"]["sinks"]
    if len(sources) != 1 or len(sinks) != 1 or not sources[0] or not sinks[0]:
        result["reason"] = "Databus source or sink references are ambiguous"
        return result
    source, sink = sources[0], sinks[0]
    resources["data_id"] = _resource_ref(source, tenant, {"DataId"})
    resources["binding"] = _resource_ref(sink, tenant, {"ElasticSearchBinding", "DorisBinding"})
    data_id_resource, binding = _data(resources["data_id"]), _data(resources["binding"])
    if not data_id_resource or not binding:
        return result
    bound_id = (data_id_resource["spec"].get("predefined") or {}).get("dataId")
    binding_data = binding["spec"].get("data") or {}
    if (
        str(bound_id) != str(data_id)
        or any(
            binding_data.get(key) != expected
            for key, expected in (("kind", "ResultTable"), ("namespace", "bklog"), ("name", rt_name))
        )
        or binding_data.get("tenant", tenant) != tenant
    ):
        result["association_status"] = "mismatch"
        result["reason"] = "Databus DataId or Binding ResultTable reference does not match the requested chain"
        return result
    rt = _data(resources["result_table"])
    if rt and str(rt["spec"].get("bizId")) != biz_id:
        result["association_status"] = "mismatch"
        result["reason"] = "ResultTable bizId does not match BKBase result table ID"
        return result
    if rt:
        result["association_status"] = "verified"
    else:
        result["reason"] = "ResultTable resource was not available for association verification"
    resources["kafka_channel"] = _resource_ref(
        data_id_resource["spec"]["predefined"].get("channel"), tenant, {"KafkaChannel"}
    )
    resources["storage"] = _resource_ref(binding["spec"].get("storage"), tenant, {"ElasticSearch", "Doris"})
    return result


def _resource_ref(ref, tenant, allowed_kinds):
    if not isinstance(ref, dict) or ref.get("kind") not in allowed_kinds:
        return probe_skipped("UNSUPPORTED_REFERENCE", "Data-link reference kind is unsupported")
    if ref.get("tenant", tenant) != tenant:
        return probe_skipped("CROSS_TENANT_REFERENCE", "Data-link reference belongs to another tenant")
    if ref.get("namespace") != "bklog":
        return probe_skipped("UNSUPPORTED_NAMESPACE", "Data-link reference is outside the BKLog namespace")
    return _resource(ref["kind"], ref.get("name"), tenant, "bklog")


def _data(probe):
    return probe.get("data") if probe.get("probe_status") == "success" else None


def _compare_evidence(result):
    cluster = _data(result["kafka_cluster"]) or {}
    routes = (_data(result["gse_route"]) or {}).get("routes") or []
    metadata = _data(result["metadata"]) or {}
    route_ids = {str(route["stream_to_id"]) for route in routes if route.get("stream_to_id") is not None}
    cluster_id = cluster.get("gse_stream_to_id")
    if cluster_id is not None and route_ids and str(cluster_id) not in route_ids:
        result["warnings"].append(
            {"code": "GSE_STREAM_MISMATCH", "message": "Kafka cluster and GSE route stream_to_id differ"}
        )
    if metadata.get("topic") and routes and all(route.get("topic") != metadata["topic"] for route in routes):
        result["warnings"].append({"code": "GSE_TOPIC_MISMATCH", "message": "Metadata and GSE route topics differ"})
    for branch in result["v4_branches"]:
        resources = branch.get("resources", {})
        channel = _data(resources.get("kafka_channel", {})) or {}
        v4_id = (channel.get("spec") or {}).get("streamToId")
        if v4_id is not None and route_ids and str(v4_id) not in route_ids:
            result["warnings"].append(
                {"code": "V4_STREAM_MISMATCH", "message": "V4 KafkaChannel and GSE route stream_to_id differ"}
            )
        if (
            channel
            and cluster
            and (channel["spec"].get("host"), str(channel["spec"].get("port")))
            != (cluster.get("host"), str(cluster.get("port")))
        ):
            result["warnings"].append(
                {
                    "code": "V4_KAFKA_ADDRESS_MISMATCH",
                    "message": "V4 KafkaChannel and Metadata cluster addresses differ",
                }
            )
        for resource_name, probe in resources.items():
            value = _data(probe)
            if value and value["status"].get("phase") != "Ok":
                result["warnings"].append(
                    {
                        "code": "V4_RESOURCE_NOT_OK",
                        "resource": resource_name,
                        "result_table_id": branch["result_table_id"],
                        "phase": value["status"].get("phase"),
                    }
                )
