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
import copy

import pytest
from django.conf import settings

from alarm_backends.core.cache.bcs_cluster import BcsClusterCacheManager
from alarm_backends.service.alert.enricher.translator.base import TranslationField
from alarm_backends.service.alert.enricher.translator.bcs_cluster import (
    BcsClusterTranslator,
)
from api.kubernetes.default import FetchK8sClusterListResource

pytestmark = pytest.mark.django_db

STRATEGY = {
    "source": "bk_monitorv3",
    "scenario": "kubernetes",
    "items": [
        {
            "query_configs": [
                {
                    "data_type_label": "time_series",
                    "data_source_label": "bk_monitor",
                },
                {
                    "data_type_label": "time_series",
                    "data_source_label": "bk_monitor",
                },
            ],
        }
    ],
}


class TestBcsClusterTranslator:
    def test_translate(self, monkeypatch, monkeypatch_cluster_management_fetch_clusters):
        monkeypatch.setattr(settings, "BCS_CLUSTER_SOURCE", "cluster-manager")
        monkeypatch.setattr(FetchK8sClusterListResource, "cache_type", None)

        BcsClusterCacheManager.refresh()

        translators = []
        for item in STRATEGY["items"]:
            translator = BcsClusterTranslator(
                item=item,
                strategy=STRATEGY,
            )
        if translator.is_enabled():
            translators.append(translator)

        def translate(data):
            data = copy.deepcopy(data)
            translated_data = {}
            for name, value in list(data.items()):
                translated_data[name] = TranslationField(name, value)
            for translator in translators:
                translated_data = translator.translate(translated_data)

            for name, value in list(translated_data.items()):
                translated_data[name] = value.to_dict()
            return translated_data

        dimensions = {
            "pod": "pod_name",
            "container": "container_name",
            "namespace": "default",
            "bcs_cluster_id": "BCS-K8S-00000",
        }
        actual = translate(dimensions)
        expect = {
            'bcs_cluster_id': {
                'display_name': 'bcs_cluster_id',
                'display_value': 'BCS-K8S-00000(蓝鲸社区版7.0)',
                'value': 'BCS-K8S-00000',
            },
            'container': {'display_name': 'container', 'display_value': 'container_name', 'value': 'container_name'},
            'namespace': {'display_name': 'namespace', 'display_value': 'default', 'value': 'default'},
            'pod': {'display_name': 'pod', 'display_value': 'pod_name', 'value': 'pod_name'},
        }
        assert actual == expect

        dimensions_2 = {
            "pod": "pod_name",
            "container": "container_name",
            "namespace": "default",
            "bcs_cluster_id": "BCS-K8S-00001",
        }
        actual = translate(dimensions_2)
        expect = {
            'bcs_cluster_id': {
                'display_name': 'bcs_cluster_id',
                'display_value': 'BCS-K8S-00001',
                'value': 'BCS-K8S-00001',
            },
            'container': {'display_name': 'container', 'display_value': 'container_name', 'value': 'container_name'},
            'namespace': {'display_name': 'namespace', 'display_value': 'default', 'value': 'default'},
            'pod': {'display_name': 'pod', 'display_value': 'pod_name', 'value': 'pod_name'},
        }
        assert actual == expect
