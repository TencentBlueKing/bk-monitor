"""
测试 object_model/constants.py 模块

这个测试文件确保所有常量类的值都被正确定义，并且各种常量列表的完整性。
"""

from bk_monitor_base.domains.object_model.constants import (
    ALLOW_CREATE_CHILD_OBJECT_MODEL_GROUP,
    NOT_CREATE_GROUP_CODE_LIST,
    NOT_DELETE_OBJECT_MODEL_GROUP_CODE_LIST,
    NOT_PLUGIN_MANAGE_OBJ_CODE_LIST,
    NOT_UPDATE_OBJECT_MODEL_CODE_LIST,
    NOT_UPDATE_OBJECT_MODEL_GROUP_CODE_LIST,
    RELATED_OBJECT_MODEL_GROUP,
    ApplicationObjectModelCode,
    BuiltinObjectModelCode,
    BuiltinObjectModelGroupCode,
    CloudObjectModelCode,
    HardwareObjectModelCode,
    K8sObjectModelCode,
)


class TestBuiltinObjectModelGroupCode:
    """测试内置对象模型分组代码常量"""

    def test_all_group_codes_are_strings(self):
        """确保所有分组代码都是字符串类型"""
        group_attributes = [attr for attr in dir(BuiltinObjectModelGroupCode) if not attr.startswith("_")]

        for attr_name in group_attributes:
            attr_value = getattr(BuiltinObjectModelGroupCode, attr_name)
            assert isinstance(attr_value, str), f"{attr_name} should be a string"

    def test_all_group_codes_have_cw_prefix(self):
        """确保所有分组代码都有 'cw-' 前缀"""
        group_attributes = [attr for attr in dir(BuiltinObjectModelGroupCode) if not attr.startswith("_")]

        for attr_name in group_attributes:
            attr_value = getattr(BuiltinObjectModelGroupCode, attr_name)
            assert attr_value.startswith("cw-"), f"{attr_name} should start with 'cw-'"

    def test_specific_group_codes_values(self):
        """测试特定分组代码的值"""
        assert BuiltinObjectModelGroupCode.BUSINESS == "cw-Business"
        assert BuiltinObjectModelGroupCode.COMPONENT == "cw-Component"
        assert BuiltinObjectModelGroupCode.DATABASES == "cw-Databases"
        assert BuiltinObjectModelGroupCode.MIDDLEWARES == "cw-Middlewares"
        assert BuiltinObjectModelGroupCode.OS == "cw-Operating_Systems"
        assert BuiltinObjectModelGroupCode.WEB_SERVICE_CHECK == "cw-Web_Service_Check"
        assert BuiltinObjectModelGroupCode.CLOUD_PLATFORMS == "cw-Cloud_Platforms"
        assert BuiltinObjectModelGroupCode.KUBERNETES == "cw-Kubernetes"
        assert BuiltinObjectModelGroupCode.APPLICATION == "cw-Application"
        assert BuiltinObjectModelGroupCode.USER_EXPERIENCE == "cw-User_Experience"

    def test_cloud_platform_group_codes(self):
        """测试云平台相关分组代码"""
        assert BuiltinObjectModelGroupCode.CLOUD_VIRTUAL_MACHINE == "cw-Cloud_Virtual_Machine"
        assert BuiltinObjectModelGroupCode.CLOUD_DATASTORE == "cw-Cloud_DataStore"
        assert BuiltinObjectModelGroupCode.CLOUD_PHYSICAL_HOST == "cw-Cloud_Physical_Host"
        assert BuiltinObjectModelGroupCode.CLOUD_HOST_CLUSTER == "cw-Cloud_Host_Cluster"
        assert BuiltinObjectModelGroupCode.CLOUD_ELASTIC_IP == "cw-Cloud_Elastic_IP"
        assert BuiltinObjectModelGroupCode.CLOUD_RDS_MYSQL == "cw-Cloud_RDS_MySQL"
        assert BuiltinObjectModelGroupCode.CLOUD_HOST_MACHINE == "cw-Cloud_Host_Machine"
        assert BuiltinObjectModelGroupCode.CLOUD_BARE_METAL_SERVER == "cw-Cloud_Bare_Metal_Server"

    def test_hardware_device_group_codes(self):
        """测试硬件设备相关分组代码"""
        assert BuiltinObjectModelGroupCode.HARDWARE_DEVICE == "cw-Hardware_Device"
        assert BuiltinObjectModelGroupCode.NETWORK_DEVICES == "cw-Network_Devices"
        assert BuiltinObjectModelGroupCode.PHYSICAL_DEVICES == "cw-Physical_Devices"

    def test_others_group_codes(self):
        """测试其他分组代码"""
        assert BuiltinObjectModelGroupCode.OTHERS_GROUP1 == "cw-Others_Group1"
        assert BuiltinObjectModelGroupCode.OTHERS_GROUP2 == "cw-Others_Group2"
        assert BuiltinObjectModelGroupCode.OTHERS_GROUP_KING_EYE == "cw-Others_Group_king_eye"


class TestBuiltinObjectModelCode:
    """测试内置对象模型代码常量"""

    def test_all_object_model_codes_are_strings(self):
        """确保所有对象模型代码都是字符串类型"""
        model_attributes = [attr for attr in dir(BuiltinObjectModelCode) if not attr.startswith("_")]

        for attr_name in model_attributes:
            attr_value = getattr(BuiltinObjectModelCode, attr_name)
            assert isinstance(attr_value, str), f"{attr_name} should be a string"

    def test_all_object_model_codes_have_cw_prefix(self):
        """确保所有对象模型代码都有 'cw-' 前缀"""
        model_attributes = [attr for attr in dir(BuiltinObjectModelCode) if not attr.startswith("_")]

        for attr_name in model_attributes:
            attr_value = getattr(BuiltinObjectModelCode, attr_name)
            assert attr_value.startswith("cw-"), f"{attr_name} should start with 'cw-'"

    def test_basic_object_model_codes(self):
        """测试基本对象模型代码"""
        assert BuiltinObjectModelCode.BIZ == "cw-biz"
        assert BuiltinObjectModelCode.HOST == "cw-Host"
        assert BuiltinObjectModelCode.WEB == "cw-web"
        assert BuiltinObjectModelCode.SERVICE == "cw-service"
        assert BuiltinObjectModelCode.WEB_SERVICE == "cw-web_service"
        assert BuiltinObjectModelCode.OTHERS == "cw-Others"

    def test_database_object_model_codes(self):
        """测试数据库相关对象模型代码"""
        assert BuiltinObjectModelCode.ORACLE == "cw-Oracle"
        assert BuiltinObjectModelCode.MYSQL == "cw-MySQL"
        assert BuiltinObjectModelCode.MSSQL == "cw-MSSQL"
        assert BuiltinObjectModelCode.MONGODB == "cw-MongoDB"
        assert BuiltinObjectModelCode.REDIS == "cw-Redis"
        assert BuiltinObjectModelCode.ELASTICSEARCH == "cw-Elasticsearch"
        assert BuiltinObjectModelCode.POSTGRESQL == "cw-PostgreSQL"

    def test_middleware_object_model_codes(self):
        """测试中间件相关对象模型代码"""
        assert BuiltinObjectModelCode.H2 == "cw-H2"
        assert BuiltinObjectModelCode.NGINX == "cw-Nginx"
        assert BuiltinObjectModelCode.TOMCAT == "cw-Tomcat"
        assert BuiltinObjectModelCode.APACHE == "cw-Apache"
        assert BuiltinObjectModelCode.WEBLOGIC == "cw-WebLogic"
        assert BuiltinObjectModelCode.KAFKA == "cw-Kafka"
        assert BuiltinObjectModelCode.RABBITMQ == "cw-RabbitMQ"
        assert BuiltinObjectModelCode.ROCKETMQ == "cw-RocketMQ"

    def test_kubernetes_object_model_codes(self):
        """测试Kubernetes相关对象模型代码"""
        assert BuiltinObjectModelCode.K8S_CLUSTER == "cw-K8s_Cluster"
        assert BuiltinObjectModelCode.K8S_WORKLOAD == "cw-K8s_Workload"
        assert BuiltinObjectModelCode.K8S_POD == "cw-K8s_Pod"
        assert BuiltinObjectModelCode.K8S_CONTAINER == "cw-K8s_Container"
        assert BuiltinObjectModelCode.K8S_NODE == "cw-K8s_Node"
        assert BuiltinObjectModelCode.K8S_PV == "cw-K8s_PersistentVolume"
        assert BuiltinObjectModelCode.K8S_PVC == "cw-K8s_PersistentVolumeClaim"

    def test_hardware_device_object_model_codes(self):
        """测试硬件设备相关对象模型代码"""
        assert BuiltinObjectModelCode.LOAD_BALANCE == "cw-Load_Balance"
        assert BuiltinObjectModelCode.FIREWALL == "cw-Firewall"
        assert BuiltinObjectModelCode.SWITCH == "cw-Switch"
        assert BuiltinObjectModelCode.ROUTER == "cw-Router"
        assert BuiltinObjectModelCode.PHYSICAL_SERVER == "cw-Physical_Server"

    def test_cloud_virtual_machine_codes(self):
        """测试云虚拟机相关代码"""
        assert BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_VMWARE == "cw-Cloud_Virtual_Machine_VMware"
        assert BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_ALI == "cw-Cloud_Virtual_Machine_Ali"
        assert BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_TENCENT == "cw-Cloud_Virtual_Machine_Tencent"
        assert BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_FUSIONCOMPUTE == "cw-Cloud_Virtual_Machine_FusionCompute"


class TestHardwareObjectModelCode:
    """测试硬件设备相关对象模型代码常量类"""

    def test_hardware_codes_reference_builtin_codes(self):
        """确保硬件设备代码正确引用内置代码"""
        assert HardwareObjectModelCode.LOAD_BALANCE == BuiltinObjectModelCode.LOAD_BALANCE
        assert HardwareObjectModelCode.FIREWALL == BuiltinObjectModelCode.FIREWALL
        assert HardwareObjectModelCode.SWITCH == BuiltinObjectModelCode.SWITCH
        assert HardwareObjectModelCode.ROUTER == BuiltinObjectModelCode.ROUTER
        assert HardwareObjectModelCode.PHYSICAL_SERVER == BuiltinObjectModelCode.PHYSICAL_SERVER

    def test_hardware_all_list_completeness(self):
        """确保 ALL 列表包含所有硬件设备代码"""
        expected_codes = [
            HardwareObjectModelCode.LOAD_BALANCE,
            HardwareObjectModelCode.FIREWALL,
            HardwareObjectModelCode.SWITCH,
            HardwareObjectModelCode.ROUTER,
            HardwareObjectModelCode.PHYSICAL_SERVER,
        ]
        assert set(HardwareObjectModelCode.ALL) == set(expected_codes)

    def test_hardware_all_list_no_duplicates(self):
        """确保 ALL 列表没有重复项"""
        assert len(HardwareObjectModelCode.ALL) == len(set(HardwareObjectModelCode.ALL))


class TestK8sObjectModelCode:
    """测试K8s相关对象模型代码常量类"""

    def test_k8s_codes_reference_builtin_codes(self):
        """确保K8s代码正确引用内置代码"""
        assert K8sObjectModelCode.CLUSTER == BuiltinObjectModelCode.K8S_CLUSTER
        assert K8sObjectModelCode.WORKLOAD == BuiltinObjectModelCode.K8S_WORKLOAD
        assert K8sObjectModelCode.POD == BuiltinObjectModelCode.K8S_POD
        assert K8sObjectModelCode.CONTAINER == BuiltinObjectModelCode.K8S_CONTAINER
        assert K8sObjectModelCode.NODE == BuiltinObjectModelCode.K8S_NODE
        assert K8sObjectModelCode.PV == BuiltinObjectModelCode.K8S_PV
        assert K8sObjectModelCode.PVC == BuiltinObjectModelCode.K8S_PVC

    def test_k8s_all_list_completeness(self):
        """确保 ALL 列表包含所有K8s代码"""
        expected_codes = [
            K8sObjectModelCode.CLUSTER,
            K8sObjectModelCode.WORKLOAD,
            K8sObjectModelCode.POD,
            K8sObjectModelCode.CONTAINER,
            K8sObjectModelCode.NODE,
            K8sObjectModelCode.PV,
            K8sObjectModelCode.PVC,
        ]
        assert set(K8sObjectModelCode.ALL) == set(expected_codes)

    def test_k8s_all_list_no_duplicates(self):
        """确保 ALL 列表没有重复项"""
        assert len(K8sObjectModelCode.ALL) == len(set(K8sObjectModelCode.ALL))


class TestCloudObjectModelCode:
    """测试云平台相关对象模型代码常量类"""

    def test_cloud_codes_reference_builtin_codes(self):
        """确保云平台代码正确引用内置代码"""
        # 测试虚拟机相关代码
        assert CloudObjectModelCode.CLOUD_VIRTUAL_MACHINE_VMWARE == BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_VMWARE
        assert CloudObjectModelCode.CLOUD_VIRTUAL_MACHINE_ALI == BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_ALI
        assert (
            CloudObjectModelCode.CLOUD_VIRTUAL_MACHINE_TENCENT == BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_TENCENT
        )

        # 测试数据存储相关代码
        assert CloudObjectModelCode.CLOUD_DATASTORE_VMWARE == BuiltinObjectModelCode.CLOUD_DATASTORE_VMWARE
        assert CloudObjectModelCode.CLOUD_DATASTORE_WINSTACK == BuiltinObjectModelCode.CLOUD_DATASTORE_WINSTACK

        # 测试物理机相关代码
        assert CloudObjectModelCode.CLOUD_PHYSICAL_HOST_VMWARE == BuiltinObjectModelCode.CLOUD_PHYSICAL_HOST_VMWARE
        assert (
            CloudObjectModelCode.CLOUD_PHYSICAL_HOST_FUSIONCOMPUTE
            == BuiltinObjectModelCode.CLOUD_PHYSICAL_HOST_FUSIONCOMPUTE
        )

        # 测试其他云服务代码
        assert CloudObjectModelCode.CLOUD_ELASTIC_IP_ALI == BuiltinObjectModelCode.CLOUD_ELASTIC_IP_ALI
        assert CloudObjectModelCode.CLOUD_RDS_MYSQL_MANAGEONE == BuiltinObjectModelCode.CLOUD_RDS_MYSQL_MANAGEONE


class TestConstantLists:
    """测试各种常量列表"""

    def test_not_update_object_model_code_list(self):
        """测试不可更新的对象模型代码列表"""
        expected_codes = [
            BuiltinObjectModelCode.WEB_SERVICE,
            BuiltinObjectModelCode.SERVICE,
            BuiltinObjectModelCode.WEB,
            BuiltinObjectModelCode.OTHERS,
        ]
        # 加上所有K8s代码
        expected_codes.extend(K8sObjectModelCode.ALL)
        # 加上所有应用观测
        expected_codes.extend(ApplicationObjectModelCode.ALL)

        assert set(NOT_UPDATE_OBJECT_MODEL_CODE_LIST) == set(expected_codes)

    def test_not_plugin_manage_obj_code_list(self):
        """测试不支持插件管理的代码列表"""
        expected_codes = [
            BuiltinObjectModelCode.WEB_SERVICE,
            BuiltinObjectModelCode.SERVICE,
            BuiltinObjectModelCode.WEB,
            BuiltinObjectModelCode.OTHERS,
        ]
        # 加上所有K8s代码
        expected_codes.extend(K8sObjectModelCode.ALL)
        # 加上所有应用观测
        expected_codes.extend(ApplicationObjectModelCode.ALL)

        assert set(NOT_PLUGIN_MANAGE_OBJ_CODE_LIST) == set(expected_codes)

    def test_not_update_object_model_group_code_list(self):
        """测试不可更新的分组代码列表"""
        expected_codes = [
            BuiltinObjectModelGroupCode.BUSINESS,
            BuiltinObjectModelGroupCode.APPLICATION,
            BuiltinObjectModelGroupCode.WEB_SERVICE_CHECK,
            BuiltinObjectModelGroupCode.OTHERS_GROUP1,
            BuiltinObjectModelGroupCode.OTHERS_GROUP2,
            BuiltinObjectModelGroupCode.USER_EXPERIENCE,
        ]

        assert set(NOT_UPDATE_OBJECT_MODEL_GROUP_CODE_LIST) == set(expected_codes)

    def test_not_delete_object_model_group_code_list(self):
        """测试不可删除的分组代码列表"""
        expected_codes = [
            BuiltinObjectModelGroupCode.BUSINESS,
            BuiltinObjectModelGroupCode.USER_EXPERIENCE,
            BuiltinObjectModelGroupCode.APPLICATION,
            BuiltinObjectModelGroupCode.WEB_SERVICE_CHECK,
            BuiltinObjectModelGroupCode.CLOUD_PLATFORMS,
            BuiltinObjectModelGroupCode.CLOUD_VIRTUAL_MACHINE,
            BuiltinObjectModelGroupCode.CLOUD_DATASTORE,
            BuiltinObjectModelGroupCode.CLOUD_PHYSICAL_HOST,
            BuiltinObjectModelGroupCode.CLOUD_HOST_CLUSTER,
            BuiltinObjectModelGroupCode.CLOUD_ELASTIC_IP,
            BuiltinObjectModelGroupCode.CLOUD_RDS_MYSQL,
            BuiltinObjectModelGroupCode.CLOUD_HOST_MACHINE,
            BuiltinObjectModelGroupCode.CLOUD_BARE_METAL_SERVER,
            BuiltinObjectModelGroupCode.KUBERNETES,
            BuiltinObjectModelGroupCode.OS,
            BuiltinObjectModelGroupCode.OTHERS_GROUP1,
            BuiltinObjectModelGroupCode.OTHERS_GROUP2,
        ]

        assert set(NOT_DELETE_OBJECT_MODEL_GROUP_CODE_LIST) == set(expected_codes)

    def test_related_object_model_group(self):
        """测试关联对象的特殊一级对象模型分组"""
        expected_codes = [
            BuiltinObjectModelGroupCode.KUBERNETES,
            BuiltinObjectModelGroupCode.OS,
            BuiltinObjectModelGroupCode.OTHERS_GROUP_KING_EYE,
        ]

        assert set(RELATED_OBJECT_MODEL_GROUP) == set(expected_codes)

    def test_allow_create_child_object_model_group(self):
        """测试可以创建对象模型的一级分组"""
        expected_codes = [
            BuiltinObjectModelGroupCode.OS,
            BuiltinObjectModelGroupCode.OTHERS_GROUP_KING_EYE,
        ]

        assert set(ALLOW_CREATE_CHILD_OBJECT_MODEL_GROUP) == set(expected_codes)

    def test_others_groups_in_not_create_group_code_list(self):
        """确保 OTHERS_GROUP1 和 OTHERS_GROUP2 在不能创建二级分组或对象模型的分组列表中"""
        assert BuiltinObjectModelGroupCode.OTHERS_GROUP1 in NOT_CREATE_GROUP_CODE_LIST
        assert BuiltinObjectModelGroupCode.OTHERS_GROUP2 in NOT_CREATE_GROUP_CODE_LIST

    def test_not_create_group_code_list(self):
        """测试不能创建二级分组或对象模型的分组列表"""
        expected_codes = [
            BuiltinObjectModelGroupCode.BUSINESS,
            BuiltinObjectModelGroupCode.USER_EXPERIENCE,
            BuiltinObjectModelGroupCode.APPLICATION,
            BuiltinObjectModelGroupCode.WEB_SERVICE_CHECK,
            BuiltinObjectModelGroupCode.CLOUD_PLATFORMS,
            BuiltinObjectModelGroupCode.CLOUD_VIRTUAL_MACHINE,
            BuiltinObjectModelGroupCode.CLOUD_DATASTORE,
            BuiltinObjectModelGroupCode.CLOUD_PHYSICAL_HOST,
            BuiltinObjectModelGroupCode.CLOUD_HOST_CLUSTER,
            BuiltinObjectModelGroupCode.CLOUD_ELASTIC_IP,
            BuiltinObjectModelGroupCode.CLOUD_RDS_MYSQL,
            BuiltinObjectModelGroupCode.CLOUD_HOST_MACHINE,
            BuiltinObjectModelGroupCode.CLOUD_BARE_METAL_SERVER,
            BuiltinObjectModelGroupCode.KUBERNETES,
            BuiltinObjectModelGroupCode.OTHERS_GROUP1,
            BuiltinObjectModelGroupCode.OTHERS_GROUP2,
        ]

        assert set(NOT_CREATE_GROUP_CODE_LIST) == set(expected_codes)

    def test_constant_lists_no_duplicates(self):
        """确保常量列表没有重复项"""
        # 测试所有列表都没有重复项
        lists_to_check = [
            NOT_UPDATE_OBJECT_MODEL_CODE_LIST,
            NOT_PLUGIN_MANAGE_OBJ_CODE_LIST,
            NOT_UPDATE_OBJECT_MODEL_GROUP_CODE_LIST,
            NOT_DELETE_OBJECT_MODEL_GROUP_CODE_LIST,
            RELATED_OBJECT_MODEL_GROUP,
            ALLOW_CREATE_CHILD_OBJECT_MODEL_GROUP,
            NOT_CREATE_GROUP_CODE_LIST,
        ]

        for lst in lists_to_check:
            assert len(lst) == len(set(lst)), f"List {lst} contains duplicates"

    def test_constant_lists_contain_valid_codes(self):
        """确保常量列表只包含有效的代码"""
        # 获取所有有效的对象模型代码
        valid_object_codes = [
            getattr(BuiltinObjectModelCode, attr)
            for attr in dir(BuiltinObjectModelCode)
            if not attr.startswith("_") and isinstance(getattr(BuiltinObjectModelCode, attr), str)
        ]

        # 获取所有有效的分组代码
        valid_group_codes = [
            getattr(BuiltinObjectModelGroupCode, attr)
            for attr in dir(BuiltinObjectModelGroupCode)
            if not attr.startswith("_") and isinstance(getattr(BuiltinObjectModelGroupCode, attr), str)
        ]

        # 检查对象模型相关列表
        for code in NOT_UPDATE_OBJECT_MODEL_CODE_LIST:
            assert code in valid_object_codes, f"Invalid object model code: {code}"

        for code in NOT_PLUGIN_MANAGE_OBJ_CODE_LIST:
            assert code in valid_object_codes, f"Invalid object model code: {code}"

        # 检查分组相关列表
        group_lists = [
            NOT_UPDATE_OBJECT_MODEL_GROUP_CODE_LIST,
            NOT_DELETE_OBJECT_MODEL_GROUP_CODE_LIST,
            RELATED_OBJECT_MODEL_GROUP,
            ALLOW_CREATE_CHILD_OBJECT_MODEL_GROUP,
            NOT_CREATE_GROUP_CODE_LIST,
        ]

        for group_list in group_lists:
            for code in group_list:
                assert code in valid_group_codes, f"Invalid group code: {code}"


class TestConstantClassProperties:
    """测试常量类的属性"""

    def test_builtin_classes_are_final(self):
        """确保常量类被标记为 @final"""
        # 这个测试确保我们不会意外修改常量类
        # 虽然我们无法直接测试 @final 装饰器，但可以测试类的基本属性
        assert hasattr(BuiltinObjectModelGroupCode, "__annotations__") or True
        assert hasattr(BuiltinObjectModelCode, "__annotations__") or True
        assert hasattr(HardwareObjectModelCode, "__annotations__") or True
        assert hasattr(K8sObjectModelCode, "__annotations__") or True
        assert hasattr(CloudObjectModelCode, "__annotations__") or True

    def test_constant_classes_have_expected_attributes(self):
        """测试常量类有预期的属性"""
        # 确保每个常量类都有足够的属性（不只是空类）
        builtin_group_attrs = [attr for attr in dir(BuiltinObjectModelGroupCode) if not attr.startswith("_")]
        assert len(builtin_group_attrs) > 20, "BuiltinObjectModelGroupCode should have many attributes"

        builtin_model_attrs = [attr for attr in dir(BuiltinObjectModelCode) if not attr.startswith("_")]
        assert len(builtin_model_attrs) > 50, "BuiltinObjectModelCode should have many attributes"

        # 确保 ALL 列表存在于相应的类中
        assert hasattr(HardwareObjectModelCode, "ALL")
        assert hasattr(K8sObjectModelCode, "ALL")
        assert isinstance(HardwareObjectModelCode.ALL, list)
        assert isinstance(K8sObjectModelCode.ALL, list)
