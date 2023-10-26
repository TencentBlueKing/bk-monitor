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

from bkmonitor.data_source.backends.base.connection import BaseDatabaseConnection
from bkmonitor.documents import EventDocument

from .operations import DatabaseOperations

logger = logging.getLogger("bkmonitor.data_source.fta_event")


class DatabaseConnection(BaseDatabaseConnection):
    vendor = "es"
    prefer_storage = "es"

    def __init__(self, query_func):
        self.query_func = query_func
        self.ops = DatabaseOperations(self)

    def execute(self, rt_id, params):
        logger.info("FTA Event QUERY: rt_id is {}, query body is {}".format(rt_id, params))
        result = EventDocument.search(all_indices=True).update_from_dict(params).execute()
        return result.to_dict()
