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
import logging
import time

from django.conf import settings
from django.db import transaction

from alarm_backends.core.lock.service_lock import share_lock
from bkmonitor.utils.cipher import transform_data_id_to_token
from core.prometheus import metrics
from metadata.models import (
    ClusterInfo,
    DataSource,
    Label,
    ResultTable,
    Space,
    TimeSeriesGroup,
)
from metadata.models.space.constants import EtlConfigs
from metadata.tools.constants import TASK_FINISHED_SUCCESS, TASK_STARTED
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


@share_lock(ttl=3600, identify="metadata_sync_relation_redis_data")
def sync_relation_redis_data():
    """
    同步cmdb-relation内置数据
    """
    logger.info("sync_relation_redis_data started")
    start_time = time.time()
    # 统计&上报 任务状态指标
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_relation_redis_data", status=TASK_STARTED, process_target=None
    ).inc()
    # 获取对应的Redis数据
    redis_key = settings.BUILTIN_DATA_RT_REDIS_KEY
    redis_data = RedisTools.hgetall(redis_key)
    # 批量获取所有内置RT对象
    existing_rts = ResultTable.objects.filter(is_builtin=True)
    existing_rts_dict = {rt.table_id: rt for rt in existing_rts}
    for field, value in redis_data.items():
        try:
            # 将json解析放在try中，确保value是有效的JSON字符串
            value_dict = json.loads(value)
            if not isinstance(value_dict, dict):
                raise ValueError(
                    "sync_relation_redis_data: Value->[%s] of field->[%s] is not a valid dictionary", value, field
                )

        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                "sync_relation_redis_data: error occurred, field->[%s], error->[%s]. Using default value_dict.",
                field,
                e,
            )
            value_dict = {"token": None, "modifyTime": None}  # 预期中的默认字典

        # 解码并解析field
        key = field.decode('utf-8')
        space_type, space_id = key.split('__')

        # 转义业务ID，非业务类型ID为负数
        biz_id = space_id if space_type == "bkcc" else Space.objects.get_biz_id_by_space(space_type, space_id)
        data_name = f"{biz_id}_{space_type}_built_in_time_series"
        table_id = f"{biz_id}_{space_type}_built_in_time_series.__default__"  # table_id有限制，必须以业务ID数字开头
        token = value_dict.get('token')  # Redis缓存中的Token数据

        logger.info("sync_relation_redis_data start sync builtin redis data, field=%s", key)

        rt = existing_rts_dict.get(table_id)
        if rt:
            try:
                new_modify_time = str(int(time.time()))
                ds = DataSource.objects.get(data_name=data_name)
                generated_token = transform_data_id_to_token(
                    metric_data_id=ds.bk_data_id, bk_biz_id=biz_id, app_name=data_name
                )
                # 兼容历史问题，如果DB中存储的Token和生成的不一致，更新之
                if ds.token != generated_token:
                    logger.info(
                        "sync_relation_redis_data: data_id->[%s] ,token is not same,db_record->[%s],"
                        "generated_token->[%s]",
                        ds.bk_data_id,
                        ds.token,
                        generated_token,
                    )
                    ds.token = generated_token
                    ds.save()

                # 更新Redis中的数据
                value_dict['token'] = generated_token
                value_dict['modifyTime'] = new_modify_time
                RedisTools.hset_to_redis(redis_key, key, json.dumps(value_dict))
                logger.info(
                    "sync_relation_redis_data: Update Data For Field->[%s],has completed,value->[%s]", key, value_dict
                )
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "sync_relation_redis_data: update redis data failed, field->[%s], value->[%s],error->[" "%s]",
                    field,
                    value_dict,
                    e,
                )
                continue
        else:
            if not token:  # RT不存在，Token不存在场景 -> 创建新DS&RT -> 写入Redis
                try:
                    logger.info("sync_relation_redis_data: create builtin metadata for field->[%s]", key)
                    with transaction.atomic():
                        # field下对应RT不存在且Token不存在，创建新DS与RT,使用事务保证实例同时成功创建
                        ds = DataSource.create_data_source(
                            data_name=data_name,
                            operator="system",
                            type_label="time_series",
                            source_label="bk_monitor",
                            etl_config=EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value,
                            space_type_id=space_type,
                            space_uid=key,
                        )
                        new_rt = TimeSeriesGroup.create_time_series_group(
                            bk_data_id=ds.bk_data_id,
                            bk_biz_id=biz_id,
                            time_series_group_name=data_name,
                            label=Label.RESULT_TABLE_LABEL_OTHER,
                            operator="system",
                            table_id=table_id,
                            is_builtin=True,
                            default_storage_config={
                                ClusterInfo.TYPE_INFLUXDB,
                            },
                        )
                        generated_token = transform_data_id_to_token(
                            metric_data_id=ds.bk_data_id,
                            bk_biz_id=biz_id,
                            app_name=data_name,
                        )
                    ds.token = generated_token
                    ds.save()
                    # 更新Redis中的Token和modifyTime
                    value_dict['token'] = generated_token
                    value_dict['modifyTime'] = new_rt.last_modify_time
                    RedisTools.hset_to_redis(redis_key, key, json.dumps(value_dict))
                    logger.info(
                        "sync_relation_redis_data: Create Data For Field->[%s],has completed,value->[%s]",
                        key,
                        value_dict,
                    )
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning(
                        "sync_relation_redis_data: create builtin metadata failed, field->[%s], value->["
                        "%s],error->[%s]",
                        field,
                        value_dict,
                        e,
                    )
                    continue

    cost_time = time.time() - start_time
    metrics.METADATA_CRON_TASK_STATUS_TOTAL.labels(
        task_name="sync_relation_redis_data", status=TASK_FINISHED_SUCCESS, process_target=None
    ).inc()
    metrics.METADATA_CRON_TASK_COST_SECONDS.labels(task_name="sync_relation_redis_data", process_target=None).observe(
        cost_time
    )
    metrics.report_all()
    logger.info("sync_relation_redis_data finished successfully,use->[%s] seconds", cost_time)
