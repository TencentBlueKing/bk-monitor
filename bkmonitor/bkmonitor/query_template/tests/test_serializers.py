"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from blueapps.account import get_user_model
from django.core.management import BaseCommand

<<<<<<<< HEAD:bklog/apps/log_databus/management/commands/init_admin.py

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
========
from typing import Any

import pytest

from .. import serializers, mock_data


class TestSerializers:
    @pytest.mark.parametrize(
        "template", [mock_data.CALLEE_SUCCESS_RATE_QUERY_TEMPLATE, mock_data.CALLEE_P99_QUERY_TEMPLATE]
    )
    def test_query_template_serializers(self, template: dict[str, Any]):
        serializer = serializers.QueryTemplateSerializer(data=template)
        serializer.is_valid(raise_exception=True)
>>>>>>>> 957c9c1868eb754f38840f152c1b848a1bd07afd:bkmonitor/bkmonitor/query_template/tests/test_serializers.py
