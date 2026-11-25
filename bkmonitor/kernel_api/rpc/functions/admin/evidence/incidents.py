from rest_framework import serializers

from bkmonitor.documents.incident import IncidentDocument, IncidentSnapshotDocument, IncidentOperationDocument
from bkmonitor.documents.issue import IssueDocument, IssueActivityDocument
from bkmonitor.models.source_analysis import IssueSourceAnalysisExecution
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin.space import tenant_business_ids
from .common import BusinessListPage, BusinessPage, business_scope, db_page, query


class SearchWindow(BusinessListPage):
    start_time = serializers.IntegerField(min_value=0, required=False)
    end_time = serializers.IntegerField(min_value=0, required=False)

    def validate(self, attrs):
        if "start_time" in attrs and "end_time" in attrs and attrs["end_time"] < attrs["start_time"]:
            raise serializers.ValidationError("结束时间不能早于开始时间")
        return attrs


class IncidentPage(SearchWindow):
    incident_id = serializers.CharField(required=False)
    status = serializers.CharField(required=False)


class IncidentTarget(BusinessPage):
    incident_id = serializers.CharField()


class IssuePage(SearchWindow):
    issue_id = serializers.CharField(required=False)
    status = serializers.CharField(required=False)


class IssueTarget(BusinessPage):
    issue_id = serializers.CharField()


def doc_page(search, p, fields, order):
    offset = (p["page"] - 1) * p["page_size"]
    response = (
        search.source(fields).sort(*order).params(track_total_hits=True)[offset : offset + p["page_size"]].execute()
    )
    total = response.hits.total
    records = []
    for hit in response.hits:
        raw = hit.to_dict()
        records.append({**{k: raw[k] for k in fields if k in raw}, "id": str(hit.meta.id)})
    return records, total.value if hasattr(total, "value") else int(total)


def scoped_docs(model, p):
    search = model.search(all_indices=True)
    if "bk_biz_id" in p:
        business_scope(p)
        return search.filter("term", bk_biz_id=str(p["bk_biz_id"]))
    return search.filter("terms", bk_biz_id=[str(biz) for biz in tenant_business_ids(p["bk_tenant_id"])])


def in_window(search, field, p):
    bounds = {key: p[param] for key, param in (("gte", "start_time"), ("lte", "end_time")) if param in p}
    return search.filter("range", **{field: bounds}) if bounds else search


def incident_children(model, p):
    parent = scoped_docs(IncidentDocument, p).filter("term", incident_id=p["incident_id"])
    if not parent.count():
        raise CustomException(message="当前业务下未找到 Incident")
    return model.search(all_indices=True).filter("term", incident_id=p["incident_id"])


@query("incident.list", "故障状态、影响及原因", IncidentPage)
def incidents(p):
    rows = in_window(scoped_docs(IncidentDocument, p), "begin_time", p)
    for k in ("incident_id", "status"):
        if k in p:
            rows = rows.filter("term", **{k: p[k]})
    return doc_page(
        rows,
        p,
        [
            "id",
            "incident_id",
            "bk_biz_id",
            "incident_name",
            "incident_reason",
            "status",
            "level",
            "begin_time",
            "end_time",
            "latest_time",
            "alert_count",
            "handlers",
            "assignees",
            "labels",
        ],
        ["-update_time", "id"],
    )


@query("incident.snapshot_list", "故障快照与根因图记录", IncidentTarget, {"incident_id": "517"})
def snapshots(p):
    rows = incident_children(IncidentSnapshotDocument, p)
    return doc_page(
        rows,
        p,
        [
            "id",
            "incident_id",
            "status",
            "create_time",
            "update_time",
            "bk_biz_ids",
            "alerts",
            "events",
            "fpp_snapshot_id",
        ],
        ["-create_time", "id"],
    )


class Snapshot(IncidentTarget):
    snapshot_id = serializers.CharField()


@query(
    "incident.snapshot_detail", "指定快照的根因图和原始内容", Snapshot, {"incident_id": "517", "snapshot_id": "snap-1"}
)
def snapshot(p):
    rows = incident_children(IncidentSnapshotDocument, p).filter("ids", values=[p["snapshot_id"]])
    return doc_page(rows, p, ["id", "incident_id", "content", "create_time", "fpp_snapshot_id"], ["id"])


@query("incident.operation_list", "故障操作时间线", IncidentTarget, {"incident_id": "517"})
def operations(p):
    return doc_page(
        incident_children(IncidentOperationDocument, p),
        p,
        ["id", "incident_id", "operator", "operation_type", "create_time", "extra_info"],
        ["-create_time", "id"],
    )


@query("issue.list", "问题状态、负责人及影响范围", IssuePage)
def issues(p):
    rows = in_window(scoped_docs(IssueDocument, p), "last_alert_time", p)
    if "issue_id" in p:
        rows = rows.filter("ids", values=[p["issue_id"]])
    if "status" in p:
        rows = rows.filter("term", status=p["status"])
    return doc_page(
        rows,
        p,
        [
            "id",
            "bk_biz_id",
            "name",
            "status",
            "priority",
            "assignee",
            "alert_count",
            "impact_scope",
            "fingerprint",
            "dimension_values",
            "first_alert_time",
            "last_alert_time",
            "is_regression",
        ],
        ["-last_alert_time", "id"],
    )


@query("issue.activity_list", "问题跟进及状态变更记录", IssueTarget, {"issue_id": "issue-1"})
def activities(p):
    rows = scoped_docs(IssueActivityDocument, p).filter("term", issue_id=p["issue_id"])
    return doc_page(
        rows,
        p,
        ["id", "issue_id", "operator", "activity_type", "time", "content", "from_value", "to_value"],
        ["-time", "id"],
    )


@query("issue.analysis_list", "问题已执行的源码分析", IssueTarget, {"issue_id": "issue-1"})
def analysis(p):
    business_scope(p)
    rows = IssueSourceAnalysisExecution.objects.filter(bk_biz_id=p["bk_biz_id"], issue_id=p["issue_id"])
    return db_page(
        rows.order_by("-id").values(
            "id",
            "analysis_id",
            "status",
            "stage",
            "attempt",
            "trigger_type",
            "result_type",
            "failure_stage",
            "failure_code",
            "failure_message",
            "update_time",
            "create_time",
        ),
        p,
    )


class Analysis(IssueTarget):
    analysis_id = serializers.CharField()


@query(
    "issue.analysis_detail",
    "读取已保存的源码分析结果",
    Analysis,
    {"issue_id": "issue-1", "analysis_id": "analysis-1"},
    safety="inspect",
)
def analysis_detail(p):
    business_scope(p)
    rows = IssueSourceAnalysisExecution.objects.filter(
        bk_biz_id=p["bk_biz_id"], issue_id=p["issue_id"], analysis_id=p["analysis_id"]
    )
    return db_page(
        rows.order_by("id").values(
            "analysis_id",
            "issue_id",
            "status",
            "stage",
            "result_type",
            "result_payload",
            "failure_code",
            "failure_message",
            "update_time",
        ),
        p,
    )
