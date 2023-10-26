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

from bkmonitor.action.converter import ActionConverter


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "args", metavar="strategy_id", nargs="*", help="strategy to migrate, default for all strategies"
        )

    def handle(self, *strategy_ids, **kwargs):
        strategy_ids = [int(s_id) for s_id in strategy_ids[0].split(",") if s_id] if strategy_ids else None
        result = ActionConverter().migrate(strategy_ids)
        print("[ActionConverter] migrate result: %s" % result)
