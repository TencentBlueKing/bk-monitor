import json
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.api.modules.bkdata_access import _BkDataAccessApi
from apps.api.modules.bkdata_meta import _BkDataMetaApi
from apps.api.modules.gse import _GseApi
from apps.exceptions import ApiResultError, PermissionError as BklogPermissionError, ValidationError
from apps.log_admin_resource.handlers.datalink_control_plane import (
    FUNC_NAME,
    get_datalink_control_plane_snapshot,
)
from apps.log_admin_resource.registry import AdminResourceRegistry, FUNCTIONS


MODULE = "apps.log_admin_resource.handlers.datalink_control_plane"
DATA_ID = 12345
RT_NAME = "bklog_space_example"
RT_ID = "42_" + RT_NAME
DATAID_NAME = "bkm_example"


def resource(kind, name, spec, phase="Ok"):
    return {
        "kind": kind,
        "metadata": {"namespace": "bklog", "name": name},
        "spec": spec,
        "status": {"phase": phase, "message": "reconcile password=hidden"},
    }


def ref(kind, name):
    return {"kind": kind, "namespace": "bklog", "name": name}


RESOURCES = {
    ("resulttables", RT_NAME): resource("ResultTable", RT_NAME, {"bizId": 42}),
    ("databuses", RT_NAME): resource(
        "Databus",
        RT_NAME,
        {
            "sources": [ref("DataId", DATAID_NAME)],
            "sinks": [ref("ElasticSearchBinding", RT_NAME)],
        },
    ),
    ("dataids", DATAID_NAME): resource(
        "DataId",
        DATAID_NAME,
        {
            "predefined": {
                "dataId": DATA_ID,
                "topic": "test_topic",
                "channel": ref("KafkaChannel", "test-kafka"),
            }
        },
    ),
    ("elasticsearchbindings", RT_NAME): resource(
        "ElasticSearchBinding",
        RT_NAME,
        {
            "data": ref("ResultTable", RT_NAME),
            "storage": ref("ElasticSearch", "paas_cluster_1"),
        },
    ),
    ("kafkachannels", "test-kafka"): resource(
        "KafkaChannel",
        "test-kafka",
        {
            "host": "kafka.example.test",
            "port": 9092,
            "streamToId": 203,
            "v3ChannelId": None,
            "auth": {"password": "hidden"},
        },
    ),
    ("elasticsearchs", "paas_cluster_1"): resource(
        "ElasticSearch",
        "paas_cluster_1",
        {
            "host": "es.example.test",
            "port": 9200,
            "password": "hidden",
        },
    ),
}


class DataLinkControlPlaneTest(SimpleTestCase):
    def setUp(self):
        self.enterContext(patch(f"{MODULE}.require_request_tenant_id", return_value="system"))
        self.biz_check = self.enterContext(patch(f"{MODULE}.require_biz_in_request_tenant"))
        self.metadata = self.enterContext(patch(f"{MODULE}.TransferApi.get_data_id"))
        self.cluster = self.enterContext(patch(f"{MODULE}.TransferApi.get_cluster_info"))
        self.route = self.enterContext(patch(f"{MODULE}.GseApi.query_route"))
        self.stream = self.enterContext(patch(f"{MODULE}.GseApi.query_stream_to"))
        self.v4_metadata = self.enterContext(patch(f"{MODULE}.BkDataMetaApi.get_datalink_metadata"))
        self.v4_resource = self.enterContext(patch(f"{MODULE}.BkDataAccessApi.get_datalink_resource"))

        self.metadata.return_value = {
            "bk_data_id": DATA_ID,
            "bk_tenant_id": "system",
            "bk_biz_id": 0,
            "data_name": "example",
            "token": "hidden",
            "mq_config": {
                "cluster_config": {
                    "cluster_id": 106,
                    "cluster_name": "test-kafka",
                    "domain_name": "kafka.example.test",
                    "port": 9092,
                },
                "storage_config": {"topic": "test_topic"},
            },
        }
        self.cluster.return_value = [
            {
                "cluster_type": "kafka",
                "cluster_config": {
                    "cluster_id": 106,
                    "cluster_name": "test-kafka",
                    "domain_name": "kafka.example.test",
                    "port": 9092,
                    "password": "hidden",
                },
            }
        ]
        self.route.return_value = [
            {
                "metadata": {"channel_id": DATA_ID},
                "route": [
                    {
                        "name": "stream_to_test_topic",
                        "stream_to": {"stream_to_id": 203, "kafka": {"topic_name": "test_topic"}},
                    }
                ],
            }
        ]
        self.stream.return_value = [
            {
                "stream_to_id": 203,
                "name": "mq_stream_to_106",
                "report_mode": "kafka",
                "kafka": {
                    "storage_address": [{"ip": "kafka.example.test", "port": 9092}],
                    "sasl_username": "hidden",
                    "sasl_passwd": "hidden",
                    "security_protocol": "SASL_PLAINTEXT",
                    "sasl_mechanisms": "SCRAM-SHA-512",
                    "compression": 0,
                    "req_acks": 1,
                },
            }
        ]
        self.v4_metadata.return_value = {"branches": [{"result_table_id": RT_ID, "kafka_host": "kafka.example.test"}]}
        self.v4_resource.side_effect = lambda **kwargs: RESOURCES[(kwargs["params"]["kind"], kwargs["params"]["name"])]

    def test_reads_verified_v4_references_and_redacts_credentials(self):
        result = AdminResourceRegistry.call(FUNC_NAME, {"bk_data_id": DATA_ID}, app_code="test-app")
        branch = result["v4_branches"][0]
        self.assertEqual(branch["association_status"], "verified")
        self.assertEqual(result["metadata"]["data"]["mq_cluster_id"], 106)
        self.assertEqual(result["kafka_cluster"]["probe_status"], "success")
        self.assertEqual(result["kafka_cluster"]["data"]["cluster_id"], 106)
        self.assertEqual(result["kafka_cluster"]["data"]["cluster_name"], "test-kafka")
        self.assertEqual(result["kafka_cluster"]["data"]["host"], "kafka.example.test")
        self.assertIsNone(result["kafka_cluster"]["data"]["gse_stream_to_id"])
        self.assertEqual(result["gse_route"]["data"]["routes"][0]["stream_to_id"], 203)
        self.assertEqual(result["gse_stream_to"][0]["probe"]["data"]["items"][0]["kafka_addresses"][0]["port"], 9092)
        self.assertEqual(branch["resources"]["kafka_channel"]["data"]["spec"]["streamToId"], 203)
        self.assertIsNone(branch["resources"]["kafka_channel"]["data"]["spec"]["v3ChannelId"])
        self.assertEqual(branch["resources"]["storage"]["data"]["spec"]["host"], "es.example.test")
        self.assertNotIn("hidden", json.dumps(result))
        self.assertIn("CONTROL_PLANE_ONLY", [item["code"] for item in result["warnings"]])
        self.assertEqual(self.v4_resource.call_count, 6)
        for call in self.v4_resource.call_args_list:
            self.assertEqual(call.kwargs["bk_tenant_id"], "system")
            self.assertFalse(call.kwargs["request_cookies"])
            self.assertEqual(call.kwargs["params"]["tenant"], "system")
        self.biz_check.assert_not_called()

    def test_cluster_accepts_legacy_top_level_identity(self):
        self.cluster.return_value[0]["cluster_id"] = 106
        self.cluster.return_value[0]["cluster_name"] = "test-kafka"
        self.cluster.return_value[0]["gse_stream_to_id"] = 203
        result = get_datalink_control_plane_snapshot({"bk_data_id": DATA_ID})
        self.assertEqual(result["kafka_cluster"]["probe_status"], "success")
        self.assertEqual(result["kafka_cluster"]["data"]["gse_stream_to_id"], 203)

    def test_cluster_rejects_conflicting_identity(self):
        self.cluster.return_value[0]["cluster_id"] = 999
        result = get_datalink_control_plane_snapshot({"bk_data_id": DATA_ID})
        self.assertEqual(result["kafka_cluster"]["probe_status"], "failed")
        self.assertEqual(result["v4_branches"][0]["association_status"], "verified")

    def test_read_only_api_routes(self):
        gse = _GseApi()
        self.assertEqual(gse.query_route.method, "POST")
        self.assertTrue(gse.query_route.url.endswith("api/v2/data/query_route"))
        self.assertIn("/api/bk-gse/", gse.query_route.url)
        for enabled in (True, False):
            with self.subTest(multi_tenant=enabled), override_settings(ENABLE_MULTI_TENANT_MODE=enabled):
                meta = _BkDataMetaApi()
                access = _BkDataAccessApi()
                self.assertEqual(meta.get_datalink_metadata.method, "GET")
                self.assertTrue(meta.get_datalink_metadata.url.endswith("v4/meta/datalink/metadata/"))
                self.assertEqual(access.get_datalink_resource.method, "GET")
                self.assertEqual(
                    access.get_datalink_resource.url_keys,
                    ["tenant", "namespace", "kind", "name"] if enabled else ["namespace", "kind", "name"],
                )

    def test_non_global_business_must_belong_to_request_tenant(self):
        self.metadata.return_value["bk_biz_id"] = 42
        self.biz_check.side_effect = BklogPermissionError("outside tenant")
        with self.assertRaises(BklogPermissionError):
            get_datalink_control_plane_snapshot({"bk_data_id": DATA_ID})
        self.biz_check.assert_called_once_with(42)
        self.route.assert_not_called()

    def test_wrong_metadata_data_id_stops_before_other_providers(self):
        self.metadata.return_value["bk_data_id"] = DATA_ID + 1
        with self.assertRaises(ValueError):
            get_datalink_control_plane_snapshot({"bk_data_id": DATA_ID})
        self.route.assert_not_called()

    def test_tenant_mismatch_stops_before_other_providers(self):
        self.metadata.return_value["bk_tenant_id"] = "other"
        with self.assertRaises(BklogPermissionError):
            get_datalink_control_plane_snapshot({"bk_data_id": DATA_ID})
        self.cluster.assert_not_called()
        self.route.assert_not_called()
        self.v4_metadata.assert_not_called()

    def test_metadata_failure_does_not_claim_data_absent(self):
        self.metadata.side_effect = ApiResultError("permission denied", code=1511001)
        result = get_datalink_control_plane_snapshot({"bk_data_id": DATA_ID})
        self.assertEqual(result["metadata"]["probe_status"], "failed")
        self.assertIsNone(result["metadata"]["exists"])
        self.assertEqual(result["gse_route"]["probe_status"], "skipped")
        self.route.assert_not_called()

    def test_v4_reference_mismatch_is_explicit_and_does_not_follow_storage(self):
        resources = dict(RESOURCES)
        resources[("dataids", DATAID_NAME)] = resource(
            "DataId",
            DATAID_NAME,
            {
                "predefined": {
                    "dataId": 999,
                    "channel": ref("KafkaChannel", "test-kafka"),
                }
            },
        )
        self.v4_resource.side_effect = lambda **kwargs: resources[(kwargs["params"]["kind"], kwargs["params"]["name"])]
        result = get_datalink_control_plane_snapshot({"bk_data_id": DATA_ID})
        branch = result["v4_branches"][0]
        self.assertEqual(branch["association_status"], "mismatch")
        self.assertNotIn("kafka_channel", branch["resources"])
        self.assertNotIn("storage", branch["resources"])

    def test_v4_permission_failure_is_unknown_and_gse_still_available(self):
        self.v4_resource.side_effect = ApiResultError("permission denied", code=1511001)
        result = get_datalink_control_plane_snapshot({"bk_data_id": DATA_ID})
        branch = result["v4_branches"][0]
        self.assertEqual(branch["association_status"], "unknown")
        self.assertIsNone(branch["resources"]["databus"]["exists"])
        self.assertEqual(result["gse_route"]["probe_status"], "success")

    def test_explicit_v4_not_found_is_distinct_from_permission_failure(self):
        self.v4_resource.side_effect = ApiResultError("resource does not exist", code=1558025)
        result = get_datalink_control_plane_snapshot({"bk_data_id": DATA_ID})
        databus = result["v4_branches"][0]["resources"]["databus"]
        self.assertFalse(databus["exists"])
        self.assertEqual(databus["error"]["code"], "RESOURCE_NOT_FOUND")

    def test_cross_tenant_reference_is_not_followed(self):
        resources = dict(RESOURCES)
        bus = resource(
            "Databus",
            RT_NAME,
            {
                "sources": [{**ref("DataId", DATAID_NAME), "tenant": "other"}],
                "sinks": [ref("ElasticSearchBinding", RT_NAME)],
            },
        )
        resources[("databuses", RT_NAME)] = bus
        self.v4_resource.side_effect = lambda **kwargs: resources[(kwargs["params"]["kind"], kwargs["params"]["name"])]
        result = get_datalink_control_plane_snapshot({"bk_data_id": DATA_ID})
        source = result["v4_branches"][0]["resources"]["data_id"]
        self.assertEqual(source["probe_status"], "skipped")
        self.assertEqual(source["error"]["code"], "CROSS_TENANT_REFERENCE")
        self.assertEqual(result["v4_branches"][0]["association_status"], "unknown")

    def test_gse_flat_stream_response_and_resource_phase(self):
        resources = dict(RESOURCES)
        resources[("databuses", RT_NAME)] = resource(
            "Databus", RT_NAME, RESOURCES[("databuses", RT_NAME)]["spec"], phase="Failed"
        )
        self.v4_resource.side_effect = lambda **kwargs: resources[(kwargs["params"]["kind"], kwargs["params"]["name"])]
        result = get_datalink_control_plane_snapshot({"bk_data_id": DATA_ID})
        self.assertEqual(result["gse_stream_to"][0]["probe"]["data"]["items"][0]["name"], "mq_stream_to_106")
        self.assertIn("V4_RESOURCE_NOT_OK", [item["code"] for item in result["warnings"]])

    def test_registry_schema_blocks_identity_and_extra_params(self):
        self.assertTrue(FUNCTIONS[FUNC_NAME]["validate_params"])
        self.assertEqual(FUNCTIONS[FUNC_NAME]["safety_level"], "inspect")
        for params in (
            {"bk_data_id": 0},
            {"bk_data_id": DATA_ID, "bk_tenant_id": "other"},
            {"bk_data_id": DATA_ID, "unexpected": True},
            {"bk_data_id": True},
        ):
            with self.subTest(params=params), self.assertRaises(ValidationError):
                AdminResourceRegistry.call(FUNC_NAME, params, app_code="test-app")
        self.metadata.assert_not_called()
