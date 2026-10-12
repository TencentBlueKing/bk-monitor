import warnings
from unittest.mock import Mock

from django.test import SimpleTestCase, override_settings
from iam import Resource

from apps.iam.backends.v3.apply import V3ApplicationBuilder
from apps.iam.backends.v3.provider import V3PermissionProvider
from apps.iam.handlers.actions import ActionEnum, get_action_by_id
from apps.iam.iam_engine.core.requests import ResourceInstance as EngineResourceInstance


@override_settings(
    BK_IAM_SYSTEM_ID="bk_log_search",
    BK_IAM_SYSTEM_NAME="日志平台",
    BK_IAM_SAAS_HOST="https://iam.example/saas",
)
class V3ApplicationBuilderTest(SimpleTestCase):
    def setUp(self):
        self.client = Mock()
        self.client.get_apply_url.return_value = (True, "success", "https://iam.example/apply?system=bk_log_search")
        self.builder = V3ApplicationBuilder(self.client, "bk_log_search", action_resolver=get_action_by_id)
        self.collection = Resource("bk_log_search", "collection", "28", {"name": "collection-28"})

    def test_apply_data_describes_action_and_resource_instances(self):
        data, url = self.builder.get_apply_data([ActionEnum.VIEW_COLLECTION], [self.collection])

        self.assertEqual(data["system_id"], "bk_log_search")
        self.assertEqual([action["id"] for action in data["actions"]], ["view_collection_v2"])
        related = data["actions"][0]["related_resource_types"]
        self.assertEqual([item["type"] for item in related], ["collection"])
        self.assertEqual(
            related[0]["instances"],
            [[{"type": "collection", "type_name": related[0]["type_name"], "id": "28", "name": "collection-28"}]],
        )
        self.assertEqual(url, "https://iam.example/apply?system=bk_log_search&tab_key=independent")

    def test_action_without_related_resources_drops_incoming_resources(self):
        data, _url = self.builder.get_apply_data([ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE], [self.collection])

        self.assertEqual(data["actions"][0]["related_resource_types"], [])
        application = self.client.get_apply_url.call_args.args[0].to_dict()
        self.assertEqual(
            application["actions"],
            [{"id": "manage_global_desensitize_rule", "related_resource_types": []}],
        )

    def test_application_only_attaches_resources_matching_the_related_type(self):
        other = Resource("bk_log_search", "indices", "9", {"name": "index-9"})

        application = self.builder.make_application([ActionEnum.VIEW_COLLECTION], [self.collection, other])

        self.assertEqual(
            application.to_dict()["actions"],
            [
                {
                    "id": "view_collection_v2",
                    "related_resource_types": [
                        {
                            "system_id": "bk_log_search",
                            "type": "collection",
                            "instances": [[{"type": "collection", "id": "28", "name": "collection-28"}]],
                        }
                    ],
                }
            ],
        )

    def test_unknown_action_id_is_kept_as_an_action_without_resources(self):
        application = self.builder.make_application(["action_that_does_not_exist"], [self.collection])

        self.assertEqual(
            application.to_dict()["actions"],
            [{"id": "action_that_does_not_exist", "related_resource_types": []}],
        )

    def test_apply_url_appends_tab_key_when_url_has_no_query(self):
        self.client.get_apply_url.return_value = (True, "success", "https://iam.example/apply")

        url = self.builder.get_apply_url([ActionEnum.VIEW_COLLECTION], [self.collection])

        self.assertEqual(url, "https://iam.example/apply?tab_key=independent")

    def test_apply_url_falls_back_to_saas_host_when_iam_fails(self):
        self.client.get_apply_url.return_value = (False, "iam unavailable", "")

        url = self.builder.get_apply_url([ActionEnum.VIEW_COLLECTION], [self.collection])

        self.assertEqual(url, "https://iam.example/saas")

    def test_missing_action_resolver_fails_loudly_instead_of_silently_skipping(self):
        builder = V3ApplicationBuilder(self.client, "bk_log_search")

        with self.assertRaises(ValueError):
            builder.get_apply_data([ActionEnum.VIEW_COLLECTION], [self.collection])


@override_settings(
    BK_IAM_SYSTEM_ID="bk_log_search",
    BK_IAM_SYSTEM_NAME="日志平台",
    BK_IAM_SAAS_HOST="https://iam.example/saas",
)
class V3PermissionProviderApplyTest(SimpleTestCase):
    def test_engine_resources_are_encoded_into_v3_sdk_resources(self):
        client = Mock()
        client.get_apply_url.return_value = (True, "success", "https://iam.example/apply")
        provider = V3PermissionProvider(client, "bk_log_search", action_resolver=get_action_by_id)

        data, _url = provider.get_apply_data(
            [ActionEnum.VIEW_COLLECTION],
            [
                EngineResourceInstance(
                    system="bk_log_search",
                    type="collection",
                    id="28",
                    name="collection-28",
                    attributes={"_bk_iam_path_": "/space,10/"},
                )
            ],
        )

        instances = data["actions"][0]["related_resource_types"][0]["instances"]
        self.assertEqual([instance[0]["id"] for instance in instances], ["28"])
        self.assertEqual([instance[0]["name"] for instance in instances], ["collection-28"])

    def test_apply_url_passes_v3_sdk_resources_straight_through(self):
        client = Mock()
        client.get_apply_url.return_value = (True, "success", "https://iam.example/apply")
        provider = V3PermissionProvider(client, "bk_log_search", action_resolver=get_action_by_id)
        collection = Resource("bk_log_search", "collection", "28", {"name": "collection-28"})

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            url = provider.get_apply_url([ActionEnum.VIEW_COLLECTION], [collection], "bk_log_search")

        self.assertEqual(url, "https://iam.example/apply?tab_key=independent")
        application = client.get_apply_url.call_args.args[0].to_dict()
        related = application["actions"][0]["related_resource_types"]
        self.assertEqual(related[0]["instances"], [[{"type": "collection", "id": "28", "name": "collection-28"}]])
        self.assertTrue(any(item.category is DeprecationWarning for item in caught))
