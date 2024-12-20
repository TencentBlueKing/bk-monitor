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
import base64
import json
import logging
from itertools import zip_longest

from django.core.management import BaseCommand

from apm.core.discover.precalculation.daemon import DaemonTaskHandler
from apm.models import ApmApplication, TraceDataSource

logger = logging.getLogger("apm")


class Command(BaseCommand):
    """
    BMW 预计算任务操作工具

    [不同模式] | 使用 -m 参数指定

    [1] -m = upsert 创建/更新预计算任务
    参数:
        --bk_biz_id 业务 Id
        --app_name 应用名称
        [--queue] 分派的队列 (不指定则为 default 队列)
        [--config] 任务配置
    作用: 开启或者更新一个 APM 应用的预计算任务

    [2] -m = reload 重新启动已有任务 + 启动未启动的任务
    参数:
        --queue 队列名称
    作用：会对所有 APM 应用进行一次遍历，得出已启动了预计算任务的应用和未启动预计算任务的应用，
    然后对启动了预计算任务的应用进行重启(worker 不变)，对未启动预计算的任务分派到 queue 队列中，
    目前此模式不推荐使用，因为已有定时任务 bmw_task_cron 作为替代

    [3] -m = rebalance 重平衡所有已运行的预计算任务
    参数:
        --queues 队列名称列表
    作用: 对所有正在运行的任务重新计算分派的队列（基于 queues），会尽量对各个队列分派相同数量的任务，
    目前此模式不推荐使用，因为已有定时任务 bmw_task_cron 作为替代
    """

    help = "Apm Precalculate Command"

    def add_arguments(self, parser):
        parser.add_argument('-m', '--mode', type=str, help='运行模式(add/reload/update/rebalance)')

        # mode = rebalance 参数 ↓
        parser.add_argument('-s', "--queues", type=str, help="队列名称列表(rebalance 基于这些队列来分派)")

        # mode = update 和 mode = add 的共同参数 ↓
        parser.add_argument('-b', "--bk_biz_id", type=str, help="bk_biz_id")
        parser.add_argument('-a', "--app_name", type=str, help="app_name")
        parser.add_argument('-c', "--config", type=str, help="配置项（base64编码）")

        # mode = update 和 mode = add 和 mode = reload 的共同参数 ↓
        parser.add_argument('-q', "--queue", type=str, help="队列名称")

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
        elif mode == "upsert":
            bk_biz_id = options.get("bk_biz_id")
            app_name = options.get("app_name")
            queue = options.get("queue")
            config = options.get("config")

            if not bk_biz_id or not app_name:
                raise ValueError("需要输入 bk_biz_id 和 app_name")

            trace_datasource = TraceDataSource.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
            application = ApmApplication.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()

            if not trace_datasource or not application or not trace_datasource.result_table_id:
                raise ValueError("应用或数据源无效")

            if config:
                config = json.loads(base64.b64decode(config))
                verify_config = input(f"当前输入的配置为: {config} \n (y/n)")
                if verify_config.lower() != "y":
                    exit(0)

            DaemonTaskHandler.execute(application.id, queue, {"config": config})
        elif mode == "rebalance":
            forward = input("确认当前所有 APM 预计算任务均已暂停 (y/n)")
            if forward.lower() != "y":
                exit(0)

            queues = options.get("queues")
            if not queues:
                raise ValueError("未输入可分配队列")

            queues = queues.split(",")
            rebalance_info, have_data_apps = DaemonTaskHandler.list_rebalance_info(queues)
            self.print_app_queue_mapping(rebalance_info, have_data_apps)
            forward = input("确认以上分配信息，y/n")
            if forward.lower() != "y":
                exit(0)

            DaemonTaskHandler.rebalance(rebalance_info)
            print("执行完成")

    @classmethod
    def print_app_queue_mapping(cls, app_queue_mapping, have_data_apps):
        for queue, apps in app_queue_mapping.items():
            print(f"队列: {queue} 分配的应用: ")
            for item in apps:
                print(
                    f"   ----> Id: {item.id} "
                    f"BkBizId: {item.bk_biz_id} "
                    f"Name: {item.app_name} "
                    f"{'有数据' if item in have_data_apps else '无数据'}"
                )
