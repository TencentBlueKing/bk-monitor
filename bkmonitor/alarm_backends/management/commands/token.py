# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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
        target_bk_biz_id = int(options.get("bk_biz_id") or 0)
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


def get_token_info(bk_biz_id=None):
    """
    获取策略令牌信息
    :param bk_biz_id: 可选业务ID，用于过滤策略
    :return: dict {strategy_id: {"token": int, "ttl": int, "table_id": str}}
    """
    result = {}
    strategies = []
    s_ids = StrategyCacheManager.get_strategy_ids()

    # 分块获取策略详情
    for chunked_s_ids in chunks(s_ids, 1000):
        chunked_strategy = StrategyCacheManager.get_strategy_by_ids(chunked_s_ids)
        strategies.extend(chunked_strategy)

    # 转换业务ID为整数类型
    target_bk_biz_id = int(bk_biz_id) if bk_biz_id else None

    for strategy in strategies:
        # 业务ID过滤
        strategy_biz_id = strategy.get("bk_biz_id")
        if not strategy_biz_id:
            continue
        strategy_biz_id = int(strategy_biz_id)
        if target_bk_biz_id and strategy_biz_id != target_bk_biz_id:
            continue

        # 获取查询MD5作为分组键
        group_key = next((item["query_md5"] for item in strategy["items"] if item.get("query_md5")), "")
        if not group_key:
            continue

        strategy_id = strategy["id"]
        token_manager = TokenBucket(group_key)

        # 获取令牌信息
        token_remain = token_manager.client.get(token_manager.token_key)
        if token_remain is None:
            continue

        token_remain = int(token_remain)
        ttl = token_manager.client.ttl(token_manager.token_key)

        # 处理TTL为None的情况
        if ttl is None:
            token_manager.client.expire(token_manager.token_key, 0)
            ttl = token_manager.client.ttl(token_manager.token_key)

        # 只记录令牌耗尽的策略
        if token_remain <= 0:
            try:
                table_id = strategy["items"][0]["query_configs"][0]["result_table_id"]
            except (KeyError, IndexError):
                table_id = "unknown"

            result[strategy_id] = {
                "token": token_remain,
                "ttl": ttl,
                "table_id": table_id,
                "bk_biz_id": strategy_biz_id,
                "strategy_name": strategy.get("name", ""),
            }

    return result
