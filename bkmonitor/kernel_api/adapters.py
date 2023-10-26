# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from copy import deepcopy

import django_filters
from django.db import models as django_models
from rest_framework import serializers

from bkmonitor.views.renderers import MonitorJSONRenderer

# tapd:1010104091006892981
API_FIELD_FORMATED_MAPPINGS = {
    "app_id": "bk_app_code",
    "app_code": "bk_app_code",
    "app_token": "bk_app_secret",
    "company_id": "bk_supplier_id",
    "company_code": "bk_supplier_account",
    "username": "bk_username",
    "plat_id": "bk_cloud_id",
    "plat_name": "bk_cloud_name",
    "biz_id": "bk_biz_id",
    "cc_biz_id": "bk_biz_id",
    "cc_plat_id": "bk_cloud_id",
    "cc_company_id": "bk_supplier_id",
}


class ApiRenderer(MonitorJSONRenderer):
    def format_field(self, result, level=0):
        if level != 0:
            if isinstance(result, (list, tuple)):
                result = [self.format_field(i, level - 1) for i in result]
            elif isinstance(result, dict):
                result = {
                    API_FIELD_FORMATED_MAPPINGS.get(k, k): self.format_field(v, level - 1)
                    for k, v in list(result.items())
                }
        return result

    def get_result(self, data, renderer_context=None):
        result = super(ApiRenderer, self).get_result(data, renderer_context)
        return self.format_field(result, -1)


class ApiModelFilterSet(django_filters.FilterSet):
    def get_extend_fields(self):
        extend_fields = {}
        for name, filter_ in list(self.filters.items()):
            if name in API_FIELD_FORMATED_MAPPINGS and name in filter_.model._meta.get_all_field_names():
                extend_fields[API_FIELD_FORMATED_MAPPINGS[name]] = name
        return extend_fields

    def __init__(self, data=None, queryset=None, prefix=None, strict=None, request=None):
        super(ApiModelFilterSet, self).__init__(data, queryset, prefix, strict, request)

        data = self.data.copy()
        extend_fields = getattr(self.Meta, "extend_fields", None) or self.get_extend_fields()
        self.data = data
        self.extend_fields = extend_fields

        for k, v in list(data.items()):
            if k in extend_fields:
                data[extend_fields[k]] = v


class SerializerFieldFormatedMeta(type):
    def __new__(cls, name, bases, attrs):
        source_mappings = attrs.get("source_mappings")
        if source_mappings:
            for attr, source in list(source_mappings.items()):
                field = attrs.get(attr)
                if not isinstance(field, (serializers.Field, django_models.Field)):
                    continue
                if field.source != attr:
                    continue
                field = deepcopy(field)
                field.source = source
                attrs[name] = attrs
        return type(name, bases, attrs)


class FormatedViewsetMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        return super(FormatedViewsetMixin, self).finalize_response(request, response, *args, **kwargs)
