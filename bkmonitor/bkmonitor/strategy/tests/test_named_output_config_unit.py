from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from bkmonitor.management.commands.rollback_strategy import prepare_history_content_for_rollback
from bkmonitor.models import ItemModel
from bkmonitor.strategy.new_strategy import QUERY_OUTPUT_CONFIG_EMPTY, Item, Strategy

from .test_named_outputs import item_config, named_output_config


def test_item_serializer_distinguishes_omitted_null_and_object_config():
    omitted = Item.Serializer(data=item_config())
    deleting = Item.Serializer(data=item_config(query_output_config=None))
    replacing = Item.Serializer(data=item_config(query_output_config=named_output_config()))

    assert omitted.is_valid(), omitted.errors
    assert deleting.is_valid(), deleting.errors
    assert replacing.is_valid(), replacing.errors
    assert "query_output_config" not in omitted.validated_data
    assert deleting.validated_data["query_output_config"] is None
    assert replacing.validated_data["query_output_config"] == named_output_config()


def test_item_to_dict_roundtrips_normalized_named_output_config():
    config = named_output_config()
    config["response_contract"] = " named_outputs/v1 "
    config["legacy_output_ref"] = " C "
    config["output_list"][0] = {"reference_name": " A ", "expression": " a "}

    serialized = Item(strategy_id=1, **item_config(query_output_config=config)).to_dict()

    assert serialized["query_output_config"] == named_output_config()


def test_item_unify_query_config_forwards_named_output_contract():
    item = Item(strategy_id=1, **item_config(query_output_config=named_output_config()))

    query_config = item.to_unify_query_config()

    assert {key: query_config[key] for key in named_output_config()} == named_output_config()
    assert [query["reference_name"] for query in query_config["query_list"]] == ["a", "b"]
    assert query_config["metric_merge"] == "a / b * 100"


def test_item_accepts_named_outputs_matching_aliases_and_effective_metric_merge():
    config = named_output_config()
    config["output_list"][0]["expression"] = " a "
    config["output_list"][1]["expression"] = " b "
    config["output_list"][2]["expression"] = " a / b * 100 "

    item = Item(strategy_id=1, **item_config(query_output_config=config))

    assert item.query_output_config["legacy_output_ref"] == "C"


def test_item_accepts_legacy_output_matching_expression_functions():
    config = named_output_config()
    config["output_list"][2]["expression"] = " abs(a / b * 100) "

    item = Item(
        strategy_id=1,
        **item_config(
            functions=[{"id": "abs", "params": []}],
            query_output_config=config,
        ),
    )

    assert item.query_output_config["output_list"][2]["expression"] == "abs(a / b * 100)"


@pytest.mark.parametrize(
    "output_index,expression",
    [
        (0, "A"),
        (2, "A / B * 100"),
    ],
)
def test_item_rejects_case_mismatch_with_effective_uq_contract(output_index, expression):
    config = named_output_config()
    config["output_list"][output_index]["expression"] = expression

    with pytest.raises(ValidationError, match="query_output_config"):
        Item(strategy_id=1, **item_config(query_output_config=config))


def test_item_rejects_function_case_mismatch_with_effective_uq_contract():
    config = named_output_config()
    config["output_list"][2]["expression"] = "ABS(a / b * 100)"

    with pytest.raises(ValidationError, match="query_output_config"):
        Item(
            strategy_id=1,
            **item_config(
                functions=[{"id": "abs", "params": []}],
                query_output_config=config,
            ),
        )


@pytest.mark.parametrize(
    "mutate_config",
    [
        lambda config: config["output_list"][2].update(expression="a + b"),
        lambda config: config["output_list"][0].update(expression="a + 0"),
        lambda config: config["output_list"][0].update(expression="missing_alias"),
    ],
)
def test_item_rejects_named_outputs_incompatible_with_current_query(mutate_config):
    config = named_output_config()
    mutate_config(config)

    with pytest.raises(ValidationError, match="query_output_config"):
        Item(strategy_id=1, **item_config(query_output_config=config))


def test_item_rejects_named_output_identity_for_missing_query_alias():
    config = named_output_config()
    query_configs = item_config()["query_configs"][:1]

    with pytest.raises(ValidationError, match="query_output_config"):
        Item(
            strategy_id=1,
            **item_config(
                query_configs=query_configs,
                query_output_config=config,
            ),
        )


def test_update_query_output_meta_preserves_unrelated_keys_and_deletes_only_reserved_key():
    current = {"owner": "monitor", "query_output_config": named_output_config()}

    replaced = Item.update_query_output_meta(current, named_output_config())
    deleted = Item.update_query_output_meta(current, None)

    assert replaced == current
    assert deleted == {"owner": "monitor"}


@pytest.mark.parametrize("invalid_meta", [[], "legacy", 1])
def test_update_query_output_meta_rejects_non_object_history(invalid_meta):
    with pytest.raises(ValidationError, match="meta"):
        Item.update_query_output_meta(invalid_meta, named_output_config())


@pytest.mark.parametrize(
    ("path", "invalid_value", "error"),
    [
        (("response_contract",), 1, "字符串"),
        (("legacy_output_ref",), True, "字符串"),
        (("output_list", 0, "reference_name"), 1, "字符串"),
        (("output_list", 0, "expression"), ["A"], "字符串"),
        (("output_list", 0, "reference_name"), "1A", "标识符"),
        (("output_list", 0, "reference_name"), "A-B", "标识符"),
    ],
)
def test_item_rejects_non_string_or_invalid_named_output_fields(path, invalid_value, error):
    config = named_output_config()
    target = config
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = invalid_value

    with pytest.raises(ValidationError, match=error):
        Item(strategy_id=1, **item_config(query_output_config=config))


def test_item_create_persists_named_output_config_in_reserved_meta(mocker):
    create = mocker.patch.object(ItemModel.objects, "create", return_value=SimpleNamespace(id=101))
    item = Item(strategy_id=1, **item_config(query_output_config=named_output_config()))

    item._create()

    assert create.call_args.kwargs["meta"] == {"query_output_config": named_output_config()}


@pytest.mark.parametrize(
    ("query_output_config", "expected_meta"),
    [
        (QUERY_OUTPUT_CONFIG_EMPTY, {"owner": "monitor", "query_output_config": named_output_config()}),
        (None, {"owner": "monitor"}),
    ],
)
def test_item_update_preserves_omitted_config_and_deletes_explicit_null(mocker, query_output_config, expected_meta):
    model = SimpleNamespace(
        meta={"owner": "monitor", "query_output_config": named_output_config()},
        time_delay=0,
        save=mocker.Mock(),
    )
    mocker.patch.object(ItemModel.objects, "get", return_value=model)
    config = item_config(id=101)
    if query_output_config is not QUERY_OUTPUT_CONFIG_EMPTY:
        config["query_output_config"] = query_output_config
    item = Item(strategy_id=1, **config)
    mocker.patch.object(item, "save_algorithms")
    mocker.patch.object(item, "save_query_configs")

    item.save()

    assert model.meta == expected_meta


def test_item_update_rejects_query_change_when_named_output_config_is_omitted(mocker):
    model = SimpleNamespace(
        meta={"owner": "monitor", "query_output_config": named_output_config()},
        time_delay=0,
        save=mocker.Mock(),
    )
    mocker.patch.object(ItemModel.objects, "get", return_value=model)
    item = Item(strategy_id=1, **item_config(id=101, expression="a + b"))
    mocker.patch.object(item, "save_algorithms")
    mocker.patch.object(item, "save_query_configs")

    with pytest.raises(ValidationError, match="完整 API.*null"):
        item.save()

    model.save.assert_not_called()


def test_item_update_accepts_query_change_with_synchronized_named_output_config(mocker):
    old_config = named_output_config()
    new_config = named_output_config()
    new_config["output_list"][2]["expression"] = "a + b"
    model = SimpleNamespace(
        meta={"owner": "monitor", "query_output_config": old_config},
        time_delay=0,
        save=mocker.Mock(),
    )
    mocker.patch.object(ItemModel.objects, "get", return_value=model)
    item = Item(
        strategy_id=1,
        **item_config(id=101, expression="a + b", query_output_config=new_config),
    )
    mocker.patch.object(item, "save_algorithms")
    mocker.patch.object(item, "save_query_configs")

    item.save()

    assert model.meta == {"owner": "monitor", "query_output_config": new_config}


def test_item_update_accepts_query_change_with_explicit_null_deletion(mocker):
    model = SimpleNamespace(
        meta={"owner": "monitor", "query_output_config": named_output_config()},
        time_delay=0,
        save=mocker.Mock(),
    )
    mocker.patch.object(ItemModel.objects, "get", return_value=model)
    item = Item(
        strategy_id=1,
        **item_config(id=101, expression="a + b", query_output_config=None),
    )
    mocker.patch.object(item, "save_algorithms")
    mocker.patch.object(item, "save_query_configs")

    item.save()

    assert model.meta == {"owner": "monitor"}


def test_item_from_models_roundtrips_named_output_config_without_database():
    model = SimpleNamespace(
        id=101,
        strategy_id=1,
        name="name",
        expression="a / b * 100",
        functions=[],
        origin_sql="",
        no_data_config={},
        target=[[]],
        metric_type="time_series",
        time_delay=0,
        meta={"owner": "monitor", "query_output_config": named_output_config()},
    )

    query_models = []
    for query_id, query_config in enumerate(item_config()["query_configs"], start=1):
        query_data = dict(query_config)
        alias = query_data.pop("alias")
        data_source_label = query_data.pop("data_source_label")
        data_type_label = query_data.pop("data_type_label")
        query_data.pop("id")
        query_models.append(
            SimpleNamespace(
                id=query_id,
                strategy_id=1,
                item_id=101,
                alias=alias,
                data_source_label=data_source_label,
                data_type_label=data_type_label,
                metric_id="",
                config=query_data,
            )
        )

    restored = Item.from_models([model], {101: []}, {101: query_models})[0]

    assert restored.to_dict()["query_output_config"] == named_output_config()


def test_strategy_history_content_resolves_omitted_named_output_config(mocker):
    strategy = Strategy.__new__(Strategy)
    strategy._id = 1
    strategy.items = [SimpleNamespace(id=101, query_output_config=QUERY_OUTPUT_CONFIG_EMPTY)]
    strategy.to_dict = mocker.Mock(return_value={"items": [{"id": 101}]})
    current_item = SimpleNamespace(id=101, meta={"query_output_config": named_output_config()})
    mocker.patch.object(ItemModel.objects, "filter").return_value.only.return_value = [current_item]

    content = strategy.get_history_content()

    assert content["items"][0]["query_output_config"] == named_output_config()


def test_pre_feature_history_rollback_explicitly_deletes_named_output_config():
    historical_content = {"items": [{"id": 101}]}

    rollback_content = prepare_history_content_for_rollback(historical_content)

    assert rollback_content["items"][0]["query_output_config"] is None
    assert "query_output_config" not in historical_content["items"][0]
