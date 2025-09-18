"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apm_web.constants import ServiceRelationLogTypeChoices
from apm_web.models import (
    Application,
    AppServiceRelation,
    CMDBServiceRelation,
    EventServiceRelation,
    LogServiceRelation,
)
from core.drf_resource import api
from monitor_web.data_explorer.event.constants import EventDomain, EventSource


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
                raise ValueError(_("关联日志平台日志需要选择业务"))
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


class ServiceConfigSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField()
    app_name = serializers.CharField()
    service_name = serializers.CharField()

    app_relation = AppServiceRelationSerializer(required=False, allow_null=True)
    cmdb_relation = CMDBServiceRelationSerializer(required=False, allow_null=True)
    log_relation_list = serializers.ListSerializer(required=False, default=[], child=LogServiceRelationSerializer())
    apdex_relation = ServiceApdexConfigSerializer(required=False, allow_null=True)
    uri_relation = serializers.ListSerializer(required=False, allow_null=True, child=serializers.CharField())
    event_relation = serializers.ListSerializer(required=False, default=[], child=EventServiceRelationSerializer())
    labels = serializers.ListSerializer(required=False, allow_null=True, child=serializers.CharField())


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

    bk_biz_id = serializers.IntegerField(label="业务 ID")
    app_name = serializers.CharField(label="应用名")
    service_name = serializers.CharField(label="本服务")
    kind = serializers.ChoiceField(label="角色", choices=[("caller", "caller"), ("callee", "callee")])

    def validate_callee_kind_consistency(self, attrs):
        """验证 callee 角色的一致性规则"""
        kind = attrs.get("kind")
        service_name = attrs.get("service_name")
        callee_server = attrs.get("callee_server")

        if kind == "callee" and callee_server and callee_server != service_name:
            raise serializers.ValidationError(_("callee 场景下 callee_server 必须等于 service_name"))
        return attrs


class ListCodeRedefinedRuleRequestSerializer(BaseCodeRedefinedRequestSerializer):
    """代码重定义规则列表查询请求序列化器"""

    callee_server = serializers.CharField(label="被调服务", required=False, allow_blank=True, default=None)
    callee_service = serializers.CharField(label="被调 Service", required=False, allow_blank=True, default=None)
    callee_method = serializers.CharField(label="被调接口", required=False, allow_blank=True, default=None)
    is_mock = serializers.BooleanField(label="是否使用mock数据", required=False, default=False)

    def validate(self, attrs):
        """验证请求参数"""
        return self.validate_callee_kind_consistency(attrs)


class CodeRedefinedRuleItemSerializer(serializers.Serializer):
    """单个代码重定义规则项序列化器"""

    callee_server = serializers.CharField(label="被调服务", allow_blank=True)
    callee_service = serializers.CharField(label="被调 Service", allow_blank=True)
    callee_method = serializers.CharField(label="被调接口", allow_blank=True)
    code_type_rules = serializers.JSONField(label="返回码映射")
    enabled = serializers.BooleanField(label="是否启用", required=False, default=True)


class SetCodeRedefinedRuleRequestSerializer(BaseCodeRedefinedRequestSerializer):
    """代码重定义规则设置请求序列化器"""

    rules = serializers.ListField(child=CodeRedefinedRuleItemSerializer(), label="规则列表", min_length=1)

    def validate(self, attrs):
        """验证参数；callee 角色下强制覆盖 callee_server=service_name"""
        kind = attrs.get("kind")
        service_name = attrs.get("service_name")

        # 对每个规则项进行验证
        if kind == "callee":
            for rule in attrs.get("rules", []):
                # 复用基础校验逻辑
                rule_attrs = {"kind": kind, "service_name": service_name, "callee_server": rule.get("callee_server")}
                self.validate_callee_kind_consistency(rule_attrs)
                rule["callee_server"] = service_name

        return attrs


class DeleteCodeRedefinedRuleRequestSerializer(BaseCodeRedefinedRequestSerializer):
    """代码重定义规则删除请求序列化器"""

    callee_server = serializers.CharField(label="被调服务", required=False, allow_blank=True)
    callee_service = serializers.CharField(label="被调 Service", required=False, allow_blank=True)
    callee_method = serializers.CharField(label="被调接口", required=False, allow_blank=True)


class SetCodeRemarkRequestSerializer(BaseCodeRedefinedRequestSerializer):
    """设置单个返回码备注 请求序列化器"""

    code = serializers.CharField(label="返回码", allow_blank=False)
    remark = serializers.CharField(label="备注", required=False, allow_blank=True, default="")
