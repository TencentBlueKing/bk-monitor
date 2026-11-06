import pytest
from django.utils import translation
from jinja2.exceptions import TemplateSyntaxError

from bkmonitor.action.serializers.action import NotifyActionConfigSlz, TemplateSerializer
from bkmonitor.utils.template import Jinja2Renderer
from constants.action import ActionSignal
from core.errors.strategy import CreateStrategyError


@pytest.mark.parametrize(("field", "label"), [("title_tmpl", "标题"), ("message_tmpl", "内容")])
@pytest.mark.parametrize(
    ("template", "line"),
    [
        ("{{content.level}}\n{{content.related_info}", 2),
        ("{{alarm.ref_values.A.value}}\n{{content.related_info}", 2),
        ("{{ 'unclosed }}", 1),
        ("{% if alarm %}\n{{content.level}}", 2),
        ("\n\n{{content.related_info}", 3),
        ("  \r\n \r\n{{content.related_info}", 3),
        (" \r \r{{content.related_info}", 3),
        ("\n\n{{content.level|missing_filter}}", 3),
        ("\n\n{{content.level is missing_test}}", 3),
    ],
)
def test_save_error_identifies_template_field_line_and_repair_hint(field, label, template, line):
    with translation.override("zh-hans"), pytest.raises(CreateStrategyError) as caught:
        serializer = NotifyActionConfigSlz(data={"template": [{"signal": ActionSignal.ABNORMAL, field: template}]})
        serializer.is_valid(raise_exception=True)

    error = caught.value
    assert f"告警通知{label}模板语法错误" in error.message
    assert f"第{line}行" in error.message
    assert "双花括号" in error.message
    assert "闭合" in error.message
    assert isinstance(error.__cause__, TemplateSyntaxError)
    assert error.__cause__.message in error.message
    assert error.code == 3313008
    assert error.error_details["type"] == "CreateStrategyError"
    assert error.error_details["code"] == 3313008
    assert error.error_details["overview"] == error.message


@pytest.mark.parametrize(("field", "label"), [("title_tmpl", "标题"), ("message_tmpl", "内容")])
def test_render_phase_syntax_error_has_the_same_context(monkeypatch, field, label):
    def fail_render(*args, **kwargs):
        raise TemplateSyntaxError("invalid expression", lineno=3)

    monkeypatch.setattr(Jinja2Renderer, "render", fail_render)
    with translation.override("zh-hans"), pytest.raises(CreateStrategyError) as caught:
        getattr(TemplateSerializer, f"validate_{field}")("{{content.level}}")

    assert f"告警通知{label}模板语法错误" in caught.value.message
    assert "第3行" in caught.value.message
    assert "invalid expression" in caught.value.message


@pytest.mark.parametrize("field", ["title_tmpl", "message_tmpl"])
@pytest.mark.parametrize(
    "template",
    ["", "{{content.level}}", "{{alarm.ref_values.a.value}}", "{% trans %}hello{% endtrans %}"],
)
def test_valid_legacy_and_reference_templates_are_unchanged(field, template):
    assert getattr(TemplateSerializer, f"validate_{field}")(template) == template


@pytest.mark.parametrize("field", ["title_tmpl", "message_tmpl"])
def test_successful_templates_keep_existing_whitespace_normalization(field):
    serializer = NotifyActionConfigSlz(
        data={"template": [{"signal": ActionSignal.ABNORMAL, field: "\n\n{{content.level}}  \n"}]}
    )
    serializer.is_valid(raise_exception=True)
    assert serializer.validated_data["template"][0][field] == "{{content.level}}"


@pytest.mark.parametrize(
    "message_template", ["{{ broken}", "{{content.level|missing_filter}}", "{{content.level is missing_test}}"]
)
def test_first_invalid_template_field_stays_the_same(message_template):
    serializer = NotifyActionConfigSlz(
        data={
            "template": [
                {
                    "signal": ActionSignal.ABNORMAL,
                    "title_tmpl": "{{ broken}",
                    "message_tmpl": "\n\n" + message_template,
                }
            ]
        }
    )
    with translation.override("zh-hans"), pytest.raises(CreateStrategyError) as caught:
        serializer.is_valid(raise_exception=True)
    assert "告警通知内容模板语法错误（第3行）" in caught.value.message
