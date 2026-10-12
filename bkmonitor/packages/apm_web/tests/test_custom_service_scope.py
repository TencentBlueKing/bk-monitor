"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2026 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from apm_web.constants import CustomServiceMatchType, CustomServiceType
from apm_web.meta.resources import CustomServiceConfigResource, DeleteCustomSeriviceResource
from apm_web.models import ApplicationCustomService

pytestmark = pytest.mark.django_db

BK_BIZ_ID = 2
OTHER_BK_BIZ_ID = 3
APP_NAME = "demo"


def create_custom_service(bk_biz_id=OTHER_BK_BIZ_ID, app_name=APP_NAME, name="victim"):
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


def test_delete_does_not_touch_another_business():
    victim = create_custom_service()

    with pytest.raises(ValueError):
        DeleteCustomSeriviceResource().perform_request({"id": victim.id, "bk_biz_id": BK_BIZ_ID})

    assert ApplicationCustomService.objects.filter(id=victim.id).exists()


def test_update_does_not_touch_another_business():
    victim = create_custom_service()

    with pytest.raises(ValueError):
        CustomServiceConfigResource().perform_request(
            {
                "id": victim.id,
                "bk_biz_id": BK_BIZ_ID,
                "app_name": APP_NAME,
                "name": "hijacked",
                "type": CustomServiceType.HTTP,
                "match_type": CustomServiceMatchType.MANUAL,
                "rule": {},
            }
        )

    victim.refresh_from_db()
    assert victim.bk_biz_id == OTHER_BK_BIZ_ID
    assert victim.name == "victim"
