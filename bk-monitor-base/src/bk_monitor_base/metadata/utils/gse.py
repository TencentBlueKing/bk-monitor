from typing import Any, final

from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.metadata import config, models
from bk_monitor_base.metadata.config import settings


@final
class KafkaGseSyncer:
    """
    同步默认的消息队列(stream_to_info)信息到zk或gse

    GSE不分租户，因此调用是使用默认的租户ID
    """

    DEFAULT_MQ_STREAM_TO_NAME = "default_mq_stream_to"
    DEFAULT_STREAM_TO_REPORT_MODEL = models.DataSource.DEFAULT_MQ_TYPE

    @classmethod
    def sync_to_gse(cls):
        qs = models.ClusterInfo.objects.filter(is_register_to_gse=True)
        for mq_cluster in qs:
            if mq_cluster.is_default_cluster and mq_cluster.bk_tenant_id == DEFAULT_TENANT_ID:
                cls.register_default_to_gse(mq_cluster)
            else:
                cls.register_to_gse(mq_cluster)

    @classmethod
    def _get_kafka_sasl_auth(cls, cluster: models.ClusterInfo) -> dict[str, Any]:
        username, password = cluster.username, cluster.password
        auth = {"sasl_username": username, "sasl_passwd": password}
        # NOTE: 现阶段先不添加模型存储sasl的认证信息，后续需要再补充
        if username and password:
            auth["sasl_mechanisms"] = config.KAFKA_SASL_MECHANISM
            auth["security_protocol"] = config.KAFKA_SASL_PROTOCOL

        return auth

    @classmethod
    def update_stream_to_info_to_gse(cls, mq_cluster: models.ClusterInfo):
        """
        刷新数据库的集群信息，比如主机名，端口这些，更新到gse，保持两边一直
        """
        name = f"mq_stream_to_{mq_cluster.cluster_id}"
        if mq_cluster.is_default_cluster and mq_cluster.bk_tenant_id == DEFAULT_TENANT_ID:
            name = cls.DEFAULT_MQ_STREAM_TO_NAME

        # 获取kafka auth信息
        kafka_auth = cls._get_kafka_sasl_auth(mq_cluster)
        params = {
            "condition": {"stream_to_id": mq_cluster.gse_stream_to_id, "plat_name": config.DEFAULT_GSE_API_PLAT_NAME},
            "operation": {"operator_name": settings.blueking.common_username},
            "specification": {
                "stream_to": {
                    "name": name,
                    "report_mode": cls.DEFAULT_STREAM_TO_REPORT_MODEL,
                    cls.DEFAULT_STREAM_TO_REPORT_MODEL: {
                        "storage_address": [{"ip": mq_cluster.domain_name, "port": mq_cluster.port}],
                        **kafka_auth,
                    },
                }
            },
        }
        return api.gse.update_stream_to(bk_tenant_id=DEFAULT_TENANT_ID, **params)

    @classmethod
    def register_stream_to_info_to_gse(cls, mq_cluster: models.ClusterInfo):
        name = f"mq_stream_to_{mq_cluster.cluster_id}"
        if mq_cluster.is_default_cluster and mq_cluster.bk_tenant_id == DEFAULT_TENANT_ID:
            name = cls.DEFAULT_MQ_STREAM_TO_NAME

        # 获取kafka auth信息
        kafka_auth = cls._get_kafka_sasl_auth(mq_cluster)
        result = api.gse.add_stream_to(
            bk_tenant_id=DEFAULT_TENANT_ID,
            metadata={"plat_name": config.DEFAULT_GSE_API_PLAT_NAME},
            operation={"operator_name": settings.blueking.common_username},
            stream_to={
                "name": name,
                "report_mode": cls.DEFAULT_STREAM_TO_REPORT_MODEL,
                cls.DEFAULT_STREAM_TO_REPORT_MODEL: {
                    "storage_address": [{"ip": mq_cluster.domain_name, "port": mq_cluster.port}],
                    **kafka_auth,
                },
            },
        )
        mq_cluster.gse_stream_to_id = result["stream_to_id"]
        mq_cluster.save()

    @classmethod
    def is_default_stream_to_id_exists(cls):
        # 判断gse那边，默认的stream_to_id:500是否存在
        try:
            params = {
                "condition": {
                    "stream_to_id": config.ZK_GSE_DATA_CLUSTER_ID,
                    "plat_name": config.DEFAULT_GSE_API_PLAT_NAME,
                },
                "operation": {"operator_name": settings.blueking.common_username},
            }
            result = api.gse.query_stream_to(bk_tenant_id=DEFAULT_TENANT_ID, **params)
            return bool(result)
        except BkApiError as e:
            print(f"default zk gse data cluster id:{config.ZK_GSE_DATA_CLUSTER_ID} not exists, error:{e}")
            return False

    @classmethod
    def register_to_gse(cls, mq_cluster: models.ClusterInfo):
        if mq_cluster.gse_stream_to_id != -1:
            # 存在则更新stream_to信息
            cls.update_stream_to_info_to_gse(mq_cluster)
        else:
            cls.register_stream_to_info_to_gse(mq_cluster)

    @classmethod
    def register_default_to_gse(cls, mq_cluster: models.ClusterInfo):
        """
        看数据库是否已经更新好了stream_to_id
            - 是，直接更新gse的stream_to的信息，保持和数据库一致
            - 否，则走gse接口查询默认的stream_to_id:500是否存在
                - 存在，则直接使用500这个默认的id，更新到数据库
                - 不存在，则走接口创建一个stream_to_id，更新到数据库
        """
        # 判断数据库的stream_to_id是否存在
        if mq_cluster.gse_stream_to_id != -1:
            # 存在则更新stream_to信息
            cls.update_stream_to_info_to_gse(mq_cluster)
            return

        if cls.is_default_stream_to_id_exists():
            # 存在则直接使用这个stream_to_id, 并更新gse的stream_to信息
            mq_cluster.gse_stream_to_id = config.ZK_GSE_DATA_CLUSTER_ID
            mq_cluster.save()
            cls.update_stream_to_info_to_gse(mq_cluster)
        else:
            # 不存在则调用创建接口
            cls.register_stream_to_info_to_gse(mq_cluster)
