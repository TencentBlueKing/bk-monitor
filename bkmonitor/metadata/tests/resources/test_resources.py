import pytest

from core.drf_resource.exceptions import CustomException
from metadata.models import ESStorage, Event, EventGroup, ResultTable, TimeSeriesGroup
from metadata.resources import GetEventGroupResource, QueryTimeSeriesGroupResource
from metadata.tests.common_utils import any_return_model
from metadata.tests.task.conftest import EventGroupFakeES

pytestmark = pytest.mark.django_db

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


@pytest.mark.django_db(databases=["default", "monitor_api"])
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
            expected_group_name = f'{self.GROUP_NAME_PREFIX}{(page_number - 1) * self.PAGE_SIZE + 1}'
            assert response_data["info"][0]["time_series_group_name"] == expected_group_name
