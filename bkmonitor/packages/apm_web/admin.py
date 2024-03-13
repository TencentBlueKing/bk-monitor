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

from django.contrib import admin

from apm_web import models


def register(model, search_fields=None, list_filter=None):
    if not search_fields:
        search_fields = ("bk_biz_id", "app_name")
    if not list_filter:
        list_filter = ("bk_biz_id", "app_name")

    clz = type(
        f"{model.__name__}Admin",
        (admin.ModelAdmin,),
        {"list_display": all_fields(model), "search_fields": search_fields, "list_filter": list_filter},
    )

    admin.site.register(model, clz)


def all_fields(model):
    return [field.name for field in model._meta.get_fields()]


register(models.Application)
register(models.ApplicationRelationInfo, ("application_id",), ("application_id",))
register(models.ApmMetaConfig, ("config_level", "level_key"), ("config_level", "level_key"))
register(models.ApplicationCustomService)
register(models.CMDBServiceRelation)
register(models.LogServiceRelation)
register(models.AppServiceRelation)
register(models.UriServiceRelation)
register(models.ApdexServiceRelation)
register(models.ProfileUploadRecord)
