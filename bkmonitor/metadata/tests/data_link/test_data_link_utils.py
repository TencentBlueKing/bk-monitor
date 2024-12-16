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

from metadata.models.data_link.utils import (
    compose_bkdata_data_id_name,
    compose_bkdata_table_id,
)


def test_compose_bkdata_table_id():
    """
    测试compose_bkdata_table_id能否正常工作
    """
    # Case1. 常规情况，未超长
    table_id = "1001_bkmonitor_time_series_50010.__default__"
    expected = "bkm_1001_bkmonitor_time_series_50010"
    assert compose_bkdata_table_id(table_id) == expected

    # Case2. 负数开头
    table_id = "-negative_start.__default__"
    expected = "bkm_neg_negative_start"
    assert compose_bkdata_table_id(table_id) == expected

    # Case3. 超长情况，截断
    table_id = "100147_bkmonitor_time_series_test_game_service_report.__default__"
    expected = "bkm_100147_bkmonitor_time_series_t_2cd3f"
    assert compose_bkdata_table_id(table_id) == expected
    assert len(compose_bkdata_table_id(table_id)) < 50

    # Case3. 超长情况，截断
    table_id = "100147_bkmonitor_time_series_test_game_service_report_custom_test.__default__"
    expected = "bkm_100147_bkmonitor_time_series_t_295a4"
    assert compose_bkdata_table_id(table_id) == expected
    assert len(compose_bkdata_table_id(table_id)) < 50

    # Case4、 联邦场景
    table_id = '1001_bkmonitor_time_series_1234567.__default__'
    expected = 'bkm_1001_bkmonitor_time_series_85090_fed'
    assert compose_bkdata_table_id(table_id, strategy='bcs_federal_subset_time_series') == expected

    table_id = '1001_bkmonitor_time_series_1234568.__default__'
    expected = 'bkm_1001_bkmonitor_time_series_083dd_fed'
    assert compose_bkdata_table_id(table_id, strategy='bcs_federal_subset_time_series') == expected

    # Case5、 中文场景
    table_id = '1001_bkmonitor_time_series_1234568_中文测试.__default__'
    expected = "bkm_1001_bkmonitor_time_series_123_e81c3"
    assert compose_bkdata_table_id(table_id) == expected

    # Case6、 联邦场景,双下划线问题
    expected = "bkm_1001_bkmonitor_time_series_e81c3_fed"
    assert compose_bkdata_table_id(table_id, strategy='bcs_federal_subset_time_series') == expected


def test_compose_bkdata_data_id_name():
    """
    测试compose_bkdata_data_id_name能否正常工作
    """
    # Case1. 常规情况，未超长
    data_name = "bcs_BCS-K8S-00000_custom_metric"
    expected = "bkm_bcs_BCS-K8S-00000_custom_metric"
    assert compose_bkdata_data_id_name(data_name) == expected

    # Case2. 超长情况，截断
    data_name = "test_lol_game_service_report_bk_monitor_data_link_game_service_test_for_compose_case"
    expected = "bkm_link_game_service_test_for_compose_case_85ca5"
    assert compose_bkdata_data_id_name(data_name) == expected
    assert len(compose_bkdata_data_id_name(data_name)) < 50

    # Case2. 超长情况，截断
    data_name = "test_val_game_service_report_bk_monitor_data_link_game_service_test_for_compose_case"
    expected = "bkm_link_game_service_test_for_compose_case_d3e5c"
    assert compose_bkdata_data_id_name(data_name) == expected
    assert len(compose_bkdata_data_id_name(data_name)) < 50

    # Case3. 中文字符串
    data_name = "test_monitor_测试数据_111222"
    expected = "bkm_test_monitor_111222ceshishuju"
    assert compose_bkdata_data_id_name(data_name) == expected
    assert len(compose_bkdata_data_id_name(data_name)) < 50

    # Case4. 超长中文字符串
    data_name = "custom_time_series_中文测试数据测试数据测试数据"
    expected = "bkm_zhongwenceshishujuceshishujuceshishuju_0c0f8"
    assert compose_bkdata_data_id_name(data_name) == expected
    assert len(compose_bkdata_data_id_name(data_name)) < 50
