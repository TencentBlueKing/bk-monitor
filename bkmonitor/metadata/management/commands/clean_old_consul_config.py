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

from django.core.management.base import BaseCommand

from metadata.config import CONSUL_PATH
from metadata.models import DataSource


class Command(BaseCommand):
    """
    清理老版本的consul路径，并将配置刷新到新的consul路径
    """

    def handle(self, *args, **options):
        self.stdout.write("[clean_old_consul_config] START.")
        # 获取全部数据源
        datasources = DataSource.objects.all()
        # 遍历类型，每种类型都要遍历datasource，更新key，且删除多余的consul key
        # 整个流程不save，model的改动都是临时的
        for datasource in datasources:
            # 需要将老版的consul路径的配置删除
            consul_config_path = f"{CONSUL_PATH}/data_id/{datasource.bk_data_id}"
            datasource.delete_consul_config(consul_config_path)

            # 然后把配置刷到新版consul路径
            datasource.refresh_consul_config()
            self.stdout.write(
                "bk_data_id->[{}] clean old consul config ({}), and refresh new config ({})".format(
                    datasource.bk_data_id, consul_config_path, datasource.consul_config_path
                )
            )
        self.stdout.write("[clean_old_consul_config] DONE!")
