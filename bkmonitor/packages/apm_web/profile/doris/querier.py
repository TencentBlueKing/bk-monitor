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
from typing import List, Optional

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
    # bkdata legacy type, may be removed in the future
    QUERY_SAMPLE = "query_sample"
    QUERY_SAMPLE_BY_JSON = "query_sample_by_json"
    COL_TYPE = "col_type"
    SERVICE_NAME = "service_name"
    SELECT_COUNT = "select_count"


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

    def get_sample_info(
        self, start: int, end: int, data_types: List[str], service_name: str, label_filter: dict = None
    ):
        """查询样本基本信息"""
        label_filter = label_filter or {}

        res = {}
        for data_type in data_types:
            info = Query(
                api_type=APIType.QUERY_SAMPLE_BY_JSON,
                api_params=APIParams(
                    biz_id=self.bk_biz_id,
                    app=self.app_name,
                    type=data_type,
                    start=start,
                    end=end,
                    service_name=service_name,
                    limit={"offset": 0, "rows": 1},
                    order={"expr": "dtEventTimeStamp", "sort": "desc"},
                    label_filter=label_filter,
                ),
                result_table_id=self.result_table_id,
            ).execute()

            if not info or not info.get("list", []):
                continue

            ts = info["list"][0].get("dtEventTimeStamp")
            if not ts:
                continue

            res[data_type] = {"last_report_time": ts}

        return res

    def exist_data(self, start: int, end: int) -> bool:
        """查询 Profile 是否有数据上报"""
        res = Query(
            api_type=APIType.SELECT_COUNT,
            api_params=APIParams(
                biz_id=self.bk_biz_id,
                app=self.app_name,
                start=start,
                end=end,
                limit={"offset": 0, "rows": 1},
            ),
            result_table_id=self.result_table_id,
        ).execute()
        if not res or not res.get("list", []):
            return False
        count = next((i["count(1)"] for i in res["list"] if i.get("count(1)")), None)
        return bool(count)

    def list_services_request_info(self, start: int, end: int):
        """
        获取此应用下各个服务的数据上报信息
        eg.
        {
            "serviceA": {
                "profiling_data_count": 888,
            },
        }
        """

        # Step1: 获取已发现的所有 Services
        profile_services = api.apm_api.query_profile_services_detail(
            **{"bk_biz_id": self.bk_biz_id, "app_name": self.app_name}
        )

        services = list({i["name"] for i in profile_services})
        if not services:
            return {}
        res = {}
        for svr in services:
            res.update(self.get_service_request_info(start, end, svr))

        return res

    def get_service_request_info(self, start: int, end: int, service_name: str):
        """
        获取 service 的请求信息
        信息包含:
        1. profiling_data_count 上报数据量
        """
        count_response = Query(
            api_type=APIType.SELECT_COUNT,
            api_params=APIParams(
                biz_id=self.bk_biz_id, app=self.app_name, start=start, end=end, service_name=service_name
            ),
            result_table_id=self.result_table_id,
        ).execute()

        if not count_response:
            return {}

        # 计算平台 select_count 时, 固定的列名称为 count(1) . 所以这里这样写
        count = next((i["count(1)"] for i in count_response.get("list", []) if i.get("count(1)")), None)

        return {service_name: {"profiling_data_count": count}} if count else {}

    def get_count(
        self, start_time: int, end_time: int, data_type: str, service_name: str = None, label_filter: dict = None
    ):
        """根据查询条件获取数据条数"""
        label_filter = label_filter or {}
        res = Query(
            api_type=APIType.SELECT_COUNT,
            api_params=APIParams(
                start=start_time,
                end=end_time,
                biz_id=self.bk_biz_id,
                app=self.app_name,
                type=data_type,
                label_filter=label_filter,
                service_name=service_name,
            ),
            result_table_id=self.result_table_id,
        ).execute()
        if not res or not res.get("list", []):
            return None

        return res["list"][0].get("count(1)", None)

    def list_labels(
        self,
        start_time: int,
        end_time: int,
        data_type: str,
        service_name: str = None,
        label_filter: dict = None,
        limit: int = None,
    ):
        """根据查询条件获取 labels 列表"""

        # todo 待 bkbase 支持 distinct 查询
        label_filter = label_filter or {}
        res = Query(
            api_type=APIType.LABELS,
            api_params=APIParams(
                start=start_time,
                end=end_time,
                biz_id=self.bk_biz_id,
                app=self.app_name,
                type=data_type,
                label_filter=label_filter,
                service_name=service_name,
                limit={"rows": limit} if limit else None,
            ),
            result_table_id=self.result_table_id,
        ).execute()

        if not res or not res.get("list", []):
            return None

        return res["list"]

    def parse_labels(self, *args, **kwargs):
        """获取 labels 后，进行解析并返回"""
        labels = self.list_labels(*args, **kwargs)
        if not labels:
            return []

        return [{"time": i["dtEventTimeStamp"], "labels": json.loads(i["labels"])} for i in labels]
