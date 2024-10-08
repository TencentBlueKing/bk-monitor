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
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from apm_web.constants import ServiceRelationLogTypeChoices
from apm_web.models import (
    Application,
    AppServiceRelation,
    CMDBServiceRelation,
    LogServiceRelation,
)
from core.drf_resource import api


class CMDBServiceRelationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CMDBServiceRelation
        fields = ["template_id"]


class LogServiceRelationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogServiceRelation
        fields = ["log_type", "related_bk_biz_id", "value"]

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
        fields = ["relate_bk_biz_id", "relate_app_name"]


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
    log_relation = LogServiceRelationSerializer(required=False, allow_null=True)
    apdex_relation = ServiceApdexConfigSerializer(required=False, allow_null=True)
    uri_relation = serializers.ListSerializer(required=False, allow_null=True, child=serializers.CharField())
    labels = serializers.ListSerializer(required=False, allow_null=True, child=serializers.CharField())


class LogServiceRelationOutputSerializer(serializers.ModelSerializer):
    log_type_alias = serializers.CharField(source="get_log_type_display")
    related_bk_biz_name = serializers.SerializerMethodField()
    value_alias = serializers.SerializerMethodField()

    def get_value_alias(self, instance):
        if instance.log_type == ServiceRelationLogTypeChoices.BK_LOG:
            # 关联了日志平台 -> 获取索引集名称
            index_set = api.log_search.search_index_set(bk_biz_id=instance.bk_biz_id)
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

    class Meta:
        model = LogServiceRelation
        fields = ["log_type", "related_bk_biz_id", "related_bk_biz_name", "value", "value_alias", "log_type_alias"]
