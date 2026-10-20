"""RecordingRule V4 公共配置接口。"""

from rest_framework import serializers

from bkmonitor.as_code import recording_rule
from bkmonitor.utils.request import get_request_username
from bkmonitor.utils.serializers import BkBizIdSerializer
from core.drf_resource import Resource
from metadata.models.record_rule.v4.as_code import dump_rule
from metadata.models.record_rule.v4.models import RecordRuleV4, RecordRuleV4Spec, RecordRuleV4SpecRecord
from metadata.models.record_rule.v4.operator import RecordRuleV4Operator
from metadata.models.record_rule.v4.resolver import RecordRuleV4Resolver


def serialize_rule(rule: RecordRuleV4) -> dict:
    latest_resolved = rule.get_latest_resolved()
    return {
        "id": rule.pk,
        "name": rule.name,
        "space_uid": rule.space_uid,
        "app": rule.app,
        "path": rule.path,
        "table_id": rule.table_id,
        "dst_vm_table_id": rule.dst_vm_table_id,
        "generation": rule.generation,
        "status": rule.status,
        "desired_status": rule.desired_status,
        "applied_desired_status": rule.applied_desired_status,
        "auto_refresh": rule.auto_refresh,
        "is_deleted": rule.is_deleted,
        "latest_resolved_id": latest_resolved.pk if latest_resolved else None,
        "applied_resolved_id": rule.applied_resolved_id,
        "conditions": rule.conditions,
        "last_check_time": rule.last_check_time,
        "last_refresh_time": rule.last_refresh_time,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


class ConfigSerializer(BkBizIdSerializer):
    config = serializers.JSONField(help_text="AsCode 单 group 对象或 YAML 字符串，不含外层 groups")

    def validate_config(self, value):
        return recording_rule.parse_group_config(value)


class RuleIdSerializer(BkBizIdSerializer):
    id = serializers.IntegerField(min_value=1)


class RecordingRuleResource(Resource):
    @staticmethod
    def get_space(params):
        return recording_rule.get_space(params["bk_biz_id"], params.get("space_uid"))

    @classmethod
    def get_rule(cls, params):
        try:
            return recording_rule.active_rules(cls.get_space(params)).get(pk=params["id"])
        except RecordRuleV4.DoesNotExist as error:
            raise serializers.ValidationError("RecordingRule 不存在") from error


class PreviewConfigResource(RecordingRuleResource):
    """预解析 RecordingRule 配置，返回 MetricQL 与来源信息，不保存或下发。"""

    class RequestSerializer(ConfigSerializer):
        id = serializers.IntegerField(min_value=1, required=False)

    def perform_request(self, params):
        declaration = params["config"]
        if "id" in params:
            rule = self.get_rule(params)
            if declaration["name"] != rule.name:
                raise serializers.ValidationError("规则组名称不可修改")
        else:
            space = self.get_space(params)
            rule = RecordRuleV4(
                bk_tenant_id=space.bk_tenant_id, space_type=space.space_type_id, space_id=space.space_id
            )
        # 只构造内存对象，复用 Resolver 的读取路径，不调用任何声明或快照保存方法。
        spec = RecordRuleV4Spec(rule=rule, interval=declaration["interval"], labels=declaration["labels"])
        resolver = RecordRuleV4Resolver(rule)
        records = []
        for index, record in enumerate(declaration["records"]):
            spec_record = RecordRuleV4SpecRecord(spec=spec, record_key=f"rules[{index}]", **record)
            try:
                resolved = resolver.resolve_record(spec_record)
            except Exception as error:
                raise serializers.ValidationError({f"config.rules[{index}]": str(error)}) from error
            resolved.pop("record_key")
            records.append({"record": record["metric_name"], **resolved})
        return {"config": declaration["raw_config"], "records": records}


class CreateConfigResource(RecordingRuleResource):
    """新建 RecordingRule 声明；apply=true 时立即解析并下发。"""

    class RequestSerializer(ConfigSerializer):
        apply = serializers.BooleanField(default=False)

    def perform_request(self, params):
        rule = recording_rule.save_declaration(self.get_space(params), params["config"])
        execution = recording_rule.execute_rule(rule) if params["apply"] else None
        rule.refresh_from_db()
        return {"saved": True, "rule": serialize_rule(rule), "config": dump_rule(rule), "execution": execution}


class UpdateConfigResource(RecordingRuleResource):
    """完整更新 RecordingRule 声明，保留名称与空间；可选立即下发。"""

    class RequestSerializer(ConfigSerializer):
        id = serializers.IntegerField(min_value=1)
        apply = serializers.BooleanField(default=False)

    def perform_request(self, params):
        space = self.get_space(params)
        try:
            rule = recording_rule.active_rules(space).get(pk=params["id"])
        except RecordRuleV4.DoesNotExist as error:
            raise serializers.ValidationError("RecordingRule 不存在") from error
        rule = recording_rule.save_declaration(space, params["config"], rule=rule)
        execution = recording_rule.execute_rule(rule) if params["apply"] else None
        rule.refresh_from_db()
        return {"saved": True, "rule": serialize_rule(rule), "config": dump_rule(rule), "execution": execution}


class DeleteConfigResource(RecordingRuleResource):
    """软删除 RecordingRule，并执行 Flow 删除；外部删除失败由后台继续重试。"""

    RequestSerializer = RuleIdSerializer

    def perform_request(self, params):
        rule = self.get_rule(params)
        execution = recording_rule.soft_delete_rule(rule)
        rule.refresh_from_db()
        return {"is_deleted": True, "rule": serialize_rule(rule), "execution": execution}


class GetConfigResource(RecordingRuleResource):
    """查询 RecordingRule 当前配置，可选观测已下发 Flow 的实时状态。"""

    class RequestSerializer(RuleIdSerializer):
        with_status = serializers.BooleanField(default=False)

    def perform_request(self, params):
        rule = self.get_rule(params)
        observation = None
        if params["with_status"]:
            if rule.get_applied_flow() is None:
                observation = {"succeeded": False, "flow_status": None, "error": "尚未下发 Flow"}
            else:
                try:
                    status = RecordRuleV4Operator(
                        rule, source="api", operator=get_request_username(default="api")
                    ).refresh_flow_health()
                    event = rule.events.order_by("-id").first()
                    message = (event.message or event.reason) if event else ""
                    observation = {
                        "succeeded": status == "ok",
                        "flow_status": status,
                        "error": "" if status == "ok" else message or status,
                    }
                except Exception as error:
                    observation = {"succeeded": False, "flow_status": None, "error": str(error)}
                rule.refresh_from_db()
        return {"rule": serialize_rule(rule), "config": dump_rule(rule), "observation": observation}


class ApplyConfigResource(RecordingRuleResource):
    """解析当前 RecordingRule 声明并下发 Flow。"""

    RequestSerializer = RuleIdSerializer

    def perform_request(self, params):
        rule = self.get_rule(params)
        execution = recording_rule.execute_rule(rule)
        rule.refresh_from_db()
        return {"rule": serialize_rule(rule), "execution": execution}


class ListConfigsResource(RecordingRuleResource):
    """分页查询 RecordingRule，仅返回本地状态，不访问 BKBase。"""

    class RequestSerializer(BkBizIdSerializer):
        name = serializers.CharField(required=False, allow_blank=True)
        app = serializers.CharField(required=False, allow_blank=True, max_length=128)
        status = serializers.CharField(required=False)
        page = serializers.IntegerField(default=1, min_value=1)
        page_size = serializers.IntegerField(default=20, min_value=1, max_value=100)

    def perform_request(self, params):
        rules = recording_rule.active_rules(self.get_space(params))
        if params.get("name"):
            rules = rules.filter(name__icontains=params["name"])
        for field in ("app", "status"):
            if field in params:
                rules = rules.filter(**{field: params[field]})
        page, page_size = params["page"], params["page_size"]
        total = rules.count()
        rules = rules.order_by("-updated_at", "-id")[(page - 1) * page_size : page * page_size]
        return {
            "items": [serialize_rule(rule) for rule in rules],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
