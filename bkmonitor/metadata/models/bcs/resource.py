# -*- coding: utf-8 -*-


import datetime
import json
import logging

from django.conf import settings
from django.db import models
from django.db.transaction import atomic
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from kubernetes import client as k8s_client

from bkmonitor.utils.consul import BKConsul
from metadata import config
from metadata.utils import consul_tools

from .cluster import BCSClusterInfo, BcsFederalClusterInfo
from .replace import ReplaceConfig
from .utils import ensure_data_id_resource, is_equal_config

logger = logging.getLogger("metadata")


class BCSResource(models.Model):
    """kubernetes资源描述"""

    # 资源信息配置
    # 资源组
    GROUP: str = "monitoring.coreos.com"
    # 版本信息
    VERSION: str = "v1"
    # 资源复数名
    PLURAL: str = None
    PLURALS: str = None
    # 使用用途
    USAGE: str = None

    # 资源集群信息
    # 集群ID，此处和cluster.ClusterInfo.
    cluster_id = models.CharField("集群ID", max_length=128)
    namespace = models.CharField("归属命名空间名", max_length=512)
    name = models.CharField("资源名", max_length=128)

    # 数据元信息
    # 此处的元信息记录的是data_id，因为实际的数据上报后可以继续分为多个结果表(result_table)，
    # 而此处记录为data_id话就可以预留后续拆分结果表的能力
    bk_data_id = models.BigIntegerField("数据源ID", db_index=True)
    is_custom_resource = models.BooleanField("是否自定义资源", default=True)
    # 用于渲染配置时使用
    is_common_data_id = models.BooleanField("是否使用公共data_id", default=True)

    record_create_time = models.DateTimeField("资源记录创建时间")
    resource_create_time = models.DateTimeField("资源在集群中创建时间")

    class Meta:
        abstract = True
        # 对于同一个资源，只可以分配一次资源
        unique_together = ("cluster_id", "namespace", "name")

    @staticmethod
    def make_bcs_client(cluster_id: int) -> k8s_client.ApiClient:
        """
        返回一个bcs操作句柄
        :param cluster_id: 集群ID
        :return:
        """
        try:
            cluster_info = BCSClusterInfo.objects.get(cluster_id=cluster_id)
        except BCSClusterInfo.DoesNotExist as err:
            logger.exception("failed to get bcs client for cluster->[%s] as cluster info is not exists.", cluster_id)
            raise ValueError(_("集群[%s]不存在") % cluster_id) from err

        return cluster_info.api_client

    def should_refresh_own_dataid(self):
        """
        判断该resource是否应该向k8s刷新只属于自己的dataid resource
        """
        # 该resource使用的非公共dataid，则需要刷新
        if not self.is_common_data_id:
            return True
        # 该resource存在配置，则需要刷新
        if ReplaceConfig.objects.filter(
            is_common=False,
            custom_level=ReplaceConfig.CUSTOM_LEVELS_RESOURCE,
            cluster_id=self.cluster_id,
            resource_name=self.name,
            resource_namespace=self.namespace,
            resource_type=self.PLURAL,
        ).exists():
            return True
        return False

    @classmethod
    def refresh_custom_resource(cls, cluster_id):
        """
        刷新自定义资源信息，追加部署的资源，更新未同步的资源
        :param cluster_id: 集群ID
        :return: True | False
        """
        api_client = cls.make_bcs_client(cluster_id=cluster_id)
        custom_client = k8s_client.CustomObjectsApi(api_client)

        # 1. 获取所有命名空间下的本资源信息
        resource_list = custom_client.list_cluster_custom_object(
            group=config.BCS_RESOURCE_GROUP_NAME,
            version=config.BCS_RESOURCE_VERSION,
            plural=config.BCS_RESOURCE_DATA_ID_RESOURCE_PLURAL,
        )
        logger.info("cluster->[%s] got resource->[%s] total->[%s]", cluster_id, cls.PLURAL, len(resource_list["items"]))

        resource_items = {}
        # 遍历所有的资源信息生成字典
        for resource in resource_list["items"]:
            name = resource["metadata"]["name"]
            resource_items[name] = resource

        # 2.遍历所有的resource,对符合条件的数据进行更新操作,只操作已经更新为非公共dataid的resource
        for item in cls.objects.filter(cluster_id=cluster_id):
            # 判断是否需要刷新独立的dataid resource
            if not item.should_refresh_own_dataid():
                continue
            # 检查k8s集群里是否已经存在对应resource
            if item.config_name not in resource_items.keys():
                # 如果k8s_resource不存在，则增加
                ensure_data_id_resource(api_client=api_client, resource_name=item.config_name, config_data=item.config)
                logger.info("cluster->[%s] add new resource->[%s]", cluster_id, item.config)
            else:
                # 否则检查信息是否一致，不一致则更新
                if not is_equal_config(item.config, resource_items[item.config_name]):
                    ensure_data_id_resource(
                        api_client=api_client, resource_name=item.config_name, config_data=item.config
                    )
                    logger.info("cluster->[%s] update resource->[%s]", cluster_id, item.config)

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def refresh_resource(cls, cluster_id: int, common_data_id: int) -> bool:
        """
        刷新集群资源信息，追加未发现的资源,删除已不存在的资源
        :param cluster_id: 集群ID
        :param common_data_id: 公共data_id，所有的资源都会注册到该data_id下
        :return: True | False
        """
        api_client = cls.make_bcs_client(cluster_id=cluster_id)
        custom_client = k8s_client.CustomObjectsApi(api_client)

        # 1. 获取所有命名空间下的本资源信息
        resource_list = custom_client.list_cluster_custom_object(
            group=cls.GROUP, version=cls.VERSION, plural=cls.PLURALS
        )
        logger.info("cluster->[%s] got resource->[%s] total->[%s]", cluster_id, cls.PLURAL, len(resource_list["items"]))

        resource_name_list = []
        # 遍历所有的资源信息
        bulk_create_data = []
        for resource in resource_list["items"]:
            namespace = resource["metadata"]["namespace"]
            name = resource["metadata"]["name"]
            resource_name_list.append("{}_{}".format(namespace, name))

            # 2. 判断是否已经注册
            if cls.objects.filter(
                cluster_id=cluster_id,
                namespace=namespace,
                name=name,
            ).exists():
                # 如果已经存在，继续下一个
                logger.info(
                    "cluster->[%s] resource->[%s] under namespace->[%s] is already exists, nothing will do.",
                    cluster_id,
                    cls.PLURAL,
                    resource["metadata"]["namespace"],
                )
                continue

            # 组装资源记录关系信息，用于批量创建
            bulk_create_data.append(
                cls(
                    cluster_id=cluster_id,
                    namespace=namespace,
                    name=name,
                    bk_data_id=common_data_id,
                    # 由于是公共data_id批量创建，都是公共的data_id
                    is_common_data_id=True,
                    # 由于是拉取集群获得的信息，所以都是自定义资源
                    is_custom_resource=True,
                    record_create_time=datetime.datetime.now(),
                    resource_create_time=datetime.datetime.now(),
                )
            )
            logger.info(
                "cluster->[%s] now create resource->[%s] name->[%s] under namespace->[%s] with data_id->[%s]"
                " success.",
                cluster_id,
                cls.PLURAL,
                name,
                namespace,
                common_data_id,
            )

        # 批量创建
        cls.objects.bulk_create(bulk_create_data)

        # 删除已经不存在的resource映射
        resource_name_set = set(resource_name_list)
        for item in cls.objects.filter(cluster_id=cluster_id):
            key = f"{item.namespace}_{item.name}"
            if key not in resource_name_set:
                item.delete()
                logger.info(
                    "cluster->[%s] delete monitor info->[%s] name->[%s] namespace->[%s] update success.",
                    cluster_id,
                    cls.PLURAL,
                    item.name,
                    item.namespace,
                )

        logger.info("cluster->[%s] all resource->[%s] update success.", cluster_id, cls.PLURAL)
        return True

    @cached_property
    def bcs_client(self) -> k8s_client.ApiClient:
        return self.make_bcs_client(self.cluster_id)

    @cached_property
    def bk_env_label(self) -> str:
        try:
            cluster_info = BCSClusterInfo.objects.get(cluster_id=self.cluster_id)
        except BCSClusterInfo.DoesNotExist as err:
            logger.exception("cluster->[%s] is not exists, err: %s", self.cluster_id, err)
            raise ValueError(_("集群[{}]不存在").format(self.cluster_id))
        return cluster_info.bk_env or settings.BCS_CLUSTER_BK_ENV_LABEL

    @cached_property
    def config_name(self) -> str:
        prefix = "common" if self.is_common_data_id else "custom"
        end = "custom" if self.is_custom_resource else "system"

        if self.bk_env_label:
            return f"{self.bk_env_label}-{prefix}-{self.USAGE}-{self.name}-{end}"
        return f"{prefix}-{self.USAGE}-{self.name}-{end}"

    @cached_property
    def config(self) -> dict:
        # 获取全局replace配置
        replace_config = ReplaceConfig.get_common_replace_config()
        # 获取集群层级replace配置
        cluster_replace_config = ReplaceConfig.get_cluster_replace_config(cluster_id=self.cluster_id)
        # 获取resource层级replace配置
        custom_replace_config = ReplaceConfig.get_resource_replace_config(
            cluster_id=self.cluster_id,
            resource_name=self.name,
            resource_namespace=self.namespace,
            resource_type=self.PLURAL,
        )

        # 将replace配置逐层覆盖
        replace_config[ReplaceConfig.REPLACE_TYPES_METRIC].update(
            cluster_replace_config[ReplaceConfig.REPLACE_TYPES_METRIC]
        )
        replace_config[ReplaceConfig.REPLACE_TYPES_DIMENSION].update(
            cluster_replace_config[ReplaceConfig.REPLACE_TYPES_DIMENSION]
        )
        replace_config[ReplaceConfig.REPLACE_TYPES_METRIC].update(
            custom_replace_config[ReplaceConfig.REPLACE_TYPES_METRIC]
        )
        replace_config[ReplaceConfig.REPLACE_TYPES_DIMENSION].update(
            custom_replace_config[ReplaceConfig.REPLACE_TYPES_DIMENSION]
        )

        cluster = BCSClusterInfo.objects.get(cluster_id=self.cluster_id)
        labels = {"usage": self.USAGE, "isCommon": "false", "isSystem": "false"}

        result = {
            "apiVersion": f"{config.BCS_RESOURCE_GROUP_NAME}/{config.BCS_RESOURCE_VERSION}",
            "kind": f"{config.BCS_RESOURCE_DATA_ID_RESOURCE_KIND}",
            "metadata": {
                "name": cluster.compose_dataid_resource_name(self.config_name),
                "labels": cluster.compose_dataid_resource_label(labels),
            },
            "spec": {
                "dataID": self.bk_data_id,
                "labels": {"bcs_cluster_id": self.cluster_id, "bk_biz_id": str(cluster.bk_biz_id)},
                "metricReplace": replace_config[ReplaceConfig.REPLACE_TYPES_METRIC],
                "dimensionReplace": replace_config[ReplaceConfig.REPLACE_TYPES_DIMENSION],
            },
        }

        # 追加一个指定的资源对应描述
        result["spec"]["monitorResource"] = {"namespace": self.namespace, "kind": self.PLURAL, "name": self.name}

        return result

    def change_data_id(self, data_id: int):
        """
        将resource使用的data_id改为新的data_id
        :param data_id: 新的data_id
        :param is_common_data_id: 更改的新data_id是否公共data_id，默认修改后，就不是公共data_id
        :return:
        """

        # 0.检查cluster的公共dataid信息，判断是否与传入的dataid发生重复了,阻挡重复的情况
        cluster = BCSClusterInfo.objects.get(cluster_id=self.cluster_id)
        is_federal_cluster = BcsFederalClusterInfo.objects.filter(
            fed_cluster_id=self.cluster_id, is_deleted=False
        ).exists()
        for usage, register_info in cluster.DATASOURCE_REGISTER_INFO.items():
            if is_federal_cluster and usage == cluster.DATA_TYPE_CUSTOM_METRIC:
                continue
            common_data_id = getattr(cluster, register_info["datasource_name"])
            if common_data_id == data_id:
                logger.error(
                    "input change dataid->[%s] conflict with common dataid->[%s] in cluster->[%s]",
                    data_id,
                    usage,
                    self.cluster_id,
                )
                raise ValueError(_("不允许传入公共dataid"))

        # 1. 修改当前资源的data_id
        self.bk_data_id = data_id

        # dataid发生修改，说明一定是改为非公共dataid，则对应调整标志位
        self.is_common_data_id = False

        self.save()
        logger.info(
            "cluster->[%s] namespace->[%s] resource->[%s] name->[%s] change to data_id->[%s] is_common->[%s]",
            self.cluster_id,
            self.namespace,
            self.PLURAL,
            self.name,
            self.bk_data_id,
            self.is_common_data_id,
        )

        # 2. 更新data_id资源
        ensure_data_id_resource(api_client=self.bcs_client, resource_name=self.config_name, config_data=self.config)

        return

    def make_data_id_resource_config(self):
        """
        渲染生成data_id配置文件
        :return:
        """

    def to_json(self):
        return {
            "cluster_id": self.cluster_id,
            "namespace": self.namespace,
            "name": self.name,
            "bk_data_id": self.bk_data_id,
            "is_custom_resource": self.is_custom_resource,
            "is_common_data_id": self.is_common_data_id,
            "resource_type": self.PLURAL,
            "resource_usage": self.USAGE,
        }

    def refresh_info_to_consul(self):
        """
        刷新当前资源dataid到consul
        仅添加当前dataid到对应路径，不会对其他dataid做修改，或者删除
        :return:
        """
        try:
            if not BCSClusterInfo.objects.filter(cluster_id=self.cluster_id).exists():
                logger.error("filter data_id:{}, cluster_id:{} failed".format(self.bk_data_id, self.cluster_id))
                return
            cluster_infos = BCSClusterInfo.objects.filter(cluster_id=self.cluster_id)
            path = "{}/project_id/{}/cluster_id/{}".format(
                config.CONSUL_PATH, cluster_infos[0].project_id, self.cluster_id
            )
            hash_consul = consul_tools.HashConsul()
            # 试图获取当前project_id, cluster_id下的data_id_list
            _, val = hash_consul.get(path)
            vals = []
            if val is not None:
                vals = json.loads(val.get("Value", "[]"))
            # 若当前data_id_list中没有这个data_id，则添加，否则直接返回
            append_data_id_list = [
                data_id for data_id in [cluster_infos[0].K8sMetricDataID, self.bk_data_id] if data_id not in vals
            ]
            if len(append_data_id_list) == 0:
                return
            vals.extend(append_data_id_list)
            hash_consul.put(path, vals)

        except Exception as e:
            logger.error("loads key:{}, value:{} failed:{}".format(path, val, e))

    @classmethod
    def refresh_all_to_consul(cls):
        """
        刷新资源与k8s集群对应的所有时序data_id到consul
        :return:
        """
        # 所有的时序dataid = k8scluster的默认K8sMetricDataID + resource(PodMonitorInfo,ServiceMonitorInfo) 的data_id_list
        path_template = config.CONSUL_PATH + "/project_id/{}/cluster_id/{}"
        info_dict = {}
        cluster_dict = {}
        # 获取所有的k8s_cluster, 构造一个字典cluster_dict {"cluster_id": "project_id"}
        # 同时初始化 构造出一个字典info_dict {"config.CONSUL_PATH/project_id/{}/cluster_id/{}": "[data_id]"}
        bcs_clusters = BCSClusterInfo.objects.all()
        for cluster in bcs_clusters:
            info_key = path_template.format(cluster.project_id, cluster.cluster_id)
            info_dict[info_key] = {cluster.K8sMetricDataID}
            cluster_dict[cluster.cluster_id] = cluster.project_id
        # 获取所有resource
        pod_monitor_infos = PodMonitorInfo.objects.all()
        service_monitor_infos = ServiceMonitorInfo.objects.all()
        try:
            # 遍历并构造出一个字典{"{}/project_id/{}/cluster_id/{}": "[data_id]"}
            for resources in [pod_monitor_infos, service_monitor_infos]:
                for resource in resources:
                    dict_key = path_template.format(cluster_dict[resource.cluster_id], resource.cluster_id)
                    info_dict.get(dict_key, set()).add(resource.bk_data_id)

            # 构造完成之后覆盖consul中的内容
            hash_consul = consul_tools.HashConsul()
            for path, vals in info_dict.items():
                hash_consul.put(path, vals)
        except Exception as e:
            logger.error("refresh all info into consul failed:{}".format(e))

    @classmethod
    def clean_all_bcs_info(cls):
        """
        清除consul上所有资源对应的所有data_id信息
        :return:
        """
        # 直接删除所有的 {}/project_id 下的所有kv
        hash_consul = consul_tools.HasrhConsul()
        root_path = config.CONSUL_PATH + "/project_id"
        bk_consul = BKConsul(
            host=hash_consul.host, port=hash_consul.port, scheme=hash_consul.scheme, verify=hash_consul.verify
        )
        bk_consul.kv.delete(root_path, recurse=True)


class PodMonitorInfo(BCSResource):
    """kubernetes中的pod Monitor信息"""

    PLURAL = "PodMonitor"
    PLURALS = "podmonitors"
    USAGE = "metric"


class ServiceMonitorInfo(BCSResource):
    """kubernetes中的service Monitor信息"""

    PLURAL = "ServiceMonitor"
    PLURALS = "servicemonitors"
    USAGE = "metric"


class LogCollectorInfo(BCSResource):
    """kubernetes中的log Collector信息"""

    GROUP = "bk.tencent.com"
    VERSION = "v1alpha1"
    PLURAL = "BkLogConfig"
    PLURALS = "bklogconfigs"
    USAGE = "log"

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def refresh_resource(cls, cluster_id: int, common_data_id: int) -> bool:
        """
        刷新集群资源信息，追加未发现的资源,删除已不存在的资源
        :param cluster_id: 集群ID
        :param common_data_id: 公共data_id，兼容参数，日志采集场景下不允许公共的dataid
        :return: True | False
        """
        api_client = cls.make_bcs_client(cluster_id=cluster_id)
        custom_client = k8s_client.CustomObjectsApi(api_client)

        # 1. 获取所有命名空间下的本资源信息
        resource_list = custom_client.list_cluster_custom_object(
            group=cls.GROUP, version=cls.VERSION, plural=cls.PLURALS
        )
        logger.info("cluster->[%s] got resource->[%s] total->[%s]", cluster_id, cls.PLURAL, len(resource_list["items"]))

        resource_name = []
        # 遍历所有的资源信息
        for resource in resource_list["items"]:
            namespace = resource["metadata"]["namespace"]
            name = resource["metadata"]["name"]
            resource_name.append("{}_{}".format(namespace, name))
            data_id = resource["spec"]["data_id"]

            # 2. 判断是否已经注册
            if cls.objects.filter(
                cluster_id=cluster_id,
                namespace=namespace,
                name=name,
            ).exists():
                # 如果已经存在，继续下一个
                logger.info(
                    "cluster->[%s] resource->[%s] under namespace->[%s] is already exists, nothing will do.",
                    cluster_id,
                    cls.PLURAL,
                    resource["metadata"]["namespace"],
                )
                continue

            # 3. 创建新的资源记录关系信息
            cls.objects.create(
                cluster_id=cluster_id,
                namespace=namespace,
                name=name,
                bk_data_id=data_id,
                # 由于是公共data_id批量创建，都是公共的data_id
                is_common_data_id=False,
                # 由于是拉取集群获得的信息，所以都是自定义资源
                is_custom_resource=True,
                record_create_time=datetime.datetime.now(),
                resource_create_time=datetime.datetime.now(),
            )
            logger.info(
                "cluster->[%s] now create resource->[%s] name->[%s] under namespace->[%s] with data_id->[%s]"
                " success.",
                cluster_id,
                cls.PLURAL,
                name,
                namespace,
                data_id,
            )

        # 删除已经不存在的resource映射
        for item in cls.objects.filter(cluster_id=cluster_id):
            key = "{}_{}".format(item.namespace, item.name)
            if key not in resource_name:
                item.delete()
                logger.info(
                    "cluster->[%s] delete log collector info->[%s] name->[%s] namespace->[%s] update success.",
                    cluster_id,
                    cls.PLURAL,
                    item.name,
                    item.namespace,
                )

        logger.info("cluster->[%s] log resource->[%s] update success.", cluster_id, cls.PLURAL)
        return True
