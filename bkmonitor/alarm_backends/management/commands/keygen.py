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
"""
生产RSA公钥秘钥队，并保存公钥，打印私钥。
"""

from Crypto.PublicKey import RSA
from django.conf import settings

from django.core.management.base import BaseCommand


def gen_key():
    key = RSA.generate(2048)
    pri_key = key.exportKey()
    return pri_key


def do_keygen():
    settings.RSA_PRIVATE_KEY = gen_key()
    print(f"{settings.RSA_PRIVATE_KEY}")


class Command(BaseCommand):
    help = "RSA KEY MANAGER"

    def handle(self, *args, **options):
        if settings.RSA_PRIVATE_KEY:
            print(f"{settings.RSA_PRIVATE_KEY}")
        else:
            do_keygen()
