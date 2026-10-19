"""Product resource queries are shared by V3 and the common V4 adapter."""

from types import SimpleNamespace
from unittest.mock import patch

from django.db.models import Q
from django.test import SimpleTestCase
from iam.resource.utils import Page, get_filter_obj

from apps.iam.backends.v4.codec import BklogNameCodec
from apps.iam.views.resources import CollectionResourceProvider, EsSourceResourceProvider, IndicesResourceProvider, SpaceResourceProvider
from iam_engine.v4.callback import V4CallbackIAM, V4ResourceApiDispatcher
from iam_engine.v4.resource import V4ResourceProvider
from apps.iam.handlers.resources import Business, Collection, Indices, EsSource


class ProductInstanceConstructionTest(SimpleTestCase):
    def test_space_lookup_retains_uid_negative_id_name_and_original_fallback(self):
        row = SimpleNamespace(bk_biz_id=-5423, space_type_id="bcs", space_name="cluster")
        with patch("apps.iam.views.resources.Space.objects.get", return_value=row) as query:
            with patch("apps.log_search.models.SpaceType.get_name_by_id", return_value="容器"):
                resource = Business.create_simple_instance("bcs__cluster", {"custom": "kept"})
        query.assert_called_once_with(space_uid="bcs__cluster")
        self.assertEqual(resource.id, "-5423")
        self.assertEqual(resource.attribute, {"id": "-5423", "name": "[容器] cluster", "custom": "kept"})
        with patch("apps.iam.views.resources.Space.objects.get", side_effect=ValueError("unknown")):
            resource = Business.create_simple_instance("missing")
        self.assertEqual(resource.attribute, {"id": "missing", "name": "missing"})

    def test_collection_and_indices_use_native_provider_queries_without_changing_v3_projection(self):
        collection = SimpleNamespace(collector_config_name="collector", bk_biz_id=2)
        with patch("apps.iam.views.resources.CollectorConfig.objects.get", return_value=collection) as query:
            resource = Collection.create_simple_instance("0012")
        query.assert_called_once_with(pk="0012")
        self.assertEqual(resource.id, "0012")
        self.assertEqual(resource.attribute, {"id": "0012", "name": "collector", "bk_biz_id": "2", "_bk_iam_path_": "/space,2/"})
        index = SimpleNamespace(index_set_name="index", space_uid="bkcc__2")
        with patch("apps.iam.views.resources.LogIndexSet.objects.get", return_value=index) as query:
            with patch("apps.iam.views.resources.space_uid_to_bk_biz_id", return_value=2):
                resource = Indices.create_simple_instance("12")
        query.assert_called_once_with(pk="12")
        self.assertEqual(resource.attribute, {"id": "12", "name": "index", "bk_biz_id": "2", "_bk_iam_path_": "/space,2/"})

    def test_supplied_attributes_skip_lookup_and_lookup_errors_keep_original_contract(self):
        from apps.log_databus.models import CollectorConfig
        with patch("apps.iam.views.resources.CollectorConfig.objects.get") as query:
            self.assertEqual(Collection.create_simple_instance("12", {"name": "supplied"}).attribute, {"name": "supplied"})
            query.assert_not_called()
            query.side_effect = CollectorConfig.DoesNotExist()
            self.assertEqual(Collection.create_simple_instance("12").attribute, {})
            query.side_effect = ValueError("invalid primary key")
            with self.assertRaises(ValueError):
                Collection.create_simple_instance("bad")

    def test_es_constructor_and_callback_share_the_source_but_keep_original_names_and_scope(self):
        config = {"cluster_id": 12, "cluster_name": "cluster", "display_name": "alias", "custom_option": {"bk_biz_id": 2}, "creator": "owner"}
        with patch("apps.iam.views.resources.TransferApi.get_cluster_info", return_value=[{"cluster_config": config}]) as query:
            resource = EsSource.create_simple_instance("12")
            rows = EsSourceResourceProvider.list_clusters("system")
        self.assertEqual(query.call_args_list[0].args[0], {"cluster_id": "12"})
        self.assertEqual(resource.attribute["name"], "alias")
        self.assertEqual(rows[0]["display_name"], "cluster")
        self.assertEqual(resource.attribute["_bk_iam_path_"], rows[0]["_bk_iam_path_"])


class Rows:
    def __init__(self, rows):
        self.rows = list(rows)

    @classmethod
    def matches(cls, row, condition):
        if isinstance(condition, Q):
            values = [cls.matches(row, child) for child in condition.children]
            result = any(values) if condition.connector == Q.OR else all(values)
            return not result if condition.negated else result
        key, expected = condition
        field, _, lookup = key.partition("__")
        actual = getattr(row, field)
        if lookup == "in":
            return actual in expected
        if lookup == "icontains":
            return expected.lower() in actual.lower()
        return str(actual) == str(expected)

    def filter(self, *args, **kwargs):
        return Rows(row for row in self.rows if all(self.matches(row, c) for c in [*args, *kwargs.items()]))

    def all(self):
        return self

    def count(self):
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def __getitem__(self, index):
        return self.rows[index]


def list_filter(**kwargs):
    return get_filter_obj(kwargs, ["parent", "search", "resource_type_chain", "action", "ancestors"])


def fetch_filter(ids, attrs=None):
    return get_filter_obj({"ids": ids, "attrs": attrs}, ["ids", "attrs"])


class ProductProviderQueryTest(SimpleTestCase):
    def setUp(self):
        self.page = Page(limit=20, offset=0)
        self.rows = Rows([
            SimpleNamespace(pk=1, collector_config_id=1, collector_config_name="match-collection", bk_biz_id=-5423, created_by="creator"),
            SimpleNamespace(pk=2, collector_config_id=2, collector_config_name="other-collection", bk_biz_id=-5423, created_by="creator"),
            SimpleNamespace(pk=3, collector_config_id=3, collector_config_name="match-foreign", bk_biz_id=10, created_by="creator"),
        ])

    @patch("apps.iam.views.resources.CollectionResourceProvider.ENABLE_MULTI_TENANT_MODE", False)
    def test_v3_contract_and_parent_precedence_are_unchanged(self):
        with patch("apps.iam.views.resources.CollectorConfig.objects.filter", self.rows.filter):
            provider = CollectionResourceProvider()
            filters = list_filter(parent={"type": "space", "id": "-5423"}, search={"collection": ["match"]})
            result = provider.list_instance(filters, self.page, bk_tenant_id="system")
            self.assertEqual(result.results, [
                {"id": "1", "display_name": "match-collection"}, {"id": "2", "display_name": "other-collection"}
            ])
            result = provider.fetch_instance_info(fetch_filter(["1"]), bk_tenant_id="system")
            self.assertEqual(result.results, [{"id": "1", "display_name": "match-collection", "_bk_iam_approver_": "creator"}])

    @patch("apps.iam.views.resources.CollectionResourceProvider.ENABLE_MULTI_TENANT_MODE", False)
    def test_v4_reuses_native_query_with_parent_keyword_and_encoded_path(self):
        with patch("apps.iam.views.resources.CollectorConfig.objects.filter", self.rows.filter):
            native = CollectionResourceProvider()
            provider = V4ResourceProvider(native, "collection", BklogNameCodec())
            filters = list_filter(parent={"type": "space", "id": "neg_5423"}, search={"collection": ["match"]})
            result = provider.list_instance(filters, self.page, bk_tenant_id="system")
            self.assertEqual(result.results, [{"id": "1", "display_name": "match-collection", "_bk_iam_path_": "/space,neg_5423/"}])
            result = provider.fetch_instance_info(fetch_filter(["1"]), bk_tenant_id="system")
            self.assertEqual(result.results, [{"id": "1", "display_name": "match-collection", "_bk_iam_approvers_": ["creator"], "_bk_iam_path_": "/space,neg_5423/"}])
            # The input remains in V4 form; conversions must not mutate caller data.
            self.assertEqual(filters.parent["id"], "neg_5423")

    @patch("apps.iam.views.resources.IndicesResourceProvider.ENABLE_MULTI_TENANT_MODE", True)
    @patch("apps.iam.views.resources.Space.get_space_uid_list", return_value=["bkcc__10"])
    @patch("apps.iam.views.resources.space_uid_to_bk_biz_id", return_value=10)
    def test_v4_indices_details_keep_tenant_boundary_and_use_one_queryset(self, *_):
        rows = Rows([
            SimpleNamespace(pk=1, index_set_name="own", space_uid="bkcc__10", created_by="creator"),
            SimpleNamespace(pk=2, index_set_name="foreign", space_uid="bkcc__20", created_by="other"),
        ])
        with patch("apps.iam.views.resources.LogIndexSet.objects.filter", wraps=rows.filter) as query:
            provider = V4ResourceProvider(IndicesResourceProvider(), "indices", BklogNameCodec())
            result = provider.fetch_instance_info(fetch_filter(["1", "2"]), bk_tenant_id="tenant-a")
        self.assertEqual([item["id"] for item in result.results], ["1"])
        self.assertEqual(result.results[0]["_bk_iam_path_"], "/space,10/")
        query.assert_called_once_with(pk__in=[1, 2])

    @patch("apps.iam.views.resources.EsSourceResourceProvider.list_clusters")
    def test_v4_es_source_uses_one_existing_cluster_snapshot(self, clusters):
        clusters.return_value = [
            {"id": "1", "display_name": "match", "bk_biz_id": "-5423", "owner": "creator", "_bk_iam_path_": "/space,-5423/"},
            {"id": "2", "display_name": "other", "bk_biz_id": "-5423", "owner": "creator", "_bk_iam_path_": "/space,-5423/"},
        ]
        provider = V4ResourceProvider(EsSourceResourceProvider(), "es_source", BklogNameCodec())
        result = provider.fetch_instance_info(fetch_filter(["1"]), bk_tenant_id="tenant-a")
        self.assertEqual(result.results, [{"id": "1", "display_name": "match", "_bk_iam_approvers_": ["creator"], "_bk_iam_path_": "/space,neg_5423/"}])
        clusters.assert_called_once_with(bk_tenant_id="tenant-a")
        clusters.reset_mock()
        result = provider.list_instance(list_filter(parent={"type": "space", "id": "neg_5423"}, search={"es_source": ["match"]}), self.page, bk_tenant_id="tenant-a")
        self.assertEqual([item["id"] for item in result.results], ["1"])
        clusters.assert_called_once_with(bk_tenant_id="tenant-a")

    @patch("apps.iam.views.resources.EsSourceResourceProvider.list_clusters", return_value=[])
    def test_v4_empty_ids_do_not_expand_to_all_es_sources(self, clusters):
        provider = V4ResourceProvider(EsSourceResourceProvider(), "es_source", BklogNameCodec())
        self.assertEqual(provider.fetch_instance_info(fetch_filter([]), bk_tenant_id="system").results, [])
        clusters.assert_not_called()

    @patch("apps.iam.views.resources.Space.get_spaces_page", return_value=([{"bk_biz_id": -5423, "space_type_name": "项目", "space_name": "demo"}], 1))
    @patch("apps.iam.views.resources.Space.get_spaces_by_bk_biz_ids", return_value=[{"bk_biz_id": -5423, "space_type_name": "项目", "space_name": "demo"}])
    def test_space_proxy_only_reads_local_snapshot(self, fetch, listing):
        provider = V4ResourceProvider(SpaceResourceProvider(), "space", BklogNameCodec())
        result = provider.list_instance(list_filter(search={"space": ["demo"]}), self.page, bk_tenant_id="tenant-a")
        self.assertEqual(result.results, [{"id": "neg_5423", "display_name": "[项目] demo"}])
        result = provider.fetch_instance_info(fetch_filter(["neg_5423"]), bk_tenant_id="tenant-a")
        self.assertEqual(result.results[0]["id"], "neg_5423")
        fetch.assert_called_once_with("tenant-a", ["-5423"])
        listing.assert_called_once_with("tenant-a", offset=0, limit=20, keywords=["demo"])


class ProductRegistrationTest(SimpleTestCase):
    def test_v4_registers_native_providers_on_common_dispatcher(self):
        from apps.iam import urls
        self.assertIs(type(urls.v4_dispatcher), V4ResourceApiDispatcher)
        self.assertIs(type(urls.v4_dispatcher.iam), V4CallbackIAM)
        for kind, native in (("space", SpaceResourceProvider), ("collection", CollectionResourceProvider), ("indices", IndicesResourceProvider), ("es_source", EsSourceResourceProvider)):
            wrapped = urls.v4_dispatcher._provider[kind]
            self.assertIs(type(wrapped), V4ResourceProvider)
            self.assertIs(type(wrapped.provider), native)
        self.assertIs(type(urls.dispatcher._provider["collection"]), CollectionResourceProvider)
