import pytest

from bkmonitor.models import DutyArrange, UserGroup
from monitor_web.data_migrate.data_export import _iter_fetcher_objects
from monitor_web.data_migrate.fetcher.strategy import get_strategy_fetcher

pytestmark = pytest.mark.django_db


def test_get_strategy_fetcher_exports_duty_arrange_bound_to_user_group():
    target_group = UserGroup.objects.create(name="target_group", bk_biz_id=2, desc="")
    target_arrange = DutyArrange.objects.create(
        user_group_id=target_group.id,
        users=[{"id": "admin", "type": "user"}],
    )
    other_group = UserGroup.objects.create(name="other_group", bk_biz_id=3, desc="")
    other_arrange = DutyArrange.objects.create(
        user_group_id=other_group.id,
        users=[{"id": "other", "type": "user"}],
    )

    export_objects = list(_iter_fetcher_objects(get_strategy_fetcher(2)))

    exported_duty_arrange_ids = {instance.id for instance in export_objects if isinstance(instance, DutyArrange)}
    assert target_arrange.id in exported_duty_arrange_ids
    assert other_arrange.id not in exported_duty_arrange_ids
