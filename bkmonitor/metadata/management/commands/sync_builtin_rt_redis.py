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
import json
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from bkmonitor.utils.cipher import transform_data_id_to_token
from metadata.models import ClusterInfo, DataSource, DataSourceResultTable, ResultTable
from metadata.utils.redis_tools import RedisTools


class Command(BaseCommand):
    help = "Sync built-in data to Redis and update the ResultTable model"

    redis_key = settings.BUILTIN_DATA_RT_REDIS_KEY

    def add_arguments(self, parser):
        parser.add_argument("--force", action='store_true', default=False, help="force sync redis data")

    def handle(self, *args, **options):
        """
        Sync built-in data to Redis and update ResultTable model
        """
        self.stdout.write("Start to sync built-in data to Redis and update ResultTable model")

        force_push = options.get("force")  # noqa 是否强制刷新，缺省参数

        # 根据对应的Key，查询Redis中的哈希表拉取数据
        redis_data = RedisTools.hgetall(self.redis_key)
        # 遍历Redis中的字段和值
        for field, value in redis_data.items():
            value_dict = json.loads(value)  # 获取对应的field与value
            key = field.decode('utf-8')  # 转码
            space_type, space_id = key.split('__')  # 分割出space_type和space_id
            # bkmonitor_{space_type}_{space_id}_built_in_time_series.__default__
            data_name = "bkmonitor_{}_{}_built_in_time_series".format(space_type, space_id)
            table_id = "bkmonitor_{}_{}_built_in_time_series.__default__".format(space_type, space_id)
            token = value_dict.get('token')
            modify_time = value_dict.get('modifyTime')  # noqa

            rt = ResultTable.objects.filter(table_id=table_id, is_builtin=True).first()

            if rt:
                if not token:  # 如果token为空，根据RT去查询对应的dataID
                    try:
                        dsrt = DataSourceResultTable.objects.get(table_id=table_id)  # 根据RT查询data_id
                        data_id = dsrt.bk_data_id
                        new_modify_time = str(int(time.time()))
                        generated_token = transform_data_id_to_token(
                            metric_data_id=data_id,
                            bk_biz_id=space_id if space_type == "bkcc" else 0,
                            app_name=data_name,
                        )
                        # 更新Redis中的dataID和modifyTime
                        value_dict['token'] = generated_token
                        value_dict['modifyTime'] = new_modify_time
                        RedisTools.hset_to_redis(self.redis_key, field, json.dumps(value_dict))

                    except DataSourceResultTable.DoesNotExist:
                        self.stdout.write(f"Error: No matching DataSourceResultTable found for table_id={table_id}")
            else:
                if not token:  # token
                    # 如果Redis中的field存在但dataID为空，在数据库中创建新的RT实例和dataID
                    # 创建数据源（返回data_id)=》创建RT
                    try:
                        ds = DataSource.create_data_source(
                            data_name=data_name,
                            operator="admin",
                            type_label="time_series",
                            source_label="bk_monitor",
                            etl_config="bk_standard_v2_time_series",
                            space_type_id=space_type,
                            space_uid=key,
                        )

                        new_rt = ResultTable.create_result_table(
                            bk_data_id=ds.bk_data_id,
                            table_id=table_id,
                            table_name_zh="内置可观测数据_{}".format(ds.bk_data_id),  #
                            is_builtin=True,
                            is_custom_table=True,
                            schema_type=ResultTable.SCHEMA_TYPE_FREE,
                            operator="admin",
                            default_storage=ClusterInfo.TYPE_INFLUXDB,
                        )

                        generated_token = transform_data_id_to_token(
                            metric_data_id=ds.bk_data_id,
                            bk_biz_id=space_id if space_type == "bkcc" else 0,
                            app_name=data_name,
                        )
                        # 更新Redis中的dataID和modifyTime
                        value_dict['token'] = generated_token
                        value_dict['modifyTime'] = new_rt.last_modify_time
                        RedisTools.hset_to_redis(self.redis_key, field, json.dumps(value_dict))

                    except Exception as e:
                        self.stdout.write(f"Error Occurs while creating new DS&RT instance, error: {e}")
                else:
                    # 如果Redis中的field存在且dataID不为空，但数据库中不存在对应的RT记录，打印错误日志
                    self.stdout.write(f"Error: Redis field {field} has dataID but no matching ResultTable found in DB")

        self.stdout.write("Sync built-in data to Redis and update ResultTable model successfully")
