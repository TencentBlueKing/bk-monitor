# -*- coding: utf-8 -*
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
from typing import Dict, Any, List

import arrow
from django.conf import settings

from apps.bk_log_admin.constants import (
    BK_DATA_CUSTOM_REPORT_USER_INDEX_SET_HISTORY,
    OPERATION_PIE_CHOICE_MAP,
    BK_DATA_CUSTOM_REPORT_USER_INDEX_SET_HISTORY_FIELD,
    DATE_HISTOGRAM_INTERVAL,
)
from apps.log_search.models import UserIndexSetSearchHistory
from apps.models import model_to_dict
from apps.utils.drf import DataPageNumberPagination
from apps.utils.local import get_local_param
from apps.utils.log import logger
from apps.utils.lucene import generate_query_string
from bk_monitor.api.client import Client
from config.domains import MONITOR_APIGATEWAY_ROOT


class IndexSetHandler(object):
    def __init__(self):
        self._client = Client(
            bk_app_code=settings.APP_CODE,
            bk_app_secret=settings.SECRET_KEY,
            monitor_host=MONITOR_APIGATEWAY_ROOT,
            report_host=f"{settings.BKMONITOR_CUSTOM_PROXY_IP}/",
            bk_username="admin",
        )

    @property
    def data_label(self):
        data_label = "{bk_biz_id}_{app_code}_{table}".format(
            bk_biz_id=settings.BLUEKING_BK_BIZ_ID,
            app_code=settings.APP_CODE.replace("-", "_"),
            table=BK_DATA_CUSTOM_REPORT_USER_INDEX_SET_HISTORY
        )
        return data_label

    @property
    def table(self):
        return f"{self.data_label}.base"

    @property
    def prometheus_table(self):
        return "custom:{bk_biz_id}_{app_code}_{table}:{field}".format(
            bk_biz_id=settings.BLUEKING_BK_BIZ_ID,
            app_code=settings.APP_CODE.replace("-", "_"),
            table=BK_DATA_CUSTOM_REPORT_USER_INDEX_SET_HISTORY,
            field=BK_DATA_CUSTOM_REPORT_USER_INDEX_SET_HISTORY_FIELD
        )

    def get_date_histogram(self, index_set_id, user_search_history_operation_time):
        """
        @param index_set_id {Int} the id of log_index_set
        @param user_search_history_operation_time {dict} the search dict
        @param user_search_history_operation_time.start_time {Str} the search begin
        @param user_search_history_operation_time.end_time the search end
        """
        start_time, end_time = self._get_start_end_time(
            user_search_history_operation_time=user_search_history_operation_time
        )
        metrics = [
            {
                "field": BK_DATA_CUSTOM_REPORT_USER_INDEX_SET_HISTORY_FIELD,
                "method": "COUNT",
                "alias": "a"
            }
        ]
        where = [
            {
                "key": "index_set_id",
                "method": "eq",
                "value": [
                    str(index_set_id)
                ]
            }
        ]
        unify_query_data = self.call_unify_query(
            start_time=start_time,
            end_time=end_time,
            metrics=metrics,
            where=where,
            interval=DATE_HISTOGRAM_INTERVAL
        )
        if not unify_query_data["series"]:
            return {"labels": [], "values": []}

        daily_label_list = []
        daily_data_list = []
        # 只有一个series
        for data in unify_query_data["series"][0]["datapoints"]:
            daily_label_list.append(arrow.get(data[1] / 1000).format())
            daily_data_list.append(data[0] if data[0] else 0)

        return {"labels": daily_label_list, "values": daily_data_list}

    def get_user_terms(self, index_set_id, user_search_history_operation_time):
        """
        @param index_set_id {Int} the id of log_index_set
        @param user_search_history_operation_time {dict} the search dict
        @param user_search_history_operation_time.start_time {Str} the search begin
        @param user_search_history_operation_time.end_time the search end
        """
        start_time, end_time = self._get_start_end_time(
            user_search_history_operation_time=user_search_history_operation_time
        )
        metrics = [
            {
                "field": BK_DATA_CUSTOM_REPORT_USER_INDEX_SET_HISTORY_FIELD,
                "method": "COUNT",
                "alias": "a"
            }
        ]
        where = [
            {
                "key": "index_set_id",
                "method": "eq",
                "value": [
                    str(index_set_id)
                ]
            }
        ]
        group_by = ["created_by"]
        unify_query_data = self.call_unify_query(
            start_time=start_time,
            end_time=end_time,
            metrics=metrics,
            where=where,
            group_by=group_by
        )
        if not unify_query_data["series"]:
            return {"labels": [], "values": []}
        created_by_label_list = []
        created_by_data_list = []
        for data in unify_query_data["series"]:
            created_by_label_list.append(data["dimensions"]["created_by"])
            created_by_data_list.append(sum([i[0] for i in data["datapoints"] if i[0]]))

        return {"labels": created_by_label_list, "values": created_by_data_list}

    def get_duration_terms(self, index_set_id, user_search_history_operation_time):
        """
        @param index_set_id {Int} the id of log_index_set
        @param user_search_history_operation_time {dict} the search dict
        @param user_search_history_operation_time.start_time {Str} the search begin
        @param user_search_history_operation_time.end_time the search end
        """
        start_time, end_time = self._get_start_end_time(
            user_search_history_operation_time=user_search_history_operation_time
        )
        pie_label_list = []
        pie_data_list = []
        for pie_choice in OPERATION_PIE_CHOICE_MAP:
            pie_label_list.append(pie_choice["label"])
            if "min" in pie_choice and "max" in pie_choice:
                promql = (
                    f"count({self.prometheus_table}{{index_set_id=\"{index_set_id}\"}} >= {pie_choice['min']} and "
                    f"{self.prometheus_table}{{index_set_id=\"{index_set_id}\"}} < {pie_choice['max']})"
                )
            elif "min" in pie_choice:
                promql = f"count({self.prometheus_table}{{index_set_id=\"{index_set_id}\"}} >= {pie_choice['min']})"
            # "max" in pie_choice
            else:
                promql = f"count({self.prometheus_table}{{index_set_id=\"{index_set_id}\"}} < {pie_choice['max']})"
            unify_query_data = self.call_unify_query_by_promql(
                start_time=start_time,
                end_time=end_time,
                promql=promql
            )
            if not unify_query_data["series"]:
                pie_data_list.append(0)
                continue
            pie_data_list.append(sum([i[0] for i in unify_query_data["series"][0]["datapoints"] if i[0]]))

        return {"labels": pie_label_list, "values": pie_data_list}

    def list_user_set_history(self, start_time, end_time, request, view, index_set_id):
        time_zone = get_local_param("time_zone")
        user_index_set_history = UserIndexSetSearchHistory.objects.filter(
            index_set_id=index_set_id,
            is_deleted=False,
            search_type="default",
            created_at__range=[
                start_time.replace(tzinfo=time_zone).datetime,
                end_time.replace(tzinfo=time_zone).datetime,
            ],
        ).order_by("-created_at", "created_by")
        pg = DataPageNumberPagination()
        page_user_index_set_history = pg.paginate_queryset(queryset=user_index_set_history, request=request, view=view)
        res = pg.get_paginated_response(
            [
                IndexSetHandler.build_query_string(
                    model_to_dict(
                        history, fields=["id", "index_set_id", "duration", "created_by", "created_at", "params"]
                    )
                )
                for history in page_user_index_set_history
            ]
        )
        return res

    @staticmethod
    def build_query_string(history):
        history["query_string"] = generate_query_string(history["params"])
        return history

    @staticmethod
    def _get_start_end_time(user_search_history_operation_time):
        start_time = int(user_search_history_operation_time["start_time"])
        end_time = int(user_search_history_operation_time["end_time"])
        return start_time, end_time

    def call_unify_query(
            self,
            start_time: int,
            end_time: int,
            metrics: List[Dict[str, Any]] = None,
            where: List[Dict[str, Any]] = None,
            group_by: List = None,
            interval: int = None
    ):
        """
        以通用的形式查询unify_query
        """
        if not metrics:
            metrics = []
        if not where:
            where = []
        if not group_by:
            group_by = []
        if not interval:
            interval = "auto"
        params = {
            "down_sample_range": "15m",
            "step": interval,
            "format": "time_series",
            "type": "range",
            "start_time": start_time,
            "end_time": end_time,
            "expression": "a",
            "display": True,
            "query_configs": [
                {
                    "data_label": self.data_label,
                    "data_source_label": "custom",
                    "data_type_label": "time_series",
                    "metrics": metrics,
                    "table": self.table,
                    "group_by": group_by,
                    "display": True,
                    "where": where,
                    "interval": interval,
                    "interval_unit": "s",
                    "time_field": "time",
                    "filter_dict": {},
                    "functions": []
                }
            ],
            "target": [],
            "bk_biz_id": str(settings.BLUEKING_BK_BIZ_ID)
        }
        try:
            return self._client.unify_query(params)
        except Exception as e:
            logger.error(f"unify_query error, params: {params}, error: {e}")
        return {
            "metrics": [],
            "series": [],
        }

    def call_unify_query_by_promql(
            self,
            start_time: int,
            end_time: int,
            promql: str,
            interval: int = None
    ):
        """
        以promql的形式查询unify_query
        """
        if not interval:
            interval = "auto"
        params = {
            "down_sample_range": "15m",
            "step": interval,
            "format": "time_series",
            "type": "range",
            "start_time": start_time,
            "end_time": end_time,
            "expression": "a",
            "display": True,
            "query_configs": [
                {
                    "data_label": self.data_label,
                    "data_source_label": "prometheus",
                    "data_type_label": "time_series",
                    "display": True,
                    "interval": interval,
                    "interval_unit": "s",
                    "time_field": "time",
                    "promql": promql
                }
            ],
            "target": [],
            "bk_biz_id": str(settings.BLUEKING_BK_BIZ_ID)
        }
        try:
            return self._client.unify_query(params)
        except Exception as e:
            logger.error(f"unify_query_by_promql error, params: {params}, error: {e}")
        return {
            "metrics": [],
            "series": [],
        }
