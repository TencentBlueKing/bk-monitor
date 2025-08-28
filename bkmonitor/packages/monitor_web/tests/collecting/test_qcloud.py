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
    CloudProductConfigResource,
    CloudMonitoringConfigResource,
    CloudMonitoringTaskListResource,
    CloudMonitoringTaskDetailResource,
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

        # 打印云产品映射接口返回的数据
        print("\n" + "=" * 50)
        print("云产品映射接口返回数据:")
        print("请求参数: {}")
        print(f"Mock products count: {len(mock_products)}")
        print("Mock products details:")
        for i, product in enumerate(mock_products):
            print(f"  {i + 1}. Namespace: {product.namespace}")
            print(f"     Product Name: {product.product_name}")
            print(f"     Description: {product.description}")
        print("\n接口返回结果:")
        print(f"Total: {result.get('total', 0)}")
        print(f"Products count: {len(result.get('products', []))}")
        if result.get("products"):
            print("Products details:")
            for i, product in enumerate(result["products"]):
                print(f"  {i + 1}. {product}")
        print("=" * 50 + "\n")

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

        # 打印API返回的原始数据
        print("\n" + "=" * 50)
        print("API原始返回数据:")
        print(f"API Response: {mock_api_response}")
        print("\n处理后的结果数据:")
        print(f"Result: {result}")
        print("=" * 50 + "\n")

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


class TestCloudProductConfigResource:
    """
    Test suite for CloudProductConfigResource.
    Focuses on verifying the product configuration query functionality including tags, filters, and metrics.
    """

    def create_mock_tag_field(self, tag_name, display_name):
        """Helper method to create mock tag field data"""
        return {
            "tag_name": tag_name,
            "display_name": display_name,
        }

    def create_mock_metric_field(self, metric_name, display_name, description, unit, dimensions):
        """Helper method to create mock metric field data"""
        return {
            "metric_name": metric_name,
            "display_name": display_name,
            "description": description,
            "unit": unit,
            "dimensions": dimensions,
        }

    @patch("packages.monitor_web.collecting.resources.qcloud.api.qcloud_monitor.query_instance_filters")
    @patch("monitor_web.models.qcloud.CloudProductMetric")
    @patch("monitor_web.models.qcloud.CloudProductTagField")
    def test_get_product_config_success(self, mock_tag_model, mock_metric_model, mock_api_call):
        """
        Test successful retrieval of product configuration including tags, filters, and metrics.
        """
        # 1. Setup: Mock tag fields
        mock_tag_fields = [
            self.create_mock_tag_field("env", "环境"),
            self.create_mock_tag_field("app", "应用"),
            self.create_mock_tag_field("project", ""),  # Empty display_name to test fallback
        ]
        mock_tag_queryset = MagicMock()
        mock_tag_queryset.values.return_value = mock_tag_fields
        mock_tag_model.objects.filter.return_value = mock_tag_queryset

        # Mock metric fields
        mock_metric_fields = [
            self.create_mock_metric_field("CPUUtilization", "CPU使用率", "CPU使用百分比", "%", ["InstanceId"]),
            self.create_mock_metric_field(
                "MemoryUtilization", "", "内存使用率", "%", ["InstanceId"]
            ),  # Empty display_name
            self.create_mock_metric_field("NetworkIn", "网络入流量", "", "MB/s", ["InstanceId"]),  # Empty description
        ]
        mock_metric_queryset = MagicMock()
        mock_metric_queryset.values.return_value = mock_metric_fields
        mock_metric_model.objects.filter.return_value = mock_metric_queryset

        # Mock API response for filters
        mock_api_response = {
            "namespace": "QCE/CVM",
            "filters": ["Domain", "ProjectId", "VpcId", "InstanceId", "InstanceName"],
        }
        mock_api_call.return_value = mock_api_response

        # 2. Action: Query product configuration
        resource = CloudProductConfigResource()
        request_data = {"namespace": "QCE/CVM"}
        result = resource.perform_request(request_data)

        # 打印接口返回的数据
        print("\n" + "=" * 60)
        print("产品配置接口返回数据:")
        print(f"请求参数: {request_data}")
        print(f"API Response (filters): {mock_api_response}")
        print(f"Tag Fields: {mock_tag_fields}")
        print(f"Metric Fields: {mock_metric_fields}")
        print("\n最终结果数据:")
        print(f"Tags: {result.get('tags', {})}")
        print(f"Filters: {result.get('filters', {})}")
        print(f"Metrics count: {len(result.get('metrics', []))}")
        if result.get("metrics"):
            print("Metrics details:")
            for i, metric in enumerate(result["metrics"]):
                print(f"  {i + 1}. {metric}")
        print("=" * 60 + "\n")

        # 3. Assertions: Verify ORM queries
        mock_tag_model.objects.filter.assert_called_once_with(namespace="QCE/CVM", is_active=True, is_deleted=False)
        mock_metric_model.objects.filter.assert_called_once_with(namespace="QCE/CVM", is_active=True, is_deleted=False)

        # Verify API call
        expected_api_data = {"namespace": "QCE/CVM"}
        mock_api_call.assert_called_once_with(expected_api_data)

        # Verify response structure
        assert "tags" in result, "Response should contain tags"
        assert "filters" in result, "Response should contain filters"
        assert "metrics" in result, "Response should contain metrics"

        # Verify tags content
        expected_tags = {
            "env": "环境",
            "app": "应用",
            "project": "project",  # Should fallback to tag_name when display_name is empty
        }
        assert result["tags"] == expected_tags, f"Tags should match expected: {result['tags']}"

        # Verify filters content
        expected_filters = {
            "Domain": "Domain",
            "ProjectId": "ProjectId",
            "VpcId": "VpcId",
            "InstanceId": "InstanceId",
            "InstanceName": "InstanceName",
        }
        assert result["filters"] == expected_filters, f"Filters should match expected: {result['filters']}"

        # Verify metrics content
        assert len(result["metrics"]) == 3, "Should return 3 metrics"

        # Check first metric
        cpu_metric = next((m for m in result["metrics"] if m["metric_name"] == "CPUUtilization"), None)
        assert cpu_metric is not None, "Should contain CPUUtilization metric"
        assert cpu_metric["display_name"] == "CPU使用率"
        assert cpu_metric["description"] == "CPU使用百分比"
        assert cpu_metric["unit"] == "%"
        assert cpu_metric["dimensions"] == ["InstanceId"]

        # Check metric with empty display_name (should fallback to metric_name)
        mem_metric = next((m for m in result["metrics"] if m["metric_name"] == "MemoryUtilization"), None)
        assert mem_metric is not None, "Should contain MemoryUtilization metric"
        assert mem_metric["display_name"] == "MemoryUtilization", "Should fallback to metric_name"

        # Check metric with empty description
        net_metric = next((m for m in result["metrics"] if m["metric_name"] == "NetworkIn"), None)
        assert net_metric is not None, "Should contain NetworkIn metric"
        assert net_metric["description"] == "", "Should handle empty description"

    @patch("packages.monitor_web.collecting.resources.qcloud.api.qcloud_monitor.query_instance_filters")
    @patch("monitor_web.models.qcloud.CloudProductMetric")
    @patch("monitor_web.models.qcloud.CloudProductTagField")
    def test_get_product_config_empty_data(self, mock_tag_model, mock_metric_model, mock_api_call):
        """
        Test product configuration when no tags or metrics are configured.
        """
        # 1. Setup: Mock empty results
        mock_tag_queryset = MagicMock()
        mock_tag_queryset.values.return_value = []
        mock_tag_model.objects.filter.return_value = mock_tag_queryset

        mock_metric_queryset = MagicMock()
        mock_metric_queryset.values.return_value = []
        mock_metric_model.objects.filter.return_value = mock_metric_queryset

        # Mock API response with no filters
        mock_api_response = {"namespace": "QCE/UNKNOWN", "filters": []}
        mock_api_call.return_value = mock_api_response

        # 2. Action: Query product configuration
        resource = CloudProductConfigResource()
        request_data = {"namespace": "QCE/UNKNOWN"}
        result = resource.perform_request(request_data)

        # 3. Assertions: Should return empty collections
        assert result["tags"] == {}, "Should return empty tags dictionary"
        assert result["filters"] == {}, "Should return empty filters dictionary"
        assert result["metrics"] == [], "Should return empty metrics list"

    @patch("packages.monitor_web.collecting.resources.qcloud.api.qcloud_monitor.query_instance_filters")
    @patch("monitor_web.models.qcloud.CloudProductMetric")
    @patch("monitor_web.models.qcloud.CloudProductTagField")
    def test_api_call_failure_handling(self, mock_tag_model, mock_metric_model, mock_api_call):
        """
        Test handling of API call failure for filters.
        """
        # 1. Setup: Mock successful ORM queries
        mock_tag_fields = [self.create_mock_tag_field("env", "环境")]
        mock_tag_queryset = MagicMock()
        mock_tag_queryset.values.return_value = mock_tag_fields
        mock_tag_model.objects.filter.return_value = mock_tag_queryset

        mock_metric_fields = [
            self.create_mock_metric_field("CPUUtilization", "CPU使用率", "CPU使用率", "%", ["InstanceId"])
        ]
        mock_metric_queryset = MagicMock()
        mock_metric_queryset.values.return_value = mock_metric_fields
        mock_metric_model.objects.filter.return_value = mock_metric_queryset

        # Mock API call failure
        mock_api_call.side_effect = Exception("External API error")

        # 2. Action: Query product configuration
        resource = CloudProductConfigResource()
        request_data = {"namespace": "QCE/CVM"}
        result = resource.perform_request(request_data)

        # 3. Assertions: Should handle API failure gracefully
        assert result["tags"] == {"env": "环境"}, "Should still return tags from ORM"
        assert result["filters"] == {}, "Should return empty filters on API failure"
        assert len(result["metrics"]) == 1, "Should still return metrics from ORM"

    @patch("packages.monitor_web.collecting.resources.qcloud.api.qcloud_monitor.query_instance_filters")
    @patch("monitor_web.models.qcloud.CloudProductMetric")
    @patch("monitor_web.models.qcloud.CloudProductTagField")
    def test_filters_with_null_dimensions(self, mock_tag_model, mock_metric_model, mock_api_call):
        """
        Test handling of metrics with null dimensions.
        """
        # 1. Setup: Mock metric with null dimensions
        mock_tag_queryset = MagicMock()
        mock_tag_queryset.values.return_value = []
        mock_tag_model.objects.filter.return_value = mock_tag_queryset

        mock_metric_fields = [
            self.create_mock_metric_field("TestMetric", "测试指标", "测试", "count", None)  # None dimensions
        ]
        mock_metric_queryset = MagicMock()
        mock_metric_queryset.values.return_value = mock_metric_fields
        mock_metric_model.objects.filter.return_value = mock_metric_queryset

        mock_api_response = {"namespace": "QCE/TEST", "filters": []}
        mock_api_call.return_value = mock_api_response

        # 2. Action: Query product configuration
        resource = CloudProductConfigResource()
        request_data = {"namespace": "QCE/TEST"}
        result = resource.perform_request(request_data)

        # 3. Assertions: Should handle null dimensions
        assert len(result["metrics"]) == 1
        metric = result["metrics"][0]
        assert metric["dimensions"] == [], "Should convert None dimensions to empty list"

    def test_request_serializer_validation(self):
        """
        Test the request serializer validation.
        """
        resource = CloudProductConfigResource()

        # Test with valid data
        valid_data = {"namespace": "QCE/CVM"}
        serializer = resource.RequestSerializer(data=valid_data)
        assert serializer.is_valid(), f"Serializer should be valid: {serializer.errors}"

        # Test with missing required fields
        invalid_data = {}  # Missing namespace
        serializer = resource.RequestSerializer(data=invalid_data)
        assert not serializer.is_valid(), "Serializer should be invalid without namespace"

    def test_response_serializer_structure(self):
        """
        Test the response serializer structure.
        """
        resource = CloudProductConfigResource()

        sample_response = {
            "tags": {"env": "环境", "app": "应用"},
            "filters": {"Domain": "Domain", "ProjectId": "ProjectId"},
            "metrics": [
                {
                    "metric_name": "CPUUtilization",
                    "display_name": "CPU使用率",
                    "description": "CPU使用百分比",
                    "unit": "%",
                    "dimensions": ["InstanceId"],
                }
            ],
        }

        serializer = resource.ResponseSerializer(data=sample_response)
        assert serializer.is_valid(), f"Response serializer should be valid: {serializer.errors}"

    @patch("monitor_web.models.qcloud.CloudProductTagField")
    def test_get_tags_from_orm_method(self, mock_tag_model):
        """
        Test the _get_tags_from_orm method specifically.
        """
        # 1. Setup: Mock tag fields
        mock_tag_fields = [
            self.create_mock_tag_field("env", "环境"),
            self.create_mock_tag_field("app", ""),  # Empty display_name
        ]
        mock_queryset = MagicMock()
        mock_queryset.values.return_value = mock_tag_fields
        mock_tag_model.objects.filter.return_value = mock_queryset

        # 2. Action: Call the method
        resource = CloudProductConfigResource()
        tags = resource._get_tags_from_orm("QCE/CVM")

        # 3. Assertions
        expected_tags = {
            "env": "环境",
            "app": "app",  # Should fallback to tag_name
        }
        assert tags == expected_tags

    @patch("packages.monitor_web.collecting.resources.qcloud.api.qcloud_monitor.query_instance_filters")
    def test_get_filters_from_api_method(self, mock_api_call):
        """
        Test the _get_filters_from_api method specifically.
        """
        # 1. Setup: Mock API response
        mock_api_response = {"namespace": "QCE/CVM", "filters": ["Domain", "ProjectId", "VpcId"]}
        mock_api_call.return_value = mock_api_response

        # 2. Action: Call the method
        resource = CloudProductConfigResource()
        filters = resource._get_filters_from_api("QCE/CVM")

        # 3. Assertions
        expected_filters = {"Domain": "Domain", "ProjectId": "ProjectId", "VpcId": "VpcId"}
        assert filters == expected_filters

    @patch("monitor_web.models.qcloud.CloudProductMetric")
    def test_get_metrics_from_orm_method(self, mock_metric_model):
        """
        Test the _get_metrics_from_orm method specifically.
        """
        # 1. Setup: Mock metric fields
        mock_metric_fields = [
            self.create_mock_metric_field("CPUUtilization", "CPU使用率", "CPU使用率", "%", ["InstanceId"]),
            self.create_mock_metric_field("MemoryUtilization", "", "内存使用率", "", None),  # Test defaults
        ]
        mock_queryset = MagicMock()
        mock_queryset.values.return_value = mock_metric_fields
        mock_metric_model.objects.filter.return_value = mock_queryset

        # 2. Action: Call the method
        resource = CloudProductConfigResource()
        metrics = resource._get_metrics_from_orm("QCE/CVM")

        # 3. Assertions
        assert len(metrics) == 2

        cpu_metric = metrics[0]
        assert cpu_metric["metric_name"] == "CPUUtilization"
        assert cpu_metric["display_name"] == "CPU使用率"
        assert cpu_metric["unit"] == "%"

        mem_metric = metrics[1]
        assert mem_metric["metric_name"] == "MemoryUtilization"
        assert mem_metric["display_name"] == "MemoryUtilization"  # Fallback to metric_name
        assert mem_metric["unit"] == ""  # Empty string for empty unit
        assert mem_metric["dimensions"] == []  # None converted to empty list


class TestCloudMonitoringTaskListResource:
    """
    Test suite for CloudMonitoringTaskListResource.
    Focuses on verifying the task list functionality including pagination and search.
    """

    def create_mock_task(
        self, task_id, bk_biz_id, namespace, collect_name, update_time, latest_datapoint=None, update_by="admin"
    ):
        """Helper method to create mock CloudMonitoringTask"""
        mock_task = Mock()
        mock_task.task_id = task_id
        mock_task.bk_biz_id = bk_biz_id
        mock_task.namespace = namespace
        mock_task.collect_name = collect_name
        mock_task.update_time = update_time
        mock_task.latest_datapoint = latest_datapoint
        mock_task.update_by = update_by
        return mock_task

    def create_mock_region(self, task_id, region_id, region_code):
        """Helper method to create mock CloudMonitoringTaskRegion"""
        mock_region = Mock()
        mock_region.task_id = task_id
        mock_region.region_id = region_id
        mock_region.region_code = region_code
        return mock_region

    @patch("monitor_web.models.qcloud.CloudMonitoringTaskRegion")
    @patch("monitor_web.models.qcloud.CloudProduct")
    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    def test_get_task_list_basic(self, mock_task_model, mock_product_model, mock_region_model):
        """
        Test basic task list retrieval without search or pagination.
        """
        # 1. Setup: Mock tasks
        from datetime import datetime

        mock_time = datetime(2025, 8, 1, 12, 0, 0)
        mock_datapoint = datetime(2025, 8, 1, 11, 50, 0)

        mock_tasks = [
            self.create_mock_task("task1", 1, "QCE/CVM", "CVM监控", mock_time, mock_datapoint),
            self.create_mock_task("task2", 1, "QCE/CDB", "CDB监控", mock_time),
        ]

        # Mock tasks queryset with chained method calls
        mock_queryset = MagicMock()
        mock_queryset.__iter__ = Mock(return_value=iter(mock_tasks))
        mock_queryset.count.return_value = len(mock_tasks)
        mock_queryset.__getitem__ = (
            lambda self, idx: mock_tasks[idx] if isinstance(idx, int) else mock_tasks[idx.start : idx.stop]
        )

        # Mock chained method calls
        mock_select_related = MagicMock()
        mock_select_related.__iter__ = Mock(return_value=iter(mock_tasks))
        mock_select_related.count.return_value = len(mock_tasks)
        mock_select_related.__getitem__ = (
            lambda self, idx: mock_tasks[idx] if isinstance(idx, int) else mock_tasks[idx.start : idx.stop]
        )
        mock_select_related.order_by.return_value = mock_select_related

        mock_queryset.select_related.return_value = mock_select_related
        mock_task_model.objects.filter.return_value = mock_queryset

        # Mock product information
        mock_products = [
            Mock(namespace="QCE/CVM", product_name="云服务器 CVM"),
            Mock(namespace="QCE/CDB", product_name="云数据库 MySQL"),
        ]
        mock_product_queryset = MagicMock()
        mock_product_queryset.__iter__ = Mock(return_value=iter(mock_products))
        mock_product_model.objects.filter.return_value = mock_product_queryset

        # Mock region configurations
        def mock_filter_regions(**kwargs):
            task_id = kwargs.get("task_id")
            is_deleted = kwargs.get("is_deleted")

            mock_region_queryset = MagicMock()

            # 只有当 is_deleted=False 时才返回地域数据
            if is_deleted is False:
                if task_id == "task1":
                    regions = [
                        self.create_mock_region("task1", 0, "ap-beijing"),
                        self.create_mock_region("task1", 1, "ap-shanghai"),
                    ]
                    mock_region_queryset.__iter__ = Mock(return_value=iter(regions))
                    mock_region_queryset.__bool__ = lambda self: True  # 确保 if region_configs 为真
                    mock_region_queryset.order_by.return_value = mock_region_queryset  # 添加 order_by 支持
                elif task_id == "task2":
                    regions = [
                        self.create_mock_region("task2", 0, "ap-guangzhou"),
                    ]
                    mock_region_queryset.__iter__ = Mock(return_value=iter(regions))
                    mock_region_queryset.__bool__ = lambda self: True  # 确保 if region_configs 为真
                    mock_region_queryset.order_by.return_value = mock_region_queryset  # 添加 order_by 支持
                else:
                    regions = []
                    mock_region_queryset.__iter__ = Mock(return_value=iter(regions))
                    mock_region_queryset.__bool__ = lambda self: False  # 确保 if region_configs 为假
                    mock_region_queryset.order_by.return_value = mock_region_queryset  # 添加 order_by 支持
            else:
                # 当 is_deleted != False 时，返回空查询集
                regions = []
                mock_region_queryset.__iter__ = Mock(return_value=iter(regions))
                mock_region_queryset.__bool__ = lambda self: False  # 确保 if region_configs 为假
                mock_region_queryset.order_by.return_value = mock_region_queryset  # 添加 order_by 支持

            return mock_region_queryset

        mock_region_model.objects.filter.side_effect = mock_filter_regions

        # 2. Action: Get task list
        resource = CloudMonitoringTaskListResource()
        request_data = {"bk_biz_id": 1}
        result = resource.perform_request(request_data)

        # 打印接口返回的数据
        print("\n" + "=" * 60)
        print("任务列表接口返回数据:")
        print(f"请求参数: {request_data}")
        print(f"任务总数: {result.get('total', 0)}")
        print(f"当前页码: {result.get('page', 0)}")
        print(f"每页数量: {result.get('page_size', 0)}")
        print("任务列表:")
        for i, task in enumerate(result.get("tasks", [])):
            print(f"  {i + 1}. {task}")
        print("=" * 60 + "\n")

        # 3. Assertions
        # Verify basic query
        mock_task_model.objects.filter.assert_called_once_with(bk_biz_id=1, is_deleted=False)

        # Verify product information query
        mock_product_model.objects.filter.assert_called_once()

        # Verify result structure
        assert result["total"] == 2, "Should return 2 tasks"
        assert result["page"] == 1, "Default page should be 1"
        assert result["page_size"] == 20, "Default page_size should be 20"
        assert len(result["tasks"]) == 2, "Should return 2 tasks in the list"

        # Verify task details
        task1 = result["tasks"][0]
        assert task1["task_id"] == "task1"
        assert task1["collect_name"] == "CVM监控"
        assert task1["product_name"] == "云服务器 CVM"
        assert len(task1["regions"]) == 2
        assert [{"id": 0, "region": "ap-beijing"}, {"id": 1, "region": "ap-shanghai"}] == task1["regions"]
        assert task1["latest_datapoint"] is not None

        task2 = result["tasks"][1]
        assert task2["task_id"] == "task2"
        assert task2["collect_name"] == "CDB监控"
        assert task2["product_name"] == "云数据库 MySQL"
        assert len(task2["regions"]) == 1
        assert [{"id": 0, "region": "ap-guangzhou"}] == task2["regions"]
        assert task2["latest_datapoint"] is None

    @patch("monitor_web.models.qcloud.CloudMonitoringTaskRegion")
    @patch("monitor_web.models.qcloud.CloudProduct")
    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    def test_task_list_with_pagination(self, mock_task_model, mock_product_model, mock_region_model):
        """
        Test task list with pagination.
        """
        # 1. Setup: Mock tasks
        from datetime import datetime

        mock_time = datetime(2025, 8, 1, 12, 0, 0)

        # Create 25 mock tasks for pagination testing
        mock_tasks = []
        for i in range(25):
            task_id = f"task{i + 1}"
            namespace = "QCE/CVM" if i % 2 == 0 else "QCE/CDB"
            collect_name = f"监控任务 {i + 1}"
            mock_tasks.append(self.create_mock_task(task_id, 1, namespace, collect_name, mock_time))

        # Mock tasks queryset with chained method calls
        mock_queryset = MagicMock()
        mock_queryset.count.return_value = len(mock_tasks)
        mock_queryset.__getitem__ = (
            lambda self, idx: mock_tasks[idx] if isinstance(idx, int) else mock_tasks[idx.start : idx.stop]
        )

        # Mock chained method calls
        mock_select_related = MagicMock()
        mock_select_related.count.return_value = len(mock_tasks)
        mock_select_related.__getitem__ = (
            lambda self, idx: mock_tasks[idx] if isinstance(idx, int) else mock_tasks[idx.start : idx.stop]
        )
        mock_select_related.order_by.return_value = mock_select_related

        mock_queryset.select_related.return_value = mock_select_related
        mock_task_model.objects.filter.return_value = mock_queryset

        # Mock product information
        mock_products = [
            Mock(namespace="QCE/CVM", product_name="云服务器 CVM"),
            Mock(namespace="QCE/CDB", product_name="云数据库 MySQL"),
        ]
        mock_product_queryset = MagicMock()
        mock_product_queryset.__iter__ = Mock(return_value=iter(mock_products))
        mock_product_model.objects.filter.return_value = mock_product_queryset

        # Mock basic region configurations
        mock_region_queryset = MagicMock()
        mock_region_queryset.__iter__ = Mock(return_value=iter([]))
        mock_region_model.objects.filter.return_value = mock_region_queryset

        # 2. Action: Get task list with pagination
        resource = CloudMonitoringTaskListResource()

        # Test page 1
        page1_data = {"bk_biz_id": 1, "page": 1, "page_size": 10}
        page1_result = resource.perform_request(page1_data)

        # Test page 2
        page2_data = {"bk_biz_id": 1, "page": 2, "page_size": 10}
        page2_result = resource.perform_request(page2_data)

        # Test page 3
        page3_data = {"bk_biz_id": 1, "page": 3, "page_size": 10}
        page3_result = resource.perform_request(page3_data)

        # 3. Assertions
        # Page 1
        assert page1_result["total"] == 25, "Total should be 25 tasks"
        assert page1_result["page"] == 1
        assert page1_result["page_size"] == 10
        assert len(page1_result["tasks"]) == 10, "Page 1 should have 10 tasks"
        assert page1_result["tasks"][0]["task_id"] == "task1"
        assert page1_result["tasks"][9]["task_id"] == "task10"

        # Page 2
        assert page2_result["total"] == 25
        assert page2_result["page"] == 2
        assert page2_result["page_size"] == 10
        assert len(page2_result["tasks"]) == 10, "Page 2 should have 10 tasks"
        assert page2_result["tasks"][0]["task_id"] == "task11"
        assert page2_result["tasks"][9]["task_id"] == "task20"

        # Page 3
        assert page3_result["total"] == 25
        assert page3_result["page"] == 3
        assert page3_result["page_size"] == 10
        assert len(page3_result["tasks"]) == 5, "Page 3 should have 5 tasks"
        assert page3_result["tasks"][0]["task_id"] == "task21"
        assert page3_result["tasks"][4]["task_id"] == "task25"

    @patch("monitor_web.models.qcloud.CloudMonitoringTaskRegion")
    @patch("monitor_web.models.qcloud.CloudProduct")
    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    def test_task_list_with_search(self, mock_task_model, mock_product_model, mock_region_model):
        """
        Test task list with search functionality.
        """
        # 1. Setup: Mock tasks
        from datetime import datetime

        mock_time = datetime(2025, 8, 1, 12, 0, 0)

        # Create mock tasks
        mock_tasks = [
            self.create_mock_task("task1", 1, "QCE/CVM", "Web服务器监控", mock_time, update_by="user1"),
            self.create_mock_task("task2", 1, "QCE/CDB", "MySQL数据库监控", mock_time, update_by="user2"),
            self.create_mock_task("task3", 1, "QCE/CLB", "负载均衡监控", mock_time, update_by="admin"),
        ]

        # 为了更明确地追踪和控制每个链式调用的行为，我们创建单独的mock对象
        filtered_result = MagicMock()
        filtered_result.__iter__ = Mock(return_value=iter([mock_tasks[0]]))
        filtered_result.__getitem__ = (
            lambda self, idx: [mock_tasks[0]][idx] if isinstance(idx, int) else [mock_tasks[0]][idx.start : idx.stop]
        )
        filtered_result.count.return_value = 1

        # 创建表示 order_by 结果的mock
        order_by_result = MagicMock()
        order_by_result.filter.return_value = filtered_result

        # 创建表示 select_related 结果的mock
        select_related_result = MagicMock()
        select_related_result.order_by.return_value = order_by_result

        # 创建初始查询结果的mock
        base_query_result = MagicMock()
        base_query_result.select_related.return_value = select_related_result

        mock_task_model.objects.filter.return_value = base_query_result

        # Mock region configurations
        mock_region_queryset = MagicMock()
        mock_region_queryset.__iter__ = Mock(return_value=iter([self.create_mock_region("task1", 0, "ap-beijing")]))
        mock_region_queryset.__bool__ = lambda self: True
        mock_region_model.objects.filter.return_value = mock_region_queryset

        # Mock product namespaces for product_name search
        def mock_product_filter(**kwargs):
            product_queryset = MagicMock()
            # When searching for product_name containing "服务器"
            if kwargs.get("product_name__icontains") == "服务器":
                product_queryset.values_list.return_value = ["QCE/CVM"]  # Return CVM namespace
            else:
                product_queryset.values_list.return_value = []
            return product_queryset

        mock_product_model.objects.filter.side_effect = mock_product_filter

        # 2. Action: Search for tasks
        resource = CloudMonitoringTaskListResource()
        search_data = {"bk_biz_id": 1, "search": "服务器"}
        search_result = resource.perform_request(search_data)

        # 3. Assertions
        assert search_result["total"] == 1, "Search should return 1 task"
        assert len(search_result["tasks"]) == 1
        assert search_result["tasks"][0]["task_id"] == "task1"
        assert search_result["tasks"][0]["collect_name"] == "Web服务器监控"

        # Verify product name search query
        mock_product_model.objects.filter.assert_any_call(product_name__icontains="服务器", is_deleted=False)

    @patch("monitor_web.models.qcloud.CloudMonitoringTaskRegion")
    @patch("monitor_web.models.qcloud.CloudProduct")
    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    def test_empty_task_list(self, mock_task_model, mock_product_model, mock_region_model):
        """
        Test behavior when no tasks are found.
        """

        # 1. Setup: Mock empty tasks queryset with chained methods
        def create_empty_chain_mock():
            """创建一个带有所有链式方法的空结果mock对象"""
            m = MagicMock()
            m.__iter__ = Mock(return_value=iter([]))
            m.count.return_value = 0
            m.__getitem__ = lambda self, idx: [][idx] if isinstance(idx, int) else [][idx.start : idx.stop]

            # 支持链式调用
            m.select_related.return_value = m
            m.order_by.return_value = m
            m.filter.return_value = m

            return m

        # 为任务查询创建一个空结果的mock
        mock_empty_queryset = create_empty_chain_mock()
        mock_task_model.objects.filter.return_value = mock_empty_queryset

        # Mock empty product queryset
        mock_product_queryset = MagicMock()
        mock_product_queryset.__iter__ = Mock(return_value=iter([]))
        mock_product_model.objects.filter.return_value = mock_product_queryset

        # Mock empty region queryset
        mock_region_queryset = MagicMock()
        mock_region_queryset.__iter__ = Mock(return_value=iter([]))
        mock_region_model.objects.filter.return_value = mock_region_queryset

        # 2. Action: Get task list for non-existent business
        resource = CloudMonitoringTaskListResource()
        request_data = {"bk_biz_id": 999}  # Non-existent business ID
        result = resource.perform_request(request_data)

        # 3. Assertions
        assert result["total"] == 0, "Should return 0 tasks"
        assert len(result["tasks"]) == 0, "Tasks list should be empty"
        assert result["page"] == 1
        assert result["page_size"] == 20

    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    def test_exception_handling(self, mock_task_model):
        """
        Test exception handling in task list retrieval.
        """
        # 1. Setup: Mock exception
        mock_task_model.objects.filter.side_effect = Exception("Database error")

        # 2. Action & Assertions: Expect exception
        resource = CloudMonitoringTaskListResource()
        request_data = {"bk_biz_id": 1}

        try:
            resource.perform_request(request_data)
            assert False, "Should raise exception on database error"
        except Exception as e:
            assert "查询任务列表失败" in str(e)

    def test_request_serializer_validation(self):
        """
        Test the request serializer validation.
        """
        resource = CloudMonitoringTaskListResource()

        # Test with valid required data
        valid_data = {"bk_biz_id": 1}
        serializer = resource.RequestSerializer(data=valid_data)
        assert serializer.is_valid(), f"Serializer should be valid with required data: {serializer.errors}"

        # Test with complete data
        complete_data = {"bk_biz_id": 1, "page": 2, "page_size": 15, "search": "服务器"}
        serializer = resource.RequestSerializer(data=complete_data)
        assert serializer.is_valid(), f"Serializer should be valid with complete data: {serializer.errors}"

        # Test with invalid data (missing bk_biz_id)
        invalid_data = {"page": 1, "page_size": 10}
        serializer = resource.RequestSerializer(data=invalid_data)
        assert not serializer.is_valid(), "Serializer should be invalid without bk_biz_id"

        # Test with invalid data types
        invalid_types = {"bk_biz_id": "not_an_integer", "page": "not_an_integer"}
        serializer = resource.RequestSerializer(data=invalid_types)
        assert not serializer.is_valid(), "Serializer should be invalid with wrong data types"

    def test_response_serializer_structure(self):
        """
        Test the response serializer structure.
        """
        resource = CloudMonitoringTaskListResource()

        from datetime import datetime

        mock_time_str = datetime(2025, 8, 1, 12, 0, 0).strftime("%Y-%m-%d %H:%M:%S %z")

        sample_response = {
            "total": 2,
            "page": 1,
            "page_size": 20,
            "tasks": [
                {
                    "task_id": "task1",
                    "collect_name": "CVM监控",
                    "product_name": "云服务器 CVM",
                    "latest_datapoint": mock_time_str,
                    "regions": ["ap-beijing", "ap-shanghai"],
                    "latest_updater": "admin",
                    "latest_update_time": mock_time_str,
                },
                {
                    "task_id": "task2",
                    "collect_name": "CDB监控",
                    "product_name": "云数据库 MySQL",
                    "latest_datapoint": None,
                    "regions": ["ap-guangzhou"],
                    "latest_updater": "user1",
                    "latest_update_time": mock_time_str,
                },
            ],
        }

        serializer = resource.ResponseSerializer(data=sample_response)
        assert serializer.is_valid(), f"Response serializer should be valid: {serializer.errors}"


class TestCloudMonitoringTaskDetailResource:
    """
    Test suite for CloudMonitoringTaskDetailResource.
    Focuses on verifying the task detail retrieval functionality including credential masking.
    """

    def create_mock_task(
        self, task_id, bk_biz_id, namespace, collect_name, collect_interval, collect_timeout, secret_id, secret_key
    ):
        """Helper method to create mock CloudMonitoringTask"""
        mock_task = Mock()
        mock_task.task_id = task_id
        mock_task.bk_biz_id = bk_biz_id
        mock_task.namespace = namespace
        mock_task.collect_name = collect_name
        mock_task.collect_interval = collect_interval
        mock_task.collect_timeout = collect_timeout
        mock_task.secret_id = secret_id
        mock_task.secret_key = secret_key
        return mock_task

    def create_mock_region_config(
        self,
        task_id,
        region_id,
        region_code,
        tags_config=None,
        filters_config=None,
        selected_metrics=None,
        dimensions_config=None,
    ):
        """Helper method to create mock CloudMonitoringTaskRegion"""
        mock_region = Mock()
        mock_region.task_id = task_id
        mock_region.region_id = region_id
        mock_region.region_code = region_code
        mock_region.tags_config = tags_config or []
        mock_region.filters_config = filters_config or []
        mock_region.selected_metrics = selected_metrics or []
        mock_region.dimensions_config = dimensions_config or []
        return mock_region

    @patch("monitor_web.models.qcloud.CloudMonitoringTaskRegion")
    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    def test_get_task_detail_success(self, mock_task_model, mock_region_model):
        """
        Test successful retrieval of task detail with credential masking.
        """
        # 1. Setup: Mock task
        mock_task = self.create_mock_task(
            task_id="test_task_123",
            bk_biz_id=1,
            namespace="QCE/CVM",
            collect_name="生产环境CVM监控",
            collect_interval="1m",
            collect_timeout="30s",
            secret_id="TESTtesttesttesttestID",
            secret_key="TESTtesttesttesttesttesttesttesttestKEY",
        )
        mock_task_model.objects.get.return_value = mock_task

        # Mock region configurations
        mock_regions = [
            self.create_mock_region_config(
                task_id="test_task_123",
                region_id=1,
                region_code="ap-beijing",
                tags_config=[{"name": "env", "values": ["production"], "fuzzy": False}],
                filters_config=[{"name": "instance-state-name", "values": ["running"]}],
                selected_metrics=["CPUUtilization", "MemoryUtilization"],
                dimensions_config=[
                    {"action": "add_dimension", "dimension_key": "env", "dimension_value": "production"}
                ],
            ),
            self.create_mock_region_config(
                task_id="test_task_123",
                region_id=2,
                region_code="ap-shanghai",
                tags_config=[{"name": "app", "values": ["web"], "fuzzy": True}],
                filters_config=[{"name": "vpc-id", "values": ["vpc-12345"]}],
                selected_metrics=["DiskUsage", "NetworkIn"],
                dimensions_config=[],
            ),
        ]

        mock_region_queryset = MagicMock()
        mock_region_queryset.__iter__ = Mock(return_value=iter(mock_regions))
        mock_region_queryset.order_by.return_value = mock_region_queryset
        mock_region_model.objects.filter.return_value = mock_region_queryset

        # 2. Action: Get task detail
        resource = CloudMonitoringTaskDetailResource()
        request_data = {"bk_biz_id": 1, "task_id": "test_task_123"}
        result = resource.perform_request(request_data)

        # 打印接口返回的数据
        print("\n" + "=" * 60)
        print("任务详情接口返回数据:")
        print(f"请求参数: {request_data}")
        print(f"任务ID: {result.get('task_id')}")
        print(f"业务ID: {result.get('bk_biz_id')}")
        print(f"资源名称: {result.get('resource_name')}")
        print(f"采集间隔: {result.get('collect_interval')}")
        print(f"采集超时: {result.get('collect_timeout')}")
        print(f"地域数量: {len(result.get('regions', []))}")
        print("地域配置详情:")
        for i, region in enumerate(result.get("regions", [])):
            print(f"  地域 {i + 1}: {region}")
        print("=" * 60 + "\n")

        # 3. Assertions: Verify model queries
        mock_task_model.objects.get.assert_called_once_with(task_id="test_task_123", bk_biz_id=1, is_deleted=False)
        mock_region_model.objects.filter.assert_called_once_with(task_id="test_task_123", is_deleted=False)

        # Verify basic response structure
        assert result["task_id"] == "test_task_123"
        assert result["bk_biz_id"] == 1
        assert result["collect_interval"] == "1m"
        assert result["collect_timeout"] == "30s"
        assert result["resource_name"] == "生产环境CVM监控"

        assert result["secret_id"] == "TES****************tID"  # Should be masked: 前3个 + *** + 后3个

        # Verify regions structure
        assert len(result["regions"]) == 2

        # Verify first region
        region1 = result["regions"][0]
        assert region1["region"] == "ap-beijing"
        assert region1["id"] == 1
        assert region1["instance_selection"]["tags"] == [{"name": "env", "values": ["production"], "fuzzy": False}]
        assert region1["instance_selection"]["filters"] == [{"name": "instance-state-name", "values": ["running"]}]
        assert region1["selected_metrics"] == ["CPUUtilization", "MemoryUtilization"]
        assert region1["dimensions"] == [
            {"action": "add_dimension", "dimension_key": "env", "dimension_value": "production"}
        ]

        # Verify second region
        region2 = result["regions"][1]
        assert region2["region"] == "ap-shanghai"
        assert region2["id"] == 2
        assert region2["instance_selection"]["tags"] == [{"name": "app", "values": ["web"], "fuzzy": True}]
        assert region2["instance_selection"]["filters"] == [{"name": "vpc-id", "values": ["vpc-12345"]}]
        assert region2["selected_metrics"] == ["DiskUsage", "NetworkIn"]
        assert region2["dimensions"] == []

    def test_mask_secret_id_method(self):
        """
        Test the _mask_secret_id method with various input scenarios.
        """
        resource = CloudMonitoringTaskDetailResource()

        # Test normal secret_id
        normal_secret_id = "TEST1234567890abcdefghijklmn"
        masked = resource._mask_secret_id(normal_secret_id)
        assert masked == "TES**********************lmn", f"Expected 'TES**********************lmn', got '{masked}'"

        # Test short secret_id (length <= 6)
        short_secret_id = "TEST12"
        masked_short = resource._mask_secret_id(short_secret_id)
        assert masked_short == "******", f"Expected '******', got '{masked_short}'"

        # Test very short secret_id
        very_short = "TE"
        masked_very_short = resource._mask_secret_id(very_short)
        assert masked_very_short == "**", f"Expected '**', got '{masked_very_short}'"

        # Test empty string
        empty_secret = ""
        masked_empty = resource._mask_secret_id(empty_secret)
        assert masked_empty == "", f"Expected '', got '{masked_empty}'"

        # Test None
        none_secret = None
        masked_none = resource._mask_secret_id(none_secret)
        assert masked_none == "", f"Expected '', got '{masked_none}'"

        # Test exactly 6 characters
        six_chars = "TEST12"
        masked_six = resource._mask_secret_id(six_chars)
        assert masked_six == "******", f"Expected '******', got '{masked_six}'"

        # Test 7 characters (just over the threshold)
        seven_chars = "TEST123"
        masked_seven = resource._mask_secret_id(seven_chars)
        assert masked_seven == "TES*123", f"Expected 'TES*123', got '{masked_seven}'"

        # Test longer secret_id
        long_secret_id = "TEST1234567890abcdefghijklmnopqrstuvwxyz"
        masked_long = resource._mask_secret_id(long_secret_id)
        expected_long = "TES" + "*" * (len(long_secret_id) - 6) + "xyz"
        assert masked_long == expected_long, f"Expected '{expected_long}', got '{masked_long}'"

    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    def test_get_task_detail_not_found(self, mock_task_model):
        """
        Test exception handling when task is not found.
        """
        # 1. Setup: Mock task not found
        from django.core.exceptions import ObjectDoesNotExist

        mock_task_model.DoesNotExist = ObjectDoesNotExist
        mock_task_model.objects.get.side_effect = ObjectDoesNotExist()

        # 2. Action & Assertions: Expect exception
        resource = CloudMonitoringTaskDetailResource()
        request_data = {"bk_biz_id": 1, "task_id": "nonexistent_task"}

        try:
            resource.perform_request(request_data)
            assert False, "Should raise exception for non-existent task"
        except Exception as e:
            assert "任务不存在" in str(e)
            assert "nonexistent_task" in str(e)

    def test_request_serializer_validation(self):
        """
        Test the request serializer validation.
        """
        resource = CloudMonitoringTaskDetailResource()

        # Test with valid data including task_id
        valid_data = {"bk_biz_id": 1, "task_id": "test_task_123"}
        serializer = resource.RequestSerializer(data=valid_data)
        assert serializer.is_valid(), f"Serializer should be valid with task_id: {serializer.errors}"

        # Test with valid data without task_id (task_id can now be provided as URL parameter)
        valid_without_task_id = {"bk_biz_id": 1}
        serializer = resource.RequestSerializer(data=valid_without_task_id)
        assert serializer.is_valid(), (
            f"Serializer should be valid without task_id (can be URL param): {serializer.errors}"
        )

        # Test with missing bk_biz_id
        missing_biz_id = {"task_id": "test_task_123"}
        serializer = resource.RequestSerializer(data=missing_biz_id)
        assert not serializer.is_valid(), "Serializer should be invalid without bk_biz_id"

    def test_response_serializer_structure(self):
        """
        Test the response serializer structure.
        """
        resource = CloudMonitoringTaskDetailResource()

        sample_response = {
            "task_id": "test_task_123",
            "bk_biz_id": 1,
            "collect_interval": "1m",
            "collect_timeout": "30s",
            "resource_name": "生产环境CVM监控",
            "secret_id": "TES****************tID",
            "regions": [
                {
                    "region": "ap-beijing",
                    "id": 1,
                    "instance_selection": {
                        "tags": [{"name": "env", "values": ["production"], "fuzzy": False}],
                        "filters": [{"name": "instance-state-name", "values": ["running"]}],
                    },
                    "selected_metrics": ["CPUUtilization", "MemoryUtilization"],
                    "dimensions": [
                        {"action": "add_dimension", "dimension_key": "env", "dimension_value": "production"}
                    ],
                },
            ],
        }

        serializer = resource.ResponseSerializer(data=sample_response)
        assert serializer.is_valid(), f"Response serializer should be valid: {serializer.errors}"

    @patch("monitor_web.models.qcloud.CloudMonitoringTaskRegion")
    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    def test_get_task_detail_from_url_param(self, mock_task_model, mock_region_model):
        """
        测试通过URL参数获取任务详情
        """
        # 1. Setup: Mock task
        mock_task = self.create_mock_task(
            task_id="test_task_123",
            bk_biz_id=1,
            namespace="QCE/CVM",
            collect_name="生产环境CVM监控",
            collect_interval="1m",
            collect_timeout="30s",
            secret_id="TESTtesttesttesttestID",
            secret_key="TESTtesttesttesttesttesttesttesttestKEY",
        )
        mock_task_model.objects.get.return_value = mock_task

        # Mock region configurations
        mock_regions = [
            self.create_mock_region_config(
                task_id="test_task_123",
                region_id=1,
                region_code="ap-beijing",
                tags_config=[],
                filters_config=[],
                selected_metrics=[],
                dimensions_config=[],
            )
        ]

        mock_region_queryset = MagicMock()
        mock_region_queryset.__iter__ = Mock(return_value=iter(mock_regions))
        mock_region_queryset.order_by.return_value = mock_region_queryset
        mock_region_model.objects.filter.return_value = mock_region_queryset

        # 2. Action: 通过URL参数task_id获取任务详情
        resource = CloudMonitoringTaskDetailResource()
        request_data = {"bk_biz_id": 1}
        task_id_from_url = "test_task_123"
        result = resource.perform_request(request_data, task_id=task_id_from_url)

        # 打印接口调用信息
        print("\n" + "=" * 60)
        print("测试URL参数task_id调用详情:")
        print(f"请求参数: {request_data}")
        print(f"URL参数task_id: {task_id_from_url}")
        print(f"返回任务ID: {result.get('task_id')}")
        print("=" * 60 + "\n")

        # 3. Assertions: 验证结果
        # 验证使用了URL中的task_id参数
        mock_task_model.objects.get.assert_called_once_with(task_id=task_id_from_url, bk_biz_id=1, is_deleted=False)
        assert result["task_id"] == task_id_from_url

    def test_missing_task_id(self):
        """
        测试当既没有URL参数也没有请求参数中的task_id时的错误处理
        """
        # 创建资源实例
        resource = CloudMonitoringTaskDetailResource()
        request_data = {"bk_biz_id": 1}

        # 期望抛出异常
        try:
            resource.perform_request(request_data)
            assert False, "应该抛出异常，因为没有提供task_id参数"
        except ValueError as e:
            assert "必须提供task_id参数" in str(e), f"期望错误消息包含'必须提供task_id参数'，实际为: {str(e)}"


class TestCloudMonitoringConfigResource:
    """
    Test suite for CloudMonitoringConfigResource.
    Focuses on verifying the task update functionality.
    """

    def create_mock_task(
        self, task_id, bk_biz_id, namespace, collect_name, collect_interval, collect_timeout, secret_id, secret_key
    ):
        """Helper method to create mock CloudMonitoringTask"""
        mock_task = Mock()
        mock_task.task_id = task_id
        mock_task.bk_biz_id = bk_biz_id
        mock_task.namespace = namespace
        mock_task.collect_name = collect_name
        mock_task.collect_interval = collect_interval
        mock_task.collect_timeout = collect_timeout
        mock_task.secret_id = secret_id
        mock_task.secret_key = secret_key
        mock_task.save = Mock()
        return mock_task

    def create_mock_region_config(
        self,
        task_id,
        region_id,
        region_code,
        tags_config=None,
        filters_config=None,
        selected_metrics=None,
        dimensions_config=None,
    ):
        """Helper method to create mock CloudMonitoringTaskRegion"""
        mock_region = Mock()
        mock_region.task_id = task_id
        mock_region.region_id = region_id
        mock_region.region_code = region_code
        mock_region.tags_config = tags_config or []
        mock_region.filters_config = filters_config or []
        mock_region.selected_metrics = selected_metrics or []
        mock_region.dimensions_config = dimensions_config or []
        mock_region.save = Mock()
        mock_region.delete = Mock()
        return mock_region

    @patch("packages.monitor_web.collecting.resources.qcloud.CloudMonitoringConfigResource._deploy_monitoring_task")
    @patch("packages.monitor_web.collecting.resources.qcloud.CloudMonitoringConfigResource._update_region_configs")
    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    def test_update_collect_name_success(self, mock_task_model, mock_update_regions, mock_deploy):
        """
        Test successful update of collect_name.
        """
        # 1. Setup: Mock task
        mock_task = self.create_mock_task(
            task_id="test_task_123",
            bk_biz_id=1,
            namespace="QCE/CVM",
            collect_name="Old Name",
            collect_interval="1m",
            collect_timeout="30s",
            secret_id="old_secret_id",
            secret_key="old_secret_key",
        )
        mock_task_model.objects.get.return_value = mock_task
        mock_task_model.DoesNotExist = Exception

        # 2. Action: Update only collect_name
        resource = CloudMonitoringConfigResource()
        request_data = {"bk_biz_id": 1, "task_id": "test_task_123", "collect_name": "New Name"}
        result = resource.perform_request(request_data)

        # 3. Assertions
        assert "监控采集任务更新成功" in result["message"]
        assert "collect_name" in result["message"]
        assert mock_task.collect_name == "New Name"
        assert mock_task.save.called
        assert mock_deploy.called
        assert not mock_update_regions.called  # No region updates

    @patch("packages.monitor_web.collecting.resources.qcloud.CloudMonitoringConfigResource._deploy_monitoring_task")
    @patch("packages.monitor_web.collecting.resources.qcloud.CloudMonitoringConfigResource._update_region_configs")
    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    def test_update_collect_interval_and_timeout_success(self, mock_task_model, mock_update_regions, mock_deploy):
        """
        Test successful update of collect_interval and collect_timeout.
        """
        # 1. Setup: Mock task
        mock_task = self.create_mock_task(
            task_id="test_task_123",
            bk_biz_id=1,
            namespace="QCE/CVM",
            collect_name="Test Name",
            collect_interval="1m",
            collect_timeout="30s",
            secret_id="old_secret_id",
            secret_key="old_secret_key",
        )
        mock_task_model.objects.get.return_value = mock_task
        mock_task_model.DoesNotExist = Exception

        # 2. Action: Update interval and timeout
        resource = CloudMonitoringConfigResource()
        request_data = {"bk_biz_id": 1, "task_id": "test_task_123", "collect_interval": "5m", "collect_timeout": "60s"}
        result = resource.perform_request(request_data)

        # 3. Assertions
        assert "监控采集任务更新成功" in result["message"]
        assert "collect_interval" in result["message"]
        assert "collect_timeout" in result["message"]
        assert mock_task.collect_interval == "5m"
        assert mock_task.collect_timeout == "60s"
        assert mock_task.save.called
        assert mock_deploy.called
        assert not mock_update_regions.called  # No region updates

    @patch("packages.monitor_web.collecting.resources.qcloud.CloudMonitoringConfigResource._deploy_monitoring_task")
    @patch("packages.monitor_web.collecting.resources.qcloud.CloudMonitoringConfigResource._update_region_configs")
    @patch("packages.monitor_web.collecting.resources.qcloud.CloudMonitoringConfigResource._validate_credentials")
    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    def test_update_credentials_success(
        self, mock_task_model, mock_validate_credentials, mock_update_regions, mock_deploy
    ):
        """
        Test successful update of credentials.
        """
        # 1. Setup: Mock task
        mock_task = self.create_mock_task(
            task_id="test_task_123",
            bk_biz_id=1,
            namespace="QCE/CVM",
            collect_name="Test Name",
            collect_interval="1m",
            collect_timeout="30s",
            secret_id="old_secret_id",
            secret_key="old_secret_key",
        )
        mock_task_model.objects.get.return_value = mock_task
        mock_task_model.DoesNotExist = Exception

        # 2. Action: Update credentials
        resource = CloudMonitoringConfigResource()
        request_data = {
            "bk_biz_id": 1,
            "task_id": "test_task_123",
            "secret_id": "new_secret_id",
            "secret_key": "new_secret_key",
        }
        result = resource.perform_request(request_data)

        # 3. Assertions
        assert "监控采集任务更新成功" in result["message"]
        assert "credentials" in result["message"]
        assert mock_task.secret_id == "new_secret_id"
        assert mock_task.secret_key == "new_secret_key"
        assert mock_validate_credentials.called
        assert mock_task.save.called
        assert mock_deploy.called
        assert not mock_update_regions.called  # No region updates

    @patch("packages.monitor_web.collecting.resources.qcloud.CloudMonitoringConfigResource._deploy_monitoring_task")
    @patch("monitor_web.models.qcloud.CloudMonitoringTaskRegion")
    @patch("packages.monitor_web.collecting.resources.qcloud.CloudMonitoringConfigResource._validate_regions")
    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    def test_update_regions_success(self, mock_task_model, mock_validate_regions, mock_region_model, mock_deploy):
        """
        Test successful update of regions configuration.
        """
        # 1. Setup: Mock task and regions
        mock_task = self.create_mock_task(
            task_id="test_task_123",
            bk_biz_id=1,
            namespace="QCE/CVM",
            collect_name="Test Name",
            collect_interval="1m",
            collect_timeout="30s",
            secret_id="test_secret_id",
            secret_key="test_secret_key",
        )
        mock_task_model.objects.get.return_value = mock_task
        mock_task_model.DoesNotExist = Exception

        # Existing region (will be updated)
        existing_region = self.create_mock_region_config(
            task_id="test_task_123",
            region_id=1,
            region_code="ap-beijing",
            tags_config=[],
            filters_config=[],
            selected_metrics=["CPUUtilization"],
        )

        # Existing region (will be deleted)
        region_to_delete = self.create_mock_region_config(
            task_id="test_task_123",
            region_id=2,
            region_code="ap-shanghai",
            tags_config=[],
            filters_config=[],
            selected_metrics=["CPUUtilization"],
        )

        # Mock region queryset
        mock_regions = {1: existing_region, 2: region_to_delete}
        mock_region_queryset = MagicMock()
        mock_region_queryset.filter.return_value = mock_regions.values()
        mock_region_model.objects.filter.return_value = mock_region_queryset
        mock_region_model.objects.create = Mock(return_value=Mock())

        # 2. Action: Update regions
        resource = CloudMonitoringConfigResource()

        # Apply mock to _update_region_configs method to use real implementation
        real_update_regions = resource._update_region_configs
        resource._update_region_configs = lambda task_id, regions: real_update_regions(task_id, regions)

        request_data = {
            "bk_biz_id": 1,
            "task_id": "test_task_123",
            "regions": [
                {
                    "id": 1,  # Existing region to update
                    "region": "ap-beijing",
                    "instance_selection": {
                        "tags": [{"name": "env", "values": ["prod"]}],
                        "filters": [{"name": "status", "values": ["running"]}],
                    },
                    "selected_metrics": ["CPUUtilization", "MemoryUsage"],
                },
                {
                    "id": 3,  # New region to add
                    "region": "ap-guangzhou",
                    "instance_selection": {"tags": [], "filters": []},
                    "selected_metrics": ["DiskUsage"],
                },
            ],
        }

        with patch.object(resource, "_get_task", return_value=mock_task):
            with patch.dict(mock_regions, {1: existing_region, 2: region_to_delete}, clear=True):
                with patch("monitor_web.models.qcloud.CloudMonitoringTaskRegion.objects.filter") as mock_filter:
                    mock_filter.return_value = mock_regions.values()
                    with patch("monitor_web.models.qcloud.CloudMonitoringTaskRegion.objects.create") as mock_create:
                        result = resource.perform_request(request_data)
                        # 验证创建新地域配置
                        assert mock_create.called, "Should create a new region config"

        # 3. Assertions
        assert "监控采集任务更新成功" in result["message"]
        assert "regions" in result["message"]
        assert mock_validate_regions.called
        assert mock_deploy.called

        # Check that existing region is updated and new region is created
        assert mock_task.save.called
        assert region_to_delete.delete.called  # Region 2 should be deleted

    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    def test_update_nonexistent_task(self, mock_task_model):
        """
        Test error handling when updating a non-existent task.
        """
        # 1. Setup: Mock task model to raise DoesNotExist
        from django.core.exceptions import ObjectDoesNotExist

        mock_task_model.DoesNotExist = ObjectDoesNotExist
        mock_task_model.objects.get.side_effect = ObjectDoesNotExist("Task does not exist")

        # 2. Action & Assertions: Expect exception to be raised
        resource = CloudMonitoringConfigResource()
        request_data = {"bk_biz_id": 1, "task_id": "nonexistent_task", "collect_name": "New Name"}

        try:
            resource.perform_request(request_data)
            assert False, "Should raise exception for non-existent task"
        except Exception as e:
            # The exception should be re-raised by the resource
            assert "Task does not exist" in str(e) or "任务不存在" in str(e)

    @patch("packages.monitor_web.collecting.resources.qcloud.CloudMonitoringConfigResource._deploy_monitoring_task")
    @patch("monitor_web.models.qcloud.CloudMonitoringTask")
    def test_no_fields_to_update(self, mock_task_model, mock_deploy):
        """
        Test when no fields need to be updated.
        """
        # 1. Setup: Mock task with existing values
        mock_task = self.create_mock_task(
            task_id="test_task_123",
            bk_biz_id=1,
            namespace="QCE/CVM",
            collect_name="Test Name",
            collect_interval="1m",
            collect_timeout="30s",
            secret_id="test_secret_id",
            secret_key="test_secret_key",
        )
        mock_task_model.objects.get.return_value = mock_task
        mock_task_model.DoesNotExist = Exception

        # 2. Action: Update with same values
        resource = CloudMonitoringConfigResource()
        request_data = {
            "bk_biz_id": 1,
            "task_id": "test_task_123",
            "collect_name": "Test Name",  # Same as existing
            "collect_interval": "1m",  # Same as existing
        }
        result = resource.perform_request(request_data)

        # 3. Assertions
        assert "没有需要更新的字段" in result["message"]
        assert not mock_task.save.called  # Should not save if no changes
        assert not mock_deploy.called  # Should not deploy if no changes
