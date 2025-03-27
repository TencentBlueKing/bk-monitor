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
from typing import Any, Dict, List, Set

from django.core.management.base import BaseCommand
from django.db.models import Value
from django_mysql.models import QuerySet

from metadata import models
from metadata.models import DataSource, EventGroup, ResultTable, ResultTableOption
from metadata.models.common import OptionBase
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis


class Command(BaseCommand):
    help = "sync event es router"

    PAGE_SIZE = 1000
    INNER_EVENT_GROUPS = [
        {"table_id": "gse_system_event", "event_group_name": "gse system event", "bk_data_id": 1000},
        {"table_id": "gse_custom_string", "event_group_name": "gse custom string", "bk_data_id": 1100000},
    ]

    def add_arguments(self, parser):
        parser.add_argument("-b", "--batch-size", type=str, help="同步批次大小")

    def handle(self, *args, **options):
        batch_size: int = int(options.get("batch_size") or 1000)
        queryset: QuerySet[models.EventGroup] = models.EventGroup.objects.filter(is_delete=False).order_by("bk_data_id")

        total: int = queryset.count()
        print(f"[sync_event_es_router] batch_size -> {batch_size}, total -> {total}")
        for begin_idx in range(0, total, batch_size):
            print(f"[sync_event_es_router] start to sync_event_es_route: begin_idx -> {begin_idx}")
            self.sync_event_es_route(
                list(queryset.values("table_id", "event_group_name", "bk_data_id")[begin_idx : begin_idx + batch_size])
            )

    @classmethod
    def sync_event_es_route(cls, event_groups: List[Dict[str, Any]], push_now: bool = True):
        table_event_group_map: Dict[str, Dict[str, Any]] = {
            event_group["table_id"]: event_group for event_group in event_groups + cls.INNER_EVENT_GROUPS
        }

        to_be_updated_storages: List[models.ESStorage] = []
        table_ids: List[str] = list(table_event_group_map.keys())
        platform_data_ids: Set[str] = set(
            DataSource.objects.filter(
                is_platform_data_id=Value(1), bk_data_id__in=[e["bk_data_id"] for e in table_event_group_map.values()]
            ).values_list("bk_data_id", flat=True)
        )
        for table_id in models.ESStorage.objects.filter(table_id__in=table_ids).values_list("table_id", flat=True):
            to_be_updated_storages.append(models.ESStorage(table_id=table_id, index_set=table_id))

        models.ESStorage.objects.bulk_update(to_be_updated_storages, fields=["index_set"])
        print(f"[sync_event_es_router] sync index_set to ESStorage: effect_rows -> {len(to_be_updated_storages)}")

        to_be_updated_rts: List[ResultTable] = []
        for table_id, event_group in table_event_group_map.items():
            event_group_name: str = event_group["event_group_name"]
            rt_obj: ResultTable = ResultTable(table_id=table_id, bk_biz_id_alias="", data_label="")

            if event_group["bk_data_id"] in platform_data_ids:
                rt_obj.bk_biz_id_alias = "dimensions.bk_biz_id"

            # k8s_event
            if event_group_name.startswith("bcs") and event_group_name.endswith("event"):
                rt_obj.data_label = "k8s_event"

            # system_event
            if table_id == "gse_system_event":
                rt_obj.data_label = "system_event"

            if rt_obj.data_label or rt_obj.bk_biz_id_alias:
                to_be_updated_rts.append(rt_obj)

        models.ResultTable.objects.bulk_update(to_be_updated_rts, fields=["bk_biz_id_alias", "data_label"])
        print(f"[sync_event_es_router] update rt -> {len(to_be_updated_rts)}")

        rt_option_map: Dict[str, Any] = {
            f'{_rt_option["table_id"]}-{_rt_option["name"]}': _rt_option
            for _rt_option in models.ResultTableOption.objects.filter(
                table_id__in=list(table_event_group_map.keys())
            ).values("id", "table_id", "name")
        }
        to_be_created_rt_options: List[ResultTableOption] = []
        to_be_updated_rt_options: List[ResultTableOption] = []
        for table_id in table_event_group_map:
            for option_name, option_value in EventGroup.DEFAULT_RESULT_TABLE_OPTIONS.items():
                value, value_type = OptionBase._parse_value(option_value)
                rt_option: ResultTableOption = ResultTableOption(
                    table_id=table_id, name=option_name, value=value, value_type=value_type
                )
                rt_option_key: str = f"{table_id}-{option_name}"
                if rt_option_key in rt_option_map:
                    rt_option.id = rt_option_map[rt_option_key]["id"]
                    to_be_updated_rt_options.append(rt_option)
                else:
                    to_be_created_rt_options.append(rt_option)

        models.ResultTableOption.objects.bulk_create(to_be_created_rt_options)
        models.ResultTableOption.objects.bulk_update(to_be_updated_rt_options, fields=["value_type", "value"])
        print(
            f"[sync_event_es_router] update_or_create rt options: "
            f"create -> {len(to_be_created_rt_options)}, update -> {len(to_be_updated_rt_options)}"
        )

        # cls._check(table_ids)

        if push_now:
            client = SpaceTableIDRedis()
            client.push_data_label_table_ids(list({rt_obj.data_label for rt_obj in to_be_updated_rts}))
            client.push_es_table_id_detail(table_id_list=table_ids, is_publish=True)

    @classmethod
    def _check(cls, table_ids: List[str]):
        for table_id in table_ids:
            s = models.ESStorage.objects.get(table_id=table_id)
            print(f"index_set -> {s.index_set}")
            for option in models.ResultTableOption.objects.filter(table_id=table_id):
                print(f"name -> {option.name}, value_type -> {option.value_type}, value -> {option.value}")
            print("------")
