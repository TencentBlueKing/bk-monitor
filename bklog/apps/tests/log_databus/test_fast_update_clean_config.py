"""Fast Update 采集配置与清洗配置解耦测试。"""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.log_databus.handlers.collector.host import HostCollectorHandler
from apps.log_databus.handlers.collector.k8s import K8sCollectorHandler
from apps.log_databus.serializers import FastCollectorUpdateSerializer, FastContainerCollectorUpdateSerializer


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
        handler.create_or_update_clean_config = MagicMock()
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
        self.assertEqual(result["subscription_id"], 20)
        self.assertEqual(result["task_id_list"], ["30"])

    def test_host_fast_update_can_skip_clean_update(self):
        handler = self.build_host_handler()
        with (
            patch("apps.log_databus.handlers.collector.host.transaction.atomic", return_value=nullcontext()),
            patch("apps.log_databus.handlers.collector.host.model_to_dict", return_value={}),
            patch("apps.log_databus.handlers.collector.host.user_operation_record.delay"),
        ):
            result = handler.fast_update({"update_clean_config": False, "is_allow_alone_data_id": False})

        handler.create_or_update_clean_config.assert_not_called()
        self.assertEqual(result["collector_config_id"], 10)

    def test_container_fast_update_keeps_old_clean_behavior_by_default(self):
        handler = K8sCollectorHandler.__new__(K8sCollectorHandler)
        handler.data = SimpleNamespace(
            is_active=True,
            collector_config_id=11,
            collector_config_name_en="container_collector",
            subscription_id=None,
            task_id_list=[31],
        )
        handler.update_container_config = MagicMock()
        handler.create_or_update_clean_config = MagicMock()

        result = handler.fast_update({})

        handler.create_or_update_clean_config.assert_called_once()
        self.assertEqual(result["task_id_list"], [31])

    def test_container_fast_update_can_skip_clean_update(self):
        handler = K8sCollectorHandler.__new__(K8sCollectorHandler)
        handler.data = SimpleNamespace(
            is_active=True,
            collector_config_id=11,
            collector_config_name_en="container_collector",
            subscription_id=None,
            task_id_list=[31],
        )
        handler.update_container_config = MagicMock()
        handler.create_or_update_clean_config = MagicMock()

        result = handler.fast_update({"update_clean_config": False})

        handler.create_or_update_clean_config.assert_not_called()
        self.assertEqual(result["collector_config_id"], 11)
