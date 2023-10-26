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
from typing import Dict, Optional

from django.core.management.base import BaseCommand, CommandError

from metadata.models import DataSourceResultTable
from metadata.models.space.constants import SPACE_REDIS_KEY, SpaceTypes
from metadata.models.space.space_redis import SpaceRedis
from metadata.utils.redis_tools import RedisTools


class Command(BaseCommand):
    help = "check space data"

    def add_arguments(self, parser):
        parser.add_argument("--space_uid", type=str, help="space uid, example: bkcc__2")
        parser.add_argument("--bk_data_id", type=int, help="data source id")
        parser.add_argument("--table_id", type=str, help="result table id")
        # TODO: 如果后续有需要再添加参数
        # parser.add_argument("--from_redis", action='store_true', default=True)

    def handle(self, *args, **options):
        space_uid, bk_data_id, table_id = options["space_uid"], options["bk_data_id"], options["table_id"]

        # space uid 不能为空
        if not space_uid:
            raise CommandError("space_uid can not be empty")

        # 查询写入 redis 的数据和读取 redis 的数据
        print("------- set redis data -------")
        self._set_data_to_redis(space_uid, bk_data_id, table_id)
        print("------- from redis data -------")
        self._get_data_from_redis(space_uid, bk_data_id, table_id)

    def _get_table_id(self, bk_data_id: Optional[int] = None, table_id: Optional[str] = None) -> Optional[str]:
        if table_id is not None:
            return table_id
        if bk_data_id:
            qs = DataSourceResultTable.objects.filter(bk_data_id=bk_data_id)
            if not qs.exists():
                raise ValueError(f"table_id not found from bk_data_id: {bk_data_id}")
            return qs.first().table_id
        else:
            return None

    def _set_data_to_redis(
        self, space_uid: str, bk_data_id: Optional[int] = None, table_id: Optional[str] = None
    ) -> Dict:
        """获取写入redis的数据"""
        space_redis = SpaceRedis()
        field_value = {}
        # 拆分数据
        space_type_id, space_id = space_uid.split("__")
        # 查询bkcc的数据
        if space_type_id == SpaceTypes.BKCC.value:
            # 获取数据
            space_redis.get_data(space_type_id, space_id)
            field_value = space_redis.compose_biz_data(
                space_type_id,
                space_id,
                space_type_id,
                space_id,
            )
        else:
            # TODO: 其它类型，后续添加
            pass

        table_id = self._get_table_id(bk_data_id, table_id)
        if table_id:
            print(field_value.get(table_id))
        else:
            print(field_value)

    def _get_data_from_redis(self, space_uid: str, bk_data_id: Optional[int] = None, table_id: Optional[str] = None):
        """从redis中读取已有的数据"""
        table_id = self._get_table_id(bk_data_id, table_id)
        client = RedisTools().client
        key = f"{SPACE_REDIS_KEY}:{space_uid}"
        if table_id:
            print(client.hget(key, table_id))
        else:
            print(client.hgetall(key))
