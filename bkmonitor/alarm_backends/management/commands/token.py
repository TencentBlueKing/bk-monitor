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
from bkmonitor.utils.common_utils import chunks

"""
access模块令牌管理
"""
from django.core.management.base import BaseCommand

from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.service.access.data.token import TokenBucket


class Command(BaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument("--bk_biz_id", help="scan all strategies with token info with bk_biz_id")
        parser.add_argument(
            "--all",
            default=False,
            action="store_true",
            help="list all strategies with token info, default only list forbidden",
        )

    def handle(self, *args, **options):
        strategies = []
        s_ids = StrategyCacheManager.get_strategy_ids()
        for chunked_s_ids in chunks(s_ids, 1000):
            chunked_strategy = StrategyCacheManager.get_strategy_by_ids(chunked_s_ids)
            strategies.extend(chunked_strategy)
        target_bk_biz_id = int(options.get("bk_biz_id", 0))
        list_all = options.get("all")
        group_key_dict = {}
        print("id\ttoken\tttl\ttable_id")
        for strategy in strategies:
            bk_biz_id = strategy["bk_biz_id"]
            if not bk_biz_id:
                continue
            bk_biz_id = int(bk_biz_id)
            if target_bk_biz_id and bk_biz_id != target_bk_biz_id:
                continue

            group_key = ""
            for item in strategy["items"]:
                if item.get("query_md5"):
                    group_key = item["query_md5"]
                    break
            if group_key:
                strategy_id = strategy["id"]
                token_manager = TokenBucket(group_key)
                token_remain = token_manager.client.get(token_manager.token_key)
                if token_remain is None:
                    continue
                token_remain = int(token_remain)
                ttl = token_manager.client.ttl(token_manager.token_key)
                # token_remain = token_remain if ttl else 60
                if ttl is None:
                    token_manager.client.expire(token_manager.token_key, 0)
                    ttl = token_manager.client.ttl(token_manager.token_key)
                if list_all or token_remain <= 0:
                    info = [token_remain, 0]
                    if token_remain <= 0:
                        info = [token_remain, ttl]
                        try:
                            info.append(strategy["items"][0]["query_configs"][0]["result_table_id"])
                            group_key_dict[strategy_id] = info
                        except Exception:
                            print("error parse strategy: %s" % strategy_id)
                    print("\t".join(map(str, [strategy_id, *info])))
