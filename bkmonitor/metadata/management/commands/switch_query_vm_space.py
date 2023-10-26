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
import time
from typing import Dict, List

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from metadata.models.vm.constants import (
    QUERY_VM_SPACE_UID_CHANNEL_KEY,
    QUERY_VM_SPACE_UID_LIST_KEY,
)
from metadata.utils.redis_tools import RedisTools


class Command(BaseCommand):
    help = "add or delete space_uid for query vm whitelist"
    ACTION_LIST = ["add", "delete"]

    def add_arguments(self, parser):
        parser.add_argument("--action", type=str, help="action, add or delete")
        parser.add_argument("--space_uids", type=str, help="space_uid, format: bkcc__1;bkci__test, split by ';'")

    def _validate(self, options: Dict):
        """校验必须参数"""
        if options.get("action") not in self.ACTION_LIST:
            raise CommandError(f"action must be one of {';'.join(self.ACTION_LIST)}")
        if not options.get("space_uids"):
            raise CommandError("params: space_uids not null")

    def handle(self, *args, **options):
        # 校验参数
        self._validate(options)
        # 获取已有的数据
        exist_space_uid_list = getattr(settings, "QUERY_VM_SPACE_UID_LIST", [])
        # 操作
        action, space_uids = options["action"], options["space_uids"]
        # 输出要操作的空间
        self.stdout.write(f"{action} space uid: {space_uids}")
        space_uid_list = space_uids.split(";")

        diff_space_uid_list = []
        if action == "add":
            diff_space_uid_list = self._add(space_uid_list, exist_space_uid_list)
        else:
            diff_space_uid_list = self._delete(space_uid_list, exist_space_uid_list)

        # 更新 动态配置
        # NOTE: 因为不可能为空，所以，如果为空时，不更新配置
        if diff_space_uid_list:
            setattr(settings, "QUERY_VM_SPACE_UID_LIST", diff_space_uid_list)

        # 发布，通知到订阅方
        curr_time = {"time": time.time()}
        RedisTools.publish(QUERY_VM_SPACE_UID_CHANNEL_KEY, [json.dumps(curr_time)])

        self.stdout.write("operate done")

    def _add(self, space_uid_list: List, exist_space_uid_list: List) -> List:
        """添加空间数据"""
        try:
            RedisTools.sadd(QUERY_VM_SPACE_UID_LIST_KEY, space_uid_list)
            return list(set(exist_space_uid_list).union(set(space_uid_list)))
        except Exception as e:
            self.stderr.write(f"add space uid error, space_uid: {';'.join(space_uid_list)}, error: {e}")

    def _delete(self, space_uid_list: List, exist_space_uid_list: List) -> List:
        """删除空间数据"""
        try:
            RedisTools.srem(QUERY_VM_SPACE_UID_LIST_KEY, space_uid_list)
            return list(set(exist_space_uid_list) - set(space_uid_list))
        except Exception as e:
            self.stderr.write(f"delete space uid error, space_uid: {';'.join(space_uid_list)}, error: {e}")
