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
from django.db.transaction import atomic

from metadata import config
from metadata.task.bcs import update_bcs_cluster_cloud_id_config


class Command(BaseCommand):
    """
    根据BCS集群的云区域ID
    """

    @atomic(config.DATABASE_CONNECTION_NAME)
    def handle(self, *args, **options):
        update_bcs_cluster_cloud_id_config()
