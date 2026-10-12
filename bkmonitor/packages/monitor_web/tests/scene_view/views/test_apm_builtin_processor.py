"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest

from apm_web.constants import TopoNodeKind
from apm_web.handlers.service_handler import ServiceHandler
from monitor_web.models.scene_view import SceneViewOrderModel
from monitor_web.scene_view.builtin import apm
from monitor_web.scene_view.builtin.apm import ApmBuiltinProcessor


class TestApmBuiltinProcessor:
    @pytest.mark.parametrize(
        ("llm_biz_list", "is_support_llm", "expected_ids"),
        [
            (
                [2],
                True,
                [
                    "service-default-overview",
                    "service-default-trace",
                    "service-llm_overview",
                    "service-llm_session",
                ],
            ),
            ([2], False, ["service-default-overview", "service-default-trace"]),
            ([3], True, ["service-default-overview", "service-default-trace"]),
            (
                [0],
                True,
                [
                    "service-default-overview",
                    "service-default-trace",
                    "service-llm_overview",
                    "service-llm_session",
                ],
            ),
        ],
    )
    def test_list_view_list_filters_llm_tabs(self, monkeypatch, llm_biz_list, is_support_llm, expected_ids):
        node = {
            "topo_key": "service-a",
            "extra_data": {"kind": TopoNodeKind.SERVICE, "category": "default"},
        }
        views = [
            SimpleNamespace(id="service-default-overview"),
            SimpleNamespace(id="service-default-trace"),
            SimpleNamespace(id="service-llm_overview"),
            SimpleNamespace(id="service-llm_session"),
        ]

        monkeypatch.setattr(ServiceHandler, "get_node", lambda *_args, **_kwargs: node)
        monkeypatch.setattr(apm, "settings", SimpleNamespace(LLM_BIZ_LIST=llm_biz_list))
        monkeypatch.setattr(ServiceHandler, "get_system", lambda _node: {"is_support_llm": is_support_llm})

        result = ApmBuiltinProcessor.list_view_list(
            "apm_service",
            views,
            {
                "bk_biz_id": 2,
                "apm_app_name": "app-a",
                "apm_service_name": "service-a",
            },
        )

        assert [view.id for view in result] == expected_ids

    def test_llm_tabs_flow_service_without_llm_metadata(self, monkeypatch):
        node = {
            "topo_key": "flow-service",
            "extra_data": {"kind": TopoNodeKind.SERVICE, "category": "default"},
        }
        views = [
            SimpleNamespace(id="service-default-overview"),
            SimpleNamespace(id="service-default-trace"),
            SimpleNamespace(id="service-llm_overview"),
            SimpleNamespace(id="service-llm_session"),
        ]

        monkeypatch.setattr(ServiceHandler, "get_node", lambda *_args, **_kwargs: node)
        monkeypatch.setattr(apm, "settings", SimpleNamespace(LLM_BIZ_LIST=[2]))

        result = ApmBuiltinProcessor.list_view_list(
            "apm_service",
            views,
            {
                "bk_biz_id": 2,
                "apm_app_name": "app-a",
                "apm_service_name": "flow-service",
            },
        )

        assert [view.id for view in result] == ["service-default-overview", "service-default-trace"]

    @pytest.mark.django_db
    def test_llm_tabs_follow_overview(self):
        ApmBuiltinProcessor.create_default_apm_order(2, "apm_service")

        order = SceneViewOrderModel.objects.get(bk_biz_id=2, scene_id="apm_service", type="").config

        assert order[:3] == ["overview", "llm_overview", "llm_session"]

    @pytest.mark.parametrize(
        "view_id",
        ["service-llm_overview", "service-llm_session"],
    )
    def test_llm_tab_includes_service_params(self, view_id):
        config = {"id": view_id}

        ApmBuiltinProcessor.handle_view_list_config("apm_service", config)

        assert config["params"] == {
            "apm_app_name": "${app_name}",
            "apm_service_name": "${service_name}",
        }

    @pytest.mark.parametrize(
        ("filename", "view_id", "name"),
        [
            ("apm_service-service-llm_overview", "llm_overview", "LLM概览"),
            ("apm_service-service-llm_session", "llm_session", "LLM会话"),
        ],
    )
    def test_llm_view_config_matches_contract(self, filename, view_id, name):
        config = ApmBuiltinProcessor._read_builtin_view_config(filename)

        assert filename in ApmBuiltinProcessor.filenames
        assert config["id"] == view_id
        assert config["name"] == name
        assert config["mode"] == "auto"
        assert config["panels"] == []
        assert config["options"] == {}
