"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.core.management.base import BaseCommand

from metadata.utils.gse import KafkaGseSyncer


class Command(BaseCommand):
    """
    同步默认的消息队列(stream_to_info)信息到zk或gse，每次部署的时候执行
    """

    def handle(self, *args, **options):
        """
        同步默认的kafka信息到zk或者gse
        """
        KafkaGseSyncer.sync_to_gse()
