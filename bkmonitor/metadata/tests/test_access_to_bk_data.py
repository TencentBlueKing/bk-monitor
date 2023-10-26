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
import logging

import mock
import pytest
from django.conf import settings

from metadata import models

logger = logging.getLogger("metadata")


@pytest.fixture(autouse=True)
def access_deploy_plan(mocker):
    mocker.patch("api.bkdata.default.AccessDeployPlan.perform_request", return_value={"raw_data_id": 1})


@pytest.fixture(autouse=True)
def init_result_table_fields():
    models.ResultTableField.objects.filter(table_id="system.mem").delete()
    fields = [
        {
            'table_id': 'system.mem',
            'field_name': 'bk_agent_id',
            'field_type': 'string',
            'description': 'Agent ID',
            'unit': '',
            'tag': 'dimension',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'bk_biz_id',
            'field_type': 'int',
            'description': '业务ID',
            'unit': '',
            'tag': 'dimension',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'bk_cloud_id',
            'field_type': 'int',
            'description': '采集器云区域ID',
            'unit': '',
            'tag': 'dimension',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'bk_cmdb_level',
            'field_type': 'string',
            'description': 'CMDB层级信息',
            'unit': '',
            'tag': 'dimension',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'bk_host_id',
            'field_type': 'string',
            'description': '采集主机ID',
            'unit': '',
            'tag': 'dimension',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'bk_supplier_id',
            'field_type': 'int',
            'description': '开发商ID',
            'unit': '',
            'tag': 'dimension',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'bk_target_cloud_id',
            'field_type': 'string',
            'description': '云区域ID',
            'unit': '',
            'tag': 'dimension',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'bk_target_host_id',
            'field_type': 'string',
            'description': '目标主机ID',
            'unit': '',
            'tag': 'dimension',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'bk_target_ip',
            'field_type': 'string',
            'description': '目标IP',
            'unit': '',
            'tag': 'dimension',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'buffer',
            'field_type': 'int',
            'description': '内存buffered大小',
            'unit': 'bytes',
            'tag': 'metric',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'cached',
            'field_type': 'int',
            'description': '内存cached大小',
            'unit': 'bytes',
            'tag': 'metric',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'free',
            'field_type': 'int',
            'description': '物理内存空闲量',
            'unit': 'bytes',
            'tag': 'metric',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'hostname',
            'field_type': 'string',
            'description': '主机名',
            'unit': '',
            'tag': 'dimension',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'ip',
            'field_type': 'string',
            'description': '采集器IP',
            'unit': '',
            'tag': 'dimension',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'pct_usable',
            'field_type': 'double',
            'description': '应用程序内存可用率',
            'unit': 'percent',
            'tag': 'metric',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'pct_used',
            'field_type': 'double',
            'description': '应用程序内存使用占比',
            'unit': 'percent',
            'tag': 'metric',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'psc_pct_used',
            'field_type': 'double',
            'description': '物理内存已用占比',
            'unit': 'percent',
            'tag': 'metric',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'psc_used',
            'field_type': 'int',
            'description': '物理内存已用量',
            'unit': 'bytes',
            'tag': 'metric',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'shared',
            'field_type': 'int',
            'description': '共享内存使用量',
            'unit': 'decbytes',
            'tag': 'metric',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'time',
            'field_type': 'timestamp',
            'description': '数据上报时间',
            'unit': '',
            'tag': 'timestamp',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'total',
            'field_type': 'int',
            'description': '物理内存总大小',
            'unit': 'bytes',
            'tag': 'metric',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'usable',
            'field_type': 'int',
            'description': '应用程序内存可用量',
            'unit': 'bytes',
            'tag': 'metric',
            'is_config_by_user': True,
        },
        {
            'table_id': 'system.mem',
            'field_name': 'used',
            'field_type': 'int',
            'description': '应用程序内存使用量',
            'unit': 'bytes',
            'tag': 'metric',
            'is_config_by_user': True,
        },
    ]
    for filed in fields:
        models.ResultTableField.objects.create(**filed)


def get_databus_cleans_status_running():
    """
    获取清洗配置的状态：running
    """
    return [
        {
            "clean_config_name": "test_clean_config_xxx",
            "clean_result_table_name": "etl_abc_test5",
            "clean_result_table_name_alias": "\u6e05\u6d17\u8868\u6d4b\u8bd5",
            "created_at": "2018-10-30T18:59:14",
            "created_by": "admin",
            "description": "\u6e05\u6d17\u6d4b\u8bd5",
            "id": 4,
            "json_config": '{"extract":{"label":null,"args":[],"type":"fun","method":"from_json","next":{"subtype":'
            '"assign_obj","label":null,"type":"assign","assign":[{"assign_to":"timestamp","type":'
            '"timestamp","key":"_time_"},{"assign_to":"field1","type":"long","key":"_dstdataid_"},'
            '{"assign_to":"field2","type":"int","key":"_gseindex_"}],"next":null}},"conf":{'
            '"timestamp_len":0,"encoding":"UTF8","time_format":"yyyy-MM-ddHH:mm:ss","timezone":8,'
            '"output_field_name":"timestamp","time_field_name":"timestamp"}}',
            "pe_config": "",
            "processing_id": "2_system_mem",
            "raw_data_id": 42,
            "status": "running",  # 成功的标志，status为running
            "status_display": "running",
            "updated_at": "2018-10-31T10:40:24",
            "updated_by": "",
        }
    ]


def get_databus_cleans_status_starting():
    """
    获取清洗配置的状态：starting
    """
    return [
        {
            "clean_config_name": "test_clean_config_xxx",
            "clean_result_table_name": "etl_abc_test5",
            "clean_result_table_name_alias": "\u6e05\u6d17\u8868\u6d4b\u8bd5",
            "created_at": "2018-10-30T18:59:14",
            "created_by": "admin",
            "description": "\u6e05\u6d17\u6d4b\u8bd5",
            "id": 4,
            "json_config": '{"extract":{"label":null,"args":[],"type":"fun","method":"from_json","next":{"subtype":'
            '"assign_obj","label":null,"type":"assign","assign":[{"assign_to":"timestamp","type":'
            '"timestamp","key":"_time_"},{"assign_to":"field1","type":"long","key":"_dstdataid_"},'
            '{"assign_to":"field2","type":"int","key":"_gseindex_"}],"next":null}},"conf":'
            '{"timestamp_len":0,"encoding":"UTF8","time_format":"yyyy-MM-ddHH:mm:ss","timezone"'
            ':8,"output_field_name":"timestamp","time_field_name":"timestamp"}}',
            "pe_config": "",
            "processing_id": "2_system_mem",
            "raw_data_id": 42,
            "status": "starting",  # 成功的标志，status为starting
            "status_display": "starting",
            "updated_at": "2018-10-31T10:40:24",
            "updated_by": "",
        }
    ]


def get_databus_cleans_status_stopped():
    """
    获取清洗配置的状态：stopped
    """
    return [
        {
            "clean_config_name": "test_clean_config_xxx",
            "clean_result_table_name": "etl_abc_test5",
            "clean_result_table_name_alias": "\u6e05\u6d17\u8868\u6d4b\u8bd5",
            "created_at": "2018-10-30T18:59:14",
            "created_by": "admin",
            "description": "\u6e05\u6d17\u6d4b\u8bd5",
            "id": 4,
            "json_config": '{"extract":{"label":null,"args":[],"type":"fun","method":"from_json","next":'
            '{"subtype":"assign_obj","label":null,"type":"assign","assign":[{"assign_to":'
            '"timestamp","type":"timestamp","key":"_time_"},{"assign_to":"field1","type":"long","key":'
            '"_dstdataid_"},{"assign_to":"field2","type":"int","key":"_gseindex_"}],"next":null}},"conf"'
            ':{"timestamp_len":0,"encoding":"UTF8","time_format":"yyyy-MM-ddHH:mm:ss","timezone":8,'
            '"output_field_name":"timestamp","time_field_name":"timestamp"}}',
            "pe_config": "",
            "processing_id": "2_system_mem",
            "raw_data_id": 42,
            "status": "stopped",  # 成功的标志，status为stopped
            "status_display": "stopped",
            "updated_at": "2018-10-31T10:40:24",
            "updated_by": "",
        }
    ]


def get_flow_deploy_info_no_start():
    """
    获取flow的最近一次部署信息：no-start状态
    """
    return None


def get_flow_deploy_info_starting():
    """
    获取flow的最近一次部署信息：starting状态
    """
    return {
        "status": "failure",
        "logs": [
            {"message": "\u9501\u5b9a DataFlow", "level": "INFO", "time": "2017-10-08 20:43:44"},
            {"message": "--- \u5f00\u59cb\u542f\u52a8 DataFlow ---", "level": "INFO", "time": "2017-10-08 20:43:44"},
            {
                "message": "\u542f\u52a8\uff081_xiaozetestclean15\uff09\u8282\u70b9",
                "level": "INFO",
                "time": "2017-10-08 20:43:44",
            },
            {"message": "\u542f\u52a8\u6e05\u6d17\u4efb\u52a1", "level": "INFO", "time": "2017-10-08 20:43:44"},
            {
                "message": "\u66f4\u65b0\u8282\u70b9\u72b6\u6001\uff0cstatus=running",
                "level": "INFO",
                "time": "2017-10-08 20:43:44",
            },
            {
                "message": "\u542f\u52a8\uff081_xiaozerealtime2\uff09\u8282\u70b9",
                "level": "INFO",
                "time": "2017-10-08 20:43:44",
            },
            {"message": "\u542f\u52a8\u5b9e\u65f6\u4efb\u52a1", "level": "INFO", "time": "2017-10-08 20:43:44"},
        ],
        "logs_en": "",
        "logs_zh": "",
        "flow_id": 1,
        "flow_status": "starting",
        "created_by": "user00",
        "action": "stop",
        "id": 57,
        "context": None,
        "start_time": "2018-11-27T21:19:32.928522",
        "end_time": "2018-11-27T21:19:32.928522",
        "version": None,
        "description": "",
        "progress": 60.1,
    }


def get_flow_deploy_info_success():
    """
    获取flow_info信息：starting状态
    """
    return {
        "status": "success",
        "logs": [
            {"message": "\u9501\u5b9a DataFlow", "level": "INFO", "time": "2017-10-08 20:43:44"},
            {"message": "--- \u5f00\u59cb\u542f\u52a8 DataFlow ---", "level": "INFO", "time": "2017-10-08 20:43:44"},
            {
                "message": "\u542f\u52a8\uff081_xiaozetestclean15\uff09\u8282\u70b9",
                "level": "INFO",
                "time": "2017-10-08 20:43:44",
            },
            {"message": "\u542f\u52a8\u6e05\u6d17\u4efb\u52a1", "level": "INFO", "time": "2017-10-08 20:43:44"},
            {
                "message": "\u66f4\u65b0\u8282\u70b9\u72b6\u6001\uff0cstatus=running",
                "level": "INFO",
                "time": "2017-10-08 20:43:44",
            },
            {
                "message": "\u542f\u52a8\uff081_xiaozerealtime2\uff09\u8282\u70b9",
                "level": "INFO",
                "time": "2017-10-08 20:43:44",
            },
            {"message": "\u542f\u52a8\u5b9e\u65f6\u4efb\u52a1", "level": "INFO", "time": "2017-10-08 20:43:44"},
        ],
        "logs_en": "",
        "logs_zh": "",
        "flow_id": 1,
        "created_by": "user00",
        "action": "stop",
        "id": 57,
        "context": None,
        "flow_status": "running",
        "start_time": "2018-11-27T21:19:32.928522",
        "end_time": "2018-11-27T21:19:32.928522",
        "version": None,
        "description": "",
        "progress": 60.1,
    }


def get_flow_deploy_info_failed():
    """
    获取flow_info信息：失败状态
    """
    return {
        "status": "failure",
        "logs": [
            {"message": "\u9501\u5b9a DataFlow", "level": "INFO", "time": "2017-10-08 20:43:44"},
            {"message": "--- \u5f00\u59cb\u542f\u52a8 DataFlow ---", "level": "INFO", "time": "2017-10-08 20:43:44"},
            {
                "message": "\u542f\u52a8\uff081_xiaozetestclean15\uff09\u8282\u70b9",
                "level": "INFO",
                "time": "2017-10-08 20:43:44",
            },
            {"message": "\u542f\u52a8\u6e05\u6d17\u4efb\u52a1", "level": "INFO", "time": "2017-10-08 20:43:44"},
            {
                "message": "\u66f4\u65b0\u8282\u70b9\u72b6\u6001\uff0cstatus=running",
                "level": "INFO",
                "time": "2017-10-08 20:43:44",
            },
            {
                "message": "\u542f\u52a8\uff081_xiaozerealtime2\uff09\u8282\u70b9",
                "level": "INFO",
                "time": "2017-10-08 20:43:44",
            },
            {"message": "\u542f\u52a8\u5b9e\u65f6\u4efb\u52a1", "level": "INFO", "time": "2017-10-08 20:43:44"},
        ],
        "logs_en": "",
        "logs_zh": "",
        "flow_id": 1,
        "created_by": "user00",
        "action": "stop",
        "id": 57,
        "context": None,
        "flow_status": "running",
        "start_time": "2018-11-27T21:19:32.928522",
        "end_time": "2018-11-27T21:19:32.928522",
        "version": None,
        "description": "",
        "progress": 60.1,
    }


def get_sample_node():
    """
    精简版的node信息
    """
    return {
        "node_config": {
            "from_result_table_ids": ["xxx"],
            "bk_biz_id": 2,
            "window_type": "fixed",
            "count_freq": 1,
            "name": "f1_offline",
            "parent_tables": None,
            "fallback_window": 2,
            "data_start": None,
            "data_end": None,
            "fixed_delay": 4,
            "delay": None,
            "table_name": "f1_offline",
            "sql": "select * from 2_f1_stream",
            "accumulate": False,
            "expire_day": 7,
            "output_name": "f1_offline",
            "schedule_period": "day",
        },
        "node_id": 117,
    }


@pytest.mark.django_db
class TestAccessToBkData:
    table_id = "system.mem"
    """
    初始化：
        确认一个table_id
        把sel.generate_bk_data_etl_config方法mocker掉
        把相关不必要的接口(配置清洗参数)请求利用mocker进行数据处理
        保证核心的测试只有相关的几个接口
    执行步骤：
        bkdata_storage = models.storage.BkDataStorage.objects.create(table_id=table_id)
        bkdata_storage.raw_data_id = 1
        bkdata_storage.create_table(table_id, is_sync_db=True, is_access_now=True)
    核心逻辑：
        1. 创建或更新清洗配置
        2. 启动清洗任务
        3. 过滤时间-flow
        4. 接入cmdb-flow
    处理过程：
        根据对应的mocker条件执行完整个流程之后，去判断对应的相关接口执行次数。
    """

    # =====================================【创建或更新清洗配置】============================================
    @staticmethod
    def successful_create_databus_cleans(mocker):
        """
        创建清洗配置成功
        """
        successful_create_databus_cleans_return = {
            "created_by": "abcabc",
            "description": "\u6e05\u6d17\u6d4b\u8bd5",
            "id": 9,
            "json_config": '{"extract": {"label": null, "args": [], "type": "fun", "method": "from_json", "next": '
            '{"subtype": "assign_obj", "label": null, "type": "assign", "assign": [{"assign_to": '
            '"timestamp", "type": "string", "key": "_time_"}, {"assign_to": "field1", "type": "long", '
            '"key": "_dstdataid_"}, {"assign_to": "field2", "type": "int", "key": "_gseindex_"}], '
            '"next": null}}, "conf": {"timestamp_len": 0, "encoding": "UTF8", "time_format": '
            '"yyyy-MM-dd HH:mm:ss", "timezone": 8, "output_field_name": "timestamp", "time_field_name": '
            '"timestamp"}}',
            "pe_config": "",
            "clean_config_name": "test_clean_config_xxx",
            "clean_result_table_name": "etl_pizza_abcabc",
            "clean_result_table_name_alias": "清洗表测试",
            "processing_id": "591_etl_pizza_abcabc",
            "raw_data_id": 42,
            "result_table": {
                "bk_biz_id": 591,
                "count_freq": 1,
                "created_at": "2018-10-31 14:16:39",
                "created_by": "admin",
                "data_processing": {},
                "description": "\u6e05\u6d17\u6d4b\u8bd5",
                "fields": [
                    {
                        "created_at": "2018-10-31 14:16:40",
                        "created_by": "admin",
                        "description": None,
                        "field_name": "timestamp",
                        "field_index": 0,
                        "field_alias": "\u65f6\u95f4\u6233",
                        "field_type": "timestamp",
                        "id": 339,
                        "is_dimension": False,
                        "origins": None,
                        "updated_at": "2018-10-31 14:16:41",
                        "updated_by": "admin",
                    },
                    {
                        "created_at": "2018-10-31 14:16:40",
                        "created_by": "admin",
                        "description": None,
                        "field_name": "ts",
                        "field_index": 1,
                        "field_alias": "\u65f6\u95f4\u6233",
                        "field_type": "string",
                        "id": 339,
                        "is_dimension": False,
                        "origins": None,
                        "updated_at": "2018-10-31 14:16:41",
                        "updated_by": "admin",
                    },
                    {
                        "created_at": "2018-10-31 14:16:41",
                        "created_by": "admin",
                        "description": None,
                        "field_name": "field1",
                        "field_index": 2,
                        "field_alias": "\u5b57\u6bb51",
                        "field_type": "long",
                        "id": 340,
                        "is_dimension": False,
                        "origins": None,
                        "updated_at": "2018-10-31 14:16:41",
                        "updated_by": "admin",
                    },
                    {
                        "created_at": "2018-10-31 14:16:41",
                        "created_by": "admin",
                        "description": None,
                        "field_name": "field2",
                        "field_index": 3,
                        "field_alias": "\u5b57\u6bb52",
                        "field_type": "int",
                        "id": 341,
                        "is_dimension": False,
                        "origins": None,
                        "updated_at": "2018-10-31 14:16:42",
                        "updated_by": "admin",
                    },
                ],
                "project_id": 4,
                "result_table_id": "591_etl_pizza_abcabc",
                "result_table_name": "etl_pizza_abcabc",
                "result_table_name_alias": "\u6e05\u6d17\u8868\u6d4b\u8bd5",
                "processing_type": "clean",
                "sensitivity": "public",
                "storages": {
                    "tspider": {
                        "cluster_type": None,
                        "created_at": "2018-11-01 13:19:10",
                        "created_by": "admin",
                        "description": "\u6d4b\u8bd5\u96c6\u7fa4\uff0c\u6d4b\u8bd5\u6e05\u6d17\u7684tspider"
                        "\u6570\u636e\u5165\u5e93",
                        "expires": "7",
                        "id": 84,
                        "physical_table_name": "591_etl_pizza_abcabc",
                        "priority": 0,
                        "storage_channel": {},
                        "storage_cluster": {
                            "belongs_to": "bkdata",
                            "cluster_domain": "xx.xx.xx.xx",
                            "cluster_group": "test",
                            "cluster_name": "default",
                            "cluster_type": "tspider",
                            "connection_info": '{"port": 12345, "user": "test"}',
                            "priority": 0,
                            "version": "2.0.0",
                        },
                        "storage_config": "",
                        "updated_at": "2018-11-01 13:19:11",
                        "updated_by": "admin",
                    }
                },
                "table_name_alias": None,
                "updated_at": "2018-11-01 15:42:48",
                "updated_by": "admin",
            },
            "result_table_id": "591_etl_pizza_abcabc",
            "status": "stopped",
            "status_display": "stopped",
            "updated_by": "",
        }
        return mocker.patch(
            "api.bkdata.default.DatabusCleans.perform_request", return_value=successful_create_databus_cleans_return
        )

    @staticmethod
    def failed_create_databus_cleans(mocker):
        """
        创建清洗配置失败
        """
        return mocker.patch("api.bkdata.default.DatabusCleans.perform_request", side_effect=Exception)

    @staticmethod
    def stop_databus_cleans(mocker):
        """
        停止清洗任务
        """
        stop_databus_cleans_return = "result_table_id为:rt_id的任务已成功停止!"
        return mocker.patch(
            "api.bkdata.default.StopDatabusCleans.perform_request", return_value=stop_databus_cleans_return
        )

    def successful_update_databus_cleans(self, mocker):
        """
        更新清洗配置成功
        """
        self.stop_databus_cleans(mocker)

        successful_update_databus_cleans_return = "true"
        return mocker.patch(
            "api.bkdata.default.UpdateDatabusCleans.perform_request",
            return_value=successful_update_databus_cleans_return,
        )

    def failed_update_databus_cleans(self, mocker):
        """
        更新清洗配置失败
        """
        self.stop_databus_cleans(mocker)

        return mocker.patch("api.bkdata.default.UpdateDatabusCleans.perform_request", side_effect=Exception)

    # =====================================【启动清洗任务】============================================
    @staticmethod
    def not_need_start_databus(mocker):
        """
        不需要启动清洗的状态（该系统已经running并且不需要修改）
        """
        return mocker.patch(
            "api.bkdata.default.GetDatabusCleans.perform_request", return_value=get_databus_cleans_status_running()
        )

    @staticmethod
    def need_start_databus_and_successful_start_databus_cleans(mocker):
        """
        需要启动清洗状态
        并且在轮训状态之后能正常跑起来
        """
        all_get_databus_cleans_status_return = [
            get_databus_cleans_status_stopped(),
            get_databus_cleans_status_starting(),
            get_databus_cleans_status_running(),
        ]
        mocker.patch(
            "api.bkdata.default.StartDatabusCleans.perform_request",
            return_value="任务(result_table_id：:result_table_id)启动成功!",
        )
        get_databus_cleans = mock.patch("api.bkdata.default.GetDatabusCleans.perform_request").start()
        get_databus_cleans.side_effect = all_get_databus_cleans_status_return
        return get_databus_cleans

    @staticmethod
    def need_start_databus_and_failed_start_databus_cleans(mocker):
        """
        需要启动清洗状态
        并且在轮训状态之后无法启动成功
        """
        # 这是不论咋样都无法启动成功的返回结果
        all_get_databus_cleans_status_return = [get_databus_cleans_status_stopped()]
        # all_get_databus_cleans_status_return += [get_databus_cleans_status_starting() for _ in range(40)]
        # 这是启动一半后，启动失败的结果
        all_get_databus_cleans_status_return += [get_databus_cleans_status_starting() for _ in range(15)]
        all_get_databus_cleans_status_return += [get_databus_cleans_status_stopped()]
        all_get_databus_cleans_status_return += [
            get_databus_cleans_status_starting() for _ in range(15)
        ]  # 后续多放几次，检验轮训是否成功
        mocker.patch(
            "api.bkdata.default.StartDatabusCleans.perform_request",
            return_value="任务(result_table_id：:result_table_id)启动成功!",
        )
        get_databus_cleans = mock.patch("api.bkdata.default.GetDatabusCleans.perform_request").start()
        get_databus_cleans.side_effect = all_get_databus_cleans_status_return
        return get_databus_cleans

    @staticmethod
    def gave_permission_with_rt_id(mocker):
        """
        mock对应的权限为true
        """
        return mocker.patch("api.bkdata.default.AuthProjectsDataCheck.perform_request", return_value=True)

    # =====================================【创建和启动flow】============================================
    """
    因为这里涉及到两个flow，他们对应的调用接口都相同，因此这里将前置全部拆分出来，然后根据设计的请求状态逻辑mocker对应的状态请求。
    """

    @staticmethod
    def perform_create_and_start_flow(mocker):
        """
        创建和启动flow的前置工作
        """
        # 获取bkdata中全部的flow（为了测试添加node，所以这里返回为None）
        mocker.patch("api.bkdata.default.GetDataFlowList.perform_request", return_value=None)
        # mock创建flow
        mocker.patch(
            "api.bkdata.default.CreateDataFlow.perform_request",
            return_value={
                "flow_id": 1,
                "created_at": "2018-10-13 21:57:14",
                "updated_at": "2018-10-23 17:41:17",
                "active": True,
                "flow_name": "flow01",
                "project_id": 1,
                "status": "no-start",
                "is_locked": 0,
                "latest_version": "V2018102317411792358",
                "bk_app_code": "bk_data",
                "created_by": None,
                "locked_by": None,
                "locked_at": None,
                "updated_by": "admin",
                "description": "",
            },
        )
        # mock获取画布
        mocker.patch(
            "api.bkdata.default.GetDataFlowGraph.perform_request",
            return_value={"nodes": [], "version": "", "links": []},
        )
        # mock添加节点
        mocker.patch("api.bkdata.default.AddDataFlowNode.perform_request", return_value=get_sample_node())

    @staticmethod
    def perform_no_create_and_no_start_flow(mocker):
        # 获取bkdata中全部的flow（为了测试添加node，所以这里返回为None）
        mocker.patch("api.bkdata.default.GetDataFlowList.perform_request", return_value=None)
        # mock创建flow
        mocker.patch(
            "api.bkdata.default.CreateDataFlow.perform_request",
            return_value={
                "flow_id": 1,
                "created_at": "2018-10-13 21:57:14",
                "updated_at": "2018-10-23 17:41:17",
                "active": True,
                "flow_name": "flow01",
                "project_id": 1,
                "status": "no-start",
                "is_locked": 0,
                "latest_version": "V2018102317411792358",
                "bk_app_code": "bk_data",
                "created_by": None,
                "locked_by": None,
                "locked_at": None,
                "updated_by": "admin",
                "description": "",
            },
        )
        all_node_return = [
            {
                "nodes": [
                    {
                        "node_config": {
                            "from_result_table_ids": ["2_system_mem"],
                            "result_table_id": "2_system_mem",
                            "name": "stream_source(2_system_mem)",
                        },
                        "node_id": 117,
                    },
                    {
                        "node_config": {
                            "from_result_table_ids": ["2_system_mem"],
                            "table_name": "system_mem_raw",
                            "output_name": "system_mem_raw",
                            "bk_biz_id": 2,
                            "name": "realtime(2_system_mem)",
                            "window_type": "none",
                            "sql": "SELECT `buffer`, `cached`, `free`, `pct_usable`, `pct_used`, `psc_pct_used`, "
                            "`psc_used`, `time`, `total`, `usable`, `used`, `bk_biz_id`, `bk_cloud_id`, "
                            "`bk_cmdb_level`, `bk_supplier_id`, `bk_target_cloud_id`, `bk_target_ip`, "
                            "`hostname`, `ip`\n        FROM 2_system_mem\n        WHERE (time> "
                            "UNIX_TIMESTAMP() - 3600) AND (time < UNIX_TIMESTAMP() + 60)",
                        },
                        "node_id": 117,
                    },
                    {
                        "node_config": {
                            "from_result_table_ids": ["2_system_mem_raw"],
                            "bk_biz_id": 2,
                            "result_table_id": "2_system_mem_raw",
                            "name": "tspider_storage(2_system_mem_raw)",
                            "expires": 30,
                            "cluster": "jungle_alert",
                        },
                        "node_id": 117,
                    },
                ],
                "version": "",
                "links": [],
            },
            {
                "nodes": [
                    {
                        "node_config": {
                            "from_result_table_ids": ["2_system_mem_raw"],
                            "result_table_id": "2_system_mem_raw",
                            "name": "stream_source(2_system_mem_raw)",
                        },
                        "node_id": 117,
                    },
                    {
                        "node_config": {
                            "from_result_table_ids": ["591_bkpub_cmdb_host_rels_split_innerip"],
                            "result_table_id": "591_bkpub_cmdb_host_rels_split_innerip",
                            "name": "unified_kv_source(591_bkpub_cmdb_host_rels_split_innerip)",
                        },
                        "node_id": 117,
                    },
                    {
                        "node_config": {
                            "from_result_table_ids": ["2_system_mem_raw", "591_bkpub_cmdb_host_rels_split_innerip"],
                            "output_name": "system_mem_full",
                            "table_name": "system_mem_full",
                            "name": "添加主机拓扑关系数据",
                            "bk_biz_id": 2,
                            "sql": "select  A.`buffer`, A.`cached`, A.`free`, A.`pct_usable`, A.`pct_used`, "
                            "A.`psc_pct_used`, A.`psc_used`, A.`total`, A.`usable`, A.`used`, A.`bk_biz_id`,"
                            " A.`bk_cloud_id`, A.`bk_cmdb_level`, A.`bk_supplier_id`, A.`bk_target_cloud_id`, "
                            "A.`bk_target_ip`, A.`hostname`, A.`ip`, B.bk_host_id, B.bk_relations\n           "
                            " from 2_system_mem_raw A\n\\ LEFT JOIN  591_bkpub_cmdb_host_rels_split_innerip B\n "
                            "ON  A.bk_target_cloud_id = B.bk_cloud_id and A.bk_target_ip = B.bk_host_innerip",
                            "window_type": "none",
                        },
                        "node_id": 117,
                    },
                    {
                        "node_config": {
                            "from_result_table_ids": ["2_system_mem_full"],
                            "bk_biz_id": 2,
                            "result_table_id": "2_system_mem_full",
                            "name": "tspider_storage(2_system_mem_full)",
                            "expires": 1,
                            "cluster": "jungle_alert",
                        },
                        "node_id": 117,
                    },
                    {
                        "node_config": {
                            "from_result_table_ids": ["2_system_mem_full"],
                            "output_name": "system_mem_cmdb",
                            "table_name": "system_mem_cmdb",
                            "name": "拆分拓扑关系中模块和集群",
                            "bk_biz_id": 2,
                            "sql": "select `buffer`, `cached`, `free`, `pct_usable`, `pct_used`, `psc_pct_used`, "
                            "`psc_used`, `total`, `usable`, `used`, `bk_biz_id`, `bk_cloud_id`, "
                            "`bk_cmdb_level`, `bk_supplier_id`, `bk_target_cloud_id`, `bk_target_ip`, "
                            "`hostname`, `ip`, bk_host_id, bk_relations, bk_obj_id, bk_inst_id\n "
                            "from 2_system_mem_full,\n\n lateral table(udf_bkpub_cmdb_split_set_module("
                            "bk_relations, bk_biz_id)) as T(bk_obj_id, bk_inst_id)",
                            "window_type": "none",
                        },
                        "node_id": 117,
                    },
                    {
                        "node_config": {
                            "from_result_table_ids": ["2_system_mem_cmdb"],
                            "bk_biz_id": 2,
                            "result_table_id": "2_system_mem_cmdb",
                            "name": "tspider_storage(2_system_mem_cmdb)",
                            "expires": 30,
                            "cluster": "jungle_alert",
                        },
                        "node_id": 117,
                    },
                ],
                "version": "",
                "links": [],
            },
        ]
        get_data_flow_graph = mock.patch("api.bkdata.default.GetDataFlowGraph.perform_request").start()
        get_data_flow_graph.side_effect = all_node_return

    @staticmethod
    def perform_no_create_need_start_flow(mocker):
        # 获取bkdata中全部的flow（为了测试添加node，所以这里返回为None）
        mocker.patch("api.bkdata.default.GetDataFlowList.perform_request", return_value=None)
        # mock创建flow
        mocker.patch(
            "api.bkdata.default.CreateDataFlow.perform_request",
            return_value={
                "flow_id": 1,
                "created_at": "2018-10-13 21:57:14",
                "updated_at": "2018-10-23 17:41:17",
                "active": True,
                "flow_name": "flow01",
                "project_id": 1,
                "status": "no-start",
                "is_locked": 0,
                "latest_version": "V2018102317411792358",
                "bk_app_code": "bk_data",
                "created_by": None,
                "locked_by": None,
                "locked_at": None,
                "updated_by": "admin",
                "description": "",
            },
        )
        all_node_return = [
            {
                "nodes": [
                    {
                        "node_config": {
                            "from_result_table_ids": ["2_system_mem"],
                            "result_table_id": "2_system_mem",
                            "name": "stream_source(2_system_mem)",
                        },
                        "node_id": 117,
                    },
                    {
                        "node_config": {
                            "from_result_table_ids": ["2_system_mem"],
                            "table_name": "system_mem_raw",
                            "output_name": "system_mem_raw",
                            "bk_biz_id": 2,
                            "name": "realtime(2_system_mem)",
                            "window_type": "none",
                            "sql": "SELECT `buffer`, `cached`, `free`, `pct_usable`, `pct_used`, `psc_pct_used`, "
                            "`psc_used`, `time`, `total`, `usable`, `used`, `bk_biz_id`, `bk_cloud_id`, "
                            "`bk_cmdb_level`, `bk_supplier_id`, `bk_target_cloud_id`, `bk_target_ip`, "
                            "`hostname`, `ip`\n FROM 2_system_mem\n WHERE (time> UNIX_TIMESTAMP() - 3600) "
                            "AND (time < UNIX_TIMESTAMP() + 60)",
                        },
                        "node_id": 117,
                    },
                    {
                        "node_config": {
                            "from_result_table_ids": ["2_system_mem_raw"],
                            "bk_biz_id": 2,
                            "result_table_id": "2_system_mem_raw",
                            "name": "tspider_storage(2_system_mem_raw)",
                            "expires": 30,
                            "cluster": "jungle_alert",
                        },
                        "node_id": 117,
                    },
                ],
                "version": "",
                "links": [],
            },
            {"nodes": [], "version": "", "links": []},
        ]
        get_data_flow_graph = mock.patch("api.bkdata.default.GetDataFlowGraph.perform_request").start()
        get_data_flow_graph.side_effect = all_node_return

        # mock添加节点
        mocker.patch("api.bkdata.default.AddDataFlowNode.perform_request", return_value=get_sample_node())

    def successful_time_flow_failed_cmdb_flow(self, mocker):
        """
        过滤时间flow成功、接入cmdb-flow失败
        """
        self.perform_create_and_start_flow(mocker)
        # mock查询flow的状态信息
        flow_info_list = [
            get_flow_deploy_info_no_start(),
            get_flow_deploy_info_starting(),
            get_flow_deploy_info_starting(),
            get_flow_deploy_info_success(),  # 从这里开始向下是属于cmdb-flow的状态请求
            get_flow_deploy_info_no_start(),
            get_flow_deploy_info_starting(),  # 多加几个是为了测试轮训是否成功
            get_flow_deploy_info_failed(),
            get_flow_deploy_info_starting(),
            get_flow_deploy_info_starting(),
        ]
        get_data_flow = mock.patch("api.bkdata.default.GetLatestDeployDataFlow.perform_request").start()
        get_data_flow.side_effect = flow_info_list

        # mock创建启动flo，
        start_data_flow = mocker.patch(
            "api.bkdata.default.StartDataFlow.perform_request", return_value={"task_id": 1111}
        )
        return get_data_flow, start_data_flow

    def successful_time_flow_successful_cmdb_flow(self, mocker):
        """
        过滤时间flow成功、接入cmdb-flow成功
        """
        self.perform_create_and_start_flow(mocker)
        # mock查询flow的状态信息
        flow_info_list = [
            get_flow_deploy_info_starting(),
            get_flow_deploy_info_starting(),
            get_flow_deploy_info_starting(),
            get_flow_deploy_info_starting(),
            get_flow_deploy_info_success(),  # 从这里开始向下是属于cmdb-flow的状态请求
            get_flow_deploy_info_starting(),
            get_flow_deploy_info_starting(),
            get_flow_deploy_info_starting(),
        ]
        get_data_flow = mock.patch("api.bkdata.default.GetLatestDeployDataFlow.perform_request").start()
        get_data_flow.side_effect = flow_info_list

        # mock创建启动flow
        start_data_flow = mocker.patch("bkmonitor.dataflow.flow.DataFlow.start", return_value={"task_id": 1111})
        return get_data_flow, start_data_flow

    def failed_time_flow(self, mocker):
        """
        创建和启动过滤时间flow失败
        """
        self.perform_create_and_start_flow(mocker)
        get_data_flow = mocker.patch(
            "api.bkdata.default.GetLatestDeployDataFlow.perform_request", return_value=get_flow_deploy_info_starting()
        )

        # mock创建启动flow
        start_data_flow = mocker.patch(
            "api.bkdata.default.RestartDataFlow.perform_request", return_value={"task_id": 1111}
        )
        return get_data_flow, start_data_flow

    def no_need_work_flow(self, mocker):
        """
        不需要执行任何flow操作
        """
        # 添加node
        self.perform_no_create_and_no_start_flow(mocker)

        get_data_flow = mocker.patch(
            "api.bkdata.default.GetLatestDeployDataFlow.perform_request", return_value=get_flow_deploy_info_success()
        )

        # mock创建启动flow
        start_data_flow = mocker.patch(
            "api.bkdata.default.RestartDataFlow.perform_request", return_value={"task_id": 1111}
        )
        return get_data_flow, start_data_flow

    def no_need_work_time_flow(self, mocker):
        """ "
        修改时间flow正常，cmdb异常
        """
        self.perform_no_create_need_start_flow(mocker)

        flow_info_list = [
            get_flow_deploy_info_success(),  # 从这里开始向下是属于cmdb-flow的状态请求
            get_flow_deploy_info_success(),
            get_flow_deploy_info_no_start(),
            get_flow_deploy_info_starting(),
            get_flow_deploy_info_success(),
            get_flow_deploy_info_starting(),  # 多加几个是为了测试轮训是否成功
            get_flow_deploy_info_starting(),
        ]
        get_data_flow = mock.patch("api.bkdata.default.GetLatestDeployDataFlow.perform_request").start()
        get_data_flow.side_effect = flow_info_list

        # mock创建启动flow
        start_data_flow = mocker.patch(
            "api.bkdata.default.StartDataFlow.perform_request", return_value={"task_id": 1111}
        )
        return get_data_flow, start_data_flow

    # =====================================================【所有的test合集】===============================================================
    def test_success_etl_success_start_success_flow(self, mocker):
        """
        对于一个新的storage，执行创建清洗配置、启动清洗配置、创建和启动flow
        """
        logger.info("=====start：test_success_etl_success_start_success_flow=========")
        start_etl_worker = self.successful_create_databus_cleans(mocker)
        get_databus_status = self.need_start_databus_and_successful_start_databus_cleans(mocker)
        self.gave_permission_with_rt_id(mocker)
        get_data_flow_status, start_data_flow = self.successful_time_flow_successful_cmdb_flow(mocker)
        mocker.patch("api.bkdata.default.GetDataFlow.perform_request", return_value={"status": "success"})
        mocker.patch("time.sleep", return_value=True)
        settings.IS_ALLOW_ALL_CMDB_LEVEL = True
        models.storage.BkDataStorage.objects.all().delete()
        bkdata_storage = models.storage.BkDataStorage.objects.create(table_id=self.table_id)
        bkdata_storage.raw_data_id = 1
        bkdata_storage.check_and_access_bkdata()
        start_etl_worker.assert_called_once()
        assert bkdata_storage.bk_data_result_table_id == "2_system_mem"
        assert get_databus_status.call_count == 3
        assert get_data_flow_status.call_count == 5
        assert start_data_flow.call_count == 2
        logger.info("=====end：test_success_etl_success_start_success_flow=========")

    def test_no_work(self, mocker):
        """
        测试全部正常的情况下的流程是否有跑动
        """
        logger.info("=====start：test_no_work=========")
        success_start_etl_worker = self.successful_create_databus_cleans(mocker)
        success_update_etl_worker = self.successful_update_databus_cleans(mocker)
        get_databus_status = self.not_need_start_databus(mocker)
        gave_permission = self.gave_permission_with_rt_id(mocker)
        get_data_flow_status, start_data_flow = self.no_need_work_flow(mocker)
        mocker.patch("time.sleep", return_value=True)
        bkdata_storage = models.storage.BkDataStorage.objects.get(table_id=self.table_id)
        bkdata_storage.check_and_access_bkdata()
        assert success_start_etl_worker.call_count == 0
        assert success_update_etl_worker.call_count == 0
        assert get_databus_status.call_count == 1
        assert gave_permission.call_count == 0
        assert get_data_flow_status.call_count == 0
        assert start_data_flow.call_count == 0
        logger.info("=====end：test_no_work=========")

    def test_failed_etl(self, mocker):
        """
        更新流程配置时出错，
        """
        logger.info("=====start：test_failed_etl=========")
        start_etl_worker = self.failed_update_databus_cleans(mocker)
        get_databus_status = self.need_start_databus_and_successful_start_databus_cleans(mocker)
        self.gave_permission_with_rt_id(mocker)
        get_data_flow_status, start_data_flow = self.successful_time_flow_successful_cmdb_flow(mocker)
        mocker.patch("api.bkdata.default.GetDataFlow.perform_request", return_value={"status": "success"})
        mocker.patch("time.sleep", return_value=True)
        models.storage.BkDataStorage.objects.all().delete()
        bkdata_storage = models.storage.BkDataStorage.objects.create(table_id=self.table_id)
        bkdata_storage.raw_data_id = 1
        bkdata_storage.etl_json_config = {"test_config": "test_config"}  # 修改etl_json_config，让其进入更新流程
        bkdata_storage.check_and_access_bkdata()
        start_etl_worker.assert_called_once()
        assert get_databus_status.call_count == 0
        assert get_data_flow_status.call_count == 0
        assert start_data_flow.call_count == 0

        # ==========================================错误之后重新执行一遍正确流程=================================================
        logger.info("===========根据当前数据库中的数据，重跑一次正确流程==============")
        start_etl_worker = self.successful_update_databus_cleans(mocker)  # 因为数据库中的et_json_config不匹配，所以进入update
        get_databus_status = self.need_start_databus_and_successful_start_databus_cleans(mocker)
        self.gave_permission_with_rt_id(mocker)
        get_data_flow_status, start_data_flow = self.successful_time_flow_successful_cmdb_flow(mocker)
        bkdata_storage.check_and_access_bkdata()
        start_etl_worker.assert_called_once()
        assert bkdata_storage.bk_data_result_table_id == "2_system_mem"
        assert get_databus_status.call_count == 3
        assert get_data_flow_status.call_count == 5
        assert start_data_flow.call_count == 2
        logger.info("=====end：test_failed_etl=========")

    def test_success_etl_failed_start(self, mocker):
        """
        更新流程成功，启动流程出错
        """
        logger.info("=====start：test_success_etl_failed_start=========")
        start_etl_worker = self.successful_update_databus_cleans(mocker)
        get_databus_status = self.need_start_databus_and_failed_start_databus_cleans(mocker)
        self.gave_permission_with_rt_id(mocker)
        get_data_flow_status, start_data_flow = self.successful_time_flow_successful_cmdb_flow(mocker)
        mocker.patch("api.bkdata.default.GetDataFlow.perform_request", return_value={"status": "no-start"})
        mocker.patch("api.bkdata.default.RestartDataFlow.perform_request", return_value={"status": "success"})
        mocker.patch("time.sleep", return_value=True)
        bkdata_storage, _ = models.storage.BkDataStorage.objects.get_or_create(table_id=self.table_id)
        bkdata_storage.raw_data_id = 1
        bkdata_storage.etl_json_config = {"test_config": "test_config"}  # 修改etl_json_config，让其进入更新流程
        bkdata_storage.check_and_access_bkdata()
        start_etl_worker.assert_called_once()
        assert get_databus_status.call_count == 17
        assert get_data_flow_status.call_count == 0
        assert start_data_flow.call_count == 0

        # ==========================================错误之后重新执行一遍正确流程=================================================
        logger.info("===========重跑一次正确流程==============")
        start_etl_worker = self.successful_update_databus_cleans(mocker)
        get_databus_status = self.need_start_databus_and_successful_start_databus_cleans(mocker)
        self.gave_permission_with_rt_id(mocker)
        get_data_flow_status, start_data_flow = self.successful_time_flow_successful_cmdb_flow(mocker)
        bkdata_storage.check_and_access_bkdata()
        assert start_etl_worker.call_count == 1  # 因为数据库中已经和产生的etl配置相同，但是存入数据库是在启动完成之后，所以还是会再次进入更新流程
        assert bkdata_storage.bk_data_result_table_id == "2_system_mem"
        assert get_databus_status.call_count == 3
        assert get_data_flow_status.call_count == 5
        assert start_data_flow.call_count == 2
        logger.info("=====end：test_success_etl_failed_start=========")

    def test_success_etl_sucess_start_failed_cmdb_flow(self, mocker):
        """
        接入过滤时间成功，但接入cmdb失败
        """
        logger.info("=====start：test_success_etl_sucess_start_failed_cmdb_flow=========")
        start_etl_worker = self.successful_update_databus_cleans(mocker)
        get_databus_status = self.need_start_databus_and_successful_start_databus_cleans(mocker)
        self.gave_permission_with_rt_id(mocker)
        get_data_flow_status, start_data_flow = self.successful_time_flow_failed_cmdb_flow(mocker)
        mocker.patch("api.bkdata.default.GetDataFlow.perform_request", return_value={"status": "no-start"})
        mocker.patch("api.bkdata.default.RestartDataFlow.perform_request", return_value={"status": "success"})
        mocker.patch("time.sleep", return_value=True)
        bkdata_storage, _ = models.storage.BkDataStorage.objects.get_or_create(table_id=self.table_id)
        bkdata_storage.raw_data_id = 1
        bkdata_storage.etl_json_config = {"test_config": "test_config"}  # 修改etl_json_config，让其进入更新流程
        bkdata_storage.check_and_access_bkdata()
        start_etl_worker.assert_called_once()
        assert get_databus_status.call_count == 3
        assert get_data_flow_status.call_count == 5
        assert start_data_flow.call_count == 2

        # ==========================================错误之后重新执行一遍正确流程=================================================
        logger.info("===========重跑一次正确流程==============")
        start_etl_worker = self.successful_update_databus_cleans(mocker)
        get_databus_status = self.not_need_start_databus(mocker)
        self.gave_permission_with_rt_id(mocker)
        get_data_flow_status, start_data_flow = self.successful_time_flow_successful_cmdb_flow(mocker)
        bkdata_storage.check_and_access_bkdata()
        assert start_etl_worker.call_count == 0  # 因为数据库中已经和产生的etl配置相同，所以不会重新进入更新操作
        assert bkdata_storage.bk_data_result_table_id == "2_system_mem"
        assert get_databus_status.call_count == 1
        assert get_data_flow_status.call_count == 5
        assert start_data_flow.call_count == 2
        logger.info("=====end：test_success_etl_sucess_start_failed_cmdb_flow=========")

    def test_success_etl_success_start_failed_time_flow(self, mocker):
        """
        接入过滤时间失败
        """
        logger.info("=====start：test_success_etl_success_start_failed_time_flow=========")
        start_etl_worker = self.successful_update_databus_cleans(mocker)
        get_databus_status = self.need_start_databus_and_successful_start_databus_cleans(mocker)
        self.gave_permission_with_rt_id(mocker)
        get_data_flow_status, start_data_flow = self.failed_time_flow(mocker)
        mocker.patch("api.bkdata.default.GetDataFlow.perform_request", return_value={"status": "success"})
        mocker.patch("time.sleep", return_value=True)
        bkdata_storage, _ = models.storage.BkDataStorage.objects.get_or_create(table_id=self.table_id)
        bkdata_storage.raw_data_id = 1
        bkdata_storage.etl_json_config = {"test_config": "test_config"}  # 修改etl_json_config，让其进入更新流程
        bkdata_storage.check_and_access_bkdata()
        start_etl_worker.assert_called_once()
        assert get_databus_status.call_count == 3
        assert get_data_flow_status.call_count == 61
        assert start_data_flow.call_count == 1

        # ==========================================错误之后重新执行一遍正确流程=================================================
        logger.info("===========重跑一次正确流程==============")
        start_etl_worker = self.successful_update_databus_cleans(mocker)
        get_databus_status = self.not_need_start_databus(mocker)
        self.gave_permission_with_rt_id(mocker)
        get_data_flow_status, start_data_flow = self.no_need_work_time_flow(mocker)
        bkdata_storage.check_and_access_bkdata()
        assert start_etl_worker.call_count == 0  # 因为数据库中已经和产生的etl配置相同，所以不会重新进入更新操作
        assert bkdata_storage.bk_data_result_table_id == "2_system_mem"
        assert get_databus_status.call_count == 1
        assert get_data_flow_status.call_count == 0
        assert start_data_flow.call_count == 0
        logger.info("=====end：test_success_etl_success_start_failed_time_flow=========")
