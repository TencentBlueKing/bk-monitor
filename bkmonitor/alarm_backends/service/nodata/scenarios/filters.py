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

from alarm_backends.service.access.data.filters import RangeFilter

logger = logging.getLogger("nodata")


class DimensionRangeFilter(RangeFilter):
    def filter(self, dimensions, item):
        """
        无数据历史维度范围过滤，过滤掉，返回True
        """
        is_match = True
        # 1. 匹配监控条件(即where条件)
        agg_condition_obj = item.origin_agg_condition_obj
        if agg_condition_obj:
            is_match = is_match and agg_condition_obj.is_match(dimensions)

        # 2. 匹配额外的内置监控条件(针对磁盘、网络做的特殊处理)
        extra_agg_condition_obj = item.extra_agg_condition_obj
        if extra_agg_condition_obj:
            is_match = is_match and extra_agg_condition_obj.is_match(dimensions)

        is_filtered = not is_match
        if is_filtered:
            logger.debug(
                "[nodata] history dimensions({dimensions}) does not match condition({condition})".format(
                    dimensions=dimensions,
                    condition=item.query_configs[0].get("agg_condition"),
                )
            )

        return is_filtered
