from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.iam.iam_engine.core.config import AuthMode, DualStackSpec
from apps.iam.iam_engine.migration.policy import ApplicationProviderNotConfiguredError, MigrationPolicy
from apps.iam.iam_engine.provider.bundle import ProviderBundle


class MigrationPolicyTest(SimpleTestCase):
    def setUp(self):
        self.v3_application = Mock(name="v3-application")
        self.v3_writer = Mock(name="v3-writer")
        self.v4_application = Mock(name="v4-application")
        self.v4_writer = Mock(name="v4-writer")
        self.bundles = {
            AuthMode.V3: ProviderBundle(application=self.v3_application, writer=self.v3_writer),
            AuthMode.V4: ProviderBundle(application=self.v4_application, writer=self.v4_writer),
        }

    def test_v4_mode_prefers_v4_application_provider(self):
        resolution = MigrationPolicy.resolve_application(AuthMode.V4, self.bundles)

        self.assertEqual(resolution.source_mode, AuthMode.V4)
        self.assertIs(resolution.provider, self.v4_application)

    def test_union_mode_prefers_v4_application_provider(self):
        resolution = MigrationPolicy.resolve_application(AuthMode.UNION, self.bundles)

        self.assertEqual(resolution.source_mode, AuthMode.V4)
        self.assertIs(resolution.provider, self.v4_application)

    def test_v3_mode_uses_v3_application_provider(self):
        resolution = MigrationPolicy.resolve_application(AuthMode.V3, self.bundles)

        self.assertEqual(resolution.source_mode, AuthMode.V3)
        self.assertIs(resolution.provider, self.v3_application)

    def test_missing_v4_application_falls_back_to_v3_for_union(self):
        bundles = {
            AuthMode.V3: ProviderBundle(application=self.v3_application, writer=self.v3_writer),
            AuthMode.V4: ProviderBundle(writer=self.v4_writer),
        }

        resolution = MigrationPolicy.resolve_application(AuthMode.UNION, bundles)

        self.assertEqual(resolution.source_mode, AuthMode.V3)
        self.assertIs(resolution.provider, self.v3_application)

    def test_missing_v4_bundle_falls_back_to_v3_for_union(self):
        bundles = {
            AuthMode.V3: ProviderBundle(application=self.v3_application, writer=self.v3_writer),
        }

        resolution = MigrationPolicy.resolve_application(AuthMode.UNION, bundles)

        self.assertEqual(resolution.source_mode, AuthMode.V3)
        self.assertIs(resolution.provider, self.v3_application)

    def test_missing_v4_bundle_falls_back_to_v3_for_v4_mode(self):
        bundles = {
            AuthMode.V3: ProviderBundle(application=self.v3_application, writer=self.v3_writer),
        }

        resolution = MigrationPolicy.resolve_application(AuthMode.V4, bundles)

        self.assertEqual(resolution.source_mode, AuthMode.V3)
        self.assertIs(resolution.provider, self.v3_application)

    def test_authorization_writers_include_v3_and_v4_when_configured(self):
        writers = MigrationPolicy.resolve_authorization_writers(self.bundles)

        self.assertEqual(
            writers,
            (
                (AuthMode.V3.value, self.v3_writer),
                (AuthMode.V4.value, self.v4_writer),
            ),
        )

    def test_authorization_writers_keep_v3_when_v4_writer_missing(self):
        bundles = {
            AuthMode.V3: ProviderBundle(application=self.v3_application, writer=self.v3_writer),
            AuthMode.V4: ProviderBundle(application=self.v4_application),
        }

        writers = MigrationPolicy.resolve_authorization_writers(bundles)

        self.assertEqual(writers, ((AuthMode.V3.value, self.v3_writer),))

    def test_raises_when_no_application_provider_configured(self):
        with self.assertRaises(ApplicationProviderNotConfiguredError):
            MigrationPolicy.resolve_application(AuthMode.V3, {})

    def test_swapped_stack_prefers_current_and_writes_legacy_first(self):
        stack = DualStackSpec(legacy=AuthMode.V4, current=AuthMode.V3)

        resolution = MigrationPolicy.resolve_application(AuthMode.UNION, self.bundles, stack=stack)
        writers = MigrationPolicy.resolve_authorization_writers(self.bundles, stack=stack)

        self.assertEqual(resolution.source_mode, AuthMode.V3)
        self.assertIs(resolution.provider, self.v3_application)
        self.assertEqual(
            writers,
            (
                (AuthMode.V4.value, self.v4_writer),
                (AuthMode.V3.value, self.v3_writer),
            ),
        )
