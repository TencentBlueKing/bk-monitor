# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import pytest

from api.metadata.default import GetClustersBySpaceUidResource
from bkmonitor.utils.kubernetes import translate_timestamp_since
from core.drf_resource import resource
from monitor_web.constants import OVERVIEW_ICON

COLUMNS = [
    {
        'checked': True,
        'disabled': False,
        'id': 'bcs_cluster_id',
        'max_width': 300,
        'min_width': 120,
        'name': '集群ID',
        'overview_name': '概览',
        'type': 'link',
        'width': 248,
    },
    {
        'checked': True,
        'disabled': False,
        'header_pre_icon': 'icon-avg',
        'id': 'cpu_usage_ratio',
        'min_width': 120,
        'name': 'CPU使用率',
        'sortable': False,
        'type': 'progress',
    },
    {'checked': True, 'disabled': False, 'id': 'name', 'min_width': 120, 'name': '集群名称', 'type': 'string'},
    {
        'checked': True,
        'disabled': False,
        'filter_list': [{'text': 'RUNNING', 'value': 'RUNNING'}],
        'filterable': True,
        'id': 'status',
        'min_width': 120,
        'name': '运行状态',
        'type': 'string',
    },
    {'checked': False, 'disabled': False, 'id': 'monitor_status', 'min_width': 120, 'name': '采集状态', 'type': 'status'},
    {'checked': False, 'disabled': False, 'id': 'environment', 'min_width': 120, 'name': '环境', 'type': 'string'},
    {
        'checked': True,
        'disabled': False,
        'id': 'node_count',
        'min_width': 120,
        'name': '节点数量',
        'sortable': False,
        'type': 'number',
    },
    {
        'checked': True,
        'disabled': False,
        'header_pre_icon': 'icon-avg',
        'id': 'memory_usage_ratio',
        'min_width': 120,
        'name': '内存使用率',
        'sortable': False,
        'type': 'progress',
    },
    {
        'checked': True,
        'disabled': False,
        'header_pre_icon': 'icon-avg',
        'id': 'disk_usage_ratio',
        'min_width': 120,
        'name': '磁盘使用率',
        'sortable': False,
        'type': 'progress',
    },
    {'checked': False, 'disabled': False, 'id': 'area_name', 'min_width': 120, 'name': '区域', 'type': 'string'},
    {'checked': True, 'disabled': False, 'id': 'created_at', 'min_width': 120, 'name': '创建时间', 'type': 'string'},
    {'checked': True, 'disabled': False, 'id': 'updated_at', 'min_width': 120, 'name': '更新时间', 'type': 'string'},
    {'checked': False, 'disabled': False, 'id': 'project_name', 'min_width': 120, 'name': '所属项目', 'type': 'string'},
    {'checked': False, 'disabled': False, 'id': 'description', 'min_width': 120, 'name': '描述', 'type': 'string'},
]
OVERVIEW_DATA = {
    'area_name': '',
    'bcs_cluster_id': {
        'icon': OVERVIEW_ICON,
        'key': '',
        'target': 'null_event',
        'url': '',
        'value': '概览',
    },
    'cpu_usage_ratio': {'label': '37.98%', 'status': 'SUCCESS', 'value': 37.98},
    'created_at': '',
    'description': '',
    'disk_usage_ratio': {'label': '37.98%', 'status': 'SUCCESS', 'value': 37.98},
    'environment': '',
    'memory_usage_ratio': {'label': '37.98%', 'status': 'SUCCESS', 'value': 37.98},
    'monitor_status': '',
    'name': '',
    'node_count': 3,
    'project_name': '',
    'status': '',
    'updated_at': '',
}
SORT = [
    {'id': 'node_count', 'name': '节点数量'},
    {'id': 'cpu_usage_ratio', 'name': 'CPU使用率'},
    {'id': 'memory_usage_ratio', 'name': '内存使用率'},
    {'id': 'disk_usage_ratio', 'name': '磁盘使用率'},
]
FILTER = [
    {'id': 'success', 'name': 1, 'status': 'success', 'tips': '正常'},
    {'id': 'failed', 'name': 0, 'status': 'failed', 'tips': '异常'},
    {'id': 'disabled', 'name': 0, 'status': 'disabled', 'tips': '无数据'},
]
DATA = [
    {
        'area_name': '',
        'bcs_cluster_id': {
            'display_value': '蓝鲸社区版7.0(BCS-K8S-00002)',
            'icon': '',
            'key': '',
            'target': 'null_event',
            'url': '',
            'value': 'BCS-K8S-00002',
        },
        'cpu_usage_ratio': {'label': '37.98%', 'status': 'SUCCESS', 'value': 37.98},
        'created_at': translate_timestamp_since('2022-01-01T00:00:00Z'),
        'description': '',
        'disk_usage_ratio': {'label': '37.98%', 'status': 'SUCCESS', 'value': 37.98},
        'environment': '正式',
        'memory_usage_ratio': {'label': '37.98%', 'status': 'SUCCESS', 'value': 37.98},
        'monitor_status': {'text': '正常', 'type': 'success'},
        'name': '蓝鲸社区版7.0',
        'node_count': 3,
        'project_name': '',
        'status': 'RUNNING',
        'updated_at': translate_timestamp_since('2022-01-01T00:00:00Z'),
    }
]


@pytest.mark.django_db(databases=["default", "monitor_api"])
class TestGetKubernetesClusterList:
    def test_perform_request(
        self,
        add_bcs_cluster_item_for_update_and_delete,
    ):
        params = {
            "page": 1,
            "page_size": 10,
            "condition_list": [{"bcs_cluster_id": "BCS-K8S-00002"}],
            "bk_biz_id": 100,
            "sort": "-cpu_usage_ratio",
        }
        actual = resource.scene_view.get_kubernetes_cluster_list(params)
        expect = {
            'columns': COLUMNS,
            'condition_list': [],
            'data': DATA,
            'filter': FILTER,
            'overview_data': OVERVIEW_DATA,
            'sort': SORT,
            'total': 1,
        }
        assert actual == expect

    def test_overview_ratio(self, add_bcs_cluster_item_for_update_and_delete):
        """测试概览的使用率数据为平均值。"""
        params = {
            "page": 1,
            "page_size": 10,
            "bk_biz_id": 2,
        }
        actual = resource.scene_view.get_kubernetes_cluster_list(params)
        assert actual["overview_data"]["cpu_usage_ratio"]["value"] == 36.48

    def test_perform_request_with_condition_by_space_id(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_cluster_item_for_update_and_delete,
    ):
        params = {
            "page": 1,
            "page_size": 10,
            "condition_list": [{"bcs_cluster_id": "BCS-K8S-00002"}],
            "bk_biz_id": -3,
            "sort": "-cpu_usage_ratio",
        }
        actual = resource.scene_view.get_kubernetes_cluster_list(params)
        expect = {
            'columns': COLUMNS,
            'condition_list': [],
            'data': [
                {
                    'area_name': '',
                    'bcs_cluster_id': {
                        'display_value': '蓝鲸社区版7.0(BCS-K8S-00002)',
                        'icon': '',
                        'key': '',
                        'target': 'null_event',
                        'url': '',
                        'value': 'BCS-K8S-00002',
                    },
                    'cpu_usage_ratio': {'label': '', 'status': 'NODATA', 'value': 0},
                    'created_at': translate_timestamp_since('2022-01-01T00:00:00Z'),
                    'description': '',
                    'disk_usage_ratio': {'label': '', 'status': 'NODATA', 'value': 0},
                    'environment': '正式',
                    'memory_usage_ratio': {'label': '', 'status': 'NODATA', 'value': 0},
                    'monitor_status': {'text': '正常', 'type': 'success'},
                    'name': '蓝鲸社区版7.0',
                    'node_count': None,
                    'project_name': '',
                    'status': 'RUNNING',
                    'updated_at': translate_timestamp_since('2022-01-01T00:00:00Z'),
                }
            ],
            'filter': FILTER,
            'overview_data': {
                'area_name': '',
                'bcs_cluster_id': {
                    'icon': OVERVIEW_ICON,
                    'key': '',
                    'target': 'null_event',
                    'url': '',
                    'value': '概览',
                },
                'cpu_usage_ratio': {'label': '35.98%', 'status': 'SUCCESS', 'value': 35.98},
                'created_at': '',
                'description': '',
                'disk_usage_ratio': {'label': '35.98%', 'status': 'SUCCESS', 'value': 35.98},
                'environment': '',
                'memory_usage_ratio': {'label': '35.98%', 'status': 'SUCCESS', 'value': 35.98},
                'monitor_status': '',
                'name': '',
                'node_count': 1,
                'project_name': '',
                'status': '',
                'updated_at': '',
            },
            'sort': SORT,
            'total': 1,
        }
        assert actual == expect

    def test_perform_request_by_space_id(
        self,
        monkeypatch_get_space_detail,
        monkeypatch_get_clusters_by_space_uid,
        add_bcs_cluster_item_for_update_and_delete,
    ):
        params = {
            "page": 1,
            "page_size": 10,
            "bk_biz_id": -3,
            "sort": "-cpu_usage_ratio",
        }
        actual = resource.scene_view.get_kubernetes_cluster_list(params)
        expect = {
            'columns': COLUMNS,
            'condition_list': [],
            'data': [
                {
                    'area_name': '',
                    'bcs_cluster_id': {
                        'display_value': '蓝鲸社区版7.0(BCS-K8S-00002)',
                        'icon': '',
                        'key': '',
                        'target': 'null_event',
                        'url': '',
                        'value': 'BCS-K8S-00002',
                    },
                    'cpu_usage_ratio': {'label': '', 'status': 'NODATA', 'value': 0},
                    'created_at': translate_timestamp_since('2022-01-01T00:00:00Z'),
                    'description': '',
                    'disk_usage_ratio': {'label': '', 'status': 'NODATA', 'value': 0},
                    'environment': '正式',
                    'memory_usage_ratio': {'label': '', 'status': 'NODATA', 'value': 0},
                    'monitor_status': {'text': '正常', 'type': 'success'},
                    'name': '蓝鲸社区版7.0',
                    'node_count': None,
                    'project_name': '',
                    'status': 'RUNNING',
                    'updated_at': translate_timestamp_since('2022-01-01T00:00:00Z'),
                },
                {
                    'area_name': '',
                    'bcs_cluster_id': {
                        'display_value': '蓝鲸社区版7.0(BCS-K8S-00000)',
                        'icon': '',
                        'key': '',
                        'target': 'null_event',
                        'url': '',
                        'value': 'BCS-K8S-00000',
                    },
                    'cpu_usage_ratio': {'label': '35.98%', 'status': 'SUCCESS', 'value': 35.98},
                    'created_at': translate_timestamp_since('2022-01-01T00:00:00Z'),
                    'description': '',
                    'disk_usage_ratio': {'label': '35.98%', 'status': 'SUCCESS', 'value': 35.98},
                    'environment': '正式',
                    'memory_usage_ratio': {'label': '35.98%', 'status': 'SUCCESS', 'value': 35.98},
                    'monitor_status': {'text': '正常', 'type': 'success'},
                    'name': '蓝鲸社区版7.0',
                    'node_count': 1,
                    'project_name': '',
                    'status': 'RUNNING',
                    'updated_at': translate_timestamp_since('2022-01-01T00:00:00Z'),
                },
            ],
            'filter': [
                {'id': 'success', 'name': 2, 'status': 'success', 'tips': '正常'},
                {'id': 'failed', 'name': 0, 'status': 'failed', 'tips': '异常'},
                {'id': 'disabled', 'name': 0, 'status': 'disabled', 'tips': '无数据'},
            ],
            'overview_data': {
                'area_name': '',
                'bcs_cluster_id': {
                    'icon': OVERVIEW_ICON,
                    'key': '',
                    'target': 'null_event',
                    'url': '',
                    'value': '概览',
                },
                'cpu_usage_ratio': {'label': '35.98%', 'status': 'SUCCESS', 'value': 35.98},
                'created_at': '',
                'description': '',
                'disk_usage_ratio': {'label': '35.98%', 'status': 'SUCCESS', 'value': 35.98},
                'environment': '',
                'memory_usage_ratio': {'label': '35.98%', 'status': 'SUCCESS', 'value': 35.98},
                'monitor_status': '',
                'name': '',
                'node_count': 1,
                'project_name': '',
                'status': '',
                'updated_at': '',
            },
            'sort': SORT,
            'total': 2,
        }
        assert actual == expect

    def test_no_cluster(
        self,
        monkeypatch,
        monkeypatch_get_space_detail,
        add_bcs_cluster_item_for_update_and_delete,
    ):
        monkeypatch.setattr(
            GetClustersBySpaceUidResource,
            "perform_request",
            lambda *args, **kwargs: [],
        )

        params = {
            "page": 1,
            "page_size": 10,
            "bk_biz_id": -3,
            "sort": "-cpu_usage_ratio",
        }
        actual = resource.scene_view.get_kubernetes_cluster_list(params)
        expect = {
            'columns': [
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'bcs_cluster_id',
                    'max_width': 300,
                    'min_width': 120,
                    'name': '集群ID',
                    'overview_name': '概览',
                    'type': 'link',
                    'width': 248,
                },
                {
                    'checked': True,
                    'disabled': False,
                    'header_pre_icon': 'icon-avg',
                    'id': 'cpu_usage_ratio',
                    'min_width': 120,
                    'name': 'CPU使用率',
                    'sortable': False,
                    'type': 'progress',
                },
                {'checked': True, 'disabled': False, 'id': 'name', 'min_width': 120, 'name': '集群名称', 'type': 'string'},
                {
                    'checked': True,
                    'disabled': False,
                    'filter_list': [],
                    'filterable': True,
                    'id': 'status',
                    'min_width': 120,
                    'name': '运行状态',
                    'type': 'string',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'monitor_status',
                    'min_width': 120,
                    'name': '采集状态',
                    'type': 'status',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'environment',
                    'min_width': 120,
                    'name': '环境',
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'node_count',
                    'min_width': 120,
                    'name': '节点数量',
                    'sortable': False,
                    'type': 'number',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'header_pre_icon': 'icon-avg',
                    'id': 'memory_usage_ratio',
                    'min_width': 120,
                    'name': '内存使用率',
                    'sortable': False,
                    'type': 'progress',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'header_pre_icon': 'icon-avg',
                    'id': 'disk_usage_ratio',
                    'min_width': 120,
                    'name': '磁盘使用率',
                    'sortable': False,
                    'type': 'progress',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'area_name',
                    'min_width': 120,
                    'name': '区域',
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'created_at',
                    'min_width': 120,
                    'name': '创建时间',
                    'type': 'string',
                },
                {
                    'checked': True,
                    'disabled': False,
                    'id': 'updated_at',
                    'min_width': 120,
                    'name': '更新时间',
                    'type': 'string',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'project_name',
                    'min_width': 120,
                    'name': '所属项目',
                    'type': 'string',
                },
                {
                    'checked': False,
                    'disabled': False,
                    'id': 'description',
                    'min_width': 120,
                    'name': '描述',
                    'type': 'string',
                },
            ],
            'condition_list': [],
            'data': [],
            'filter': [
                {'id': 'success', 'name': 0, 'status': 'success', 'tips': '正常'},
                {'id': 'failed', 'name': 0, 'status': 'failed', 'tips': '异常'},
                {'id': 'disabled', 'name': 0, 'status': 'disabled', 'tips': '无数据'},
            ],
            'overview_data': {
                'area_name': '',
                'bcs_cluster_id': {
                    'icon': OVERVIEW_ICON,
                    'key': '',
                    'target': 'null_event',
                    'url': '',
                    'value': '概览',
                },
                'cpu_usage_ratio': {'label': '', 'status': 'SUCCESS', 'value': 0},
                'created_at': '',
                'description': '',
                'disk_usage_ratio': {'label': '', 'status': 'NODATA', 'value': 0},
                'environment': '',
                'memory_usage_ratio': {'label': '', 'status': 'NODATA', 'value': 0},
                'monitor_status': '',
                'name': '',
                'node_count': None,
                'project_name': '',
                'status': '',
                'updated_at': '',
            },
            'sort': SORT,
            'total': 0,
        }
        assert actual == expect
