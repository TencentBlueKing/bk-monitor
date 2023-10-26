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


import json

from django.db import migrations


def update_host_property(apps, schema_editor):
    HostProperty = apps.get_model("monitor", "HostProperty")
    HostProperty.objects.filter(property="SetName").delete()
    HostProperty.objects.filter(property="ModuleName").update(property="Topo", property_display="拓扑层级")
    prop = HostProperty.objects.create(
        property="BizName", property_display="业务名", required=False, selected=False, index=0
    )

    HostPropertyConf = apps.get_model("monitor", "HostPropertyConf")
    for conf in HostPropertyConf.objects.all():
        property_list = json.loads(conf.property_list)
        new_property_list = []
        for c in property_list:
            if c["id"] == "SetName":
                continue
            if c["id"] == "ModuleName":
                c["id"] = "Topo"
                c["name"] = "拓扑层级"
            new_property_list.append(c)

        new_property_list.append(
            {
                "id": prop.property,
                "name": prop.property_display,
                "required": prop.required,
                "selected": prop.selected,
                "index": len(new_property_list) + 1,
            }
        )
        conf.property_list = json.dumps(new_property_list)
        conf.save()


class Migration(migrations.Migration):

    dependencies = [
        ("monitor", "0061_init_component_instance_name"),
    ]

    operations = [migrations.RunPython(update_host_property)]
