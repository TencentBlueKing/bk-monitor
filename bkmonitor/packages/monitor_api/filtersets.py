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
import django_filters
from django.apps import apps
from django.conf import settings
from django.db.models import fields

COMMON_CMP_LOOKUPS = ["gt", "gte", "lt", "lte"]
COMMON_LIKE_LOOKUPS = ["contains", "icontains", "startswith", "endswith"]
COMMON_DATE_LOOKUPS = ["year", "month", "day"]
COMMON_TIME_LOOKUPS = ["hour", "minute", "second"]

NUMBER_LOOKUPS = COMMON_CMP_LOOKUPS + ["in"]
DATE_LOOKUPS = COMMON_CMP_LOOKUPS + COMMON_DATE_LOOKUPS + ["range"]
TIME_LOOKUPS = COMMON_CMP_LOOKUPS + COMMON_TIME_LOOKUPS + ["range"]
DATETIME_LOOKUPS = DATE_LOOKUPS + COMMON_TIME_LOOKUPS

ADVANCED_LOOKUPS = {
    fields.AutoField: NUMBER_LOOKUPS,
    fields.BigIntegerField: NUMBER_LOOKUPS,
    fields.CharField: COMMON_LIKE_LOOKUPS + ["in"],
    fields.DateField: DATE_LOOKUPS,
    fields.DateTimeField: DATETIME_LOOKUPS,
    fields.DecimalField: NUMBER_LOOKUPS,
    fields.EmailField: COMMON_LIKE_LOOKUPS,
    fields.FilePathField: COMMON_LIKE_LOOKUPS,
    fields.FloatField: NUMBER_LOOKUPS,
    fields.IntegerField: NUMBER_LOOKUPS,
    fields.IPAddressField: COMMON_LIKE_LOOKUPS + ["in"],
    fields.GenericIPAddressField: COMMON_LIKE_LOOKUPS + ["in"],
    fields.PositiveIntegerField: NUMBER_LOOKUPS,
    fields.PositiveSmallIntegerField: NUMBER_LOOKUPS,
    fields.SlugField: COMMON_LIKE_LOOKUPS + ["in"],
    fields.SmallIntegerField: NUMBER_LOOKUPS,
    fields.TextField: COMMON_LIKE_LOOKUPS,
    fields.TimeField: TIME_LOOKUPS,
    fields.URLField: COMMON_LIKE_LOOKUPS,
    fields.UUIDField: ["in"],
}

IMPLICIT_LOOKUPS = ["exact", "isnull"]


def get_lookups(filter_model):
    result = {}

    for field in filter_model._meta.get_fields():
        if field.is_relation:
            continue

        # 跳过jsonfield
        if field.__class__.__name__ == "JSONField":
            continue

        lookups = []
        lookups.extend(IMPLICIT_LOOKUPS)
        lookups.extend(ADVANCED_LOOKUPS.get(field.__class__, []))
        result[field.attname] = set(lookups)

    return result


def get_filterset(filter_model):
    class Meta:
        model = filter_model
        fields = get_lookups(model)

    cls_name = "%sFilterSet" % model.__name__
    return cls_name, type(
        cls_name,
        (django_filters.FilterSet,),
        {
            "Meta": Meta,
        },
    )


for full_name, _ in settings.MONITOR_API_MODELS:
    app_label, model_name = full_name.split(".")
    app_config = apps.get_app_config(app_label)
    model = app_config.get_model(model_name)
    name, filterset = get_filterset(model)
    locals()[name] = filterset
