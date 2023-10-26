import pytest

from core.drf_resource.exceptions import CustomException
from metadata.models import ESStorage, Event, EventGroup, ResultTable
from metadata.resources import GetEventGroupResource
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
