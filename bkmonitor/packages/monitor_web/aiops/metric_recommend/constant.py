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
from functools import partial

from django.conf import settings
from django.template import Template

METRIC_RECOMMAND_INPUT_MAPPINGS = {
    "metrics_json": "metrics_json",
    "series_time": "series_time",
    "bk_cloud_id": "bk_cloud_id",
    "ip": "ip",
    "bk_biz_id": "bk_biz_id",
}

METRIC_RECOMMAND_SCENE_SERVICE_TEMPLATE = partial(
    "{processing_id_prefix}_{bk_biz_id}".format,
    processing_id_prefix=settings.BK_DATA_METRIC_RECOMMEND_PROCESSING_ID_PREFIX,
)

BIZ_FILTER_SQL_EXPR = Template(
    "SELECT bk_biz_id, ip, bk_cloud_id, metrics_json, _startTime_ as series_time"
    " FROM {{source_rt_id}}"
    " WHERE bk_biz_id = '{{access_bk_biz_id}}'"
)
