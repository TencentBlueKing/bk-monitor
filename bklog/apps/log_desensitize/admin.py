# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
from django.contrib import admin
from apps.utils.admin import AppModelAdmin
from apps.log_desensitize.models import DesensitizeRule, DesensitizeConfig, DesensitizeFieldConfig


@admin.register(DesensitizeRule)
class DesensitizeRuleAdmin(AppModelAdmin):
    list_display = [
        "rule_name",
        "operator",
        "params",
        "match_pattern",
        "space_uid",
        "is_public",
        "match_fields",
        "is_active",
        "created_at",
        "created_by",
        "is_deleted",
    ]
    search_fields = [
        "rule_name",
        "operator",
        "space_uid",
        "is_public",
        "is_active"
    ]


@admin.register(DesensitizeConfig)
class DesensitizeConfigAdmin(AppModelAdmin):
    list_display = ["index_set_id", "text_fields", "created_at", "created_by"]
    search_fields = ["index_set_id"]


@admin.register(DesensitizeFieldConfig)
class DesensitizeFieldConfigAdmin(AppModelAdmin):
    list_display = [
        "index_set_id",
        "field_name",
        "rule_id",
        "operator",
        "params",
        "match_pattern",
        "created_at",
        "created_by"
    ]
    search_fields = [
        "index_set_id",
        "field_name",
        "rule_id",
        "operator",
        "params",
        "match_pattern",
    ]
