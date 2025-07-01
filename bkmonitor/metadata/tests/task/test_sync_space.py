import json

import pytest
from mockredis.redis import mock_redis_client

from api.cmdb.define import Business
from metadata.models import BCSClusterInfo
from metadata.models.space import Space, SpaceDataSource, SpaceResource
from metadata.models.space.constants import (
    SPACE_DETAIL_REDIS_KEY_PREFIX,
    SYSTEM_USERNAME,
    SpaceTypes,
)
from metadata.task.sync_space import (
    refresh_bkci_space_name,
    refresh_cluster_resource,
    sync_bcs_space,
    sync_bkcc_space,
    sync_bkcc_space_data_source,
)
from metadata.tests.common_utils import MockCache

pytestmark = pytest.mark.django_db(databases="__all__")


def test_sync_bkcc_space(create_and_delete_record, table_id, mocker):
    biz_id = 1
    mocker.patch(
        "core.drf_resource.api.cmdb.get_business", return_value=[Business(bk_biz_id=biz_id, bk_biz_name="test")]
    )

    mocker.patch("redis.Redis", side_effect=mock_redis_client)
    mocker.patch("metadata.utils.redis_tools.RedisTools.push_space_to_redis", return_value=True)
    client = mock_redis_client()

    def mock_hmset_redis(*args, **kwargs):
        client.hmset(*args, **kwargs)

    mocker.patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis", side_effect=mock_hmset_redis)

    sync_bkcc_space()

    space_obj = Space.objects.filter(space_type_id=SpaceTypes.BKCC.value, space_id=str(biz_id))
    assert space_obj.exists()

    data = client.hgetall(f"{SPACE_DETAIL_REDIS_KEY_PREFIX}:{SpaceTypes.BKCC.value}__{biz_id}")
    for key, val in data.items():
        assert key.decode("utf-8") == table_id
        val_dict = json.loads(val.decode("utf-8"))
        for k in ["type", "field", "measurement_type", "bk_data_id", "filters", "segmented_enable", "data_label"]:
            assert k in val_dict


def test_sync_bcs_space(create_and_delete_record, table_id, mocker):
    fake_project_id = "projectid"
    fake_project_name = "projectname"
    fake_project_code = "projectcode"
    fake_bk_biz_id = "1"
    fake_data_id = 1
    # mock get projects
    mocker.patch(
        "metadata.task.sync_space.get_valid_bcs_projects",
        return_value=[
            {
                "project_id": fake_project_id,
                "name": fake_project_name,
                "project_code": fake_project_code,
                "bk_biz_id": fake_bk_biz_id,
            }
        ],
    )
    mocker.patch(
        "core.drf_resource.api.bcs_cluster_manager.get_project_clusters",
        return_value=[
            {
                "project_id": fake_project_id,
                "cluster_id": "BCS-K8S-00000",
                "bk_biz_id": fake_bk_biz_id,
                "is_shared": False,
            },
            {
                "project_id": fake_project_id,
                "cluster_id": "BCS-K8S-00001",
                "bk_biz_id": fake_bk_biz_id,
                "is_shared": True,
            },
        ],
    )
    mocker.patch(
        "core.drf_resource.api.bcs_cluster_manager.get_shared_clusters",
        return_value=[{"project_id": fake_project_id, "cluster_id": "BCS-K8S-00001"}],
    )
    mocker.patch(
        "core.drf_resource.api.bcs.fetch_shared_cluster_namespaces",
        return_value=[
            {
                "project_id": fake_project_id,
                "cluster_id": "BCS-K8S-00001",
                "namespace": "test1",
            },
            {
                "project_id": fake_project_id,
                "cluster_id": "BCS-K8S-00001",
                "namespace": "test2",
            },
        ],
    )
    mocker.patch("redis.Redis", side_effect=mock_redis_client)
    mocker.patch("metadata.utils.redis_tools.RedisTools.push_space_to_redis", return_value=True)

    client = mock_redis_client()

    def mock_hmset_redis(*args, **kwargs):
        client.hmset(*args, **kwargs)

    mocker.patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis", side_effect=mock_hmset_redis)
    # 创建业务所属的data id
    SpaceDataSource.objects.create(
        creator=SYSTEM_USERNAME,
        space_type_id=SpaceTypes.BKCC.value,
        space_id=fake_bk_biz_id,
        bk_data_id=fake_data_id,
    )
    # 添加注册的集群信息
    BCSClusterInfo.objects.get_or_create(
        cluster_id="BCS-K8S-00000",
        bk_biz_id=fake_bk_biz_id,
        project_id=fake_project_id,
        status="running",
        domain_name="example.com",
        port=80,
        server_address_path="test",
        K8sMetricDataID=100011,
    )

    sync_bcs_space()

    space_obj = Space.objects.filter(space_type_id=SpaceTypes.BKCI.value, space_id=fake_project_code)
    assert space_obj.exists()

    space_data_id_obj = SpaceDataSource.objects.filter(space_type_id=SpaceTypes.BKCI.value, space_id=fake_project_code)
    assert space_data_id_obj.exists()
    assert not space_data_id_obj.first().from_authorization

    space_res = SpaceResource.objects.filter(space_type_id=SpaceTypes.BKCI.value, space_id=fake_project_code)
    assert len(space_res) == 2
    res_type = []
    for sr in space_res:
        res_type.append(sr.resource_type)
    assert set(res_type) == {"bkcc", "bcs"}

    data = client.hgetall(f"{SPACE_DETAIL_REDIS_KEY_PREFIX}:{SpaceTypes.BKCI.value}__{fake_project_code}")
    for key, val in data.items():
        assert key.decode("utf-8") == table_id
        val_dict = json.loads(val.decode("utf-8"))
        for k in ["type", "field", "measurement_type", "segmented_enable", "bk_data_id", "filters", "data_label"]:
            assert k in val_dict


def test_sync_bkcc_space_data_source(create_and_delete_record, table_id, mocker):
    mocker.patch("redis.Redis", side_effect=mock_redis_client)
    mocker.patch("metadata.utils.redis_tools.RedisTools.push_space_to_redis", return_value=True)

    client = mock_redis_client()

    def mock_hmset_redis(*args, **kwargs):
        client.hmset(*args, **kwargs)

    mocker.patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis", side_effect=mock_hmset_redis)

    # 测试新加
    test_create_data_id = 199
    mocker.patch("metadata.task.sync_space.get_biz_data_id", return_value={1: [test_create_data_id]})

    sync_bkcc_space_data_source()

    assert SpaceDataSource.objects.filter(space_type_id="bkcc", space_id="1", bk_data_id=test_create_data_id).exists()


def test_refresh_cluster_resource(create_and_delete_record, create_and_delete_space, mocker):
    # 测试新加
    fake_project_id = "projectid"
    fake_project_cluster_id = "BCS-K8S-00001"
    fake_shared_cluster_id = "BCS-K8S-00002"
    mocker.patch(
        "core.drf_resource.api.bcs_cluster_manager.get_project_clusters",
        return_value=[
            {
                "project_id": fake_project_id,
                "cluster_id": fake_project_cluster_id,
                "is_shared": False,
            },
            {
                "project_id": fake_project_id,
                "cluster_id": fake_shared_cluster_id,
                "is_shared": False,
            },
            {
                "project_id": fake_project_id,
                "cluster_id": fake_shared_cluster_id,
                "is_shared": True,
            },
        ],
    )
    mocker.patch(
        "core.drf_resource.api.bcs.fetch_shared_cluster_namespaces",
        return_value=[],
    )
    mocker.patch("metadata.task.sync_space.get_metadata_cluster_list", return_value=["BCS-K8S-00001", "BCS-K8S-00002"])
    mocker.patch("redis.client.StrictRedis", side_effect=mock_redis_client)
    mocker.patch("metadata.utils.redis_tools.RedisTools.push_and_publish_spaces", return_value=True)

    refresh_cluster_resource()

    # 校验记录存在
    assert SpaceResource.objects.filter(space_id=fake_project_id).exists()
    # 校验维度
    dimensions = SpaceResource.objects.get(space_type_id="bkci", space_id=fake_project_id).dimension_values
    # 校验维度中集群一致
    assert {fake_project_cluster_id, fake_shared_cluster_id} == {d["cluster_id"] for d in dimensions}
    # 校验项目集群的命名空间为空
    for d in dimensions:
        assert d["namespace"] is None


def test_refresh_cluster_resource_with_share_clusters(create_and_delete_record, create_and_delete_space, mocker):
    # 测试新加
    fake_project_id = "projectid"
    fake_project_cluster_id = "BCS-K8S-00001"
    fake_shared_cluster_id = "BCS-K8S-00002"
    mocker.patch(
        "core.drf_resource.api.bcs_cluster_manager.get_project_clusters",
        return_value=[
            {
                "project_id": fake_project_id,
                "cluster_id": fake_project_cluster_id,
                "is_shared": False,
            },
            {
                "project_id": fake_project_id,
                "cluster_id": fake_shared_cluster_id,
                "is_shared": True,
            },
        ],
    )
    mocker.patch(
        "core.drf_resource.api.bcs.fetch_shared_cluster_namespaces",
        return_value=[
            {
                "project_id": fake_project_id,
                "cluster_id": fake_shared_cluster_id,
                "namespace": "test1",
            },
            {
                "project_id": fake_project_id,
                "cluster_id": fake_shared_cluster_id,
                "namespace": "test2",
            },
            {
                "project_id": fake_project_id,
                "cluster_id": "BCS-K8S-00003",
                "namespace": "test3",
            },
        ],
    )
    mocker.patch("metadata.task.sync_space.get_metadata_cluster_list", return_value=["BCS-K8S-00001", "BCS-K8S-00002"])
    mocker.patch("redis.client.StrictRedis", side_effect=mock_redis_client)
    mocker.patch("metadata.utils.redis_tools.RedisTools.push_and_publish_spaces", return_value=True)
    mocker.patch("alarm_backends.core.storage.redis.Cache.__new__", return_value=MockCache())

    refresh_cluster_resource()

    # 校验记录存在
    assert SpaceResource.objects.filter(space_id=fake_project_id).exists()
    # 校验维度
    dimensions = SpaceResource.objects.get(space_type_id="bkci", space_id=fake_project_id).dimension_values
    # 校验维度中集群一致
    assert {fake_project_cluster_id, fake_shared_cluster_id} == {d["cluster_id"] for d in dimensions}
    # 共享集群所在项目查询时，对应的命名空间都为空
    for d in dimensions:
        if d["cluster_id"] == fake_project_cluster_id:
            assert d["namespace"] is None
        if d["cluster_id"] == fake_shared_cluster_id:
            assert set(d["namespace"]) == {"test1", "test2"}


def test_refresh_bkci_space_name(create_and_delete_record, create_and_delete_space, mocker):
    fake_project_id = "projectid"
    fake_project_name = "projectname"
    fake_project_code = "projectid"
    fake_bk_biz_id = "1"
    fake_project_name_two = "testbkci1"

    mocker.patch(
        "metadata.task.sync_space.get_bkci_projects",
        return_value=[
            {
                "project_id": fake_project_id,
                "name": fake_project_name,
                "project_code": fake_project_code,
                "bk_biz_id": fake_bk_biz_id,
            }
        ],
    )
    mocker.patch("redis.Redis", side_effect=mock_redis_client)
    # 执行更新操作
    refresh_bkci_space_name()

    # 更新的记录的名称
    assert Space.objects.get(space_type_id="bkci", space_id=fake_project_id).space_name == fake_project_name
    # 没有变更
    assert Space.objects.get(space_type_id="bkci", space_id="testbkci1").space_name == fake_project_name_two
