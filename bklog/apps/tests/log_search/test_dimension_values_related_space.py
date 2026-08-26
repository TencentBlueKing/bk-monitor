# -*- coding: utf-8 -*-
"""CI coverage for dimension_values related-space scene tags.

GitHub unittest.yml runs `python manage.py test apps.tests` only.
The scene-search suite under apps/log_search/tests is not in that path.
"""

from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.log_search.models import IndexSetTag, LogIndexSet
from apps.log_search.views.scene_search_views import SceneSearchViewSet


def _get_viewset(action_name, request):
    from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
    from rest_framework.request import Request

    vs = SceneSearchViewSet(format_kwarg=None)
    if not isinstance(request, Request):
        request = Request(request, parsers=[JSONParser(), FormParser(), MultiPartParser()])
    vs.request = request
    vs.kwargs = {}
    vs.action = action_name
    return vs


class TestDimensionValuesRelatedSpace(TestCase):
    def test_omitted_space_uids_only_scans_current_biz(self):
        scene_tag = IndexSetTag.get_tag_id(name="scene", value="k8s", tag_type="scene")
        biz_tag = IndexSetTag.get_tag_id(name="cluster_id", value="BCS-BIZ-CI-001", tag_type="scene")
        related_tag = IndexSetTag.get_tag_id(name="cluster_id", value="BCS-RELATED-CI-001", tag_type="scene")

        LogIndexSet.objects.create(
            index_set_name="idx_biz_ci",
            space_uid="bkcc__2",
            scenario_id="log",
            tag_ids=[str(scene_tag), str(biz_tag)],
            is_active=True,
        )
        LogIndexSet.objects.create(
            index_set_name="idx_related_ci",
            space_uid="bcs__BCS-K8S-001",
            scenario_id="log",
            tag_ids=[str(scene_tag), str(related_tag)],
            is_active=True,
        )

        values = IndexSetTag.get_dimension_values(bk_biz_id=2, scene="k8s", dimension_key="cluster_id")
        self.assertEqual(set(values), {"BCS-BIZ-CI-001"})

    def test_space_uids_include_related_and_exclude_unlisted(self):
        scene_tag = IndexSetTag.get_tag_id(name="scene", value="k8s", tag_type="scene")
        biz_tag = IndexSetTag.get_tag_id(name="cluster_id", value="BCS-BIZ-CI-002", tag_type="scene")
        related_tag = IndexSetTag.get_tag_id(name="cluster_id", value="BCS-RELATED-CI-002", tag_type="scene")
        other_tag = IndexSetTag.get_tag_id(name="cluster_id", value="BCS-OTHER-CI-002", tag_type="scene")

        LogIndexSet.objects.create(
            index_set_name="idx_biz_ci2",
            space_uid="bkcc__2",
            scenario_id="log",
            tag_ids=[str(scene_tag), str(biz_tag)],
            is_active=True,
        )
        LogIndexSet.objects.create(
            index_set_name="idx_related_ci2",
            space_uid="bcs__BCS-K8S-001",
            scenario_id="log",
            tag_ids=[str(scene_tag), str(related_tag)],
            is_active=True,
        )
        LogIndexSet.objects.create(
            index_set_name="idx_other_ci2",
            space_uid="bcs__BCS-K8S-999",
            scenario_id="log",
            tag_ids=[str(scene_tag), str(other_tag)],
            is_active=True,
        )

        values = IndexSetTag.get_dimension_values(
            bk_biz_id=2,
            scene="k8s",
            dimension_key="cluster_id",
            space_uids=["bkcc__2", "bcs__BCS-K8S-001"],
        )
        self.assertEqual(set(values), {"BCS-BIZ-CI-002", "BCS-RELATED-CI-002"})
        self.assertNotIn("BCS-OTHER-CI-002", values)

    def test_filters_apply_across_related_space_union(self):
        scene_tag = IndexSetTag.get_tag_id(name="scene", value="k8s", tag_type="scene")
        stdout_tag = IndexSetTag.get_tag_id(name="stream", value="stdout", tag_type="scene")
        file_tag = IndexSetTag.get_tag_id(name="stream", value="file", tag_type="scene")
        c1 = IndexSetTag.get_tag_id(name="cluster_id", value="BCS-STDOUT-CI-001", tag_type="scene")
        c2 = IndexSetTag.get_tag_id(name="cluster_id", value="BCS-FILE-CI-001", tag_type="scene")

        LogIndexSet.objects.create(
            index_set_name="related_stdout_ci",
            space_uid="bcs__BCS-K8S-001",
            scenario_id="log",
            tag_ids=[str(scene_tag), str(stdout_tag), str(c1)],
            is_active=True,
        )
        LogIndexSet.objects.create(
            index_set_name="related_file_ci",
            space_uid="bcs__BCS-K8S-001",
            scenario_id="log",
            tag_ids=[str(scene_tag), str(file_tag), str(c2)],
            is_active=True,
        )

        values = IndexSetTag.get_dimension_values(
            bk_biz_id=2,
            scene="k8s",
            dimension_key="cluster_id",
            filters=[{"field_name": "stream", "value": ["stdout"], "op": "eq"}],
            space_uids=["bkcc__2", "bcs__BCS-K8S-001"],
        )
        self.assertEqual(set(values), {"BCS-STDOUT-CI-001"})

    def test_none_space_uids_uses_exact_space_uid_in_not_suffix(self):
        with patch("apps.log_search.models.bk_biz_id_to_space_uid", return_value="bkcc__2") as m_space, patch.object(
            IndexSetTag, "get_tag_id", return_value=1
        ), patch.object(IndexSetTag, "_normalize_dimension_filters", return_value=[]), patch(
            "apps.log_search.models.LogIndexSet"
        ) as m_idx:
            m_idx.objects.filter.return_value.values_list.return_value = []
            result = IndexSetTag.get_dimension_values(bk_biz_id=2, scene="host", dimension_key="cluster_id")
            m_space.assert_called_once_with(2)
            m_idx.objects.filter.assert_called_once_with(space_uid__in=["bkcc__2"], is_active=True)
        self.assertEqual(result, [])


@override_settings(PRE_SEARCH_SECONDS=60, TIME_ZONE="UTC")
class TestDimensionValuesViewRelatedSpace(TestCase):
    @patch("apps.log_search.views.scene_search_views.IndexSetHandler.get_all_related_space_uids")
    @patch("apps.log_search.models.IndexSetTag.get_dimension_values")
    def test_view_passes_related_space_uids(self, mock_dv, mock_related):
        mock_dv.return_value = ["BCS-K8S-001"]
        mock_related.return_value = ["bkcc__2", "bcs__BCS-K8S-001"]

        factory = APIRequestFactory()
        request = factory.post(
            "/api/v1/search/scene/dimension_values/",
            data={"bk_biz_id": 2, "scene": "k8s", "dimension_key": "cluster_id"},
            format="json",
        )
        vs = _get_viewset("dimension_values", request)
        response = vs.dimension_values(request)

        self.assertEqual(response.status_code, 200)
        mock_related.assert_called_once_with("bkcc__2")
        mock_dv.assert_called_once_with(
            bk_biz_id=2,
            scene="k8s",
            dimension_key="cluster_id",
            filters=None,
            space_uids=["bkcc__2", "bcs__BCS-K8S-001"],
        )
