"""Monitor-owned alert analysis APIs; incident results remain explicitly attributed."""

import logging

from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from ai_whale.alert_analysis_access import authorized_alert, authorize_incident, check_alert_history, current_identity
from ai_whale.alert_analysis_session import PANELS, ensure_session
from bkmonitor.documents import IncidentDocument
from core.drf_resource import Resource
from monitor_web.incident.resources import (
    IncidentDiagnosisResource,
    IncidentPanelDetailResource,
    IncidentResultsResource,
)


logger = logging.getLogger("ai_whale")


class AlertAnalysisSerializer(serializers.Serializer):
    # String IDs preserve precision when the frontend constructs session codes.
    alert_id = serializers.RegexField(r"^[1-9][0-9]{0,31}$")
    bk_biz_id = serializers.IntegerField()


def related_incident(params):
    alert = authorized_alert(params["alert_id"], params["bk_biz_id"])
    if not alert.incident_id:
        return None
    incident = IncidentDocument.get(str(alert.incident_id), fetch_remote=False)
    if incident and int(incident.bk_biz_id) != int(alert.bk_biz_id):
        raise PermissionDenied("关联故障不属于当前告警业务")
    if incident is not None:
        authorize_incident(incident)
    return incident


def analysis_context(params):
    incident = related_incident(params)
    context = {
        "subject": {"type": "alert", "alert_id": str(params["alert_id"])},
        "source": None,
        "analysis": {"status": "unavailable", "reason": "no_related_incident", "sub_panels": {}},
    }
    if incident is None:
        return context
    diagnosis = IncidentDiagnosisResource()
    context["source"] = {
        "type": "incident_analysis",
        "monitor_incident_id": str(incident.id),
        "incident_id": int(incident.incident_id),
    }
    raw = diagnosis.get_remote_analysis_results(incident, bk_biz_id=params["bk_biz_id"])
    raw_panels = raw.get("incident_diagnosis", {}).get("sub_panels", {})
    panels = {}
    for name in PANELS:
        if name not in raw_panels:
            continue
        panel = raw_panels[name]
        enabled = panel.get("status") == "running" or (
            panel.get("is_show", True) and IncidentResultsResource._content_valid(panel.get("content"))
        )
        panels[name] = {
            "status": panel.get("status"),
            "enabled": enabled,
            "message": panel.get("message") or "",
            **(diagnosis.format_diagnosis(raw, name, [params["bk_biz_id"]]) if enabled else {}),
        }
    statuses = [panel["status"] for panel in panels.values() if panel["enabled"]]
    status = "unavailable"
    if statuses:
        status = (
            "running" if "running" in statuses else "finished" if all(s == "finished" for s in statuses) else "failed"
        )
    context["analysis"] = {"status": status, "sub_panels": panels}
    if status == "unavailable":
        context["analysis"]["reason"] = "analysis_not_available"
    return context


class AlertAnalysisRelatedIncidentResource(Resource):
    RequestSerializer = AlertAnalysisSerializer

    def perform_request(self, validated_request_data):
        incident = related_incident(validated_request_data)
        return {
            "incident": {
                "id": str(incident.id),
                "incident_id": int(incident.incident_id),
                "bk_biz_id": int(incident.bk_biz_id),
            }
            if incident is not None
            else {}
        }


class AlertAnalysisResultsResource(Resource):
    RequestSerializer = AlertAnalysisSerializer

    def perform_request(self, validated_request_data):
        return analysis_context(validated_request_data)


class AlertAnalysisDiagnosisResource(Resource):
    class RequestSerializer(AlertAnalysisSerializer):
        sub_panel = serializers.ChoiceField(choices=PANELS, default="summary")

    def perform_request(self, validated_request_data):
        context = analysis_context(validated_request_data)
        panel = validated_request_data["sub_panel"]
        context["analysis"]["sub_panels"] = {
            panel: context["analysis"]["sub_panels"].get(panel, {"enabled": False, "status": "unavailable"})
        }
        return context


class AlertAnalysisPanelDetailResource(Resource):
    class RequestSerializer(AlertAnalysisSerializer):
        drawer_type = serializers.ChoiceField(choices=("event", "log", "trace"))
        detail_ref = serializers.DictField()
        incident_task_id = serializers.IntegerField(required=False, min_value=1)
        page = serializers.IntegerField(default=1, min_value=1)
        page_size = serializers.IntegerField(default=30, min_value=1, max_value=1000)
        sort_list = serializers.ListField(
            required=False,
            max_length=10,
            child=serializers.ListField(child=serializers.CharField(), min_length=2, max_length=2),
        )

    def perform_request(self, validated_request_data):
        incident = related_incident(validated_request_data)
        if incident is None or not IncidentDiagnosisResource.is_bkfara_incident(incident):
            raise ValidationError("当前告警没有可读取明细的 BKFara 关联故障")
        params = {key: value for key, value in validated_request_data.items() if key != "alert_id"}
        # Never trust a client-supplied incident ID; BKFara also validates task/ref ownership.
        params["incident_id"] = int(incident.incident_id)
        return IncidentPanelDetailResource().request(params)


class AlertAnalysisSessionContextResource(Resource):
    RequestSerializer = AlertAnalysisSerializer

    def perform_request(self, validated_request_data):
        from redis.exceptions import LockError
        from ai_whale.resources.resources import aidev_interface
        from utils.redis_client import RedisClient

        # Authorize before acquiring locks or contacting the conversation service.
        authorized_alert(validated_request_data["alert_id"], validated_request_data["bk_biz_id"])
        username, tenant_id = current_identity()
        try:
            return ensure_session(
                aidev_interface,
                RedisClient(),
                context_factory=lambda: analysis_context(validated_request_data),
                alert_id=validated_request_data["alert_id"],
                username=username,
                tenant_id=tenant_id,
                agent_code=settings.AIDEV_AGENT_APP_CODE,
                history_validator=check_alert_history,
            )
        except LockError as exc:
            error = APIException("告警会话正在准备，请稍后重试", code="session_preparing")
            error.status_code = 409
            raise error from exc
        except APIException:
            raise
        except Exception as exc:
            # Upstream exceptions may contain response bodies; keep those out of the frontend response.
            logger.warning("Alert session preparation failed (%s)", type(exc).__name__)
            error = APIException("告警分析会话尚未确认持久化，请重试", code="session_not_ready")
            error.status_code = 502
            raise error from exc
