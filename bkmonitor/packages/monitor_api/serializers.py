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


from django.apps import apps
from django.conf import settings

from bkmonitor.views import serializers
from monitor_api import models


def get_serializer(model):

    _extra_kwargs = {}

    # learn more at https://github.com/encode/django-rest-framework/issues/1101
    if issubclass(model, models.AbstractRecordModel):
        _extra_kwargs.update(
            {
                "is_enabled": {
                    "default": True,
                },
            }
        )

    class Meta:
        model = model
        fields = "__all__"
        extra_kwargs = _extra_kwargs

    cls_name = "%sSerializer" % model.__name__
    return cls_name, type(
        str(cls_name),
        (serializers.ModelSerializer,),
        {
            "Meta": Meta,
        },
    )


for full_name, _ in settings.MONITOR_API_MODELS:
    app_label, model_name = full_name.split(".")
    app_config = apps.get_app_config(app_label)
    model = app_config.get_model(model_name)
    name, serializer = get_serializer(model)
    locals()[name] = serializer
