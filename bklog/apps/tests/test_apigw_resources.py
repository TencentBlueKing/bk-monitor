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
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from pathlib import Path

import yaml
from django.test import SimpleTestCase


PUBLIC_RESOURCES = {
    ("GET", "/clustering_config/{index_set_id}/config/"),
    ("GET", "/databus_collectors/"),
    ("GET", "/databus_collectors/{collector_config_id}/"),
    ("GET", "/index_set/{index_set_id}/"),
    ("GET", "/search_index_set/"),
    ("GET", "/search_index_set/{index_set_id}/fields/"),
    ("POST", "/databus_collectors/fast_create/"),
    ("POST", "/databus_collectors/{collector_config_id}/fast_update/"),
    ("POST", "/databus_collectors/{collector_config_id}/start/"),
    ("POST", "/databus_collectors/{collector_config_id}/stop/"),
    ("POST", "/esquery_search/"),
    ("POST", "/index_set/"),
    ("POST", "/pattern/{index_set_id}/search/"),
    ("POST", "/query/ts/"),
    ("POST", "/query/ts/raw/"),
    ("POST", "/query/ts/reference/"),
    ("PUT", "/index_set/{index_set_id}/"),
    ("DELETE", "/databus_collectors/{collector_config_id}/"),
    ("DELETE", "/index_set/{index_set_id}/"),
}


class ApiGatewayResourcesTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        bklog_root = Path(__file__).resolve().parents[2]
        resources_path = bklog_root / "support-files" / "apigw" / "resources.yaml"
        cls.resources = yaml.safe_load(resources_path.read_text(encoding="utf-8"))
        cls.zh_docs_dir = resources_path.parent / "apidocs" / "zh"

    def test_public_resources_match_approved_scope(self):
        public_resources = {
            (method.upper(), path)
            for path, methods in self.resources["paths"].items()
            for method, operation in methods.items()
            if operation["x-bk-apigateway-resource"]["isPublic"]
        }

        self.assertEqual(public_resources, PUBLIC_RESOURCES)

    def test_public_resources_require_app_and_resource_permissions(self):
        expected_auth_config = {
            "userVerifiedRequired": False,
            "appVerifiedRequired": True,
            "resourcePermissionRequired": True,
        }

        for method, path in PUBLIC_RESOURCES:
            resource = self.resources["paths"][path][method.lower()]["x-bk-apigateway-resource"]
            self.assertTrue(resource["allowApplyPermission"], f"{method} {path}")
            self.assertEqual(resource["authConfig"], expected_auth_config, f"{method} {path}")

    def test_delete_resources_keep_private_compatibility_paths(self):
        paths = self.resources["paths"]

        self.assertIn("delete", paths["/index_set/{index_set_id}/"])
        self.assertIn("delete", paths["/databus_collectors/{collector_config_id}/"])

        compatibility_resources = {
            "/delete_index_set/{index_set_id}/": "esb_delete_index_set",
            "/databus/collectors/{collector_config_id}/": "delete_databus_collectors",
        }
        for path, operation_id in compatibility_resources.items():
            resource = paths[path]["delete"]
            self.assertEqual(resource["operationId"], operation_id)
            self.assertFalse(resource["x-bk-apigateway-resource"]["isPublic"])

    def test_operation_ids_are_unique(self):
        operation_ids = [
            operation["operationId"] for methods in self.resources["paths"].values() for operation in methods.values()
        ]

        self.assertEqual(len(operation_ids), len(set(operation_ids)))

    def test_public_resources_have_chinese_docs(self):
        for methods in self.resources["paths"].values():
            for operation in methods.values():
                resource = operation["x-bk-apigateway-resource"]
                if not resource["isPublic"]:
                    continue

                operation_id = operation["operationId"]
                doc_path = self.zh_docs_dir / f"{operation_id}.md"
                self.assertTrue(doc_path.is_file(), f"missing API document: {doc_path.name}")

                content = doc_path.read_text(encoding="utf-8")
                self.assertIn("## 功能描述", content, doc_path.name)
                self.assertIn("## 请求", content, doc_path.name)
