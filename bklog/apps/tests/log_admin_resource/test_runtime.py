from django.test import SimpleTestCase, override_settings

from apps.exceptions import ValidationError
from apps.log_admin_resource.registry import FUNCTIONS, AdminResourceRegistry
from apps.log_admin_resource.schema import validate_params


FUNC_NAME = "bklog.runtime.version.snapshot"


class RuntimeVersionSnapshotTest(SimpleTestCase):
    @override_settings(APP_CODE="bk_log_search", VERSION="4.9.0-alpha.347")
    def test_returns_existing_runtime_settings(self):
        result = AdminResourceRegistry.call(FUNC_NAME, {}, app_code="resource-reader")

        self.assertEqual(
            result,
            {
                "app_code": "bk_log_search",
                "version": "4.9.0-alpha.347",
            },
        )
        validate_params(result, FUNCTIONS[FUNC_NAME]["response_schema"])

    @override_settings(APP_CODE=None, VERSION=None)
    def test_missing_values_are_returned_as_empty_strings(self):
        result = AdminResourceRegistry.call(FUNC_NAME, {}, app_code="resource-reader")

        self.assertEqual(result, {"app_code": "", "version": ""})

    def test_rejects_unknown_params(self):
        with self.assertRaisesRegex(ValidationError, "contains unsupported fields: git_commit"):
            AdminResourceRegistry.call(FUNC_NAME, {"git_commit": True}, app_code="resource-reader")

    def test_metadata_declares_read_only_version_contract(self):
        metadata = AdminResourceRegistry.call(
            "__meta__", {"action": "detail", "target_func_name": FUNC_NAME}, app_code="resource-reader"
        )

        self.assertEqual(metadata["safety_level"], "read")
        self.assertTrue(FUNCTIONS[FUNC_NAME]["validate_params"])
        self.assertEqual(metadata["params_schema"]["additionalProperties"], False)
        self.assertEqual(
            metadata["response_schema"]["required"],
            ["app_code", "version"],
        )
