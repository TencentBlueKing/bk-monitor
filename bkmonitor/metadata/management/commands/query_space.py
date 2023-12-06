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
import json
from typing import Dict, List, Tuple

from django.core.management.base import BaseCommand
from django.db import models
from django.db.models import Q
from django.db.models.functions import Concat

from metadata.models import Space, SpaceDataSource, SpaceResource
from metadata.models.space.constants import SPACE_UID_HYPHEN
from metadata.models.space.utils import get_platform_data_id_list


class Command(BaseCommand):
    help = "query space detail"

    def add_arguments(self, parser):
        parser.add_argument("--space_uid", action="append", help="query space detail by uid")
        parser.add_argument("--id", action="append", help="query space detail by id(mysql id)")

    def handle(self, *args, **options):
        space_uid_list = options.get("space_uid")
        id_list = options.get("id")
        space_list = []
        if space_uid_list:
            space_list = self._query_by_space_uid_list(space_uid_list)
        if id_list:
            space_list.extend(self._query_by_id_list(id_list))
        if not space_list:
            self.stdout.write(json.dumps([]))
            return
        space_dict = {}
        for s in space_list:
            space_dict[(s["space_type_id"], s["space_id"])] = s
        # 获取关联数据
        space_data_source_dict, space_resource_dict = self._get_space_data(space_dict.keys())
        # 添加平台级 data id
        platform_data_id_list = get_platform_data_id_list()
        for key, val in space_dict.items():
            data_sources = space_data_source_dict.get(key, [])
            data_sources.extend(platform_data_id_list)
            val["data_sources"] = data_sources
            val["resources"] = space_resource_dict.get(key, [])

        self.stdout.write(json.dumps(space_dict.values()))

    def _check_space_uid_list(self, space_uid_list: List) -> bool:
        error_uid_list = []
        for suid in space_uid_list:
            if SPACE_UID_HYPHEN not in suid:
                error_uid_list.append(suid)
        if error_uid_list:
            self.stderr.write(f"space_uid:{','.join(error_uid_list)} format error, expect to contains `__`")

    def _query_by_space_uid_list(self, space_uid_list) -> List:
        # 使用 annotate 过滤数据
        space_list = (
            Space.objects.annotate(space_uid=Concat("space_type_id", models.Value(SPACE_UID_HYPHEN), "space_id"))
            .filter(space_uid__in=space_uid_list)
            .values("space_uid", "id", "space_type_id", "space_id", "status")
        )
        return list(space_list)

    def _query_by_id_list(self, id_list: List) -> Dict:
        space_list = (
            Space.objects.annotate(space_uid=Concat("space_type_id", models.Value(SPACE_UID_HYPHEN), "space_id"))
            .filter(id__in=id_list)
            .values("space_uid", "id", "space_type_id", "space_id", "status")
        )
        return list(space_list)

    def _get_space_data(self, space_uid_list: List) -> Tuple[Dict, Dict]:
        # 获取关联的 data id
        filter_q = Q()
        # space_uid_list 格式为 [(space_type_id, space_id), (space_type_id1, space_id1)]
        for s in space_uid_list:
            filter_q |= Q(space_type_id=s[0], space_id=s[1])
        space_data_source = SpaceDataSource.objects.filter(filter_q)
        space_data_source_dict = {}
        for sd in space_data_source:
            key = (sd.space_type_id, sd.space_id)
            if key in space_data_source_dict:
                space_data_source_dict[key].append(sd.bk_data_id)
            else:
                space_data_source_dict[key] = [sd.bk_data_id]
        # 获取对应的资源
        space_resource = SpaceResource.objects.filter(filter_q)
        space_resource_dict = {}
        for sr in space_resource:
            key = (sr.space_type_id, sr.space_id)
            resource = {
                "resource_type": sr.resource_type,
                "resource_id": sr.resource_id,
                "dimension_values": sr.dimension_values,
            }
            if key in space_resource_dict:
                space_resource_dict[key].append(resource)
            else:
                space_resource_dict[key] = [resource]
        return space_data_source_dict, space_resource_dict
