from unittest import mock

import pytest

from api.cmdb import default as cmdb


def _biz(bk_biz_id: int) -> dict:
    return {"bk_biz_id": bk_biz_id, "bk_biz_name": f"biz-{bk_biz_id}", "time_zone": "Asia/Shanghai"}


@pytest.fixture
def search_business(mocker):
    """替换 cc 客户端，隔离真实请求与缓存"""
    fake_client = mock.MagicMock()
    fake_client.request.cacheless.return_value = {"info": [_biz(2)], "count": 1}
    mocker.patch.object(cmdb.client, "search_business", fake_client)
    mocker.patch.object(cmdb.client, "search_object_attribute", return_value=[])
    return fake_client


def test_get_business_uses_cache_by_default(search_business):
    search_business.return_value = {"info": [_biz(2)], "count": 1}

    result = cmdb.GetBusiness().request(bk_tenant_id="system")

    assert [biz.bk_biz_id for biz in result] == [2]
    search_business.request.cacheless.assert_not_called()
    search_business.set_cached.assert_not_called()


def test_get_business_no_cache_backfills_shared_cache(search_business):
    result = cmdb.GetBusiness().request(bk_tenant_id="system", no_cache=True)

    assert [biz.bk_biz_id for biz in result] == [2]
    search_business.request.cacheless.assert_called_once_with(bk_tenant_id="system")
    # 非空结果需要回填共享缓存，让 web 侧不必等缓存过期
    search_business.set_cached.assert_called_once_with({"info": [_biz(2)], "count": 1}, bk_tenant_id="system")


def test_get_business_no_cache_with_archived_backfills_same_key(search_business):
    cmdb.GetBusiness().request(bk_tenant_id="system", is_archived=True, no_cache=True)

    search_business.request.cacheless.assert_called_once_with(
        bk_tenant_id="system", condition={"bk_data_status": "disabled"}
    )
    search_business.set_cached.assert_called_once_with(
        {"info": [_biz(2)], "count": 1}, bk_tenant_id="system", condition={"bk_data_status": "disabled"}
    )


def test_get_business_no_cache_skip_backfill_when_empty(search_business):
    search_business.request.cacheless.return_value = {"info": [], "count": 0}

    result = cmdb.GetBusiness().request(bk_tenant_id="system", no_cache=True)

    assert result == []
    search_business.request.cacheless.assert_called_once()
    # 空结果不回填，避免把异常数据写入缓存
    search_business.set_cached.assert_not_called()
