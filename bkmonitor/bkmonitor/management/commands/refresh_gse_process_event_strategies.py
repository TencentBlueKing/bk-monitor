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

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import translation
from django.utils.translation import gettext as _

from bkmonitor.models import DutyArrange, UserGroup


class Command(BaseCommand):
    """
    执行进程托管的内置策略逻辑
    使用示例
    web页面管理端：admin/bkmonitor/globalconfig/?is_advanced__exact=1
    OFFICIAL_PLUGINS_MANAGERS 配置好之后，执行：
    ./bin/manage.sh refresh_gse_process_event_strategies
    """

    def handle(self, *usernames, **kwargs):
        if not settings.OFFICIAL_PLUGINS_MANAGERS:
            print("未配置OFFICIAL_PLUGINS_MANAGERS全局变量, 命令退出")
            return

        print(f"变更官方插件管理员通知组: {settings.OFFICIAL_PLUGINS_MANAGERS}")
        # 获取当前所有官方插件通知组
        ug_ids = list(UserGroup.objects.filter(name="【蓝鲸】官方插件管理员").values_list("id", flat=True))
        translation.activate("en")
        ext_ug_ids = list(UserGroup.objects.filter(name=_("【蓝鲸】官方插件管理员")).values_list("id", flat=True))
        ug_ids += ext_ug_ids
        das = DutyArrange.objects.filter(user_group_id__in=ug_ids)
        for da in das:
            print(
                f"UserGroup[{da.user_group_id}]: {[i['id'] for i in da.users if i['type']=='user']} ->"
                f" {settings.OFFICIAL_PLUGINS_MANAGERS}"
            )
            da.users = [{"id": user, "type": "user"} for user in settings.OFFICIAL_PLUGINS_MANAGERS]
            da.save()
