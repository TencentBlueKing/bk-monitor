# -*- coding: utf-8 -*-
import json

import pytest
from django.core.cache import cache
from mockredis import mock_redis_client
from rest_framework.exceptions import ValidationError

from bkmonitor.utils.local import local
from core.drf_resource.exceptions import CustomException
from metadata import models
from metadata.models.space import (
    Space,
    SpaceDataSource,
    SpaceResource,
    SpaceType,
    constants,
)
from metadata.models.space.constants import SpaceTypes
from metadata.resources import (
    CreateSpaceResource,
    DisableSpaceResource,
    GetBizRelatedBkciSpacesResource,
    GetSpaceDetailResource,
    ListSpacesResource,
    ListSpaceTypesResource,
    RefreshMetricForKihan,
    UpdateSpaceResource,
)
from metadata.tests.common_utils import generate_random_string
from metadata.utils.redis_tools import RedisTools

pytestmark = pytest.mark.django_db
DEFAULT_DIMENSION_FIELDS = ["project_id"]
TYPE_ID = generate_random_string()
SPACE_NAME = generate_random_string()
SPACE_ID = generate_random_string()
BK_DATA_ID = 1
CLUSTER_ID = generate_random_string()


@pytest.fixture
def create_and_delete_space_record():
    SpaceType.objects.create(type_id=TYPE_ID, type_name=SPACE_NAME, dimension_fields=["project_id"])
    Space.objects.create(space_type_id=TYPE_ID, space_id=SPACE_ID, space_name=SPACE_NAME, space_code=SPACE_ID)
    SpaceDataSource.objects.create(space_type_id=TYPE_ID, space_id=SPACE_ID, bk_data_id=BK_DATA_ID)
    SpaceResource.objects.create(
        space_type_id=TYPE_ID,
        space_id=SPACE_ID,
        resource_type=TYPE_ID,
        resource_id=SPACE_ID,
        dimension_values=[{"project_id": SPACE_ID, "cluster_id": CLUSTER_ID}],
    )
    yield
    SpaceResource.objects.all().delete()
    SpaceDataSource.objects.all().delete()
    Space.objects.all().delete()
    SpaceType.objects.all().delete()


@pytest.fixture
def create_or_delete_records(mocker):
    models.SpaceResource.objects.create(
        space_type_id=SpaceTypes.BKCI.value, space_id='space1', resource_type=SpaceTypes.BKCC.value, resource_id=1001
    )
    models.SpaceResource.objects.create(
        space_type_id=SpaceTypes.BKCI.value, space_id='space2', resource_type=SpaceTypes.BKCC.value, resource_id=1001
    )
    models.SpaceResource.objects.create(
        space_type_id=SpaceTypes.BKCI.value, space_id='space3', resource_type=SpaceTypes.BKCC.value, resource_id=1002
    )
    yield
    models.SpaceResource.objects.all().delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_get_biz_related_bkci_spaces_resource(create_or_delete_records):
    """
    测试获取业务关联的bkci空间
    """
    params = dict(space_id=1001)
    expected = ['space1', 'space2']
    result = GetBizRelatedBkciSpacesResource().request(params)
    assert len(result) == 2
    assert set(result) == set(expected)


def test_list_space_types(create_and_delete_space_record):
    result = ListSpaceTypesResource().request()
    assert len(result) == 1


def test_list_space(create_and_delete_space_record):
    result = ListSpacesResource().request()
    assert "count" in result
    assert "list" in result
    assert type(result["list"]) == list
    assert result["count"] == 1

    result = ListSpacesResource().request(space_id="notfound")
    assert result["count"] == 0

    result = ListSpacesResource().request(space_name="notfound")
    assert result["count"] == 0

    # 再创建一条，测试分页
    type_id = generate_random_string()
    name = generate_random_string()
    space_id = generate_random_string()
    Space.objects.create(space_type_id=type_id, space_id=space_id, space_name=name, space_code=space_id)

    result = ListSpacesResource().request()
    assert result["count"] == 2

    result = ListSpacesResource().request(page=1, page_size=1)
    assert len(result["list"]) == 1

    # 如果需要展示详细信息，判断返回字段存在
    result = ListSpacesResource().request(is_detail=True)
    results = result["list"]
    assert "data_sources" in results[0]
    assert "resources" in results[0]


def test_get_space_detail(create_and_delete_space_record):
    # 判断空间 ID 不存在
    with pytest.raises(ValueError):
        GetSpaceDetailResource().request(space_type_id="notexist", space_id="notfound")

    # 获取详情
    result = GetSpaceDetailResource().request(space_type_id=TYPE_ID, space_id=SPACE_ID)
    for key in ["resources", "data_sources"]:
        assert key in result

    assert result["resources"][0]["resource_id"] == SPACE_ID
    assert result["data_sources"][0]["bk_data_id"] == BK_DATA_ID


def test_create_space(create_and_delete_space_record, mocker):
    space_id = generate_random_string()
    space_name = generate_random_string()
    req_data = {
        "creator": "admin",
        "space_type_id": TYPE_ID,
        "space_id": space_id,
        "space_name": space_name,
        "space_code": space_id,
        "resources": [{"resource_type": TYPE_ID, "resource_id": space_id}],
    }

    # 校验空间类型不存在
    with pytest.raises(CustomException):
        _req_data = req_data.copy()
        _req_data.update({"space_type_id": "notfound"})
        CreateSpaceResource().request(**_req_data)

    # 校验名称已经存在
    with pytest.raises(CustomException):
        _req_data = req_data.copy()
        _req_data.update({"space_name": SPACE_NAME})
        CreateSpaceResource().request(**_req_data)

    # 校验空间 ID 已存在
    with pytest.raises(CustomException):
        _req_data = req_data.copy()
        _req_data.update({"space_id": SPACE_ID})
        CreateSpaceResource().request(**_req_data)

    # 绑定的资源类型不存在
    with pytest.raises(CustomException):
        _req_data = req_data.copy()
        _req_data.update({"resources": [{"resource_type": "notfound", "resource_id": "test"}]})
        CreateSpaceResource().request(**_req_data)

    # 创建空间
    mocker.patch("metadata.task.tasks.push_space_to_redis.delay", return_value=True)
    result = CreateSpaceResource().request(**req_data)
    for key in ["space_type_id", "space_id", "space_name", "space_code"]:
        assert key in result
    assert result["space_id"] == space_id
    assert result["space_name"] == space_name
    # 查询空间存在
    space_obj = Space.objects.get(space_type_id=TYPE_ID, space_id=space_id)
    space_obj.space_code = space_id
    space_resource = SpaceResource.objects.filter(space_type_id=TYPE_ID, space_id=space_id).values(
        "resource_type", "resource_id"
    )
    assert len(space_resource) == 1
    assert space_resource[0]["resource_type"] == TYPE_ID
    # 校验开启容器服务
    assert space_obj.is_bcs_valid


def test_update_space(create_and_delete_space_record):
    space_name = generate_random_string()
    resource_id = "100149"
    resource_type = "bkcc"
    req_data = {
        "updater": "admin",
        "space_type_id": TYPE_ID,
        "space_id": SPACE_ID,
        "space_name": space_name,
        "resources": [
            {"resource_type": resource_type, "resource_id": resource_id},
            {"resource_type": TYPE_ID, "resource_id": SPACE_ID},
        ],
    }

    # 空间名称已经存在
    with pytest.raises(CustomException):
        exist_space_name = "existname"
        Space.objects.create(
            space_type_id=TYPE_ID, space_id=resource_id, space_name=exist_space_name, space_code=SPACE_ID
        )
        _req_data = req_data.copy()
        _req_data["space_name"] = exist_space_name
        UpdateSpaceResource().request(**_req_data)
        Space.objects.create(space_type_id=TYPE_ID, space_id=resource_id).delete()

    # 绑定资源的类型不存在
    with pytest.raises(CustomException):
        UpdateSpaceResource().request(**req_data)

    # 更新资源
    # 创建资源类型
    SpaceType.objects.create(type_id=resource_type, type_name=resource_type)
    UpdateSpaceResource().request(**req_data)


def test_update_space_code(create_and_delete_space_record):
    req_data = {
        "updater": "admin",
        "space_type_id": TYPE_ID,
        "space_id": SPACE_ID,
        "space_code": SPACE_ID,
    }

    # 更新空间
    UpdateSpaceResource().request(**req_data)
    assert Space.objects.get(space_type_id=TYPE_ID, space_id=SPACE_ID).is_bcs_valid


def test_disable_space(create_and_delete_space_record):
    result = DisableSpaceResource().request(spaces=[{"space_type_id": TYPE_ID, "space_id": SPACE_ID}])
    assert len(result) == 1
    assert result[0]["space_id"] == SPACE_ID


@pytest.fixture
def patch_redis_tools(mocker):
    client = mock_redis_client()

    def mock_hget_redis(*args, **kwargs):
        return client.hget(*args, **kwargs)

    def mock_hmset_redis(*args, **kwargs):
        client.hmset(*args, **kwargs)

    def mock_publish(*args, **kwargs):
        client.publish(*args, **kwargs)

    mocker.patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis", side_effect=mock_hmset_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.hget", side_effect=mock_hget_redis)
    mocker.patch("metadata.utils.redis_tools.RedisTools.publish", side_effect=mock_publish)

    data = {
        "type": "bkcc",
        "db": "555_bkmonitor_time_series_539389",
        "measurement": "__default__",
        "clusterID": 115,
        "storageId": "555",
        "clusterName": "",
        "field": ["a", "b", "c"],
        "measurement_type": "bk_split_measurement",
        "segmented_enable": True,
        "bk_data_id": "539389",
        "filters": [],
        "retention_policies": {"autogen": {"is_default": True, "resolution": 0}},
    }
    # 预设数据
    mock_hmset_redis(
        f"{constants.SPACE_REDIS_KEY}:{RefreshMetricForKihan.SPACE_UID}",
        {RefreshMetricForKihan.TABLE_ID: json.dumps(data)},
    )


class TestRefreshMetricForKihan:
    def test_rate_limit(self):
        cache.set(RefreshMetricForKihan.RATE_LIMIT_KEY, 1, RefreshMetricForKihan.RATE_LIMIT_TIMEOUT)
        with pytest.raises(ValidationError):
            RefreshMetricForKihan().request()

    def test_push_data(self, mocker, patch_redis_tools):
        # 调整为 0, 跳过校验
        cache.set(RefreshMetricForKihan.RATE_LIMIT_KEY, 0, RefreshMetricForKihan.RATE_LIMIT_TIMEOUT)

        self._mocker_data(mocker, patch_redis_tools)

        # 更新数据
        RefreshMetricForKihan().request()

        redis_data = RedisTools.hget(
            f"{constants.SPACE_CHANNEL}:{RefreshMetricForKihan.SPACE_UID}", RefreshMetricForKihan.TABLE_ID
        )
        redis_data = json.loads(redis_data.decode("utf-8"))
        assert len(redis_data["field"]) == 5

    def test_check_metric_count(self, mocker, patch_redis_tools):
        cache.set(RefreshMetricForKihan.RATE_LIMIT_KEY, 0, RefreshMetricForKihan.RATE_LIMIT_TIMEOUT)

        self._mocker_data(mocker, patch_redis_tools)

        class MockerResult:
            def json(self):
                return {"data": [{"metric": f"{i}"} for i in range(1, 1000)]}

        mocker.patch("requests.get", return_value=MockerResult())

        with pytest.raises(ValidationError):
            RefreshMetricForKihan().request()

    def _mocker_data(self, mocker, patch_redis_tools):
        class MockerResult:
            def json(self):
                return {"data": [{"metric": "a"}, {"metric": "d"}, {"metric": "e"}]}

        mocker.patch("requests.get", return_value=MockerResult())

        class MockerRequest:
            def __init__(self):
                self.META = {"HTTP_X_PROM_DOMAIN": "http://test.example.com"}

        setattr(local, "current_request", MockerRequest())
