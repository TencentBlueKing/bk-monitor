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

from packages.monitor_web.collecting.resources.qcloud import (
    CloudProductMappingResource,
    CloudProductInstanceQueryResource,
)


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


class TestCloudProductInstanceQueryResource:
    """
    Test suite for CloudProductInstanceQueryResource.
    Focuses on verifying the instance query functionality with external API calls.
    """

    def create_mock_task(self, task_id, secret_id, secret_key):
        """Helper method to create mock CloudMonitoringTask"""
        mock_task = Mock()
        mock_task.task_id = task_id
        mock_task.secret_id = secret_id
        mock_task.secret_key = secret_key
        return mock_task

    def create_mock_instance_field(self, field_name, display_name, description, is_active=True):
        """Helper method to create mock CloudProductInstanceField"""
        return {
            "field_name": field_name,
            "display_name": display_name,
            "description": description,
            "is_active": is_active,
        }

    @patch("packages.monitor_web.collecting.resources.qcloud.api.qcloud_monitor.query_instances")
    @patch("monitor_web.models.qcloud.CloudProductInstanceField")
    def test_query_instances_with_credentials(self, mock_field_model, mock_api_call):
        """
        Test instance query with direct credentials.
        """
        # 1. Setup: Mock field configuration and API response
        mock_fields = [
            self.create_mock_instance_field("InstanceId", "实例ID", "云服务器实例的唯一标识符"),
            self.create_mock_instance_field("InstanceName", "实例名称", "云服务器实例的名称"),
        ]

        mock_queryset = MagicMock()
        mock_queryset.values.return_value = mock_fields
        mock_field_model.objects.filter.return_value = mock_queryset

        # Mock API response
        mock_api_response = {
            "total": 2,
            "data": [
                {
                    "InstanceId": "i-1234567890abcdef0",
                    "InstanceName": "web-server-01",
                    "PrivateIpAddress": "PRIVATE_IP_1",
                    "PublicIpAddress": "PUBLIC_IP_1",
                },
                {
                    "InstanceId": "i-0987654321fedcba0",
                    "InstanceName": "web-server-02",
                    "PrivateIpAddress": "PRIVATE_IP_2",
                    "PublicIpAddress": "PUBLIC_IP_2",
                },
            ],
        }
        mock_api_call.return_value = mock_api_response

        # 2. Action: Query instances with direct credentials
        resource = CloudProductInstanceQueryResource()
        request_data = {
            "namespace": "QCE/CVM",
            "region": "ap-beijing",
            "secret_id": "test_secret_id",
            "secret_key": "test_secret_key",
            "tags": [],
            "filters": [],
        }
        result = resource.perform_request(request_data)

        # 3. Assertions
        # Verify field configuration query
        mock_field_model.objects.filter.assert_called_once_with(namespace="QCE/CVM", is_active=True, is_deleted=False)

        # Verify API call
        expected_api_data = {
            "secretId": "test_secret_id",
            "secretKey": "test_secret_key",
            "namespace": "QCE/CVM",
            "region": "ap-beijing",
            "tags": [],
            "filters": [],
        }
        mock_api_call.assert_called_once_with(expected_api_data)

        # Verify response structure
        assert result["total"] == 2, "Total should match API response"
        assert len(result["data"]) == 2, "Should return 2 filtered instances"

        # Verify filtered data structure
        instance = result["data"][0]
        assert "InstanceId" in instance, "Should contain InstanceId field"
        assert "InstanceName" in instance, "Should contain InstanceName field"
        assert "PrivateIpAddress" not in instance, "Should not contain unconfigured fields"

        # Verify field structure
        assert instance["InstanceId"]["value"] == "i-1234567890abcdef0"
        assert instance["InstanceId"]["display_name"] == "实例ID"
        assert instance["InstanceId"]["description"] == "云服务器实例的唯一标识符"

    @patch("packages.monitor_web.collecting.resources.qcloud.api.qcloud_monitor.query_instances")
    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    @patch("monitor_web.models.qcloud.CloudProductInstanceField")
    def test_query_instances_with_task_id(self, mock_field_model, mock_task_model, mock_api_call):
        """
        Test instance query using task_id to retrieve credentials.
        """
        # 1. Setup: Mock task lookup
        mock_task = self.create_mock_task("test_task_id", "task_secret_id", "task_secret_key")
        mock_task_model.objects.get.return_value = mock_task

        # Mock field configuration
        mock_fields = [self.create_mock_instance_field("InstanceId", "实例ID", "实例标识符")]
        mock_queryset = MagicMock()
        mock_queryset.values.return_value = mock_fields
        mock_field_model.objects.filter.return_value = mock_queryset

        # Mock API response
        mock_api_response = {"total": 1, "data": [{"InstanceId": "i-test123"}]}
        mock_api_call.return_value = mock_api_response

        # 2. Action: Query instances using task_id
        resource = CloudProductInstanceQueryResource()
        request_data = {"namespace": "QCE/CVM", "region": "ap-beijing", "task_id": "test_task_id"}
        result = resource.perform_request(request_data)

        # 3. Assertions
        # Verify task lookup
        mock_task_model.objects.get.assert_called_once_with(task_id="test_task_id")

        # Verify API call with task credentials
        expected_api_data = {
            "secretId": "task_secret_id",
            "secretKey": "task_secret_key",
            "namespace": "QCE/CVM",
            "region": "ap-beijing",
            "tags": [],
            "filters": [],
        }
        mock_api_call.assert_called_once_with(expected_api_data)

        assert result["total"] == 1

    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    def test_query_instances_task_not_found(self, mock_task_model):
        """
        Test exception handling when task_id is not found.
        """
        # 1. Setup: Mock task not found
        from django.core.exceptions import ObjectDoesNotExist

        mock_task_model.DoesNotExist = ObjectDoesNotExist
        mock_task_model.objects.get.side_effect = ObjectDoesNotExist()

        # 2. Action & Assertions: Expect exception
        resource = CloudProductInstanceQueryResource()
        request_data = {"namespace": "QCE/CVM", "region": "ap-beijing", "task_id": "nonexistent_task_id"}

        try:
            resource.perform_request(request_data)
            assert False, "Should raise exception for non-existent task_id"
        except Exception as e:
            assert "未找到任务ID" in str(e)

    def test_query_instances_missing_credentials(self):
        """
        Test exception handling when neither credentials nor task_id is provided.
        """
        # Action & Assertions: Expect exception
        resource = CloudProductInstanceQueryResource()
        request_data = {"namespace": "QCE/CVM", "region": "ap-beijing"}

        try:
            resource.perform_request(request_data)
            assert False, "Should raise exception for missing credentials"
        except Exception as e:
            assert "必须提供secret_id和secret_key，或者提供task_id" in str(e)

    @patch("packages.monitor_web.collecting.resources.qcloud.api.qcloud_monitor.query_instances")
    @patch("monitor_web.models.qcloud.CloudProductInstanceField")
    def test_filter_instance_data_no_field_config(self, mock_field_model, mock_api_call):
        """
        Test instance data filtering when no field configuration exists.
        """
        # 1. Setup: Mock empty field configuration
        mock_queryset = MagicMock()
        mock_queryset.values.return_value = []  # No field configuration
        mock_field_model.objects.filter.return_value = mock_queryset

        # Mock API response
        mock_api_response = {"total": 1, "data": [{"InstanceId": "i-test123", "InstanceName": "test-instance"}]}
        mock_api_call.return_value = mock_api_response

        # 2. Action: Query instances
        resource = CloudProductInstanceQueryResource()
        request_data = {
            "namespace": "QCE/UNKNOWN",
            "region": "ap-beijing",
            "secret_id": "test_id",
            "secret_key": "test_key",
        }
        result = resource.perform_request(request_data)

        # 3. Assertions: Should return original data when no field config exists
        assert result["total"] == 1
        assert result["data"] == [{"InstanceId": "i-test123", "InstanceName": "test-instance"}]

    @patch("packages.monitor_web.collecting.resources.qcloud.api.qcloud_monitor.query_instances")
    def test_api_call_failure(self, mock_api_call):
        """
        Test exception handling when external API call fails.
        """
        # 1. Setup: Mock API failure
        mock_api_call.side_effect = Exception("External API error")

        # 2. Action & Assertions: Expect exception
        resource = CloudProductInstanceQueryResource()
        request_data = {
            "namespace": "QCE/CVM",
            "region": "ap-beijing",
            "secret_id": "test_id",
            "secret_key": "test_key",
        }

        try:
            resource.perform_request(request_data)
            assert False, "Should raise exception for API failure"
        except Exception as e:
            assert "实例查询失败" in str(e)

    @patch("packages.monitor_web.collecting.resources.qcloud.api.qcloud_monitor.query_instances")
    @patch("monitor_web.models.qcloud.CloudProductInstanceField")
    def test_filter_instance_data_partial_fields(self, mock_field_model, mock_api_call):
        """
        Test filtering when instance data has more fields than configured.
        """
        # 1. Setup: Configure only subset of fields
        mock_fields = [
            self.create_mock_instance_field("InstanceId", "实例ID", "实例标识符")
            # Note: Not configuring InstanceName, PrivateIp, etc.
        ]
        mock_queryset = MagicMock()
        mock_queryset.values.return_value = mock_fields
        mock_field_model.objects.filter.return_value = mock_queryset

        # Mock API response with extra fields
        mock_api_response = {
            "total": 1,
            "data": [
                {
                    "InstanceId": "i-test123",
                    "InstanceName": "test-instance",
                    "PrivateIpAddress": "PRIVATE_IP_TEST",
                    "PublicIpAddress": "PUBLIC_IP_TEST",
                    "Status": "running",
                }
            ],
        }
        mock_api_call.return_value = mock_api_response

        # 2. Action: Query instances
        resource = CloudProductInstanceQueryResource()
        request_data = {
            "namespace": "QCE/CVM",
            "region": "ap-beijing",
            "secret_id": "test_id",
            "secret_key": "test_key",
        }
        result = resource.perform_request(request_data)

        # 3. Assertions: Should only return configured fields
        assert result["total"] == 1
        assert len(result["data"]) == 1

        instance = result["data"][0]
        assert "InstanceId" in instance, "Should contain configured field"
        assert "InstanceName" not in instance, "Should not contain unconfigured field"
        assert "PrivateIpAddress" not in instance, "Should not contain unconfigured field"
        assert len(instance) == 1, "Should only contain 1 configured field"

    def test_request_serializer_validation(self):
        """
        Test the request serializer validation.
        """
        resource = CloudProductInstanceQueryResource()

        # Test with valid data including required fields
        valid_data = {
            "namespace": "QCE/CVM",
            "region": "ap-beijing",
            "secret_id": "test_id",
            "secret_key": "test_key",
            "tags": [{"name": "env", "values": ["prod"], "fuzzy": False}],
            "filters": [{"name": "instance-state-name", "values": ["running"]}],
        }
        serializer = resource.RequestSerializer(data=valid_data)
        assert serializer.is_valid(), f"Serializer should be valid: {serializer.errors}"

        # Test with minimal required data
        minimal_data = {"namespace": "QCE/CVM", "region": "ap-beijing", "task_id": "test_task"}
        serializer = resource.RequestSerializer(data=minimal_data)
        assert serializer.is_valid(), f"Serializer should be valid with minimal data: {serializer.errors}"

        # Test with missing required fields
        invalid_data = {
            "region": "ap-beijing"
            # Missing namespace
        }
        serializer = resource.RequestSerializer(data=invalid_data)
        assert not serializer.is_valid(), "Serializer should be invalid without required fields"

    def test_response_serializer_structure(self):
        """
        Test the response serializer structure.
        """
        resource = CloudProductInstanceQueryResource()

        sample_response = {
            "total": 1,
            "data": [
                {
                    "InstanceId": {
                        "value": "i-1234567890abcdef0",
                        "display_name": "实例ID",
                        "description": "云服务器实例的唯一标识符",
                    },
                    "InstanceName": {
                        "value": "web-server-01",
                        "display_name": "实例名称",
                        "description": "云服务器实例的名称",
                    },
                }
            ],
        }

        serializer = resource.ResponseSerializer(data=sample_response)
        assert serializer.is_valid(), f"Response serializer should be valid: {serializer.errors}"
