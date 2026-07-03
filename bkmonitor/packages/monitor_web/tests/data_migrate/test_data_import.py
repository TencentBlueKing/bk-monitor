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
        "migrate_system_event_strategy_config",
        lambda **kwargs: events.append(("migrate_system_event", kwargs["bk_biz_id"], kwargs["dry_run"])),
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
        ("migrate_system_event", [2], False),
        ("repair", [2], False),
    ]


def test_import_biz_data_skips_builtin_system_event_migration_when_only_global(monkeypatch, tmp_path):
    events = []

    monkeypatch.setattr(
        data_import,
        "read_json_file",
        lambda *args, **kwargs: {
            "format": "json",
            "bk_biz_ids": [0],
            "global_files": ["global/foo.json"],
            "biz_files": {},
        },
    )
    monkeypatch.setattr(data_import, "_cleanup_biz_related_configs", lambda bk_biz_ids: None)
    monkeypatch.setattr(data_import, "import_model_from_file", lambda **kwargs: ["imported"])
    monkeypatch.setattr(data_import, "_sync_close_records_to_application_config", lambda **kwargs: None)
    monkeypatch.setattr(
        data_import,
        "migrate_system_event_strategy_config",
        lambda **kwargs: events.append(("migrate_system_event", kwargs["bk_biz_id"], kwargs["dry_run"])),
    )
    monkeypatch.setattr(data_import, "repair_plugin_strategy_result_table_id", lambda **kwargs: None)

    imported_objects = data_import.import_biz_data_from_directory(tmp_path, bk_biz_ids=[0])

    assert imported_objects == ["imported"]
    assert events == []


def test_import_biz_data_can_skip_business_cleanup_and_post_handlers(monkeypatch, tmp_path):
    events = []

    monkeypatch.setattr(
        data_import,
        "read_json_file",
        lambda *args, **kwargs: {
            "format": "json",
            "bk_biz_ids": [2],
            "global_files": [],
            "biz_files": {"2": ["biz/2/custom_report.json"]},
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
        "migrate_system_event_strategy_config",
        lambda **kwargs: events.append(("migrate_system_event", kwargs["bk_biz_id"], kwargs["dry_run"])),
    )
    monkeypatch.setattr(
        data_import,
        "repair_plugin_strategy_result_table_id",
        lambda **kwargs: events.append(("repair", kwargs["bk_biz_id"], kwargs["dry_run"])),
    )

    imported_objects = data_import.import_biz_data_from_directory(
        tmp_path,
        bk_biz_ids=[2],
        atomic=False,
        cleanup_existing=False,
        sync_close_records=False,
        migrate_builtin_system_event_strategy=False,
        repair_plugin_strategy=False,
    )

    assert imported_objects == ["imported"]
    assert events == [("import", tmp_path / "biz/2/custom_report.json", False)]
