from http import HTTPStatus
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from apps.iam.backends.v4.config import DEFAULT_MODEL_BASE_PATH, V4Options
from apps.iam.backends.v4.exceptions import V4ClientError, V4ResponseError
from apps.iam.backends.v4.model_client import V4ModelClient


def build_response(status_code, payload=None):
    response = Mock(status_code=status_code, content=b"" if payload is None else b"body")
    response.json.return_value = payload
    return response


def ok(payload):
    return build_response(HTTPStatus.OK, payload)


def created(payload):
    return build_response(HTTPStatus.CREATED, payload)


def no_content():
    return build_response(HTTPStatus.NO_CONTENT)


class V4ModelClientTest(SimpleTestCase):
    maxDiff = None

    def setUp(self):
        self.client = V4ModelClient(
            V4Options(
                app_code="bk_log_search",
                app_secret="secret",
                gateway_url="https://bkiam.example/prod/",
                system_id="bklog_test",
                timeout_seconds=1,
                batch_chunk_size=100,
                batch_max_workers=4,
                auth_path="api/v1/open/rbac/authorization/systems/{system_id}/auth/",
                auth_by_resources_path="api/v1/open/rbac/authorization/systems/{system_id}/auth-by-resources/",
                authorized_resources_path=(
                    "api/v1/open/rbac/authorization/systems/{system_id}/relation/authorized-resources/"
                ),
                apply_url_path="api/v1/open/application/permission-apply-urls/",
            ),
            username="admin",
            bk_tenant_id="system",
        )

    @staticmethod
    def called_paths(request_mock):
        return [call.kwargs["url"] for call in request_mock.call_args_list]

    # ------------------------------------------------------------------ system

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_retrieve_system_returns_payload(self, request_mock):
        request_mock.return_value = ok({"data": {"id": "bklog_test", "name": "日志平台"}})

        self.assertEqual(self.client.retrieve_system(), {"id": "bklog_test", "name": "日志平台"})
        self.assertEqual(
            self.called_paths(request_mock),
            [f"https://bkiam.example/prod/{DEFAULT_MODEL_BASE_PATH}bklog_test/"],
        )

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_retrieve_system_maps_not_found_to_none(self, request_mock):
        request_mock.return_value = build_response(HTTPStatus.NOT_FOUND, {"error": {"message": "not found"}})

        self.assertIsNone(self.client.retrieve_system())

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_retrieve_system_rejects_non_object_payload(self, request_mock):
        request_mock.return_value = ok({"data": ["bklog_test"]})

        with self.assertRaisesRegex(V4ResponseError, "retrieve_system response must be an object"):
            self.client.retrieve_system()

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_retrieve_system_propagates_other_client_errors(self, request_mock):
        request_mock.return_value = build_response(HTTPStatus.FORBIDDEN, {"error": {"message": "no permission"}})

        with self.assertRaises(V4ClientError):
            self.client.retrieve_system()

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_create_system_injects_effective_system_id(self, request_mock):
        request_mock.return_value = created({"data": {"id": "bklog_test"}})

        system_id = self.client.create_system({"name": "日志平台", "clients": ["bk_log_search"]})

        self.assertEqual(system_id, "bklog_test")
        self.assertEqual(
            request_mock.call_args.kwargs["json"],
            {"name": "日志平台", "clients": ["bk_log_search"], "id": "bklog_test"},
        )
        self.assertEqual(
            self.called_paths(request_mock),
            [f"https://bkiam.example/prod/{DEFAULT_MODEL_BASE_PATH}"],
        )

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_update_system_requires_no_content(self, request_mock):
        request_mock.return_value = ok({"data": {}})

        with self.assertRaises(V4ClientError):
            self.client.update_system({"name": "新名称"})

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_update_system_accepts_no_content(self, request_mock):
        request_mock.return_value = no_content()

        self.assertIsNone(self.client.update_system({"name": "新名称"}))
        self.assertEqual(request_mock.call_args.kwargs["method"], "PUT")

    # ----------------------------------------------------------- resource type

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_list_resource_types_follows_pagination(self, request_mock):
        first_page = [{"id": f"rt{index}", "name": str(index), "ancestors": []} for index in range(100)]
        second_page = [{"id": "rt100", "name": "100", "ancestors": ["rt0"]}]
        request_mock.side_effect = [
            ok({"data": {"count": 101, "results": first_page}}),
            ok({"data": {"count": 101, "results": second_page}}),
        ]

        results = self.client.list_resource_types()

        self.assertEqual(len(results), 101)
        self.assertEqual(results[-1]["id"], "rt100")
        self.assertEqual(
            self.called_paths(request_mock),
            [
                f"https://bkiam.example/prod/{DEFAULT_MODEL_BASE_PATH}bklog_test/resource-types/"
                f"?page={page}&page_size=100"
                for page in (1, 2)
            ],
        )

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_list_stops_on_empty_page_even_if_count_is_larger(self, request_mock):
        request_mock.side_effect = [ok({"data": {"count": 5, "results": []}})]

        self.assertEqual(self.client.list_actions(), [])
        self.assertEqual(request_mock.call_count, 1)

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_list_rejects_response_without_results(self, request_mock):
        request_mock.return_value = ok({"data": {"count": 1}})

        with self.assertRaisesRegex(V4ResponseError, "results list"):
            self.client.list_roles()

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_list_rejects_response_without_count(self, request_mock):
        request_mock.return_value = ok({"data": {"results": [{"id": "space"}]}})

        with self.assertRaisesRegex(V4ResponseError, "integer count"):
            self.client.list_resource_types()

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_list_rejects_non_object_result_item(self, request_mock):
        request_mock.return_value = ok({"data": {"count": 1, "results": ["space"]}})

        with self.assertRaisesRegex(V4ResponseError, "result item must be an object"):
            self.client.list_resource_types()

    @patch("apps.iam.backends.v4.model_client.MAX_PAGES", 1)
    @patch("apps.iam.backends.v4.client.requests.request")
    def test_list_refuses_to_page_forever(self, request_mock):
        # count 与 results 不自洽时必须报错，而不是一直翻页。
        request_mock.return_value = ok({"data": {"count": 10_000, "results": [{"id": "space"}]}})

        with self.assertRaisesRegex(V4ResponseError, "pagination exceeded 1 pages"):
            self.client.list_actions()

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_batch_create_resource_types_returns_created_ids(self, request_mock):
        request_mock.return_value = created({"data": ["space", "indices"]})

        payload = [
            {"id": "space", "name": "空间", "ancestors": []},
            {"id": "indices", "name": "索引集", "ancestors": ["space"]},
        ]
        self.assertEqual(self.client.batch_create_resource_types(payload), ["space", "indices"])
        self.assertEqual(request_mock.call_args.kwargs["json"], payload)

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_batch_create_skips_request_for_empty_input(self, request_mock):
        self.assertEqual(self.client.batch_create_actions([]), [])

        request_mock.assert_not_called()

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_batch_create_rejects_non_list_response(self, request_mock):
        request_mock.return_value = created({"data": {"id": "space"}})

        with self.assertRaisesRegex(V4ResponseError, "batch create response must be a list"):
            self.client.batch_create_resource_types([{"id": "space", "name": "空间", "ancestors": []}])

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_update_resource_type_targets_detail_path(self, request_mock):
        request_mock.return_value = no_content()

        self.client.update_resource_type("es_source", {"name": "ES 源"})

        self.assertEqual(
            self.called_paths(request_mock),
            [f"https://bkiam.example/prod/{DEFAULT_MODEL_BASE_PATH}bklog_test/resource-types/es_source/"],
        )

    # ----------------------------------------------------------------- action

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_update_action_targets_detail_path(self, request_mock):
        request_mock.return_value = no_content()

        self.client.update_action("search_log", {"name": "日志检索"})

        self.assertEqual(
            self.called_paths(request_mock),
            [f"https://bkiam.example/prod/{DEFAULT_MODEL_BASE_PATH}bklog_test/actions/search_log/"],
        )
        self.assertEqual(request_mock.call_args.kwargs["json"], {"name": "日志检索"})

    # ------------------------------------------------------------------- role

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_batch_create_role_actions_targets_role_actions_path(self, request_mock):
        request_mock.return_value = created({"data": ["search_log"]})

        result = self.client.batch_create_role_actions(
            "space_viewer", [{"id": "search_log", "resource_type_id": "indices"}]
        )

        self.assertEqual(result, ["search_log"])
        self.assertEqual(
            self.called_paths(request_mock),
            [f"https://bkiam.example/prod/{DEFAULT_MODEL_BASE_PATH}bklog_test/roles/space_viewer/actions/"],
        )

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_batch_delete_role_actions_passes_ids_as_query(self, request_mock):
        request_mock.return_value = no_content()

        self.client.batch_delete_role_actions("space_viewer", ["search_log", "view_business"])

        self.assertEqual(request_mock.call_args.kwargs["method"], "DELETE")
        self.assertEqual(
            self.called_paths(request_mock),
            [
                f"https://bkiam.example/prod/{DEFAULT_MODEL_BASE_PATH}bklog_test/roles/space_viewer/actions/"
                "?ids=search_log%2Cview_business"
            ],
        )

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_batch_create_roles_posts_to_roles_path(self, request_mock):
        request_mock.return_value = created({"data": ["space_viewer"]})

        result = self.client.batch_create_roles([{"id": "space_viewer", "name": "业务只读", "actions": []}])

        self.assertEqual(result, ["space_viewer"])
        self.assertEqual(
            self.called_paths(request_mock),
            [f"https://bkiam.example/prod/{DEFAULT_MODEL_BASE_PATH}bklog_test/roles/"],
        )

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_update_role_targets_detail_path(self, request_mock):
        request_mock.return_value = no_content()

        self.client.update_role("space_viewer", {"name": "业务只读"})

        self.assertEqual(
            self.called_paths(request_mock),
            [f"https://bkiam.example/prod/{DEFAULT_MODEL_BASE_PATH}bklog_test/roles/space_viewer/"],
        )

    @patch("apps.iam.backends.v4.client.requests.request")
    def test_batch_delete_role_actions_skips_empty_input(self, request_mock):
        self.client.batch_delete_role_actions("space_viewer", [])

        request_mock.assert_not_called()


@override_settings(
    APP_CODE="bk_log_search",
    SECRET_KEY="secret",
    BK_IAM_SYSTEM_ID="bk_log_search",
    BK_IAM_V4_SYSTEM_ID="bklog_test",
    BK_IAM_V4_APIGATEWAY_URL="https://bkiam.example/prod/",
)
class V4ModelClientFromSettingsTest(SimpleTestCase):
    def test_from_settings_uses_v4_gateway_and_system(self):
        client = V4ModelClient.from_settings(username="admin", bk_tenant_id="system")

        self.assertEqual(client.options.gateway_url, "https://bkiam.example/prod/")
        self.assertEqual(client.options.system_id, "bklog_test")
        self.assertEqual(client.options.model_base_path, DEFAULT_MODEL_BASE_PATH)
        self.assertEqual(client.bk_tenant_id, "system")
