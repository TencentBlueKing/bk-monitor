"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from blueapps.account.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    设置超级管理员
    使用示例
    python manage.py set_superuser user1 user2 user3 user4 ...
    """

    def add_arguments(self, parser):
        parser.add_argument("args", metavar="username", nargs="+", help="username to be set superuser")

    def handle(self, *usernames, **kwargs):
        for username in usernames:
            user, is_created = User.objects.update_or_create(
                username=username,
                defaults={
                    "is_superuser": True,
                    "is_staff": True,
                },
            )
            if is_created:
                print(f"User({user.username}) is created as superuser.")
            else:
                print(f"User({user.username}) is updated as superuser.")
