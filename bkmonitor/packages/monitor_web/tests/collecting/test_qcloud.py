"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from core.drf_resource import resource
from monitor_web.models.qcloud import CloudProduct

pytestmark = pytest.mark.django_db


class TestQcloudCollectingResource:
    """
    Test suite for QcloudCollectingResource.
    Focuses on verifying the basic query functionality for cloud product namespaces.
    """

    def test_get_all_cloud_product_namespaces(self):
        """
        Verify that the resource correctly returns all created cloud product namespaces.
        """
        # 1. Setup: Clean up existing data and create new test data
        CloudProduct.objects.all().delete()
        test_products = [
            CloudProduct.objects.create(
                namespace="QCE/CVM",
                product_name="Cloud Virtual Machine",
                description="Scalable virtual server instances.",
            ),
            CloudProduct.objects.create(
                namespace="QCE/CDB", product_name="Cloud Database MySQL", description="Managed MySQL database service."
            ),
            CloudProduct.objects.create(
                namespace="QCE/CLB",
                product_name="Cloud Load Balancer",
                description="Distributes incoming traffic across multiple instances.",
            ),
        ]
        expected_namespaces = {p.namespace for p in test_products}

        # 2. Action: Call the resource to get all cloud products
        result = resource.collecting.cloud_product_mapping()

        # 3. Assertions: Verify the result
        # Check that the total count is correct
        assert result["total"] == len(test_products), "Total number of products should match created ones."

        # Check that the number of returned products is correct
        assert len(result["products"]) == len(test_products), "Number of products in list should match created ones."

        # Check that all expected namespaces are present in the result
        returned_namespaces = {p["namespace"] for p in result["products"]}
        assert returned_namespaces == expected_namespaces, "Returned namespaces should match the created ones."

        # 4. Teardown: Clean up the created test data
        CloudProduct.objects.all().delete()
