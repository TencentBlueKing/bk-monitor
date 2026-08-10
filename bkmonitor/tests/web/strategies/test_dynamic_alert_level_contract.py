"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from bkmonitor.models import AlgorithmModel
from bkmonitor.strategy.new_strategy import Algorithm, Strategy
from bkmonitor.strategy.serializers import IntelligentDetectSerializer


def make_strategy_config():
    return {
        "items": [
            {
                "query_configs": [{"intelligent_detect": {"use_sdk": True}}],
                "algorithms": [
                    {
                        "type": "IntelligentDetect",
                        "level": 2,
                        "config": {"alert_level_mode": "auto"},
                    }
                ],
            }
        ],
        "detects": [{"level": 2}],
    }


def test_intelligent_detect_mode_is_optional_without_injected_default():
    serializer = IntelligentDetectSerializer(data={"args": {"$sensitivity": 5}, "plan_id": 1, "visual_type": "score"})

    serializer.is_valid(raise_exception=True)

    assert "alert_level_mode" not in serializer.validated_data


def test_intelligent_detect_auto_mode_is_preserved_by_serializer():
    serializer = IntelligentDetectSerializer(
        data={
            "args": {"$sensitivity": 5},
            "plan_id": 1,
            "visual_type": "score",
            "alert_level_mode": "auto",
        }
    )

    serializer.is_valid(raise_exception=True)

    assert serializer.validated_data["alert_level_mode"] == "auto"


def test_existing_auto_mode_is_preserved_when_old_client_omits_field():
    algorithm = Algorithm(
        strategy_id=101,
        item_id=1,
        type="IntelligentDetect",
        config={"args": {"$sensitivity": 3}, "plan_id": 1},
        level=2,
    )
    model = SimpleNamespace(
        type="IntelligentDetect",
        config={"args": {"$sensitivity": 5}, "plan_id": 1, "alert_level_mode": "auto"},
    )

    merged = algorithm._merge_with_db_config(model)

    assert merged["alert_level_mode"] == "auto"


def test_explicit_manual_mode_replaces_existing_auto_mode():
    algorithm = Algorithm(
        strategy_id=101,
        item_id=1,
        type="IntelligentDetect",
        config={"args": {"$sensitivity": 3}, "plan_id": 1, "alert_level_mode": "manual"},
        level=2,
    )
    model = SimpleNamespace(
        type="IntelligentDetect",
        config={"args": {"$sensitivity": 5}, "plan_id": 1, "alert_level_mode": "auto"},
    )

    merged = algorithm._merge_with_db_config(model)

    assert merged["alert_level_mode"] == "manual"


def test_strategy_inherits_existing_auto_mode_before_effective_config_validation(monkeypatch):
    current_algorithm = SimpleNamespace(id=0, type="IntelligentDetect", config={})
    strategy = Strategy.__new__(Strategy)
    strategy._id = 101
    strategy.items = [SimpleNamespace(algorithms=[current_algorithm])]
    existing_algorithm = SimpleNamespace(id=11, config={"alert_level_mode": "auto"})
    monkeypatch.setattr(AlgorithmModel.objects, "filter", lambda **_kwargs: [existing_algorithm])

    strategy.inherit_dynamic_alert_level_mode()

    assert current_algorithm.config["alert_level_mode"] == "auto"


def test_strategy_allows_explicit_manual_mode_to_exit_existing_auto(monkeypatch):
    current_algorithm = SimpleNamespace(id=11, type="IntelligentDetect", config={"alert_level_mode": "manual"})
    strategy = Strategy.__new__(Strategy)
    strategy._id = 101
    strategy.items = [SimpleNamespace(algorithms=[current_algorithm])]
    existing_algorithm = SimpleNamespace(id=11, config={"alert_level_mode": "auto"})
    monkeypatch.setattr(AlgorithmModel.objects, "filter", lambda **_kwargs: [existing_algorithm])

    strategy.inherit_dynamic_alert_level_mode()

    assert current_algorithm.config["alert_level_mode"] == "manual"


def test_existing_auto_mode_rejects_algorithm_type_replacement_without_manual(monkeypatch):
    current_algorithm = SimpleNamespace(id=11, type="Threshold", config=[])
    strategy = Strategy.__new__(Strategy)
    strategy._id = 101
    strategy.items = [SimpleNamespace(algorithms=[current_algorithm])]
    existing_algorithm = SimpleNamespace(id=11, config={"alert_level_mode": "auto"})
    monkeypatch.setattr(AlgorithmModel.objects, "filter", lambda **_kwargs: [existing_algorithm])

    with pytest.raises(ValidationError):
        strategy.inherit_dynamic_alert_level_mode()


def test_existing_auto_mode_rejects_ambiguous_duplicate_algorithms_without_mode(monkeypatch):
    current_algorithms = [
        SimpleNamespace(id=0, type="IntelligentDetect", config={}),
        SimpleNamespace(id=0, type="IntelligentDetect", config={}),
    ]
    strategy = Strategy.__new__(Strategy)
    strategy._id = 101
    strategy.items = [SimpleNamespace(algorithms=current_algorithms)]
    existing_algorithm = SimpleNamespace(id=11, config={"alert_level_mode": "auto"})
    monkeypatch.setattr(AlgorithmModel.objects, "filter", lambda **_kwargs: [existing_algorithm])

    with pytest.raises(ValidationError):
        strategy.inherit_dynamic_alert_level_mode()


def test_valid_auto_level_contract():
    Strategy.Serializer.validate_dynamic_alert_level(make_strategy_config())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda config: config["items"].append(copy.deepcopy(config["items"][0])),
        lambda config: config["items"][0]["query_configs"].append({"intelligent_detect": {"use_sdk": True}}),
        lambda config: config["items"][0]["algorithms"].append({"type": "Threshold", "level": 2, "config": []}),
        lambda config: config["items"][0]["algorithms"][0].update(type="Threshold"),
        lambda config: config["items"][0]["query_configs"][0]["intelligent_detect"].update(use_sdk="true"),
        lambda config: config["items"][0]["query_configs"][0].update(intelligent_detect=None),
        lambda config: config["items"][0]["algorithms"][0].update(level=1),
        lambda config: config["detects"].append({"level": 1}),
        lambda config: config["detects"][0].update(level=1),
    ],
)
def test_invalid_auto_level_contract_is_rejected(mutate):
    config = make_strategy_config()
    mutate(config)

    with pytest.raises(ValidationError):
        Strategy.Serializer.validate_dynamic_alert_level(config)


def test_manual_strategy_is_not_restricted_by_auto_contract():
    config = make_strategy_config()
    config["items"][0]["algorithms"][0]["config"]["alert_level_mode"] = "manual"
    config["items"].append(copy.deepcopy(config["items"][0]))

    Strategy.Serializer.validate_dynamic_alert_level(config)
