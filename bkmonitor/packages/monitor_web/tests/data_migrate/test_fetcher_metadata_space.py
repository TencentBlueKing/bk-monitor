from monitor_web.data_migrate.fetcher.metadata.space import get_metadata_space_fetcher


def _fetcher_filters(fetchers):
    return {model._meta.label: filters for model, filters, _exclude in fetchers}


def test_get_metadata_space_fetcher_resolves_negative_biz_id(monkeypatch):
    from monitor_web.data_migrate.fetcher.metadata import space as space_fetcher

    requested_biz_ids = []

    def get_space_info_by_biz_id(bk_biz_id):
        requested_biz_ids.append(bk_biz_id)
        return {"space_type": "bkci", "space_id": "project-demo"}

    monkeypatch.setattr(
        space_fetcher.Space.objects,
        "get_space_info_by_biz_id",
        get_space_info_by_biz_id,
    )

    filters = _fetcher_filters(get_metadata_space_fetcher(-42))

    assert requested_biz_ids == [-42]
    assert filters == {
        "metadata.Space": {"space_type_id": "bkci", "space_id": "project-demo"},
        "metadata.SpaceDataSource": {"space_type_id": "bkci", "space_id": "project-demo"},
        "metadata.SpaceResource": {"space_type_id": "bkci", "space_id": "project-demo"},
    }


def test_get_metadata_space_fetcher_keeps_bkcc_biz_behavior(monkeypatch):
    from monitor_web.data_migrate.fetcher.metadata import space as space_fetcher

    monkeypatch.setattr(
        space_fetcher.Space.objects,
        "get_space_info_by_biz_id",
        lambda bk_biz_id: {"space_type": "bkcc", "space_id": str(bk_biz_id)},
    )

    filters = _fetcher_filters(get_metadata_space_fetcher(2))

    assert filters["metadata.SpaceDataSource"] == {"space_type_id": "bkcc", "space_id": "2"}


def test_get_metadata_space_fetcher_keeps_global_filters():
    assert all(filters is None for _model, filters, _exclude in get_metadata_space_fetcher(None))

    filters = _fetcher_filters(get_metadata_space_fetcher(0))
    assert filters["metadata.SpaceDataSource"] == {"space_type_id": "bkcc", "space_id": "0"}
