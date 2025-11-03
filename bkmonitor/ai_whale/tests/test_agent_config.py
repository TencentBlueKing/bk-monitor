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
from aidev_agent.api import BKAidevApi
from ai_whale.models import AgentConfigManager

pytestmark = pytest.mark.django_db


def test_retrieve_agent_config():
    client = BKAidevApi.get_client()

    res = client.api.retrieve_agent_config(path_params={"agent_code": "aidev-metadata"})["data"]

    assert res["agent_code"] == "aidev-metadata"


def test_agent_config_manager():
    config = AgentConfigManager.get_config("aidev-metadata")
    assert config.agent_code == "aidev-metadata"
    assert config.agent_name == "metadata-agent"
