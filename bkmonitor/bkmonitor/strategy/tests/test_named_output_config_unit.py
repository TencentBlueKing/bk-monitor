from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from bkmonitor.models import ItemModel
from bkmonitor.strategy.new_strategy import QUERY_OUTPUT_CONFIG_EMPTY, Item

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
    config["output_list"][0] = {"reference_name": " A ", "expression": " A "}

    serialized = Item(strategy_id=1, **item_config(query_output_config=config)).to_dict()

    assert serialized["query_output_config"] == named_output_config()


def test_item_unify_query_config_forwards_named_output_contract():
    item = Item(strategy_id=1, **item_config(query_output_config=named_output_config()))

    query_config = item.to_unify_query_config()

    assert {key: query_config[key] for key in named_output_config()} == named_output_config()


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


def test_item_from_models_roundtrips_named_output_config_without_database():
    model = SimpleNamespace(
        id=101,
        strategy_id=1,
        name="name",
        expression="A / B * 100",
        functions=[],
        origin_sql="",
        no_data_config={},
        target=[[]],
        metric_type="time_series",
        time_delay=0,
        meta={"owner": "monitor", "query_output_config": named_output_config()},
    )

    restored = Item.from_models([model], {101: []}, {101: []})[0]

    assert restored.to_dict()["query_output_config"] == named_output_config()
