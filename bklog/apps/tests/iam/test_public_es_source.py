import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase, override_settings
from iam import IAM, ObjectSet, make_expression

from apps.api import TransferApi
from apps.iam.backends.v3.provider import V3PermissionProvider
from apps.iam.backends.v4.codec import BklogNameCodec
from apps.iam.backends.v4.provider import V4PermissionProvider
from apps.iam.exceptions import PermissionDeniedError
from apps.iam.handlers.actions import ActionEnum, get_action_by_id
from apps.iam.handlers.drf import InstanceActionPermission
from apps.iam.handlers.permission import Permission
from apps.iam.handlers.resources import ResourceEnum
from apps.iam.views.resources import EsSourceResourceProvider
from apps.log_databus.constants import STORAGE_CLUSTER_TYPE
from apps.log_databus.handlers.storage import StorageHandler
from apps.log_databus.views.storage_views import StorageViewSet
from iam_engine.core.config import AuthMode
from iam_engine.provider.bundle import ProviderBundle
from iam_engine.provider.router import ModeRouter
from iam_engine.v4.callback import V4ResourceApiDispatcher
from iam_engine.v4.resource import V4ResourceProvider


def cluster(biz_id="", registered_system="_default", cluster_id=3):
    return {
        "cluster_type": STORAGE_CLUSTER_TYPE,
        "cluster_config": {
            "cluster_id": cluster_id,
            "cluster_name": f"es_cluster{cluster_id}",
            "registered_system": registered_system,
            "creator": "admin",
            "create_time": "",
            "last_modify_time": "",
            "custom_option": {"bk_biz_id": biz_id},
        },
        "auth_info": {"username": "", "password": ""},
    }


@override_settings(BLUEKING_BK_BIZ_ID=1)
class PublicEsSourceResourceTest(SimpleTestCase):
    def test_public_resource_uses_configured_business_without_modifying_metadata(self):
        for biz_id in (None, "", 0, 99):
            for configured_biz_id in (1, 42):
                with self.subTest(biz_id=biz_id, configured_biz_id=configured_biz_id):
                    data = cluster(biz_id=biz_id)
                    if biz_id is None:
                        data["cluster_config"]["custom_option"].clear()
                    before = copy.deepcopy(data)
                    with (
                        self.settings(BLUEKING_BK_BIZ_ID=configured_biz_id),
                        patch.object(TransferApi, "get_cluster_info", return_value=[data]),
                    ):
                        resource = ResourceEnum.ES_SOURCE.create_instance("3")
                    self.assertEqual(resource.attribute["_bk_iam_path_"], f"/space,{configured_biz_id}/")
                    self.assertEqual(resource.attribute["bk_biz_id"], str(configured_biz_id))
                    self.assertEqual(data, before)

    def test_private_resource_keeps_its_business(self):
        for biz_id in (5, -42, 0, ""):
            with self.subTest(biz_id=biz_id):
                with patch.object(TransferApi, "get_cluster_info", return_value=[cluster(biz_id, "bklog")]):
                    resource = ResourceEnum.ES_SOURCE.create_instance("3")
                self.assertEqual(resource.attribute["bk_biz_id"], str(biz_id))
                self.assertEqual(resource.attribute["_bk_iam_path_"], f"/space,{biz_id}/")


@override_settings(BLUEKING_BK_BIZ_ID=1, IGNORE_IAM_PERMISSION=False, DEMO_BIZ_ID=0)
class PublicEsSourcePermissionTest(SimpleTestCase):
    def permission(self, mode, username):
        def policy(subject_id):
            biz_id = 1 if subject_id == "authorized" else 99
            return {"op": "starts_with", "field": "es_source._bk_iam_path_", "value": f"/space,{biz_id}/"}

        sdk = IAM("test", "test", "https://iam.example/")
        sdk._do_policy_query = Mock(side_effect=lambda request: policy(request.subject.id))
        sdk._do_policy_query_by_actions = Mock(
            side_effect=lambda request, **kwargs: [
                {"action": {"id": action.id}, "condition": policy(request.subject.id)} for action in request.actions
            ]
        )
        v3 = V3PermissionProvider(sdk, ResourceEnum.ES_SOURCE.system_id)

        def allowed(subject, resource):
            objects = ObjectSet()
            objects.add_object("es_source", resource["attributes"])
            return make_expression(policy(subject["id"])).eval(objects)

        client = Mock()
        client.options.batch_chunk_size = 20
        client.options.batch_max_workers = 1
        client.direct_auth.side_effect = lambda subject, action_id, resource: allowed(subject, resource)
        client.direct_auth_by_resources.side_effect = lambda subject, action_id, resources: {
            item["id"]: allowed(subject, item) for item in resources
        }
        v4 = V4PermissionProvider(client, action_resolver=get_action_by_id)
        with patch.object(Permission, "get_iam_client", return_value=sdk):
            permission = Permission(username=username, bk_tenant_id="tenant-1")
        permission._mode_router = ModeRouter(
            mode_provider=Mock(get_mode=Mock(return_value=mode)),
            bundles={AuthMode.V3: ProviderBundle(auth=v3), AuthMode.V4: ProviderBundle(auth=v4)},
            pair_executor=lambda left, right: (left(), right()),
        )
        permission.get_apply_data = Mock(return_value=({}, ""))
        return permission

    def test_list_and_write_keep_same_business_scope_in_all_modes(self):
        config = {
            "ES_PUBLIC_STORAGE_DURATION": 7,
            "ES_REPLICAS": 0,
            "ES_SHARDS": 3,
            "ES_SHARDS_MAX": 64,
        }
        with patch("apps.log_search.handlers.index_set.IndexSetHandler.get_index_set_for_storage"):
            included, item = StorageHandler.filter_es_cluster(1, True, False, cluster(), config)
        self.assertTrue(included)
        self.assertEqual(item["bk_biz_id"], 1)

        action = ActionEnum.MANAGE_ES_SOURCE
        for mode in (AuthMode.V3, AuthMode.V4, AuthMode.UNION):
            for username in ("authorized", "other_business"):
                with self.subTest(mode=mode, username=username):
                    permission = self.permission(mode, username)
                    view = StorageViewSet()
                    request = SimpleNamespace(method="PUT", data={"bk_biz_id": 99}, query_params={"bk_biz_id": 99})
                    with (
                        patch.object(view, "params_valid", return_value={"bk_biz_id": 1}),
                        patch.object(StorageHandler, "list", return_value=[copy.deepcopy(item)]),
                        patch("apps.iam.handlers.drf.Permission", return_value=permission),
                        patch.object(TransferApi, "get_cluster_info", return_value=[cluster()]) as query,
                    ):
                        response = view.list(request)
                        query.assert_not_called()
                        self.assertEqual(response.data[0]["permission"][action.id], username == "authorized")
                        instance_view = SimpleNamespace(
                            kwargs={"cluster_id": "3"}, lookup_field="cluster_id", lookup_url_kwarg=None
                        )
                        instance_permission = InstanceActionPermission([action], ResourceEnum.ES_SOURCE)
                        if username == "authorized":
                            self.assertTrue(instance_permission.has_permission(request, instance_view))
                        else:
                            with self.assertRaises(PermissionDeniedError):
                                instance_permission.has_permission(request, instance_view)
                        query.assert_called_once_with({"cluster_id": "3"})
                        encoded = BklogNameCodec().encode_resource_for_auth(
                            Permission._to_engine_resource(instance_permission.resources[0])
                        )
                        self.assertEqual(encoded["attributes"]["_bk_iam_path_"], "/space,1/")


@override_settings(BLUEKING_BK_BIZ_ID=1, ENABLE_MULTI_TENANT_MODE=True)
class PublicEsSourceCallbackTest(SimpleTestCase):
    def setUp(self):
        self.api = self.enterContext(patch.object(TransferApi, "get_cluster_info"))
        self.api.side_effect = lambda params, bk_tenant_id=None: [cluster()] if bk_tenant_id == "tenant-1" else []
        iam = Mock()
        iam.mode_loader.return_value = AuthMode.V4
        iam.is_basic_auth_allowed.return_value = True
        self.dispatcher = V4ResourceApiDispatcher(iam, system="bklog_test")
        self.dispatcher.register(
            "es_source", V4ResourceProvider(EsSourceResourceProvider(), "es_source", BklogNameCodec())
        )

    def dispatch(self, method, filter_data, tenant_id="tenant-1", page=None):
        body = {"type": "es_source", "method": method, "filter": filter_data}
        if page is not None:
            body["page"] = page
        request = RequestFactory().post(
            "/api/v1/iam/v4/resource/",
            data=json.dumps(body),
            content_type="application/json",
            HTTP_AUTHORIZATION="Basic test",
            HTTP_X_BK_TENANT_ID=tenant_id,
        )
        return self.dispatcher._dispatch(request)

    def test_http_fetch_returns_public_cluster_with_business_path(self):
        for biz_id in (None, "", 0):
            with self.subTest(biz_id=biz_id):
                data = cluster(biz_id=biz_id)
                if biz_id is None:
                    data["cluster_config"]["custom_option"].clear()
                before = copy.deepcopy(data)
                self.api.side_effect = None
                self.api.return_value = [data]
                response = self.dispatch("fetch_instance_info", {"ids": ["3"], "attrs": ["_bk_iam_path_"]})
                self.assertEqual(response.status_code, 200)
                result = json.loads(response.content)["data"]
                self.assertEqual(result[0]["id"], "3")
                self.assertEqual(result[0]["_bk_iam_path_"], "/space,1/")
                self.assertEqual(data, before)
                self.assertEqual(self.api.call_args.kwargs, {"bk_tenant_id": "tenant-1"})

    def test_http_list_keyword_respects_parent_space(self):
        for keyword in ("", "es_cluster", "missing"):
            for parent_id in ("1", "99"):
                with self.subTest(keyword=keyword, parent_id=parent_id):
                    response = self.dispatch(
                        "list_instance",
                        {"parent": {"type": "space", "id": parent_id}, "keyword": keyword},
                        page={"page": 1, "page_size": 10},
                    )
                    self.assertEqual(response.status_code, 200)
                    result = json.loads(response.content)["data"]
                    self.assertEqual(result["count"], 1 if parent_id == "1" and keyword != "missing" else 0)
                    if result["results"]:
                        self.assertEqual(result["results"][0]["id"], "3")

    def test_http_callback_does_not_return_cluster_from_another_tenant(self):
        response = self.dispatch("fetch_instance_info", {"ids": ["3"]}, tenant_id="tenant-2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["data"], [])
        self.api.assert_called_once_with(
            {"cluster_type": STORAGE_CLUSTER_TYPE, "no_request": True}, bk_tenant_id="tenant-2"
        )

    def test_http_callback_requires_tenant_header(self):
        response = self.dispatch("fetch_instance_info", {"ids": ["3"]}, tenant_id="")
        self.assertEqual(response.status_code, 400)
        self.api.assert_not_called()

    def test_v3_callback_keeps_public_filter_and_private_instances(self):
        self.api.side_effect = None
        self.api.return_value = [cluster(), cluster(5, "bklog", 4), cluster("", "bklog", 5)]
        legacy = EsSourceResourceProvider.list_clusters("tenant-1")
        current = EsSourceResourceProvider.list_clusters("tenant-1", include_public=True)
        self.assertEqual([item["id"] for item in legacy], ["4"])
        self.assertEqual([item["id"] for item in current], ["3", "4"])
        self.assertEqual(current[1]["_bk_iam_path_"], "/space,5/")
