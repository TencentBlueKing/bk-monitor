"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
----------------------------------------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.constants import ApiTokenAuthType
from apps.iam import ActionEnum
from apps.log_commons.models import ApiAuthToken
from apps.log_commons.token import CodeccTokenHandler, GrafanaTokenHandler, TokenHandlerFactory
from apps.log_commons.views import GetApiTokenViewSet


class TestGrafanaApiToken(TestCase):
    """Grafana 数据源 token 鉴权"""

    SPACE_UID = "bkcc__2"
    OTHER_SPACE_UID = "bkcc__3"
    BIZ_ID = 2

    def setUp(self):
        self.token = ApiAuthToken.objects.create(
            space_uid=self.SPACE_UID,
            type=ApiTokenAuthType.GRAFANA.value,
            token="testgrafana0001",
        )

    def test_token_handler_registered(self):
        handler = TokenHandlerFactory.get_handler(ApiTokenAuthType.GRAFANA.value)
        self.assertIsInstance(handler, GrafanaTokenHandler)

    def test_request_without_token_redirect(self):
        response = self.client.get("/api/v1/grafana/options/")
        self.assertEqual(response.status_code, 302)

    def test_request_with_valid_token(self):
        response = self.client.get("/api/v1/grafana/test/", HTTP_X_BKLOG_TOKEN=self.token.token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], "OK")

    def test_expired_token_rejected(self):
        self.token.expire_time = timezone.now() - timedelta(days=1)
        self.token.save()
        response = self.client.get("/api/v1/grafana/test/", HTTP_X_BKLOG_TOKEN=self.token.token)
        self.assertEqual(response.status_code, 403)

    @patch("apps.middleware.api_token_middleware.bk_biz_id_to_space_uid")
    def test_cross_biz_rejected(self, mock_biz_to_space):
        mock_biz_to_space.return_value = self.OTHER_SPACE_UID
        response = self.client.get(
            "/api/v1/grafana/metric/?bk_biz_id=3",
            HTTP_X_BKLOG_TOKEN=self.token.token,
        )
        self.assertEqual(response.status_code, 403)

    @patch("apps.middleware.api_token_middleware.bk_biz_id_to_space_uid")
    def test_matched_space_allowed(self, mock_biz_to_space):
        mock_biz_to_space.return_value = self.SPACE_UID
        # 仅验证中间件不拦截，业务数据由后续查询决定
        with patch("apps.grafana.views.GrafanaViewSet.get_validated_data", return_value={"bk_biz_id": 2}):
            with patch("apps.grafana.views.GrafanaQueryHandler.get_metric_list", return_value=[]):
                response = self.client.get(
                    "/api/v1/grafana/metric/?bk_biz_id=2",
                    HTTP_X_BKLOG_TOKEN=self.token.token,
                )
        self.assertEqual(response.status_code, 200)

    def test_grafana_token_limited_to_grafana_views(self):
        response = self.client.get("/api/v1/meta/spaces/mine/", HTTP_X_BKLOG_TOKEN=self.token.token)
        self.assertEqual(response.status_code, 403)

    @patch("apps.log_commons.views.Permission")
    def test_assert_biz_permission(self, mock_permission):
        mock_permission.return_value.is_allowed_by_biz.return_value = True
        GetApiTokenViewSet._assert_biz_permission(self.BIZ_ID)
        mock_permission.return_value.is_allowed_by_biz.assert_called_once_with(
            self.BIZ_ID, ActionEnum.VIEW_DASHBOARD, raise_exception=True
        )

    @patch("apps.log_commons.token.ApiAuthToken")
    @patch("apps.log_commons.token.get_request_username")
    def test_grafana_token_query_without_creator(self, mock_username, mock_model):
        mock_username.return_value = "user_a"
        mock_model.objects.filter.return_value.first.return_value = None
        mock_model.objects.create.return_value.token = "token_a"

        GrafanaTokenHandler().get_or_create_token("bkcc__4")

        self.assertNotIn("created_by", mock_model.objects.filter.call_args.kwargs)

    @patch("apps.log_commons.token.ApiAuthToken")
    @patch("apps.log_commons.token.get_request_username")
    def test_codecc_token_query_with_creator(self, mock_username, mock_model):
        mock_username.return_value = "user_a"
        mock_model.objects.filter.return_value.first.return_value = None
        mock_model.objects.create.return_value.token = "token_a"

        CodeccTokenHandler().get_or_create_token("bkcc__5")

        self.assertEqual(mock_model.objects.filter.call_args.kwargs["created_by"], "user_a")
