import pytest

from api.cmdb import client


@pytest.fixture(autouse=True)
def bypass_base(mocker):
    mocker.patch.object(client.APIResource, "full_request_data", side_effect=lambda data: data)
    mocker.patch.object(client, "get_backend_username", return_value="admin")
    mocker.patch.object(client, "validate_bk_biz_id", side_effect=lambda bk_biz_id: bk_biz_id)


@pytest.mark.parametrize(
    "resource,sort",
    [
        (client.ListServiceInstanceDetail, "-id"),
        (client.SearchModule, "bk_module_id"),
        (client.SearchSet, "bk_set_id"),
        (client.SearchBusiness, "bk_biz_id"),
        (client.SearchDynamicGroup, "id"),
    ],
)
def test_page_without_sort_uses_unique_field_order(resource, sort):
    page = {"start": 500, "limit": 500}

    result = resource().full_request_data({"page": page})

    assert result["page"] == {"start": 500, "limit": 500, "sort": sort}
    assert page == {"start": 500, "limit": 500}


def test_explicit_sort_is_kept():
    result = client.SearchModule().full_request_data(
        {"bk_biz_id": 2, "page": {"start": 0, "limit": 200, "sort": "name"}}
    )

    assert result["page"]["sort"] == "name"


def test_request_without_page_is_unchanged():
    assert "page" not in client.ListServiceInstanceDetail().full_request_data({"bk_biz_id": 2})


def test_resource_without_page_sort_is_unchanged():
    result = client.ListBizHostsTopo().full_request_data({"page": {"start": 0, "limit": 500}})

    assert result["page"] == {"start": 0, "limit": 500}
