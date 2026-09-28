# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from unittest import TestCase, mock

from bkmonitor.iam import ActionEnum
from monitor_web.notice_group.resources.front import (
    DeleteNoticeGroupResource,
    NoticeGroupDetailResource,
)

MODULE = "monitor_web.notice_group.resources.front"


class Denied(Exception):
    pass


def _notice_group(bk_biz_id):
    return {
        "id": 1,
        "bk_biz_id": bk_biz_id,
        "name": "group",
        "message": "",
        "notice_receiver": [],
        "notice_way": {},
        "webhook_url": "",
        "wxwork_group": {},
        "create_user": "admin",
        "update_user": "admin",
        "create_time": "",
        "update_time": "",
    }


@mock.patch.object(NoticeGroupDetailResource, "get_users_info", return_value={})
@mock.patch(f"{MODULE}.resource")
@mock.patch(f"{MODULE}.Permission")
class TestNoticeGroupDetailBizPermission(TestCase):
    def test_checks_group_biz(self, permission_cls, resource, get_users_info):
        resource.notice_group.backend_search_notice_group.return_value = [_notice_group(3)]
        permission_cls.return_value.is_allowed_by_biz.side_effect = Denied

        with self.assertRaises(Denied):
            NoticeGroupDetailResource().perform_request({"id": 1})

        permission_cls.return_value.is_allowed_by_biz.assert_called_once_with(
            3, ActionEnum.VIEW_NOTIFY_TEAM, raise_exception=True
        )
        get_users_info.assert_not_called()

    def test_global_group_skips_check(self, permission_cls, resource, get_users_info):
        resource.notice_group.backend_search_notice_group.return_value = [_notice_group(0)]
        resource.cc.get_notify_roles.return_value = {}

        result = NoticeGroupDetailResource().perform_request({"id": 1})

        permission_cls.assert_not_called()
        self.assertEqual(result["bk_biz_id"], 0)


@mock.patch(f"{MODULE}.resource")
@mock.patch(f"{MODULE}.Permission")
@mock.patch(f"{MODULE}.NoticeGroup.objects")
class TestDeleteNoticeGroupBizPermission(TestCase):
    def test_checks_each_group_biz(self, group_objects, permission_cls, resource):
        group_objects.filter.return_value.values_list.return_value = [2, 3, 3]

        DeleteNoticeGroupResource().perform_request({"id_list": [1, 2, 3]})

        group_objects.filter.assert_called_once_with(id__in=[1, 2, 3])
        is_allowed_by_biz = permission_cls.return_value.is_allowed_by_biz
        self.assertEqual(is_allowed_by_biz.call_count, 2)
        is_allowed_by_biz.assert_has_calls(
            [
                mock.call(2, ActionEnum.MANAGE_NOTIFY_TEAM, raise_exception=True),
                mock.call(3, ActionEnum.MANAGE_NOTIFY_TEAM, raise_exception=True),
            ],
            any_order=True,
        )
        resource.notice_group.backend_delete_notice_group.assert_called_once_with(ids=[1, 2, 3])

    def test_denied_biz_stops_delete(self, group_objects, permission_cls, resource):
        group_objects.filter.return_value.values_list.return_value = [3]
        permission_cls.return_value.is_allowed_by_biz.side_effect = Denied

        with self.assertRaises(Denied):
            DeleteNoticeGroupResource().perform_request({"id_list": [1]})
        resource.notice_group.backend_delete_notice_group.assert_not_called()
