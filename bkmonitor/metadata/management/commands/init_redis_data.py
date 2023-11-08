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

from metadata.models.space import Space
from metadata.models.space.constants import (
    SPACE_CHANNEL,
    SPACE_REDIS_KEY,
    SPACE_UID_HYPHEN,
    SpaceTypes,
)
from metadata.models.space.space_redis import push_redis_data
from metadata.task.sync_space import push_and_publish_space_router
from metadata.utils.redis_tools import RedisTools


class Command(BaseCommand):
    help = "init space data to redis"
    space_redis_key = SPACE_REDIS_KEY
    bkcc_type_id = SpaceTypes.BKCC.value
    bcs_type_id = SpaceTypes.BCS.value

    def add_arguments(self, parser):
        parser.add_argument("--force", action='store_true', default=False, help="force push redis data")
        parser.add_argument(
            "--push_pre_version", action='store_true', default=False, help="include pre-version redis data struct"
        )

    def handle(self, *args, **options):
        """
        NOTE: 因为后续 redis 的 hmset 会被废弃，因此，这里直接使用 hset 直接推送数据
        """
        self.stdout.write("start to push space to redis")

        force_push = options.get("force")
        # 判断redis中是否存在数据，如果存在，则直接返回
        if not force_push and RedisTools.is_member_exist(self.space_redis_key):
            print("space data has pushed to redis")
            return

        # 推送数据
        push_and_publish_space_router()

        # 推送历史版本的数据结构
        if options.get("push_pre_version"):
            try:
                self._push_pre_version_data()
            except Exception as e:
                self.stderr.write("push pre-version data error，error: %s", e)

        self.stdout.write("push space to redis successfully")

    def _push_pre_version_data(self):
        """推送先前版本的数据"""
        self.stdout.write("start to push pre-version data to redis")

        spaces = Space.objects.all().values("space_type_id", "space_id")
        # 推送空间数据，格式: key: bkmonitorv3:spaces value: space_type_id__space_id
        space_uid_list = []
        for s in spaces:
            if s["space_type_id"] not in [self.bcs_type_id, self.bkcc_type_id]:
                continue
            space_uid_list.append(f"{s['space_type_id']}{SPACE_UID_HYPHEN}{s['space_id']}")
        RedisTools.sadd(self.space_redis_key, space_uid_list)

        # 推送业务相关空间
        for s in spaces:
            push_redis_data(s["space_type_id"], s["space_id"])
        # NOTE: 为防止变动更新没有通知到unify-query, 增加一次空间发布
        RedisTools.publish(SPACE_CHANNEL, space_uid_list)

        self.stdout.write("push pre-version data successfully")
