"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
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

import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.log_databus.models import GrokInfo


OVERRIDE_MIDDLEWARE = "apps.tests.middlewares.OverrideMiddleware"


@override_settings(MIDDLEWARE=(OVERRIDE_MIDDLEWARE,))
class TestGrokViewSetAPI(TestCase):
    """
    测试 GrokViewSet 中的接口
    """

    def setUp(self):
        """测试前置设置"""
        self.bk_biz_id = 200
        self.base_url = "/api/v1/databus/grok/"

        # 清除可能存在的测试数据
        GrokInfo.objects.filter(bk_biz_id=self.bk_biz_id, name="TEST_GROK").delete()

    def tearDown(self):
        """清理测试数据"""
        GrokInfo.objects.filter(bk_biz_id=self.bk_biz_id, name="TEST_GROK").delete()

    @patch("apps.log_databus.views.grok_views.GrokViewSet.get_permissions", lambda _: [])
    def test_list_grok(self):
        """测试列表查询接口"""
        # 创建测试数据
        GrokInfo.objects.create(
            bk_biz_id=self.bk_biz_id,
            name="TEST_GROK",
            pattern="%{WORD:level}",
            sample="INFO",
            description="测试 Grok 模式",
        )

        response = self.client.get(self.base_url, {"bk_biz_id": self.bk_biz_id})

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertTrue(content["result"])
        self.assertEqual(content["code"], 0)
        self.assertIn("total", content["data"])
        self.assertIn("list", content["data"])

    @patch("apps.log_databus.views.grok_views.GrokViewSet.get_permissions", lambda _: [])
    def test_create_grok(self):
        """测试创建接口"""
        data = {
            "bk_biz_id": self.bk_biz_id,
            "name": "TEST_GROK",
            "pattern": "%{WORD:level}",
            "sample": "INFO",
            "description": "测试 Grok 模式",
        }
        response = self.client.post(self.base_url, data=json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertTrue(content["result"])
        self.assertEqual(content["code"], 0)
        self.assertIn("id", content["data"])
        self.assertTrue(GrokInfo.objects.filter(id=content["data"]["id"]).exists())

    @patch("apps.log_databus.views.grok_views.GrokViewSet.get_permissions", lambda _: [])
    def test_update_grok(self):
        """测试更新接口"""
        grok = GrokInfo.objects.create(
            bk_biz_id=self.bk_biz_id,
            name="TEST_GROK",
            pattern="%{WORD:level}",
            sample="INFO",
            description="测试 Grok 模式",
        )

        update_data = {
            "bk_biz_id": self.bk_biz_id,
            "pattern": "%{WORD:level} %{NUMBER:code}",
            "sample": "INFO 200",
            "description": "更新后的描述",
        }
        response = self.client.put(
            f"{self.base_url}{grok.id}/",
            data=json.dumps(update_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertTrue(content["result"])
        self.assertEqual(content["code"], 0)

        grok.refresh_from_db()
        self.assertEqual(grok.pattern, update_data["pattern"])
        self.assertEqual(grok.sample, update_data["sample"])
        self.assertEqual(grok.description, update_data["description"])

    @patch("apps.log_databus.views.grok_views.GrokViewSet.get_permissions", lambda _: [])
    def test_destroy_grok(self):
        """测试删除接口"""
        grok = GrokInfo.objects.create(
            bk_biz_id=self.bk_biz_id,
            name="TEST_GROK",
            pattern="%{WORD:level}",
            sample="INFO",
            description="测试 Grok 模式",
        )

        response = self.client.delete(f"{self.base_url}{grok.id}/")

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertTrue(content["result"])
        self.assertEqual(content["code"], 0)
        self.assertFalse(GrokInfo.objects.filter(id=grok.id).exists())

    @patch("apps.log_databus.views.grok_views.GrokViewSet.get_permissions", lambda _: [])
    def test_get_updated_by_list(self):
        """测试更新人列表接口"""
        GrokInfo.objects.create(
            bk_biz_id=self.bk_biz_id,
            name="TEST_GROK",
            pattern="%{WORD:level}",
            sample="INFO",
            description="测试 Grok 模式",
        )

        response = self.client.get(f"{self.base_url}updated_by_list/", {"bk_biz_id": self.bk_biz_id})

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertTrue(content["result"])
        self.assertEqual(content["code"], 0)
        self.assertIsInstance(content["data"], list)

    @patch("apps.log_databus.views.grok_views.GrokViewSet.get_permissions", lambda _: [])
    def test_search_grok(self):
        """测试搜索联想接口"""
        GrokInfo.objects.create(
            bk_biz_id=self.bk_biz_id,
            name="TEST_GROK",
            pattern="%{WORD:level}",
            sample="INFO",
            description="测试 Grok 模式",
        )

        response = self.client.get(
            f"{self.base_url}search/",
            {"bk_biz_id": self.bk_biz_id, "keyword": "TEST", "page": 1, "pagesize": 10},
        )

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertTrue(content["result"])
        self.assertEqual(content["code"], 0)
        self.assertIn("total", content["data"])
        self.assertIn("list", content["data"])

    @patch("apps.log_databus.views.grok_views.GrokViewSet.get_permissions", lambda _: [])
    def test_debug_grok(self):
        """测试调试接口"""
        data = {
            "bk_biz_id": self.bk_biz_id,
            "pattern": "%{WORD:level}",
            "sample": "INFO",
        }
        response = self.client.post(
            f"{self.base_url}debug/",
            data=json.dumps(data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertTrue(content["result"])
        self.assertEqual(content["code"], 0)
        self.assertIn("data", content)
        self.assertIn("_matched", content["data"])
        self.assertIn("level", content["data"])
        self.assertEqual(content["data"]["level"], "INFO")
