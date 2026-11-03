from django.test import SimpleTestCase

from apps.log_databus.handlers.collector.k8s import K8sCollectorHandler
from apps.log_databus.models import ContainerCollectorConfig


class K8sIgnoreOlderTests(SimpleTestCase):
    @staticmethod
    def make_config(**params):
        return ContainerCollectorConfig(
            collector_config_id=1,
            collector_type="container_log_config",
            namespaces=["app"],
            namespaces_exclude=[],
            any_namespace=False,
            data_encoding="UTF-8",
            params={
                "paths": ["/logs/app.log"],
                "conditions": {"type": "none"},
                **params,
            },
            workload_type="",
            workload_name="",
            container_name="",
            container_name_exclude="",
            match_labels=[],
            match_expressions=[],
            match_annotations=[],
            all_container=False,
        )

    def test_ignore_older_seconds_are_converted_to_duration(self):
        for seconds in (0, 86400):
            with self.subTest(seconds=seconds):
                raw_config = K8sCollectorHandler.container_config_to_raw_config(self.make_config(ignore_older=seconds))

                self.assertEqual(raw_config["ignoreOlder"], f"{seconds}s")

    def test_missing_ignore_older_keeps_legacy_config_unchanged(self):
        raw_config = K8sCollectorHandler.container_config_to_raw_config(self.make_config())

        self.assertNotIn("ignoreOlder", raw_config)
