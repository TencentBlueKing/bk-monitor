"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import json
import logging
import os
import time
from collections import Counter
from itertools import zip_longest

from django.conf import settings
from django.core.management import BaseCommand

from apm.core.discover.precalculation.check import PreCalculateCheck
from apm.core.discover.precalculation.daemon import DaemonTaskHandler
from apm.core.discover.precalculation.task_spec import PreCalculateTaskSpec, PreCalculateTaskSpecProvider
from apm.models import ApmApplication

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

    [4] -m = stop_all 停用所有预计算任务
    参数:
        [--backup] 备份文件路径 (不指定则写到当前目录 apm_precalculate_tasks_<时间戳>.json)
    作用: 先把 BMW 中所有 APM 预计算任务（dataId、队列、payload）备份到文件，确认后逐个删除。
    要求已开启全局配置 APM_BMW_TASK_CRON_DRY_RUN，否则 bmw_task_cron 会重新下发这些任务

    [5] -m = restore 按备份文件恢复预计算任务
    参数:
        --backup 备份文件路径
        [--data-ids] 只恢复这些 dataId（逗号分隔）
        [--exclude-data-ids] 不恢复这些 dataId（逗号分隔）
        [--exclude-biz-ids] 不恢复这些业务下的 dataId（逗号分隔）
        [--exclude-app-prefixes] 不恢复应用名以这些前缀开头的 dataId（逗号分隔）
    作用: 按备份文件中的队列和 payload 重新下发任务，已在运行的 dataId 会跳过，可重复执行；
    恢复前可以修改备份文件中的 queue 来调整任务分配。
    按业务/应用名过滤时，dataId 下的应用全部命中才排除；共享 dataId 只有部分应用命中时仍恢复并单独列出

    [6] -m = move 迁移预计算任务到指定队列
    参数:
        --data-ids 要迁移的 dataId（逗号分隔）
        --queue 目标队列
    作用: 删除这些 dataId 在 BMW 中的全部任务记录，等待原 worker 停止后，用原 payload 在目标队列重建。
    通道积压已满的任务迁移后，原 worker 可能残留占用内存，需要重启原 worker 释放
    """

    MOVE_WAIT_SECONDS = 15

    help = "Apm Precalculate Command"

    def add_arguments(self, parser):
        parser.add_argument("-m", "--mode", type=str, help="运行模式(upsert/reload/rebalance/stop_all/restore)")

        # mode = stop_all 和 mode = restore 参数 ↓
        parser.add_argument("--backup", type=str, help="预计算任务备份文件路径")

        # mode = restore 过滤参数 ↓
        parser.add_argument("--data-ids", type=str, help="restore 时只恢复 / move 时迁移这些 dataId（逗号分隔）")
        parser.add_argument("--exclude-data-ids", type=str, help="不恢复这些 dataId（逗号分隔）")
        parser.add_argument("--exclude-biz-ids", type=str, help="不恢复这些业务下的 dataId（逗号分隔）")
        parser.add_argument("--exclude-app-prefixes", type=str, help="不恢复应用名以这些前缀开头的 dataId（逗号分隔）")

        # mode = rebalance 参数 ↓
        parser.add_argument("-s", "--queues", type=str, help="队列名称列表(rebalance 基于这些队列来分派)")

        # mode = update 和 mode = add 的共同参数 ↓
        parser.add_argument("-b", "--bk_biz_id", type=str, help="bk_biz_id")
        parser.add_argument("-a", "--app_name", type=str, help="app_name")
        parser.add_argument("-c", "--config", type=str, help="配置项（base64编码）")

        # mode = update 和 mode = add 和 mode = reload 的共同参数 ↓
        parser.add_argument("-q", "--queue", type=str, help="队列名称")

    @classmethod
    def pretty_print(cls, task_specs):
        return "\n".join(
            [
                " || ".join([cls.format_task_spec(model) for model in group if model is not None])
                for group in zip_longest(*(iter(task_specs),) * 5)
            ]
        )

    @classmethod
    def format_task_spec(cls, task_spec: PreCalculateTaskSpec) -> str:
        apps = ",".join([f"{app.bk_biz_id}:{app.id}:{app.app_name}" for app in task_spec.apps])
        return f"(data_id={task_spec.data_id}, shared={task_spec.is_shared}, apps=[{apps}])"

    def handle(self, *args, **options):
        mode = options.get("mode")
        if mode == "reload":
            queue = options.get("queue")
            if not queue:
                raise ValueError("需要输入队列名称")

            task_specs_for_beat, task_specs_for_daemon, task_specs_for_reload, task_specs_for_create = (
                DaemonTaskHandler.get_task_info()
            )
            logger.info(
                f"APM 预计算任务分布："
                f"\n定时任务共 {len(task_specs_for_beat)} 个：\n{self.pretty_print(task_specs_for_beat)}\n---\n"
                f"\n正常运行的常驻任务共 {len(task_specs_for_daemon)} 个：\n{self.pretty_print(task_specs_for_daemon)}\n---\n"
                f"\n需要重载的常驻任务共 {len(task_specs_for_reload)} 个：\n{self.pretty_print(task_specs_for_reload)}\n---\n"
                f"\n需要创建的常驻任务共 {len(task_specs_for_create)} 个：\n{self.pretty_print(task_specs_for_create)}\n---\n"
            )

            forward = input("是否继续 Y / N")
            if forward.lower() == "y":
                DaemonTaskHandler.create_tasks(task_specs_for_create, queue)
                DaemonTaskHandler.reload_tasks(task_specs_for_reload)
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

            application = ApmApplication.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()

            if not application or not application.trace_datasource or not application.trace_datasource.result_table_id:
                raise ValueError("应用或数据源无效")

            task_spec = PreCalculateTaskSpecProvider.get_task_spec(application.trace_datasource.bk_data_id)

            if config:
                config = json.loads(base64.b64decode(config))
                verify_config = input(f"当前输入的配置为: {config} \n (y/n)")
                if verify_config.lower() != "y":
                    exit(0)

            DaemonTaskHandler.execute(task_spec, queue, {"config": config})
        elif mode == "rebalance":
            forward = input("确认当前所有 APM 预计算任务均已暂停 (y/n)")
            if forward.lower() != "y":
                exit(0)

            queues = options.get("queues")
            if not queues:
                raise ValueError("未输入可分配队列")

            queues = queues.split(",")
            rebalance_info, have_data_task_specs = DaemonTaskHandler.list_rebalance_info(queues)
            self.print_task_spec_queue_mapping(rebalance_info, have_data_task_specs)
            forward = input("确认以上分配信息，y/n")
            if forward.lower() != "y":
                exit(0)

            DaemonTaskHandler.rebalance(rebalance_info)
            print("执行完成")
        elif mode == "stop_all":
            self.stop_all(options.get("backup"))
        elif mode == "restore":
            self.restore(options.get("backup"), options)
        elif mode == "move":
            self.move(set(self.split_option(options.get("data_ids"))), options.get("queue"))

    @classmethod
    def stop_all(cls, backup_path):
        if not settings.APM_BMW_TASK_CRON_DRY_RUN:
            raise ValueError("请先开启全局配置 APM_BMW_TASK_CRON_DRY_RUN，否则 bmw_task_cron 会重新下发已停用的任务")

        tasks = PreCalculateCheck._list_daemon_tasks()
        duplicated = [data_id for data_id, count in Counter(task["data_id"] for task in tasks).items() if count > 1]
        print(
            f"共 {len(tasks)} 个 APM 预计算任务，重复 dataId: {duplicated}，"
            f"按队列分布: {dict(Counter(task['queue'] for task in tasks))}"
        )
        if not tasks:
            return

        backup_path = backup_path or f"apm_precalculate_tasks_{int(time.time())}.json"
        with open(backup_path, "w") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        print(f"已备份到 {os.path.abspath(backup_path)}，可用 -m restore --backup 恢复")

        if input(f"确认停用以上 {len(tasks)} 个任务 (y/n)").lower() != "y":
            exit(0)

        for task in tasks:
            DaemonTaskHandler.remove(task["task_uni_id"])
        print(f"停用完成，剩余 APM 预计算任务 {len(PreCalculateCheck._list_daemon_tasks())} 个")

    @classmethod
    def restore(cls, backup_path, options):
        if not backup_path:
            raise ValueError("需要输入 --backup 备份文件路径")

        with open(backup_path) as f:
            tasks = cls.filter_restore_tasks(json.load(f), options)

        running_data_ids = {task["data_id"] for task in PreCalculateCheck._list_daemon_tasks()}
        pending = {}
        for task in tasks:
            if task["data_id"] not in running_data_ids:
                pending.setdefault(task["data_id"], task)
        print(
            f"备份共 {len(tasks)} 个任务，跳过已运行 {len(running_data_ids & {task['data_id'] for task in tasks})} 个，"
            f"待恢复 {len(pending)} 个，按队列分布: {dict(Counter(task['queue'] for task in pending.values()))}"
        )
        if not pending:
            return

        if input(f"确认恢复以上 {len(pending)} 个任务 (y/n)").lower() != "y":
            exit(0)

        for data_id, task in pending.items():
            DaemonTaskHandler._create_daemon_task(data_id, task["queue"], task["payload"])
        print("恢复完成")

    @classmethod
    def move(cls, data_ids, queue):
        if not data_ids or not queue:
            raise ValueError("需要输入 --data-ids 和 --queue")

        tasks = [task for task in PreCalculateCheck._list_daemon_tasks() if task["data_id"] in data_ids]
        missing = data_ids - {task["data_id"] for task in tasks}
        if missing:
            raise ValueError(f"以下 dataId 没有预计算任务: {sorted(missing)}")

        print(f"待迁移任务（dataId, 当前队列）: {[(task['data_id'], task['queue']) for task in tasks]} -> {queue}")
        if input(f"确认迁移以上 {len(data_ids)} 个 dataId 到 {queue} (y/n)").lower() != "y":
            exit(0)

        for task in tasks:
            DaemonTaskHandler.remove(task["task_uni_id"])
        remaining = [task["data_id"] for task in PreCalculateCheck._list_daemon_tasks() if task["data_id"] in data_ids]
        if remaining:
            raise ValueError(f"以下 dataId 删除后仍存在，已中止，请检查后重试: {sorted(set(remaining))}")

        # 等待原 worker 停止任务，避免新旧 worker 同时消费同一个 topic
        time.sleep(cls.MOVE_WAIT_SECONDS)
        payloads = {}
        for task in tasks:
            payloads.setdefault(task["data_id"], task["payload"])
        for data_id, payload in payloads.items():
            DaemonTaskHandler._create_daemon_task(data_id, queue, payload)
        print("迁移完成；通道积压已满的任务迁移后，原 worker 可能残留占用内存，需要重启原 worker 释放")

    @staticmethod
    def split_option(value):
        return [item.strip() for item in (value or "").split(",") if item.strip()]

    @classmethod
    def filter_restore_tasks(cls, tasks, options):
        only_data_ids = set(cls.split_option(options.get("data_ids")))
        exclude_data_ids = set(cls.split_option(options.get("exclude_data_ids")))
        exclude_biz_ids = {int(i) for i in cls.split_option(options.get("exclude_biz_ids"))}
        exclude_app_prefixes = tuple(cls.split_option(options.get("exclude_app_prefixes")))

        if only_data_ids:
            tasks = [task for task in tasks if task["data_id"] in only_data_ids]
        if exclude_data_ids:
            tasks = [task for task in tasks if task["data_id"] not in exclude_data_ids]
        if not (exclude_biz_ids or exclude_app_prefixes):
            return tasks

        task_specs = PreCalculateTaskSpecProvider.list_task_specs(
            enabled_only=False,
            require_trace_enabled=False,
            require_metric_enabled=False,
            data_ids={task["data_id"] for task in tasks},
        )
        apps_mapping = {task_spec.data_id: task_spec.apps for task_spec in task_specs}

        def is_excluded_app(app):
            return app.bk_biz_id in exclude_biz_ids or app.app_name.startswith(exclude_app_prefixes)

        def display(data_id):
            return f"{data_id}({','.join(f'{app.bk_biz_id}:{app.app_name}' for app in apps_mapping.get(data_id, ()))})"

        kept, excluded, partial, unresolved = [], set(), set(), set()
        for task in tasks:
            apps = apps_mapping.get(task["data_id"], ())
            hit_count = sum(1 for app in apps if is_excluded_app(app))
            if apps and hit_count == len(apps):
                excluded.add(task["data_id"])
                continue
            if hit_count:
                partial.add(task["data_id"])
            if not apps:
                unresolved.add(task["data_id"])
            kept.append(task)

        print(f"按业务/应用名排除 {len(excluded)} 个 dataId: {[display(data_id) for data_id in sorted(excluded)]}")
        if partial:
            print(
                f"以下共享 dataId 只有部分应用命中，仍会恢复，如需排除请加到 --exclude-data-ids: "
                f"{[display(data_id) for data_id in sorted(partial)]}"
            )
        if unresolved:
            print(f"以下 dataId 查不到对应应用，仍会恢复: {sorted(unresolved)}")
        return kept

    @classmethod
    def print_task_spec_queue_mapping(cls, task_spec_queue_mapping, have_data_task_specs):
        for queue, task_specs in task_spec_queue_mapping.items():
            print(f"队列: {queue} 分配的任务: ")
            for item in task_specs:
                print(
                    f"   ----> DataId: {item.data_id} "
                    f"Shared: {item.is_shared} "
                    f"Apps: {[f'{app.bk_biz_id}:{app.app_name}' for app in item.apps]} "
                    f"{'有数据' if item in have_data_task_specs else '无数据'}"
                )
