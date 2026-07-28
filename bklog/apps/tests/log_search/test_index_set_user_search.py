from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.log_search.handlers.index_set import IndexSetHandler
from apps.log_search.models import LogIndexSet, Scenario, UserIndexSetSearchHistory


class TestFetchUserSearchIndexSet(TestCase):
    USERNAME = "admin"
    SPACE_UID = "bkcc__2"

    @staticmethod
    def _create_index_set(name: str, space_uid: str, is_active: bool = True) -> LogIndexSet:
        return LogIndexSet.objects.create(
            index_set_name=name,
            space_uid=space_uid,
            scenario_id=Scenario.LOG,
            is_active=is_active,
        )

    @classmethod
    def _create_history(
        cls,
        index_set_id: int,
        keyword: str,
        duration: float,
        created_at,
    ) -> UserIndexSetSearchHistory:
        history = UserIndexSetSearchHistory.objects.create(
            index_set_id=index_set_id,
            search_type="default",
            params={"keyword": keyword},
            duration=duration,
        )
        UserIndexSetSearchHistory.objects.filter(pk=history.pk).update(
            created_by=cls.USERNAME,
            created_at=created_at,
        )
        history.created_by = cls.USERNAME
        history.created_at = created_at
        return history

    def test_uses_two_queries_and_preserves_filter_order_and_limit(self):
        first_index_set = self._create_index_set("first", self.SPACE_UID)
        second_index_set = self._create_index_set("second", self.SPACE_UID)
        other_space_index_set = self._create_index_set("other-space", "bkcc__3")
        inactive_index_set = self._create_index_set("inactive", self.SPACE_UID, is_active=False)

        now = timezone.now()
        self._create_history(first_index_set.index_set_id, "first", 1.0, now)
        second_history = self._create_history(
            second_index_set.index_set_id,
            "second",
            2.0,
            now + timedelta(seconds=1),
        )
        self._create_history(
            other_space_index_set.index_set_id,
            "other-space",
            3.0,
            now + timedelta(seconds=2),
        )
        self._create_history(
            inactive_index_set.index_set_id,
            "inactive",
            4.0,
            now + timedelta(seconds=3),
        )

        with self.assertNumQueries(2):
            result = IndexSetHandler.fetch_user_search_index_set(
                {
                    "username": self.USERNAME,
                    "space_uid": self.SPACE_UID,
                    "limit": 1,
                }
            )

        self.assertEqual(
            result,
            [
                {
                    "index_set_id": second_index_set.index_set_id,
                    "created_at": second_history.created_at,
                    "params": {"keyword": "second"},
                    "duration": 2.0,
                    "index_set_name": second_index_set.index_set_name,
                    "space_uid": second_index_set.space_uid,
                }
            ],
        )
