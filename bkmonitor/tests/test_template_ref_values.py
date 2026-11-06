from copy import deepcopy
from types import SimpleNamespace
from collections import defaultdict

import pytest
from rest_framework.exceptions import ValidationError

from bkmonitor.action.serializers.action import TemplateSerializer
from bkmonitor.documents import EventDocument
from bkmonitor.strategy.new_strategy import Strategy
from bkmonitor.utils.template import Jinja2Renderer
from bkmonitor.utils.template_ref_values import RefValueTemplateError, validate_ref_value_template


def output_config(*names):
    return {
        "response_contract": "named_outputs/v1",
        "legacy_output_ref": names[-1],
        "output_list": [{"reference_name": name, "expression": "a"} for name in names],
    }


def context(*names):
    return {
        "_query_output_config": output_config(*names),
        "alarm": {"ref_values": {name: {"value": index, "state": "SUCCESS"} for index, name in enumerate(names)}},
    }


@pytest.mark.parametrize("reference", ["a", "A"])
def test_unique_case_insensitive_reference(reference):
    assert Jinja2Renderer.render("{{alarm.ref_values." + reference + ".value}}", context("A")) == "0"


def test_exact_names_win_and_ambiguous_fallback_is_rejected():
    values = context("Foo", "FOO")
    assert Jinja2Renderer.render("{{alarm.ref_values.Foo.value}}/{{alarm.ref_values.FOO.value}}", values) == "0/1"
    with pytest.raises(RefValueTemplateError, match="ambiguous"):
        Jinja2Renderer.render("{{alarm.ref_values.foo.value}}", values)


@pytest.mark.parametrize("reference", ["items", "get", "keys", "_A", "__class__"])
def test_configured_reference_is_data_not_a_python_attribute(reference):
    assert Jinja2Renderer.render("{{alarm.ref_values." + reference + ".value}}", context(reference)) == "0"


@pytest.mark.parametrize(
    "template",
    [
        "{{alarm.ref_values}}",
        "{{alarm.ref_values.A}}",
        '{{alarm.ref_values.get("A", {}).get("value")}}',
        '{{alarm.ref_values["A"].value}}',
        "{{alarm.ref_values.A.value.real}}",
        "{{alarm.ref_values.A.value + 1}}",
        "{{alarm.ref_values.A.value | default(1)}}",
        "{% set v = alarm.ref_values %}{{v.A.value}}",
        "{% set v = alarm.ref_values.A.value %}{{v}}",
        "{{alarm.ref_values.A.STATE}}",
        '{{alarm["ref_values"].A.value}}',
        '{{alarm | attr("ref_values")}}',
        '{{[alarm] | map(attribute="ref_values.A.value") | list}}',
    ],
)
def test_validator_and_renderer_reject_non_leaf_syntax(template):
    with pytest.raises(RefValueTemplateError):
        validate_ref_value_template(template, ["A"])
    with pytest.raises(RefValueTemplateError):
        Jinja2Renderer.render(template, context("A"))


@pytest.mark.parametrize(
    "template",
    [
        "{% set a = alarm %}{{a.ref_values.A.value}}",
        '{% set key = "ref_" ~ "values" %}{{alarm[key].A.value}}',
        '{% set key = "ref_" ~ "values" %}{{alarm.get(key).A.value}}',
        '{% set key = "ref_" ~ "values" %}{{alarm|attr(key)}}',
    ],
)
def test_runtime_blocks_indirect_container_access(template):
    with pytest.raises(RefValueTemplateError):
        Jinja2Renderer.render(template, context("A"))


def test_snapshot_never_expands_whitelist_or_uses_its_own_case_fallback():
    values = context("A")
    values["alarm"]["ref_values"] = {"a": {"value": 99, "state": "SUCCESS"}, "EXTRA": {"value": 100}}
    assert Jinja2Renderer.render("{{alarm.ref_values.a.value}}/{{alarm.ref_values.A.state}}", values) == "--/MISSING"
    with pytest.raises(RefValueTemplateError, match="unconfigured"):
        Jinja2Renderer.render("{{alarm.ref_values.EXTRA.value}}", values)


@pytest.mark.parametrize("state", ["MISSING", "ERROR", "UNSUPPORTED"])
def test_non_success_states_do_not_expose_a_stale_value(state):
    values = context("A")
    values["alarm"]["ref_values"]["A"] = {"state": state, "value": 99}
    assert Jinja2Renderer.render("{{alarm.ref_values.A.value}}/{{alarm.ref_values.A.state}}", values) == f"--/{state}"


def test_partial_output_preserves_its_value_and_state():
    values = context("A")
    values["alarm"]["ref_values"]["A"] = {"state": "PARTIAL", "value": 42}
    assert Jinja2Renderer.render("{{alarm.ref_values.A.value}}/{{alarm.ref_values.A.state}}", values) == "42/PARTIAL"


def test_missing_configuration_is_rejected_and_other_template_features_are_unchanged():
    with pytest.raises(RefValueTemplateError, match="unconfigured"):
        Jinja2Renderer.render("{{alarm.ref_values.A.value}}", {"alarm": {"ref_values": {"A": {"value": 1}}}})
    assert (
        Jinja2Renderer.render('{{alarm.dimensions.get("host")}}', {"alarm": {"dimensions": {"host": "demo"}}}) == "demo"
    )


def test_values_are_constants_not_recompiled_templates_and_inputs_stay_unchanged():
    values = context("A")
    values["alarm"]["ref_values"]["A"]["value"] = "{{ marker() }}"
    before = deepcopy(values)
    assert Jinja2Renderer.render("{{alarm.ref_values.a.value}}", values) == "{{ marker() }}"
    assert values == before


@pytest.mark.parametrize("field", ["title_tmpl", "message_tmpl"])
def test_template_serializer_does_not_swallow_reference_syntax_errors(field):
    with pytest.raises(Exception, match="only .*alarm.ref_values"):
        getattr(TemplateSerializer, f"validate_{field}")("{{alarm.ref_values}}")


def test_strategy_validation_uses_effective_omitted_or_null_configuration():
    strategy = object.__new__(Strategy)
    strategy.notice = SimpleNamespace(config={"template": [{"message_tmpl": "{{alarm.ref_values.a.value}}"}]})
    strategy.get_history_content = lambda: {"items": [{"query_output_config": output_config("A")}]}
    strategy.validate_notice_ref_values()
    strategy.get_history_content = lambda: {"items": [{"query_output_config": None}]}
    with pytest.raises(ValidationError, match="unconfigured"):
        strategy.validate_notice_ref_values()


def test_strategy_checks_each_item_instead_of_the_union():
    strategy = object.__new__(Strategy)
    strategy.notice = SimpleNamespace(config={"template": [{"message_tmpl": "{{alarm.ref_values.a.value}}"}]})
    strategy.get_history_content = lambda: {
        "items": [{"query_output_config": output_config("A")}, {"query_output_config": output_config("B")}]
    }
    with pytest.raises(ValidationError, match="unconfigured"):
        strategy.validate_notice_ref_values()


def test_existing_i18n_templates_are_accepted_by_save_and_runtime():
    template = "{% trans %}hello{% endtrans %}"
    assert TemplateSerializer.validate_message_tmpl(template) == template
    assert Jinja2Renderer.render(template, {}) == "hello"


@pytest.mark.parametrize(
    "template",
    [
        "{{anomaly_record.extra_info.origin_alarm.data}}",
        "{{json.dumps(anomaly_record.extra_info.origin_alarm.data)}}",
        "{{anomaly_record.extra_info|pprint}}",
        "{{alert.event.extra_info.origin_alarm.data|string}}",
    ],
)
def test_raw_event_context_cannot_expose_snapshot_containers(template):
    event = EventDocument(extra_info={"origin_alarm": {"data": {"value": 1, "ref_values": {"X": {"value": 919}}}}})
    values = {"anomaly_record": event, "alert": SimpleNamespace(event=event)}
    rendered = Jinja2Renderer.render(template, values)
    assert "ref_values" not in rendered
    assert "919" not in rendered
    assert event.extra_info.origin_alarm.data.ref_values.X.value == 919


def test_projection_preserves_legacy_defaultdict_values():
    values = {"data": defaultdict(lambda: {"value": 42})}
    assert Jinja2Renderer.render('{{data["missing"].value}}', values) == "42"
