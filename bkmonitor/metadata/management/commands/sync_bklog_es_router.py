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

import threading
from queue import Full, Queue
from typing import Dict, List, Set, Tuple

from django.core.management.base import BaseCommand
from django.db.transaction import atomic

from core.drf_resource import api
from metadata import config, models
from metadata.models.constants import (
    BULK_CREATE_BATCH_SIZE,
    BULK_UPDATE_BATCH_SIZE,
    EsSourceType,
)
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis


class Command(BaseCommand):
    help = "sync bklog es router"
    PAGE_SIZE = 1000
    DEFAULT_QUEUE_MAX_SIZE = 100000

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="强制刷新")

    def handle(self, *args, **options):
        if not self._can_refresh(options):
            self.stdout.write("data exists, skip refresh")
            return

        # 获取数据
        data_queue = self._list_es_router()
        if data_queue.empty():
            self.stdout.write("no data, skip refresh")
            return

        # 组装数据
        es_router_list = []
        while not data_queue.empty():
            _data = data_queue.get()
            es_router_list.extend(_data)

        # 批量创建或更新结果表及 es 存储
        update_space_set, update_rt_set, update_data_label_set = self._update_or_create_es_data(es_router_list)
        # 推送并发布
        self._push_and_publish(update_space_set, update_rt_set, update_data_label_set)

        self.stdout.write("sync bklog es router success")

    def _can_refresh(self, options):
        """判断是否可以刷新"""
        if options.get("force"):
            return True
        # 如果存在索引集的数据，则认为不需要拉取历史数据
        return not models.ESStorage.objects.exclude(index_set=None).exclude(index_set="").exists()

    def _list_es_router(self) -> Queue:
        # 拉取总数量
        try:
            data = api.log_search.list_es_router()
        except Exception as e:
            self.stderr.write(f"failed to list es router, err: {e}")
            return Queue()
        total = data.get("total") or 0
        # 如果数据为空，则直接返回
        if total == 0:
            return Queue()

        page_total = total // self.PAGE_SIZE if total % self.PAGE_SIZE == 0 else total // self.PAGE_SIZE + 1

        # 批量拉取接口数据
        threads = []
        data_queue = Queue(maxsize=self.DEFAULT_QUEUE_MAX_SIZE)
        for page in range(1, page_total + 1):
            t = threading.Thread(target=self._request_es_router, args=(page, data_queue))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        return data_queue

    def _request_es_router(self, page: int, data_queue: Queue):
        data = api.log_search.list_es_router(page=page, pagesize=self.PAGE_SIZE)
        es_router_list = data.get("list") or []
        try:
            data_queue.put(es_router_list)
        except Full:
            self.stderr.write("queue is full, please increase the queue size")
        except Exception as e:
            self.stderr.write(f"failed to put data into queue, err: {e}")

    def _get_biz_id_by_space(self, space_type_and_id: List) -> Dict:
        space_and_biz = {}
        for space in set(space_type_and_id):
            biz_id = models.Space.objects.get_biz_id_by_space(space_type=space[0], space_id=space[1])
            # 如果为 None， 则转换为 0
            space_and_biz[f"{space[0]}__{space[1]}"] = biz_id or 0
        return space_and_biz

    def _update_or_create_es_data(self, es_router_list: List) -> Tuple:
        tid_info, tid_list, space_type_and_id = {}, [], []
        for router in es_router_list:
            _table_id = router.get("table_id")
            if not _table_id:
                continue
            tid_info[_table_id] = router
            tid_list.append(_table_id)
            space_type_and_id.append(tuple(router["space_uid"].split("__")))

        # 过滤存在的结果表，然后更新别名和索引集
        exist_rt_objs = models.ResultTable.objects.filter(table_id__in=tid_list)
        exist_tid_list, updated_rt_objs = [], []
        for obj in exist_rt_objs:
            obj.data_label = tid_info[obj.table_id]["data_label"]
            updated_rt_objs.append(obj)
            exist_tid_list.append(obj.table_id)

        exist_objs = models.ESStorage.objects.filter(table_id__in=tid_list)
        # 批量更新数据集
        updated_objs = []
        for obj in exist_objs:
            obj.index_set = tid_info[obj.table_id]["index_set"]
            updated_objs.append(obj)

        try:
            with atomic(config.DATABASE_CONNECTION_NAME):
                models.ResultTable.objects.bulk_update(
                    updated_rt_objs, ["data_label"], batch_size=BULK_UPDATE_BATCH_SIZE
                )
                models.ESStorage.objects.bulk_update(updated_objs, ["index_set"], batch_size=BULK_UPDATE_BATCH_SIZE)
        except Exception as e:
            self.stderr.write(f"failed to update rt or es storage, err: {e}")
            return set(), set(), set()

        # 组装数据
        space_and_biz = self._get_biz_id_by_space(space_type_and_id)
        rt_obj_list, es_obj_list = [], []
        update_space_set, update_rt_set, update_data_label_set = set(), set(), set()
        need_add_option_objs, need_update_option_objs = [], []
        for tid, info in tid_info.items():
            # 针对所有
            update_rt_set.add(tid)
            update_data_label_set.add(info["data_label"])
            # 创建或更新 option
            if info.get("options"):
                (
                    _need_add_option_objs,
                    _need_update_option_objs,
                ) = self._compose_create_or_update_option_objs(tid, info["options"])
                # 更新
                if _need_add_option_objs:
                    need_add_option_objs.extend(_need_add_option_objs)
                # 创建
                if _need_update_option_objs:
                    need_update_option_objs.extend(_need_update_option_objs)
            # 批量创建或者更新option
            # 过滤已经存在或者数据为空的数据
            if tid in exist_tid_list or (
                not info.get("cluster_id") and info["source_type"] != EsSourceType.BKDATA.value
            ):
                continue
            # 记录需要更新的空间
            update_space_set.add(tuple(info["space_uid"].split("__")))
            # 组装结果表的数据
            rt_obj_list.append(
                models.ResultTable(
                    table_id=info["table_id"],
                    table_name_zh=info["table_id"],
                    is_custom_table=True,
                    default_storage=models.ClusterInfo.TYPE_ES,
                    creator="system",
                    bk_biz_id=space_and_biz.get(info["space_uid"], 0),
                    data_label=info["data_label"],
                )
            )
            es_obj_list.append(
                models.ESStorage(
                    table_id=info["table_id"],
                    storage_cluster_id=info["cluster_id"] or 0,  # 针对 bkdata 的 es 忽略集群
                    source_type=info["source_type"],
                    index_set=info["index_set"],
                    need_create_index=info["need_create_index"] or True,  # 区分是否需要创建索引
                )
            )
        # 批量创建结果表，批量创建 es 存储
        try:
            with atomic(config.DATABASE_CONNECTION_NAME):
                models.ResultTable.objects.bulk_create(rt_obj_list, batch_size=BULK_CREATE_BATCH_SIZE)
                models.ESStorage.objects.bulk_create(es_obj_list, batch_size=BULK_CREATE_BATCH_SIZE)
                models.ResultTableOption.objects.bulk_create(need_add_option_objs, batch_size=BULK_CREATE_BATCH_SIZE)
                models.ResultTableOption.objects.bulk_update(
                    need_update_option_objs, ["value", "value_type"], batch_size=BULK_UPDATE_BATCH_SIZE
                )
        except Exception as e:
            self.stderr.write(f"failed to create rt or es storage, err: {e}")

        return update_space_set, update_rt_set, update_data_label_set

    def _push_and_publish(self, update_space_set: Set, update_rt_set: Set, update_data_label_set: Set):
        """推送并发布"""
        client = SpaceTableIDRedis()
        # 如果为空时，则不需要进行路由更新
        if update_space_set:
            # 推送空间
            for space_type, space_id in update_space_set:
                client.push_space_table_ids(space_type, space_id, is_publish=True)
        # 推送标签
        if update_data_label_set:
            client.push_data_label_table_ids(list(update_data_label_set), is_publish=True)
        # 推送详情
        if update_rt_set:
            client.push_table_id_detail(is_publish=True, include_es_table_ids=True)

    def _compose_create_or_update_option_objs(self, table_id: str, options: List[Dict]) -> Tuple[List, List]:
        """创建或者更新结果表 option"""
        # 查询结果表下的option
        exist_objs = {obj.name: obj for obj in models.ResultTableOption.objects.filter(table_id=table_id)}
        need_update_objs, need_add_objs = [], []

        for option in options:
            exist_obj = exist_objs.get(option["name"])
            need_update = False
            if exist_obj:
                # 更新数据
                if option["value"] != exist_obj.value:
                    exist_obj.value = option["value"]
                    need_update = True
                if option["value_type"] != exist_obj.value_type:
                    exist_obj.value_type = option["value_type"]
                    need_update = True
                # 判断是否需要更新
                if need_update:
                    need_update_objs.append(exist_obj)
            else:
                need_add_objs.append(models.ResultTableOption(table_id=table_id, **dict(option)))

        return need_add_objs, need_update_objs
