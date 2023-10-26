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
import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from monitor_web.commons.data_access import PluginDataAccessor
from monitor_web.models import CollectorPluginMeta

from metadata.models import DataSource

logger = logging.getLogger("metadata")


class Command(BaseCommand):
    def handle(self, *args, **options):
        if settings.ROLE != "api":
            print("try with: ./bin/api_manage.sh change_plugin_biz --arguments")
            return
        plugin_id = options["plugin_id"]
        bk_biz_id = options["bk_biz_id"]
        # 获取 plugin 信息
        try:
            plugin = CollectorPluginMeta.objects.get(plugin_id=plugin_id)
        except CollectorPluginMeta.DoesNotExist:
            self.stdout.write(f"can not find plugin, plugin_id:{plugin_id}")
            return

        if int(bk_biz_id) != plugin.bk_biz_id and plugin.bk_biz_id != 0:
            self.stdout.write("for non-global plugin, input biz ID needs to be consistent with the actual biz ID")
            return

        plugin_data_info = PluginDataAccessor(plugin.current_version, operator=None)

        # 更新 datasource
        DataSource.objects.get(bk_data_id=plugin_data_info.data_id).update_config(
            operator="admin", space_uid=f"bkcc__{bk_biz_id}"
        )

    def add_arguments(self, parser):
        parser.add_argument("--plugin_id", type=str, required=True, help="插件 ID")
        parser.add_argument("--bk_biz_id", type=int, required=True, help="业务 ID")
