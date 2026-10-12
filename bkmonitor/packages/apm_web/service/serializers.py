"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apm_web.constants import ServiceRelationLogTypeChoices
from apm_web.models import (
    Application,
    AppServiceRelation,
    CMDBServiceRelation,
    EventServiceRelation,
    LogServiceRelation,
    CodeRedefinedConfigRelation,
)
from apm_web.handlers.service_handler import ServiceHandler
from bkmonitor.models import UserGroup
from bkmonitor.utils.common_utils import count_md5
from core.drf_resource import api
from monitor_web.data_explorer.event.constants import EventDomain, EventSource
from constants.apm import CallSide


class CMDBServiceRelationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CMDBServiceRelation
        fields = ["template_id", "updated_at", "updated_by"]


class EventServiceRelationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventServiceRelation
        fields = ["table", "relations", "options", "updated_at", "updated_by"]


class LogServiceRelationSerializer(serializers.ModelSerializer):
    value = serializers.CharField(required=False, allow_null=True)

    class Meta:
        model = LogServiceRelation
        fields = ["log_type", "related_bk_biz_id", "value", "value_list", "updated_at", "updated_by"]

    def validate(self, attrs):
        if attrs["log_type"] == ServiceRelationLogTypeChoices.BK_LOG:
            if "related_bk_biz_id" not in attrs or not attrs["related_bk_biz_id"]:
                raise serializers.ValidationError(_("关联日志平台日志需要选择业务"))
        else:
            attrs["related_bk_biz_id"] = None

        return attrs


class AppServiceRelationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppServiceRelation
        fields = ["relate_bk_biz_id", "relate_app_name", "updated_at", "updated_by"]


class ApplicationListSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="app_name")
    name = serializers.CharField(source="app_name")

    class Meta:
        model = Application
        fields = ["id", "name", "application_id"]


class ServiceApdexConfigSerializer(serializers.Serializer):
    apdex_value = serializers.CharField()


class IncrementalK8sRelationSerializer(serializers.Serializer):
    bcs_cluster_id = serializers.CharField(label=_("BCS 集群 ID"), max_length=64)
    namespace = serializers.CharField(label=_("命名空间"), max_length=63)
    kind = serializers.CharField(label=_("Workload 类型"), max_length=64)
    name = serializers.CharField(label=_("Workload 名称"), max_length=253)


class IncrementalCICDRelationSerializer(serializers.Serializer):
    project_id = serializers.CharField(label=_("项目 ID"), max_length=128)
    pipeline_id = serializers.CharField(label=_("流水线 ID"), max_length=128)
    pipeline_name = serializers.CharField(label=_("流水线名称"), max_length=255)


def build_service_notice_group_name(app_name: str, service_name: str) -> str:
    return f"【APM】 {app_name}/{service_name} 服务告警组"


class ServiceConfigSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
    app_name = serializers.CharField(label=_("应用名"), max_length=50)
    service_name = serializers.CharField(label=_("服务名"), max_length=512)

    app_relation = AppServiceRelationSerializer(allow_null=True, default=None)
    cmdb_relation = CMDBServiceRelationSerializer(allow_null=True, default=None)
    log_relation_list = serializers.ListSerializer(default=[], child=LogServiceRelationSerializer())
    apdex_relation = ServiceApdexConfigSerializer(allow_null=True, default=None)
    uri_relation = serializers.ListSerializer(default=[], child=serializers.CharField())
    event_relation = serializers.ListSerializer(default=[], child=EventServiceRelationSerializer())
    incremental_cicd_relations = serializers.ListSerializer(required=False, child=IncrementalCICDRelationSerializer())
    incremental_k8s_relations = serializers.ListSerializer(required=False, child=IncrementalK8sRelationSerializer())
    labels = serializers.ListSerializer(required=False, allow_null=True, child=serializers.CharField())
    # 仅显式提交 owners 时维护服务告警组；空列表表示清空通知人。
    owners = serializers.ListField(
        label=_("服务负责人列表"),
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        request_fields: set[str] = set(self.initial_data)
        incremental_fields: set[str] = request_fields & {
            "incremental_cicd_relations",
            "incremental_k8s_relations",
        }
        full_relation_fields: set[str] = request_fields & {
            "app_relation",
            "cmdb_relation",
            "log_relation_list",
            "apdex_relation",
            "uri_relation",
            "event_relation",
        }
        # owners 独立维护告警组通知人，可以与增量关系一起提交，不参与关系配置模式互斥判断。
        if incremental_fields and (full_relation_fields or "labels" in request_fields):
            raise serializers.ValidationError(_("增量事件关联字段不能与其他服务配置字段同时提交"))

        if "owners" in request_fields:
            # 生成的名称最终写入 UserGroup.name，先按模型字段限制拒绝超长名称。
            group_name: str = build_service_notice_group_name(attrs["app_name"], attrs["service_name"])
            group_name_max_length = UserGroup._meta.get_field("name").max_length  # pyright: ignore[reportAttributeAccessIssue]
            if group_name_max_length is not None and len(group_name) > group_name_max_length:
                raise serializers.ValidationError(
                    {
                        "owners": _("指定 owners 后生成的服务告警组名称不能超过 %(max_length)s 个字符")
                        % {"max_length": group_name_max_length}
                    }
                )

        uri_relations: list[str] = attrs["uri_relation"]
        if len(set(uri_relations)) != len(uri_relations):
            raise serializers.ValidationError(_("uri 含有重复配置项"))

        if attrs.get("apdex_relation"):
            attrs["apdex_relation"]["apdex_key"] = ServiceHandler.get_service_apdex_key(
                attrs["bk_biz_id"], attrs["app_name"], attrs["service_name"]
            )

        if incremental_fields or not full_relation_fields:
            # 增量、空请求和仅标签请求只处理显式字段，避免完整保存协议的默认值清空其他配置。
            for field in set(attrs) - request_fields:
                attrs.pop(field)

        return super().validate(attrs)


class LogServiceRelationOutputSerializer(serializers.ModelSerializer):
    log_type_alias = serializers.CharField(source="get_log_type_display")
    related_bk_biz_name = serializers.SerializerMethodField()
    value_alias = serializers.SerializerMethodField()
    value_list = serializers.SerializerMethodField()

    def get_value_alias(self, instance):
        if instance.log_type == ServiceRelationLogTypeChoices.BK_LOG:
            # 关联了日志平台 -> 获取索引集名称
            index_set = api.log_search.search_index_set(bk_biz_id=instance.related_bk_biz_id)
            for index in index_set:
                if str(index["index_set_id"]) == instance.value:
                    return index["index_set_name"]

        return None

    def get_related_bk_biz_name(self, instance):
        bk_biz_id = instance.related_bk_biz_id
        if bk_biz_id:
            response = api.cmdb.get_business(bk_biz_ids=[bk_biz_id])
            if response:
                return response[0].display_name

        return None

    def get_value_list(self, instance):
        if instance.log_type != ServiceRelationLogTypeChoices.BK_LOG:
            return None

        # 关联了日志平台 -> 获取索引集名称
        index_set = api.log_search.search_index_set(bk_biz_id=instance.related_bk_biz_id)
        value_list = []
        for index in index_set:
            if index["index_set_id"] in instance.value_list:
                value_list.append({"value": index["index_set_id"], "value_alias": index["index_set_name"]})
        return value_list

    class Meta:
        model = LogServiceRelation
        fields = [
            "log_type",
            "related_bk_biz_id",
            "related_bk_biz_name",
            "value",
            "value_list",
            "value_alias",
            "log_type_alias",
            "updated_at",
            "updated_by",
            "is_global",
        ]


class BaseServiceRequestSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务 ID")
    app_name = serializers.CharField(label="服务名")


class BasePipelineRequestSerializer(BaseServiceRequestSerializer):
    keyword = serializers.CharField(label="关键字", required=False, allow_blank=True)
    page = serializers.IntegerField(label="页码", required=False, default=1)
    page_size = serializers.IntegerField(label="每页条数", required=False, default=5)
    is_mock = serializers.BooleanField(label="是否使用mock数据", required=False, default=False)


class PipelineOverviewRequestSerializer(BasePipelineRequestSerializer):
    domain = serializers.CharField(label="事件领域", required=False, default=EventDomain.CICD.value)
    source = serializers.CharField(label="事件来源", required=False, default=EventSource.BKCI.value)


class ListPipelineRequestSerializer(BasePipelineRequestSerializer):
    project_id = serializers.CharField(label="项目ID")


class BaseCodeRedefinedRequestSerializer(serializers.Serializer):
    """代码重定义规则基础请求序列化器"""

    bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
    app_name = serializers.CharField(label=_("应用名"))
    service_name = serializers.CharField(label=_("本服务"), required=False)
    kind = serializers.ChoiceField(label=_("角色"), choices=CallSide.choices(), required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        # 服务级配置：必须指定 kind
        if attrs.get("service_name") and not attrs.get("kind"):
            raise serializers.ValidationError(_("请填写类型"))
        return super().validate(attrs)


class ListCodeRedefinedRuleRequestSerializer(BaseCodeRedefinedRequestSerializer):
    """代码重定义规则列表查询请求序列化器"""

    callee_server = serializers.CharField(label=_("被调服务"), required=False, allow_blank=True)
    callee_service = serializers.CharField(label=_("被调 Service"), required=False, allow_blank=True)
    callee_method = serializers.CharField(label=_("被调接口"), required=False, allow_blank=True)


class CodeRedefinedRuleItemSerializer(serializers.Serializer):
    """单个代码重定义规则项序列化器"""

    kind = serializers.ChoiceField(label=_("角色"), choices=CallSide.choices(), required=False)
    service_names = serializers.ListField(
        label=_("服务名列表"), child=serializers.CharField(), allow_null=True, required=False
    )
    is_global = serializers.BooleanField(label=_("是否全局"), default=False)
    callee_server = serializers.CharField(label=_("被调服务"), allow_blank=True)
    callee_service = serializers.CharField(label=_("被调 Service"), allow_blank=True)
    callee_method = serializers.CharField(label=_("被调接口"), allow_blank=True)
    code_type_rules = serializers.JSONField(label=_("返回码映射"))
    enabled = serializers.BooleanField(label=_("是否启用"), required=False, default=True)


class SetCodeRedefinedRuleRequestSerializer(BaseCodeRedefinedRequestSerializer):
    """代码重定义规则设置请求序列化器"""

    UNIQUE_FIELDS = ("is_global", "service_name", "kind", "callee_server", "callee_service", "callee_method")

    rules = serializers.ListField(child=CodeRedefinedRuleItemSerializer(), label=_("规则列表"))

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs = super().validate(attrs)
        kind: str | None = attrs.get("kind")
        service_name: str | None = attrs.get("service_name")

        # 服务级配置只保留非全局规则
        if service_name:
            attrs["rules"] = [rule for rule in attrs["rules"] if not rule["is_global"]]

        unique_set: set[str] = set()
        for rule in attrs.get("rules", []):
            rule["kind"] = kind if service_name else rule.get("kind")
            if not rule["kind"]:
                raise serializers.ValidationError(_("请填写类型"))

            # 外层有 service_name 时，强制覆盖 service_names
            rule["service_names"] = [service_name] if service_name else rule.get("service_names", [])
            if rule["is_global"] is False and not rule["service_names"]:
                raise serializers.ValidationError(_("请填写服务名"))

            rule["callee_server"] = "" if rule["kind"] == CallSide.CALLEE.value else rule["callee_server"]

        # 唯一性校验
        for record in CodeRedefinedConfigRelation.build_sync_records(attrs.get("rules", [])):
            unique_key: str = count_md5({field: record.get(field) for field in self.UNIQUE_FIELDS})
            if unique_key in unique_set:
                raise serializers.ValidationError(
                    _(
                        "规则列表中存在重复的规则："
                        "是否全局：{is_global} "
                        "服务名：{service_name} "
                        "类型：{kind} "
                        "被调服务：{callee_server} "
                        "被调 Service：{callee_service} "
                        "被调接口：{callee_method} "
                    ).format(
                        is_global=record["is_global"],
                        service_name=record["service_name"],
                        kind=record["kind"],
                        callee_server=record["callee_server"],
                        callee_service=record["callee_service"],
                        callee_method=record["callee_method"],
                    )
                )
            unique_set.add(unique_key)

        return attrs


def build_code_remark_configs(remark_configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    remark_records: list[dict[str, Any]] = []
    for remark_config in remark_configs:
        service_names = [""] if remark_config.get("is_global") else remark_config.get("service_names", [])
        for service_name in service_names:
            remark_records.append(
                {
                    "service_name": service_name,
                    "kind": remark_config.get("kind"),
                    "code": remark_config.get("code", ""),
                    "remark": remark_config.get("remark", ""),
                }
            )
    return remark_records


class CodeRemarkItemSerializer(serializers.Serializer):
    """单个返回码备注项序列化器，用于应用级别配置"""

    kind = serializers.ChoiceField(label=_("角色"), choices=CallSide.choices())
    code = serializers.CharField(label=_("返回码"), allow_blank=False)
    remark = serializers.CharField(label=_("备注"), allow_blank=True, default="")
    is_global = serializers.BooleanField(label=_("是否全局生效"), default=False)
    service_names = serializers.ListField(label=_("生效服务列表"), child=serializers.CharField(), default=[])

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs.get("is_global") and attrs.get("service_names"):
            raise serializers.ValidationError(_("全局配置时，service_names 应为空列表"))

        if not attrs.get("is_global") and not attrs.get("service_names"):
            raise serializers.ValidationError(_("非全局配置时，service_names 应非空列表"))

        return super().validate(attrs)


class SetCodeRemarkRequestSerializer(BaseCodeRedefinedRequestSerializer):
    """设置返回码备注请求序列化器，同时支持服务级别和应用级别配置"""

    code = serializers.CharField(label=_("返回码"), allow_blank=False, required=False)
    remark = serializers.CharField(label=_("备注"), allow_blank=True, default="")
    is_global = serializers.BooleanField(label=_("是否全局生效"), default=False)
    remarks = serializers.ListField(label=_("备注列表"), child=CodeRemarkItemSerializer(), required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs = super().validate(attrs)
        # 服务配置场景下，kind、code 两者必须同时存在
        if attrs.get("service_name") and not (attrs.get("kind") and attrs.get("code")):
            raise serializers.ValidationError(_("服务配置场景下，kind、code 必须同时存在"))

        # service_name 为空时要求请求体显式传入 remarks 字段
        if not attrs.get("service_name") and "remarks" not in attrs:
            raise serializers.ValidationError(_("应用配置场景下，remarks 字段必须存在"))

        # 应用配置场景下，校验记录唯一性（service_name、kind、code）
        unique_keys: set[tuple[str, str, str]] = set()
        for remark_dict in build_code_remark_configs(attrs.get("remarks", [])):
            unique_key = (remark_dict["service_name"], remark_dict["kind"], remark_dict["code"])
            if unique_key in unique_keys:
                raise serializers.ValidationError(
                    _(
                        "应用配置记录键存在冲突，"
                        "is_global={is_global}, service_name={service_name}, kind={kind}, code={code}"
                    ).format(
                        is_global=remark_dict["service_name"] == "",
                        service_name=remark_dict["service_name"],
                        kind=remark_dict["kind"],
                        code=remark_dict["code"],
                    )
                )
            unique_keys.add(unique_key)

        return attrs
