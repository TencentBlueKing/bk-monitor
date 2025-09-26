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
from blueapps.account import get_user_model
from django.core.management import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, help="admin user name")

    def handle(self, **options):
        try:
            username = options.get("username")
            user = get_user_model()
            user.objects.filter(username=username).update(is_superuser=True, is_staff=True)
            print("[Init Admin Auth] operate SUCCESS!")
        except Exception as e:
            print(f"[Init Admin Auth] operate FAILED! details: {str(e)}")
