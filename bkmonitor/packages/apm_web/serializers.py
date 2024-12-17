# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.fields import empty

from apm_web.constants import CustomServiceMatchType, CustomServiceType
from apm_web.models import ApdexServiceRelation, Application, ApplicationCustomService


class ApplicationListSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="app_name")
    name = serializers.CharField(source="app_name")

    class Meta:
        model = Application
        fields = ["id", "name", "application_id"]


class ApdexConfigSerializer(serializers.Serializer):
    apdex_default = serializers.IntegerField(label="默认apdex")
    apdex_http = serializers.IntegerField(label="网页apdex")
    apdex_db = serializers.IntegerField(label="DB apdex")
    apdex_rpc = serializers.IntegerField(label="远程调用apdex")
    apdex_backend = serializers.IntegerField(label="后台服务apdex")
    apdex_messaging = serializers.IntegerField(label="消息队列apdex")


class ServiceApdexConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApdexServiceRelation
        fields = ["apdex_value", "updated_at", "updated_by"]


class CustomServiceSerializer(serializers.ModelSerializer):
    rule = serializers.JSONField()

    class Meta:
        model = ApplicationCustomService
        fields = ["name", "type", "match_type", "rule"]


OPERATOR_CHOICES = (("eq", _("相等")), ("nq", _("不相等")), ("reg", _("正则")))


class HostUriSerializer(serializers.Serializer):
    operator = serializers.ChoiceField(choices=OPERATOR_CHOICES)
    value = serializers.CharField()


class ParamsSerializer(serializers.Serializer):
    name = serializers.CharField()
    operator = serializers.ChoiceField(choices=OPERATOR_CHOICES)
    value = serializers.CharField()


class RuleSerializer(serializers.Serializer):
    host = HostUriSerializer(required=False)
    path = HostUriSerializer(required=False)
    params = serializers.ListSerializer(child=ParamsSerializer(), required=False)

    def validate(self, attrs):
        if not attrs.keys():
            raise ValueError(_("至少需要设置一个匹配规则"))
        return attrs


class AutoMatchRuleSerializer(serializers.Serializer):
    regex = serializers.CharField()

    def validate_regex(self, value):
        if "peer_service" not in value:
            raise ValueError(_("没有设置peer_service"))

        return value


class CustomServiceConfigSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务id")
    app_name = serializers.CharField(label="应用名称")
    name = serializers.CharField(required=False)
    type = serializers.ChoiceField(choices=CustomServiceType.choices())
    match_type = serializers.ChoiceField(choices=CustomServiceMatchType.choices())
    rule = serializers.JSONField()

    def validate(self, attrs):
        if attrs["match_type"] == CustomServiceMatchType.AUTO:
            AutoMatchRuleSerializer(data=attrs["rule"]).is_valid(raise_exception=True)
        else:
            if not attrs["rule"]:
                raise ValueError(_("没有传递匹配规则"))
            RuleSerializer(data=attrs["rule"]).is_valid(raise_exception=True)

        return attrs


class ApplicationCacheSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ["application_id", "bk_biz_id", "app_name", "metric_result_table_id", "is_enabled_profiling"]


class AsyncSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(label="业务id")
    column = serializers.CharField(label="列名")


class ServiceParamsSerializer(serializers.Serializer):
    category = serializers.CharField(label="分类", required=False, default="")
    kind = serializers.CharField(label="类型", required=False, default="")
    predicate_value = serializers.CharField(label="分类具体值", allow_blank=True, required=False, default="")


class ComponentInstanceIdDynamicField(serializers.Field):
    """
    组件实例ID动态字段
    同时支持传递List/Str
    原因:
        因为前端在组件错误页面下bk_instance_id赋值为字符串 但是在接口/错误页面下bk_instance_id赋值为列表
        导致两个类型不一致 所以在实例用到的接口如果又在接口/错误页下用到 就需要此字段来支持
    """

    def to_internal_value(self, data):
        return data

    def to_representation(self, value):
        return value

    def run_validation(self, data=empty):
        res = super(ComponentInstanceIdDynamicField, self).run_validation(data)
        if not isinstance(res, (list, str)):
            raise ValueError(_("组件实例id仅支持list/str"))

        return res
