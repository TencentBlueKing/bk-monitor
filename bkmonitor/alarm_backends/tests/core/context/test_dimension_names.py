from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from elasticsearch_dsl import AttrDict

from alarm_backends.core.context import ActionContext
from alarm_backends.core.context.alarm import Alarm
from alarm_backends.service.alert.enricher.dimension import MonitorTranslateEnricher
from bkmonitor.utils.template import Jinja2Renderer


NAME = "base62L6Z57G75BOZ5pm45"


@pytest.mark.parametrize("use_action", [False, True])
def test_notice_dimensions_normalize_old_snapshots_without_mutation(use_action):
    dimension = {"key": f"tags.{NAME}", "value": 0, "display_key": NAME, "display_value": 0}
    alert = SimpleNamespace(dimensions=[AttrDict(dimension)], agg_dimensions=[NAME])
    action = SimpleNamespace(dimensions=[dimension] if use_action else [])
    alarm = Alarm(SimpleNamespace(action=action, alert=alert, notice_way="mail"))

    assert alarm.new_dimensions[f"tags.{NAME}"].display_key == "物品类型"
    assert alarm.new_dimensions[f"tags.{NAME}"].value == 0
    assert dimension["display_key"] == NAME
    assert alert.dimensions[0].display_key == NAME


def test_legacy_notice_template_gets_readable_name():
    translation = {"display_name": NAME, "value": "22", "display_value": "22"}
    alarm = Alarm(SimpleNamespace(alert=SimpleNamespace(origin_alarm={"dimension_translation": {NAME: translation}})))

    assert alarm.dimensions[NAME].display_name == "物品类型"
    assert translation["display_name"] == NAME


def test_notice_dimension_string_and_template_use_readable_names():
    dimension = {"key": f"tags.{NAME}", "value": "22", "display_key": NAME, "display_value": "22"}
    alert = SimpleNamespace(dimensions=[AttrDict(dimension)], agg_dimensions=[NAME])
    alarm = Alarm(SimpleNamespace(action=None, alert=alert, notice_way="mail", limit=False))

    assert alarm.dimension_string_list == ["物品类型=22"]
    assert Jinja2Renderer.render("{{ alarm.dimension_string }}", {"alarm": alarm}) == "物品类型=22"


def test_new_alert_enrichment_keeps_dimension_identity_and_existing_alias(mocker):
    translator = mocker.patch("alarm_backends.service.alert.enricher.dimension.TranslatorFactory")
    translator.return_value.translate.return_value = {
        NAME: {"display_name": NAME, "value": "22", "display_value": "22"},
        "app_name": {"display_name": "APM 应用", "value": "demo", "display_value": "demo"},
    }
    origin = {"data": {"dimensions": {NAME: "22", "app_name": "demo"}}}
    alert = Mock()
    alert.get_extra_info.side_effect = lambda key: {"strategy": {"items": []}, "origin_alarm": origin}[key]
    alert.dimensions = [{"key": f"tags.{NAME}", "value": "22"}, {"key": "tags.app_name", "value": "demo"}]

    assert MonitorTranslateEnricher([alert]).enrich_alert(alert) is alert
    assert alert.dimensions[0] == {
        "key": f"tags.{NAME}",
        "value": "22",
        "display_key": "物品类型",
        "display_value": "22",
    }
    assert alert.dimensions[1]["display_key"] == "APM 应用"
    assert origin["dimension_translation"][NAME]["display_name"] == "物品类型"


def test_aggregate_notice_dimensions_are_readable(mocker):
    mocker.patch("alarm_backends.core.context.StrategyCacheManager.get_strategy_by_id", return_value={"name": "demo"})
    alert = SimpleNamespace(
        id="test-alert",
        strategy_id=1,
        event_document=SimpleNamespace(target="demo"),
        dimensions=[AttrDict({"key": f"tags.{NAME}", "display_key": NAME, "display_value": "22"})],
    )

    assert ActionContext.get_alerts_dict([alert])[0]["dimension"] == "物品类型=22"
