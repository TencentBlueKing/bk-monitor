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

from django.template import Context
from monitor_web.aiops.metric_recommend.constant import BIZ_FILTER_SQL_EXPR

logger = logging.getLogger("monitor_web")


def build_biz_filter_sql(source_rt_id, access_bk_biz_id):
    """构建用于进行业务过滤的指标推荐表的SQL.

    :param source_rt_id: 数据源结果表, 由算法同学统一构建，所有业务共用
    :param access_bk_biz_id: 需要接入指标推荐的业务ID
    """
    return BIZ_FILTER_SQL_EXPR.render(
        Context(
            {
                "source_rt_id": source_rt_id,
                "access_bk_biz_id": access_bk_biz_id,
            }
        )
    )
