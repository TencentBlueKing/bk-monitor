import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from monitor_web.data_migrate import partial


def test_partial_export_includes_only_selected_tenant_data_id_relations(monkeypatch, tmp_path):
    relations = [
        partial.SpaceDataSource(
            id=index, bk_tenant_id=tenant, space_type_id=space_type, space_id=space_id, bk_data_id=data_id
        )
        for index, (tenant, space_type, space_id, data_id) in enumerate(
            [
                ("system", "bkcc", "18824", 533326),
                ("system", "bkci", "gos-backend", 533326),
                ("system", "bkcc", "18824", 999),
                ("another-tenant", "bkcc", "18824", 533326),
            ],
            start=1,
        )
    ]
    monkeypatch.setattr(
        partial,
        "_build_bcs_refs_and_fetchers",
        lambda **kwargs: (
            {
                "cluster_ids": ["BCS-K8S-40997"],
                "metric_data_ids": [533326],
                "event_data_ids": [],
                "log_data_ids": [],
            },
            [],
        ),
    )
    monkeypatch.setattr(partial, "_get_table_ids_by_data_ids", lambda **kwargs: set())
    monkeypatch.setattr(partial, "_build_data_source_export_refs", lambda *args: [])
    monkeypatch.setattr(partial, "_build_cluster_export_refs", lambda *args: [])

    def iter_objects(fetchers, context):
        for model, filters, _exclude in fetchers:
            if model is partial.SpaceDataSource:
                for relation in relations:
                    if (
                        relation.bk_tenant_id == filters["bk_tenant_id"]
                        and relation.bk_data_id in filters["bk_data_id__in"]
                    ):
                        yield relation

    monkeypatch.setattr(partial, "_iter_fetcher_objects", iter_objects)
    partial.export_partial_data_to_directory(
        tmp_path, bk_tenant_id="system", bk_biz_id=18824, bcs_cluster_ids=["BCS-K8S-40997"]
    )

    manifest = json.loads((tmp_path / "manifest.json").read_text())
    records = [
        record
        for filename in manifest["biz_files"]["18824"]
        for record in json.loads((tmp_path / filename).read_text())
    ]
    assert [(record["model"], record["fields"]["space_id"]) for record in records] == [
        ("metadata.spacedatasource", "18824"),
        ("metadata.spacedatasource", "gos-backend"),
    ]
    assert all(record["fields"]["bk_data_id"] == 533326 for record in records)
    assert all(record["fields"]["bk_tenant_id"] == "system" for record in records)


@pytest.mark.parametrize(
    "source_space_id,target_space_id",
    [
        ("gos-backend", "tencent-gos-backend"),
        ("tencent-gos-backend", "tencent-gos-backend"),
        ("gos-backend", "gos-backend"),
    ],
)
def test_partial_import_resolves_target_spaces_without_reusing_relation_pks(
    monkeypatch, tmp_path, source_space_id, target_space_id
):
    records = [
        {
            "model": "metadata.spacedatasource",
            "pk": 100,
            "fields": {
                "bk_tenant_id": "tencent",
                "space_type_id": "bkci",
                "space_id": source_space_id,
                "bk_data_id": 533326,
                "from_authorization": True,
            },
        },
        {
            "model": "metadata.spacedatasource",
            "pk": 101,
            "fields": {
                "bk_tenant_id": "tencent",
                "space_type_id": "bkcc",
                "space_id": "18824",
                "bk_data_id": 533326,
                "from_authorization": False,
            },
        },
        {"model": "metadata.datasource", "pk": 533326, "fields": {"bk_tenant_id": "tencent"}},
    ]
    fixture_path = tmp_path / "relations.json"
    fixture_path.write_text(json.dumps(records))
    (tmp_path / "manifest.json").write_text(
        json.dumps({"bk_biz_ids": [18824], "biz_files": {"18824": [fixture_path.name]}})
    )
    target_spaces = {
        ("tencent", "bkci", target_space_id): SimpleNamespace(space_id=target_space_id),
        ("tencent", "bkcc", "18824"): SimpleNamespace(space_id="18824"),
    }

    def space_key(lookup):
        return lookup["bk_tenant_id"], lookup["space_type_id"], lookup["space_id"]

    def get_space(**lookup):
        try:
            return target_spaces[space_key(lookup)]
        except KeyError:
            raise partial.Space.DoesNotExist from None

    get_space_mock = Mock(side_effect=get_space)
    monkeypatch.setattr(partial.Space.objects, "filter", Mock(side_effect=AssertionError("unexpected exists query")))
    monkeypatch.setattr(partial.Space.objects, "get", get_space_mock)
    monkeypatch.setattr(partial, "precheck_partial_import_directory", lambda **kwargs: {"result": True})
    imported_records = []

    def import_biz_data(**kwargs):
        imported_records.extend(json.loads(fixture_path.read_text()))
        return imported_records

    monkeypatch.setattr(partial, "import_biz_data_from_directory", import_biz_data)
    result = partial.import_partial_data_from_directory(tmp_path, atomic=False)

    assert result["imported_count"] == 3
    assert imported_records[0]["pk"] is None
    assert imported_records[0]["fields"]["space_id"] == target_space_id
    assert imported_records[0]["fields"]["from_authorization"] is True
    assert imported_records[1]["pk"] is None
    assert imported_records[1]["fields"]["space_id"] == "18824"
    assert imported_records[2] == records[2]
    expected_space_ids = [source_space_id]
    if source_space_id != target_space_id:
        expected_space_ids.append(target_space_id)
    assert [call.kwargs["space_id"] for call in get_space_mock.call_args_list] == [*expected_space_ids, "18824"]


@pytest.mark.parametrize("space_type,space_id", [("bkcc", "18824"), ("bkci", "gos-backend")])
def test_partial_import_missing_target_space_reports_sync_guidance_without_importing(
    monkeypatch, tmp_path, space_type, space_id
):
    records = [
        {
            "model": "metadata.spacedatasource",
            "pk": 100,
            "fields": {
                "bk_tenant_id": "tencent",
                "space_type_id": space_type,
                "space_id": space_id,
                "bk_data_id": 533326,
            },
        }
    ]
    fixture_path = tmp_path / "relations.json"
    fixture_path.write_text(json.dumps(records))
    (tmp_path / "manifest.json").write_text(
        json.dumps({"bk_biz_ids": [18824], "biz_files": {"18824": [fixture_path.name]}})
    )
    get_space = Mock(side_effect=partial.Space.DoesNotExist)
    monkeypatch.setattr(partial.Space.objects, "get", get_space)
    monkeypatch.setattr(partial, "precheck_partial_import_directory", lambda **kwargs: {"result": True})
    import_biz_data = Mock()
    monkeypatch.setattr(partial, "import_biz_data_from_directory", import_biz_data)

    with pytest.raises(ValueError, match="请先同步目标空间") as error:
        partial.import_partial_data_from_directory(tmp_path, atomic=False)

    assert "tencent" in str(error.value)
    assert space_type in str(error.value)
    assert space_id in str(error.value)
    expected_space_ids = [space_id]
    if space_type == "bkci":
        expected_space_ids.append(f"tencent-{space_id}")
        assert f"tencent-{space_id}" in str(error.value)
    assert [call.kwargs["space_id"] for call in get_space.call_args_list] == expected_space_ids
    import_biz_data.assert_not_called()
    assert json.loads(fixture_path.read_text()) == records


def test_partial_rebuild_publishes_only_affected_spaces_and_table_details(monkeypatch):
    space_rows = Mock()
    space_rows.values_list.return_value.distinct.return_value = [
        ("bkcc", "18824"),
        ("bkci", "tencent-gos-backend"),
    ]
    filter_relations = Mock(return_value=space_rows)
    monkeypatch.setattr(partial.SpaceDataSource.objects, "filter", filter_relations)
    table_ids = {"18824_bkmonitor_time_series_533326.__default__"}
    collect_tables = Mock(return_value=table_ids)
    monkeypatch.setattr(partial, "_get_table_ids_by_data_ids", collect_tables)
    space_client = Mock()
    monkeypatch.setattr(partial, "SpaceTableIDRedis", lambda: space_client)

    partial._refresh_partial_space_routes(bk_tenant_id="tencent", data_ids=[533326])

    filter_relations.assert_called_once_with(bk_tenant_id="tencent", bk_data_id__in=[533326])
    collect_tables.assert_called_once_with(bk_tenant_id="tencent", data_ids=[533326])
    space_client.push_data_label_table_ids.assert_called_once_with(
        bk_tenant_id="tencent", table_id_list=sorted(table_ids), is_publish=True
    )
    space_client.push_table_id_detail.assert_called_once_with(
        bk_tenant_id="tencent", table_id_list=sorted(table_ids), is_publish=True
    )
    assert [call.kwargs for call in space_client.push_space_table_ids.call_args_list] == [
        {"space_type": "bkcc", "space_id": "18824", "is_publish": True},
        {"space_type": "bkci", "space_id": "tencent-gos-backend", "is_publish": True},
    ]


def test_partial_rebuild_does_not_publish_when_no_data_ids(monkeypatch):
    monkeypatch.setattr(partial.SpaceDataSource.objects, "filter", Mock(side_effect=AssertionError("unexpected query")))
    partial._refresh_partial_space_routes(bk_tenant_id="tencent", data_ids=[])
