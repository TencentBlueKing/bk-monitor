from typing import final


@final
class BuiltinObjectModelGroupCode:
    """
    内置对象模型分组
    """

    # 业务资源概览
    BUSINESS = "cw-Business"
    # 组件
    COMPONENT = "cw-Component"
    # 组件-数据库监控
    DATABASES = "cw-Databases"
    # 组件-中间件监控
    MIDDLEWARES = "cw-Middlewares"
    # 主机监控
    OS = "cw-Operating_Systems"
    # 网站服务拨测
    WEB_SERVICE_CHECK = "cw-Web_Service_Check"
    # 云平台监控
    CLOUD_PLATFORMS = "cw-Cloud_Platforms"
    # 云平台监控-虚拟机
    CLOUD_VIRTUAL_MACHINE = "cw-Cloud_Virtual_Machine"
    # 云平台监控-数据存储
    CLOUD_DATASTORE = "cw-Cloud_DataStore"
    # 云平台监控-物理机
    CLOUD_PHYSICAL_HOST = "cw-Cloud_Physical_Host"
    # 云平台监控-物理机集群
    CLOUD_HOST_CLUSTER = "cw-Cloud_Host_Cluster"
    # 云平台监控-弹性公网IP
    CLOUD_ELASTIC_IP = "cw-Cloud_Elastic_IP"
    # 云平台监控-关系型数据库-MySQL
    CLOUD_RDS_MYSQL = "cw-Cloud_RDS_MySQL"
    # 云平台监控-宿主机
    CLOUD_HOST_MACHINE = "cw-Cloud_Host_Machine"
    # 云平台监控-裸金属服务器
    CLOUD_BARE_METAL_SERVER = "cw-Cloud_Bare_Metal_Server"
    # 硬件设备
    HARDWARE_DEVICE = "cw-Hardware_Device"
    # 硬件设备-网络设备
    NETWORK_DEVICES = "cw-Network_Devices"
    # 硬件设备-物理机
    PHYSICAL_DEVICES = "cw-Physical_Devices"
    # K8s监控
    KUBERNETES = "cw-Kubernetes"
    # 应用观测
    APPLICATION = "cw-Application"
    # 用户体验
    USER_EXPERIENCE = "cw-User_Experience"
    # 其他
    OTHERS_GROUP1 = "cw-Others_Group1"
    # 其他-其他
    OTHERS_GROUP2 = "cw-Others_Group2"
    OTHERS_GROUP_KING_EYE = "cw-Others_Group_king_eye"


@final
class BuiltinObjectModelCode:
    """
    内置对象模型code
    """

    # 业务
    BIZ = "cw-biz"
    # 主机
    HOST = "cw-Host"
    # KRUM
    WEB = "cw-web"
    # KAPM相关code
    # 应用
    APPLICATION = "cw-application"
    # 服务
    SERVICE = "cw-service"
    # 服务实例
    SERVICE_INSTANCE = "cw-service_instance"
    # 接口
    INTERFACE = "cw-interface"

    # 网站服务code(拨测)
    WEB_SERVICE = "cw-web_service"
    # 其他
    OTHERS = "cw-Others"

    # 组件相关code
    # 组件-数据库
    ORACLE = "cw-Oracle"
    MYSQL = "cw-MySQL"
    MSSQL = "cw-MSSQL"
    MONGODB = "cw-MongoDB"
    REDIS = "cw-Redis"
    ELASTICSEARCH = "cw-Elasticsearch"
    POSTGRESQL = "cw-PostgreSQL"
    # 组件-中间件
    H2 = "cw-H2"
    NGINX = "cw-Nginx"
    TOMCAT = "cw-Tomcat"
    APACHE = "cw-Apache"
    WEBLOGIC = "cw-WebLogic"
    KAFKA = "cw-Kafka"
    RABBITMQ = "cw-RabbitMQ"
    ROCKETMQ = "cw-RocketMQ"

    # 容器监控相关code
    K8S_CLUSTER = "cw-K8s_Cluster"
    K8S_WORKLOAD = "cw-K8s_Workload"
    K8S_POD = "cw-K8s_Pod"
    K8S_CONTAINER = "cw-K8s_Container"
    K8S_NODE = "cw-K8s_Node"
    K8S_PV = "cw-K8s_PersistentVolume"
    K8S_PVC = "cw-K8s_PersistentVolumeClaim"

    # 硬件设备相关code
    # 硬件设备-网络设备
    LOAD_BALANCE = "cw-Load_Balance"
    FIREWALL = "cw-Firewall"
    SWITCH = "cw-Switch"
    ROUTER = "cw-Router"
    # 硬件-物理机
    PHYSICAL_SERVER = "cw-Physical_Server"

    # 云平台相关code
    # 虚拟机
    CLOUD_VIRTUAL_MACHINE_VMWARE = "cw-Cloud_Virtual_Machine_VMware"
    CLOUD_VIRTUAL_MACHINE_ALI = "cw-Cloud_Virtual_Machine_Ali"
    CLOUD_VIRTUAL_MACHINE_TENCENT = "cw-Cloud_Virtual_Machine_Tencent"
    CLOUD_VIRTUAL_MACHINE_FUSIONCOMPUTE = "cw-Cloud_Virtual_Machine_FusionCompute"
    CLOUD_VIRTUAL_MACHINE_WINSTACK = "cw-Cloud_Virtual_Machine_WinStack"
    CLOUD_VIRTUAL_MACHINE_H3CLOUD = "cw-Cloud_Virtual_Machine_H3Cloud"
    CLOUD_VIRTUAL_MACHINE_ALIYUNPRIVATE = "cw-Cloud_Virtual_Machine_AliyunPrivate"
    CLOUD_VIRTUAL_MACHINE_MANAGEONE = "cw-Cloud_Virtual_Machine_ManageOne"
    CLOUD_VIRTUAL_MACHINE_MANAGEMENT_MANAGEONE = "cw-Cloud_Virtual_Machine_Management_ManageOne"
    CLOUD_VIRTUAL_MACHINE_ZSTACK = "cw-Cloud_Virtual_Machine_ZStack"
    CLOUD_VIRTUAL_MACHINE_ESTACK = "cw-Cloud_Virtual_Machine_eStack"
    # 数据存储
    CLOUD_DATASTORE_VMWARE = "cw-Cloud_DataStore_VMware"
    CLOUD_DATASTORE_WINSTACK = "cw-Cloud_DataStore_WinStack"
    CLOUD_DATASTORE_ALIYUNPRIVATE = "cw-Cloud_DataStore_AliyunPrivate"
    # 物理机
    CLOUD_PHYSICAL_HOST_VMWARE = "cw-Cloud_Physical_Host_VMware"
    CLOUD_PHYSICAL_HOST_FUSIONCOMPUTE = "cw-Cloud_Physical_Host_FusionCompute"
    CLOUD_PHYSICAL_HOST_WINSTACK = "cw-Cloud_Physical_Host_WinStack"
    CLOUD_PHYSICAL_HOST_H3CLOUD = "cw-Cloud_Physical_Host_H3Cloud"
    CLOUD_PHYSICAL_HOST_MANAGEONE = "cw-Cloud_Physical_Host_ManageOne"
    CLOUD_PHYSICAL_HOST_ZSTACK = "cw-Cloud_Physical_Host_ZStack"
    # 物理机集群
    CLOUD_HOST_CLUSTER_VMWARE = "cw-Cloud_Host_Cluster_VMware"
    CLOUD_HOST_CLUSTER_FUSIONCOMPUTE = "cw-Cloud_Host_Cluster_FusionCompute"
    CLOUD_HOST_CLUSTER_WINSTACK = "cw-Cloud_Host_Cluster_WinStack"
    CLOUD_HOST_CLUSTER_H3CLOUD = "cw-Cloud_Host_Cluster_H3Cloud"
    # 弹性公网IP
    CLOUD_ELASTIC_IP_ALI = "cw-Cloud_Elastic_IP_Ali"
    CLOUD_ELASTIC_IP_TENCENT = "cw-Cloud_Elastic_IP_Tencent"
    # 关系型数据库 - MySQL
    CLOUD_RDS_MYSQL_MANAGEONE = "cw-Cloud_RDS_MySQL_ManageOne"
    # 宿主机
    CLOUD_HOST_MACHINE_MANAGEONE = "cw-Cloud_Host_Machine_ManageOne"
    # 裸金属服务器
    CLOUD_BARE_METAL_SERVER_MANAGEONE = "cw-Cloud_Bare_Metal_Server_ManageOne"


@final
class HardwareObjectModelCode:
    """
    硬件设备相关内置对象code
    """

    LOAD_BALANCE = BuiltinObjectModelCode.LOAD_BALANCE
    FIREWALL = BuiltinObjectModelCode.FIREWALL
    SWITCH = BuiltinObjectModelCode.SWITCH
    ROUTER = BuiltinObjectModelCode.ROUTER
    PHYSICAL_SERVER = BuiltinObjectModelCode.PHYSICAL_SERVER

    ALL = [LOAD_BALANCE, FIREWALL, SWITCH, ROUTER, PHYSICAL_SERVER]


@final
class K8sObjectModelCode:
    """
    容器监控相关内置对象code
    """

    CLUSTER = BuiltinObjectModelCode.K8S_CLUSTER
    WORKLOAD = BuiltinObjectModelCode.K8S_WORKLOAD
    POD = BuiltinObjectModelCode.K8S_POD
    CONTAINER = BuiltinObjectModelCode.K8S_CONTAINER
    NODE = BuiltinObjectModelCode.K8S_NODE
    PV = BuiltinObjectModelCode.K8S_PV
    PVC = BuiltinObjectModelCode.K8S_PVC

    ALL = [CLUSTER, WORKLOAD, POD, CONTAINER, NODE, PV, PVC]


@final
class ApplicationObjectModelCode:
    """
    应用观测相关内置对象code
    """

    APPLICATION = BuiltinObjectModelCode.APPLICATION
    SERVICE = BuiltinObjectModelCode.SERVICE
    SERVICE_INSTANCE = BuiltinObjectModelCode.SERVICE_INSTANCE
    INTERFACE = BuiltinObjectModelCode.INTERFACE

    ALL = [APPLICATION, SERVICE, SERVICE_INSTANCE, INTERFACE]


@final
class CloudObjectModelCode:
    """
    内置云平台相关对象模型code
    """

    CLOUD_VIRTUAL_MACHINE_VMWARE = BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_VMWARE
    CLOUD_VIRTUAL_MACHINE_ALI = BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_ALI
    CLOUD_VIRTUAL_MACHINE_TENCENT = BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_TENCENT
    CLOUD_VIRTUAL_MACHINE_FUSIONCOMPUTE = BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_FUSIONCOMPUTE
    CLOUD_VIRTUAL_MACHINE_WINSTACK = BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_WINSTACK
    CLOUD_VIRTUAL_MACHINE_H3CLOUD = BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_H3CLOUD
    CLOUD_VIRTUAL_MACHINE_ALIYUNPRIVATE = BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_ALIYUNPRIVATE
    CLOUD_VIRTUAL_MACHINE_MANAGEONE = BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_MANAGEONE
    CLOUD_VIRTUAL_MACHINE_MANAGEMENT_MANAGEONE = BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_MANAGEMENT_MANAGEONE
    CLOUD_VIRTUAL_MACHINE_ZSTACK = BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_ZSTACK
    CLOUD_VIRTUAL_MACHINE_ESTACK = BuiltinObjectModelCode.CLOUD_VIRTUAL_MACHINE_ESTACK
    CLOUD_DATASTORE_VMWARE = BuiltinObjectModelCode.CLOUD_DATASTORE_VMWARE
    CLOUD_DATASTORE_WINSTACK = BuiltinObjectModelCode.CLOUD_DATASTORE_WINSTACK
    CLOUD_DATASTORE_ALIYUNPRIVATE = BuiltinObjectModelCode.CLOUD_DATASTORE_ALIYUNPRIVATE
    CLOUD_PHYSICAL_HOST_VMWARE = BuiltinObjectModelCode.CLOUD_PHYSICAL_HOST_VMWARE
    CLOUD_PHYSICAL_HOST_FUSIONCOMPUTE = BuiltinObjectModelCode.CLOUD_PHYSICAL_HOST_FUSIONCOMPUTE
    CLOUD_PHYSICAL_HOST_WINSTACK = BuiltinObjectModelCode.CLOUD_PHYSICAL_HOST_WINSTACK
    CLOUD_PHYSICAL_HOST_H3CLOUD = BuiltinObjectModelCode.CLOUD_PHYSICAL_HOST_H3CLOUD
    CLOUD_PHYSICAL_HOST_MANAGEONE = BuiltinObjectModelCode.CLOUD_PHYSICAL_HOST_MANAGEONE
    CLOUD_PHYSICAL_HOST_ZSTACK = BuiltinObjectModelCode.CLOUD_PHYSICAL_HOST_ZSTACK
    CLOUD_HOST_CLUSTER_VMWARE = BuiltinObjectModelCode.CLOUD_HOST_CLUSTER_VMWARE
    CLOUD_HOST_CLUSTER_FUSIONCOMPUTE = BuiltinObjectModelCode.CLOUD_HOST_CLUSTER_FUSIONCOMPUTE
    CLOUD_HOST_CLUSTER_WINSTACK = BuiltinObjectModelCode.CLOUD_HOST_CLUSTER_WINSTACK
    CLOUD_HOST_CLUSTER_H3CLOUD = BuiltinObjectModelCode.CLOUD_HOST_CLUSTER_H3CLOUD
    CLOUD_ELASTIC_IP_ALI = BuiltinObjectModelCode.CLOUD_ELASTIC_IP_ALI
    CLOUD_ELASTIC_IP_TENCENT = BuiltinObjectModelCode.CLOUD_ELASTIC_IP_TENCENT
    CLOUD_RDS_MYSQL_MANAGEONE = BuiltinObjectModelCode.CLOUD_RDS_MYSQL_MANAGEONE
    CLOUD_HOST_MACHINE_MANAGEONE = BuiltinObjectModelCode.CLOUD_HOST_MACHINE_MANAGEONE
    CLOUD_BARE_METAL_SERVER_MANAGEONE = BuiltinObjectModelCode.CLOUD_BARE_METAL_SERVER_MANAGEONE


# 不可修改的对象模型code列表
NOT_UPDATE_OBJECT_MODEL_CODE_LIST = [
    BuiltinObjectModelCode.WEB_SERVICE,
    BuiltinObjectModelCode.WEB,
    BuiltinObjectModelCode.OTHERS,
    *K8sObjectModelCode.ALL,
    *ApplicationObjectModelCode.ALL,
]

# 不支持插件管理的code列表
NOT_PLUGIN_MANAGE_OBJ_CODE_LIST = [
    BuiltinObjectModelCode.WEB_SERVICE,
    BuiltinObjectModelCode.WEB,
    BuiltinObjectModelCode.OTHERS,
    *K8sObjectModelCode.ALL,
    *ApplicationObjectModelCode.ALL,
]

# 不可更新的分组列表
NOT_UPDATE_OBJECT_MODEL_GROUP_CODE_LIST = [
    BuiltinObjectModelGroupCode.BUSINESS,
    BuiltinObjectModelGroupCode.APPLICATION,
    BuiltinObjectModelGroupCode.WEB_SERVICE_CHECK,
    BuiltinObjectModelGroupCode.OTHERS_GROUP1,
    BuiltinObjectModelGroupCode.OTHERS_GROUP2,
    BuiltinObjectModelGroupCode.USER_EXPERIENCE,
]

# 不可删除的对象分组列表
NOT_DELETE_OBJECT_MODEL_GROUP_CODE_LIST = [
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

# 关联对象的特殊一级对象模型分组
RELATED_OBJECT_MODEL_GROUP = [
    BuiltinObjectModelGroupCode.KUBERNETES,
    BuiltinObjectModelGroupCode.OS,
    BuiltinObjectModelGroupCode.OTHERS_GROUP_KING_EYE,
]

# 可以创建对象模型的一级分组
ALLOW_CREATE_CHILD_OBJECT_MODEL_GROUP = [
    BuiltinObjectModelGroupCode.OS,
    BuiltinObjectModelGroupCode.OTHERS_GROUP_KING_EYE,
]

# 不能创建二级分组或对象模型的分组列表
NOT_CREATE_GROUP_CODE_LIST = [
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
