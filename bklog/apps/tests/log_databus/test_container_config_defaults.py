"""容器采集配置 Serializer 默认值回归测试。

apps/log_databus/handlers/collector/k8s.py 与 collector_views.py 对一批 required=False
的字段使用直接下标取值（如 config["label_selector"]["match_labels"]、config["container"]
["workload_type"]、data["extra_labels"]），缺省时会抛 KeyError 并被包装成 3600500。
这里锁定这些字段的默认值，同时锁定「更新语义不得注入默认值」这条相反的约束。
"""

from django.test import SimpleTestCase
from rest_framework.fields import SkipField

from apps.log_databus.handlers.collector.k8s import K8sCollectorHandler
from apps.log_databus.models import ContainerCollectorConfig
from apps.log_databus.serializers import (
    BcsContainerConfigSerializer,
    ContainerCollectorConfigToYamlSerializer,
    ContainerConfigSerializer,
    CreateContainerCollectorSerializer,
    FastContainerCollectorUpdateSerializer,
    PartialContainerConfigSerializer,
    UpdateContainerCollectorSerializer,
    default_annotation_selector,
    default_container,
    default_container_config_fields,
    default_label_selector,
)

EMPTY_CONTAINER = {
    "workload_type": "",
    "workload_name": "",
    "container_name": "",
    "container_name_exclude": "",
}
MINIMAL_CONTAINER_CONFIG = {"collector_type": "container_log_config", "params": {}}


class DefaultFactoryTests(SimpleTestCase):
    def test_factories_return_fresh_objects(self):
        self.assertEqual(default_container(), EMPTY_CONTAINER)
        self.assertEqual(default_label_selector(), {"match_labels": [], "match_expressions": []})
        self.assertEqual(default_annotation_selector(), {"match_annotations": []})

        self.assertIsNot(default_container(), default_container())
        self.assertIsNot(default_label_selector(), default_label_selector())
        self.assertIsNot(default_annotation_selector(), default_annotation_selector())


class ContainerConfigSerializerDefaultTests(SimpleTestCase):
    """ContainerConfigSerializer 服务于 create / update / fast_* / to_yaml 四类入口。"""

    def _validated(self, **overrides):
        slz = ContainerConfigSerializer(data={**MINIMAL_CONTAINER_CONFIG, **overrides})
        self.assertTrue(slz.is_valid(), slz.errors)
        return slz.validated_data

    def test_omitted_optional_fields_are_filled(self):
        data = self._validated()

        self.assertEqual(data["container"], EMPTY_CONTAINER)
        self.assertEqual(data["label_selector"], {"match_labels": [], "match_expressions": []})
        self.assertEqual(data["annotation_selector"], {"match_annotations": []})
        self.assertEqual(data["paths"], [])
        self.assertEqual(data["data_encoding"], "UTF-8")
        self.assertEqual(data["namespaces"], [])
        self.assertEqual(data["namespaces_exclude"], [])

    def test_empty_nested_dict_fills_child_keys(self):
        data = self._validated(label_selector={}, annotation_selector={}, container={})

        self.assertEqual(data["label_selector"], {"match_labels": [], "match_expressions": []})
        self.assertEqual(data["annotation_selector"], {"match_annotations": []})
        self.assertEqual(data["container"], EMPTY_CONTAINER)

    def test_partial_label_selector_fills_sibling_key(self):
        data = self._validated(label_selector={"match_labels": [{"key": "app", "value": "x"}]})

        self.assertEqual(data["label_selector"]["match_expressions"], [])
        self.assertEqual(data["label_selector"]["match_labels"][0]["key"], "app")

    def test_explicitly_passed_values_win(self):
        data = self._validated(
            data_encoding="GBK",
            paths=["/log/a.log"],
            container={"workload_type": "Deployment", "workload_name": "app"},
        )

        self.assertEqual(data["data_encoding"], "GBK")
        self.assertEqual(data["paths"], ["/log/a.log"])
        self.assertEqual(data["container"]["workload_type"], "Deployment")


class BcsContainerConfigSerializerDefaultTests(SimpleTestCase):
    def test_omitted_optional_fields_are_filled(self):
        slz = BcsContainerConfigSerializer(data={})
        self.assertTrue(slz.is_valid(), slz.errors)
        data = slz.validated_data

        # create_bcs_container_config 以下标方式取 data_encoding / paths / namespaces
        self.assertEqual(data["data_encoding"], "UTF-8")
        self.assertEqual(data["paths"], [])
        self.assertEqual(data["namespaces"], [])
        self.assertEqual(data["container"], EMPTY_CONTAINER)
        self.assertEqual(data["label_selector"], {"match_labels": [], "match_expressions": []})
        self.assertEqual(data["annotation_selector"], {"match_annotations": []})


class MutableDefaultIsolationTests(SimpleTestCase):
    """ListSerializer 会为每个 item 复用同一个 child 实例，默认值必须是可调用的。"""

    def test_sibling_configs_do_not_share_default_objects(self):
        slz = ContainerCollectorConfigToYamlSerializer(
            data={"configs": [dict(MINIMAL_CONTAINER_CONFIG), dict(MINIMAL_CONTAINER_CONFIG)]}
        )
        self.assertTrue(slz.is_valid(), slz.errors)
        first, second = slz.validated_data["configs"]

        self.assertIsNot(first["container"], second["container"])
        self.assertIsNot(first["label_selector"], second["label_selector"])
        self.assertIsNot(first["label_selector"]["match_labels"], second["label_selector"]["match_labels"])
        self.assertIsNot(first["annotation_selector"], second["annotation_selector"])
        self.assertIsNot(first["paths"], second["paths"])

        first["label_selector"]["match_labels"].append({"key": "leaked"})
        self.assertEqual(second["label_selector"]["match_labels"], [])

    def test_plugin_param_defaults_are_isolated(self):
        """params 是 ContainerConfigSerializer 的子节点，同样受 child 复用影响。"""
        slz = ContainerCollectorConfigToYamlSerializer(
            data={"configs": [dict(MINIMAL_CONTAINER_CONFIG), dict(MINIMAL_CONTAINER_CONFIG)]}
        )
        self.assertTrue(slz.is_valid(), slz.errors)
        first, second = slz.validated_data["configs"]

        for field in ("exclude_files", "redis_hosts", "syslog_conditions", "kafka_hosts", "kafka_topics"):
            self.assertIsNot(first["params"][field], second["params"][field], field)

        first["params"]["exclude_files"].append("/leaked/from/config0.log")
        self.assertEqual(second["params"]["exclude_files"], [])


class PartialContainerConfigSerializerTests(SimpleTestCase):
    """更新语义：config 级字段不注入默认值，未提交的由 compare_config 沿用存量值。"""

    def test_omitted_config_level_fields_stay_absent(self):
        slz = PartialContainerConfigSerializer(data=MINIMAL_CONTAINER_CONFIG)
        self.assertTrue(slz.is_valid(), slz.errors)

        for field in PartialContainerConfigSerializer.PARTIAL_FIELDS:
            self.assertNotIn(field, slz.validated_data)

    def test_submitted_selector_still_fills_inner_keys(self):
        # 提交了 label_selector 即视为整体替换，缺失子键仍补 []，
        # 保住本 PR 最初要修的 config["label_selector"]["match_expressions"] KeyError
        slz = PartialContainerConfigSerializer(
            data={**MINIMAL_CONTAINER_CONFIG, "label_selector": {"match_labels": [{"key": "app", "value": "x"}]}}
        )
        self.assertTrue(slz.is_valid(), slz.errors)

        self.assertEqual(slz.validated_data["label_selector"]["match_expressions"], [])

    def test_parent_serializer_keeps_its_defaults(self):
        # 摘 default 发生在子类 get_fields()，不能回传污染创建语义
        slz = ContainerConfigSerializer(data=MINIMAL_CONTAINER_CONFIG)
        self.assertTrue(slz.is_valid(), slz.errors)

        self.assertEqual(slz.validated_data["container"], EMPTY_CONTAINER)
        self.assertEqual(slz.validated_data["data_encoding"], "UTF-8")


class MergeContainerConfigTests(SimpleTestCase):
    """compare_config 覆盖存量记录前的字段合并。"""

    @staticmethod
    def existed_config():
        return ContainerCollectorConfig(
            namespaces=["ns-a"],
            namespaces_exclude=[],
            workload_type="Deployment",
            workload_name="billing",
            container_name="app",
            container_name_exclude="",
            match_labels=[{"key": "env", "value": "prod"}],
            match_expressions=[],
            match_annotations=[],
            data_encoding="GBK",
            params={"paths": ["/data/app.log"]},
        )

    def test_omitted_fields_reuse_existed_values(self):
        submitted = {**MINIMAL_CONTAINER_CONFIG, "params": {"paths": ["/data/new.log"]}}
        merged = K8sCollectorHandler.merge_container_config(submitted, self.existed_config())

        self.assertEqual(merged["container"]["workload_type"], "Deployment")
        self.assertEqual(merged["container"]["workload_name"], "billing")
        self.assertEqual(merged["container"]["container_name"], "app")
        self.assertEqual(merged["label_selector"]["match_labels"], [{"key": "env", "value": "prod"}])
        self.assertEqual(merged["data_encoding"], "GBK")
        self.assertEqual(merged["namespaces"], ["ns-a"])
        self.assertEqual(merged["paths"], ["/data/app.log"])

    def test_omitted_container_does_not_widen_collect_scope(self):
        """回归：省略 container 曾把过滤条件清空、all_container 抬成 True。

        表达式与 compare_config 内的 is_all_container 保持一致。
        """
        submitted = dict(MINIMAL_CONTAINER_CONFIG)
        merged = K8sCollectorHandler.merge_container_config(submitted, self.existed_config())

        is_all_container = not any(
            [
                merged["container"]["workload_type"],
                merged["container"]["workload_name"],
                merged["container"]["container_name"],
                merged["container"]["container_name_exclude"],
                merged["label_selector"]["match_labels"],
                merged["label_selector"]["match_expressions"],
                merged["annotation_selector"]["match_annotations"],
            ]
        )
        self.assertFalse(is_all_container)

    def test_submitted_fields_win(self):
        submitted = {
            **MINIMAL_CONTAINER_CONFIG,
            "container": {
                "workload_type": "StatefulSet",
                "workload_name": "",
                "container_name": "",
                "container_name_exclude": "",
            },
            "data_encoding": "UTF-8",
            "namespaces": [],
        }
        merged = K8sCollectorHandler.merge_container_config(submitted, self.existed_config())

        self.assertEqual(merged["container"]["workload_type"], "StatefulSet")
        self.assertEqual(merged["container"]["workload_name"], "")
        self.assertEqual(merged["data_encoding"], "UTF-8")
        self.assertEqual(merged["namespaces"], [])

    def test_new_config_falls_back_to_empty_defaults(self):
        merged = K8sCollectorHandler.merge_container_config(dict(MINIMAL_CONTAINER_CONFIG), None)

        self.assertEqual(merged["container"], EMPTY_CONTAINER)
        self.assertEqual(merged["label_selector"], {"match_labels": [], "match_expressions": []})
        self.assertEqual(merged["annotation_selector"], {"match_annotations": []})
        self.assertEqual(merged["data_encoding"], "UTF-8")
        self.assertEqual(merged["namespaces"], [])
        self.assertEqual(merged["paths"], [])

    def test_full_payload_is_untouched(self):
        # 创建语义与 BCS 链路提交的是全字段，合并不得改动任何提交值
        submitted = {**MINIMAL_CONTAINER_CONFIG, **default_container_config_fields()}
        submitted["container"]["workload_type"] = "DaemonSet"
        submitted["namespaces"] = ["ns-b"]
        merged = K8sCollectorHandler.merge_container_config(submitted, self.existed_config())

        self.assertEqual(merged["container"]["workload_type"], "DaemonSet")
        self.assertEqual(merged["container"]["workload_name"], "")
        self.assertEqual(merged["data_encoding"], "UTF-8")
        self.assertEqual(merged["namespaces"], ["ns-b"])
        self.assertEqual(merged["paths"], [])


class ExtraLabelsDefaultTests(SimpleTestCase):
    def test_to_yaml_serializer_fills_extra_labels(self):
        # collector_views.py container_configs_to_yaml 用 data["extra_labels"] 下标取值
        slz = ContainerCollectorConfigToYamlSerializer(data={"configs": [dict(MINIMAL_CONTAINER_CONFIG)]})
        self.assertTrue(slz.is_valid(), slz.errors)
        self.assertEqual(slz.validated_data["extra_labels"], [])

    def test_create_serializer_fills_extra_labels(self):
        # create_container_config 用 data["extra_labels"] 下标取值。
        # 只跑该字段的取值逻辑，避免为无关必填字段拼装整个 payload。
        field = CreateContainerCollectorSerializer().fields["extra_labels"]

        self.assertEqual(field.get_default(), [])
        self.assertIsNot(field.get_default(), field.get_default())

    def test_fast_update_keeps_extra_labels_absent(self):
        slz = FastContainerCollectorUpdateSerializer(data={})
        self.assertTrue(slz.is_valid(), slz.errors)
        self.assertNotIn("extra_labels", slz.validated_data)

    def test_update_serializer_keeps_extra_labels_absent(self):
        # 更新链路靠 "field in data" 判断是否覆盖，注入默认值会把存量标签清空
        field = UpdateContainerCollectorSerializer().fields["extra_labels"]

        with self.assertRaises(SkipField):
            field.get_default()
