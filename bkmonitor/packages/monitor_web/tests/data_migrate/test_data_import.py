from monitor_web.data_migrate import data_import


def test_import_biz_data_repairs_plugin_strategy_result_table_id(monkeypatch, tmp_path):
    events = []

    monkeypatch.setattr(
        data_import,
        "read_json_file",
        lambda *args, **kwargs: {
            "format": "json",
            "bk_biz_ids": [0, 2, 3],
            "global_files": ["global/foo.json"],
            "biz_files": {"2": ["biz/2/strategy.json"], "3": ["biz/3/strategy.json"]},
        },
    )
    monkeypatch.setattr(
        data_import,
        "_cleanup_biz_related_configs",
        lambda bk_biz_ids: events.append(("cleanup", bk_biz_ids)),
    )
    monkeypatch.setattr(
        data_import,
        "import_model_from_file",
        lambda **kwargs: events.append(("import", kwargs["file_path"], kwargs["atomic"])) or ["imported"],
    )
    monkeypatch.setattr(
        data_import,
        "_sync_close_records_to_application_config",
        lambda **kwargs: events.append(("sync", kwargs["directory_path"], kwargs["bk_biz_ids"])),
    )
    monkeypatch.setattr(
        data_import,
        "repair_plugin_strategy_result_table_id",
        lambda **kwargs: events.append(("repair", kwargs["bk_biz_id"], kwargs["dry_run"])),
    )

    imported_objects = data_import.import_biz_data_from_directory(tmp_path, bk_biz_ids=[2], atomic=False)

    assert imported_objects == ["imported"]
    assert events == [
        ("cleanup", [2]),
        ("import", tmp_path / "biz/2/strategy.json", False),
        ("sync", tmp_path, [2]),
        ("repair", [2], False),
    ]
