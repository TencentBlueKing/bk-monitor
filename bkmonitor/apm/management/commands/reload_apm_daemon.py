# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from itertools import zip_longest

from django.core.management import BaseCommand

from apm.core.discover.precalculation.daemon import DaemonTaskHandler
from apm.models import ApmApplication, TraceDataSource

logger = logging.getLogger("apm")


class Command(BaseCommand):
    """
    操作预计算任务
    -m 选择模式
    可选项：reload / update / rebalance

    mode == reload 重新启动常驻任务
    参数：
        -q 指定重新启动后的队列名称（可选）

    mode == update 更新or创建常驻任务
    参数：
        -b 需要更新的应用的业务 id
        -a 需要更新的应用的 appName
        -p 调整此应用的qps (0为无限制 <0 为拒绝)

    mode == rebalance 将所有APM应用进行重新分配常驻任务
    参数：
        -r 可用的队列 如："apm-01,apm-02,apm-03"
    """

    help = "reload task from apm pre-calculate tasks"

    def add_arguments(self, parser):
        parser.add_argument('-m', '--mode', type=str, help='运行模式(reload/update/rebalance)')
        parser.add_argument('-q', "--queue", type=str, help="创建任务时分配到的队列名称(reload 模式下)")
        parser.add_argument('-b', "--bk_biz_id", type=str, help="需要创建/更新的业务 id(update 模式下)")
        parser.add_argument('-a', "--app_name", type=str, help="需要创建/更新的 app_name(update 模式下)")
        parser.add_argument('-p', "--qps", type=str, help="需要创建/更新的 qps(update 模式下)")
        parser.add_argument('-r', "--queues", type=str, help="可分配的队列用,连接(update 模式下)")

    @classmethod
    def pretty_print(cls, apps):
        return '\n'.join(
            [
                ' || '.join(
                    [
                        f"({model.bk_biz_id}, {model.id}, {model.app_name}, {model.trace_datasource.bk_data_id})"
                        for model in group
                        if model is not None
                    ]
                )
                for group in zip_longest(*(iter(apps),) * 5)
            ]
        )

    def handle(self, *args, **options):
        """
        重新启动 dataId 没有数据的预计算任务
        """

        mode = options.get("mode")

        if mode == "reload":
            queue = options.get("queue")
            if not queue:
                raise ValueError("需要输入队列名称")

            apps_for_beat, apps_for_daemon, apps_for_reload, apps_for_create = DaemonTaskHandler.get_task_info()
            logger.info(
                f"APM 预计算任务分布："
                f"\n定时任务共 {len(apps_for_beat)} 个：\n{self.pretty_print(apps_for_beat)}\n---\n"
                f"\n正常运行的常驻任务共 {len(apps_for_daemon)} 个：\n{self.pretty_print(apps_for_daemon)}\n---\n"
                f"\n需要重载的常驻任务共 {len(apps_for_reload)} 个：\n{self.pretty_print(apps_for_reload)}\n---\n"
                f"\n需要创建的常驻任务共 {len(apps_for_create)} 个：\n{self.pretty_print(apps_for_create)}\n---\n"
            )

            forward = input("是否继续 Y / N")
            if forward.lower() == "y":
                DaemonTaskHandler.create_tasks(apps_for_create, queue)
                DaemonTaskHandler.reload_tasks(apps_for_reload)
            elif forward.lower() == "n":
                exit(0)
            else:
                raise ValueError("无效输入")
        elif mode == "update":
            bk_biz_id = options.get("bk_biz_id")
            app_name = options.get("app_name")
            queue = options.get("queue")
            qps = options.get("qps")

            if not bk_biz_id or not app_name:
                raise ValueError("需要输入 bk_biz_id 和 app_name")

            trace_datasource = TraceDataSource.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
            application = ApmApplication.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()

            if not trace_datasource or not application:
                raise ValueError("应用不存在")

            DaemonTaskHandler.upsert_tasks(
                application.id, trace_datasource.bk_data_id, queue, {"qps": qps} if qps else {}
            )
        elif mode == "rebalance":
            forward = input("确认当前所有 APM 预计算任务均已暂停 (y/n)")
            if forward.lower() != "y":
                exit(0)

            queues = options.get("queue")
            if not queues:
                raise ValueError("未输入可分配队列")

            queues = queues.split(",")
            rebalance_info = DaemonTaskHandler.list_rebalance_info(queues)
            self.print_app_queue_mapping(rebalance_info)
            forward = input("确认以上分配信息，y/n")
            if forward.lower() != "y":
                exit(0)

            DaemonTaskHandler.rebalance(rebalance_info)
            print("执行完成")

    @classmethod
    def print_app_queue_mapping(cls, app_queue_mapping):
        for queue, apps in app_queue_mapping.items():
            print(f"队列: {queue} 分配的应用: ")
            for item in apps:
                print(f"   ----> Id: {item.id} BkBizId: {item.bk_biz_id} Name: {item.app_name}")
