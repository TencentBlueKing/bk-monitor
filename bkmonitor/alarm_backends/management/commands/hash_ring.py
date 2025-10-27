"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from optparse import OptionError

from django.conf import settings
from django.core.management.base import BaseCommand

from alarm_backends.management.base.base import ConsulDispatchCommand
from bkmonitor.utils.common_utils import get_local_ip

logger = logging.getLogger("self_monitor")


class HashRing(ConsulDispatchCommand):
    def on_start(self, *args):
        pass

    def __init__(self, command):
        self.__COMMAND_NAME__ = command
        super().__init__()

    @classmethod
    def is_leader(cls):
        # 使用容器部署时，只需要启动一个进程，不需要通过HashRing判断
        if settings.IS_CONTAINER_MODE:
            return True

        # 处理蓝鲸业务的机器定位为: leader
        # 复用run_access的consul 注册path
        command = cls("run_access-data")

        try:
            _, host_targets = command.dispatch_all_hosts(command.query_for_hosts())
        except ZeroDivisionError:
            logger.exception("寻找leader失败，集群无任何注册节点")
            return False

        local_host = get_local_ip()
        local_targets = host_targets.get(local_host, [])
        if not local_targets:
            logger.error(f"Node: {local_host} get nothing target")
        return settings.DEFAULT_BK_BIZ_ID in local_targets


class Command(BaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--host")
        parser.add_argument("--biz_id", type=int)
        parser.add_argument("--type")

    def handle(self, name="run_access-data", *args, **options):
        if not name:
            raise OptionError("name is required.", "name")

        command = HashRing(options.get("type") or name)

        biz_id = options.get("biz_id")
        host = options.get("host")
        if host == "localhost":
            host = command.host_addr

        _, host_targets = command.dispatch_all_hosts(command.query_for_hosts())

        for target_host, targets in list(host_targets.items()):
            if host and target_host != host:
                continue
            target_list = [i for i in targets if not biz_id or i == biz_id]
            if target_list:
                print(f"host: {target_host}")
                for target in target_list:
                    print(f"- {target}")
