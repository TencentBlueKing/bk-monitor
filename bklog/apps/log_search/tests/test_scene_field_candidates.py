"""
Unit tests for IaaS 字段联想候选值接口 (list_field_candidates).

Covers:
- SceneFieldCandidatesSerializer 校验（容器/主机分支必填项、分页上限）
- SceneFieldCandidatesHandler._build_addition（目标维度自排除 / eq|include 映射 / query_string 包含下推）
- SceneFieldCandidatesHandler.list_candidates（去重有序列表的分页切片）
- get_field_candidates 分流（container 透传监控 / host 走 ts/reference 聚合）
- ViewSet 端点 list_field_candidates
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.log_search.views.scene_search_views import (
    SceneFieldCandidatesSerializer,
    SceneSearchViewSet,
)

SPACE_UID = "bkcc__2"
TABLE_ID_CONDITIONS = [
    [
        {"field_name": "scene", "value": ["host"], "op": "eq"},
    ]
]


def _get_viewset(action_name, request):
    from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
    from rest_framework.request import Request

    vs = SceneSearchViewSet(format_kwarg=None)
    if not isinstance(request, Request):
        request = Request(request, parsers=[JSONParser(), FormParser(), MultiPartParser()])
    vs.request = request
    vs.kwargs = {}
    vs.action = action_name
    return vs


# =========================================================================
# 1. Serializer validation
# =========================================================================


class TestSceneFieldCandidatesSerializer(TestCase):
    def test_container_valid(self):
        data = {
            "space_uid": SPACE_UID,
            "bk_biz_id": 2,
            "scene": "k8s",
            "resource_type": "namespace",
            "bcs_cluster_ids": ["BCS-K8S-00000"],
        }
        s = SceneFieldCandidatesSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_container_missing_cluster_ids_fails(self):
        data = {
            "space_uid": SPACE_UID,
            "bk_biz_id": 2,
            "scene": "k8s",
            "resource_type": "namespace",
        }
        s = SceneFieldCandidatesSerializer(data=data)
        self.assertFalse(s.is_valid())

    def test_host_valid(self):
        data = {
            "space_uid": SPACE_UID,
            "bk_biz_id": 2,
            "scene": "host",
            "resource_type": "serverIp",
            "table_id_conditions": TABLE_ID_CONDITIONS,
            "start_time": "2026-03-25 00:00:00",
            "end_time": "2026-03-25 01:00:00",
        }
        s = SceneFieldCandidatesSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_host_missing_table_id_conditions_fails(self):
        data = {
            "space_uid": SPACE_UID,
            "bk_biz_id": 2,
            "scene": "host",
            "resource_type": "serverIp",
            "start_time": "2026-03-25 00:00:00",
            "end_time": "2026-03-25 01:00:00",
        }
        s = SceneFieldCandidatesSerializer(data=data)
        self.assertFalse(s.is_valid())

    def test_host_missing_time_fails(self):
        data = {
            "space_uid": SPACE_UID,
            "bk_biz_id": 2,
            "scene": "host",
            "resource_type": "serverIp",
            "table_id_conditions": TABLE_ID_CONDITIONS,
        }
        s = SceneFieldCandidatesSerializer(data=data)
        self.assertFalse(s.is_valid())

    def test_page_size_capped(self):
        data = {
            "space_uid": SPACE_UID,
            "bk_biz_id": 2,
            "scene": "k8s",
            "resource_type": "namespace",
            "bcs_cluster_ids": ["BCS-K8S-00000"],
            "page_size": 99999,
        }
        s = SceneFieldCandidatesSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["page_size"], 1000)

    def test_defaults(self):
        data = {
            "space_uid": SPACE_UID,
            "bk_biz_id": 2,
            "scene": "k8s",
            "resource_type": "namespace",
            "bcs_cluster_ids": ["BCS-K8S-00000"],
        }
        s = SceneFieldCandidatesSerializer(data=data)
        s.is_valid(raise_exception=True)
        self.assertEqual(s.validated_data["page"], 1)
        self.assertEqual(s.validated_data["page_size"], 500)
        self.assertEqual(s.validated_data["conditions"], [])


# =========================================================================
# 2. SceneFieldCandidatesHandler._build_addition
# =========================================================================


class TestBuildAddition(TestCase):
    def _handler(self, resource_type, query_string=""):
        from apps.log_unifyquery.handler.scene_field_candidates import (
            SceneFieldCandidatesHandler,
        )

        h = SceneFieldCandidatesHandler.__new__(SceneFieldCandidatesHandler)
        h.resource_type = resource_type
        h.candidate_query_string = query_string
        return h

    def test_self_dimension_excluded(self):
        h = self._handler("serverIp")
        addition = h._build_addition(
            [
                {"key": "serverIp", "method": "eq", "value": ["10.0.0.1"]},
                {"key": "path", "method": "eq", "value": ["/var/log/a.log"]},
            ]
        )
        fields = [a["field"] for a in addition]
        self.assertNotIn("serverIp", fields)
        self.assertIn("path", fields)

    def test_eq_and_include_method_mapping(self):
        h = self._handler("serverIp")
        addition = h._build_addition(
            [
                {"key": "path", "method": "eq", "value": ["/var/log/a.log"]},
                {"key": "module", "method": "include", "value": ["api"]},
            ]
        )
        by_field = {a["field"]: a for a in addition}
        self.assertEqual(by_field["path"]["operator"], "=")
        self.assertEqual(by_field["module"]["operator"], "contains")

    def test_query_string_pushed_down_as_contains(self):
        h = self._handler("serverIp", query_string="10.0")
        addition = h._build_addition([])
        self.assertEqual(len(addition), 1)
        self.assertEqual(addition[0]["field"], "serverIp")
        self.assertEqual(addition[0]["operator"], "contains")
        self.assertEqual(addition[0]["value"], ["10.0"])

    def test_empty_query_string_no_push_down(self):
        h = self._handler("serverIp", query_string="")
        addition = h._build_addition([])
        self.assertEqual(addition, [])

    def test_scalar_value_normalized_to_list(self):
        h = self._handler("serverIp")
        addition = h._build_addition([{"key": "path", "method": "eq", "value": "/var/log/a.log"}])
        self.assertEqual(addition[0]["value"], ["/var/log/a.log"])


# =========================================================================
# 3. SceneFieldCandidatesHandler.list_candidates pagination
# =========================================================================


class TestListCandidatesPagination(TestCase):
    def _handler(self, items, page, page_size, resource_type="serverIp"):
        from apps.log_unifyquery.handler.scene_field_candidates import (
            SceneFieldCandidatesHandler,
        )

        h = SceneFieldCandidatesHandler.__new__(SceneFieldCandidatesHandler)
        h.resource_type = resource_type
        h.page = page
        h.page_size = page_size
        h.terms = MagicMock(return_value={"aggs_items": {resource_type: items}})
        return h

    def test_first_page(self):
        h = self._handler(["a", "b", "c", "d", "e"], page=1, page_size=2)
        result = h.list_candidates()
        self.assertEqual(result["count"], 5)
        self.assertEqual(result["items"], ["a", "b"])

    def test_second_page(self):
        h = self._handler(["a", "b", "c", "d", "e"], page=2, page_size=2)
        result = h.list_candidates()
        self.assertEqual(result["count"], 5)
        self.assertEqual(result["items"], ["c", "d"])

    def test_out_of_range_page_returns_empty(self):
        h = self._handler(["a", "b"], page=5, page_size=2)
        result = h.list_candidates()
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["items"], [])

    def test_empty_aggs(self):
        from apps.log_unifyquery.handler.scene_field_candidates import (
            SceneFieldCandidatesHandler,
        )

        h = SceneFieldCandidatesHandler.__new__(SceneFieldCandidatesHandler)
        h.resource_type = "serverIp"
        h.page = 1
        h.page_size = 10
        h.terms = MagicMock(return_value={"aggs_items": {}})
        result = h.list_candidates()
        self.assertEqual(result, {"count": 0, "items": []})


# =========================================================================
# 4. SceneFieldCandidatesHandler full init (params assembly)
# =========================================================================


@override_settings(PRE_SEARCH_SECONDS=60, TIME_ZONE="UTC")
class TestSceneFieldCandidatesHandlerInit(TestCase):
    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    def test_init_assembles_params(self, mock_local, mock_user, mock_ext):
        from apps.log_unifyquery.handler.scene_field_candidates import (
            SceneFieldCandidatesHandler,
        )

        params = {
            "space_uid": SPACE_UID,
            "bk_biz_id": 2,
            "scene": "host",
            "resource_type": "serverIp",
            "table_id_conditions": TABLE_ID_CONDITIONS,
            "conditions": [
                {"key": "serverIp", "method": "eq", "value": ["10.0.0.1"]},
                {"key": "path", "method": "eq", "value": ["/var/log/a.log"]},
            ],
            "query_string": "10",
            "page": 1,
            "page_size": 10,
            "start_time": "2026-03-25 00:00:00",
            "end_time": "2026-03-25 01:00:00",
        }
        h = SceneFieldCandidatesHandler(params)

        self.assertEqual(h.resource_type, "serverIp")
        self.assertEqual(h.agg_fields, ["serverIp"])
        # agg_field 写入 search_params 供 base_dict field_name 使用
        self.assertEqual(h.search_params["agg_field"], "serverIp")
        # size = max(page*page_size, page_size) = 10
        self.assertEqual(h.search_params["size"], 10)
        # addition：自排除 serverIp、保留 path、追加 query_string contains
        addition_fields = [a["field"] for a in h.search_params["addition"]]
        self.assertNotIn("serverIp", [a["field"] for a in h.search_params["addition"] if a["operator"] == "="])
        self.assertIn("path", addition_fields)
        contains_items = [a for a in h.search_params["addition"] if a["operator"] == "contains"]
        self.assertTrue(any(a["field"] == "serverIp" and a["value"] == ["10"] for a in contains_items))


# =========================================================================
# 5. get_field_candidates dispatch
# =========================================================================


class TestGetFieldCandidatesDispatch(TestCase):
    def test_container_branch_maps_k8s_fields_for_monitor(self):
        with patch("apps.api.MonitorApi") as mock_api:
            mock_api.list_resource_candidates.return_value = {"count": 2, "items": ["ns-a", "ns-b"]}

            from apps.log_search.handlers.scene_search import get_field_candidates

            result = get_field_candidates(
                {
                    "scene": "k8s",
                    "bk_biz_id": 2,
                    "bcs_cluster_ids": ["BCS-K8S-00000"],
                    "resource_type": "__ext.io_kubernetes_workload_name",
                    "conditions": [
                        {"key": "__ext.io_kubernetes_pod_namespace", "method": "eq", "value": ["ns-a"]},
                        {"key": "__ext.container_name", "method": "include", "value": ["api"]},
                    ],
                    "query_string": "ns",
                    "page": 1,
                    "page_size": 500,
                }
            )

        self.assertEqual(result, {"count": 2, "items": ["ns-a", "ns-b"]})
        mock_api.list_resource_candidates.assert_called_once()
        call_params = mock_api.list_resource_candidates.call_args[0][0]
        self.assertEqual(call_params["bk_biz_id"], 2)
        self.assertEqual(call_params["resource_type"], "workload_name")
        self.assertEqual(
            call_params["conditions"],
            [
                {"key": "namespace", "method": "eq", "value": ["ns-a"]},
                {"key": "container_name", "method": "include", "value": ["api"]},
            ],
        )
        self.assertEqual(call_params["bcs_cluster_ids"], ["BCS-K8S-00000"])

    def test_container_branch_none_result_defaults_empty(self):
        with patch("apps.api.MonitorApi") as mock_api:
            mock_api.list_resource_candidates.return_value = None

            from apps.log_search.handlers.scene_search import get_field_candidates

            result = get_field_candidates(
                {
                    "scene": "k8s",
                    "bk_biz_id": 2,
                    "bcs_cluster_ids": ["BCS-K8S-00000"],
                    "resource_type": "namespace",
                }
            )

        self.assertEqual(result, {"count": 0, "items": []})

    def test_host_branch_uses_handler(self):
        with patch(
            "apps.log_unifyquery.handler.scene_field_candidates.SceneFieldCandidatesHandler"
        ) as mock_handler_cls:
            mock_handler = MagicMock()
            mock_handler.list_candidates.return_value = {"count": 1, "items": ["10.0.0.1"]}
            mock_handler_cls.return_value = mock_handler

            from apps.log_search.handlers.scene_search import get_field_candidates

            data = {"scene": "host", "resource_type": "serverIp"}
            result = get_field_candidates(data)

        self.assertEqual(result, {"count": 1, "items": ["10.0.0.1"]})
        mock_handler_cls.assert_called_once_with(data)


# =========================================================================
# 6. ViewSet endpoint
# =========================================================================


@override_settings(PRE_SEARCH_SECONDS=60, TIME_ZONE="UTC")
class TestSceneSearchViewSetListFieldCandidates(TestCase):
    def test_container_endpoint(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/api/v1/search/scene/list_field_candidates/",
            data={
                "space_uid": SPACE_UID,
                "bk_biz_id": 2,
                "scene": "k8s",
                "resource_type": "namespace",
                "bcs_cluster_ids": ["BCS-K8S-00000"],
                "query_string": "ns",
            },
            format="json",
        )
        with patch(
            "apps.log_search.views.scene_search_views.get_field_candidates",
            return_value={"count": 1, "items": ["ns-a"]},
        ) as mock_dispatch:
            vs = _get_viewset("list_field_candidates", request)
            response = vs.list_field_candidates(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"count": 1, "items": ["ns-a"]})
        mock_dispatch.assert_called_once()

    def test_host_endpoint_validates_and_dispatches(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/api/v1/search/scene/list_field_candidates/",
            data={
                "space_uid": SPACE_UID,
                "bk_biz_id": 2,
                "scene": "host",
                "resource_type": "serverIp",
                "table_id_conditions": TABLE_ID_CONDITIONS,
                "start_time": "2026-03-25 00:00:00",
                "end_time": "2026-03-25 01:00:00",
            },
            format="json",
        )
        with patch(
            "apps.log_search.views.scene_search_views.get_field_candidates",
            return_value={"count": 2, "items": ["10.0.0.1", "10.0.0.2"]},
        ) as mock_dispatch:
            vs = _get_viewset("list_field_candidates", request)
            response = vs.list_field_candidates(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        # table_id_conditions 经 AllConditionsBuilder 透传
        dispatched = mock_dispatch.call_args[0][0]
        self.assertEqual(dispatched["table_id_conditions"], TABLE_ID_CONDITIONS)

    def test_host_endpoint_missing_time_fails(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/api/v1/search/scene/list_field_candidates/",
            data={
                "space_uid": SPACE_UID,
                "bk_biz_id": 2,
                "scene": "host",
                "resource_type": "serverIp",
                "table_id_conditions": TABLE_ID_CONDITIONS,
            },
            format="json",
        )
        vs = _get_viewset("list_field_candidates", request)
        with self.assertRaises(Exception):
            vs.list_field_candidates(request)
