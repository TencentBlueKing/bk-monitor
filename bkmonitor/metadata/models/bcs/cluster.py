import copy
import logging

from django.conf import settings
from django.db import models
from django.db.transaction import atomic
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from kubernetes import client as k8s_client

from bkmonitor.utils.db import JsonField
from metadata import config
from metadata.models import common
from metadata.models.custom_report import EventGroup, TimeSeriesGroup
from metadata.models.data_source import DataSource
from metadata.models.result_table import ResultTableOption

from .replace import ReplaceConfig
from .utils import ensure_data_id_resource, is_equal_config

logger = logging.getLogger("metadata")


class BCSClusterInfo(models.Model):
    """kubernetes集群信息"""

    DATA_TYPE_K8S_METRIC = "k8s_metric"
    DATA_TYPE_K8S_EVENT = "k8s_event"
    DATA_TYPE_CUSTOM_METRIC = "custom_metric"

    CLUSTER_STATUS_RUNNING = "running"
    CLUSTER_STATUS_DELETED = "deleted"
    CLUSTER_STATUS_INIT_FAILED = "init_failed"
    CLUSTER_RAW_STATUS_RUNNING = "RUNNING"
    CLUSTER_RAW_STATUS_DELETED = "DELETED"

    DEFAULT_SERVICE_MONITOR_DIMENSION_TERM = ["bk_monitor_name", "bk_monitor_namespace/bk_monitor_name"]

    DATASOURCE_REGISTER_INFO = {
        DATA_TYPE_K8S_METRIC: {
            "etl_config": "bk_standard_v2_time_series",
            "report_class": TimeSeriesGroup,
            # k8s不支持下划线，python不支持中划线,所以要写两个
            "datasource_name": "K8sMetricDataID",
            "is_split_measurement": True,
            "is_system": True,
            "usage": "metric",
        },
        DATA_TYPE_CUSTOM_METRIC: {
            "etl_config": "bk_standard_v2_time_series",
            "report_class": TimeSeriesGroup,
            "datasource_name": "CustomMetricDataID",
            "is_split_measurement": True,
            "is_system": False,
            "usage": "metric",
        },
        DATA_TYPE_K8S_EVENT: {
            "etl_config": "bk_standard_v2_event",
            "report_class": EventGroup,
            "datasource_name": "K8sEventDataID",
            "is_system": True,
            "usage": "event",
            # 背景：k8s 事件具有一致的 data_label，便于对多集群进行聚合查询
            "data_label": DATA_TYPE_K8S_EVENT,
        },
    }

    # 业务信息
    # 集群ID，ID和BCS的集群ID一致
    cluster_id = models.CharField("集群ID", db_index=True, max_length=128)
    bcs_api_cluster_id = models.CharField("bcs-api集群ID", db_index=True, max_length=128)
    bk_biz_id = models.IntegerField("业务ID", db_index=True)
    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")
    bk_cloud_id = models.IntegerField("云区域ID", default=None, null=True)
    project_id = models.CharField("项目ID", max_length=128)
    status = models.CharField("集群状态", default=CLUSTER_RAW_STATUS_RUNNING, max_length=50)

    # 集群链接信息
    domain_name = models.CharField("集群链接域名", max_length=512)
    port = models.IntegerField("集群链接端口")
    # 注意，此处保留的是集群请求的根路径。
    # 如果是k8s的原生访问，此处写/即可；但是如果是BCS的代理，此处需要是bcs-api返回的server_address_path
    server_address_path = models.CharField("集群请求根路径", max_length=512)

    # apiKey是openAPI的身份认证信息规则，具体可以参考：https://swagger.io/docs/specification/authentication/api-keys/
    # 对于BCS代理的集群，常用的配置可以是：
    # api_key: {"authorization": f"{context['user_token']}"}, api_key_prefix: {"authorization": "Bearer"}
    # 其中，key为使用的认证类型，value分别为认证信息和认证信息前缀
    api_key_type = models.CharField("身份认证信息类型", max_length=128, default="authorization")
    api_key_content = models.CharField("身份认证信息", max_length=128)
    api_key_prefix = models.CharField("身份认证信息前缀", default="Bearer", max_length=128)
    # SSL相关内容
    is_skip_ssl_verify = models.BooleanField("是否跳过SSL认证", default=True)
    cert_content = models.TextField("认证证书信息", default=None, null=True)

    # 默认的data_id信息
    K8sMetricDataID = models.IntegerField("k8s指标data_id", default=0)
    CustomMetricDataID = models.IntegerField("自定义指标data_id", default=0)
    K8sEventDataID = models.IntegerField("k8s事件data_id", default=0)
    CustomEventDataID = models.IntegerField("自定义事件data_id", default=0)
    SystemLogDataID = models.IntegerField("系统日志data_id", default=0)
    CustomLogDataID = models.IntegerField("应用或自定义日志data_id", default=0)
    bk_env = models.CharField("配置来源标签", max_length=32, default="", null=True, blank=True)

    # 创建及变更信息
    creator = models.CharField("创建者", max_length=32)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_user = models.CharField("最后更新者", max_length=32)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)

    # 是否允许查看历史数据（针对已下线集群）
    is_deleted_allow_view = models.BooleanField("已下线集群是否允许查看数据", default=False)

    @cached_property
    def api_client(self) -> k8s_client.ApiClient:
        """
        返回一个可用的k8s APIClient
        注意，此处会有一个缓存，如果是使用shell进行修改了配置项，需要重新赋值实例，否则client会依旧使用旧的配置
        """
        return k8s_client.ApiClient(self.k8s_client_config)

    @cached_property
    def core_api(self) -> k8s_client.CoreV1Api:
        """
        返回一个core v1的api client
        可以覆盖：ConfigMap/Endpoints/Event/Namespace/Node/Pod/PersistentVolume/secret
        """
        return getattr(k8s_client, self.get_api_class())(self.api_client)

    @cached_property
    def k8s_client_config(self) -> k8s_client.Configuration:
        """返回一个可用的k8s集群配置信息"""
        host = (
            f"{settings.BCS_API_GATEWAY_SCHEMA}://"
            f"{self.domain_name}:{self.port}/{self.server_address_path}/{self.cluster_id}"
        )
        k8s_config = k8s_client.Configuration(
            host=host,
            api_key={self.api_key_type: self.api_key_content},
            api_key_prefix={self.api_key_type: self.api_key_prefix},
        )
        k8s_config.verify_ssl = not self.is_skip_ssl_verify

        return k8s_config

    @cached_property
    def bk_env_label(self) -> str:
        """集群配置标签"""
        # 如果指定集群有特定的标签，则以集群记录为准
        return self.bk_env or settings.BCS_CLUSTER_BK_ENV_LABEL

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def register_cluster(
        cls,
        bk_biz_id: int,
        cluster_id: str,
        project_id: str,
        creator: str,
        bk_tenant_id: str,
        domain_name: str = settings.BCS_API_GATEWAY_HOST,
        port: int = settings.BCS_API_GATEWAY_PORT,
        api_key_type: str = "authorization",
        api_key_prefix: str = "Bearer",
        is_skip_ssl_verify: bool = True,
        transfer_cluster_id: str = None,
        bk_env: str = settings.BCS_CLUSTER_BK_ENV_LABEL,
        is_fed_cluster: bool | None = False,
    ) -> "BCSClusterInfo":
        """
        注册一个新的bcs集群信息
        :param bk_biz_id: 业务ID
        :param cluster_id: 集群ID(BCS SaaS的集群ID)
        :param project_id: 项目ID
        :param creator: 创建者
        :param domain_name: BCS集群域名，默认为空时，直接使用BCS-API的IP或域名
        :param port: 集群端口号，默认是BCS-API的https端口
        :param is_skip_ssl_verify: 是否跳过SSL认证
        :param api_key_type: 集群链接认证类型，默认是authorization
        :param api_key_prefix: 认证类型前缀，默认是Bearer
        :param transfer_cluster_id: 默认使用的transfer集群ID
        :param bk_env: 集群环境标签
        :param bk_tenant_id: 租户ID
        :param is_fed_cluster: 是否是联邦集群
        :return: 新建的集群信息；否则直接抛出异常
        """
        # 1. 判断集群ID是否已经接入
        # todo 同一个集群在切换业务时不能重复接入
        if cls.objects.filter(cluster_id=cluster_id).exists():
            logger.error(
                "failed to register cluster_id->[%s] under project_id->[%s] for cluster is already register"
                ", nothing will do any more"
            )
            raise ValueError(_("集群已经接入，请确认后重试"))

        # 直接基于环境变量进行bcs纳管k8s信息的填充
        api_key_content = settings.BCS_API_GATEWAY_TOKEN
        server_address_path = "clusters"

        cluster = cls.objects.create(
            cluster_id=cluster_id,
            bcs_api_cluster_id=cluster_id,
            bk_biz_id=bk_biz_id,
            project_id=project_id,
            domain_name=domain_name,
            port=port,
            server_address_path=server_address_path,
            api_key_type=api_key_type,
            api_key_content=api_key_content,
            api_key_prefix=api_key_prefix,
            is_skip_ssl_verify=is_skip_ssl_verify,
            creator=creator,
            bk_tenant_id=bk_tenant_id,
            bk_env=bk_env or settings.BCS_CLUSTER_BK_ENV_LABEL,
        )
        logger.info(
            "cluster->[%s] of bk_biz_id->[%s],bk_tenant_id->[%s] create database record success.",
            cluster.cluster_id,
            bk_biz_id,
            bk_tenant_id,
        )

        if transfer_cluster_id is None:
            transfer_cluster_id = settings.DEFAULT_TRANSFER_CLUSTER_ID_FOR_K8S
            logger.debug("k8s cluster config is None, will use settings instead->[%s]", transfer_cluster_id)

        # 3. 注册6个必要的data_id和自定义事件及自定义时序上报内容
        for usage, register_info in cluster.DATASOURCE_REGISTER_INFO.items():
            # 注册data_id
            data_source = cluster.create_datasource(
                usage=usage,
                bk_tenant_id=bk_tenant_id,
                etl_config=register_info["etl_config"],
                operator=creator,
                mq_cluster_id=settings.BCS_KAFKA_STORAGE_CLUSTER_ID,
                transfer_cluster_id=transfer_cluster_id,
            )
            logger.info(
                "cluster->[%s] usage->[%s] is register datasource->[%s] success.",
                cluster.cluster_id,
                usage,
                data_source.bk_data_id,
            )

            # 注册自定义时序 或 自定义事件
            report_class = register_info["report_class"]
            if register_info["usage"] == "metric":
                # 如果是指标的类型，需要考虑增加influxdb proxy的集群隔离配置
                default_storage_config = {"proxy_cluster_name": settings.INFLUXDB_DEFAULT_PROXY_CLUSTER_NAME_FOR_K8S}
                additional_options = {
                    ResultTableOption.OPTION_CUSTOM_REPORT_DIMENSION_VALUES: cls.DEFAULT_SERVICE_MONITOR_DIMENSION_TERM
                }
            else:
                default_storage_config = {"cluster_id": settings.BCS_CUSTOM_EVENT_STORAGE_CLUSTER_ID}
                additional_options = copy.deepcopy(EventGroup.DEFAULT_RESULT_TABLE_OPTIONS)
                field_names = [field["field_name"] for field in EventGroup.STORAGE_FIELD_LIST]
                field_names.append("time")
                additional_options[ResultTableOption.OPTION_ES_DOCUMENT_ID] = field_names
                additional_options[ResultTableOption.OPTION_ENABLE_V4_EVENT_GROUP_DATA_LINK] = True

            report_group = report_class.create_custom_group(
                bk_data_id=data_source.bk_data_id,
                bk_biz_id=bk_biz_id,
                custom_group_name=f"bcs_{cluster.cluster_id}_{usage}",
                # TODO 增加新的label container
                label="other_rt",
                operator=creator,
                is_split_measurement=register_info.get("is_split_measurement", False),
                default_storage_config=default_storage_config,
                additional_options=additional_options,
                data_label=register_info.get("data_label"),
                bk_tenant_id=bk_tenant_id,
            )

            logger.info(
                "cluster->[%s] of bk_tenant_id->[%s] register group->[%s] for usage->[%s] success.",
                cluster.cluster_id,
                bk_tenant_id,
                report_group.custom_group_name,
                usage,
            )

            # 记录data_id信息
            # k8s不支持下划线,python不支持中划线
            setattr(cluster, register_info["datasource_name"], data_source.bk_data_id)
            logger.info(
                "cluster->[%s] of bk_tenant_id->[%s] usage->[%s] datasource_name->[%s] with data_id->[%s] is mark now.",
                cluster.cluster_id,
                bk_tenant_id,
                usage,
                data_source.data_name,
                data_source.bk_data_id,
            )

        # 由于改了4个data_id，所以此处需要save一波，否则临时修改的配置未持久化
        cluster.save()
        logger.info("cluster->[%s] all datasource info save to database success.", cluster.cluster_id)

        return cluster

    # 下发的资源配置中不携带租户属性
    def compose_dataid_resource_name(self, name: str, is_fed_cluster: bool | None = False) -> str:
        """组装下发的配置资源的名称"""
        if self.bk_env_label:
            name = f"{self.bk_env_label}-{name}"
        # 如果是联邦集群，则添加`fed`后缀
        if is_fed_cluster:
            name = f"{name}-{self.cluster_id.lower()}-fed"
        return name

    def compose_dataid_resource_label(self, labels: dict) -> dict:
        """组装下发的配置资源的标签"""
        if self.bk_env_label:
            labels["bk_env"] = self.bk_env_label
        return labels

    def refresh_common_resource(self, is_fed_cluster: bool | None = False):
        """
        刷新内置公共dataid资源信息，追加部署的资源，更新未同步的资源
        :param is_fed_cluster: 是否是联邦集群
        :return: True | False
        """
        api_client = self.api_client
        custom_client = k8s_client.CustomObjectsApi(api_client)

        # 1. 获取所有命名空间下的本资源信息
        resource_list = custom_client.list_cluster_custom_object(
            group=config.BCS_RESOURCE_GROUP_NAME,
            version=config.BCS_RESOURCE_VERSION,
            plural=config.BCS_RESOURCE_DATA_ID_RESOURCE_PLURAL,
        )
        logger.info(
            "cluster->[%s] got common dataid resource total->[%s]", self.cluster_id, len(resource_list["items"])
        )

        resource_items = {}
        # 遍历所有的资源信息生成字典
        for resource in resource_list["items"]:
            name = resource["metadata"]["name"]
            resource_items[name] = resource

        for usage, register_info in self.DATASOURCE_REGISTER_INFO.items():
            if is_fed_cluster and usage != self.DATA_TYPE_CUSTOM_METRIC:
                continue
            # 由于k8s命名格式要求，取小写
            datasource_name_lower = self.compose_dataid_resource_name(
                register_info["datasource_name"].lower(), is_fed_cluster=is_fed_cluster
            )

            dataid_config = self.make_config(register_info, usage=usage, is_fed_cluster=is_fed_cluster)
            # 检查k8s集群里是否已经存在对应resource
            if datasource_name_lower not in resource_items.keys():
                # 如果k8s_resource不存在，则增加
                ensure_data_id_resource(api_client, datasource_name_lower, dataid_config)
                logger.info("cluster->[%s] add new resource->[%s]", self.cluster_id, dataid_config)
            else:
                # 否则检查信息是否一致，不一致则更新
                if not is_equal_config(dataid_config, resource_items[datasource_name_lower]):
                    ensure_data_id_resource(api_client, datasource_name_lower, dataid_config)
                    logger.info("cluster->[%s] update resource->[%s]", self.cluster_id, dataid_config)

    @atomic(config.DATABASE_CONNECTION_NAME)
    def refresh_cluster_bcs_info(
        self,
        domain_name: str = settings.BCS_API_GATEWAY_HOST,
        port: int = settings.BCS_API_GATEWAY_PORT,
        api_key_content: str = settings.BCS_API_GATEWAY_TOKEN,
        server_address_path: str = "clusters",
    ):
        """
        环境变量发生变化时，需要刷新对应参数信息
        """
        self.domain_name = domain_name
        self.port = port
        self.api_key_content = api_key_content
        self.server_address_path = server_address_path
        self.save()

    def make_config(self, item, usage, is_fed_cluster: bool = False) -> dict:
        # 获取全局的replace配置
        replace_config = ReplaceConfig.get_common_replace_config()
        cluster_replace_config = ReplaceConfig.get_cluster_replace_config(cluster_id=self.cluster_id)
        replace_config[ReplaceConfig.REPLACE_TYPES_METRIC].update(
            cluster_replace_config[ReplaceConfig.REPLACE_TYPES_METRIC]
        )
        replace_config[ReplaceConfig.REPLACE_TYPES_DIMENSION].update(
            cluster_replace_config[ReplaceConfig.REPLACE_TYPES_DIMENSION]
        )

        """在k8s集群里建立的dataid资源配置"""
        # 联邦集群的自定义指标的isCommon配置为false
        labels = {
            "usage": item["usage"],
            "isCommon": "false" if usage == self.DATA_TYPE_CUSTOM_METRIC and is_fed_cluster else "true",
            "isSystem": "true" if item["is_system"] else "false",
        }
        result = {
            "apiVersion": f"{config.BCS_RESOURCE_GROUP_NAME}/{config.BCS_RESOURCE_VERSION}",
            "kind": f"{config.BCS_RESOURCE_DATA_ID_RESOURCE_KIND}",
            "metadata": {
                "name": self.compose_dataid_resource_name(item["datasource_name"].lower(), is_fed_cluster),
                "labels": self.compose_dataid_resource_label(labels),
            },
            "spec": {
                "dataID": getattr(self, item["datasource_name"]),
                "labels": {"bcs_cluster_id": self.cluster_id, "bk_biz_id": str(self.bk_biz_id)},
                "metricReplace": replace_config[ReplaceConfig.REPLACE_TYPES_METRIC],
                "dimensionReplace": replace_config[ReplaceConfig.REPLACE_TYPES_DIMENSION],
            },
        }
        return result

    def init_resource(self, is_fed_cluster: bool | None = False) -> bool:
        """初始化resource信息并绑定data_id"""
        # 基于各dataid，生成配置并写入bcs集群
        for usage, register_info in self.DATASOURCE_REGISTER_INFO.items():
            # 针对联邦集群，跳过 k8s 内置指标的 data_id 下发
            if is_fed_cluster and usage != self.DATA_TYPE_CUSTOM_METRIC:
                continue
            dataid_config = self.make_config(register_info, usage=usage, is_fed_cluster=is_fed_cluster)
            name = self.compose_dataid_resource_name(
                register_info["datasource_name"].lower(), is_fed_cluster=is_fed_cluster
            )
            if not ensure_data_id_resource(self.api_client, name, dataid_config):
                return False
        return True

    def get_api_class(self) -> str:
        """返回一个集群的api版本号"""
        resp = k8s_client.CoreApi(self.api_client).get_api_versions()
        version = resp.versions[0]
        return f"Core{version.capitalize()}Api"

    def create_datasource(
        self,
        usage: str,
        etl_config: str,
        operator: str,
        transfer_cluster_id: str,
        mq_cluster_id: str,
        bk_tenant_id: str,
    ) -> DataSource:
        """
        创建数据源
        :param usage: datasource用途, 可以为: k8s_metric/custom_metric/k8s_event/custom_event
        :param operator: 操作用户名
        :param etl_config: 清洗配置，可以为bk_standard_v2_time_series(时序)、bk_standard_v2_event(事件)和bk_flat_batch(日志)
        :param transfer_cluster_id: transfer集群ID，决定数据交由哪个transfer集群处理
        :param mq_cluster_id: 消息队列集群 ID
        :param bk_tenant_id: 租户ID
        :return: DataSource
        """
        type_label_dict = {
            "bk_standard_v2_time_series": "time_series",
            "bk_standard_v2_event": "event",
            "bk_flat_batch": "log",
        }
        try:
            datasource = DataSource.create_data_source(
                data_name=f"bcs_{self.cluster_id}_{usage}",
                etl_config=etl_config,
                operator=operator,
                source_label="bk_monitor",
                mq_cluster=mq_cluster_id,
                type_label=type_label_dict[etl_config],
                transfer_cluster_id=transfer_cluster_id,
                source_system=settings.SAAS_APP_CODE,
                bcs_cluster_id=self.cluster_id,
                bk_biz_id=self.bk_biz_id,
                bk_tenant_id=bk_tenant_id,
            )
        except ValueError as err:
            logger.exception(
                "failed to create datasource for cluster->[%s], will raise the exception and nothing will do.",
                self.cluster_id,
            )
            raise ValueError(_("创建数据源失败，请联系管理员协助")) from err
        except KeyError:
            logger.exception("got etl_config->[%s] which is not in config, maybe something go wrong?", etl_config)
            raise ValueError(_("清洗配置非预期，请联系管理员协助处理"))

        logger.info(
            "data_source->[%s] is create by etl_config->[%s] for cluster_id->[%s]",
            datasource.bk_data_id,
            etl_config,
            self.cluster_id,
        )
        return datasource

    def to_json(self):
        return {
            "cluster_id": self.cluster_id,
            "bk_tenant_id": self.bk_tenant_id,
            "bcs_api_cluster_id": self.bcs_api_cluster_id,
            "bk_biz_id": self.bk_biz_id,
            "project_id": self.project_id,
            "domain_name": self.domain_name,
            "port": self.port,
            "server_address_path": self.server_address_path,
            "api_key_type": self.api_key_type,
            "api_key_content": self.api_key_content,
            "api_key_prefix": self.api_key_prefix,
            "is_skip_ssl_verify": self.is_skip_ssl_verify,
            "cert_content": self.cert_content,
            "k8s_event_data_id": self.K8sEventDataID,
        }

    def to_json_for_user(self):
        """
        返回必要信息
        """
        return {
            "cluster_id": self.cluster_id,
            "bk_tenant_id": self.bk_tenant_id,
            "bk_biz_id": self.bk_biz_id,
            "status": self.status,
            "K8sMetricDataID": self.K8sMetricDataID,
            "CustomMetricDataID": self.CustomMetricDataID,
            "K8sEventDataID": self.K8sEventDataID,
        }


class BcsFederalClusterInfo(common.BaseModelWithTime):
    fed_cluster_id = models.CharField("代理集群 ID", max_length=32)
    host_cluster_id = models.CharField("HOST 集群 ID", max_length=32)
    sub_cluster_id = models.CharField("子集群 ID", max_length=32)
    is_deleted = models.BooleanField("是否已删除", default=False)
    fed_namespaces = JsonField("命名空间列表", default=[])
    fed_builtin_metric_table_id = models.CharField("内置指标结果表", max_length=128, null=True, blank=True)
    fed_builtin_event_table_id = models.CharField("内置事件结果表", max_length=128, null=True, blank=True)

    class Meta:
        verbose_name = "BCS联邦集群拓扑信息"
        verbose_name_plural = "BCS联邦集群拓扑信息"

    @classmethod
    def is_federal_cluster(cls, cluster_id: str) -> bool:
        """判断是否为联邦集群，这里对应的是集群入口，不包含子集群和host集群"""
        return cls.objects.filter(host_cluster_id=cluster_id).exists()
