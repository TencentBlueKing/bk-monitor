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

from alarm_backends.core.alarm_engine.config import shadow_flag, shadow_kafka_config, shadow_topics


@pytest.mark.parametrize("value", [True, "true", "True", " TRUE "])
def test_shadow_flag_only_opens_for_an_explicit_true(value):
    assert shadow_flag(value) is True


@pytest.mark.parametrize(
    "value",
    [
        False,
        "false",
        "False",
        "0",
        "",
        "  ",
        "yes",
        "1",
        1,
        None,
        (),
        {"enabled": True},
    ],
)
def test_shadow_flag_fails_closed_for_every_other_value(value):
    assert shadow_flag(value) is False


def test_shadow_kafka_config_accepts_a_mapping_and_copies_it():
    source = {"topic": "alarm-engine-trigger-input-shadow", "bootstrap.servers": "kafka:9092"}
    resolved = shadow_kafka_config(source)
    assert resolved == source
    resolved["topic"] = "mutated"
    assert source["topic"] == "alarm-engine-trigger-input-shadow"


def test_shadow_kafka_config_decodes_an_environment_json_document():
    assert shadow_kafka_config('{"topic":"shadow-input","enable.idempotence":true}') == {
        "topic": "shadow-input",
        "enable.idempotence": True,
    }


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "not json",
        '["shadow-input"]',
        '"shadow-input"',
        '{"topic":"a","topic":"b"}',
        b'{"topic":"shadow-input"}',
        None,
        42,
    ],
)
def test_shadow_kafka_config_rejects_documents_that_are_not_objects(value):
    assert shadow_kafka_config(value) == {}


def test_shadow_topics_normalizes_a_comma_separated_environment_value():
    assert shadow_topics(" go-decision , trigger-input ,, trigger-input ") == ("go-decision", "trigger-input")


def test_shadow_topics_normalizes_a_configured_sequence():
    assert shadow_topics(["python-decision", "trigger-input", "trigger-input"]) == (
        "python-decision",
        "trigger-input",
    )


@pytest.mark.parametrize("value", ["", "  ,  ", [], (), None, 42, ["trigger-input", 7]])
def test_shadow_topics_yields_no_allowlist_for_empty_or_unusable_values(value):
    assert shadow_topics(value) == ()
