# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import copy
import json
import logging
import typing
from dataclasses import asdict, dataclass, field

from core.drf_resource import api

logger = logging.getLogger("apm")


@dataclass
class ApiParamLimit:
    offset: int
    rows: int


@dataclass
class ApiParamOrder:
    expr: str
    sort: str = "asc"


@dataclass
class ApiParam:
    biz_id: str = ""
    app: str = ""
    type: str = ""
    start: int = ""
    end: int = ""
    label_filter: typing.Dict = field(default_factory=list)
    service_name: str = ""
    limit: ApiParamLimit = None
    order: ApiParamOrder = None

    def to_json(self):
        r = {
            "biz_id": self.biz_id,
            "app": self.app,
        }
        if self.type:
            r["type"] = self.type
        if self.label_filter:
            r["label_filter"] = self.label_filter
        if self.service_name:
            r["service_name"] = self.service_name
        if self.limit:
            r["limit"] = asdict(self.limit)
        if self.order:
            r["order"] = asdict(self.order)
        if self.start:
            r["start"] = self.start
        if self.end:
            r["end"] = self.end
        return r


class ProfileQueryBuilder:
    def __init__(self, _table_name, bk_biz_id, app_name):
        self.table_name = _table_name
        self.api_type = None
        self.api_params = ApiParam(biz_id=bk_biz_id, app=app_name)

    @classmethod
    def from_table(cls, table_name, bk_biz_id, app_name):
        return cls(table_name, bk_biz_id, app_name)

    def with_api_type(self, _type):
        if self.api_type:
            logger.warning(f"[ProfileQuery] api_type: {self.api_type} found, overwrite")
        self.api_type = _type
        return self

    def with_time(self, start, end):
        if len(str(start)) == 10:
            start = start * 1000
        if len(str(end)) == 10:
            end = end * 1000

        if self.api_params.start:
            logger.warning(f"[ProfileQuery] start_time: {self.api_params.start} found, overwrite")
        self.api_params.start = start
        if self.api_params.end:
            logger.warning(f"[ProfileQuery] end_time: {self.api_params.end} found, overwrite")
        self.api_params.end = end
        return self

    def with_type(self, _type):
        if self.api_params.type:
            logger.warning(f"[ProfileQuery] type: {self.api_params.type} found, overwrite")
        self.api_params.type = _type
        return self

    def with_filters(self, filters):
        if self.api_params.label_filter:
            logger.warning(f"[ProfileQuery] type: {self.api_params.type} found, overwrite")
        self.api_params.label_filter = filters
        return self

    def with_service_filter(self, service_name):
        if self.api_params.service_name:
            logger.warning(f"[ProfileQuery] service_name: {self.api_params.type} found, overwrite")
        self.api_params.service_name = service_name
        return self

    def with_offset_limit(self, offset, limit):
        if self.api_params.limit:
            logger.warning(f"[ProfileQuery] limit: {self.api_params.limit} found, overwrite")
        self.api_params.limit = ApiParamLimit(offset=offset, rows=limit)
        return self

    def copy(self):
        return copy.deepcopy(self)

    def execute(self):
        params = {
            "sql": json.dumps(
                {
                    "api_type": self.api_type,
                    "api_params": self.api_params.to_json(),
                    "result_table_id": self.table_name,
                }
            ),
            "prefer_storage": "doris",
            "_user_request": True,
        }
        logger.info(f"[ProfileQuery] origin_params: \n{json.dumps(params)}\n")
        response = api.bkdata.query_data(**params)
        return response.get("list", [])
