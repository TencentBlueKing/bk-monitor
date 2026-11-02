"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from elasticsearch_dsl import AttrDict

from alarm_backends.core.cache.result_table import ResultTableCacheManager
from alarm_backends.core.context.alarm import Alarm
from alarm_backends.service.alert.enricher import translator
from alarm_backends.service.alert.enricher.dimension import MonitorTranslateEnricher
from alarm_backends.service.alert.enricher.translator import base
from alarm_backends.service.alert.enricher.translator.apm import ApmTranslator
from alarm_backends.service.alert.enricher.translator.base import TranslationField
from alarm_backends.service.alert.enricher.translator.result_table import ResultTableTranslator
from bkmonitor.utils.template import Jinja2Renderer


@pytest.fixture
def apm_strategy(monkeypatch):
    monkeypatch.setattr(base, "bk_biz_id_to_bk_tenant_id", lambda biz_id: "system")
    return {
        "bk_biz_id": 2,
        "items": [
            {
                "query_configs": [
                    {
                        "data_source_label": "custom",
                        "data_type_label": "time_series",
                        "result_table_id": "2_bkapm_metric_demo.__default__",
                    }
                ]
            }
        ],
    }


@pytest.mark.parametrize(
    "name,alias,expected",
    [
        ("base62Mm45BOZ5eM2yBMRzB", None, "所属品牌"),
        ("base62Mm45BOZ5eM2yBMRzB", "base62Mm45BOZ5eM2yBMRzB", "所属品牌"),
        ("base62Mm45BOZ5eM2yBMRzB", "品牌别名", "品牌别名"),
        ("base62Mm45BOZ5eM2yBMRzB", "", "所属品牌"),
        ("base62L6Z57G75BOZ5pm45", None, "物品类型"),
        ("namespace", None, "物理环境"),
        ("base62", None, "base62"),
        ("base62invalid!", None, "base62invalid!"),
    ],
)
def test_apm_dimension_translation_preserves_alias_and_identity(apm_strategy, name, alias, expected):
    field = TranslationField(name, 0, display_name=alias, display_value=0)
    apm_translator = ApmTranslator(item=apm_strategy["items"][0], strategy=apm_strategy)

    assert apm_translator.is_enabled()
    result = apm_translator.translate({name: field})

    assert result[name].display_name == expected
    assert result[name].name == name
    assert result[name].value == 0
    assert result[name].display_value == 0


def test_apm_dimension_translation_preserves_cluster_namespace(apm_strategy):
    fields = {
        "namespace": TranslationField("namespace", "demo", display_name="集群命名空间"),
        "bcs_cluster_id": TranslationField("bcs_cluster_id", "cluster"),
    }
    apm_translator = ApmTranslator(item=apm_strategy["items"][0], strategy=apm_strategy)

    assert apm_translator.translate(fields)["namespace"].display_name == "集群命名空间"


@pytest.mark.parametrize("use_action", [False, True])
@pytest.mark.parametrize(
    "alias,expected_name",
    [(None, "所属品牌"), ("", "所属品牌"), ("base62Mm45BOZ5eM2yBMRzB", "所属品牌"), ("业务品牌", "业务品牌")],
)
def test_new_apm_alert_and_notice_use_translated_names(monkeypatch, apm_strategy, alias, expected_name, use_action):
    name = "base62Mm45BOZ5eM2yBMRzB"
    rt_info = {"fields": [{"field_name": name, "field_alias": alias}]} if alias is not None else None
    monkeypatch.setattr(ResultTableCacheManager, "get_result_table_by_id", lambda *args: rt_info)
    monkeypatch.setattr(translator, "INSTALLED_TRANSLATORS", (ResultTableTranslator, ApmTranslator))
    origin = {"data": {"dimensions": {name: "22"}}}
    alert = SimpleNamespace(
        dimensions=[{"key": f"tags.{name}", "value": "22"}],
        get_extra_info=lambda key: {"strategy": apm_strategy, "origin_alarm": origin}[key],
        is_new=lambda: True,
    )

    assert MonitorTranslateEnricher([alert]).enrich() == [alert]

    assert origin["dimension_translation"][name] == {
        "display_name": expected_name,
        "display_value": "22",
        "value": "22",
    }
    assert alert.dimensions == [
        {"key": f"tags.{name}", "display_key": expected_name, "display_value": "22", "value": "22"}
    ]
    notice_alert = SimpleNamespace(
        dimensions=[AttrDict(d) for d in alert.dimensions], agg_dimensions=[name], origin_alarm=origin
    )
    action = SimpleNamespace(dimensions=deepcopy(alert.dimensions) if use_action else [])
    alarm = Alarm(SimpleNamespace(action=action, alert=notice_alert, notice_way="mail", limit=False))

    assert Jinja2Renderer.render("{{ alarm.dimension_string }}", {"alarm": alarm}) == f"{expected_name}=22"


def test_non_apm_alert_keeps_existing_dimension_translation(monkeypatch, apm_strategy):
    apm_strategy["items"][0]["query_configs"][0]["result_table_id"] = "system.cpu"
    monkeypatch.setattr(ResultTableCacheManager, "get_result_table_by_id", lambda *args: None)
    monkeypatch.setattr(translator, "INSTALLED_TRANSLATORS", (ResultTableTranslator, ApmTranslator))
    name = "base62Mm45BOZ5eM2yBMRzB"

    result = translator.TranslatorFactory(apm_strategy).translate({name: "22"})

    assert result[name]["display_name"] == name
