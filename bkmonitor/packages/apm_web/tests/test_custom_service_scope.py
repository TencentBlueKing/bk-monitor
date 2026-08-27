from unittest import mock

import pytest

from apm_web.constants import CustomServiceMatchType, CustomServiceType
from apm_web.meta.resources import CustomServiceConfigResource, DeleteCustomSeriviceResource
from apm_web.models import ApplicationCustomService


pytestmark = pytest.mark.django_db


def create_custom_service(bk_biz_id=3, app_name="demo", name="victim"):
    return ApplicationCustomService.objects.create(
        bk_biz_id=bk_biz_id,
        app_name=app_name,
        name=name,
        type=CustomServiceType.HTTP,
        match_type=CustomServiceMatchType.MANUAL,
        rule={},
    )


def test_delete_requires_bk_biz_id():
    assert not DeleteCustomSeriviceResource.RequestSerializer(data={"id": 1}).is_valid()


@mock.patch("apm_web.tasks.update_application_config.delay")
def test_delete_does_not_touch_another_business(_delay_mock):
    victim = create_custom_service()

    with pytest.raises(ValueError):
        DeleteCustomSeriviceResource().perform_request({"id": victim.id, "bk_biz_id": 2})

    assert ApplicationCustomService.objects.filter(id=victim.id).exists()


@mock.patch("apm_web.tasks.update_application_config.delay")
def test_update_does_not_touch_another_business(_delay_mock):
    victim = create_custom_service()

    with pytest.raises(ValueError):
        CustomServiceConfigResource().perform_request(
            {
                "id": victim.id,
                "bk_biz_id": 2,
                "app_name": "demo",
                "name": "hijacked",
                "type": CustomServiceType.HTTP,
                "match_type": CustomServiceMatchType.MANUAL,
                "rule": {},
            }
        )

    victim.refresh_from_db()
    assert victim.bk_biz_id == 3
    assert victim.name == "victim"
