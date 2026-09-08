from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps as django_apps
from django.test import SimpleTestCase, TestCase, override_settings

from apps.exceptions import ValidationError
from apps.feature_toggle.models import FeatureToggle
from apps.log_clustering.models import AiopsSignatureAndPattern, ClusteringConfig
from apps.log_databus.models import BcsRule, CollectorConfig, ContainerCollectorConfig
from apps.log_extract.models import ExtractLink, ExtractLinkHost
from apps.log_admin_resource.handlers.model_query import (
    FUNCTIONS,
    LOOKUPS_EXACT,
    MASKED_VALUE,
    SENSITIVE_TREE_KEY_PATTERN,
    SPECS,
    _apply_scope,
    _is_model_available,
    _mask_global_config_row,
    _mask_sensitive_tree,
    _normalize_filter,
    _normalize_limit,
    _normalize_order_by,
    _normalize_selected_fields,
    _resolve_model,
    _serialize_instance,
    _validate_spec,
    get_model_spec_detail,
    list_model_specs,
    query_model,
)
from apps.log_admin_resource.registry import AdminResourceRegistry
from apps.log_admin_resource.schema import validate_params
from apps.log_search.models import BizProperty, GlobalConfig, LogIndexSet, Scenario, Space


class ModelSpecContractTest(SimpleTestCase):
    def test_registry_declares_exactly_the_confirmed_fifty_one_models(self):
        self.assertEqual(len(SPECS), 51)
        self.assertIn("log_search.LogIndexSet", SPECS)
        self.assertIn("log_extract.ExtractLink", SPECS)
        self.assertIn("tgpa.TGPAReport", SPECS)
        self.assertNotIn("log_extract.Tasks", SPECS)
        self.assertNotIn("log_search.UserOperationRecord", SPECS)

    def test_no_allowlisted_field_matches_recursive_sensitive_key_rules(self):
        suspicious = [
            f"{alias}.{field_name}"
            for alias, spec in SPECS.items()
            for field_name in spec.field_lookups
            if SENSITIVE_TREE_KEY_PATTERN.search(field_name)
        ]

        self.assertEqual(suspicious, [])

    def test_list_only_returns_models_available_in_current_environment(self):
        with patch(
            "apps.log_admin_resource.handlers.model_query._is_model_available",
            side_effect=lambda spec: spec.domain != "tgpa",
        ):
            result = list_model_specs({})

        validate_params(result, FUNCTIONS["bklog.model.list"]["response_schema"], "response")
        self.assertEqual(result["count"], 48)
        self.assertTrue(all(item["domain"] != "tgpa" for item in result["items"]))
        self.assertEqual(result["next_call"]["func_name"], "bklog.model.detail")

    def test_list_filters_domain_without_expanding_field_schemas(self):
        with patch("apps.log_admin_resource.handlers.model_query._is_model_available", return_value=True):
            result = list_model_specs({"domain": "log_extract"})

        self.assertEqual(result["count"], 3)
        self.assertEqual(
            [item["model"] for item in result["items"]],
            ["log_extract.ExtractLink", "log_extract.ExtractLinkHost", "log_extract.Strategies"],
        )
        self.assertTrue(all("allowed_fields" not in item for item in result["items"]))

    def test_list_rejects_unknown_or_unavailable_domain(self):
        with self.assertRaisesRegex(ValidationError, "unknown or unavailable model domain"):
            list_model_specs({"domain": "unknown"})

    def test_every_current_environment_spec_matches_real_model_fields_and_managers(self):
        available = 0
        for alias, spec in SPECS.items():
            if not _is_model_available(spec):
                continue
            with self.subTest(model=alias):
                resolved, model = _resolve_model(alias)
                self.assertIs(resolved, spec)
                self.assertEqual(model._meta.object_name, spec.model_name)
                available += 1
        expected = 51 if _is_model_available(SPECS["tgpa.TGPAReport"]) else 48
        self.assertEqual(available, expected)

    def test_detail_describes_per_field_lookups_scope_limits_and_example(self):
        detail = get_model_spec_detail({"model": "log_search.LogIndexSet"})

        validate_params(detail, FUNCTIONS["bklog.model.detail"]["response_schema"], "response")
        self.assertEqual(detail["model"], "log_search.LogIndexSet")
        self.assertEqual(
            detail["field_lookups"]["index_set_name"],
            [
                "contains",
                "endswith",
                "exact",
                "in",
                "isnull",
                "startswith",
            ],
        )
        self.assertEqual(detail["max_limit"], 200)
        self.assertIn("current request tenant", detail["server_scope"])
        self.assertEqual(detail["manager"], "origin_objects")
        self.assertEqual(detail["next_call"]["func_name"], "bklog.model.query")
        self.assertTrue(detail["examples"])

    def test_every_model_spec_has_a_legal_bounded_query_example(self):
        for alias, spec in SPECS.items():
            with self.subTest(model=alias):
                self.assertTrue(spec.examples)
                for example in spec.examples:
                    fields = _normalize_selected_fields(example.get("fields"), None, spec)
                    ordering = _normalize_order_by(example.get("order_by"), spec)
                    limit = _normalize_limit(example.get("limit"), spec.max_limit)
                    self.assertTrue(fields)
                    self.assertLessEqual(len(ordering), 5)
                    self.assertLessEqual(limit, spec.max_limit)

    def test_unknown_and_unavailable_models_have_distinct_errors(self):
        with self.assertRaisesRegex(ValidationError, "outside the Resource Call allowlist"):
            _resolve_model("auth.User")

        with patch("apps.log_admin_resource.handlers.model_query.django_apps.get_model", side_effect=LookupError):
            with self.assertRaisesRegex(ValidationError, "unavailable in this environment"):
                _resolve_model("tgpa.TGPAReport")

    def test_model_availability_handles_optional_app_lookup(self):
        spec = SPECS["tgpa.TGPAReport"]
        with patch("apps.log_admin_resource.handlers.model_query.django_apps.get_model", return_value=object()):
            self.assertTrue(_is_model_available(spec))
        with patch("apps.log_admin_resource.handlers.model_query.django_apps.get_model", side_effect=LookupError):
            self.assertFalse(_is_model_available(spec))

    def test_model_spec_validation_fails_closed_for_invalid_server_declarations(self):
        base = SPECS["log_extract.ExtractLink"]
        model = django_apps.get_model("log_extract", "ExtractLink")
        relation_base = SPECS["log_extract.ExtractLinkHost"]
        relation_model = django_apps.get_model("log_extract", "ExtractLinkHost")
        cases = (
            (
                replace(
                    base,
                    field_lookups={"missing": LOOKUPS_EXACT},
                    default_fields=("missing",),
                    allowed_order_by=("missing",),
                    default_order_by=("missing",),
                ),
                model,
                "invalid ModelSpec field",
            ),
            (
                replace(
                    relation_base,
                    field_lookups={"link": LOOKUPS_EXACT},
                    default_fields=("link",),
                    allowed_order_by=("link",),
                    default_order_by=("link",),
                ),
                relation_model,
                "relation object is forbidden",
            ),
            (
                replace(
                    base,
                    field_lookups={"qcloud_secret_id": LOOKUPS_EXACT},
                    default_fields=("qcloud_secret_id",),
                    allowed_order_by=("qcloud_secret_id",),
                    default_order_by=("qcloud_secret_id",),
                ),
                model,
                "sensitive field is forbidden",
            ),
            (
                replace(
                    base,
                    field_lookups={"link_id": frozenset({"regex"})},
                    default_fields=("link_id",),
                    allowed_order_by=("link_id",),
                    default_order_by=("link_id",),
                ),
                model,
                "invalid ModelSpec lookups",
            ),
            (replace(base, default_fields=("missing",)), model, "default fields are outside"),
            (replace(base, fixed_filters={"missing": 1}), model, "fixed filters are outside"),
            (replace(base, allowed_order_by=("missing",)), model, "order fields are outside"),
            (
                replace(base, default_order_by=("-name",), allowed_order_by=("link_id",)),
                model,
                "default ordering is outside",
            ),
            (replace(base, manager_name="missing"), model, "manager does not exist"),
            (replace(base, max_limit=0), model, "invalid ModelSpec max limit"),
        )
        for spec, model_class, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(RuntimeError, message):
                _validate_spec(spec, model_class)

    def test_limit_normalization_covers_default_conversion_and_boundaries(self):
        self.assertEqual(_normalize_limit(None, 50), 50)
        self.assertEqual(_normalize_limit("20", 50), 20)
        for value, message in (
            (True, "must be an integer"),
            ("bad", "must be an integer"),
            (0, "must be positive"),
            (51, "must be at most 50"),
        ):
            with self.subTest(value=value), self.assertRaisesRegex(ValidationError, message):
                _normalize_limit(value, 50)

    def test_field_selection_defaults_deduplicates_excludes_and_rejects_unsafe_fields(self):
        spec = SPECS["log_extract.ExtractLink"]
        self.assertEqual(_normalize_selected_fields(None, None, spec), spec.default_fields)
        self.assertEqual(
            _normalize_selected_fields(["link_id", "name", "link_id"], ["name"], spec),
            ("link_id",),
        )
        cases = (
            ([], None, "non-empty array"),
            ("link_id", None, "non-empty array"),
            (["link_id"], "name", "exclude_fields must be an array"),
            (["missing"], None, "outside the ModelSpec allowlist"),
            (["qcloud_secret_id"], None, "sensitive field is not readable"),
            (["link_id"], ["link_id"], "selection must not be empty"),
        )
        for fields, excluded, message in cases:
            with self.subTest(fields=fields), self.assertRaisesRegex(ValidationError, message):
                _normalize_selected_fields(fields, excluded, spec)

    def test_filter_normalization_rejects_relation_unsafe_lookup_and_bad_values(self):
        spec = SPECS["log_extract.ExtractLink"]
        self.assertEqual(
            _normalize_filter({"link_id__in": [1, 2], "name__contains": "cos"}, spec),
            {"link_id__in": [1, 2], "name__contains": "cos"},
        )
        cases = (
            ("link_id=1", "filter must be an object"),
            ({"link__name__exact": "x"}, "relation traversal is forbidden"),
            ({"name__regex": "x"}, "unsupported lookup"),
            ({"link_id__contains": "1"}, "lookup is not allowed"),
            ({"link_id__in": []}, "must be a non-empty array"),
            ({"link_id__in": list(range(501))}, "at most 500 items"),
            ({"link_id__isnull": "yes"}, "must be boolean"),
            ({"link_id": 1, "link_id__exact": 1}, "duplicate filter"),
        )
        for raw_filter, message in cases:
            with self.subTest(raw_filter=raw_filter), self.assertRaisesRegex(ValidationError, message):
                _normalize_filter(raw_filter, spec)

    def test_query_schema_bounds_filter_complexity_and_scalar_size(self):
        schema = FUNCTIONS["bklog.model.query"]["params_schema"]
        with self.assertRaisesRegex(ValidationError, "at most 50 properties"):
            validate_params(
                {"model": "log_search.LogIndexSet", "filter": {f"field-{index}": index for index in range(51)}},
                schema,
            )
        with self.assertRaisesRegex(ValidationError, "at most 4096 characters"):
            validate_params(
                {"model": "log_search.LogIndexSet", "filter": {"index_set_id": "x" * 4097}},
                schema,
            )
        with self.assertRaises(ValidationError):
            validate_params(
                {"model": "log_search.LogIndexSet", "filter": {"index_set_id": {"nested": "value"}}},
                schema,
            )

    def test_fixed_filter_is_appended_and_conflicts_are_rejected(self):
        spec = replace(SPECS["log_extract.ExtractLink"], fixed_filters={"link_type": "common"})
        self.assertEqual(_normalize_filter({}, spec)["link_type"], "common")
        self.assertEqual(_normalize_filter({"link_type": "common"}, spec)["link_type"], "common")
        for raw_filter in ({"link_type": "bk_repo"}, {"link_type__in": ["common"]}):
            with (
                self.subTest(raw_filter=raw_filter),
                self.assertRaisesRegex(ValidationError, "conflicts with fixed scope"),
            ):
                _normalize_filter(raw_filter, spec)

    def test_ordering_defaults_and_rejects_unbounded_or_unknown_fields(self):
        spec = SPECS["log_extract.ExtractLink"]
        self.assertEqual(_normalize_order_by(None, spec), list(spec.default_order_by))
        self.assertEqual(_normalize_order_by(["name", "-link_id"], spec), ["name", "-link_id"])
        self.assertEqual(_normalize_order_by([], spec), list(spec.default_order_by))
        cases = (
            ("name", "must be an array"),
            (["link_id"] * 6, "at most 5 fields"),
            ([""], "non-empty strings"),
            (["operator"], "outside the ModelSpec allowlist"),
        )
        for order_by, message in cases:
            with self.subTest(order_by=order_by), self.assertRaisesRegex(ValidationError, message):
                _normalize_order_by(order_by, spec)

    def test_recursive_masking_covers_nested_keys_json_strings_and_credential_urls(self):
        value = {
            "nested": {"apiKey": "secret", "safe": "ok"},
            "items": [{"token": "secret"}],
            "url": "https://user:pass@example.com/path",
            "message": "failed password=top-secret authorization: Bearer bearer-secret",
            "json": '{"password":"secret","name":"ok"}',
            "invalid_json": "{not-json api_key=api-secret",
        }

        masked = _mask_sensitive_tree(value)

        self.assertEqual(masked["nested"]["apiKey"], MASKED_VALUE)
        self.assertEqual(masked["items"][0]["token"], MASKED_VALUE)
        self.assertEqual(masked["url"], MASKED_VALUE)
        self.assertEqual(masked["message"], "failed password=*** authorization: ***")
        self.assertEqual(json_loads(masked["json"])["password"], MASKED_VALUE)
        self.assertEqual(masked["invalid_json"], "{not-json api_key=***")

    def test_global_config_row_masking_uses_raw_instance_key_even_if_not_selected(self):
        sensitive = _mask_global_config_row({"configs": {"safe": "value"}}, SimpleNamespace(config_id="API_TOKEN"))
        public = _mask_global_config_row({"configs": {"safe": "value"}}, SimpleNamespace(config_id="PUBLIC"))
        omitted = _mask_global_config_row({"config_id": "API_TOKEN"}, SimpleNamespace(config_id="API_TOKEN"))

        self.assertEqual(sensitive["configs"], MASKED_VALUE)
        self.assertEqual(public["configs"], {"safe": "value"})
        self.assertNotIn("configs", omitted)

    def test_instance_serialization_is_json_safe_and_one_bad_field_does_not_abort_row(self):
        class BadString:
            def __str__(self):
                raise RuntimeError("cannot stringify")

        class Row:
            good = {"token": "secret", "count": 1}
            bad = BadString()

            @property
            def unreadable(self):
                raise RuntimeError("cannot read")

        result = _serialize_instance(Row(), ("good", "bad", "unreadable"))

        self.assertEqual(result["good"]["token"], MASKED_VALUE)
        self.assertEqual(result["bad"], "<unserializable>")
        self.assertEqual(result["unreadable"], "<unserializable>")


def json_loads(value):
    import json

    return json.loads(value)


class ModelQueryScopeTest(TestCase):
    @staticmethod
    def create_space(bk_biz_id, tenant_id, *, deleted=False):
        space = Space.objects.create(
            space_uid=f"bkcc__{bk_biz_id}",
            bk_biz_id=bk_biz_id,
            space_type_id="bkcc",
            space_type_name="业务",
            space_id=str(bk_biz_id),
            space_name=f"biz-{bk_biz_id}",
            bk_tenant_id=tenant_id,
        )
        if deleted:
            Space.origin_objects.filter(pk=space.pk).update(is_deleted=True)
        return space

    def setUp(self):
        self.create_space(2, "tenant-1")
        self.create_space(4, "tenant-1", deleted=True)
        self.create_space(3, "tenant-2")

    @patch("apps.log_admin_resource.handlers.model_query.get_request_tenant_id", return_value="tenant-1")
    def test_tenant_scope_includes_soft_deleted_evidence_and_excludes_other_tenant(self, _mock_tenant):
        first_page = query_model(
            {
                "model": "log_search.Space",
                "fields": ["space_uid", "bk_tenant_id", "is_deleted"],
                "order_by": ["space_uid"],
                "limit": 1,
            }
        )
        all_rows = query_model(
            {
                "model": "log_search.Space",
                "fields": ["space_uid", "bk_tenant_id", "is_deleted"],
                "order_by": ["space_uid"],
                "limit": 10,
            }
        )

        self.assertTrue(first_page["has_more"])
        self.assertEqual(first_page["count"], 1)
        self.assertEqual({item["space_uid"] for item in all_rows["items"]}, {"bkcc__2", "bkcc__4"})
        self.assertTrue(any(item["is_deleted"] for item in all_rows["items"]))
        self.assertTrue(all(item["bk_tenant_id"] == "tenant-1" for item in all_rows["items"]))

    @patch("apps.log_admin_resource.handlers.model_query.get_request_tenant_id", return_value="tenant-1")
    def test_business_and_space_scopes_exclude_cross_tenant_rows(self, _mock_tenant):
        BizProperty.objects.create(bk_biz_id=0, biz_property_id="global", biz_property_name="global")
        BizProperty.objects.create(bk_biz_id=2, biz_property_id="mine", biz_property_name="mine")
        BizProperty.objects.create(bk_biz_id=3, biz_property_id="other", biz_property_name="other")
        LogIndexSet.objects.create(
            index_set_id=1001,
            index_set_name="mine",
            space_uid="bkcc__2",
            category_id="host",
            scenario_id=Scenario.LOG,
        )
        LogIndexSet.objects.create(
            index_set_id=1002,
            index_set_name="other",
            space_uid="bkcc__3",
            category_id="host",
            scenario_id=Scenario.LOG,
        )

        biz_result = query_model(
            {"model": "log_search.BizProperty", "fields": ["bk_biz_id", "biz_property_id"], "limit": 10}
        )
        index_result = query_model(
            {"model": "log_search.LogIndexSet", "fields": ["index_set_id", "space_uid"], "limit": 10}
        )

        self.assertEqual({item["bk_biz_id"] for item in biz_result["items"]}, {0, 2})
        self.assertEqual(index_result["items"], [{"index_set_id": 1001, "space_uid": "bkcc__2"}])

    @patch("apps.log_admin_resource.handlers.model_query.get_request_tenant_id", return_value="tenant-1")
    def test_indirect_scopes_exclude_cross_tenant_rows_through_owning_models(self, _mock_tenant):
        own_link = ExtractLink.objects.create(name="own-link", operator="operator", op_bk_biz_id=2)
        other_link = ExtractLink.objects.create(name="other-link", operator="operator", op_bk_biz_id=3)
        ExtractLinkHost.objects.create(target_dir="/own", bk_cloud_id=0, ip="127.0.0.1", link=own_link)
        ExtractLinkHost.objects.create(target_dir="/other", bk_cloud_id=0, ip="127.0.0.2", link=other_link)

        own_rule = BcsRule.objects.create(rule_name="own-rule", bcs_project_id="own-project")
        other_rule = BcsRule.objects.create(rule_name="other-rule", bcs_project_id="other-project")
        own_collector = CollectorConfig.objects.create(
            collector_config_name="own-collector",
            collector_config_name_en="own_collector",
            bk_biz_id=2,
            category_id="os",
            collector_scenario_id="row",
            custom_type="log",
            environment="linux",
            rule_id=own_rule.id,
        )
        other_collector = CollectorConfig.objects.create(
            collector_config_name="other-collector",
            collector_config_name_en="other_collector",
            bk_biz_id=3,
            category_id="os",
            collector_scenario_id="row",
            custom_type="log",
            environment="linux",
            rule_id=other_rule.id,
        )
        own_container = ContainerCollectorConfig.objects.create(
            collector_config_id=own_collector.collector_config_id,
            collector_type="container",
        )
        ContainerCollectorConfig.objects.create(
            collector_config_id=other_collector.collector_config_id,
            collector_type="container",
        )

        own_clustering = ClusteringConfig.objects.create(
            index_set_id=2001,
            model_id="own-model",
            min_members=1,
            max_dist_list="0.1",
            predefined_varibles="",
            delimeter="",
            max_log_length=1024,
            clustering_fields="log",
            bk_biz_id=2,
        )
        ClusteringConfig.objects.create(
            index_set_id=2002,
            model_id="other-model",
            min_members=1,
            max_dist_list="0.1",
            predefined_varibles="",
            delimeter="",
            max_log_length=1024,
            clustering_fields="log",
            bk_biz_id=3,
        )
        own_pattern = AiopsSignatureAndPattern.objects.create(
            model_id=own_clustering.model_id,
            signature="own-signature",
            pattern="own pattern",
        )
        AiopsSignatureAndPattern.objects.create(
            model_id="other-model",
            signature="other-signature",
            pattern="other pattern",
        )

        results = {
            "op_biz": query_model({"model": "log_extract.ExtractLink", "fields": ["link_id"], "order_by": ["link_id"]}),
            "link": query_model(
                {"model": "log_extract.ExtractLinkHost", "fields": ["link_id"], "order_by": ["link_id"]}
            ),
            "collector": query_model(
                {
                    "model": "log_databus.ContainerCollectorConfig",
                    "fields": ["id", "collector_config_id"],
                    "order_by": ["id"],
                }
            ),
            "rule": query_model({"model": "log_databus.BcsRule", "fields": ["id"], "order_by": ["id"]}),
            "model": query_model(
                {
                    "model": "log_clustering.AiopsSignatureAndPattern",
                    "fields": ["id", "model_id"],
                    "order_by": ["id"],
                }
            ),
        }

        self.assertEqual(results["op_biz"]["items"], [{"link_id": own_link.link_id}])
        self.assertEqual(results["link"]["items"], [{"link_id": own_link.link_id}])
        self.assertEqual(
            results["collector"]["items"],
            [{"id": own_container.id, "collector_config_id": own_collector.collector_config_id}],
        )
        self.assertEqual(results["rule"]["items"], [{"id": own_rule.id}])
        self.assertEqual(results["model"]["items"], [{"id": own_pattern.id, "model_id": "own-model"}])

    @patch("apps.log_admin_resource.handlers.model_query.get_request_tenant_id", return_value="tenant-1")
    def test_text_filter_default_order_and_has_more_are_bounded(self, _mock_tenant):
        for index in range(3):
            BizProperty.objects.create(
                bk_biz_id=2,
                biz_property_id=f"service-{index}",
                biz_property_name=f"service {index}",
            )

        result = query_model(
            {
                "model": "log_search.BizProperty",
                "filter": {"biz_property_name__contains": "service"},
                "fields": ["id", "biz_property_id"],
                "limit": 2,
            }
        )

        validate_params(result, FUNCTIONS["bklog.model.query"]["response_schema"], "response")
        self.assertEqual(result["count"], 2)
        self.assertTrue(result["has_more"])
        self.assertEqual(result["limit"], 2)
        self.assertNotIn("total", result)

    def test_global_config_uses_recursive_and_row_key_masking(self):
        GlobalConfig.objects.create(config_id="DB_PASSWORD", configs={"value": "top-secret"})
        GlobalConfig.objects.create(
            config_id="PUBLIC_CONFIG",
            configs={"nested": {"access_token": "secret", "endpoint": "https://user:pass@example.com/path"}},
        )

        result = query_model(
            {
                "model": "log_search.GlobalConfig",
                "fields": ["config_id", "configs"],
                "order_by": ["config_id"],
                "limit": 10,
            }
        )
        by_id = {item["config_id"]: item["configs"] for item in result["items"]}

        self.assertEqual(by_id["DB_PASSWORD"], MASKED_VALUE)
        self.assertEqual(by_id["PUBLIC_CONFIG"]["nested"]["access_token"], MASKED_VALUE)
        self.assertEqual(by_id["PUBLIC_CONFIG"]["nested"]["endpoint"], MASKED_VALUE)

    def test_feature_toggle_query_recursively_masks_persisted_json(self):
        FeatureToggle.objects.create(
            name="secret-feature",
            feature_config={
                "endpoint": "https://user:pass@example.com/path",
                "nested": {"access_token": "top-secret", "safe": "ok"},
            },
        )

        result = query_model(
            {
                "model": "feature_toggle.FeatureToggle",
                "filter": {"name": "secret-feature"},
                "fields": ["name", "feature_config"],
                "limit": 10,
            }
        )

        config = result["items"][0]["feature_config"]
        self.assertEqual(config["endpoint"], MASKED_VALUE)
        self.assertEqual(config["nested"]["access_token"], MASKED_VALUE)
        self.assertEqual(config["nested"]["safe"], "ok")

    @patch("apps.log_admin_resource.handlers.model_query.get_request_tenant_id", return_value="tenant-1")
    def test_extract_link_secret_fields_are_not_describable_or_queryable(self, _mock_tenant):
        ExtractLink.objects.create(
            name="safe-link",
            link_type="common",
            operator="operator",
            op_bk_biz_id=2,
            qcloud_secret_id="secret-id",
            qcloud_secret_key="secret-key",
            is_enable=True,
        )

        detail = get_model_spec_detail({"model": "log_extract.ExtractLink"})
        field_names = set(detail["allowed_fields"])
        self.assertNotIn("qcloud_secret_id", field_names)
        self.assertNotIn("qcloud_secret_key", field_names)
        with self.assertRaisesRegex(ValidationError, "sensitive field"):
            query_model(
                {
                    "model": "log_extract.ExtractLink",
                    "fields": ["link_id", "qcloud_secret_key"],
                    "limit": 10,
                }
            )

    @patch("apps.log_admin_resource.handlers.model_query.get_request_tenant_id", return_value="tenant-1")
    def test_query_empty_result_and_per_model_limit_are_explicit(self, _mock_tenant):
        empty = query_model(
            {
                "model": "log_search.BizProperty",
                "filter": {"biz_property_id": "does-not-exist"},
                "limit": 10,
            }
        )
        self.assertEqual(empty["items"], [])
        self.assertEqual(empty["count"], 0)
        self.assertFalse(empty["has_more"])

        with self.assertRaisesRegex(ValidationError, "at most 100"):
            query_model({"model": "feature_toggle.FeatureToggle", "limit": 101})

    @patch("apps.log_admin_resource.handlers.model_query.get_request_tenant_id", return_value="tenant-1")
    def test_query_rejects_filter_values_incompatible_with_model_field_types(self, _mock_tenant):
        with self.assertRaisesRegex(ValidationError, "filter values are incompatible"):
            query_model(
                {
                    "model": "log_extract.ExtractLink",
                    "filter": {"link_id": "not-an-integer"},
                    "fields": ["link_id"],
                    "limit": 10,
                }
            )

    def test_query_supports_a_model_spec_without_default_ordering(self):
        alias = "log_search.GlobalConfig"
        unordered = replace(SPECS[alias], default_order_by=())
        with patch.dict(SPECS, {alias: unordered}):
            result = query_model({"model": alias, "order_by": [], "limit": 10})

        self.assertEqual(result["model"], alias)

    @patch("apps.log_admin_resource.handlers.model_query.get_request_tenant_id", return_value="tenant-1")
    def test_all_scope_implementations_build_readonly_querysets(self, _mock_tenant):
        aliases = {
            "global": "log_search.GlobalConfig",
            "tenant": "log_search.Space",
            "space": "log_clustering.RegexTemplate",
            "biz": "log_search.BizProperty",
            "op_biz": "log_extract.ExtractLink",
            "index_set": "log_search.IndexSetFieldsConfig",
            "collector": "log_databus.ContainerCollectorConfig",
            "link": "log_extract.ExtractLinkHost",
            "rule": "log_databus.BcsRule",
            "model": "log_clustering.AiopsSignatureAndPattern",
        }
        for scope, alias in aliases.items():
            with self.subTest(scope=scope):
                spec, model = _resolve_model(alias)
                scoped = _apply_scope(getattr(model, spec.manager_name).all(), spec)
                self.assertEqual(spec.scope, scope)
                self.assertEqual(scoped.model, model)

    @patch("apps.log_admin_resource.handlers.model_query.get_request_tenant_id", return_value="")
    def test_scoped_model_requires_request_tenant(self, _mock_tenant):
        spec, model = _resolve_model("log_search.Space")
        with self.assertRaisesRegex(ValidationError, "request tenant is required"):
            _apply_scope(model.origin_objects.all(), spec)

    @patch("apps.log_admin_resource.handlers.model_query.get_request_tenant_id", return_value="tenant-1")
    def test_unknown_server_scope_fails_closed(self, _mock_tenant):
        spec, model = _resolve_model("log_search.Space")
        with self.assertRaisesRegex(RuntimeError, "unsupported ModelSpec scope"):
            _apply_scope(model.origin_objects.all(), replace(spec, scope="unknown"))


@override_settings(
    RESOURCE_CALL_APP_CODE_WHITE_LIST=[],
)
class ModelQueryRegistryTest(TestCase):
    def test_meta_exposes_list_detail_and_query_as_read_capabilities(self):
        result = AdminResourceRegistry.call("__meta__", {"action": "list"}, app_code="resource-reader")

        for name in ("bklog.model.list", "bklog.model.detail", "bklog.model.query"):
            self.assertIn(name, result["functions"])
        detail = AdminResourceRegistry.call(
            "__meta__", {"action": "detail", "target_func_name": "bklog.model.query"}, app_code="resource-reader"
        )
        self.assertEqual(detail["safety_level"], "read")
        self.assertEqual(detail["params_schema"]["properties"]["limit"]["maximum"], 500)

    @patch("apps.log_admin_resource.handlers.model_query.get_request_tenant_id", return_value="tenant-1")
    def test_registry_progressive_list_detail_query_uses_one_protocol(self, _mock_tenant):
        Space.objects.create(
            space_uid="bkcc__2",
            bk_biz_id=2,
            space_type_id="bkcc",
            space_type_name="业务",
            space_id="2",
            space_name="biz-2",
            bk_tenant_id="tenant-1",
        )

        listed = AdminResourceRegistry.call("bklog.model.list", {"domain": "log_search"}, app_code="resource-reader")
        detailed = AdminResourceRegistry.call(
            "bklog.model.detail", {"model": "log_search.Space"}, app_code="resource-reader"
        )
        queried = AdminResourceRegistry.call(
            "bklog.model.query",
            {"model": "log_search.Space", "fields": ["space_uid", "bk_tenant_id"], "limit": 10},
            app_code="resource-reader",
        )

        self.assertGreater(listed["count"], 0)
        self.assertEqual(detailed["model"], "log_search.Space")
        self.assertEqual(queried["items"], [{"space_uid": "bkcc__2", "bk_tenant_id": "tenant-1"}])

    def test_model_write_or_arbitrary_function_is_not_registered(self):
        with self.assertRaisesRegex(ValidationError, "unknown func_name"):
            AdminResourceRegistry.call("bklog.model.update", {}, app_code="resource-reader")
