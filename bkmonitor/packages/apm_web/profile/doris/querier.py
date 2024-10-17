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

from django.utils.translation import ugettext_lazy as _
from opentelemetry import trace

from apm_web.models import Application
from core.drf_resource import api
from core.errors.api import BKAPIError

logger = logging.getLogger(__name__)

tracer = trace.get_tracer(__name__)


class APIType(Enum):
    LABELS = "labels"
    LABEL_VALUES = "label_values"
    # bkdata legacy type, may be removed in the future
    QUERY_SAMPLE = "query_sample"
    QUERY_SAMPLE_BY_JSON = "query_sample_by_json"
    COL_TYPE = "col_type"
    SERVICE_NAME = "service_name"
    SELECT_COUNT = "select_aggregate"


class ConverterType:
    """Bkbase 原始 profile 可以转换的数据类型"""

    # Profile 类型使用 DorisConverter 转换
    Profile = "profile"
    # Tree 类型使用 TreeConverter
    Tree = "tree"


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
    # dimension_fields: 仅在 select_count / query_sample_by_json 接口生效
    dimension_fields: str = None
    # general_filters:  仅在 select_count / query_sample_by_json 接口生效
    general_filters: Optional[dict] = None
    # metric_fields:  仅在 select_count / query_sample_by_json 接口生效
    metric_fields: str = None

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
        if self.dimension_fields:
            r["dimension_fields"] = self.dimension_fields
        if self.general_filters:
            r["general_filters"] = self.general_filters
        if self.metric_fields:
            r["metric_fields"] = self.metric_fields
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

    def execute(self, retry_if_empty_handler=None) -> Optional[dict]:
        res = self._execute()

        if (not res or not res.get("list")) and retry_if_empty_handler:
            retry_if_empty_handler(self.api_params)
            res = self._execute()

        return res

    def _execute(self):
        # bkData need a raw string with double quotes
        sql = json.dumps(self.to_dict())
        logger.info("[ProfileDatasource] query_data params: %s", sql)

        try:
            params = {
                "sql": sql,
                "prefer_storage": "doris",
                "_user_request": True,
            }
            return api.bkdata.query_data(**params)
        except BKAPIError as e:
            logger.exception(f"query bkdata doris failed, error: {e}")

        return None


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

    def get_sample_info(self, start: int, end: int, sample_type: str, service_name: str, label_filter: dict = None):
        """根据 sample_type 查询最新的数据时间（最近上报时间）"""
        label_filter = label_filter or {}

        if not sample_type:
            return None

        info = Query(
            api_type=APIType.QUERY_SAMPLE_BY_JSON,
            api_params=APIParams(
                biz_id=self.bk_biz_id,
                app=self.app_name,
                general_filters={"sample_type": f"op_eq|{sample_type}"},
                start=start,
                end=end,
                service_name=service_name,
                limit={"offset": 0, "rows": 1},
                order={"expr": "dtEventTimeStamp", "sort": "desc"},
                label_filter=label_filter,
                dimension_fields="dtEventTimeStamp",
            ),
            result_table_id=self.result_table_id,
        ).execute()

        if not info or not info.get("list", []):
            return None

        ts = info["list"][0].get("dtEventTimeStamp")
        if not ts:
            return None

        return ts

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
                metric_fields="count(*)",
                dimension_fields="app",
            ),
            result_table_id=self.result_table_id,
        ).execute()
        if not res or not res.get("list", []):
            return False
        count = next((i["count(*)"] for i in res["list"] if i.get("app") == self.app_name), None)
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
        count_mapping = self.get_service_request_count_mapping(start, end)
        for svr in services:
            res.update({svr: {"profiling_data_count": count_mapping[svr]}} if svr in count_mapping else {})

        return res

    def get_service_request_count_mapping(self, start: int, end: int):
        """
        获取 service 的请求信息
        信息包含:
        1. profiling_data_count 上报数据量
        """
        res = Query(
            api_type=APIType.SELECT_COUNT,
            api_params=APIParams(
                biz_id=self.bk_biz_id,
                app=self.app_name,
                start=start,
                end=end,
                dimension_fields="service_name",
                metric_fields="count(*)",
            ),
            result_table_id=self.result_table_id,
        ).execute()

        if not res:
            return {}

        # 计算平台 select_count 时, 固定的列名称为 count(1) . 所以这里这样写
        return {i["service_name"]: i["count(*)"] for i in res["list"]}

    def get_service_count(self, start_time, end_time, service_name):
        """获取单个 service 数据量"""

        res = Query(
            api_type=APIType.SELECT_COUNT,
            api_params=APIParams(
                biz_id=self.bk_biz_id,
                app=self.app_name,
                start=start_time,
                end=end_time,
                service_name=service_name,
                dimension_fields="service_name",
                metric_fields="count(*)",
            ),
            result_table_id=self.result_table_id,
        ).execute()

        if not res or not res.get("list"):
            return None

        return next(i["count(*)"] for i in res["list"])

    def get_count(
        self, start_time: int, end_time: int, sample_type: str, service_name: str = None, label_filter: dict = None
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
                label_filter=label_filter,
                service_name=service_name,
                metric_fields="count(*)",
                dimension_fields="FLOOR((dtEventTimeStamp / 1000) / 60) * 60000 AS time",
                general_filters={"sample_type": f"op_eq|{sample_type}"},
            ),
            result_table_id=self.result_table_id,
        ).execute()
        if not res or not res.get("list", []):
            return []
        return [[i["count(*)"], int(i["time"])] for i in res["list"] if "time" in i]

    def list_labels(
        self,
        start_time: int,
        end_time: int,
        sample_type: str,
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
                general_filters={"sample_type": f"op_eq|{sample_type}"},
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
