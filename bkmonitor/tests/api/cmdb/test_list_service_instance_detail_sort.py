import pytest

from api.cmdb import client


@pytest.fixture
def full_request_data(mocker):
    mocker.patch.object(client.CMDBBaseResource, "full_request_data", side_effect=lambda data: data)
    return client.ListServiceInstanceDetail().full_request_data


def test_page_without_sort_uses_unique_id_order(full_request_data):
    page = {"start": 500, "limit": 500}

    result = full_request_data({"bk_biz_id": 2, "service_instance_ids": [1, 2], "page": page})

    assert result["page"] == {"start": 500, "limit": 500, "sort": "-id"}
    assert page == {"start": 500, "limit": 500}


def test_explicit_sort_is_kept(full_request_data):
    result = full_request_data({"bk_biz_id": 2, "page": {"start": 0, "limit": 200, "sort": "name"}})

    assert result["page"]["sort"] == "name"


def test_request_without_page_is_unchanged(full_request_data):
    assert full_request_data({"bk_biz_id": 2}) == {"bk_biz_id": 2}
