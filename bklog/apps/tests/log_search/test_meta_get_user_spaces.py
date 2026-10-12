from unittest.mock import patch

from django.test import SimpleTestCase

from apps.log_search.handlers.meta import MetaHandler


class MetaGetUserSpacesTest(SimpleTestCase):
    @patch("apps.log_search.handlers.meta.TransferApi.list_sticky_spaces", return_value=[])
    @patch("apps.log_search.handlers.meta.get_request_tenant_id", return_value="tenant-1")
    @patch("apps.log_search.handlers.meta.get_request_username", return_value="admin")
    @patch("apps.log_search.handlers.meta.Permission")
    @patch("apps.log_search.handlers.meta.Space.get_all_spaces")
    def test_has_permission_without_space_uid_reuses_filter_result(
        self,
        get_all_spaces,
        permission_cls,
        _username,
        _tenant,
        _sticky,
    ):
        allowed = [
            {
                "id": 1,
                "space_type_id": "bkcc",
                "space_type_name": "业务",
                "space_id": "2",
                "space_name": "蓝鲸",
                "space_uid": "bkcc__2",
                "space_code": "2",
                "bk_biz_id": 2,
                "time_zone": '"Asia/Shanghai"',
                "bk_tenant_id": "tenant-1",
            }
        ]
        permission_cls.return_value.filter_space_list_by_action.return_value = allowed

        results = MetaHandler.get_user_spaces(has_permission=True)

        get_all_spaces.assert_not_called()
        permission_cls.return_value.filter_space_list_by_action.assert_called_once()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["space_uid"], "bkcc__2")
        self.assertTrue(results[0]["permission"]["view_business_v2"])

    @patch("apps.log_search.handlers.meta.TransferApi.list_sticky_spaces", return_value=[])
    @patch("apps.log_search.handlers.meta.get_request_tenant_id", return_value="tenant-1")
    @patch("apps.log_search.handlers.meta.get_request_username", return_value="admin")
    @patch("apps.log_search.handlers.meta.Permission")
    @patch("apps.log_search.handlers.meta.Space.get_all_spaces")
    def test_with_space_uid_passes_loaded_spaces_to_filter(
        self,
        get_all_spaces,
        permission_cls,
        _username,
        _tenant,
        _sticky,
    ):
        spaces = [
            {
                "id": 1,
                "space_type_id": "bkci",
                "space_type_name": "研发项目",
                "space_id": "a6",
                "space_name": "gggg",
                "space_uid": "bkci__a6",
                "space_code": "a6",
                "bk_biz_id": -5423,
                "time_zone": '"Asia/Shanghai"',
                "bk_tenant_id": "tenant-1",
            }
        ]
        get_all_spaces.return_value = spaces
        permission_cls.return_value.filter_space_list_by_action.return_value = spaces

        results = MetaHandler.get_user_spaces(space_uid="bkci__a6", has_permission=True)

        get_all_spaces.assert_called_once_with(bk_tenant_id="tenant-1", space_uid="bkci__a6")
        permission_cls.return_value.filter_space_list_by_action.assert_called_once()
        self.assertEqual(results[0]["space_uid"], "bkci__a6")

    @patch("apps.log_search.handlers.meta.TransferApi.list_sticky_spaces", return_value=[])
    @patch("apps.log_search.handlers.meta.get_request_tenant_id", return_value="tenant-1")
    @patch("apps.log_search.handlers.meta.get_request_username", return_value="admin")
    @patch("apps.log_search.handlers.meta.Permission")
    @patch("apps.log_search.handlers.meta.Space.get_all_spaces")
    def test_without_has_permission_keeps_full_catalog(
        self,
        get_all_spaces,
        permission_cls,
        _username,
        _tenant,
        _sticky,
    ):
        spaces = [
            {
                "id": 1,
                "space_type_id": "bkcc",
                "space_type_name": "业务",
                "space_id": "2",
                "space_name": "蓝鲸",
                "space_uid": "bkcc__2",
                "space_code": "2",
                "bk_biz_id": 2,
                "time_zone": '"Asia/Shanghai"',
                "bk_tenant_id": "tenant-1",
            },
            {
                "id": 2,
                "space_type_id": "bkcc",
                "space_type_name": "业务",
                "space_id": "3",
                "space_name": "无权限",
                "space_uid": "bkcc__3",
                "space_code": "3",
                "bk_biz_id": 3,
                "time_zone": '"Asia/Shanghai"',
                "bk_tenant_id": "tenant-1",
            },
        ]
        get_all_spaces.return_value = spaces
        permission_cls.return_value.filter_space_list_by_action.return_value = [spaces[0]]

        results = MetaHandler.get_user_spaces(has_permission=False)

        get_all_spaces.assert_called_once_with(bk_tenant_id="tenant-1")
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0]["permission"]["view_business_v2"])
        self.assertFalse(results[1]["permission"]["view_business_v2"])
