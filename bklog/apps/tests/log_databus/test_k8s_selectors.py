"""标签与注解在采集配置和 Pod/Node 预览中的一致性回归。"""

from copy import deepcopy
from unittest.mock import patch

from django.test import SimpleTestCase
from kubernetes import client

from apps.log_databus.handlers.collector.k8s import K8sCollectorHandler
from apps.log_databus.models import ContainerCollectorConfig
from apps.log_databus.serializers import PreviewContainersSerializer


class SelectorPreviewTests(SimpleTestCase):
    def setUp(self):
        self.bcs = self.enterContext(patch("apps.log_databus.handlers.collector.k8s.Bcs")).return_value
        self.cluster = self.enterContext(
            patch.object(K8sCollectorHandler, "get_cluster_info", return_value={"is_shared": False})
        )
        self.handler = K8sCollectorHandler()

    @staticmethod
    def resources(kind):
        items = []
        for name, annotations in [
            ("none", None),
            ("empty", {}),
            ("other", {"other": "x"}),
            ("web", {"tier": "web"}),
            ("system", {"tier": "system"}),
            ("api", {"tier": "api"}),
        ]:
            metadata = client.V1ObjectMeta(name=name, namespace="app", annotations=annotations)
            items.append(
                client.V1Node(metadata=metadata)
                if kind == "node"
                else client.V1Pod(metadata=metadata, spec=client.V1PodSpec(containers=[client.V1Container(name="app")]))
            )
        list_type = client.V1NodeList if kind == "node" else client.V1PodList
        return list_type(
            items=items,
            api_version="v1",
            kind="NodeList" if kind == "node" else "PodList",
            metadata=client.V1ListMeta(resource_version="123"),
        )

    def preview(self, kind, expressions, **kwargs):
        api = self.bcs.api_instance_core_v1
        resources = self.resources(kind)
        api.list_node.return_value = resources
        api.list_namespaced_pod.return_value = resources
        api.list_pod_for_all_namespaces.return_value = resources
        serializer = PreviewContainersSerializer(
            data={
                "type": kind,
                "bk_biz_id": 2,
                "bcs_cluster_id": "cluster",
                "annotation_selector": {"match_annotations": expressions},
                **kwargs,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        data = dict(serializer.validated_data)
        data["topo_type"] = data.pop("type")
        return [name for group in self.handler.preview_containers(**data) for name in group["items"]]

    def test_annotation_operators_match_missing_and_present_keys_on_pods_and_nodes(self):
        for kind in ["pod", "node"]:
            for operator, expected in [
                ("In", ["web"]),
                ("NotIn", ["none", "empty", "other", "system", "api"]),
                ("Exists", ["web", "system", "api"]),
                ("DoesNotExist", ["none", "empty", "other"]),
            ]:
                with self.subTest(kind=kind, operator=operator):
                    self.assertEqual(
                        self.preview(kind, [{"key": "tier", "operator": operator, "value": "(web)"}]), expected
                    )

    def test_annotation_values_trim_whitespace(self):
        for kind in ["pod", "node"]:
            for operator, expected in [("In", ["web", "system"]), ("NotIn", ["none", "empty", "other", "api"])]:
                with self.subTest(kind=kind, operator=operator):
                    self.assertEqual(
                        self.preview(kind, [{"key": "tier", "operator": operator, "value": "(web, system)"}]), expected
                    )

    def test_annotations_are_anded(self):
        for kind in ["pod", "node"]:
            with self.subTest(kind=kind):
                self.assertEqual(
                    self.preview(
                        kind,
                        [
                            {"key": "tier", "operator": "NotIn", "value": "(web, system)"},
                            {"key": "other", "operator": "DoesNotExist", "value": ""},
                        ],
                    ),
                    ["none", "empty", "api"],
                )

    def test_filter_preserves_kubernetes_list_type_metadata_and_input(self):
        for kind in ["pod", "node"]:
            with self.subTest(kind=kind):
                original = self.resources(kind)
                filtered = self.handler.filter_by_annotations(
                    original, [{"key": "tier", "operator": "DoesNotExist", "value": "stale"}]
                )
                self.assertIs(type(filtered), type(original))
                self.assertEqual(filtered.kind, original.kind)
                self.assertEqual(filtered.api_version, original.api_version)
                self.assertEqual(filtered.metadata.resource_version, "123")
                self.assertEqual(len(original.items), 6)
                self.assertEqual([item.metadata.name for item in filtered.items], ["none", "empty", "other"])

    def test_annotation_positive_namespace_still_uses_namespaced_query(self):
        self.assertEqual(
            self.preview("pod", [{"key": "tier", "operator": "NotIn", "value": "(system)"}], namespaces=["app"]),
            ["none", "empty", "other", "web", "api"],
        )
        self.bcs.api_instance_core_v1.list_namespaced_pod.assert_called_once_with(namespace="app")
        self.bcs.api_instance_core_v1.list_pod_for_all_namespaces.assert_not_called()

    def test_empty_annotation_selector_keeps_all_resources(self):
        for kind in ["pod", "node"]:
            with self.subTest(kind=kind):
                self.assertEqual(self.preview(kind, []), ["none", "empty", "other", "web", "system", "api"])

    def test_label_operators_still_use_kubernetes_selector_on_pods_and_nodes(self):
        for kind, api_name in [("pod", "list_namespaced_pod"), ("node", "list_node")]:
            for operator, expression in [
                ("In", "tier in (web,api)"),
                ("NotIn", "tier notin (web,api)"),
                ("Exists", "tier"),
                ("DoesNotExist", "!tier"),
            ]:
                with self.subTest(kind=kind, operator=operator):
                    api = getattr(self.bcs.api_instance_core_v1, api_name)
                    api.reset_mock()
                    self.assertEqual(
                        self.preview(
                            kind,
                            [{"key": "tier", "operator": "DoesNotExist", "value": ""}],
                            namespaces=["app"],
                            label_selector={
                                "match_expressions": [{"key": "tier", "operator": operator, "value": "(web,api)"}]
                            },
                        ),
                        ["none", "empty", "other"],
                    )
                    expected = {"label_selector": expression}
                    if kind == "pod":
                        expected["namespace"] = "app"
                    api.assert_called_once_with(**expected)

    def test_annotation_namespace_container_and_shared_scopes_intersect(self):
        resources = self.resources("pod")
        resources.items[0].metadata.namespace = "system"
        resources.items[1].spec.containers[0].name = "sidecar"
        resources.items[2].metadata.namespace = "unauthorized"
        self.bcs.api_instance_core_v1.list_pod_for_all_namespaces.return_value = resources
        self.cluster.return_value = {"is_shared": True}
        with patch.object(
            K8sCollectorHandler, "_get_shared_cluster_namespace", return_value=[{"name": "app"}, {"name": "system"}]
        ):
            result = self.handler.preview_containers(
                "pod",
                2,
                "cluster",
                namespaces_exclude=["system"],
                annotation_selector={"match_annotations": [{"key": "tier", "operator": "NotIn", "value": "(system)"}]},
                container={"container_name_exclude": "sidecar"},
            )
        self.assertEqual(result, [{"group": "namespace = app", "total": 2, "items": ["web", "api"]}])


class RawSelectorTests(SimpleTestCase):
    def test_raw_label_and_annotation_unary_operators_never_emit_stale_values(self):
        for operator, expected in [
            ("In", ["web", "api"]),
            ("NotIn", ["web", "api"]),
            ("Exists", []),
            ("DoesNotExist", []),
        ]:
            with self.subTest(operator=operator):
                expression = {"key": "tier", "operator": operator, "value": "web, api"}
                original = deepcopy(expression)
                config = ContainerCollectorConfig(
                    collector_config_id=1,
                    collector_type="container_log_config",
                    namespaces=["app"],
                    any_namespace=False,
                    data_encoding="UTF-8",
                    params={
                        "paths": ["/logs/app.log"],
                        "conditions": {"type": "match", "match_type": "include", "match_content": ""},
                    },
                    workload_type="",
                    workload_name="",
                    container_name="",
                    match_labels=[],
                    match_expressions=[expression],
                    match_annotations=[expression],
                    all_container=False,
                )
                raw = K8sCollectorHandler.container_config_to_raw_config(config)
                for field in ["labelSelector", "annotationSelector"]:
                    self.assertEqual(
                        raw[field]["matchExpressions"], [{"key": "tier", "operator": operator, "values": expected}]
                    )
                self.assertEqual(expression, original)
                self.assertEqual(raw["namespaceSelector"]["matchNames"], ["app"])
