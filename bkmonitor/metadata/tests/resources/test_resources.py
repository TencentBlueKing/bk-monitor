import pytest
from django.utils import timezone

from constants.common import DEFAULT_TENANT_ID
from core.drf_resource.exceptions import CustomException
from metadata.models import (
    ESStorage,
    EsSnapshotRepository,
    EsSnapshot,
    EsSnapshotIndice,
    Event,
    EventGroup,
    ResultTable,
    TimeSeriesGroup,
)
from metadata.resources import (
    BulkCreateResultTableSnapshotResource,
    BulkModifyResultTableSnapshotResource,
    CreateResultTableSnapshotResource,
    GetEventGroupResource,
    ListResultTableSnapshotResource,
    QueryTimeSeriesGroupResource,
)
from metadata.tests.common_utils import any_return_model
from metadata.tests.task.conftest import EventGroupFakeES

pytestmark = pytest.mark.django_db(databases="__all__")

EventGroupName = "test_event_group_1"
DataID = 2000001
TableID = "gse_event_report_base_1"


@pytest.fixture
def create_and_delete_record():
    EventGroup(event_group_name=EventGroupName, bk_data_id=DataID, bk_biz_id=1, table_id=TableID).save()
    ResultTable.objects.create(table_id=TableID, bk_biz_id=1, is_custom_table=False)
    yield
    EventGroup.objects.filter(event_group_name=EventGroupName).delete()
    Event.objects.all().delete()
    ResultTable.objects.filter(table_id=TableID).delete()


def test_get_event_group_resource(mocker, create_and_delete_record):
    even_group = EventGroup.objects.get(event_group_name=EventGroupName)

    # 获取指定EventGroup信息，附加result_table_info
    resp = GetEventGroupResource().request(
        event_group_id=even_group.event_group_id, with_result_table_info=True, need_refresh=False
    )
    assert resp.pop("shipper_list", None) is not None
    assert resp == even_group.to_json()

    # 获取指定EventGroup信息，不附加result_table_info
    resp = GetEventGroupResource().request(
        event_group_id=even_group.event_group_id, with_result_table_info=False, need_refresh=False
    )
    assert resp == even_group.to_json()

    mocker.patch("metadata.models.storage.ESStorage.objects.get", side_effect=any_return_model(ESStorage)).start()
    mocker.patch("metadata.utils.es_tools.get_client", return_value=EventGroupFakeES()).start()

    # 获取指定EventGroup信息，立即刷新事件维度信息
    resp = GetEventGroupResource().request(
        event_group_id=even_group.event_group_id, with_result_table_info=False, need_refresh=True
    )
    assert resp == even_group.to_json()
    assert resp["event_info_list"][0] == Event.objects.get(event_group_id=even_group.event_group_id).to_json()

    # 不存在的EventGroup
    with pytest.raises(ValueError):
        GetEventGroupResource().request(event_group_id=123321, with_result_table_info=False, need_refresh=False)

    # 未传event_group_id参数
    with pytest.raises(CustomException):
        GetEventGroupResource().request(with_result_table_info=False, need_refresh=False)


@pytest.mark.django_db(databases="__all__")
class TestTimeSeriesGroupResource:
    """测试 TimeSeriesGroupResource。"""

    BK_DATA_ID = 1
    BK_BIZ_ID = 100
    GROUP_NAME_PREFIX = "Group "
    COUNT = 2
    PAGE_SIZE = 1

    @pytest.fixture(autouse=True)
    def groups_for_biz(self):
        """创建指定数量的数据库记录供测试使用。"""
        groups = [
            TimeSeriesGroup(
                time_series_group_name=f"{self.GROUP_NAME_PREFIX}{i}",
                bk_biz_id=self.BK_BIZ_ID,
                bk_data_id=self.BK_DATA_ID,
            )
            for i in range(1, self.COUNT + 1)
        ]
        TimeSeriesGroup.objects.bulk_create(groups)
        return groups

    @pytest.fixture(autouse=True)
    def mock_get_bcs_dataids(self, mocker):
        """Mock get_bcs_dataids 方法以返回空的测试数据。"""
        mocker.patch("metadata.resources.resources.get_bcs_dataids", return_value=([], {}))

    @pytest.fixture(autouse=True)
    def mock_settings(self, settings):
        """Mock 设置。"""
        # get_metric_info_list 中使用 native datetime 对象在 last_modify_time 字段上过滤，这里 hack 掉
        settings.USE_TZ = False

    def test_query_all_groups(self):
        """测试在不使用分页的情况下查询所有记录。"""
        request_data = {"bk_biz_id": self.BK_BIZ_ID}
        resource = QueryTimeSeriesGroupResource()
        response_data = resource.request(request_data)

        assert len(response_data) == self.COUNT
        expected_group_names = {f"{self.GROUP_NAME_PREFIX}{i}" for i in range(1, self.COUNT + 1)}
        assert {group["time_series_group_name"] for group in response_data} == expected_group_names

    def test_query_with_pagination(self):
        """测试分页。"""
        resource = QueryTimeSeriesGroupResource()

        for page_number in range(1, self.COUNT + 1):
            request_data = {
                "page_size": self.PAGE_SIZE,
                "page": page_number,
                "bk_biz_id": self.BK_BIZ_ID,
            }

            response_data = resource.request(request_data)

            assert response_data["count"] == self.COUNT
            assert len(response_data["info"]) == self.PAGE_SIZE
            # 检查每页第一项的名称是否正确
            expected_group_name = f"{self.GROUP_NAME_PREFIX}{(page_number - 1) * self.PAGE_SIZE + 1}"
            assert response_data["info"][0]["time_series_group_name"] == expected_group_name


class TestEsSnapshotResources:
    tenant = DEFAULT_TENANT_ID

    @pytest.fixture(autouse=True)
    def es_storage_records(self):
        table_ids = [
            "2_system.table_a",
            "2_system.table_b",
            "2_system.table_c",
            "table_x",
        ]
        EsSnapshotRepository.objects.update_or_create(
            repository_name="repo_a",
            cluster_id=1,
            bk_tenant_id=self.tenant,
            defaults={"creator": "tester"},
        )
        EsSnapshotRepository.objects.update_or_create(
            repository_name="repo_b",
            cluster_id=1,
            bk_tenant_id=self.tenant,
            defaults={"creator": "tester"},
        )
        EsSnapshotRepository.objects.update_or_create(
            repository_name="repo_c",
            cluster_id=1,
            bk_tenant_id=self.tenant,
            defaults={"creator": "tester"},
        )
        EsSnapshotRepository.objects.update_or_create(
            repository_name="repo_shared",
            cluster_id=1,
            bk_tenant_id=self.tenant,
            defaults={"creator": "tester"},
        )
        for table_id in table_ids:
            ESStorage.objects.update_or_create(
                table_id=table_id,
                bk_tenant_id=self.tenant,
                defaults={"storage_cluster_id": 1},
            )
        yield
        ESStorage.objects.filter(table_id__in=table_ids, bk_tenant_id=self.tenant).delete()
        EsSnapshotRepository.objects.filter(
            repository_name__in=["repo_a", "repo_b", "repo_c", "repo_shared"],
            bk_tenant_id=self.tenant,
        ).delete()

    @pytest.fixture
    def snapshot_records(self):
        tenant = DEFAULT_TENANT_ID
        base_time = timezone.now()

        snapshot_data = [
            {"table_id": "2_system.table_a", "repo": "repo_a", "status": EsSnapshot.ES_RUNNING_STATUS, "days": 7},
            {"table_id": "2_system.table_a", "repo": "repo_b", "status": EsSnapshot.ES_STOPPED_STATUS, "days": 7},
            {"table_id": "2_system.table_b", "repo": "repo_shared", "status": EsSnapshot.ES_RUNNING_STATUS, "days": 30},
            {"table_id": "2_system.table_c", "repo": "repo_shared", "status": EsSnapshot.ES_STOPPED_STATUS, "days": 14},
            {"table_id": "2_system.table_c", "repo": "repo_c", "status": EsSnapshot.ES_RUNNING_STATUS, "days": 14},
        ]

        snapshots = []
        created_index_keys = []
        for idx, item in enumerate(snapshot_data, start=1):
            snapshot = EsSnapshot.objects.create(
                table_id=item["table_id"],
                target_snapshot_repository_name=item["repo"],
                snapshot_days=item["days"],
                creator="tester",
                last_modify_user="tester",
                status=item["status"],
                bk_tenant_id=tenant,
            )
            snapshots.append(snapshot)

            EsSnapshotIndice.objects.create(
                table_id=snapshot.table_id,
                bk_tenant_id=tenant,
                snapshot_name=f"snapshot_{idx}",
                cluster_id=idx,
                repository_name=snapshot.target_snapshot_repository_name,
                index_name=f"index_{idx}",
                doc_count=idx * 10,
                store_size=idx * 100,
                start_time=base_time,
                end_time=base_time,
            )
            created_index_keys.append(
                (
                    snapshot.table_id,
                    snapshot.target_snapshot_repository_name,
                    f"snapshot_{idx}",
                    tenant,
                )
            )

        yield snapshots

        for table_id, repository_name, snapshot_name, tenant_id in created_index_keys:
            EsSnapshotIndice.objects.filter(
                table_id=table_id,
                repository_name=repository_name,
                snapshot_name=snapshot_name,
                bk_tenant_id=tenant_id,
            ).delete()
        if snapshots:
            EsSnapshot.objects.filter(id__in=[snapshot.id for snapshot in snapshots]).delete()

    def test_create_snapshot_default_status(self, mocker):
        """Ensure create API falls back to running status when client omits it."""
        snapshot_mock = mocker.Mock()
        snapshot_mock.to_json.return_value = {"table_id": "table_x"}
        create_patch = mocker.patch(
            "metadata.resources.resources.models.EsSnapshot.create_snapshot",
            return_value=snapshot_mock,
        )

        payload = {
            "bk_tenant_id": self.tenant,
            "table_id": "table_x",
            "target_snapshot_repository_name": "repo_x",
            "snapshot_days": 3,
            "operator": "tester",
        }
        response = CreateResultTableSnapshotResource().request(payload)

        assert response == {"table_id": "table_x"}
        create_patch.assert_called_once()
        _, kwargs = create_patch.call_args
        assert kwargs["status"] == EsSnapshot.ES_RUNNING_STATUS

    def test_create_snapshot_invalid_status(self):
        """Reject creation when client passes an unsupported snapshot status value."""
        payload = {
            "bk_tenant_id": self.tenant,
            "table_id": "table_x",
            "target_snapshot_repository_name": "repo_x",
            "snapshot_days": 3,
            "operator": "tester",
            "status": "invalid",
        }
        with pytest.raises(CustomException):
            CreateResultTableSnapshotResource().request(payload)

    def test_bulk_create_snapshot_conflict(self, mocker):
        """Surface backend ValueError when bulk create hits duplicate/running conflicts."""
        mocker.patch(
            "metadata.resources.resources.models.EsSnapshot.bulk_create_snapshot",
            side_effect=ValueError("conflict"),
        )
        payload = {
            "bk_tenant_id": self.tenant,
            "table_ids": ["table_a"],
            "target_snapshot_repository_name": "repo",
            "snapshot_days": 3,
            "operator": "tester",
            "status": EsSnapshot.ES_RUNNING_STATUS,
        }
        with pytest.raises(ValueError):
            BulkCreateResultTableSnapshotResource().request(payload)

    def test_bulk_modify_snapshot_invalid_status(self):
        """Validate serializer choice enforcement for bulk modify status field."""
        payload = {
            "bk_tenant_id": self.tenant,
            "table_ids": ["table_a"],
            "snapshot_days": 3,
            "operator": "tester",
            "status": "invalid",
        }
        with pytest.raises(CustomException):
            BulkModifyResultTableSnapshotResource().request(payload)

    def test_create_snapshot_running_conflict(self, snapshot_records):
        """Creating another config in same repo/table should raise duplicate repo error."""
        table_id = "2_system.table_a"
        with pytest.raises(ValueError, match="目标es集群快照仓库结果表快照已存在"):
            CreateResultTableSnapshotResource().request(
                {
                    "bk_tenant_id": self.tenant,
                    "table_id": table_id,
                    "target_snapshot_repository_name": "repo_a",
                    "snapshot_days": 5,
                    "operator": "tester",
                }
            )

    def test_modify_snapshot_running_conflict(self, snapshot_records):
        """Switching a stopped repo to running while another repo runs should fail."""
        with pytest.raises(ValueError, match="已存在启用中结果表快照"):
            EsSnapshot.modify_snapshot(
                table_id="2_system.table_a",
                snapshot_days=10,
                operator="tester",
                status=EsSnapshot.ES_RUNNING_STATUS,
                target_snapshot_repository_name="repo_b",
                bk_tenant_id=self.tenant,
            )

    def test_bulk_modify_snapshot_conflict_rollback(self, snapshot_records):
        """Bulk modify keeps data unchanged when running-conflict aborts the transaction."""
        target_table_ids = ["2_system.table_b", "2_system.table_c"]
        original_days = {
            (obj.table_id, obj.target_snapshot_repository_name): obj.snapshot_days
            for obj in EsSnapshot.objects.filter(
                table_id__in=target_table_ids,
                target_snapshot_repository_name="repo_shared",
            )
        }
        with pytest.raises(ValueError, match="已存在启用中结果表快照"):
            BulkModifyResultTableSnapshotResource().request(
                {
                    "bk_tenant_id": self.tenant,
                    "table_ids": target_table_ids,
                    "snapshot_days": 90,
                    "operator": "tester",
                    "status": EsSnapshot.ES_RUNNING_STATUS,
                    "target_snapshot_repository_name": "repo_shared",
                }
            )
        for snapshot in EsSnapshot.objects.filter(
            table_id__in=target_table_ids,
            target_snapshot_repository_name="repo_shared",
        ):
            assert snapshot.snapshot_days == original_days[
                (snapshot.table_id, snapshot.target_snapshot_repository_name)
            ]

    def test_validated_snapshot_requires_repository(self, snapshot_records):
        """validated_snapshot must force repository_name when multiple configs exist."""
        with pytest.raises(ValueError, match="快照仓库名称不能为空"):
            EsSnapshot.validated_snapshot(
                table_id="2_system.table_a",
                bk_tenant_id=self.tenant,
            )

    @pytest.mark.django_db(databases="__all__")
    def test_list_snapshot_repository_filter(self, snapshot_records):
        """List API should filter/aggregate stats across table_id + repository combinations."""
        resource = ListResultTableSnapshotResource()

        table_ids = ["2_system.table_a", "2_system.table_b"]
        all_results = resource.request({
            "bk_tenant_id": self.tenant,
            "table_ids": table_ids,
        })
        assert len(all_results) == 3
        doc_counts = {
            (item["table_id"], item["target_snapshot_repository_name"]): item["doc_count"]
            for item in all_results
        }
        assert doc_counts[("2_system.table_a", "repo_a")] == 10
        assert doc_counts[("2_system.table_a", "repo_b")] == 20
        assert doc_counts[("2_system.table_b", "repo_shared")] == 30

        repo_filtered = resource.request(
            {
                "bk_tenant_id": self.tenant,
                "repository_names": ["repo_b"],
                "table_ids": table_ids,
            }
        )
        assert len(repo_filtered) == 1
        assert repo_filtered[0]["target_snapshot_repository_name"] == "repo_b"
        assert repo_filtered[0]["doc_count"] == 20

        empty_filtered = resource.request(
            {
                "bk_tenant_id": self.tenant,
                "repository_names": ["missing"],
                "table_ids": table_ids,
            }
        )
        assert empty_filtered == []
