"""BCS 元数据只读排查；首屏不扫描资源表，不调用上游。"""

from time import monotonic

from django.db.models import Count, Min, Max, Q
from django.utils import timezone
from rest_framework import serializers

from bkmonitor import models as bcs_models
from kernel_api.rpc.functions.admin.bcs_management import management_scope
from core.drf_resource import api
from core.errors.api import BKAPIError
from api.bcs_cluster_manager.default import FetchClustersResource
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response
from kernel_api.rpc.functions.admin.consul import _redact_sensitive_value
from metadata import models

KINDS = {
    "Pod": bcs_models.BCSPod,
    "Container": bcs_models.BCSContainer,
    "Node": bcs_models.BCSNode,
    "Workload": bcs_models.BCSWorkload,
    "Service": bcs_models.BCSService,
    "Ingress": bcs_models.BCSIngress,
    "ServiceMonitor": bcs_models.BCSServiceMonitor,
    "PodMonitor": bcs_models.BCSPodMonitor,
}
TARGETS = [
    "Pod",
    "Node",
    "ReplicaSet",
    "Job",
    "Deployment",
    "StatefulSet",
    "DaemonSet",
    "Service",
    "Ingress",
    "ServiceMonitor",
    "PodMonitor",
]


class ClusterLookup(FetchClustersResource):
    """排查调用保留上游失败，避免非零业务码被适配为空列表。"""

    def render_response_data(self, validated_request_data, response_data):
        if not isinstance(response_data, dict) or response_data.get("code") != 0:
            raise BKAPIError(system_name=self.module_name, url=self.action, result=response_data)
        return super().render_response_data(validated_request_data, response_data)


class Params(serializers.Serializer):
    bk_tenant_id = serializers.CharField(max_length=128)
    cluster_id = serializers.CharField(max_length=64)
    resource_kind = serializers.ChoiceField(choices=list(KINDS), default="Pod")
    resource_id = serializers.IntegerField(min_value=1, required=False)
    namespace = serializers.CharField(max_length=128, required=False, allow_blank=True)
    name = serializers.CharField(max_length=128, required=False, allow_blank=True)
    node_name = serializers.CharField(max_length=128, required=False, allow_blank=True)
    workload_name = serializers.CharField(max_length=128, required=False, allow_blank=True)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)
    target = serializers.ChoiceField(choices=["cluster", *TARGETS], default="Pod")
    space_uid = serializers.CharField(max_length=256, required=False)
    table_id = serializers.CharField(max_length=256, required=False, allow_blank=True)


def context(params):
    serializer = Params(data=params)
    serializer.is_valid(raise_exception=True)
    p = serializer.validated_data
    if p["bk_tenant_id"] == "__all__":
        raise CustomException(message="请选择明确租户")
    return p


def cluster_context(p):
    base = bcs_models.BCSCluster.objects.filter(bk_tenant_id=p["bk_tenant_id"], bcs_cluster_id=p["cluster_id"]).first()
    info = models.BCSClusterInfo.objects.filter(bk_tenant_id=p["bk_tenant_id"], cluster_id=p["cluster_id"]).first()
    return base, info


def scoped_resources(p):
    base, _ = cluster_context(p)
    if base is None:
        raise CustomException(message="当前租户尚无 BCSCluster 记录")
    if (
        bcs_models.BCSCluster.objects.filter(bcs_cluster_id=p["cluster_id"])
        .exclude(bk_tenant_id=p["bk_tenant_id"])
        .exists()
    ):
        raise CustomException(message="跨租户重复集群 ID 的资源表无法隔离，暂不支持读取")
    query = KINDS[p["resource_kind"]].objects.filter(bcs_cluster_id=p["cluster_id"], bk_biz_id=base.bk_biz_id)
    fields = {f.name for f in query.model._meta.fields}
    for field in ("namespace", "name", "node_name", "workload_name"):
        if p.get(field):
            if field not in fields:
                raise CustomException(message=f"{p['resource_kind']} 不支持 {field} 筛选")
            query = query.filter(**{field: p[field]})
    return query


def paged(query, p):
    start = (p["page"] - 1) * p["page_size"]
    rows = list(query[start : start + p["page_size"] + 1])
    return {
        "items": rows[: p["page_size"]],
        "has_more": len(rows) > p["page_size"],
        "page": p["page"],
        "page_size": p["page_size"],
    }


def summary(p):
    base, info = cluster_context(p)
    result = {
        "cluster_exists": base is not None,
        "registration_exists": info is not None,
        "cluster": None
        if base is None
        else {
            "id": base.pk,
            "bk_biz_id": base.bk_biz_id,
            "space_uid": base.space_uid,
            "last_synced_at": base.last_synced_at,
        },
        "registration": None if info is None else {"bk_biz_id": info.bk_biz_id, "project_id": info.project_id},
    }
    return result


def scope(p):
    base, info = cluster_context(p)
    biz = info.bk_biz_id if info else (base.bk_biz_id if base else None)
    return management_scope(p["cluster_id"], biz, "BCSClusterInfo" if info else "BCSCluster")


def resource_list(p):
    query = scoped_resources(p)
    fields = {f.name for f in query.model._meta.fields}
    selected = [
        f
        for f in ["id", "name", "namespace", "status", "last_synced_at", "node_name", "workload_name", "pod_name"]
        if f in fields
    ]
    return paged(query.order_by("id").values(*selected), p)


def resource_detail(p):
    if "resource_id" not in p:
        raise CustomException(message="resource_id 必填")
    query = scoped_resources(p).filter(pk=p["resource_id"])
    row = query.values().first()
    if row is None:
        raise CustomException(message="资源不存在")
    # Labels are fetched only for the selected row.
    row["labels"] = list(query.first().labels.values("key", "value")[:100])
    return {"resource": row, "labels_limit": 100}


def resource_stats(p):
    return {
        "resource_kind": p["resource_kind"],
        "observed_at": timezone.now(),
        **scoped_resources(p).aggregate(count=Count("pk"), oldest=Min("last_synced_at"), newest=Max("last_synced_at")),
    }


def upstream_inspect(p):
    base, info = cluster_context(p)
    started = monotonic()
    result = {
        "target": p["target"],
        "observed_at": timezone.now(),
        "page": p["page"],
        "items": [],
        "has_more": False,
        "complete": False,
        "error": None,
        "cache_mode": "bypass",
    }
    # Cluster Manager accepts a business filter; missing local clusters use the tenant inventory explicitly.
    if p["target"] == "cluster" or (base is None and info is None):
        inventory = ClusterLookup()({"bk_tenant_id": p["bk_tenant_id"], "cluster_id": p["cluster_id"]})
        raw = next((c for c in inventory if c["clusterID"] == p["cluster_id"]), None)
        cluster = (
            None
            if raw is None
            else {
                "cluster_id": raw["clusterID"],
                "name": raw.get("clusterName"),
                "bk_biz_id": int(raw["businessID"]),
                "project_id": raw.get("projectID"),
                "status": raw.get("status"),
            }
        )
        if cluster is None:
            raise CustomException(message="BCS 当前租户未返回该集群")
        if p["target"] == "cluster":
            result.update(
                items=[{k: cluster.get(k) for k in ["cluster_id", "name", "bk_biz_id", "project_id", "status"]}],
                complete=True,
                management_scope=management_scope(p["cluster_id"], cluster.get("bk_biz_id"), "BCS"),
                cache_mode="upstream_client",
            )
            result.update(outcome="success", duration_ms=round((monotonic() - started) * 1000))
            return result
    try:
        # Explicit safe field projection avoids env values, annotations and credentials.
        rows = api.bcs_storage.fetch_page(
            {
                "bk_tenant_id": p["bk_tenant_id"],
                "cluster_id": p["cluster_id"],
                "type": p["target"],
                "offset": (p["page"] - 1) * p["page_size"],
                "limit": p["page_size"],
                "field": "data.metadata.name,data.metadata.namespace,data.metadata.uid,data.metadata.resourceVersion,data.metadata.creationTimestamp,data.metadata.ownerReferences,data.status.phase",
            }
        )
        result["items"] = [
            {
                "metadata": {
                    k: r.get("metadata", {}).get(k)
                    for k in ["name", "namespace", "uid", "resourceVersion", "creationTimestamp", "ownerReferences"]
                },
                "phase": r.get("status", {}).get("phase"),
            }
            for r in rows
        ]
        result.update(
            has_more=len(rows) == p["page_size"],
            complete=p["page"] == 1 and len(rows) < p["page_size"],
            outcome="empty" if not rows else "success",
        )
    except Exception as exc:
        result.update(outcome="error", error=str(_redact_sensitive_value(str(exc)))[:4096])
    result["duration_ms"] = round((monotonic() - started) * 1000)
    return result


def space_list(p):
    base, info = cluster_context(p)
    biz = info.bk_biz_id if info else (base.bk_biz_id if base else None)
    project = info.project_id if info else None
    identities = {}
    if biz is not None:
        identities[("bkcc", str(biz))] = "业务归属"
    if base and "__" in base.space_uid:
        identities[tuple(base.space_uid.split("__", 1))] = "BCSCluster.space_uid"
    if project:
        identities[("bcs", project)] = "项目空间"
    condition = Q(pk__in=[])
    for space_type, space_id in identities:
        condition |= Q(space_type_id=space_type, space_id=space_id)
    # 仅通过既有 (space_type_id, space_id) 唯一索引读取少量已知空间。
    query = (
        models.Space.objects.filter(condition, bk_tenant_id=p["bk_tenant_id"])
        .order_by("id")
        .values("space_type_id", "space_id")
    )
    result = paged(query, p)
    for row in result["items"]:
        row["space_uid"] = f"{row['space_type_id']}__{row['space_id']}"
        row["resource_type"] = identities[(row["space_type_id"], row["space_id"])]
        row["resource_id"] = row["space_id"]
    result["scope"] = "仅列出已记录和归属空间；其他共享空间请指定 UID 检查，不做全表反查。"
    result["owner_space"] = f"bkcc__{biz}" if biz is not None else None
    result["recorded_space"] = base.space_uid if base else None
    return result


def space_inspect(p):
    if not p.get("space_uid") or "__" not in p["space_uid"]:
        raise CustomException(message="space_uid 必填，格式 type__id")
    space_type, space_id = p["space_uid"].split("__", 1)
    space = models.Space.objects.filter(
        bk_tenant_id=p["bk_tenant_id"], space_type_id=space_type, space_id=space_id
    ).first()
    if space is None:
        raise CustomException(message="当前租户空间不存在")
    base, _ = cluster_context(p)
    if base is None:
        raise CustomException(message="当前租户 BCSCluster 不存在，无法检查本地查询范围")
    result = {
        "space_uid": p["space_uid"],
        "observed_at": timezone.now(),
        "visibility": "unknown",
        "namespace_scope": "unknown",
        "namespaces": [],
        "reason": "",
        "metric_route": None,
    }
    if space_type == "bkcc":
        visible = str(base.bk_biz_id) == space_id
        result.update(
            visibility="visible" if visible else "not_visible",
            namespace_scope="all" if visible else "none",
            reason="按业务归属查询",
        )
    else:
        try:
            clusters = api.kubernetes.get_cluster_info_from_bcs_space({"space_uid": p["space_uid"]})
            matched = clusters.get(p["cluster_id"])
            namespaces = matched.get("namespace_list", []) if matched else []
            visible = bool(matched) and (not p.get("namespace") or not namespaces or p["namespace"] in namespaces)
            start = (p["page"] - 1) * p["page_size"]
            result.update(
                visibility="visible" if visible else "not_visible",
                namespace_scope=("subset" if namespaces else "all") if matched else "none",
                namespaces=namespaces[start : start + p["page_size"]],
                namespace_count=len(namespaces),
                has_more=start + p["page_size"] < len(namespaces),
                reason="来自现有空间查询 resolver（可能使用业务缓存）",
            )
        except Exception as exc:
            result.update(visibility="unknown", reason=str(_redact_sensitive_value(str(exc)))[:4096])
    if p.get("table_id"):
        from kernel_api.rpc.functions.admin.query_route import query_routes

        result["metric_route"] = query_routes(
            {"bk_tenant_id": p["bk_tenant_id"], "space_uid": p["space_uid"], "table_ids": [p["table_id"]]}
        )["data"]
    return result


HANDLERS = {
    "management_scope": scope,
    "metadata_summary": summary,
    "metadata_resource_list": resource_list,
    "metadata_resource_detail": resource_detail,
    "metadata_resource_stats": resource_stats,
    "metadata_upstream_inspect": upstream_inspect,
    "metadata_space_list": space_list,
    "metadata_space_inspect": space_inspect,
}


def register(name, handler):
    operation = f"bcs_cluster.{name}"

    def call(params):
        p = context(params)
        return build_response(
            operation=operation, func_name=f"admin.{operation}", bk_tenant_id=p["bk_tenant_id"], data=handler(p)
        )

    KernelRPCRegistry.register(
        f"admin.{operation}",
        summary=f"BCS 只读排查：{name}",
        description="显式租户；分页最大100；统计及远端检查按需调用；read。错误沿用 RPC envelope。",
        params_schema={
            "type": "object",
            "required": ["bk_tenant_id", "cluster_id"],
            "additionalProperties": False,
            "properties": {
                name: (
                    {"type": "integer", "minimum": 1, **({"maximum": 100} if name == "page_size" else {})}
                    if isinstance(field, serializers.IntegerField)
                    else {
                        "type": "string",
                        **({"enum": list(field.choices)} if isinstance(field, serializers.ChoiceField) else {}),
                    }
                )
                for name, field in Params().fields.items()
            },
        },
        example_params={"bk_tenant_id": "system", "cluster_id": "BCS-K8S-10001", "page": 1, "page_size": 20},
    )(call)


for _name, _handler in HANDLERS.items():
    register(_name, _handler)
