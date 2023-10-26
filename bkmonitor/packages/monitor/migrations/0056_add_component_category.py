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


from django.db import migrations

from monitor.models import ComponentCategoryRelationship


def add_default_component_category(apps, schema_editor):
    ComponentCategory = apps.get_model("monitor", "ComponentCategory")

    default_categories = [
        {
            "display_name": "消息队列",
            "components": [
                "rabbitmq",
                "zookeeper",
                "kafka",
            ],
        },
        {
            "display_name": "HTTP服务",
            "components": [
                "haproxy",
                "weblogic",
                "iis",
                "apache",
                "nginx",
                "tomcat",
            ],
        },
        {
            "display_name": "数据库",
            "components": [
                "oracle",
                "memcache",
                "mssql",
                "mongodb",
                "elastic",
                "mysql",
                "redis",
            ],
        },
        {
            "display_name": "办公应用",
            "components": [
                "ad",
                "exchange2010",
            ],
        },
    ]

    for category_info in default_categories:
        category, _ = ComponentCategory.objects.update_or_create(
            display_name=category_info["display_name"],
        )
        for component_name in category_info["components"]:
            ComponentCategoryRelationship.objects.update_or_create(
                category_id=category.id, component_name=component_name, is_internal=True
            )


class Migration(migrations.Migration):

    dependencies = [
        ("monitor", "0055_auto_20181129_1828"),
    ]

    operations = [migrations.RunPython(add_default_component_category)]
