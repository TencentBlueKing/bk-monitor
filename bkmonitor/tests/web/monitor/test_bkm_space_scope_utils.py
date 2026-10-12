from types import SimpleNamespace

import pytest

from bkm_space import scope as scope_utils


def test_bk_biz_id_to_scope_id_supports_bkcc_and_non_bkcc_spaces(monkeypatch):
    spaces = {
        -88888: "bkci__project_with_underscore",
        -77777: "bcs__cluster",
        -66666: "bksaas__app",
    }
    monkeypatch.setattr(scope_utils, "bk_biz_id_to_space_uid", spaces.__getitem__)
    monkeypatch.setattr(scope_utils, "parse_space_uid", lambda space_uid: tuple(space_uid.split("__", 1)))

    assert scope_utils.bk_biz_id_to_scope_id(2) == "bkcc_2"
    assert scope_utils.bk_biz_id_to_scope_id(-88888) == "bkci_project_with_underscore"
    assert scope_utils.bk_biz_id_to_scope_id(-77777) == "bcs_cluster"
    assert scope_utils.bk_biz_id_to_scope_id(-66666) == "bksaas_app"


@pytest.mark.parametrize("sentinel", [-1, -2])
def test_bk_biz_id_to_scope_id_rejects_monitor_query_sentinels(sentinel):
    with pytest.raises(ValueError, match="query sentinel must be expanded"):
        scope_utils.bk_biz_id_to_scope_id(sentinel)


def test_scope_id_to_bk_biz_id_supports_historical_config_without_scope_identity(monkeypatch):
    space_ids = {
        "bkci__project_with_underscore": 88888,
        "bcs__cluster": 77777,
        "bksaas__app": 66666,
    }
    monkeypatch.setattr(
        scope_utils.api,
        "SpaceApi",
        SimpleNamespace(gen_space_uid=lambda scope_type, scope_value: f"{scope_type}__{scope_value}"),
    )
    monkeypatch.setattr(
        scope_utils,
        "space_uid_to_bk_biz_id",
        lambda space_uid: -space_ids[space_uid],
    )

    assert scope_utils.scope_id_to_bk_biz_id("bkcc_2") == 2
    assert scope_utils.scope_id_to_bk_biz_id("bkci_project_with_underscore") == -88888
    assert scope_utils.scope_id_to_bk_biz_id("bcs_cluster") == -77777
    assert scope_utils.scope_id_to_bk_biz_id("bksaas_app") == -66666
    assert scope_utils.scope_id_to_bk_biz_id("") == 0


def test_scope_conversion_rejects_non_standard_fallback_when_space_lookup_fails(monkeypatch):
    monkeypatch.setattr(scope_utils, "bk_biz_id_to_space_uid", lambda _bk_biz_id: "")

    with pytest.raises(ValueError, match="cannot resolve bk_biz_id"):
        scope_utils.bk_biz_id_to_scope_id(-88888)

    monkeypatch.setattr(
        scope_utils.api,
        "SpaceApi",
        SimpleNamespace(gen_space_uid=lambda scope_type, scope_value: f"{scope_type}__{scope_value}"),
    )

    def raise_missing_space(_space_uid):
        raise RuntimeError("missing space")

    monkeypatch.setattr(scope_utils, "space_uid_to_bk_biz_id", raise_missing_space)
    assert scope_utils.scope_id_to_bk_biz_id("bkci_missing") == 0
