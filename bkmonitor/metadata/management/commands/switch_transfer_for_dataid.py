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

from django.core.management.base import BaseCommand, CommandError

from metadata.models import DataSource


class Command(BaseCommand):
    """
    将指定 data id 切换到新的 transfer 集群
    # 用法1 ：切换特定的一批 data_id 到 test 集群
    bin/manage.sh switch_transfer_for_dataid test --data_id 1500001 1500002

    # 用法2：切换来源系统为 bk_monitor 的所有 data_id 到 test 集群
    bin/manage.sh switch_transfer_for_dataid test --source_system bk_monitor
    """

    def add_arguments(self, parser):
        parser.add_argument("transfer_cluster_id", type=str, help="target transfer cluster id")
        parser.add_argument("--data_id", type=int, nargs="*", help="data_id to switch")
        parser.add_argument("--bk_data_ids", type=str, help="data_ids, split by comma")
        parser.add_argument("--source_system", type=str, help="data_id for source system to switch")

    def handle(self, transfer_cluster_id, *args, **options):
        data_ids = options.get("data_id")
        bk_data_ids = options.get("bk_data_ids")
        source_system = options.get("source_system")

        if not (data_ids or bk_data_ids or source_system):
            raise CommandError("one of --data_id, --source_system or --bk_data_ids option must be given")

        queryset = DataSource.objects.all()
        if data_ids:
            queryset = queryset.filter(bk_data_id__in=data_ids)
        if source_system:
            queryset = queryset.filter(source_system=source_system)
        if bk_data_ids:
            filter_data_id_list = [int(data_id) for data_id in bk_data_ids.split(",")]
            queryset = queryset.filter(bk_data_id__in=filter_data_id_list)

        self.stdout.write(
            self.style.SUCCESS("[switch_transfer_for_dataid] START. Total count: {}".format(queryset.count()))
        )

        for datasource in queryset:
            # 需要将老版的consul路径的配置删除
            old_transfer_id = datasource.transfer_cluster_id
            datasource.delete_consul_config()
            datasource.transfer_cluster_id = transfer_cluster_id
            datasource.save(update_fields=["transfer_cluster_id"])
            # 从 db 中重新拉取数据
            datasource.clean_cache()
            # 然后把配置刷到新版consul路径
            datasource.refresh_consul_config()

            self.stdout.write(
                "data_id({}) transfer config changed: [{}] -> [{}]".format(
                    datasource.bk_data_id, old_transfer_id, datasource.transfer_cluster_id
                )
            )

        self.stdout.write(self.style.SUCCESS("[switch_transfer_for_dataid] DONE!"))
