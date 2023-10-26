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


import pytest

from core.errors.uptime_check import UptimeCheckProcessError


@pytest.mark.django_db
class TestUptimeCheckNode(object):
    # def test_query_result(self, mocker):
    #     from monitor_web.uptime_check.serializers import UptimeCheckNodeSerializer
    #
    #     validated_data = {
    #         "bk_biz_id": 2,
    #         "name": "\u4e2d\u56fd\u5e7f\u4e1c\u79fb\u52a8",
    #         "ip": "10.0.1.16",
    #         "carrieroperator": "\u79fb\u52a8",
    #         "location": {"country": "\u4e2d\u56fd", "city": "\u5e7f\u4e1c"},
    #         "plat_id": 0,
    #         "is_common": False,
    #     }
    #
    #     mocker.patch("bkmonitor.data_source.backends.base.compiler.SQLCompiler.execute_sql", return_value=[None])
    #     assert UptimeCheckNodeSerializer().node_beat_check(validated_data)

    def test_query_result_no_data(self, mocker):
        from monitor_web.uptime_check.serializers import UptimeCheckNodeSerializer

        validated_data = {
            "bk_biz_id": 2,
            "name": "\u4e2d\u56fd\u5e7f\u4e1c\u79fb\u52a8",
            "ip": "10.0.1.16",
            "carrieroperator": "\u79fb\u52a8",
            "location": {"country": "\u4e2d\u56fd", "city": "\u5e7f\u4e1c"},
            "plat_id": 0,
            "is_common": False,
        }

        query_result_mock = mocker.patch(
            "bkmonitor.data_source.backends.base.compiler.SQLCompiler.execute_sql", return_value=[]
        )
        with pytest.raises(UptimeCheckProcessError):
            UptimeCheckNodeSerializer().node_beat_check(validated_data)
            query_result_mock.assert_called_once()
