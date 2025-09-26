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

from core.drf_resource import api


class TestFetchClustersResource:
    """测试获得集群列表 ."""

    def test_perform_request(self, monkeypatch_cluster_management_fetch_clusters):
        actual = api.bcs_cluster_manager.fetch_clusters()
        expect = [
            {
                'businessID': '2',
                'clusterID': 'BCS-K8S-00000',
                'clusterName': '蓝鲸社区版7.0',
                'clusterType': 'single',
                'createTime': '2022-01-01T00:00:00+08:00',
                'creator': 'admin',
                'description': '蓝鲸社区版7.0集群',
                'engineType': 'k8s',
                'environment': 'prod',
                'is_shared': False,
                'labels': {},
                'master': {
                    '1.1.1.1': {
                        'CPU': 0,
                        'GPU': 0,
                        'VPC': '',
                        'clusterID': '',
                        'deviceID': '',
                        'innerIP': '1.1.1.1',
                        'instanceType': '',
                        'mem': 0,
                        'nodeGroupID': '',
                        'nodeID': '',
                        'passwd': '',
                        'region': 'default',
                        'status': '',
                        'zone': 0,
                        'zoneID': '',
                    }
                },
                'networkType': 'overlay',
                'projectID': '0000000000',
                'status': 'RUNNING',
                'updateTime': '2022-01-01T00:00:00+08:00',
            },
            {
                'businessID': '100',
                'clusterID': 'BCS-K8S-00002',
                'clusterName': '共享集群',
                'clusterType': 'single',
                'createTime': '2022-01-01T00:00:00+08:00',
                'creator': 'admin',
                'description': '共享集群',
                'engineType': 'k8s',
                'environment': 'prod',
                'is_shared': True,
                'labels': {},
                'master': {
                    '1.1.1.1': {
                        'CPU': 0,
                        'GPU': 0,
                        'VPC': '',
                        'clusterID': '',
                        'deviceID': '',
                        'innerIP': '1.1.1.1',
                        'instanceType': '',
                        'mem': 0,
                        'nodeGroupID': '',
                        'nodeID': '',
                        'passwd': '',
                        'region': 'default',
                        'status': '',
                        'zone': 0,
                        'zoneID': '',
                    }
                },
                'networkType': 'overlay',
                'projectID': '2222222222',
                'status': 'RUNNING',
                'updateTime': '2022-01-01T00:00:00+08:00',
            },
        ]
        assert actual == expect
