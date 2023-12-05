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

from metadata.models import DataSource, Space


class Command(BaseCommand):
    def handle(self, *args, **options):
        space_uid = options["space_uid"]
        data_ids = options["data_ids"]

        if not data_ids:
            self.stdout.write("data_ids can not be empty")
            return
        if space_uid:
            space_type_id, space_id = space_uid.split("__")
            try:
                space = Space.objects.get(space_id=space_id, space_type_id=space_type_id)
            except Space.DoesNotExist:
                self.stdout.write("can not find space {}__{}".format(space_type_id, space_id))
                return
            DataSource.objects.filter(bk_data_id__in=data_ids).update(space_uid=space.space_uid)
        else:
            DataSource.objects.filter(bk_data_id__in=data_ids).update(space_uid="")

        self.stdout.write(f"data_id's space_uid modified to {space_uid}")

    def add_arguments(self, parser):
        parser.add_argument("--space_uid", type=str, required=False, default="", help="空间UID")
        parser.add_argument("--data_ids", type=int, nargs="*", required=True, help="要修改的DataID")
