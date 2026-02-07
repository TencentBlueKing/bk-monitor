import django
import pytest

from apm.constants import ApmCacheType
from apm.core.discover.instance import InstanceDiscover
from apm.core.handlers.apm_cache_handler import ApmCacheHandler
from apm.models import ApmApplication, TopoInstance
from apm.models.datasource import TraceDataSource

pytestmark = pytest.mark.django_db

SPAN_DATA_LIST = [
    {
        "attributes": {
            "api_name": "Mysql:Unknown:Unknown",
            "db.name": "",
            "db.statement": "UPDATE `django_session` SET `session_data` = %s WHERE`django_session`.`session_key` = %s",
            "db.system": "mysql",
            "net.peer.port": 3306,
        },
        "elapsed_time": 1091,
        "end_time": 1696733860660293,
        "events": [],
        "kind": 3,
        "links": [],
        "parent_span_id": "d2acb401061821e7",
        "resource": {
            "bk.instance.id": "python:bk_monitorv3_web::127.0.0.1:",
            "net.host.ip": "127.0.0.1",
            "service.name": "bk_monitorv3_web",
            "telemetry.sdk.language": "python",
            "telemetry.sdk.name": "opentelemetry",
            "telemetry.sdk.version": "1.11.1",
        },
        "span_id": "529b2a63944ccc07",
        "span_name": "UPDATE",
        "start_time": 1696733860659202,
        "status": {"code": 0, "message": ""},
        "time": "1696733864000",
        "trace_id": "1a45b33f9f0b1014348f6e0a08b31506",
        "trace_state": "",
    },
    {
        "trace_state": "",
        "status": {"code": 0, "message": ""},
        "span_name": "Elasticsearch/",
        "span_id": "5325d04510fae007",
        "attributes": {
            "apdex_type": "satisfied",
            "db.system": "elasticsearch",
            "elasticsearch.url": "/",
            "elasticsearch.method": "GET",
        },
        "links": [],
        "time": "1696923681000",
        "trace_id": "99731a2ca12d15f335c1cc6e7f753656",
        "kind": 3,
        "events": [],
        "resource": {
            "telemetry.sdk.name": "opentelemetry",
            "telemetry.sdk.version": "1.11.1",
            "service.name": "bk_monitorv3_api",
            "bk.instance.id": "python::bk_monitorv3_api",
            "net.host.ip": "127.0.0.1",
            "telemetry.sdk.language": "python",
        },
        "elapsed_time": 5730,
        "end_time": 1696923678388608,
        "start_time": 1696923678382877,
        "parent_span_id": "e959d22f9f027b2e",
    },
]
BK_BIZ_ID = 2
APP_NAME = "test_topoinstance_demo"
APP_ALIAS = "test_topoinstance_demo"
DESCRIPTION = "this is demo"
TABLE_ID = "2_bkapm.test_topoinstance_demo"
STORAGE_CLUSTER_ID = 3


class TemInstanceDiscover(InstanceDiscover):
    MAX_COUNT = 2


@pytest.mark.django_db(databases="__all__")
class TestTopoInstance(django.test.TestCase):
    databases = {
        "default",
        "monitor_api",
    }

    def test_topo_instance(self):
        from metadata import models as metadata_models

        ApmApplication.objects.create(
            bk_biz_id=BK_BIZ_ID, app_name=APP_NAME, app_alias=APP_ALIAS, description=DESCRIPTION
        )
        TraceDataSource.objects.create(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME, result_table_id=TABLE_ID)

        metadata_models.ESStorage.objects.create(table_id=TABLE_ID, storage_cluster_id=STORAGE_CLUSTER_ID)

        topo_instance = TemInstanceDiscover(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)

        exists_data = topo_instance.list_exists()
        topo_instance.discover(SPAN_DATA_LIST, exists_data)
        queryset = TopoInstance.objects.filter(bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)
        assert queryset.count() <= topo_instance.MAX_COUNT

        exists_data = topo_instance.list_exists()
        topo_instance.discover(SPAN_DATA_LIST, exists_data)
        name = ApmCacheHandler.get_cache_key(ApmCacheType.TOPO_INSTANCE, bk_biz_id=BK_BIZ_ID, app_name=APP_NAME)
        cache_data = ApmCacheHandler().get_cache_data(name)

        assert len(cache_data) <= topo_instance.MAX_COUNT

        data = {str(i.id) + ":" + i.instance_id for i in list(queryset)}

        for k in cache_data.keys():
            assert k in data

        TopoInstance.objects.all().delete()
        ApmApplication.objects.all().delete()
        TraceDataSource.objects.all().delete()
        metadata_models.ESStorage.objects.all().delete()

        ApmCacheHandler().redis_client.delete(name)
