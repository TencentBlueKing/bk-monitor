"""容器采集配置 selector 默认值回归测试。

容器文件采集克隆新建点「下一步」报 3600500，detail 指向 match_labels：
create_container_config 用 config["label_selector"]["match_labels"] 直接下标取值
（apps/log_databus/handlers/collector/k8s.py:636-638），label_selector 里缺子键时
抛 KeyError 并被包装成 3600500。这里锁定这些字段的默认值。
"""

from django.test import SimpleTestCase

from apps.log_databus.serializers import ContainerConfigSerializer, default_label_selector

# create_container_config 对每个 config 直接下标取值的 selector 字段
SELECTOR_KEYS = (
    ("label_selector", "match_labels"),
    ("label_selector", "match_expressions"),
    ("annotation_selector", "match_annotations"),
)
MINIMAL_CONFIG = {"collector_type": "container_log_config", "params": {"paths": ["/data/log/app.log"]}}


class LabelSelectorDefaultTests(SimpleTestCase):
    def _validated(self, **overrides):
        slz = ContainerConfigSerializer(data={**MINIMAL_CONFIG, **overrides})
        self.assertTrue(slz.is_valid(), slz.errors)
        return slz.validated_data

    def assert_no_keyerror_on_create(self, data):
        for parent, child in SELECTOR_KEYS:
            self.assertIn(parent, data)
            self.assertIn(child, data[parent], f"{parent}.{child}")

    def test_clone_payload_without_match_labels(self):
        """复现单据场景：克隆带出了 label_selector，但其中没有 match_labels。"""
        data = self._validated(label_selector={"match_expressions": []})

        self.assert_no_keyerror_on_create(data)
        self.assertEqual(data["label_selector"]["match_labels"], [])

    def test_empty_selector_dicts(self):
        data = self._validated(label_selector={}, annotation_selector={})

        self.assert_no_keyerror_on_create(data)
        self.assertEqual(data["label_selector"], {"match_labels": [], "match_expressions": []})
        self.assertEqual(data["annotation_selector"], {"match_annotations": []})

    def test_selectors_omitted(self):
        data = self._validated()

        self.assert_no_keyerror_on_create(data)
        self.assertEqual(data["label_selector"], default_label_selector())

    def test_submitted_values_are_preserved(self):
        """验收标准：有传 match_labels 时行为与现网一致。"""
        data = self._validated(
            label_selector={"match_labels": [{"key": "app", "value": "billing"}]},
            annotation_selector={"match_annotations": [{"key": "team", "value": "log"}]},
        )

        self.assertEqual(data["label_selector"]["match_labels"], [{"key": "app", "operator": "=", "value": "billing"}])
        self.assertEqual(data["label_selector"]["match_expressions"], [])
        self.assertEqual(data["annotation_selector"]["match_annotations"][0]["key"], "team")

    def test_sibling_configs_do_not_share_defaults(self):
        """ListSerializer 为每个 item 复用同一个 child 实例，default 必须可调用。"""
        slz = ContainerConfigSerializer(data=[dict(MINIMAL_CONFIG), dict(MINIMAL_CONFIG)], many=True)
        self.assertTrue(slz.is_valid(), slz.errors)
        first, second = slz.validated_data

        self.assertIsNot(first["label_selector"], second["label_selector"])
        self.assertIsNot(first["label_selector"]["match_labels"], second["label_selector"]["match_labels"])

        first["label_selector"]["match_labels"].append({"key": "leaked"})
        self.assertEqual(second["label_selector"]["match_labels"], [])
