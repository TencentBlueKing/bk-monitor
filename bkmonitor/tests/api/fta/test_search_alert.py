# -*- coding: utf-8 -*-

import time
from unittest.mock import patch

from django.test import TestCase
from monitor_web.alert_events.resources import GraphPointResource

from bkmonitor.documents import AlertDocument, EventDocument
from bkmonitor.utils.elasticsearch.fake_elasticsearch import FakeElasticsearchBucket

patch("elasticsearch_dsl.connections.Connections.create_connection", return_value=FakeElasticsearchBucket()).start()

from fta_web.home.resources import BizWithAlertStatisticsResource


class SearchAlertCase(TestCase):
    def setUp(self) -> None:
        for doc in [AlertDocument, EventDocument]:
            ilm = doc.get_lifecycle_manager()
            ilm.es_client.indices.delete(index=doc.Index.name)

    def tearDown(self) -> None:
        for doc in [AlertDocument, EventDocument]:
            ilm = doc.get_lifecycle_manager()
            ilm.es_client.indices.delete(index=doc.Index.name)

    def test_something(self):
        alert_id = "{}1111111".format(int(time.time()))
        alert = AlertDocument(
            **{
                "id": alert_id,
                "begin_time": int(time.time()),
                "create_time": int(time.time()),
                "end_time": int(time.time()),
                "is_shielded": False,
                "is_handled": False,
                "is_ack": False,
                "dedupe_md5": "testdedupe_md5",
                "assignee": ["admin"],
            }
        )
        alert_handle = AlertDocument(
            **{
                "id": "22222",
                "begin_time": int(time.time()),
                "create_time": int(time.time()),
                "end_time": int(time.time()),
                "is_shielded": True,
                "is_handled": False,
                "is_ack": False,
                "assignee": ["admin"],
            }
        )
        AlertDocument.bulk_create([alert, alert_handle])
        md5test = AlertDocument.get_by_dedupe_md5(dedupe_md5="testdedupe_md5")
        self.assertIsNotNone(md5test)
        alert_from_db = AlertDocument.get(id=alert_id)
        self.assertIsNotNone(alert_from_db)

        search = AlertDocument.search()

        # brand_name = A('terms', field='is_handled')
        # brand_pk = A('terms', field='id')
        # brand_key_aggs = [
        #     # {'brand_pk': brand_pk},
        #     {'brand_name': brand_name}
        # ]
        # search.aggs.bucket("composite_test", "composite", sources=brand_key_aggs)
        search.aggs.bucket("is_handled", "terms", field="is_handled").bucket(
            "is_shielded", "terms", field="is_shielded"
        )
        result = search.execute()
        self.assertIsNotNone(result.aggs.is_handled.buckets)
        print(result.aggs.is_handled.buckets[0].is_shielded.buckets)

    def test_biz_with_alert(self):
        business_info = {
            "business_with_permission": [dict(bk_biz_id=1, bk_biz_name="1")],
            "business_list": {
                0: dict(bk_biz_id=0, bk_biz_name="0"),
                1: dict(bk_biz_id=1, bk_biz_name="1"),
                3: dict(bk_biz_id=3, bk_biz_name="3"),
            },
            "unauthorized_biz_ids": [0, 3],
        }
        patch_cmdb = patch(
            "fta_web.home.resources.BizWithAlertStatisticsResource.get_all_business_list", return_value=business_info
        )
        patch_cmdb.start()
        alert_id_template = "%s1111111{}" % (int(time.time()))
        alerts = [
            AlertDocument(
                **{
                    "id": alert_id_template.format(i),
                    "event": EventDocument(**{"bk_biz_id": i % 2}),
                    "begin_time": int(time.time()),
                    "create_time": int(time.time()),
                    "end_time": int(time.time()),
                    "is_shielded": False,
                    "is_handled": False,
                    "is_ack": False,
                    "assignee": ["admin"],
                }
            )
            for i in range(0, 10)
        ]

        AlertDocument.bulk_create(alerts)
        rsp = BizWithAlertStatisticsResource().perform_request(validated_request_data={})
        self.assertEqual(rsp["business_with_alert"], [dict(bk_biz_id=0, bk_biz_name="0")])
        self.assertEqual(rsp["business_with_permission"], [dict(bk_biz_id=1, bk_biz_name="1")])
        patch_cmdb.stop()

    def test_graph_point(self):
        promql_strategy = {
            "items": [
                {
                    "algorithms": [
                        {
                            "level": 2,
                            "id": 6169,
                            "type": "Threshold",
                            "config": [[{"method": "eq", "threshold": 0}]],
                            "unit_prefix": "",
                        }
                    ],
                    "update_time": 1676341751,
                    "expression": "a",
                    "origin_sql": "",
                    "functions": [],
                    "query_configs": [
                        {
                            "metric_id": "avg by(instance_host,cluster_domain) (bkmonitor:exporter_twempro",
                            "promql": "for test",
                            "data_type_label": "time_series",
                            "functions": [],
                            "agg_interval": 60,
                            "alias": "a",
                            "id": 6128,
                            "data_source_label": "prometheus",
                        }
                    ],
                    "query_md5": "71dd500cd6f6e44b551dd03ad9f13018",
                    "name": "AVG(mysql_up)",
                    "no_data_config": {
                        "is_enabled": False,
                        "level": 2,
                        "continuous": 10,
                        "agg_dimension": ["bk_target_service_instance_id"],
                    },
                    "target": [[]],
                }
            ]
        }
        alerts = [
            AlertDocument(
                **{
                    "id": "11111122222",
                    "event": EventDocument(**{"bk_biz_id": 2}),
                    "begin_time": int(time.time()),
                    "create_time": int(time.time()),
                    "end_time": int(time.time()),
                    "is_shielded": False,
                    "is_handled": False,
                    "is_ack": False,
                    "assignee": ["admin"],
                    "extra_info": {"strategy": promql_strategy, "origin_alarm": {"data": {"time": 1676327400}}},
                }
            )
        ]
        request_data = {
            "bk_biz_id": 2,
            "id": "11111122222",
            "chart_type": "main",
            "time_range": "2023-02-13 17:47:27 -- 2023-02-14 17:47:27",
        }

        AlertDocument.bulk_create(alerts)
        data = GraphPointResource().perform_request(request_data)
        self.assertEqual(len(data["series"]), 0)
