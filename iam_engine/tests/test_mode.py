from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from iam_engine.core.config import AuthMode
from iam_engine.core.exceptions import InvalidAuthModeError
from iam_engine.mode import FeatureToggleModeProvider


@pytest.mark.parametrize("value,expected", [("v3", AuthMode.V3), (" V4 ", AuthMode.V4), ("UNION", AuthMode.UNION)])
def test_explicit_environment_has_priority_and_never_reads_toggle(value, expected):
    loader = Mock()
    mode = FeatureToggleModeProvider(loader, env_loader=lambda: value)
    assert mode.get_mode() is expected
    loader.assert_not_called()


@pytest.mark.parametrize("value", ["primary", "all_of", "any_of", "unknown"])
def test_invalid_environment_does_not_fall_back(value):
    loader = Mock(return_value=None)
    mode = FeatureToggleModeProvider(loader, env_loader=lambda: value)
    with pytest.raises(InvalidAuthModeError):
        mode.get_mode()
    loader.assert_not_called()


@pytest.mark.parametrize(
    "status,config", [("off", {"mode": "v3"}), ("debug", {"mode": "union"}), ("on", ["v3"]), ("on", {"mode": "all_of"})]
)
def test_invalid_toggle_is_rejected(status, config):
    mode = FeatureToggleModeProvider(
        lambda name: SimpleNamespace(status=status, feature_config=config), env_loader=lambda: ""
    )
    with pytest.raises(InvalidAuthModeError):
        mode.get_mode()


def test_missing_or_unavailable_toggle_preserves_bklog_v3_default():
    mode = FeatureToggleModeProvider(lambda name: None, env_loader=lambda: "")
    assert mode.get_mode() is AuthMode.V3
    mode.toggle_loader = Mock(side_effect=RuntimeError("offline store unavailable"))
    assert mode.get_mode() is AuthMode.V3


def test_toggle_is_dynamic_and_has_no_business_grey_logic():
    loader = Mock(
        side_effect=[SimpleNamespace(status="on", feature_config={"mode": mode}) for mode in ("v3", "v4", "union")]
    )
    provider = FeatureToggleModeProvider(loader, env_loader=lambda: "")
    assert [provider.get_mode() for _ in range(3)] == [AuthMode.V3, AuthMode.V4, AuthMode.UNION]
