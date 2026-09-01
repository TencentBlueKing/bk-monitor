import logging
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Optional, Union


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class FakeSpaceTypeEnum(str, Enum):
    BKCC = "bkcc"
    BCS = "bcs"
    BKCI = "bkci"
    BKSAAS = "bksaas"


def _load_scope_utils(fake_space_api):
    utils_source = (PROJECT_ROOT / "bkm_space/utils.py").read_text(encoding="utf-8")
    utils_source = utils_source[utils_source.index("def space_uid_to_bk_biz_id") :]
    scope_source = (PROJECT_ROOT / "bkm_space/scope.py").read_text(encoding="utf-8")
    scope_source = scope_source[scope_source.index("def bk_biz_id_to_scope_id") :]
    namespace = {
        "api": SimpleNamespace(SpaceApi=fake_space_api),
        "logger": logging.getLogger(__name__),
        "SpaceTypeEnum": FakeSpaceTypeEnum,
        "Dict": dict,
        "List": list,
        "Optional": Optional,
        "Tuple": tuple,
        "Union": Union,
        "MONITOR_SCOPE_QUERY_SENTINELS": {-1, -2},
    }
    exec(utils_source, namespace)
    exec(scope_source, namespace)
    return namespace


def test_bk_biz_id_to_scope_id_supports_bkcc_non_bkcc_and_sentinels():
    spaces = {
        -88888: "bkci__project_with_underscore",
        -77777: "bcs__cluster",
        -66666: "bksaas__app",
    }
    namespace = _load_scope_utils(
        SimpleNamespace(
            get_space_detail=lambda **kwargs: SimpleNamespace(space_uid=spaces[kwargs["bk_biz_id"]]),
            gen_space_uid=lambda scope_type, scope_value: f"{scope_type}__{scope_value}",
            parse_space_uid=lambda space_uid: tuple(space_uid.split("__", 1)),
        )
    )

    assert namespace["bk_biz_id_to_scope_id"](2) == "bkcc_2"
    assert namespace["bk_biz_id_to_scope_id"](-1) == "bkcc_-1"
    assert namespace["bk_biz_id_to_scope_id"](-2) == "bkcc_-2"
    assert namespace["bk_biz_id_to_scope_id"](-88888) == "bkci_project_with_underscore"
    assert namespace["bk_biz_id_to_scope_id"](-77777) == "bcs_cluster"
    assert namespace["bk_biz_id_to_scope_id"](-66666) == "bksaas_app"


def test_scope_id_to_bk_biz_id_supports_historical_config_without_scope_identity():
    space_ids = {
        "bkci__project_with_underscore": 88888,
        "bcs__cluster": 77777,
        "bksaas__app": 66666,
    }
    namespace = _load_scope_utils(
        SimpleNamespace(
            get_space_detail=lambda **kwargs: SimpleNamespace(id=space_ids[kwargs["space_uid"]]),
            gen_space_uid=lambda scope_type, scope_value: f"{scope_type}__{scope_value}",
            parse_space_uid=lambda space_uid: tuple(space_uid.split("__", 1)),
        )
    )

    assert namespace["scope_id_to_bk_biz_id"]("bkcc_2") == 2
    assert namespace["scope_id_to_bk_biz_id"]("bkci_project_with_underscore") == -88888
    assert namespace["scope_id_to_bk_biz_id"]("bcs_cluster") == -77777
    assert namespace["scope_id_to_bk_biz_id"]("bksaas_app") == -66666
    assert namespace["scope_id_to_bk_biz_id"]("") == 0


def test_scope_conversion_rejects_non_standard_fallback_when_space_lookup_fails():
    namespace = _load_scope_utils(
        SimpleNamespace(
            get_space_detail=lambda **kwargs: None,
            gen_space_uid=lambda scope_type, scope_value: f"{scope_type}__{scope_value}",
            parse_space_uid=lambda space_uid: tuple(space_uid.split("__", 1)),
        )
    )

    try:
        namespace["bk_biz_id_to_scope_id"](-88888)
    except ValueError as error:
        assert str(error) == "cannot resolve bk_biz_id: -88888"
    else:
        raise AssertionError("未解析的监控空间不能伪装成 BKCC scope")
    assert namespace["scope_id_to_bk_biz_id"]("bkci_missing") == 0
