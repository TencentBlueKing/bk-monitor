"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import datetime, timezone as datetime_timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from django.template import TemplateDoesNotExist, engines
from django.utils import timezone, translation

from bkmonitor.utils.sms import (
    SMS_TEMPLATE_KINDS,
    format_sms_time,
    get_sms_template_mode,
    render_standard_sms,
    sms_utf16_length,
    standard_sms_template_kind,
)

TIME = "2025年1月1日 01:02分"
GUIDANCE = "请到企业微信/蓝鲸监控平台查看。"
ENGLISH_NO_ACTION = {
    "recovered/action": "Skip ",
    "recovered/converge": "ignore",
    "closed/action": "Skip ",
    "closed/converge": "Skip ",
}
VALUES = {
    "time": TIME,
    "level": "致命",
    "count": 5,
    "name": "CPU",
    "operator": "a",
    "status": "失败",
    "duration": "2小时",
    "shield_action": "开始",
}

CHINESE_MESSAGES = {
    "abnormal/action": f"{TIME}，您有1条致命级的告警待处理（CPU），{GUIDANCE}",
    "abnormal/converge": f"{TIME}，您有5条致命级的告警待处理（代表：CPU），{GUIDANCE}",
    "recovered/action": f"{TIME}，您的1条致命级告警已恢复（CPU），无需处理，详情{GUIDANCE}",
    "recovered/converge": f"{TIME}，您的5条致命级告警已恢复，无需处理，详情{GUIDANCE}",
    "closed/action": f"{TIME}，您的1条致命级告警已关闭（CPU），无需处理，详情{GUIDANCE}",
    "closed/converge": f"{TIME}，您的5条致命级告警已关闭，无需处理，详情{GUIDANCE}",
    "ack/action": f"{TIME}，您关注的1条告警已由 a 确认处理（CPU），{GUIDANCE}",
    "ack/converge": f"{TIME}，您关注的5条告警已由 a 确认处理，{GUIDANCE}",
    "assign/action": f"{TIME}，有1条致命级的告警分派给您处理（CPU），{GUIDANCE}",
    "assign/converge": f"{TIME}，有5条致命级的告警分派给您处理，{GUIDANCE}",
    "fta_action": f"{TIME}，您的告警处理套餐（CPU）执行状态为失败，{GUIDANCE}",
    "incident": f"{TIME}，您有1个致命级的故障待处理（关联5条告警），{GUIDANCE}",
    "shield": f"{TIME}，您有一条告警屏蔽已开始，屏蔽时长2小时，{GUIDANCE}",
}


@pytest.fixture(params=["web", "worker"])
def sms_template_backend(request, settings):
    template_dir = str(Path(__file__).resolve().parents[3] / "templates")
    if request.param == "web":
        settings.MAKO_DIR_NAME = "templates"
        backend = "blueapps.template.backends.mako.MakoTemplates"
        options = {"default_filters": ["h"]}
    else:
        backend = "django_jinja.backend.Jinja2"
        options = {"match_extension": ".jinja"}
    settings.TEMPLATES = [
        {"NAME": "sms_role", "BACKEND": backend, "DIRS": [template_dir], "APP_DIRS": False, "OPTIONS": options}
    ]
    assert engines["sms_role"].__class__.__module__ == backend.rsplit(".", 1)[0]
    return request.param


@pytest.mark.parametrize(("kind", "expected"), CHINESE_MESSAGES.items())
def test_role_template_backend_keeps_standard_jinja_rendering(sms_template_backend, kind, expected):
    assert render_standard_sms(kind, VALUES, language="zh-hans") == expected

    english = render_standard_sms(
        kind,
        {
            **VALUES,
            "time": "2025-12-31 23:59",
            "level": "Emergency",
            "name": "A",
            "operator": "a",
            "status": "Failed",
            "duration": "2h",
            "shield_action": "started",
        },
        language="en",
    )
    assert "{{" not in english
    assert english.startswith("2025-12-31 23:59 ")
    assert english.endswith("WeCom/BK.")
    assert sms_utf16_length(english) <= 70


def test_missing_standard_template_does_not_use_default(sms_template_backend, settings, tmp_path):
    fallback = tmp_path / "notice" / "standard" / "fta_action" / "default_content.jinja"
    fallback.parent.mkdir(parents=True)
    fallback.write_text("fallback", encoding="utf-8")
    settings.TEMPLATES = [{**settings.TEMPLATES[0], "DIRS": [str(tmp_path)]}]

    with pytest.raises(TemplateDoesNotExist):
        render_standard_sms("fta_action", VALUES, language="zh-hans")


@pytest.mark.parametrize(("kind", "expected"), CHINESE_MESSAGES.items())
def test_chinese_standard_template_matrix(kind, expected):
    content = render_standard_sms(kind, VALUES, language="zh-hans")

    assert content == expected
    assert len(content.encode("utf-16-le")) // 2 <= 70


@pytest.mark.parametrize("kind", SMS_TEMPLATE_KINDS)
def test_english_standard_template_matrix(kind):
    values = {
        **VALUES,
        "time": "2025-12-31 23:59",
        "level": "Emergency",
        "name": "A",
        "operator": "a",
        "status": "Failed",
        "duration": "2h",
        "shield_action": "started",
    }

    content = render_standard_sms(kind, values, language="en")

    assert content.startswith("2025-12-31 23:59 ")
    assert content.endswith("WeCom/BK.")
    assert not any("\u4e00" <= character <= "\u9fff" for character in content)
    assert len(content.encode("utf-16-le")) // 2 <= 70
    if kind in ENGLISH_NO_ACTION:
        assert ENGLISH_NO_ACTION[kind] in content
    if kind == "incident":
        assert "5 alerts" in content
        assert "Act:Emergency fault" in content


@pytest.mark.parametrize("count", [1000, 100000, 2147483647])
@pytest.mark.parametrize(
    "kind",
    ["abnormal/converge", "recovered/converge", "closed/converge", "ack/converge", "assign/converge", "incident"],
)
def test_english_count_templates_support_32_bit_counts(kind, count):
    values = {
        **VALUES,
        "time": "2026-12-31 23:59",
        "count": count,
        "level": "Emergency",
        "name": "名称😀" * 100,
        "operator": ["operator😀" * 100, "other"],
    }

    content = render_standard_sms(kind, values, language="en")

    assert content.startswith("2026-12-31 23:59 ")
    assert str(count) in content
    assert content.endswith("See WeCom/BK.")
    assert len(content.encode("utf-16-le")) // 2 <= 70
    if kind != "ack/converge":
        assert "Emergency" in content
    if kind in ENGLISH_NO_ACTION:
        assert ENGLISH_NO_ACTION[kind] in content
    if kind == "assign/converge":
        assert "Assigned:" in content
    if kind == "incident":
        assert "Act:Emergency fault" in content


@pytest.mark.parametrize("kind", SMS_TEMPLATE_KINDS)
@pytest.mark.parametrize("language", ["zh-hans", "en"])
def test_matrix_handles_longest_date_and_long_names(kind, language):
    values = {
        **VALUES,
        "time": "2025年12月31日 23:59分",
        "count": 999,
        "name": "名称😀" * 100,
        "operator": ["操作人😀" * 100, "other"],
        "status": "执行中",
    }
    if language == "en":
        values.update(
            time="2025-12-31 23:59", level="Emergency", status="Executing", duration="2h", shield_action="ended"
        )

    content = render_standard_sms(kind, values, language=language)

    assert len(content.encode("utf-16-le")) // 2 <= 70
    assert content.endswith(GUIDANCE if language == "zh-hans" else "WeCom/BK.")
    if kind in ("recovered/action", "recovered/converge", "closed/action", "closed/converge"):
        assert "无需处理" in content if language == "zh-hans" else ENGLISH_NO_ACTION[kind] in content


@pytest.mark.parametrize("kind", SMS_TEMPLATE_KINDS)
def test_only_explicit_sms_paths_are_mapped(kind):
    assert standard_sms_template_kind(f"notice/{kind}/sms_content.jinja") == kind
    assert standard_sms_template_kind(f"notice/{kind}/markdown_content.jinja") is None
    assert standard_sms_template_kind(f"notice/{kind}/sms_title.jinja") is None
    assert standard_sms_template_kind(f"notice/standard/{kind}/sms_content.jinja") is None


@pytest.mark.parametrize("path", ["notice/abnormal/action/default_content.jinja", "custom/sms_content.jinja", ""])
def test_unrelated_template_paths_are_unchanged(path):
    assert standard_sms_template_kind(path) is None


@pytest.mark.parametrize("mode", ["legacy", "standard"])
def test_valid_mode_is_read_on_every_call(settings, mode):
    settings.SMS_NOTICE_TEMPLATE_MODE = mode
    settings.SMS_NOTICE_TEMPLATE_MODE_DEFAULT = "legacy"
    assert get_sms_template_mode() == mode

    settings.SMS_NOTICE_TEMPLATE_MODE = "standard" if mode == "legacy" else "legacy"
    assert get_sms_template_mode() == settings.SMS_NOTICE_TEMPLATE_MODE


@pytest.mark.parametrize("invalid", [None, "", "STANDARD", "unexpected", [], {}, 1, True])
@pytest.mark.parametrize("fallback", ["legacy", "standard"])
def test_invalid_dynamic_mode_uses_static_default(settings, caplog, invalid, fallback):
    settings.SMS_NOTICE_TEMPLATE_MODE = invalid
    settings.SMS_NOTICE_TEMPLATE_MODE_DEFAULT = fallback

    assert get_sms_template_mode() == fallback
    assert "invalid SMS_NOTICE_TEMPLATE_MODE" in caplog.text


@pytest.mark.parametrize("name", ["a" * 200, "中" * 200, "😀" * 200, "a😀中" * 100])
@pytest.mark.parametrize("language", ["zh-hans", "en"])
def test_length_budget_preserves_guidance_and_unicode(name, language):
    values = {**VALUES, "name": name}
    if language == "en":
        values.update(time="2025-12-31 23:59", level="Emergency", status="Failed")

    content = render_standard_sms("fta_action", values, language=language)

    assert content.endswith(GUIDANCE if language == "zh-hans" else "See WeCom/BK.")
    assert len(content.encode("utf-16-le")) // 2 <= 70
    assert "…" in content
    assert not any(0xD800 <= ord(character) <= 0xDFFF for character in content)


def test_exact_70_units_does_not_shorten_name():
    fixed = render_standard_sms("fta_action", {**VALUES, "name": ""}, language="zh-hans")
    budget = 70 - sms_utf16_length(fixed)

    exact = render_standard_sms("fta_action", {**VALUES, "name": "a" * budget}, language="zh-hans")
    truncated = render_standard_sms("fta_action", {**VALUES, "name": "a" * (budget + 1)}, language="zh-hans")

    assert sms_utf16_length(exact) == 70
    assert "…" not in exact
    assert sms_utf16_length(truncated) == 70
    assert "…" in truncated


def test_name_is_shortened_before_operator():
    content = render_standard_sms("ack/action", {**VALUES, "name": "名称" * 100, "operator": "admin"})

    assert "由 admin 确认处理" in content
    assert "…" in content
    assert sms_utf16_length(content) == 70
    assert content.endswith(GUIDANCE)


def test_multiple_short_operators_remain_visible():
    content = render_standard_sms("ack/converge", {**VALUES, "operator": ["a", "b"]}, language="zh-hans")
    assert "由 a、b 确认处理" in content


def test_long_name_and_multiple_operators_preserve_operator_count():
    content = render_standard_sms(
        "ack/action", {**VALUES, "name": "告警" * 100, "operator": ["操作人" * 100, "other"]}, language="zh-hans"
    )

    assert "告警" not in content.split("确认处理", 1)[1]
    assert "等2人 确认处理（）" in content
    assert "…" in content
    assert sms_utf16_length(content) <= 70
    assert content.endswith(GUIDANCE)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("CPU\n\r\t负载", "CPU 负载"),
        ("[CPU](https://example.com/status)", "CPU"),
        ('<a href="https://example.com">CPU</a>', "CPU"),
        ("CPU https://example.com/a?b=c", "CPU"),
        ("CPU www.example.com/a", "CPU"),
        ("CPU example.com/a", "CPU"),
        ("CPU https:\u200b//example.com/a", "CPU"),
        ("A&amp;B", "A&B"),
    ],
)
def test_link_and_control_character_cleanup(name, expected):
    values = {**VALUES, "name": name}
    content = render_standard_sms("fta_action", values, language="zh-hans")

    assert f"（{expected}）" in content
    assert "example.com" not in content
    assert "\n" not in content
    assert values["name"] == name


def test_names_are_plain_data_and_never_a_second_template():
    content = render_standard_sms("fta_action", {**VALUES, "name": "{{ 7*7 }}"}, language="zh-hans")
    assert "（{{ 7*7 }}）" in content
    assert "49" not in content


def test_ack_operators_count_people_instead_of_alerts():
    content = render_standard_sms("ack/converge", {**VALUES, "count": 20, "operator": ["alice"] * 20}, "zh-hans")
    assert "已由 alice 确认处理" in content
    assert "等20人" not in content


def test_fixed_fields_are_not_silently_truncated():
    with pytest.raises(ValueError, match="fixed fields exceed"):
        render_standard_sms("incident", {**VALUES, "count": "1" * 100}, language="zh-hans")


def test_unknown_template_kind_is_an_implementation_error():
    with pytest.raises(ValueError, match="unsupported standard SMS kind"):
        render_standard_sms("custom", VALUES)


@pytest.mark.parametrize(
    "event_time",
    [
        datetime(2025, 12, 1, 5, 35, tzinfo=datetime_timezone.utc),
        datetime(2025, 12, 1, 5, 35),
        "2025-12-01T05:35:00Z",
        "2025-12-01T05:35:00",
        1764567300,
        "1764567300",
    ],
)
def test_time_uses_event_value_and_explicit_business_timezone(event_time):
    with timezone.override(ZoneInfo("UTC")):
        assert format_sms_time(event_time, tz="Asia/Shanghai", language="zh-hans") == "2025年12月1日 13:35分"
        assert format_sms_time(event_time, tz="Asia/Shanghai", language="en") == "2025-12-01 13:35"
        assert timezone.get_current_timezone_name() == "UTC"


def test_default_time_and_template_language_follow_current_context_without_leaking():
    event_time = "2025-12-01T05:35:00Z"
    with translation.override("en"), timezone.override(ZoneInfo("Asia/Shanghai")):
        assert format_sms_time(event_time) == "2025-12-01 13:35"
        assert render_standard_sms("fta_action", VALUES, language="zh-hans").endswith(GUIDANCE)
        assert translation.get_language() == "en"
    with translation.override("zh-hans"), timezone.override(ZoneInfo("UTC")):
        assert format_sms_time(event_time) == "2025年12月1日 05:35分"
        assert render_standard_sms("fta_action", {**VALUES, "time": "T"}, language="en").endswith("See WeCom/BK.")
        assert translation.get_language() == "zh-hans"


@pytest.mark.parametrize("event_time", [None, "", "invalid", {}, [], True, float("inf")])
def test_missing_or_invalid_event_time_is_unknown(event_time):
    assert format_sms_time(event_time, language="zh-hans") == "时间未知"


def test_invalid_business_timezone_is_unknown():
    assert format_sms_time(1764567300, tz="Invalid/Zone", language="zh-hans") == "时间未知"


def test_missing_render_time_uses_unknown_time():
    assert render_standard_sms("fta_action", {**VALUES, "time": ""}, language="zh-hans").startswith("时间未知，")
