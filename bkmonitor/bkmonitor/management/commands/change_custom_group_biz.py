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
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from metadata.models import (
    DataSource,
    ResultTable,
    Space,
    SpaceDataSource,
    TimeSeriesGroup,
)
from monitor_web.models import CustomTSTable

logger = logging.getLogger("metadata")


class Command(BaseCommand):
    def handle(self, *args, **options):
        if settings.ROLE != "api":
            print("try with: ./bin/api_manage.sh change_custom_group_biz --arguments")
            return
        group_name = options["group_name"]
        bk_biz_id = options["bk_biz_id"]
        is_platform = options["is_platform"]
        # 更新 time_series_group 业务信息
        try:
            ts_group = TimeSeriesGroup.objects.get(time_series_group_name=group_name)
        except TimeSeriesGroup.DoesNotExist:
            self.stdout.write(f"can not find time_series_group, group name:{group_name}")
            return
        if is_platform == "true":
            input_bk_biz_id = 0
            is_platform_flag = True
        else:
            input_bk_biz_id = bk_biz_id
            is_platform_flag = False
        ts_group.bk_biz_id = input_bk_biz_id
        ts_group.save()
        # 更新 result_table 业务信息
        rt = ResultTable.objects.get(table_id=ts_group.table_id)
        rt.bk_biz_id = input_bk_biz_id
        rt.save()

        # 更新 custom ts table 业务信息
        ct = CustomTSTable.objects.get(time_series_group_id=ts_group.time_series_group_id)
        ct.bk_biz_id = bk_biz_id
        ct.is_platform = is_platform_flag
        ct.save()

        ds = DataSource.objects.get(bk_data_id=ts_group.bk_data_id)
        origin_space_uid = ds.space_uid
        biz_change = False
        if origin_space_uid != f"bkcc__{bk_biz_id}":
            biz_change = True
        if biz_change or ds.is_platform_data_id != is_platform_flag:
            # 更新 datasource
            ds.update_config(operator="admin", space_uid=f"bkcc__{bk_biz_id}", is_platform_data_id=is_platform_flag)

        if biz_change:
            try:
                origin_bk_biz_id = origin_space_uid.split("__", -1)[-1]
                space_ds = SpaceDataSource.objects.get(bk_data_id=ds.bk_data_id, space_id=origin_bk_biz_id)
                if SpaceDataSource.objects.filter(bk_data_id=ds.bk_data_id, space_id=bk_biz_id).exists():
                    space_ds.delete()
                else:
                    space_ds.space_id = bk_biz_id
                    space_ds.save()
                self.stdout.write(f"update spacedatasource space_id [{origin_bk_biz_id}]->[{bk_biz_id}] success")
            except SpaceDataSource.DoesNotExist:
                self.stdout.write(
                    f"spacedatasource does not exist, bk data id: {ds.bk_data_id} space id: {origin_bk_biz_id}"
                )
                SpaceDataSource.objects.create(bk_data_id=ds.bk_data_id, space_id=bk_biz_id)
            except Exception as e:
                self.stdout.write(f"update spacedatasource occur error: {e}")
                return
            finally:
                from metadata.task.sync_space import push_and_publish_space_router

                if Space.objects.filter(space_id=bk_biz_id).exists():
                    push_and_publish_space_router(space_id=bk_biz_id)

    def add_arguments(self, parser):
        parser.add_argument("--group_name", type=str, required=True, help="时序分组名")
        parser.add_argument("--bk_biz_id", type=int, required=True, help="业务 ID")
        parser.add_argument("--is_platform", type=str, required=True, help="是否是平台级")
