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

from django.db.models.loading import get_models
from django.core.management.commands.test import Command as BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        unmanaged_models = [m for m in get_models() if not m._meta.managed]
        for m in unmanaged_models:
            m._meta.managed = True
        super(Command, self).handle(*args, **kwargs)
