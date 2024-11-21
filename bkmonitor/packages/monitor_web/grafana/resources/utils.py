import itertools
import json

from apm_web.profile.doris.querier import APIType


def get_label_values(instance=None, validated_data: dict = None):
    offset, rows = validated_data["offset"], validated_data["rows"]
    essentials = instance._get_essentials(validated_data)
    bk_biz_id = essentials["bk_biz_id"]
    app_name = essentials["app_name"]
    service_name = essentials["service_name"]
    result_table_id = essentials["result_table_id"]

    start, end = instance._enlarge_duration(validated_data["start"], validated_data["end"], offset=offset)
    results = instance.query(
        api_type=APIType.LABEL_VALUES,
        app_name=app_name,
        bk_biz_id=bk_biz_id,
        service_name=service_name,
        extra_params={
            "label_key": validated_data["label_key"],
            "limit": {"offset": offset, "rows": rows},
        },
        result_table_id=result_table_id,
        start=start,
        end=end,
    )
    return results


def get_labels_keys(instance=None, validated_data: dict = None, limit: int = None):
    essentials = instance._get_essentials(validated_data)
    bk_biz_id = essentials["bk_biz_id"]
    app_name = essentials["app_name"]
    service_name = essentials["service_name"]
    result_table_id = essentials["result_table_id"]

    start, end = instance._enlarge_duration(
        validated_data["start"], validated_data["end"], offset=validated_data.get("offset", 0)
    )

    results = instance.query(
        api_type=APIType.LABELS,
        app_name=app_name,
        bk_biz_id=bk_biz_id,
        service_name=service_name,
        result_table_id=result_table_id,
        start=start,
        end=end,
        extra_params={"limit": {"rows": limit}},
    )

    label_keys = set(
        itertools.chain(*[list(json.loads(i["labels"]).keys()) for i in results.get("list", []) if i.get("labels")])
    )
    return label_keys
