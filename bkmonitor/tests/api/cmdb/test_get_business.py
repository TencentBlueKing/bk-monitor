from unittest import mock

import pytest

from api.cmdb import default as cmdb


def _biz(bk_biz_id: int) -> dict:
    return {"bk_biz_id": bk_biz_id, "bk_biz_name": f"biz-{bk_biz_id}", "time_zone": "Asia/Shanghai"}


@pytest.fixture
def search_business(mocker):
    """替换 cc 客户端，隔离真实请求与缓存"""
    fake_client = mock.MagicMock()
    fake_client.request.refresh.return_value = {"info": [_biz(2)], "count": 1}
    mocker.patch.object(cmdb.client, "search_business", fake_client)
    mocker.patch.object(cmdb.client, "search_object_attribute", return_value=[])
    return fake_client


def test_get_business_refresh_cc_cache(search_business):
    result = cmdb.GetBusiness().request(bk_tenant_id="system")

    assert [biz.bk_biz_id for biz in result] == [2]
    # 强制刷新缓存，保证拿到实时业务列表并回写共享缓存
    search_business.request.refresh.assert_called_once_with(bk_tenant_id="system")


def test_get_business_refresh_cc_cache_with_archived(search_business):
    search_business.request.refresh.return_value = {"info": [], "count": 0}

    cmdb.GetBusiness().request(bk_tenant_id="system", is_archived=True)

    # 归档业务的 key 必须带上 condition，否则会刷新到另一份缓存
    search_business.request.refresh.assert_called_once_with(
        bk_tenant_id="system", condition={"bk_data_status": "disabled"}
    )
