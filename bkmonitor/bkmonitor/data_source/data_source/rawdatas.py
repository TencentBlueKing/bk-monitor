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
from core.drf_resource import api
from core.errors.api import BKAPIError
from core.errors.bkmonitor.rawdatas import (
    MetricsDataCountApiError,
    SamplingApiError,
    StoragesApiError,
)


class BkRawDatasSource(object):
    @staticmethod
    def get_storages_data(bk_biz_id):
        """
        获取存储信息
        参数:
        bk_biz_id：数据源id

        return:
        api response

        except:
        StoragesApiError
        """
        try:
            response = api.bkbase.get_storages_data(raw_data_id=bk_biz_id, with_sql=True)
            return response
        except BKAPIError:
            raise StoragesApiError()

    @staticmethod
    def get_sampling_data(bk_biz_id):
        """
        获取采样数据
        """
        try:
            response = api.bkbase.get_sampling_data(data_id=bk_biz_id)
            return response
        except BKAPIError:
            return SamplingApiError()

    @staticmethod
    def get_test(bk_biz_id):
        """
        获取采样数据
        """
        response = api.bkbase.test(raw_data_id=bk_biz_id)
        return response

    @staticmethod
    def get_metrics_data_count(start_time, end_time, bk_biz_id, is_day=False):
        """
        获取数据量统计

        param：
        start_time(int):开始时间(时间戳)
        end_time(int):结束时间(时间戳)
        bk_biz_id(int):数据源ID
        time_grain(bool):是否为天查询

        return:
        api data

        except:
        return
        """
        params = {
            "start_time": f"{start_time}s",
            "end_time": f"{end_time}s",
            "bk_biz_id": bk_biz_id,
        }
        if is_day:
            params.update({"time_grain": "1d"})

        try:
            response = api.bkbase.get_metrics_data_count(**params)
            return response
        except BKAPIError:
            raise MetricsDataCountApiError()
