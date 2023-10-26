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
from django.conf import settings
from django.core.cache import cache
from django.core.management import BaseCommand

from bkmonitor.middlewares.application_protection import ProtectionMiddleware, init


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--action",
            type=str,
            default="init",
        )
        parser.add_argument(
            "--rate",
            type=int,
            default=0,
        )
        parser.add_argument(
            "--user",
            type=str,
            default="",
        )

    def handle(self, **kwargs):
        if settings.ROLE != "api":
            print("try with: ./bin/api_manage.sh web_protection --rate=20")
            return
        action = kwargs["action"]
        if action == "init":
            rate = kwargs.pop("rate")
            if not rate:
                print("try with: ./bin/api_manage.sh web_protection --rate=20")
            init(rate)

        if action == "query":
            user = kwargs.pop("user")
            if not user:
                print("try with: ./bin/api_manage.sh web_protection --action=query --user=username")
            ttl = cache.ttl(f"{ProtectionMiddleware.cache_key_prefix}_{user}_slug")
            if ttl:
                print(f"{user} is forbidden for {ttl} seconds")
            else:
                print(f"ok!")

        if action == "stop":
            to_be_deleted = cache.keys(f"{ProtectionMiddleware.cache_key_prefix}*")
            ret = cache.delete_many(to_be_deleted)
            print(f"clear {ret} success")
