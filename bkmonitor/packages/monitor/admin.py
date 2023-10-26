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

from django.contrib import admin
from monitor import models


class UserConfigAdmin(admin.ModelAdmin):
    list_display = ("username", "key")
    list_filter = ("username",)


class ApplicationConfigAdmin(admin.ModelAdmin):
    list_display = ("cc_biz_id", "key")
    list_filter = ("cc_biz_id",)


class GlobalConfigAdmin(admin.ModelAdmin):
    list_display = ("key",)


class UptimeCheckNodeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bk_biz_id",
        "is_common",
        "name",
        "ip",
        "plat_id",
        "location",
        "carrieroperator",
        "is_deleted",
        "update_user",
        "update_time",
    )
    list_filter = ("bk_biz_id", "is_common", "ip", "is_deleted", "update_user", "update_time")


class UptimeCheckTaskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bk_biz_id",
        "protocol",
        "name",
        "location",
        "get_nodes",
        "status",
        "is_deleted",
        "update_user",
        "update_time",
    )
    list_filter = ("bk_biz_id", "protocol", "is_deleted", "update_user", "update_time")

    def get_nodes(self, obj):
        return "\n".join(["{}-{}".format(str(p.id), p.name) for p in obj.nodes.all()])


class UptimeCheckGroupAdmin(admin.ModelAdmin):
    list_display = ("id", "bk_biz_id", "name", "get_nodes", "is_deleted", "update_user", "update_time")
    list_filter = ("bk_biz_id", "is_deleted", "update_user", "update_time")

    def get_nodes(self, obj):
        return "\n".join(["{}-{}".format(str(task.id), task.name) for task in obj.tasks.all()])


admin.site.register(models.UserConfig, UserConfigAdmin)
admin.site.register(models.ApplicationConfig, ApplicationConfigAdmin)
admin.site.register(models.GlobalConfig, GlobalConfigAdmin)
admin.site.register(models.UptimeCheckGroup, UptimeCheckGroupAdmin)
admin.site.register(models.UptimeCheckNode, UptimeCheckNodeAdmin)
admin.site.register(models.UptimeCheckTask, UptimeCheckTaskAdmin)
