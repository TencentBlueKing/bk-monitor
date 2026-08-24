"""容器采集配置 Serializer 默认值回归测试。

apps/log_databus/handlers/collector/k8s.py 与 collector_views.py 对一批 required=False
的字段使用直接下标取值（如 config["label_selector"]["match_labels"]、config["container"]
["workload_type"]、data["extra_labels"]），缺省时会抛 KeyError 并被包装成 3600500。
这里锁定这些字段的默认值，同时锁定「更新语义不得注入默认值」这条相反的约束。
"""

from django.test import SimpleTestCase
from rest_framework.fields import empty

from apps.log_databus.serializers import (
    BcsContainerConfigSerializer,
    ContainerCollectorConfigToYamlSerializer,
    ContainerConfigSerializer,
    CreateContainerCollectorSerializer,
    FastContainerCollectorUpdateSerializer,
    UpdateContainerCollectorSerializer,
    default_annotation_selector,
    default_container,
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


class ExtraLabelsDefaultTests(SimpleTestCase):
    def test_to_yaml_serializer_fills_extra_labels(self):
        # collector_views.py container_configs_to_yaml 用 data["extra_labels"] 下标取值
        slz = ContainerCollectorConfigToYamlSerializer(data={"configs": [dict(MINIMAL_CONTAINER_CONFIG)]})
        self.assertTrue(slz.is_valid(), slz.errors)
        self.assertEqual(slz.validated_data["extra_labels"], [])

    def test_create_serializer_fills_extra_labels(self):
        # create_container_config 用 data["extra_labels"] 下标取值；
        # 这里断言字段契约而非整体校验，避免为无关必填字段拼装大段 payload。
        self.assertIs(CreateContainerCollectorSerializer().fields["extra_labels"].default, list)

    def test_fast_update_keeps_extra_labels_absent(self):
        slz = FastContainerCollectorUpdateSerializer(data={})
        self.assertTrue(slz.is_valid(), slz.errors)
        self.assertNotIn("extra_labels", slz.validated_data)

    def test_update_serializer_keeps_extra_labels_absent(self):
        # 更新链路靠 "field in data" 判断是否覆盖，设了 default 会把存量标签清空
        self.assertIs(UpdateContainerCollectorSerializer().fields["extra_labels"].default, empty)
