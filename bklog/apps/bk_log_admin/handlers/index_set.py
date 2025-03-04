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
import arrow
import pytz
from django.db.models import Case, CharField, Count, Value, When
from django.db.models.functions import TruncDate
from django.utils.encoding import force_str

from apps.bk_log_admin.constants import OPERATION_PIE_CHOICE_MAP
from apps.log_search.models import UserIndexSetSearchHistory
from apps.models import model_to_dict
from apps.utils.drf import DataPageNumberPagination
from apps.utils.local import get_local_param
from apps.utils.lucene import generate_query_string


class IndexSetHandler(object):
    @staticmethod
    def get_user_index_set_history_objs(index_set_id, start_time, end_time):
        """
        获取索引集用户检索记录表数据
        :param index_set_id: 索引集id
        :param start_time: 起始时间
        :param end_time: 结束时间
        """
        objs = UserIndexSetSearchHistory.objects.filter(
            index_set_id=index_set_id,
            search_type="default",
            created_at__range=[
                start_time.datetime,
                end_time.datetime,
            ],
        )
        return objs

    def get_date_histogram(self, index_set_id, user_search_history_operation_time):
        """
        @param index_set_id {Int} the id of log_index_set
        @param user_search_history_operation_time {dict} the search dict
        @param user_search_history_operation_time.start_time {Str} the search begin
        @param user_search_history_operation_time.end_time the search end
        """
        user_index_set_history_objs = self.get_user_index_set_history_objs(
            index_set_id,
            arrow.get(user_search_history_operation_time["start_time"]),
            arrow.get(user_search_history_operation_time["end_time"]),
        )
        user_index_set_history = (
            user_index_set_history_objs.annotate(
                day=TruncDate("created_at", tzinfo=pytz.timezone("UTC")),
            )
            .values("day")
            .annotate(count=Count('id'))
        )
        daily_label_list = []
        daily_data_list = []
        for item in user_index_set_history:
            agg_date = arrow.get(item["day"]).format()
            daily_label_list.append(agg_date)
            daily_data_list.append(item["count"])

        return {"labels": daily_label_list, "values": daily_data_list}

    def get_user_terms(self, index_set_id, user_search_history_operation_time):
        """
        @param index_set_id {Int} the id of log_index_set
        @param user_search_history_operation_time {dict} the search dict
        @param user_search_history_operation_time.start_time {Str} the search begin
        @param user_search_history_operation_time.end_time the search end
        """
        user_index_set_history_objs = self.get_user_index_set_history_objs(
            index_set_id,
            arrow.get(user_search_history_operation_time["start_time"]),
            arrow.get(user_search_history_operation_time["end_time"]),
        )
        user_index_set_history = user_index_set_history_objs.values("created_by").annotate(count=Count("id"))
        created_by_label_list = []
        created_by_data_list = []
        for item in user_index_set_history:
            created_by_label_list.append(item["created_by"])
            created_by_data_list.append(item["count"])
        return {"labels": created_by_label_list, "values": created_by_data_list}

    def get_duration_terms(self, index_set_id, user_search_history_operation_time):
        """
        @param index_set_id {Int} the id of log_index_set
        @param user_search_history_operation_time {dict} the search dict
        @param user_search_history_operation_time.start_time {Str} the search begin
        @param user_search_history_operation_time.end_time the search end
        """
        user_index_set_history_objs = self.get_user_index_set_history_objs(
            index_set_id,
            arrow.get(user_search_history_operation_time["start_time"]),
            arrow.get(user_search_history_operation_time["end_time"]),
        )

        # 根据分组范围和对应的标签构建Case表达式
        case_expression = Case(
            *[
                When(duration__gte=item["min"], duration__lt=item["max"], then=Value(force_str(item["label"])))
                if item.get("max")
                else When(duration__gte=item["min"], then=Value(force_str(item["label"])))
                for item in OPERATION_PIE_CHOICE_MAP
            ],
            output_field=CharField(),
        )
        results = user_index_set_history_objs.annotate(duration_range=case_expression)
        grouped_results = results.values("duration_range").annotate(count=Count("id"))
        pie_label_list = []
        pie_data_list = []
        for item in grouped_results:
            pie_label_list.append(item["duration_range"])
            pie_data_list.append(item["count"])
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
