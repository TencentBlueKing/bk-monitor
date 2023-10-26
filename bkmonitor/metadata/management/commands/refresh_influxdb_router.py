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

from typing import Any
from django.core.management.base import BaseCommand

from metadata import models
from metadata.utils import consul_tools


class Command(BaseCommand):
    help = "refresh influxdb router command"

    def handle(self, *args: Any, **options: Any) -> None:
        """当有变动时，更新 influxdb 对应的路由，以使立即生效"""
        self.stdout.write("start to refresh influxdb router")
        try:
            for host_info in models.InfluxDBHostInfo.objects.all():
                host_info.refresh_consul_cluster_config()

            models.InfluxDBClusterInfo.refresh_consul_cluster_config()

            index = models.InfluxDBStorage.objects.count()
            for result_table in models.InfluxDBStorage.objects.all():
                index -= 1
                result_table.refresh_consul_cluster_config(is_publish=(index == 0))

            # 更新 vm router
            models.AccessVMRecord.refresh_vm_router()
        except Exception as e:
            self.stderr.write(f"failed to refresh influxdb router info {e}")

        # 刷新tag路由
        try:
            models.InfluxDBTagInfo.refresh_consul_tag_config()
        except Exception as e:
            self.stderr.write(f"refresh consul tag error, {e}")

        # 任务完成前，更新一下version
        consul_tools.refresh_router_version()
        self.stdout.write("refresh influxdb router completely")
