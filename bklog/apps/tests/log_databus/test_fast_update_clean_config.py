"""Fast Update 采集配置与清洗配置解耦测试。"""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.http import Http404
from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from apps.iam import ActionEnum
from apps.iam.handlers.drf import InstanceActionPermission
from apps.log_databus.handlers.collector.host import HostCollectorHandler
from apps.log_databus.handlers.collector.k8s import K8sCollectorHandler
from apps.log_databus.serializers import FastCollectorUpdateSerializer, FastContainerCollectorUpdateSerializer
from apps.log_databus.views.collector_views import CollectorViewSet


class FastUpdateSerializerTests(SimpleTestCase):
    def test_update_clean_config_defaults_to_true(self):
        for serializer_class in (FastCollectorUpdateSerializer, FastContainerCollectorUpdateSerializer):
            with self.subTest(serializer=serializer_class.__name__):
                serializer = serializer_class(data={})
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertIs(serializer.validated_data["update_clean_config"], True)

    def test_update_clean_config_accepts_false(self):
        for serializer_class in (FastCollectorUpdateSerializer, FastContainerCollectorUpdateSerializer):
            with self.subTest(serializer=serializer_class.__name__):
                serializer = serializer_class(data={"update_clean_config": False})
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertIs(serializer.validated_data["update_clean_config"], False)

    def test_host_update_does_not_inject_encoding_or_plugin_defaults(self):
        serializer = FastCollectorUpdateSerializer(data={"params": {"paths": ["/var/log/app.log"]}})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("data_encoding", serializer.validated_data)
        self.assertEqual(serializer.validated_data["params"], {"paths": ["/var/log/app.log"]})

    def test_host_update_accepts_partial_exclude_files(self):
        serializer = FastCollectorUpdateSerializer(data={"params": {"exclude_files": ["*.gz"]}})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["params"], {"exclude_files": ["*.gz"]})


class FastUpdateHandlerTests(SimpleTestCase):
    @staticmethod
    def build_host_handler():
        handler = HostCollectorHandler.__new__(HostCollectorHandler)
        handler.data = SimpleNamespace(
            is_active=True,
            bkdata_biz_id=None,
            bk_biz_id=2,
            collector_config_name_en="test_collector",
            collector_config_name="test collector",
            description="old description",
            target_object_type="HOST",
            target_node_type="INSTANCE",
            target_nodes=[{"bk_host_id": 1}],
            params={"paths": ["/var/log/old.log"], "tail_files": False},
            data_encoding="GBK",
            bk_data_id=None,
            bk_data_name="",
            index_set_id=None,
            etl_processor="bkbase",
            collector_scenario_id="row",
            collector_config_id=10,
            subscription_id=20,
            task_id_list=["30"],
            save=MagicMock(),
        )
        handler.build_bk_data_name = MagicMock(return_value="2_test_collector")
        handler._cat_illegal_ips = MagicMock()
        handler._update_or_create_subscription = MagicMock()
        handler.create_or_update_clean_config = MagicMock()
        handler.sync_scene_labels = MagicMock()
        return handler

    def test_host_fast_update_keeps_old_clean_behavior_by_default(self):
        handler = self.build_host_handler()
        with (
            patch("apps.log_databus.handlers.collector.host.transaction.atomic", return_value=nullcontext()),
            patch("apps.log_databus.handlers.collector.host.model_to_dict", return_value={}),
            patch("apps.log_databus.handlers.collector.host.user_operation_record.delay"),
        ):
            result = handler.fast_update({"is_allow_alone_data_id": False})

        handler.create_or_update_clean_config.assert_called_once()
        handler.sync_scene_labels.assert_not_called()
        self.assertEqual(result["subscription_id"], 20)
        self.assertEqual(result["task_id_list"], [])

    def test_host_fast_update_can_skip_clean_update(self):
        handler = self.build_host_handler()
        with (
            patch("apps.log_databus.handlers.collector.host.transaction.atomic", return_value=nullcontext()),
            patch("apps.log_databus.handlers.collector.host.model_to_dict", return_value={}),
            patch("apps.log_databus.handlers.collector.host.user_operation_record.delay"),
        ):
            result = handler.fast_update({"update_clean_config": False, "is_allow_alone_data_id": False})

        handler.create_or_update_clean_config.assert_not_called()
        # 场景化检索的路由标签与清洗配置无关，跳过清洗时仍需同步
        handler.sync_scene_labels.assert_called_once_with()
        self.assertEqual(result["collector_config_id"], 10)

    def test_host_fast_update_can_clear_description_and_targets(self):
        handler = self.build_host_handler()
        with (
            patch("apps.log_databus.handlers.collector.host.transaction.atomic", return_value=nullcontext()),
            patch("apps.log_databus.handlers.collector.host.model_to_dict", return_value={}),
            patch("apps.log_databus.handlers.collector.host.user_operation_record.delay"),
            patch("apps.log_databus.handlers.collector.host.CollectorScenario.get_instance", return_value=MagicMock()),
        ):
            handler.fast_update(
                {
                    "description": "",
                    "target_nodes": [],
                    "update_clean_config": False,
                    "is_allow_alone_data_id": False,
                }
            )

        self.assertEqual(handler.data.description, "")
        self.assertEqual(handler.data.target_nodes, [])
        handler._update_or_create_subscription.assert_called_once()

    def test_host_fast_update_persists_encoding_and_updates_subscription(self):
        handler = self.build_host_handler()
        with (
            patch("apps.log_databus.handlers.collector.host.transaction.atomic", return_value=nullcontext()),
            patch("apps.log_databus.handlers.collector.host.model_to_dict", return_value={}),
            patch("apps.log_databus.handlers.collector.host.user_operation_record.delay"),
            patch("apps.log_databus.handlers.collector.host.CollectorScenario.get_instance", return_value=MagicMock()),
        ):
            handler.fast_update(
                {
                    "data_encoding": "UTF-8",
                    "update_clean_config": False,
                    "is_allow_alone_data_id": False,
                }
            )

        self.assertEqual(handler.data.data_encoding, "UTF-8")
        subscription_params = handler._update_or_create_subscription.call_args.kwargs["params"]
        self.assertEqual(subscription_params["encoding"], "UTF-8")
        self.assertEqual(subscription_params["paths"], ["/var/log/old.log"])

    def test_host_fast_update_merges_partial_plugin_params(self):
        handler = self.build_host_handler()
        with (
            patch("apps.log_databus.handlers.collector.host.transaction.atomic", return_value=nullcontext()),
            patch("apps.log_databus.handlers.collector.host.model_to_dict", return_value={}),
            patch("apps.log_databus.handlers.collector.host.user_operation_record.delay"),
            patch("apps.log_databus.handlers.collector.host.CollectorScenario.get_instance", return_value=MagicMock()),
        ):
            handler.fast_update(
                {
                    "params": {"paths": ["/var/log/new.log"]},
                    "update_clean_config": False,
                    "is_allow_alone_data_id": False,
                }
            )

        self.assertEqual(
            handler.data.params,
            {"paths": ["/var/log/new.log"], "tail_files": False},
        )
        subscription_params = handler._update_or_create_subscription.call_args.kwargs["params"]
        self.assertEqual(subscription_params["encoding"], "GBK")
        self.assertIs(subscription_params["tail_files"], False)

    def test_host_fast_update_validates_partial_params_after_merge(self):
        handler = self.build_host_handler()
        handler.data.params = {"paths": []}

        with self.assertRaises(ValidationError):
            handler.fast_update(
                {
                    "params": {"exclude_files": ["*.gz"]},
                    "update_clean_config": False,
                    "is_allow_alone_data_id": False,
                }
            )

    def test_host_metadata_update_does_not_validate_targets_or_return_stale_tasks(self):
        handler = self.build_host_handler()
        with (
            patch("apps.log_databus.handlers.collector.host.transaction.atomic", return_value=nullcontext()),
            patch("apps.log_databus.handlers.collector.host.model_to_dict", return_value={}),
            patch("apps.log_databus.handlers.collector.host.user_operation_record.delay"),
        ):
            result = handler.fast_update(
                {
                    "description": "new description",
                    "update_clean_config": False,
                    "is_allow_alone_data_id": False,
                }
            )

        handler._cat_illegal_ips.assert_not_called()
        handler._update_or_create_subscription.assert_not_called()
        self.assertEqual(result["task_id_list"], [])

    def test_container_fast_update_keeps_old_clean_behavior_by_default(self):
        handler = K8sCollectorHandler.__new__(K8sCollectorHandler)
        handler.data = SimpleNamespace(
            is_active=True,
            collector_config_id=11,
            collector_config_name_en="container_collector",
            subscription_id=None,
            task_id_list=[31],
            yaml_config_enabled=False,
        )
        handler.update_container_config = MagicMock()
        handler.create_or_update_clean_config = MagicMock()
        handler.sync_scene_labels = MagicMock()

        result = handler.fast_update({})

        handler.create_or_update_clean_config.assert_called_once()
        handler.sync_scene_labels.assert_not_called()
        self.assertEqual(result["task_id_list"], [])

    def test_container_fast_update_can_skip_clean_update(self):
        handler = K8sCollectorHandler.__new__(K8sCollectorHandler)
        handler.data = SimpleNamespace(
            is_active=True,
            collector_config_id=11,
            collector_config_name_en="container_collector",
            subscription_id=None,
            task_id_list=[31],
            yaml_config_enabled=False,
        )
        handler.update_container_config = MagicMock()
        handler.create_or_update_clean_config = MagicMock()
        handler.sync_scene_labels = MagicMock()

        result = handler.fast_update({"update_clean_config": False})

        handler.create_or_update_clean_config.assert_not_called()
        handler.sync_scene_labels.assert_called_once_with()
        self.assertEqual(result["collector_config_id"], 11)
        self.assertEqual(result["task_id_list"], [])

    def test_container_yaml_only_update_returns_deployment_tasks(self):
        handler = K8sCollectorHandler.__new__(K8sCollectorHandler)
        handler.data = SimpleNamespace(
            is_active=True,
            collector_config_id=11,
            collector_config_name_en="container_collector",
            subscription_id=None,
            task_id_list=[31],
            yaml_config_enabled=True,
        )
        handler.update_container_config = MagicMock()
        handler.create_or_update_clean_config = MagicMock()
        handler.sync_scene_labels = MagicMock()

        result = handler.fast_update({"yaml_config": "encoded-yaml", "update_clean_config": False})

        handler.update_container_config.assert_called_once()
        self.assertEqual(result["task_id_list"], [31])

    def test_container_label_update_redeploys_existing_configs(self):
        handler = K8sCollectorHandler.__new__(K8sCollectorHandler)
        handler.collector_config_id = 11
        handler.data = SimpleNamespace(
            is_active=True,
            bk_biz_id=2,
            bcs_cluster_id="BCS-K8S-00000",
            collector_config_id=11,
            collector_config_name="container collector",
            index_set_id=None,
            bk_data_id=150011,
            yaml_config_enabled=False,
            add_pod_label=False,
            task_id_list=[],
            save=MagicMock(),
        )
        handler.create_container_release = MagicMock()
        container_config = SimpleNamespace(id=31)
        queryset = MagicMock()
        queryset.__iter__.return_value = iter([container_config])
        queryset.values_list.return_value = [31]

        with (
            patch(
                "apps.log_databus.handlers.collector.k8s.ContainerCollectorConfig.objects.filter",
                return_value=queryset,
            ),
            patch("apps.log_databus.handlers.collector.k8s.LogIndexSet.objects.filter") as mock_index_sets,
            patch("apps.log_databus.handlers.collector.k8s.model_to_dict", return_value={}),
            patch("apps.log_databus.handlers.collector.k8s.user_operation_record.delay"),
        ):
            mock_index_sets.return_value.first.return_value = None
            handler.update_container_config({"add_pod_label": True})

        handler.create_container_release.assert_called_once_with(container_config)
        self.assertEqual(handler.data.task_id_list, [31])

    @patch("apps.log_databus.tasks.collector.create_container_release.delay")
    @patch(
        "apps.log_databus.handlers.collector.k8s.CollectorScenario.get_edge_transport_output_params",
        return_value={},
    )
    @patch("apps.log_databus.handlers.collector.k8s.CollectorConfig.objects.get")
    def test_yaml_release_overlays_current_metadata(self, mock_get_collector, _mock_edge_params, mock_delay):
        mock_get_collector.return_value.data_link_id = None
        handler = K8sCollectorHandler.__new__(K8sCollectorHandler)
        handler.data = SimpleNamespace(
            yaml_config_enabled=True,
            bk_data_id=150011,
            extra_labels=[{"key": "env", "value": "prod"}],
            add_pod_label=True,
            add_pod_annotation=True,
            bcs_cluster_id="BCS-K8S-00000",
        )
        handler._generate_bklog_config_name = MagicMock(return_value="bklog-31")
        container_config = SimpleNamespace(
            id=31,
            collector_config_id=11,
            raw_config={
                "dataId": 1,
                "extMeta": {"stale": "value"},
                "addPodLabel": False,
                "addPodAnnotation": False,
            },
            params={},
            save=MagicMock(),
        )

        handler.create_container_release(container_config)

        request_params = mock_delay.call_args.kwargs["config_params"]
        self.assertEqual(request_params["dataId"], 150011)
        self.assertEqual(request_params["extMeta"], {"env": "prod"})
        self.assertIs(request_params["addPodLabel"], True)
        self.assertIs(request_params["addPodAnnotation"], True)

    @patch("apps.log_databus.tasks.collector.create_container_release.delay")
    @patch(
        "apps.log_databus.handlers.collector.k8s.CollectorScenario.get_edge_transport_output_params",
        return_value={},
    )
    @patch("apps.log_databus.handlers.collector.k8s.CollectorConfig.objects.get")
    def test_yaml_release_accepts_null_extra_labels(self, mock_get_collector, _mock_edge_params, mock_delay):
        mock_get_collector.return_value.data_link_id = None
        handler = K8sCollectorHandler.__new__(K8sCollectorHandler)
        handler.data = SimpleNamespace(
            yaml_config_enabled=True,
            bk_data_id=150011,
            extra_labels=None,
            add_pod_label=False,
            add_pod_annotation=False,
            bcs_cluster_id="BCS-K8S-00000",
        )
        handler._generate_bklog_config_name = MagicMock(return_value="bklog-31")
        container_config = SimpleNamespace(
            id=31,
            collector_config_id=11,
            raw_config={"extMeta": {"stale": "value"}},
            params={},
            save=MagicMock(),
        )

        handler.create_container_release(container_config)

        self.assertEqual(mock_delay.call_args.kwargs["config_params"]["extMeta"], {})

    @patch.object(K8sCollectorHandler, "container_config_to_raw_config", return_value={})
    def test_form_release_accepts_null_extra_labels(self, _mock_raw_config):
        collector = SimpleNamespace(
            bk_data_id=150011,
            extra_labels=None,
            add_pod_label=False,
            add_pod_annotation=False,
        )

        raw_config = K8sCollectorHandler.collector_container_config_to_raw_config(
            collector,
            SimpleNamespace(),
        )

        self.assertEqual(raw_config["extMeta"], {})


class FastUpdatePermissionTests(SimpleTestCase):
    @patch("apps.log_databus.views.collector_views.get_object_or_404")
    def test_update_context_returns_only_fast_update_metadata(self, mock_get_object):
        mock_get_object.return_value = SimpleNamespace(
            collector_config_id=11,
            bk_biz_id=2,
            environment="container",
            collector_scenario_id="row",
            yaml_config_enabled=True,
            subscription_id=None,
        )

        response = CollectorViewSet().update_context(SimpleNamespace(), collector_config_id=11)

        self.assertEqual(
            response.data,
            {
                "collector_config_id": 11,
                "bk_biz_id": 2,
                "environment": "container",
                "collector_scenario_id": "row",
                "yaml_config_enabled": True,
                "subscription_id": None,
            },
        )

    @patch("apps.log_databus.views.collector_views.get_object_or_404", side_effect=Http404)
    def test_update_context_returns_404_for_missing_collector(self, _mock_get_object):
        with self.assertRaises(Http404):
            CollectorViewSet().update_context(SimpleNamespace(), collector_config_id=999)

    @patch(
        "apps.log_databus.views.collector_views.Permission.get_auth_info",
        return_value={"bk_app_code": "__not_whitelisted__"},
    )
    def test_fast_update_requires_manage_collection(self, _mock_get_auth_info):
        view = CollectorViewSet()
        view.action = "fast_update"
        view.request = SimpleNamespace()

        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_COLLECTION])

    @patch(
        "apps.log_databus.views.collector_views.Permission.get_auth_info",
        return_value={"bk_app_code": "__trusted_app__"},
    )
    @patch("apps.log_databus.views.collector_views.settings.ESQUERY_WHITE_LIST", ["__trusted_app__"])
    def test_fast_update_can_force_permission_for_whitelisted_app(self, _mock_get_auth_info):
        view = CollectorViewSet()
        view.action = "fast_update"
        view.request = SimpleNamespace(query_params={}, data={"enforce_permission": True})

        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_COLLECTION])

    @patch(
        "apps.log_databus.views.collector_views.Permission.get_auth_info",
        return_value={"bk_app_code": "__not_whitelisted__"},
    )
    def test_update_context_requires_manage_collection(self, _mock_get_auth_info):
        view = CollectorViewSet()
        view.action = "update_context"
        view.request = SimpleNamespace(query_params={}, data={})

        permissions = view.get_permissions()

        self.assertEqual(len(permissions), 1)
        self.assertIsInstance(permissions[0], InstanceActionPermission)
        self.assertEqual(permissions[0].actions, [ActionEnum.MANAGE_COLLECTION])
