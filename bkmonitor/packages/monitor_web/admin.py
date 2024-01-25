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
import inspect

from django.contrib import admin

from monitor_web import models

# 因为配置admin界面时，list_display, search_fields, list_filter 都是全部字段中排除效果不好的几个，
# 所以在这里对每个model名称后面提供这三个选项要排除的字段，并以全小写提供。
model_admins = [
    ["AlertSolution", (), (), ()],
    ["CollectConfigMeta", ("plugin",), (), ("id", "name", "deployment_config")],
    ["CollectorPluginConfig", (), (), ("id",)],
    ["CollectorPluginInfo", ("logo",), (), ("id", "metric_json")],
    ["CollectorPluginMeta", (), (), ("id", "plugin_id")],
    ["CustomEventGroup", (), (), ("id", "name")],
    ["CustomEventItem", (), (), ("id",)],
    ["DataTargetMapping", (), (), ("id",)],
    ["DeploymentConfigVersion", (), (), ("id", "task_ids")],
    ["ImportDetail", (), (), ("id",)],
    ["ImportHistory", (), (), ("id",)],
    ["ImportParse", (), (), ("id",)],
    ["OperatorSystem", (), (), ("id",)],
    ["PluginVersionHistory", (), (), ("id",)],
    ["UploadedFileInfo", (), (), ("id",)],
    ["QueryHistory", ("config",), ("config",), ("id", "name", "config")],
]

for model_name, list_display_exclude, search_fields_exclude, list_filter_exclude in model_admins:
    model_class = getattr(models, model_name)
    fields = [field.name for field in model_class._meta.fields if field.name in model_class.__dict__]
    admin.site.register(
        model_class,
        list_display=[field for field in fields if field.lower() not in list_display_exclude],
        search_fields=[field for field in fields if field.lower() not in search_fields_exclude],
        list_filter=[field for field in fields if field.lower() not in list_filter_exclude],
    )

# 自动导入剩余model
for name, obj in inspect.getmembers(models):
    try:
        if inspect.isclass(obj) and name not in [model_admin[0] for model_admin in model_admins]:
            admin.site.register(getattr(models, name))
    except Exception:
        pass
