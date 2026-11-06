import copy
from types import SimpleNamespace

import pytest
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkmonitor.management.commands.rollback_strategy import prepare_history_content_for_rollback
from bkmonitor.models import ItemModel
from bkmonitor.strategy.new_strategy import QUERY_OUTPUT_CONFIG_EMPTY, Item, Strategy
from bkmonitor.strategy.partial_update import ItemPatchSerializer

from .test_named_outputs import item_config, named_output_config


@pytest.mark.django_db(databases="__all__")
def test_full_save_database_roundtrip_with_omission_and_clear(clean_model):
    item = Item(strategy_id=1, **item_config(access_lookback_periods=15, query_output_config=named_output_config()))
    item.save()
    model = ItemModel.objects.get(id=item.id)
    model.meta["owner"] = "monitor"
    model.save(update_fields=["meta"])

    Item(strategy_id=1, **item_config(id=item.id)).save()
    model.refresh_from_db()
    assert model.meta == {
        "owner": "monitor",
        "query_output_config": named_output_config(),
    }
    assert model.access_lookback_periods == 15
    Item(strategy_id=1, **item_config(id=item.id, access_lookback_periods=None)).save()
    model.refresh_from_db()
    assert model.meta == {"owner": "monitor", "query_output_config": named_output_config()}
    assert model.access_lookback_periods is None


@pytest.mark.parametrize("value", [None, 1, 15, 100])
def test_internal_item_accepts_lookback(value):
    item = Item(strategy_id=1, **item_config(access_lookback_periods=value))
    assert item.access_lookback_periods == value


@pytest.mark.parametrize("value", [None, 1, 15, 100])
def test_public_serializers_do_not_accept_internal_lookback(value):
    full = Item.Serializer(data=item_config(access_lookback_periods=value))
    partial = ItemPatchSerializer(data={"access_lookback_periods": value})
    assert full.is_valid(), full.errors
    assert "access_lookback_periods" not in full.validated_data
    assert not partial.is_valid()
    assert "access_lookback_periods" in partial.errors


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "invalid", [], {}])
def test_internal_item_rejects_invalid_lookback(value):
    with pytest.raises(ValidationError):
        Item(strategy_id=1, **item_config(access_lookback_periods=value))


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("current", [None, 15])
@pytest.mark.parametrize("value", [None, 1, 30])
def test_full_request_cannot_overwrite_internal_fields(clean_model, current, value):
    item = Item(strategy_id=1, **item_config(time_delay=60, access_lookback_periods=current))
    item.save()
    serializer = Item.Serializer(data=item_config(id=item.id, time_delay=value, access_lookback_periods=value))
    serializer.is_valid(raise_exception=True)
    Item(strategy_id=1, **serializer.validated_data).save()
    model = ItemModel.objects.get(id=item.id)
    assert model.time_delay == 60
    assert model.access_lookback_periods == current


def test_omitted_field_is_not_injected_and_survives_deepcopy():
    serializer = Item.Serializer(data=item_config())
    assert serializer.is_valid(), serializer.errors
    assert "access_lookback_periods" not in serializer.validated_data
    item = copy.deepcopy(
        Item(strategy_id=1, **item_config()), {id(QUERY_OUTPUT_CONFIG_EMPTY): QUERY_OUTPUT_CONFIG_EMPTY}
    )
    assert item.access_lookback_periods is serializers.empty
    assert "access_lookback_periods" not in item.to_dict()


@pytest.mark.parametrize("value", [serializers.empty, None, 1, 15])
def test_full_save_preserves_omitted_or_updates_explicit_override(mocker, value):
    meta = {"owner": "monitor", "query_output_config": named_output_config()}
    model = SimpleNamespace(meta=copy.deepcopy(meta), time_delay=0, access_lookback_periods=12, save=mocker.Mock())
    mocker.patch.object(ItemModel.objects, "get", return_value=model)
    config = item_config(id=101)
    if value is not serializers.empty:
        config["access_lookback_periods"] = value
    item = Item(strategy_id=1, **config)
    mocker.patch.object(item, "save_algorithms")
    mocker.patch.object(item, "save_query_configs")
    item.save()
    assert model.access_lookback_periods == (12 if value is serializers.empty else value)
    assert model.meta == meta


def test_create_and_read_back_with_named_output_meta(mocker):
    create = mocker.patch.object(ItemModel.objects, "create", return_value=SimpleNamespace(id=101))
    item = Item(strategy_id=1, **item_config(access_lookback_periods=15, query_output_config=named_output_config()))
    item._create()
    saved = create.call_args.kwargs
    assert saved["access_lookback_periods"] == 15
    assert saved["meta"] == {"query_output_config": named_output_config()}
    model = SimpleNamespace(id=101, **saved)
    mocker.patch("bkmonitor.strategy.new_strategy.QueryConfig.from_models", return_value=item.query_configs)
    restored = Item.from_models([model], {101: []}, {101: []})[0]
    assert restored.to_dict()["access_lookback_periods"] == 15
    assert restored.to_dict()["query_output_config"] == named_output_config()


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("meta", [[], {"owner": "monitor"}, ["historical"]])
def test_lookback_column_is_independent_of_meta(clean_model, meta):
    item = Item(strategy_id=1, **item_config())
    item.save()
    ItemModel.objects.filter(id=item.id).update(meta=meta)
    Item(strategy_id=1, **item_config(id=item.id, access_lookback_periods=15)).save()
    model = ItemModel.objects.get(id=item.id)
    assert model.access_lookback_periods == 15
    assert model.meta == meta


def test_full_save_history_preserves_omitted_value_even_with_explicit_output_config(mocker):
    strategy = Strategy.__new__(Strategy)
    strategy._id = 1
    strategy.items = [SimpleNamespace(id=101, query_output_config=None, access_lookback_periods=serializers.empty)]
    strategy.to_dict = mocker.Mock(return_value={"items": [{"id": 101, "query_output_config": None}]})
    model = SimpleNamespace(id=101, meta=[], access_lookback_periods=15)
    mocker.patch.object(ItemModel.objects, "filter").return_value.only.return_value = [model]
    assert strategy.get_history_content()["items"][0]["access_lookback_periods"] == 15


def test_rollback_to_pre_feature_history_clears_override_without_mutating_history():
    history = {"items": [{"id": 101}, {"id": 102, "access_lookback_periods": 12}]}
    prepared = prepare_history_content_for_rollback(history)
    assert prepared["items"][0]["access_lookback_periods"] is None
    assert prepared["items"][1]["access_lookback_periods"] == 12
    assert "access_lookback_periods" not in history["items"][0]
