"""
Unit tests for scene_search endpoints (SceneSearchViewSet).
Covers: scenes / search / fields / date_histogram / agg_field / total
"""

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.log_search.views.scene_search_views import (
    AllConditionsBuilder,
    ConditionFieldSerializer,
    SceneAggFieldSerializer,
    SceneDateHistogramSerializer,
    SceneFieldsSerializer,
    SceneSearchSerializer,
    SceneSearchViewSet,
    SceneTotalSerializer,
    _SceneRouteMixin,
)


# =========================================================================
# Test fixtures
# =========================================================================

SPACE_UID = "bkcc__2"
TABLE_ID_CONDITIONS = [
    [
        {"field_name": "scene", "value": ["k8s"], "op": "eq"},
        {"field_name": "cluster_id", "value": ["BCS-K8S-00000"], "op": "eq"},
    ]
]

BASE_POST_BODY = {
    "space_uid": SPACE_UID,
    "table_id_conditions": TABLE_ID_CONDITIONS,
}

SEARCH_POST_BODY = {
    **BASE_POST_BODY,
    "keyword": "error",
    "start_time": "2026-03-25 00:00:00",
    "end_time": "2026-03-25 01:00:00",
}


def _make_post_request(data, factory=None):
    factory = factory or APIRequestFactory()
    request = factory.post(
        "/api/v1/search/scene/search/",
        data=data,
        format="json",
    )
    return request


# =========================================================================
# 1. AllConditionsBuilder
# =========================================================================

class TestAllConditionsBuilder(TestCase):

    def test_valid_conditions(self):
        conds = [[{"field_name": "scene", "value": ["k8s"], "op": "eq"}]]
        result = AllConditionsBuilder.from_raw(conds)
        self.assertEqual(result, conds)

    def test_default_op_eq(self):
        conds = [[{"field_name": "scene", "value": ["k8s"]}]]
        result = AllConditionsBuilder.from_raw(conds)
        self.assertEqual(result, conds)

    def test_invalid_op_raises(self):
        conds = [[{"field_name": "scene", "value": ["k8s"], "op": "like"}]]
        with self.assertRaises(ValueError):
            AllConditionsBuilder.from_raw(conds)

    def test_missing_field_name_raises(self):
        conds = [[{"value": ["k8s"], "op": "eq"}]]
        with self.assertRaises(ValueError):
            AllConditionsBuilder.from_raw(conds)

    def test_missing_value_raises(self):
        conds = [[{"field_name": "scene", "op": "eq"}]]
        with self.assertRaises(ValueError):
            AllConditionsBuilder.from_raw(conds)

    def test_multi_or_groups(self):
        conds = [
            [{"field_name": "scene", "value": ["k8s"], "op": "eq"}],
            [{"field_name": "scene", "value": ["host"], "op": "eq"}],
        ]
        result = AllConditionsBuilder.from_raw(conds)
        self.assertEqual(len(result), 2)


# =========================================================================
# 2. Serializer validation
# =========================================================================

class TestConditionFieldSerializer(TestCase):

    def test_valid(self):
        s = ConditionFieldSerializer(data={"field_name": "scene", "value": ["k8s"], "op": "eq"})
        self.assertTrue(s.is_valid(), s.errors)

    def test_default_op(self):
        s = ConditionFieldSerializer(data={"field_name": "scene", "value": ["k8s"]})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["op"], "eq")

    def test_invalid_op(self):
        s = ConditionFieldSerializer(data={"field_name": "scene", "value": ["k8s"], "op": "like"})
        self.assertFalse(s.is_valid())

    def test_missing_field_name(self):
        s = ConditionFieldSerializer(data={"value": ["k8s"]})
        self.assertFalse(s.is_valid())


class TestSceneRouteMixin(TestCase):

    def test_valid(self):
        s = _SceneRouteMixin(data=BASE_POST_BODY)
        self.assertTrue(s.is_valid(), s.errors)

    def test_empty_conditions_fails(self):
        s = _SceneRouteMixin(data={"space_uid": SPACE_UID, "table_id_conditions": []})
        self.assertFalse(s.is_valid())


class TestSceneSearchSerializer(TestCase):

    def test_valid_minimal(self):
        s = SceneSearchSerializer(data=SEARCH_POST_BODY)
        self.assertTrue(s.is_valid(), s.errors)

    def test_defaults(self):
        data = {**SEARCH_POST_BODY}
        s = SceneSearchSerializer(data=data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        self.assertEqual(d["begin"], 0)
        self.assertEqual(d["size"], 50)
        self.assertEqual(d["keyword"], "error")

    def test_missing_start_time_fails(self):
        data = {**BASE_POST_BODY, "end_time": "2026-03-25 01:00:00"}
        s = SceneSearchSerializer(data=data)
        self.assertFalse(s.is_valid())


class TestSceneFieldsSerializer(TestCase):

    def test_valid_minimal(self):
        s = SceneFieldsSerializer(data=BASE_POST_BODY)
        self.assertTrue(s.is_valid(), s.errors)

    def test_with_time(self):
        data = {**BASE_POST_BODY, "start_time": "2026-03-25 00:00:00", "end_time": "2026-03-25 01:00:00"}
        s = SceneFieldsSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)


class TestSceneDateHistogramSerializer(TestCase):

    def test_valid(self):
        data = {**SEARCH_POST_BODY, "interval": "5m"}
        s = SceneDateHistogramSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_defaults(self):
        s = SceneDateHistogramSerializer(data=SEARCH_POST_BODY)
        s.is_valid(raise_exception=True)
        self.assertEqual(s.validated_data["interval"], "auto")


class TestSceneAggFieldSerializer(TestCase):

    def test_valid(self):
        data = {**SEARCH_POST_BODY, "agg_field": "status"}
        s = SceneAggFieldSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_missing_agg_field_fails(self):
        s = SceneAggFieldSerializer(data=SEARCH_POST_BODY)
        self.assertFalse(s.is_valid())


class TestSceneTotalSerializer(TestCase):

    def test_valid(self):
        s = SceneTotalSerializer(data=SEARCH_POST_BODY)
        self.assertTrue(s.is_valid(), s.errors)


# =========================================================================
# 3. ViewSet endpoint tests
# =========================================================================

def _get_viewset(action_name, request, initkwargs=None):
    """Instantiate viewset, wrap request with DRF Request, and route action."""
    from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
    from rest_framework.request import Request
    vs = SceneSearchViewSet(**{**(initkwargs or {}), "format_kwarg": None})
    if not isinstance(request, Request):
        request = Request(request, parsers=[JSONParser(), FormParser(), MultiPartParser()])
    vs.request = request
    vs.kwargs = {}
    vs.action = action_name
    return vs


@override_settings(
    PRE_SEARCH_SECONDS=60,
    TIME_ZONE="UTC",
    FEATURE_TOGGLE={"feature_id": True},
)
class TestSceneSearchViewSetScenes(TestCase):
    """GET /search/scene/scenes/"""

    def test_scenes_via_view(self):
        factory = APIRequestFactory()
        request = factory.get("/api/v1/search/scene/scenes/")

        with patch(
            "apps.log_search.constants.SceneLabelEnum.get_choices",
            return_value=(("k8s", "容器场景"), ("host", "主机场景")),
        ), patch(
            "apps.log_databus.constants.SCENE_SEARCH_DIMENSIONS",
            {"k8s": [{"key": "cluster_id"}], "host": []},
        ):
            vs = _get_viewset("scenes", request)
            response = vs.scenes(request)

        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["id"], "k8s")
        self.assertEqual(data[0]["name"], "容器场景")
        self.assertEqual(data[0]["dimensions"], [{"key": "cluster_id"}])
        self.assertEqual(data[1]["id"], "host")
        self.assertEqual(data[1]["dimensions"], [])


@override_settings(PRE_SEARCH_SECONDS=60, TIME_ZONE="UTC")
class TestSceneSearchViewSetSearch(TestCase):
    """POST /search/scene/search/"""

    @patch("apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler.search")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    def test_search_success(self, mock_local, mock_user, mock_ext_user, mock_search):
        mock_search.return_value = {
            "list": [{"log": "test error msg"}],
            "origin_log_list": [],
            "total": 1,
            "took": 10,
        }

        factory = APIRequestFactory()
        request = _make_post_request(SEARCH_POST_BODY, factory)
        vs = _get_viewset("search", request)
        response = vs.search(request)

        self.assertEqual(response.status_code, 200)
        mock_search.assert_called_once()

    def test_search_missing_space_uid_fails(self):
        data = {
            "table_id_conditions": TABLE_ID_CONDITIONS,
            "keyword": "error",
            "start_time": "2026-03-25 00:00:00",
            "end_time": "2026-03-25 01:00:00",
        }
        factory = APIRequestFactory()
        request = _make_post_request(data, factory)
        vs = _get_viewset("search", request)

        with self.assertRaises(Exception):
            vs.search(request)


@override_settings(PRE_SEARCH_SECONDS=60, TIME_ZONE="UTC")
class TestSceneSearchViewSetFields(TestCase):
    """POST /search/scene/fields/"""

    @patch("apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler.fields")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    def test_fields_success(self, mock_local, mock_user, mock_ext_user, mock_fields):
        mock_fields.return_value = {
            "fields": [{"field_name": "log", "field_type": "text"}],
            "display_fields": ["dtEventTimeStamp", "log"],
            "sort_list": [["dtEventTimeStamp", "desc"]],
        }

        factory = APIRequestFactory()
        request = _make_post_request(BASE_POST_BODY, factory)
        vs = _get_viewset("fields", request)
        response = vs.fields(request)

        self.assertEqual(response.status_code, 200)
        mock_fields.assert_called_once_with(scope="default")

    @patch("apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler.fields")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    def test_fields_with_empty_time(self, mock_local, mock_user, mock_ext_user, mock_fields):
        """SceneFieldsSerializer allows empty start_time/end_time — handler should handle it."""
        mock_fields.return_value = {"fields": [], "display_fields": [], "sort_list": []}

        data = {**BASE_POST_BODY, "start_time": "", "end_time": ""}
        factory = APIRequestFactory()
        request = _make_post_request(data, factory)
        vs = _get_viewset("fields", request)
        response = vs.fields(request)

        self.assertEqual(response.status_code, 200)


@override_settings(PRE_SEARCH_SECONDS=60, TIME_ZONE="UTC")
class TestSceneSearchViewSetDateHistogram(TestCase):
    """POST /search/scene/date_histogram/"""

    @patch("apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler.date_histogram")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    def test_date_histogram_success(self, mock_local, mock_user, mock_ext_user, mock_dh):
        mock_dh.return_value = {"series": [{"values": [1, 2, 3]}]}

        factory = APIRequestFactory()
        request = _make_post_request(SEARCH_POST_BODY, factory)
        vs = _get_viewset("date_histogram", request)
        response = vs.date_histogram(request)

        self.assertEqual(response.status_code, 200)
        mock_dh.assert_called_once_with(interval="auto")

    @patch("apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler.date_histogram")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    def test_date_histogram_with_interval(self, mock_local, mock_user, mock_ext_user, mock_dh):
        mock_dh.return_value = {"series": []}

        data = {**SEARCH_POST_BODY, "interval": "5m"}
        factory = APIRequestFactory()
        request = _make_post_request(data, factory)
        vs = _get_viewset("date_histogram", request)
        response = vs.date_histogram(request)

        mock_dh.assert_called_once_with(interval="5m")


@override_settings(PRE_SEARCH_SECONDS=60, TIME_ZONE="UTC")
class TestSceneSearchViewSetAggField(TestCase):
    """POST /search/scene/agg_field/"""

    @patch("apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler.agg_field")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    def test_agg_field_success(self, mock_local, mock_user, mock_ext_user, mock_agg):
        mock_agg.return_value = {"series": [{"group_values": ["200"], "values": [[100]]}]}

        data = {**SEARCH_POST_BODY, "agg_field": "status"}
        factory = APIRequestFactory()
        request = _make_post_request(data, factory)
        vs = _get_viewset("agg_field", request)
        response = vs.agg_field(request)

        self.assertEqual(response.status_code, 200)
        mock_agg.assert_called_once_with(agg_field="status")


@override_settings(PRE_SEARCH_SECONDS=60, TIME_ZONE="UTC")
class TestSceneSearchViewSetTotal(TestCase):
    """POST /search/scene/total/"""

    @patch("apps.log_unifyquery.handler.scene_search.SceneUnifyQueryHandler.total")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    def test_total_success(self, mock_local, mock_user, mock_ext_user, mock_total):
        mock_total.return_value = {"total": 42}

        factory = APIRequestFactory()
        request = _make_post_request(SEARCH_POST_BODY, factory)
        vs = _get_viewset("total", request)
        response = vs.total(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"total": 42})


# =========================================================================
# 4. SceneUnifyQueryHandler unit tests
# =========================================================================

@override_settings(PRE_SEARCH_SECONDS=60, TIME_ZONE="UTC")
class TestSceneUnifyQueryHandler(TestCase):
    """Test handler initialization and method assembly."""

    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    def test_init_basic(self, mock_local, mock_user, mock_ext_user):
        from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler

        params = {
            **SEARCH_POST_BODY,
            "begin": 0,
            "size": 50,
        }
        handler = SceneUnifyQueryHandler(params)

        self.assertEqual(handler.space_uid, SPACE_UID)
        self.assertEqual(handler.table_id_conditions, TABLE_ID_CONDITIONS)
        self.assertIn("query_list", handler.base_dict)
        self.assertEqual(handler.base_dict["space_uid"], SPACE_UID)
        self.assertEqual(handler.base_dict["query_list"][0]["table_id_conditions"], TABLE_ID_CONDITIONS)

    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    def test_init_empty_time(self, mock_local, mock_user, mock_ext_user):
        """Empty start_time/end_time should not crash deal_time_format."""
        from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler

        params = {
            **BASE_POST_BODY,
            "start_time": "",
            "end_time": "",
        }
        handler = SceneUnifyQueryHandler(params)
        self.assertEqual(handler.start_time, "")
        self.assertEqual(handler.end_time, "")

    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    def test_sort_order(self, mock_local, mock_user, mock_ext_user):
        from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler

        params = {
            **SEARCH_POST_BODY,
            "sort_list": [["dtEventTimeStamp", "desc"], ["log", "asc"]],
        }
        handler = SceneUnifyQueryHandler(params)
        self.assertEqual(handler.order_by, ["-dtEventTimeStamp", "log"])

    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    def test_additions_transform(self, mock_local, mock_user, mock_ext_user):
        from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler

        params = {
            **SEARCH_POST_BODY,
            "addition": [
                {"key": "status", "method": "is", "value": "200"},
            ],
        }
        handler = SceneUnifyQueryHandler(params)
        conditions = handler.base_dict["query_list"][0]["conditions"]
        self.assertIn("field_list", conditions)
        self.assertTrue(len(conditions["field_list"]) > 0)

    @patch("apps.log_unifyquery.handler.scene_search.UnifyQueryApi.query_field_map")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    def test_fields_method(self, mock_local, mock_user, mock_ext_user, mock_api):
        from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler

        mock_api.return_value = {
            "fields": {
                "log": {"type": "text", "description": "日志内容"},
                "status": {"type": "keyword", "description": "状态码"},
            }
        }

        params = {**BASE_POST_BODY, "start_time": "", "end_time": ""}
        handler = SceneUnifyQueryHandler(params)
        result = handler.fields()

        self.assertEqual(len(result["fields"]), 2)
        log_field = next(f for f in result["fields"] if f["field_name"] == "log")
        self.assertTrue(log_field["is_analyzed"])
        self.assertFalse(log_field["es_doc_values"])

        status_field = next(f for f in result["fields"] if f["field_name"] == "status")
        self.assertFalse(status_field["is_analyzed"])
        self.assertTrue(status_field["es_doc_values"])

    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    def test_deal_query_result(self, mock_local, mock_user, mock_ext_user):
        from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler

        params = {**SEARCH_POST_BODY, "begin": 0, "size": 10}
        handler = SceneUnifyQueryHandler(params)

        raw_result = {
            "list": [
                {"log": "test error", "__index": "my_index", "__doc_id": "doc1"},
            ],
            "total": 1,
            "took": 5,
        }
        result = handler._deal_query_result(raw_result)
        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["list"]), 1)
        self.assertEqual(result["list"][0]["index"], "my_index")
        self.assertEqual(result["list"][0]["__id__"], "doc1")
        self.assertNotIn("__index", result["list"][0])

    @patch("apps.log_unifyquery.handler.scene_search.UnifyQueryApi.query_ts_raw")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_external_username", return_value="")
    @patch("apps.log_unifyquery.handler.scene_search.get_request_username", return_value="admin")
    @patch("apps.log_unifyquery.handler.scene_search.get_local_param", return_value="UTC")
    def test_total_method(self, mock_local, mock_user, mock_ext_user, mock_api):
        from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler

        mock_api.return_value = {"list": [], "total": 999, "took": 2}

        params = {**SEARCH_POST_BODY, "begin": 0, "size": 50}
        handler = SceneUnifyQueryHandler(params)
        result = handler.total()

        self.assertEqual(result, {"total": 999})
        call_args = mock_api.call_args[0][0]
        self.assertEqual(call_args["limit"], 1)
        self.assertEqual(call_args["highlight"]["enable"], False)
