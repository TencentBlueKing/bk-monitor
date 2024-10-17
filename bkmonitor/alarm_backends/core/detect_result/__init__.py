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

from alarm_backends.constants import (
    LATEST_NO_DATA_CHECK_POINT,
    LATEST_POINT_WITH_ALL_KEY,
)
from alarm_backends.core.cache import key

CONST_MAX_LEN_CHECK_RESULT = 30  # 检测结果缓存，默认只保留30条数据

ANOMALY_LABEL = "ANOMALY"  # 异常标识


class Result(object):
    _pipeline = None

    def __init__(
        self,
        strategy_id=None,
        item_id=None,
        dimensions_md5=None,
        level=None,
        check_result_cache_key=None,
        service_type="detect",
    ):
        if check_result_cache_key:
            _, strategy_id, item_id, dimensions_md5, level = check_result_cache_key.rsplit(".", 4)

        assert all([strategy_id, item_id, dimensions_md5, level])

        self.service_type = service_type
        self.strategy_id = strategy_id
        self.item_id = item_id
        self.dimensions_md5 = dimensions_md5
        self.level = level

        self.CHECK_RESULT = self.pipeline()

    @classmethod
    def pipeline(cls):
        pass


class CheckResult(Result):
    def __init__(self, *args, **kwargs):
        super(CheckResult, self).__init__(*args, **kwargs)

    @classmethod
    def pipeline(cls):
        """
        外部可直接使用pipeline对象，同时对象内部也使用相同的pipeline对象
        >>>redis_pipeline = CheckResult.pipeline()
        >>>assert redis_pipeline is CheckResult(
        ...    strategy_id=1, item_id=2, dimensions_md5="md5_str", level="1").CHECK_RESULT
        """
        if cls._pipeline is None:
            cls._pipeline = key.CHECK_RESULT_CACHE_KEY.client.pipeline(transaction=False)
        return cls._pipeline

    @property
    def check_result_cache_key(self):
        return key.CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=self.strategy_id, item_id=self.item_id, dimensions_md5=self.dimensions_md5, level=self.level
        )

    @property
    def last_check_point_field(self):
        return key.LAST_CHECKPOINTS_CACHE_KEY.get_field(dimensions_md5=self.dimensions_md5, level=self.level)

    @property
    def latest_point_with_all_field(self):
        return key.LAST_CHECKPOINTS_CACHE_KEY.get_field(dimensions_md5=LATEST_POINT_WITH_ALL_KEY, level=self.level)

    @property
    def latest_no_data_check_point_field(self):
        return key.LAST_CHECKPOINTS_CACHE_KEY.get_field(dimensions_md5=LATEST_NO_DATA_CHECK_POINT, level=self.level)

    @property
    def md5_to_dimension_key(self):
        return self.get_md5_to_dimension_key(self.service_type, self.strategy_id, self.item_id)

    @staticmethod
    def get_md5_to_dimension_key(service_type: str, strategy_id: int, item_id: int):
        return key.MD5_TO_DIMENSION_CACHE_KEY.get_key(
            service_type=service_type,
            strategy_id=strategy_id,
            item_id=item_id,
        )

    # ----- Func of check_result_cache ----- #
    def add_check_result_cache(self, **kwargs):
        """Add check result cache"""

        ret = self.CHECK_RESULT.zadd(self.check_result_cache_key, kwargs)
        if ret:
            self.CHECK_RESULT.expire(self.check_result_cache_key, key.CHECK_RESULT_CACHE_KEY.ttl)
        return ret

    def remove_old_check_result_cache(self, point_remains=0):
        point_remains = point_remains or 0
        return self.CHECK_RESULT.zremrangebyrank(
            self.check_result_cache_key, 0, -point_remains or -CONST_MAX_LEN_CHECK_RESULT
        )

    def remove_expired_check_result_cache(self, expired_timestamp):
        return self.CHECK_RESULT.zremrangebyscore(self.check_result_cache_key, 0, expired_timestamp)

    # ----- Func of last_check_point   ----- #
    @staticmethod
    def update_last_checkpoint_by_d_md5(strategy_id, item_id, dimensions_md5, check_point, level):
        """Update last check point by dimensions md5"""
        detect_service = key.LAST_CHECKPOINTS_CACHE_KEY.client
        last_checkpoint_cache_field = key.LAST_CHECKPOINTS_CACHE_KEY.get_field(
            dimensions_md5=dimensions_md5,
            level=level,
        )
        last_checkpoint_cache_key = key.LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=strategy_id, item_id=item_id)
        detect_service.hset(last_checkpoint_cache_key, last_checkpoint_cache_field, check_point)
        return check_point

    @staticmethod
    def expire_last_checkpoint_cache(strategy_id, item_id):
        key.LAST_CHECKPOINTS_CACHE_KEY.expire(strategy_id=strategy_id, item_id=item_id)

    # ----- Func of dimension ----- #
    def update_key_to_dimension(self, dimensions):
        # nodata 逻辑
        self.CHECK_RESULT.hset(self.md5_to_dimension_key, self.dimensions_md5, json.dumps(dimensions))

    def expire_key_to_dimension(self):
        # nodata 逻辑
        self.CHECK_RESULT.expire(self.md5_to_dimension_key, key.MD5_TO_DIMENSION_CACHE_KEY.ttl)

    @classmethod
    def get_dimension_by_key(cls, service_type: str, strategy_id: int, item_id: int, dimensions_md5: str):
        # nodata 逻辑
        cache_key = cls.get_md5_to_dimension_key(service_type, strategy_id, item_id)
        dimension_data = key.MD5_TO_DIMENSION_CACHE_KEY.client.hget(cache_key, dimensions_md5)
        if dimension_data:
            return json.loads(dimension_data)

        return None

    @classmethod
    def remove_dimension_by_key(cls, service_type: str, strategy_id: int, item_id: int, dimensions_md5: str):
        # nodata 逻辑
        cache_key = cls.get_md5_to_dimension_key(service_type, strategy_id, item_id)
        key.MD5_TO_DIMENSION_CACHE_KEY.client.hdel(cache_key, dimensions_md5)

    @classmethod
    def get_dimensions_keys(cls, service_type, strategy_id, item_id):
        # nodata 逻辑
        cache_key = cls.get_md5_to_dimension_key(service_type, strategy_id, item_id)
        return key.MD5_TO_DIMENSION_CACHE_KEY.client.hkeys(cache_key)
