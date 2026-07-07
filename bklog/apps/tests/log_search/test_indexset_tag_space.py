from django.test import TestCase

from apps.log_search.constants import TagColor
from apps.log_search.exceptions import IndexSetTagNameExistException, IndexSetTagNotExistException
from apps.log_search.handlers.index_set import IndexSetHandler
from apps.log_search.models import IndexSetTag, LogIndexSet, Scenario
from apps.log_search.serializers import CreateIndexSetTagSerializer, IndexSetTagListSerializer


class TestIndexSetTagSpace(TestCase):
    def test_user_tag_can_use_same_name_in_different_spaces(self):
        space_a = "bkcc__2"
        space_b = "bkcc__3"

        tag_a = IndexSetHandler.create_tag({"space_uid": space_a, "name": "shared-name", "color": TagColor.GREEN.value})
        tag_b = IndexSetHandler.create_tag({"space_uid": space_b, "name": "shared-name", "color": TagColor.BLUE.value})

        self.assertNotEqual(tag_a["tag_id"], tag_b["tag_id"])
        self.assertEqual(tag_a["space_uid"], space_a)
        self.assertEqual(tag_b["space_uid"], space_b)

    def test_user_tag_name_conflicts_with_global_tag_in_space(self):
        IndexSetTag.objects.create(name="legacy-global", color=TagColor.GREEN.value)

        with self.assertRaises(IndexSetTagNameExistException):
            IndexSetHandler.create_tag({"space_uid": "bkcc__2", "name": "legacy-global", "color": TagColor.BLUE.value})

    def test_user_tag_name_conflicts_in_same_space(self):
        IndexSetTag.objects.create(space_uid="bkcc__2", name="space-tag", color=TagColor.GREEN.value)

        with self.assertRaises(IndexSetTagNameExistException):
            IndexSetHandler.create_tag({"space_uid": "bkcc__2", "name": "space-tag", "color": TagColor.BLUE.value})

    def test_create_tag_serializer_allows_empty_space_uid(self):
        serializer = CreateIndexSetTagSerializer(data={"name": "global-tag", "color": TagColor.GREEN.value})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["space_uid"], "")

    def test_tag_list_serializer_allows_empty_space_uid(self):
        serializer = IndexSetTagListSerializer(data={})

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["space_uid"], "")

    def test_tag_list_returns_global_and_current_space_tags(self):
        global_tag = IndexSetTag.objects.create(name="legacy-global", color=TagColor.GREEN.value)
        space_tag = IndexSetTag.objects.create(space_uid="bkcc__2", name="space-tag", color=TagColor.BLUE.value)
        other_space_tag = IndexSetTag.objects.create(
            space_uid="bkcc__3", name="other-space-tag", color=TagColor.RED.value
        )

        tag_ids = {tag["tag_id"] for tag in IndexSetHandler.tag_list(space_uid="bkcc__2")}

        self.assertIn(global_tag.tag_id, tag_ids)
        self.assertIn(space_tag.tag_id, tag_ids)
        self.assertNotIn(other_space_tag.tag_id, tag_ids)

    def test_add_tag_rejects_other_space_user_tag(self):
        index_set = LogIndexSet.objects.create(
            index_set_name="test-index-set",
            space_uid="bkcc__2",
            scenario_id=Scenario.ES,
        )
        other_space_tag = IndexSetTag.objects.create(
            space_uid="bkcc__3", name="other-space-tag", color=TagColor.RED.value
        )

        with self.assertRaises(IndexSetTagNotExistException):
            IndexSetHandler(index_set.index_set_id).add_tag(other_space_tag.tag_id)
