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
from django.core.management import CommandError, call_command

from metadata import models

from .conftest import DEFAULT_DATA_ID, DEFAULT_MQ_CLUSTER_ID_ONE

pytestmark = pytest.mark.django_db


def test_failed_switch_kafka_cluster(create_and_delete_record):
    # 不传递参数
    with pytest.raises(CommandError):
        call_command("switch_kafka_for_data_id")

    # 传递错误参数
    with pytest.raises(CommandError):
        call_command("switch_kafka_for_data_id", "--data_ids=-1")
    with pytest.raises(CommandError):
        call_command("switch_kafka_for_data_id", f"--data_ids={DEFAULT_DATA_ID}", "--kafka_cluster_id=-1")


def test_successful_switch_kafka_cluster(create_and_delete_record, mocker):
    mocker.patch("metadata.models.DataSource.refresh_outer_config", return_value=True)
    call_command(
        "switch_kafka_for_data_id", f"--data_ids={DEFAULT_DATA_ID}", f"--kafka_cluster_id={DEFAULT_MQ_CLUSTER_ID_ONE}"
    )

    # 测试 datasource mq 队列
    obj = models.DataSource.objects.get(bk_data_id=DEFAULT_DATA_ID)
    assert obj.mq_cluster_id == DEFAULT_MQ_CLUSTER_ID_ONE
