"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests
from django.conf import settings

from api.bkdata.default import QueryDataResource

logger = logging.getLogger(__name__)


class APIType(Enum):
    LABELS = "labels"
    LABEL_VALUES = "label_values"
    QUERY_SAMPLE = "query_sample"


@dataclass
class APIParams:
    biz_id: str
    app: str
    type: str
    start: int
    end: int

    label_key: Optional[str] = None
    label_filter: Optional[dict] = None

    def to_dict(self):
        r = {
            "biz_id": self.biz_id,
            "app": self.app,
            "type": self.type,
            "start": self.start,
            "end": self.end,
        }
        if self.label_key:
            r["label_key"] = self.label_key
        if self.label_filter:
            r["label_filter"] = self.label_filter

        return r


@dataclass
class Query:
    api_type: APIType
    api_params: APIParams
    result_table_id: str

    def to_dict(self):
        r = {
            "api_type": self.api_type.value,
            "api_params": self.api_params.to_dict(),
            "result_table_id": self.result_table_id,
        }
        return r

    def execute(self) -> Optional[dict]:
        # bkData need a raw string with double quotes
        sql = json.dumps(self.to_dict())
        logger.debug("[ProfileDatasource] query_data params: %s", sql)

        # TODO: api.bkdata.query_data is not working on making sql valid, fix it.
        try:
            res = requests.post(
                url=f"{QueryDataResource.base_url}{QueryDataResource.action}",
                json={
                    "sql": sql,
                    "bk_app_code": settings.APP_CODE,
                    "bk_app_secret": settings.SECRET_KEY,
                    "prefer_storage": "doris",
                    "bk_username": settings.COMMON_USERNAME,
                    "bkdata_authentication_method": "user",
                },
                headers={"Content-Type": "application/json"},
            ).json()
        except Exception:  # pylint: disable=broad-except
            logger.exception("query bkdata doris failed")
            return None

        if not res["result"]:
            logger.error("query bkdata doris failed: %s", res["message"])
            return None

        return res["data"]
