import pytest
from rest_framework.exceptions import ValidationError

from bkmonitor.models import AlgorithmModel, ItemModel, QueryConfigModel
from bkmonitor.strategy.new_strategy import Item


pytestmark = pytest.mark.django_db


def named_output_config():
    return {
        "response_contract": "named_outputs/v1",
        "legacy_output_ref": "C",
        "output_list": [
            {"reference_name": "A", "expression": "A"},
            {"reference_name": "B", "expression": "B"},
            {"reference_name": "C", "expression": "A / B * 100"},
        ],
    }


def item_config(**overrides):
    config = {
        "id": 0,
        "name": "name",
        "expression": "A / B * 100",
        "origin_sql": "test",
        "no_data_config": {},
        "target": [[]],
        "algorithms": [],
        "query_configs": [
            {
                "data_source_label": "bk_monitor",
                "data_type_label": "time_series",
                "alias": "A",
                "id": 0,
                "result_table_id": "xxxx",
                "metric_field": "aaa",
                "unit": "count",
                "agg_method": "sum",
                "agg_condition": [],
                "agg_dimension": ["service"],
                "agg_interval": 60,
            },
            {
                "data_source_label": "bk_monitor",
                "data_type_label": "time_series",
                "alias": "B",
                "id": 0,
                "result_table_id": "xxxx",
                "metric_field": "bbb",
                "unit": "count",
                "agg_method": "sum",
                "agg_condition": [],
                "agg_dimension": ["service"],
                "agg_interval": 60,
            },
        ],
    }
    config.update(overrides)
    return config


def test_query_output_config_object_roundtrip_preserves_other_meta(clean_model):
    item = Item(strategy_id=1, **item_config(query_output_config=named_output_config()))
    item.save()
    model = ItemModel.objects.get(id=item.id)
    model.meta["owner"] = "monitor"
    model.save(update_fields=["meta"])

    restored = Item.from_models(
        [model],
        {model.id: list(AlgorithmModel.objects.filter(item_id=model.id))},
        {model.id: list(QueryConfigModel.objects.filter(item_id=model.id))},
    )[0]
    restored.save()

    saved = ItemModel.objects.get(id=item.id)
    assert restored.to_dict()["query_output_config"] == named_output_config()
    assert saved.meta == {"owner": "monitor", "query_output_config": named_output_config()}


def test_query_output_config_omitted_preserves_existing_value(clean_model):
    item = Item(strategy_id=1, **item_config(query_output_config=named_output_config()))
    item.save()

    Item(strategy_id=1, **item_config(id=item.id)).save()

    assert ItemModel.objects.get(id=item.id).meta["query_output_config"] == named_output_config()


def test_query_output_config_explicit_null_deletes_only_reserved_meta(clean_model):
    item = Item(strategy_id=1, **item_config(query_output_config=named_output_config()))
    item.save()
    model = ItemModel.objects.get(id=item.id)
    model.meta["owner"] = "monitor"
    model.save(update_fields=["meta"])

    Item(strategy_id=1, **item_config(id=item.id, query_output_config=None)).save()

    assert ItemModel.objects.get(id=item.id).meta == {"owner": "monitor"}


def test_query_output_config_rejects_overwrite_when_meta_is_not_object(clean_model):
    item = Item(strategy_id=1, **item_config())
    item.save()
    ItemModel.objects.filter(id=item.id).update(meta=["legacy"])

    updating = Item(strategy_id=1, **item_config(id=item.id, query_output_config=named_output_config()))

    with pytest.raises(ValidationError, match="meta"):
        updating.save()
