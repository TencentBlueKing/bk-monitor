"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import Mock, patch, MagicMock

from packages.monitor_web.collecting.resources.qcloud import CloudProductMappingResource


class TestCloudProductMappingResource:
    """
    Test suite for CloudProductMappingResource.
    Focuses on verifying the query and search functionality for cloud products.
    """

    def create_mock_product(self, namespace, product_name, description, is_deleted=False):
        """Helper method to create mock cloud product"""
        mock_product = Mock()
        mock_product.namespace = namespace
        mock_product.product_name = product_name
        mock_product.description = description
        mock_product.is_deleted = is_deleted
        return mock_product

    @patch("packages.monitor_web.collecting.resources.qcloud.CloudProduct")
    def test_get_all_cloud_products(self, mock_cloud_product):
        """
        Verify that the resource correctly returns all created cloud products.
        """
        # 1. Setup: Mock the CloudProduct queryset
        mock_products = [
            self.create_mock_product("QCE/CVM", "Cloud Virtual Machine", "Scalable virtual server instances."),
            self.create_mock_product("QCE/CDB", "Cloud Database MySQL", "Managed MySQL database service."),
            self.create_mock_product(
                "QCE/CLB", "Cloud Load Balancer", "Distributes incoming traffic across multiple instances."
            ),
        ]

        mock_queryset = MagicMock()
        mock_queryset.__iter__ = Mock(return_value=iter(mock_products))
        mock_cloud_product.objects.filter.return_value = mock_queryset

        # 2. Action: Call the resource to get all cloud products
        resource = CloudProductMappingResource()
        result = resource.perform_request({})

        # 3. Assertions: Verify the result
        mock_cloud_product.objects.filter.assert_called_once_with(is_deleted=False)
        assert result["total"] == 3, "Total number of products should be 3."
        assert len(result["products"]) == 3, "Products list should contain 3 items."

        # Verify product details
        expected_namespaces = {"QCE/CVM", "QCE/CDB", "QCE/CLB"}
        returned_namespaces = {p["namespace"] for p in result["products"]}
        assert returned_namespaces == expected_namespaces, "Returned namespaces should match expected ones."

    @patch("packages.monitor_web.collecting.resources.qcloud.CloudProduct")
    def test_search_cloud_products_by_namespace(self, mock_cloud_product):
        """
        Test searching cloud products by namespace.
        """
        # 1. Setup: Mock the CloudProduct queryset
        mock_products = [
            self.create_mock_product("QCE/CVM", "Cloud Virtual Machine", "Scalable virtual server instances."),
        ]

        mock_queryset = MagicMock()
        mock_queryset.__iter__ = Mock(return_value=iter(mock_products))
        mock_queryset.filter.return_value = mock_queryset
        mock_cloud_product.objects.filter.return_value = mock_queryset

        # 2. Action: Search for products containing "CVM" in namespace
        resource = CloudProductMappingResource()
        result = resource.perform_request({"search": "CVM"})

        # 3. Assertions: Verify the result
        mock_cloud_product.objects.filter.assert_called_once_with(is_deleted=False)
        assert result["total"] == 1, "Should return only one product matching the search."
        assert len(result["products"]) == 1, "Products list should contain only one item."
        assert result["products"][0]["namespace"] == "QCE/CVM", "Should return the CVM product."

    @patch("packages.monitor_web.collecting.resources.qcloud.CloudProduct")
    def test_search_cloud_products_by_product_name(self, mock_cloud_product):
        """
        Test searching cloud products by product name.
        """
        # 1. Setup: Mock the CloudProduct queryset
        mock_products = [
            self.create_mock_product("QCE/CDB", "Cloud Database MySQL", "Managed MySQL database service."),
        ]

        mock_queryset = MagicMock()
        mock_queryset.__iter__ = Mock(return_value=iter(mock_products))
        mock_queryset.filter.return_value = mock_queryset
        mock_cloud_product.objects.filter.return_value = mock_queryset

        # 2. Action: Search for products containing "Database" in product name
        resource = CloudProductMappingResource()
        result = resource.perform_request({"search": "Database"})

        # 3. Assertions: Verify the result
        assert result["total"] == 1, "Should return only one product matching the search."
        assert len(result["products"]) == 1, "Products list should contain only one item."
        assert result["products"][0]["namespace"] == "QCE/CDB", "Should return the CDB product."
        assert "Database" in result["products"][0]["product_name"], "Product name should contain 'Database'."

    @patch("packages.monitor_web.collecting.resources.qcloud.CloudProduct")
    def test_search_cloud_products_by_description(self, mock_cloud_product):
        """
        Test searching cloud products by description.
        """
        # 1. Setup: Mock the CloudProduct queryset
        mock_products = [
            self.create_mock_product(
                "QCE/CLB", "Cloud Load Balancer", "Distributes incoming traffic across multiple instances."
            ),
        ]

        mock_queryset = MagicMock()
        mock_queryset.__iter__ = Mock(return_value=iter(mock_products))
        mock_queryset.filter.return_value = mock_queryset
        mock_cloud_product.objects.filter.return_value = mock_queryset

        # 2. Action: Search for products containing "traffic" in description
        resource = CloudProductMappingResource()
        result = resource.perform_request({"search": "traffic"})

        # 3. Assertions: Verify the result
        assert result["total"] == 1, "Should return only one product matching the search."
        assert len(result["products"]) == 1, "Products list should contain only one item."
        assert result["products"][0]["namespace"] == "QCE/CLB", "Should return the CLB product."
        assert "traffic" in result["products"][0]["description"], "Description should contain 'traffic'."

    @patch("packages.monitor_web.collecting.resources.qcloud.CloudProduct")
    def test_search_cloud_products_no_results(self, mock_cloud_product):
        """
        Test searching cloud products with no matching results.
        """
        # 1. Setup: Mock empty queryset
        mock_queryset = MagicMock()
        mock_queryset.__iter__ = Mock(return_value=iter([]))
        mock_queryset.filter.return_value = mock_queryset
        mock_cloud_product.objects.filter.return_value = mock_queryset

        # 2. Action: Search for non-existent product
        resource = CloudProductMappingResource()
        result = resource.perform_request({"search": "NonExistentProduct"})

        # 3. Assertions: Verify no products are returned
        assert result["total"] == 0, "Should return zero products for non-matching search."
        assert len(result["products"]) == 0, "Products list should be empty."

    @patch("packages.monitor_web.collecting.resources.qcloud.CloudProduct")
    def test_search_functionality_with_models_q(self, mock_cloud_product):
        """
        Test that the search functionality correctly uses Django's Q objects for filtering.
        """
        # 1. Setup: Mock the CloudProduct queryset
        mock_products = [
            self.create_mock_product("QCE/CVM", "Cloud Virtual Machine", "Scalable virtual server instances."),
        ]

        mock_queryset = MagicMock()
        mock_queryset.__iter__ = Mock(return_value=iter(mock_products))
        mock_queryset.filter.return_value = mock_queryset
        mock_cloud_product.objects.filter.return_value = mock_queryset

        # 2. Action: Search for products
        resource = CloudProductMappingResource()
        result = resource.perform_request({"search": "CVM"})

        # 3. Assertions: Verify that filter was called correctly
        mock_cloud_product.objects.filter.assert_called_once_with(is_deleted=False)
        # The second filter call should be made on the queryset for search functionality
        mock_queryset.filter.assert_called_once()
        assert result["total"] == 1, "Should return one product."

    @patch("packages.monitor_web.collecting.resources.qcloud.CloudProduct")
    def test_exclude_deleted_products(self, mock_cloud_product):
        """
        Test that deleted products are excluded from results.
        """
        # 1. Setup: Mock non-deleted products only
        mock_products = [
            self.create_mock_product(
                "QCE/CVM", "Cloud Virtual Machine", "Scalable virtual server instances.", is_deleted=False
            ),
        ]

        mock_queryset = MagicMock()
        mock_queryset.__iter__ = Mock(return_value=iter(mock_products))
        mock_cloud_product.objects.filter.return_value = mock_queryset

        # 2. Action: Get all cloud products
        resource = CloudProductMappingResource()
        result = resource.perform_request({})

        # 3. Assertions: Verify that filter excludes deleted products
        mock_cloud_product.objects.filter.assert_called_once_with(is_deleted=False)
        assert result["total"] == 1, "Should return only non-deleted products."
        assert len(result["products"]) == 1, "Products list should contain only non-deleted products."
        assert result["products"][0]["namespace"] == "QCE/CVM", "Should return only the non-deleted product."

    def test_request_serializer_validation(self):
        """
        Test the request serializer validation.
        """
        resource = CloudProductMappingResource()
        serializer = resource.RequestSerializer()

        # Test with valid data
        valid_data = {"search": "CVM"}
        serializer = resource.RequestSerializer(data=valid_data)
        assert serializer.is_valid(), "Serializer should be valid with search parameter."

        # Test with empty data (search is optional)
        empty_data = {}
        serializer = resource.RequestSerializer(data=empty_data)
        assert serializer.is_valid(), "Serializer should be valid without search parameter."

    def test_response_serializer_structure(self):
        """
        Test the response serializer structure.
        """
        resource = CloudProductMappingResource()

        sample_response = {
            "total": 2,
            "products": [
                {
                    "namespace": "QCE/CVM",
                    "product_name": "Cloud Virtual Machine",
                    "description": "Scalable virtual server instances.",
                },
                {
                    "namespace": "QCE/CDB",
                    "product_name": "Cloud Database MySQL",
                    "description": "Managed MySQL database service.",
                },
            ],
        }

        serializer = resource.ResponseSerializer(data=sample_response)
        assert serializer.is_valid(), "Response serializer should be valid with proper structure."
