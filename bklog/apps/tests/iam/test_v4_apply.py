from django.test import SimpleTestCase
from django.utils.functional import Promise

from apps.iam.backends.v4.apply import build_apply_data
from apps.iam.backends.v4.codec import BklogNameCodec
from apps.iam.handlers.actions import ActionEnum
from apps.iam.handlers.resources import ResourceEnum
from apps.iam.iam_engine.core.requests import ResourceInstance

SYSTEM_ID = "bk_log_search"
SYSTEM_NAME = "日志平台"


def build(action_resources):
    return build_apply_data(
        system_id=SYSTEM_ID,
        system_name=SYSTEM_NAME,
        codec=BklogNameCodec(),
        action_resources=action_resources,
    )


def make_resource(resource_type, resource_id, name=""):
    return ResourceInstance(
        system=resource_type.system_id,
        type=resource_type.id,
        id=resource_id,
        name=name,
    )


class BuildApplyDataTest(SimpleTestCase):
    def test_produces_the_v3_compatible_shape(self):
        resource = make_resource(ResourceEnum.INDICES, "20", name="索引集A")

        data = build([(ActionEnum.SEARCH_LOG, [resource])])

        self.assertEqual(data["system_id"], SYSTEM_ID)
        self.assertEqual(data["system_name"], SYSTEM_NAME)
        self.assertEqual(len(data["actions"]), 1)

        action = data["actions"][0]
        self.assertEqual(action["name"], ActionEnum.SEARCH_LOG.name)
        self.assertEqual(
            action["related_resource_types"],
            [
                {
                    "system_id": SYSTEM_ID,
                    "system_name": SYSTEM_NAME,
                    "type": "indices",
                    "type_name": ResourceEnum.INDICES.name,
                    "instances": [
                        [{"type": "indices", "type_name": ResourceEnum.INDICES.name, "id": "20", "name": "索引集A"}]
                    ],
                }
            ],
        )

    def test_action_id_uses_the_v4_encoding(self):
        data = build([(ActionEnum.SEARCH_LOG, [make_resource(ResourceEnum.INDICES, "20")])])

        # V4 模型不保留 V3 的 _v2 后缀，展示 id 必须与 apply_url 指向的申请单一致。
        self.assertEqual(ActionEnum.SEARCH_LOG.id, "search_log_v2")
        self.assertEqual(data["actions"][0]["id"], "search_log")

    def test_names_stay_lazy_for_the_rendering_layer(self):
        data = build([(ActionEnum.SEARCH_LOG, [make_resource(ResourceEnum.INDICES, "20")])])

        self.assertIsInstance(data["actions"][0]["name"], Promise)
        self.assertIsInstance(data["actions"][0]["related_resource_types"][0]["type_name"], Promise)

    def test_action_without_related_resource_types_reports_no_resource(self):
        data = build([(ActionEnum.MANAGE_GLOBAL_DESENSITIZE_RULE, [make_resource(ResourceEnum.INDICES, "20")])])

        self.assertEqual(data["actions"][0]["id"], "manage_global_desensitize_rule")
        self.assertEqual(data["actions"][0]["related_resource_types"], [])

    def test_resource_of_another_type_is_not_attached_to_the_action(self):
        data = build([(ActionEnum.SEARCH_LOG, [make_resource(ResourceEnum.COLLECTION, "1")])])

        self.assertEqual(data["actions"][0]["related_resource_types"], [])

    def test_multiple_instances_of_the_same_type_become_separate_chains(self):
        resources = [
            make_resource(ResourceEnum.INDICES, "20", name="A"),
            make_resource(ResourceEnum.INDICES, "21", name="B"),
        ]

        data = build([(ActionEnum.SEARCH_LOG, resources)])

        instances = data["actions"][0]["related_resource_types"][0]["instances"]
        self.assertEqual([chain[0]["id"] for chain in instances], ["20", "21"])
        self.assertEqual([len(chain) for chain in instances], [1, 1])

    def test_missing_instance_name_stays_empty_like_v3(self):
        data = build([(ActionEnum.SEARCH_LOG, [make_resource(ResourceEnum.INDICES, "20")])])

        self.assertEqual(data["actions"][0]["related_resource_types"][0]["instances"][0][0]["name"], "")

    def test_matches_the_paths_read_by_the_permission_dialog(self):
        """按 web/src/components/common/auth-dialog.vue updateData 的取数路径复算一遍。

        前端把结构读错时只会在控制台打一句日志、弹窗静默不出现，线上很难发现，只能靠这里锁住。
        """
        data = build([(ActionEnum.SEARCH_LOG, [make_resource(ResourceEnum.INDICES, "20", name="索引集A")])])

        rows = [
            {
                "system": data["system_name"],
                "permission": action["name"],
                "sources": [
                    f"{node['type_name']}：{node['name']}"
                    for resource_type in action["related_resource_types"]
                    for chain in resource_type["instances"]
                    for node in chain
                ],
            }
            for action in data["actions"]
        ]

        self.assertEqual(
            rows,
            [
                {
                    "system": SYSTEM_NAME,
                    "permission": ActionEnum.SEARCH_LOG.name,
                    "sources": [f"{ResourceEnum.INDICES.name}：索引集A"],
                }
            ],
        )

    def test_matches_the_paths_read_by_the_permission_page(self):
        """按 web/src/components/common/auth-container-page.vue getResource 的取数路径复算一遍。"""
        data = build([(ActionEnum.SEARCH_LOG, [make_resource(ResourceEnum.INDICES, "20", name="索引集A")])])

        related = data["actions"][0]["related_resource_types"]
        lines = [f"{node['type_name']}: [{node['id']}] {node['name']}" for node in related[0]["instances"][0]]

        self.assertEqual(lines, [f"{ResourceEnum.INDICES.name}: [20] 索引集A"])

    def test_every_action_keeps_its_own_resources(self):
        resources = [
            make_resource(ResourceEnum.BUSINESS, "10", name="空间A"),
            make_resource(ResourceEnum.INDICES, "20", name="索引集A"),
        ]

        data = build([(ActionEnum.VIEW_BUSINESS, resources), (ActionEnum.SEARCH_LOG, resources)])

        self.assertEqual([action["id"] for action in data["actions"]], ["view_business", "search_log"])
        self.assertEqual(
            [action["related_resource_types"][0]["instances"][0][0]["id"] for action in data["actions"]],
            ["10", "20"],
        )
