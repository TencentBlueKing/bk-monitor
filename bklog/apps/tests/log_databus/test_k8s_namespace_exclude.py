"""容器采集候选的命名空间排除范围回归测试。"""

from itertools import permutations
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.log_databus.constants import TopoType, WorkLoadType
from apps.log_databus.exceptions import NodeNotAllowedException, VclusterNodeNotAllowedException
from apps.log_databus.handlers.collector.k8s import K8sCollectorHandler
from apps.log_databus.serializers import PreviewContainersSerializer
from apps.log_databus.views.collector_views import CollectorViewSet


class NamespaceExcludeTests(SimpleTestCase):
    def setUp(self):
        self.bcs = self.enterContext(patch("apps.log_databus.handlers.collector.k8s.Bcs")).return_value
        self.cluster_info = self.enterContext(
            patch.object(
                K8sCollectorHandler, "get_cluster_info", return_value={"is_shared": False, "is_virtual": False}
            )
        )
        self.allowed = self.enterContext(
            patch.object(
                K8sCollectorHandler,
                "list_namespace",
                return_value=[{"id": "app", "name": "app"}, {"id": "system", "name": "system"}],
            )
        )
        self.handler = K8sCollectorHandler()
        self.items = [
            {"metadata": {"namespace": "system", "name": "excluded"}},
            {"metadata": {"namespace": "app", "name": "included"}},
            {"metadata": {"namespace": "other", "name": "other"}},
        ]
        self.bcs.api_instance_core_v1.list_pod_for_all_namespaces.return_value.to_dict.return_value = {
            "items": self.items
        }
        self.bcs.api_instance_core_v1.list_namespaced_pod.return_value.to_dict.return_value = {"items": [self.items[1]]}
        self.workload_apis = [
            (WorkLoadType.DEPLOYMENT, self.bcs.api_instance_apps_v1, "deployment"),
            (WorkLoadType.STATEFUL_SET, self.bcs.api_instance_apps_v1, "stateful_set"),
            (WorkLoadType.JOB, self.bcs.api_instance_batch_v1, "job"),
            (WorkLoadType.DAEMON_SET, self.bcs.api_instance_apps_v1, "daemon_set"),
        ]
        for _, api, kind in self.workload_apis:
            getattr(api, f"list_{kind}_for_all_namespaces").return_value.to_dict.return_value = {"items": self.items}
            getattr(api, f"list_namespaced_{kind}").return_value.to_dict.return_value = {"items": [self.items[1]]}

    def workload(self, **kwargs):
        return self.handler.get_workload(
            workload_type=WorkLoadType.DEPLOYMENT, bcs_cluster_id="cluster", bk_biz_id=2, **kwargs
        )

    def topo(self, **kwargs):
        return self.handler.list_topo(topo_type=TopoType.POD.value, bk_biz_id=2, bcs_cluster_id="cluster", **kwargs)

    def test_exclude_uses_one_cluster_query_for_each_workload_type(self):
        for workload_type, api, kind in self.workload_apis:
            with self.subTest(workload_type=workload_type):
                self.assertEqual(
                    self.handler.get_workload(workload_type, "cluster", namespaces_exclude="system", bk_biz_id=2),
                    ["included", "other"],
                )
                getattr(api, f"list_{kind}_for_all_namespaces").assert_called_once_with()
                getattr(api, f"list_namespaced_{kind}").assert_not_called()

    def test_single_include_preserves_namespaced_query_for_each_workload_type(self):
        for workload_type, api, kind in self.workload_apis:
            with self.subTest(workload_type=workload_type):
                self.assertEqual(self.handler.get_workload(workload_type, "cluster", "app"), ["included"])
                getattr(api, f"list_namespaced_{kind}").assert_called_once_with(namespace="app")
                getattr(api, f"list_{kind}_for_all_namespaces").assert_not_called()

    def test_multiple_include_keeps_only_selected_namespaces(self):
        self.assertEqual(self.workload(namespace="system,app"), ["excluded", "included"])

    def test_empty_namespace_means_all_and_accepts_none(self):
        self.assertEqual(self.workload(namespace=None), ["excluded", "included", "other"])
        self.assertEqual(len(self.topo(namespace=None)["children"]), 3)

    def test_conflicting_scopes_are_rejected_before_resource_query(self):
        for call in [self.workload, self.topo]:
            with self.subTest(call=call.__name__):
                with self.assertRaisesMessage(ValidationError, "不能同时指定命名空间和排除指定空间"):
                    call(namespace="app", namespaces_exclude="system")
        self.bcs.api_instance_apps_v1.list_deployment_for_all_namespaces.assert_not_called()
        self.bcs.api_instance_core_v1.list_pod_for_all_namespaces.assert_not_called()

    def test_shared_workload_intersects_permissions_and_excludes(self):
        self.cluster_info.return_value["is_shared"] = True
        self.assertEqual(self.workload(namespaces_exclude="system"), ["included"])
        self.bcs.api_instance_apps_v1.list_deployment_for_all_namespaces.assert_called_once_with()
        self.bcs.api_instance_apps_v1.list_namespaced_deployment.assert_not_called()

    def test_shared_topo_intersects_permissions_and_excludes(self):
        self.cluster_info.return_value["is_shared"] = True
        self.assertEqual(
            self.topo(namespaces_exclude="system")["children"],
            [
                {
                    "id": "app",
                    "name": "app",
                    "type": "namespace",
                    "children": [{"id": "included", "name": "included", "type": "pod"}],
                },
            ],
        )
        self.bcs.api_instance_core_v1.list_pod_for_all_namespaces.assert_called_once_with()
        self.bcs.api_instance_core_v1.list_namespaced_pod.assert_not_called()

    def test_shared_empty_complement_never_falls_back_to_all(self):
        self.cluster_info.return_value["is_shared"] = True
        self.assertEqual(self.workload(namespaces_exclude="app,system"), [])
        self.assertEqual(self.topo(namespaces_exclude="app,system")["children"], [])
        self.bcs.api_instance_apps_v1.list_deployment_for_all_namespaces.assert_not_called()
        self.bcs.api_instance_core_v1.list_pod_for_all_namespaces.assert_not_called()

    def test_shared_no_authorized_namespace_is_empty(self):
        self.cluster_info.return_value["is_shared"] = True
        self.allowed.return_value = []
        self.assertEqual(self.workload(namespaces_exclude="system"), [])
        self.assertEqual(self.topo(namespaces_exclude="system")["children"], [])

    def test_topo_excludes_multiple_namespaces(self):
        self.assertEqual([item["id"] for item in self.topo(namespaces_exclude="system,other")["children"]], ["app"])

    def test_topo_include_keeps_namespaced_query(self):
        self.assertEqual([item["id"] for item in self.topo(namespace="app")["children"]], ["app"])
        self.bcs.api_instance_core_v1.list_namespaced_pod.assert_called_once_with(namespace="app")
        self.bcs.api_instance_core_v1.list_pod_for_all_namespaces.assert_not_called()

    def test_node_restrictions_still_apply_in_exclude_mode(self):
        for flag, exception in [
            ("is_shared", NodeNotAllowedException),
            ("is_virtual", VclusterNodeNotAllowedException),
        ]:
            with self.subTest(flag=flag):
                self.cluster_info.return_value = {"is_shared": False, "is_virtual": False, flag: True}
                with self.assertRaises(exception):
                    self.handler.list_topo(TopoType.NODE.value, 2, "cluster", namespaces_exclude="system")
        self.bcs.api_instance_core_v1.list_node.assert_not_called()

    def test_get_workload_view_passes_exclusion_and_business_to_handler(self):
        response = CollectorViewSet().get_workload(
            SimpleNamespace(
                GET={
                    "type": WorkLoadType.DEPLOYMENT,
                    "bcs_cluster_id": "cluster",
                    "bk_biz_id": "2",
                    "namespaces_exclude": "system",
                }
            )
        )
        self.assertEqual(response.data, ["included", "other"])
        self.cluster_info.assert_called_once_with("2", "cluster")

    def test_list_topo_view_passes_exclusion_to_handler(self):
        response = CollectorViewSet().list_topo(
            SimpleNamespace(
                GET={
                    "type": TopoType.POD.value,
                    "bcs_cluster_id": "cluster",
                    "bk_biz_id": "2",
                    "namespaces_exclude": "system,other",
                }
            )
        )
        self.assertEqual([item["id"] for item in response.data["children"]], ["app"])

    def test_unknown_workload_stays_empty(self):
        self.assertEqual(self.handler.get_workload("unknown", "cluster", namespaces_exclude="system", bk_biz_id=2), [])


class ContainerExcludePreviewTests(SimpleTestCase):
    def setUp(self):
        self.bcs = self.enterContext(patch("apps.log_databus.handlers.collector.k8s.Bcs")).return_value
        self.enterContext(
            patch.object(
                K8sCollectorHandler, "get_cluster_info", return_value={"is_shared": False, "is_virtual": False}
            )
        )
        self.handler = K8sCollectorHandler()

    @staticmethod
    def pod(name, container_names, namespace="app"):
        return SimpleNamespace(
            metadata=SimpleNamespace(namespace=namespace, name=name, owner_references=[]),
            spec=SimpleNamespace(containers=[SimpleNamespace(name=name) for name in container_names]),
        )

    def preview(self, pods, **scope):
        api = self.bcs.api_instance_core_v1
        api.list_namespaced_pod.return_value = SimpleNamespace(items=pods)
        api.list_pod_for_all_namespaces.return_value = SimpleNamespace(items=pods)
        serializer = PreviewContainersSerializer(
            data={
                "type": "pod",
                "bk_biz_id": 2,
                "bcs_cluster_id": "cluster",
                "container": {"container_name_exclude": "sidecar,agent"},
                **scope,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        data = dict(serializer.validated_data)
        data["topo_type"] = data.pop("type")
        return self.handler.preview_containers(**data)

    def test_container_exclusion_preserves_matches_in_every_pod_order(self):
        pods = [
            self.pod("excluded-sidecar", ["sidecar"]),
            self.pod("allowed-app", ["app"]),
            self.pod("excluded-agent", ["agent", "sidecar"]),
            self.pod("allowed-mixed", ["sidecar", "app"]),
        ]
        for ordered_pods in permutations(pods):
            with self.subTest(order=[pod.metadata.name for pod in ordered_pods]):
                result = self.preview(list(ordered_pods), namespaces=["app"])
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["group"], "namespace = app")
                self.assertEqual(result[0]["total"], 2)
                self.assertEqual(sorted(result[0]["items"]), ["allowed-app", "allowed-mixed"])

    def test_all_containers_excluded_returns_empty_preview(self):
        self.assertEqual(
            self.preview(
                [self.pod("sidecar-only", ["sidecar"]), self.pod("agent-only", ["agent"])],
                namespaces=["app"],
            ),
            [],
        )

    def test_namespace_and_container_exclusions_apply_together(self):
        result = self.preview(
            [
                self.pod("system-app", ["app"], namespace="system"),
                self.pod("sidecar-only", ["sidecar"]),
                self.pod("allowed-app", ["app"]),
            ],
            namespaces_exclude=["system"],
        )
        self.assertEqual(result, [{"group": "namespace = app", "total": 1, "items": ["allowed-app"]}])
        self.bcs.api_instance_core_v1.list_pod_for_all_namespaces.assert_called_once_with()
        self.bcs.api_instance_core_v1.list_namespaced_pod.assert_not_called()
