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
import mock
import pytest
from apm_web.models import Application, ApplicationRelationInfo


@pytest.fixture(autouse=True)
def create_application(db):
    param = {
        "application_id": 10,
        "bk_biz_id": 2,
        "app_name": "test_demo",
        "app_alias": "test_demo",
        "description": "this is demo",
        "metric_result_table_id": "2_bkapm_metric_test_demo.__default__",
        "trace_result_table_id": "2_bkapm.trace_test_demo",
        "time_series_group_id": 13,
    }
    Application.objects.create(**param)

    need_create_application_relation_infos = {
        (10, "plugin", "opentelemetry"),
        (10, "deployment", "centos"),
        (10, "language", "java"),
    }

    ApplicationRelationInfo.objects.bulk_create(
        [
            ApplicationRelationInfo(
                application_id=i[0],
                relation_key=i[1],
                relation_value=i[2],
            )
            for i in need_create_application_relation_infos
        ]
    )


@pytest.fixture(autouse=True)
def get_rules():
    return_value = {
        "id": 4,
        "bk_biz_id": 0,
        "app_name": "",
        "category_id": "db",
        "endpoint_key": "span_name",
        "instance_key": "attributes.db.system,attributes.net.peer.name,attributes.net.peer.ip,attributes.net.peer.port",
        "topo_kind": "component",
        "predicate_key": "attributes.db.system",
    }
    mock.patch("apm_web.handlers.db_handler.DbInstanceHandler.get_rules", return_value=return_value).start()


@pytest.fixture(autouse=True)
def get_param():
    mock.patch(
        "apm_web.handlers.db_handler.DbComponentHandler.build_component_filter_params", return_value=None
    ).start()
