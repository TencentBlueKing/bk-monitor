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
import datetime
import os
from collections import defaultdict

import six
from django.conf import settings

from bkmonitor.data_source import load_data_source
from bkmonitor.data_source.unify_query.query import UnifyQuery
from bkmonitor.utils.cache import CacheType, using_cache
from bkmonitor.utils.common_utils import host_key, ignored
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import resource
from core.errors.dataapi import SqlQueryException

NO_DATA_CONCURRENT_NUMBER = os.getenv("NO_DATA_CONCURRENT_NUMBER", 20)


class DataBase(object):
    @classmethod
    def get_plat_id(cls, point):
        raise NotImplementedError

    @classmethod
    def parse_hostindex_data_result(cls, data, item_field=None, dimension_field=None, conversion=1.0, unit_display=""):
        if not data:
            return defaultdict(dict)

        if isinstance(item_field, str):
            item_field = [item_field]

        multi_performance_point_info = defaultdict(dict)
        for item in item_field:
            performance_point_info = dict()
            for point in data:
                # 将计算平台platid为0的转换成1
                plat_id = cls.get_plat_id(point)
                key = host_key(ip=point["ip"], plat_id=plat_id)
                if dimension_field:
                    dimension = point[dimension_field]
                    key = "{}::{}".format(key, dimension)
                if key not in performance_point_info and point[item] is not None:
                    val = point[item]
                    with ignored(TypeError, log_exception=False):
                        if isinstance(val, int) and int(conversion) == 1:
                            val = int(val)
                        else:
                            val = float(val) / conversion
                            val = round(val, settings.POINT_PRECISION)
                    performance_point_info[key] = {"val": val, "unit": unit_display}
                else:
                    continue

            if dimension_field:
                new_performance_point_info = dict()
                for k, v in six.iteritems(performance_point_info):
                    key, dimension = k.split("::")
                    bp_item = {dimension: v["val"]}
                    if key not in new_performance_point_info:
                        new_performance_point_info[key] = {"val": [bp_item], "unit": v["unit"]}
                    else:
                        new_performance_point_info[key]["val"].append(bp_item)
                performance_point_info = new_performance_point_info

                # cpu 单核使用率展示专用逻辑，当前版本不展示单核使用率，因此可以不做排序
                # for host_id, val in six.iteritems(performance_point_info):
                #     performance_point_info[host_id]["val"] = sorted(
                #         val["val"], key=lambda x: str(list(x.keys())[0])
                #     )
            multi_performance_point_info[item] = performance_point_info
        return multi_performance_point_info


class TSDBData(DataBase):
    @classmethod
    def get_plat_id(cls, point):
        if point.get("bk_cloud_id") is not None:
            return str(point["bk_cloud_id"])
        if point.get("plat_id") is not None:
            return str(point["plat_id"])
        return "0"

    @classmethod
    def get_hostid_status_by_result_table(cls, hostid_list, result_table_list, using_new_dimensions=False):
        """
        获取hostid数据状态，遍历查询每张表，直到每一个hostid都有数据，或者表遍历完
        """
        report_info = dict().fromkeys(hostid_list, False)
        if not hostid_list:
            return report_info

        dimensions = settings.NEW_DEFAULT_HOST_DIMENSIONS

        for result_table_id in result_table_list:
            try:
                data = cls.get_data(table_name=result_table_id, select_field=["count(*)"], group_by_field=dimensions)
            except SqlQueryException:
                continue

            if data:
                for point in data:
                    plat_id = cls.get_plat_id(point)
                    key = host_key(ip=point["ip"], plat_id=plat_id)
                    if key in hostid_list and key in report_info:
                        report_info[key] = True
                        hostid_list.remove(key)
            if all(report_info.values()):
                break
        return report_info

    @classmethod
    @using_cache(CacheType.DATA)
    def get_data_with_cache(
        cls, table_name, select_field, group_by_field=None, filter_dict=None, limit=1, order_by_field=None
    ):
        return cls.get_data(table_name, select_field, group_by_field, filter_dict, limit, order_by_field)

    @classmethod
    def get_data(
        cls,
        table_name,
        select_field,
        group_by_field=None,
        filter_dict=None,
        limit=settings.SQL_MAX_LIMIT,
        order_by_field=None,
    ):
        if order_by_field:
            order_by = [order_by_field]
        else:
            order_by = None
        table_name = resource.commons.trans_bkcloud_rt_bizid(table_name)

        filter_dict = filter_dict or {}
        if not any([key.startswith("time") for key in filter_dict]):
            # 如果没有传时间范围条件，则默认取最后5分钟的数据
            filter_dict["time__gte"] = "3m"
        if "cloud_id" in filter_dict:
            filter_dict["plat_id"] = filter_dict.pop("cloud_id")

        group_by_field = ["ip", "bk_cloud_id", "minute1"] if group_by_field is None else group_by_field

        # 判断类型，将字符串转换为list
        if isinstance(select_field, list):
            values = select_field
        elif isinstance(select_field, six.string_types):
            values = select_field.split(",")
        else:
            values = []

        data_source_class = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)
        data_source = data_source_class(
            table=table_name,
            metrics=[{"field": field} for field in values],
            filter_dict=filter_dict,
            group_by=group_by_field,
            order_by=order_by,
        )
        data = data_source.query_data(limit=limit)

        if "bk_cloud_id" in group_by_field:
            for d in data:
                d["bk_cloud_id"] = cls.get_plat_id(d)
        return data


class TSDataBase(object):
    def __init__(self, db_name, result_tables=None, bk_biz_id=None):
        self.bk_biz_id = bk_biz_id
        self.tables = result_tables
        self.db_name = db_name

    def table_id(self, table_name):
        table_id = "{db_name}.{table}".format(db_name=self.db_name, table=table_name)
        # if self.bk_biz_id:
        #     table_id = "{bk_biz_id}_{table_id}".format(bk_biz_id=self.bk_biz_id, table_id=table_id)

        return table_id

    def get_data(self, table_name, select_field, group_by_field=None, filter_dict=None, limit=settings.SQL_MAX_LIMIT):
        table_id = self.table_id(table_name)
        filter_dict = filter_dict or {}
        if not any([key.startswith("time") for key in filter_dict]):
            # 如果没有传时间范围条件，则默认取最后5分钟的数据
            filter_dict["time__gt"] = "5m"
        if "cloud_id" in filter_dict:
            filter_dict["plat_id"] = filter_dict.pop("cloud_id")

        group_by_field = ["minute1"] if group_by_field is None else group_by_field

        # 判断类型，将字符串转换为list
        if isinstance(select_field, list):
            values = select_field
        elif isinstance(select_field, six.string_types):
            values = select_field.split(",")
        else:
            values = []

        data_source_class = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)
        data_source = data_source_class(
            table=table_id,
            metrics=[{"field": field} for field in values],
            filter_dict=filter_dict,
            group_by=group_by_field,
        )
        data = data_source.query_data(limit=limit)

        return data

    @staticmethod
    def get_group_by_field(target):
        group_by_field_mapping = {
            "HOST": ["bk_target_ip", "bk_target_cloud_id"],
            "SERVICE": ["bk_target_service_instance_id"],
        }
        if "bk_target_ip" in target and "bk_target_cloud_id" in target:
            return group_by_field_mapping["HOST"]
        elif "bk_target_service_instance_id" in target:
            return group_by_field_mapping["SERVICE"]

    def concurrent_check_if_no_data_by_unify_query(self, target_result, group_by_fields, filter_dict):
        table = self.tables[0]
        filter_dict = filter_dict or {}
        # 如果没有传时间范围条件，则默认取最后5分钟的数据
        time_delta = filter_dict.get("time_gt", "5m")
        time_delta = int(time_delta.split("m")[0])
        data_source_class = load_data_source(DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES)
        # 组成 group by 语句
        group_statement = ",".join(group_by_fields)
        # 组成 count 语句
        count_statement = ""
        # 只取前五个
        # TODO 汇聚周期注意不要写死 1m
        for field in table.fields[0:5]:
            base_statement = (
                f"count_over_time(bkmonitor:{self.db_name}:{field['field_name']}"
                f"{{bk_collect_config_id=\'{filter_dict['bk_collect_config_id']}\'}}[1m])"
            )
            if count_statement:
                base_statement = " or " + base_statement
            count_statement += base_statement
        # 如果没有待查询指标，则直接返回
        if not count_statement:
            return target_result
        promql_statement = f"sum by ({group_statement}) ({count_statement})"
        query_config = {
            "data_source_label": DataSourceLabel.PROMETHEUS,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "promql": promql_statement,
            "interval": 60,
            "alias": "a",
        }
        data_source = data_source_class(bk_biz_id=self.bk_biz_id, **query_config)
        query = UnifyQuery(bk_biz_id=self.bk_biz_id, data_sources=[data_source], expression="")
        query_data = query.query_data(
            start_time=int(
                (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=time_delta)).timestamp()
            )
            * 1000,
            end_time=int(datetime.datetime.now(datetime.timezone.utc).timestamp()) * 1000,
        )

        for row in query_data:
            row_key = tuple(str(row[field]) for field in group_by_fields)
            if row_key in target_result:
                target_result[row_key] = True
        return target_result

    def no_data_test(self, test_target_list, filter_dict=None):
        """
        无数据检测
        :param test_target_list: 检测目标
        :param filter_dict: 检测范围
        :return: [{
            "bk_target_ip": "x.x.x.x",
            "bk_target_cloud_id": 0,
            "no_data": True
        },{
            "bk_target_service_instance_id": 1,
            "no_data": True,
        }]
        """
        if len(test_target_list) == 0:
            return []

        group_by_fields = tuple(self.get_group_by_field(test_target_list[0]))
        target_result = {}
        for target in test_target_list:
            target_key = tuple([str(target[field]) for field in group_by_fields])
            target_result[target_key] = False
        target_result = self.concurrent_check_if_no_data_by_unify_query(target_result, group_by_fields, filter_dict)
        result_target_list = []
        for target_key, ok in target_result.items():
            target_info = dict(zip(group_by_fields, target_key))
            target_info["no_data"] = not ok
            result_target_list.append(target_info)
        return result_target_list
