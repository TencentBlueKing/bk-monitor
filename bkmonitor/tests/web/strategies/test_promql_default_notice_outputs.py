import copy
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from bkmonitor.models import ItemModel, StrategyModel
from bkmonitor.strategy.new_strategy import Strategy
from monitor_web.strategies.resources.v2 import SaveStrategyV2Resource


def _promql_item(*aliases, expression="a + b", **overrides):
    item = {
        "id": 0,
        "expression": expression,
        "functions": [],
        "query_configs": [
            {
                "alias": alias,
                "promql": f"sum({alias}_total)",
                "agg_interval": 60,
                "data_source_label": "prometheus",
                "data_type_label": "time_series",
                "expression_mode": "promql",
            }
            for alias in aliases
        ],
    }
    item.update(overrides)
    return item


def _capture_page_save(mocker, item):
    from monitor_web.strategies.resources.v2 import SaveStrategyForPageResource

    save = mocker.patch.object(SaveStrategyV2Resource, "perform_request", side_effect=lambda params, **kwargs: params)
    request = {"bk_biz_id": 2, "items": [item]}
    original = copy.deepcopy(request)
    result = SaveStrategyForPageResource().perform_request(request)
    assert request == original
    save.assert_called_once()
    return result["items"][0]


def test_page_save_generates_default_for_all_queries_including_unused_alias(mocker):
    item = _capture_page_save(mocker, _promql_item("a", "b", "c"))

    assert item["query_output_config"] == {
        "response_contract": "named_outputs/v1",
        "legacy_output_ref": "RESULT",
        "output_list": [
            {"reference_name": "A", "expression": "a"},
            {"reference_name": "B", "expression": "b"},
            {"reference_name": "C", "expression": "c"},
            {"reference_name": "RESULT", "expression": "a + b"},
        ],
    }


def test_notice_preview_reuses_new_page_defaults_without_writing(mocker):
    from fta_web.action.resources.frontend_resources import RenderNoticeTemplate

    item = _promql_item("a", "b", "c")
    config = RenderNoticeTemplate.get_output_config({"bk_biz_id": 2, "preview_item": item})
    assert [output["reference_name"] for output in config["output_list"]] == ["A", "B", "C", "RESULT"]
    assert "query_output_config" not in item


def test_notice_preview_tracks_edited_defaults_but_keeps_explicit_null(mocker):
    from fta_web.action.resources.frontend_resources import RenderNoticeTemplate
    from monitor_web.strategies.resources.v2 import SaveStrategyForPageResource

    old_config = SaveStrategyForPageResource.default_output_config(_promql_item("a", "b"))
    _mock_persisted_item(mocker, meta={"query_output_config": old_config})
    params = {
        "bk_biz_id": 2,
        "strategy_id": 9,
        "preview_item": _promql_item("a", "b", "c", expression="a - b", id=101, query_output_config=old_config),
    }
    result = RenderNoticeTemplate.get_output_config(params)
    assert result["output_list"][-1] == {"reference_name": "RESULT", "expression": "a - b"}
    assert result["output_list"][2] == {"reference_name": "C", "expression": "c"}
    params["preview_item"]["query_output_config"] = None
    assert RenderNoticeTemplate.get_output_config(params) is None


def test_notice_preview_keeps_omitted_custom_config_and_disabled_legacy_item(mocker):
    from fta_web.action.resources.frontend_resources import RenderNoticeTemplate

    custom = {
        "response_contract": "named_outputs/v1",
        "legacy_output_ref": "RESULT",
        "output_list": [
            {"reference_name": "detail", "expression": "a"},
            {"reference_name": "RESULT", "expression": "a + b"},
        ],
    }
    params = {"bk_biz_id": 2, "strategy_id": 9, "preview_item": _promql_item("a", "b", id=101)}
    _mock_persisted_item(mocker, meta={"query_output_config": custom})
    assert RenderNoticeTemplate.get_output_config(params) == custom
    _mock_persisted_item(mocker, meta={})
    assert RenderNoticeTemplate.get_output_config(params) is None


def test_notice_preview_validates_reference_config_and_draft_schema():
    from fta_web.action.resources.frontend_resources import RenderNoticeTemplate

    serializer = RenderNoticeTemplate.RequestSerializer(
        data={"template": "legacy", "preview_item": {"query_configs": []}}
    )
    assert not serializer.is_valid()
    with pytest.raises(ValidationError):
        RenderNoticeTemplate.get_output_config(
            {"query_output_config": {"response_contract": "unknown", "output_list": []}}
        )


def test_notice_preview_supports_signed_space_business_ids():
    from fta_web.action.resources.frontend_resources import RenderNoticeTemplate

    serializer = RenderNoticeTemplate.RequestSerializer(
        data={"template": "{{alarm.ref_values.a.value}}", "bk_biz_id": -42, "preview_item": _promql_item("a", "b")}
    )
    assert serializer.is_valid(), serializer.errors
    config = RenderNoticeTemplate.get_output_config(serializer.validated_data)
    assert config["output_list"][0]["reference_name"] == "A"


def test_page_save_uses_effective_expression_with_functions(mocker):
    item = _promql_item("a", "b", functions=[{"id": "abs", "params": []}])

    result = _capture_page_save(mocker, item)

    assert result["query_output_config"]["output_list"][-1] == {
        "reference_name": "RESULT",
        "expression": "abs(a + b)",
    }


def test_page_save_preserves_explicit_null_and_existing_legacy_mode(mocker):
    disabled = _capture_page_save(mocker, _promql_item("a", "b", query_output_config=None))
    old_mode = _promql_item("a", "b")
    for query in old_mode["query_configs"]:
        query.pop("expression_mode")
    legacy = _capture_page_save(mocker, old_mode)

    assert disabled["query_output_config"] is None
    assert "query_output_config" not in legacy


@pytest.mark.parametrize("aliases", [("a", "b", "c", "d"), ("a", "A"), ("a", "RESULT")])
def test_page_save_rejects_capacity_and_output_name_collisions(mocker, aliases):
    with pytest.raises(ValidationError):
        _capture_page_save(mocker, _promql_item(*aliases))


def _mock_persisted_item(mocker, *, expression="a + b", meta=None, aliases=("a", "b"), mode="promql"):
    old_item = SimpleNamespace(id=101, expression=expression, functions=[], meta=meta if meta is not None else [])
    mocker.patch(
        "monitor_web.strategies.resources.v2.StrategyModel.objects.filter"
    ).return_value.exists.return_value = True
    mocker.patch("monitor_web.strategies.resources.v2.ItemModel.objects.filter").return_value.only.return_value = [
        old_item
    ]
    old_queries = [
        SimpleNamespace(
            item_id=101,
            alias=alias,
            data_source_label="prometheus",
            data_type_label="time_series",
            config={"promql": f"sum({alias}_total)", "agg_interval": 60, "expression_mode": mode}
            if mode
            else {"promql": f"sum({alias}_total)", "agg_interval": 60},
        )
        for alias in aliases
    ]
    mocker.patch(
        "monitor_web.strategies.resources.v2.QueryConfigModel.objects.filter"
    ).return_value.order_by.return_value = old_queries
    return old_item


def test_page_refreshes_transmitted_old_default_before_strategy_construction(mocker):
    from .test_strategy_v3 import get_strategy_dict
    from monitor_web.strategies.resources.v2 import SaveStrategyForPageResource

    old = _promql_item("a", "b")
    old_default = SaveStrategyForPageResource.default_output_config(old)
    _mock_persisted_item(mocker, meta={"query_output_config": old_default})
    request = get_strategy_dict({"is_enabled": False})
    request["id"] = 9
    request["items"][0].update(_promql_item("a", "b", expression="a - b", id=101, query_output_config=old_default))

    with pytest.raises(ValidationError, match="query_output_config"):
        Strategy(**request)
    prepared = SaveStrategyForPageResource.add_page_defaults(request)
    serializer = Strategy.Serializer(data=prepared)
    assert serializer.is_valid(), serializer.errors
    Strategy(**serializer.validated_data)
    assert prepared["items"][0]["query_output_config"]["output_list"][-1]["expression"] == "a - b"
    assert request["items"][0]["query_output_config"] == old_default


def test_page_refreshes_omitted_old_default_and_alias_changes(mocker):
    from monitor_web.strategies.resources.v2 import SaveStrategyForPageResource

    old = _promql_item("a", "b")
    old_default = SaveStrategyForPageResource.default_output_config(old)
    _mock_persisted_item(mocker, meta={"query_output_config": old_default})

    changed = SaveStrategyForPageResource.add_page_defaults(
        {"bk_biz_id": 2, "id": 9, "items": [_promql_item("a", "c", "d", expression="a + c", id=101)]}
    )
    assert changed["items"][0]["query_output_config"] == SaveStrategyForPageResource.default_output_config(
        _promql_item("a", "c", "d", expression="a + c")
    )
    removed = SaveStrategyForPageResource.add_page_defaults(
        {
            "bk_biz_id": 2,
            "id": 9,
            "items": [_promql_item("a", "c", expression="a + c", id=101, query_output_config=old_default)],
        }
    )
    assert [output["reference_name"] for output in removed["items"][0]["query_output_config"]["output_list"]] == [
        "A",
        "C",
        "RESULT",
    ]


@pytest.mark.parametrize(
    "aliases,output_order,old_expression,new_expression",
    [
        (("a", "b", "c"), ("B", "A", "C", "RESULT"), "a + b", "a - b"),
        (("a", "c", "d"), ("A", "D", "C", "RESULT"), "a + c", "a - c"),
    ],
)
def test_page_recognizes_reordered_default_for_edit_and_single_conversion(
    mocker, aliases, output_order, old_expression, new_expression
):
    from monitor_web.strategies.resources.v2 import SaveStrategyForPageResource

    old = _promql_item(*aliases, expression=old_expression)
    old_default = SaveStrategyForPageResource.default_output_config(old)
    outputs = {output["reference_name"]: output for output in old_default["output_list"]}
    reordered = {**old_default, "output_list": [outputs[name] for name in output_order]}
    _mock_persisted_item(mocker, expression=old_expression, meta={"query_output_config": reordered}, aliases=aliases)

    edited = SaveStrategyForPageResource.add_page_defaults(
        {
            "bk_biz_id": 2,
            "id": 9,
            "items": [_promql_item(*aliases, expression=new_expression, id=101, query_output_config=reordered)],
        }
    )
    assert edited["items"][0]["query_output_config"]["output_list"][-1]["expression"] == new_expression

    single = _promql_item(aliases[0], expression=aliases[0], id=101, query_output_config=reordered)
    single["query_configs"][0].pop("expression_mode")
    converted = SaveStrategyForPageResource.add_page_defaults({"bk_biz_id": 2, "id": 9, "items": [single]})
    assert converted["items"][0]["query_output_config"] is None


def test_page_keeps_disabled_existing_mode_and_explicit_custom_mapping(mocker):
    from monitor_web.strategies.resources.v2 import SaveStrategyForPageResource

    _mock_persisted_item(mocker)
    disabled = SaveStrategyForPageResource.add_page_defaults(
        {"bk_biz_id": 2, "id": 9, "items": [_promql_item("a", "b", id=101)]}
    )
    assert "query_output_config" not in disabled["items"][0]

    custom = {
        "response_contract": "named_outputs/v1",
        "legacy_output_ref": "RESULT",
        "output_list": [
            {"reference_name": "A", "expression": "a"},
            {"reference_name": "RESULT", "expression": "a + b"},
        ],
    }
    _mock_persisted_item(mocker, meta={"query_output_config": custom})
    supplied = SaveStrategyForPageResource.add_page_defaults(
        {"bk_biz_id": 2, "id": 9, "items": [_promql_item("a", "b", id=101, query_output_config=custom)]}
    )
    assert supplied["items"][0]["query_output_config"] == custom


@pytest.mark.parametrize("meta", [[], {}])
def test_page_keeps_existing_multi_mode_disabled_but_enables_legacy_conversion(mocker, meta):
    from monitor_web.strategies.resources.v2 import SaveStrategyForPageResource

    _mock_persisted_item(mocker, meta=meta)
    unchanged = SaveStrategyForPageResource.add_page_defaults(
        {"bk_biz_id": 2, "id": 9, "items": [_promql_item("a", "b", id=101)]}
    )
    assert "query_output_config" not in unchanged["items"][0]

    _mock_persisted_item(mocker, meta=meta, mode=None)
    upgraded = SaveStrategyForPageResource.add_page_defaults(
        {"bk_biz_id": 2, "id": 9, "items": [_promql_item("a", "b", id=101)]}
    )
    assert upgraded["items"][0]["query_output_config"]["legacy_output_ref"] == "RESULT"


def test_page_does_not_mask_invalid_explicit_config(mocker):
    from .test_strategy_v3 import get_strategy_dict
    from monitor_web.strategies.resources.v2 import SaveStrategyForPageResource

    old_default = SaveStrategyForPageResource.default_output_config(_promql_item("a", "b"))
    _mock_persisted_item(mocker, meta={"query_output_config": old_default})
    invalid = copy.deepcopy(old_default)
    invalid["output_list"][0]["reference_name"] = []
    request = get_strategy_dict({"is_enabled": False})
    request["id"] = 9
    request["items"][0].update(_promql_item("a", "b", id=101, query_output_config=invalid))
    prepared = SaveStrategyForPageResource.add_page_defaults(request)
    assert prepared["items"][0]["query_output_config"] == invalid
    serializer = Strategy.Serializer(data=prepared)
    assert serializer.is_valid(), serializer.errors
    with pytest.raises(ValidationError, match="命名输出引用和表达式必须为字符串"):
        Strategy(**serializer.validated_data)


def test_save_route_is_page_only():
    from monitor_web.strategies.resources.v2 import SaveStrategyForPageResource
    from monitor_web.strategies.views import StrategiesViewSet
    from core.drf_resource import resource

    route = next(route for route in StrategiesViewSet.resource_routes if route.endpoint == "v2/save_strategy")
    assert route.resource_class is SaveStrategyForPageResource
    assert resource.strategies.save_strategy_v2.__class__ is SaveStrategyV2Resource


def test_page_matches_item_ids_like_strategy_save(mocker):
    from monitor_web.strategies.resources.v2 import SaveStrategyForPageResource

    old = [SimpleNamespace(id=1), SimpleNamespace(id=2), SimpleNamespace(id=3)]
    new = [{"id": 2}, {"id": 0}, {"id": 2}, {"id": 999}]
    assert [item.id if item else 0 for item in SaveStrategyForPageResource.match_old_items(new, old)] == [2, 1, 3, 0]


@pytest.fixture
def strategy_payload(mocker):
    from .test_strategy_v3 import get_strategy_dict

    payload = get_strategy_dict({"is_enabled": False})
    payload["items"][0]["query_configs"] = _promql_item("a", "b")["query_configs"]
    payload["items"][0]["expression"] = "a + b"
    mocker.patch.object(Strategy, "convert")
    mocker.patch("bkmonitor.strategy.new_strategy.is_ipv6_biz", return_value=False)
    return payload


def _save(resource_class, payload):
    resource = resource_class()
    return resource.perform_request(resource.validate_request_data(copy.deepcopy(payload)))


@pytest.mark.django_db(databases="__all__")
def test_page_save_persists_default_and_regular_save_keeps_omission(strategy_payload):
    from monitor_web.strategies.resources.v2 import SaveStrategyForPageResource

    page_result = _save(SaveStrategyForPageResource, strategy_payload)
    page_item = ItemModel.objects.get(strategy_id=page_result["id"])
    assert page_item.meta["query_output_config"]["output_list"][-1] == {
        "reference_name": "RESULT",
        "expression": "a + b",
    }

    regular_payload = copy.deepcopy(strategy_payload)
    regular_payload["name"] = "regular-save"
    regular_result = _save(SaveStrategyV2Resource, regular_payload)
    assert ItemModel.objects.get(strategy_id=regular_result["id"]).meta == []


@pytest.mark.django_db(databases="__all__")
def test_page_save_refreshes_existing_default_and_preserves_disabled_item(strategy_payload):
    from monitor_web.strategies.resources.v2 import SaveStrategyForPageResource

    result = _save(SaveStrategyForPageResource, strategy_payload)
    item = ItemModel.objects.get(strategy_id=result["id"])
    old_config = copy.deepcopy(item.meta["query_output_config"])
    edit = Strategy.from_models([StrategyModel.objects.get(id=result["id"])])[0].to_dict()
    edit["items"][0]["expression"] = "a - b"
    edit["items"][0]["query_output_config"] = old_config
    _save(SaveStrategyForPageResource, edit)
    item.refresh_from_db()
    assert item.meta["query_output_config"]["output_list"][-1]["expression"] == "a - b"

    edit["items"][0]["query_output_config"] = None
    _save(SaveStrategyForPageResource, edit)
    item.refresh_from_db()
    assert item.meta == {}

    edit["items"][0].pop("query_output_config")
    _save(SaveStrategyForPageResource, edit)
    item.refresh_from_db()
    assert item.meta == {}
