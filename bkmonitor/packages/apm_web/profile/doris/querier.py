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
from django.utils.translation import ugettext_lazy as _

from api.bkdata.default import QueryDataResource
from apm_web.models import Application
from core.drf_resource import api

logger = logging.getLogger(__name__)


class APIType(Enum):
    LABELS = "labels"
    LABEL_VALUES = "label_values"
    QUERY_SAMPLE = "query_sample"
    COL_TYPE = "col_type"
    SERVICE_NAME = "service_name"


@dataclass
class APIParams:
    biz_id: str
    app: str

    service_name: Optional[str] = None
    start: int = None
    end: int = None
    type: Optional[str] = None
    label_key: Optional[str] = None
    label_filter: Optional[dict] = None
    limit: dict = None
    order: dict = None

    def to_dict(self):
        r = {
            "biz_id": self.biz_id,
            "app": self.app,
            "start": self.start,
            "end": self.end,
        }
        if self.type:
            r["type"] = self.type
        if self.label_key:
            r["label_key"] = self.label_key
        if self.label_filter:
            r["label_filter"] = self.label_filter
        if self.limit:
            r["limit"] = self.limit
        if self.order:
            r["order"] = self.order
        if self.service_name:
            r["service_name"] = self.service_name
        if self.start:
            r["start"] = self.start
        if self.end:
            r["end"] = self.end
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


class QueryTemplate:
    def __init__(self, bk_biz_id, app_name):
        try:
            application_id = Application.objects.get(app_name=app_name, bk_biz_id=bk_biz_id).pk
        except Exception:  # pylint: disable=broad-except
            raise ValueError(_("应用({}) 不存在").format(app_name))

        try:
            application_info = api.apm_api.detail_application({"application_id": application_id})
        except Exception:  # pylint: disable=broad-except
            raise ValueError(_("应用({}.{}) 不存在").format(bk_biz_id, app_name))

        if "profiling_config" not in application_info:
            raise ValueError(_("应用({}.{}) 未开启性能分析").format(bk_biz_id, app_name))

        self.result_table_id = application_info["profiling_config"]["result_table_id"]
        self.bk_biz_id = bk_biz_id
        self.app_name = app_name

    def get_sample_info(self, start, end, _type, label_filter=None):
        """查询样本基本信息"""
        if not label_filter:
            label_filter = {}

        res = Query(
            api_type=APIType.QUERY_SAMPLE,
            api_params=APIParams(
                biz_id=self.bk_biz_id,
                app=self.app_name,
                type=_type,
                start=start,
                end=end,
                limit={"offset": 0, "rows": 1},
                order={"expr": "time", "sort": "desc"},
                **label_filter,
            ),
            result_table_id=self.result_table_id,
        ).execute()
        if not res:
            return None

        data_list = res.get("list", [])
        if not data_list:
            return None

        return {"last_report_time": data_list[0].get("timestamp")}

    def exist_data(self, start, end) -> bool:
        """查询 Profile 是否有数据上报"""
        # 如果有时间内有查询到存在任何一个 type 即代表有数据上报
        res = Query(
            api_type=APIType.QUERY_SAMPLE,
            api_params=APIParams(
                biz_id=self.bk_biz_id,
                app=self.app_name,
                start=start,
                end=end,
                limit={"offset": 0, "rows": 1},
            ),
            result_table_id=self.result_table_id,
        ).execute()
        if not res:
            return False

        return bool(res.get("list", []))

    def list_services_request_info(self, start, end):
        """获取此应用下各个服务的数据上报信息"""

        # Step1: 获取所有 Services
        services_response = Query(
            api_type=APIType.SERVICE_NAME,
            api_params=APIParams(
                biz_id=self.bk_biz_id,
                app=self.app_name,
            ),
            result_table_id=self.result_table_id,
        ).execute()
        if not services_response:
            return {}

        services = [i.get("service_name") for i in services_response.get("list", []) if i.get("service_name")]
        if not services:
            return {}
        res = {}
        for svr in services:
            res.update(self.get_service_request_info(start, end, svr))

        return res

    def get_service_request_info(self, start, end, service_name):
        # TODO 补充逻辑 目前 bkbase 还没有提供查询数据量的接口 eg. {"serviceA": {"profiling_data_count": 1000}}
        return {service_name: {"profiling_data_count": 0}}
