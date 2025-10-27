import json
import logging
import random
import string

from pydantic import ValidationError

from alarm_backends.service.scheduler.app import app
from metadata.models import DataSource, DataSourceResultTable, ResultTable, ResultTableOption
from metadata.models.bkdata.result_table import BkBaseResultTable
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.data_link import DataLink
from metadata.models.data_link.data_link_configs import DorisStorageBindingConfig, ESStorageBindingConfig
from metadata.models.result_table import LogV4DataLinkOption
from metadata.models.storage import DorisStorage, ESStorage

logger = logging.getLogger(__name__)


@app.task(ignore_result=True, queue="celery_metadata_task_worker")
def apply_log_datalink(bk_tenant_id: str, table_id: str):
    """创建/更新日志V4数据链路

    Args:
        bk_tenant_id: 租户ID
        table_id: 结果表ID
    """

    # 获取结果表和数据源信息
    rt = ResultTable.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
    dsrt = DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).last()
    if not dsrt:
        raise ValueError(f"apply_log_v4_datalink: tenant({bk_tenant_id}) {table_id} related datasource not found")
    ds: DataSource = DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=dsrt.bk_data_id)

    # 如果datasource是gse创建的，需要在bkbase上注册
    ds.register_to_bkbase(bk_biz_id=rt.bk_biz_id)

    # 判断使用V4链路还是transfer链路
    enabled_v4_datalink_option = ResultTableOption.objects.filter(
        bk_tenant_id=bk_tenant_id, table_id=table_id, name=ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK
    ).first()
    if enabled_v4_datalink_option and enabled_v4_datalink_option.get_value():
        # 使用V4链路
        # 读取option中的日志链路配置
        datalink_option = ResultTableOption.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id=table_id, name=ResultTableOption.OPTION_V4_LOG_DATA_LINK
        ).first()
        if not datalink_option:
            raise ValueError(f"apply_log_v4_datalink: tenant({bk_tenant_id}) {table_id} datalink option not found")

        # 校验配置
        try:
            datalink_config = LogV4DataLinkOption(**json.loads(datalink_option.value))
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(
                "apply_log_v4_datalink: tenant(%s) %s datalink option json parse error, %s",
                bk_tenant_id,
                table_id,
                str(e),
            )
            raise ValueError(f"apply_log_v4_datalink: tenant({bk_tenant_id}) {table_id} datalink option is not json")
        except ValidationError as e:
            logger.error(
                "apply_log_v4_datalink: tenant(%s) %s datalink option is invalid, %s", bk_tenant_id, table_id, str(e)
            )
            raise ValueError(f"apply_log_v4_datalink: tenant({bk_tenant_id}) {table_id} datalink option is invalid")

        # 存储集群查询
        es_storage: ESStorage | None = None
        doris_storage: DorisStorage | None = None
        if datalink_config.es_storage_config:
            es_storage = ESStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).first()
            if not es_storage:
                logger.error("apply_log_v4_datalink: tenant(%s) %s es storage not found", bk_tenant_id, table_id)
                raise ValueError(f"apply_log_v4_datalink: tenant({bk_tenant_id}) {table_id} es storage not found")

        if datalink_config.doris_storage_config:
            doris_storage = DorisStorage.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).first()
            if not doris_storage:
                logger.error("apply_log_v4_datalink: tenant(%s) %s doris storage not found", bk_tenant_id, table_id)
                raise ValueError(f"apply_log_v4_datalink: tenant({bk_tenant_id}) {table_id} doris storage not found")

        # 创建/更新V4链路配置
        bkbase_rt = BkBaseResultTable.objects.filter(bk_tenant_id=bk_tenant_id, monitor_table_id=table_id).first()
        if not bkbase_rt:
            # 生成链路名称，格式为bklog_{bk_biz_id}_{16位随机字符串}
            random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=16))
            datalink, _ = DataLink.objects.get_or_create(
                bk_tenant_id=bk_tenant_id,
                data_link_name=f"bklog_{rt.bk_biz_id}_{random_str}",
                namespace="bklog",
                data_link_strategy=DataLink.BK_LOG,
            )
        else:
            datalink = DataLink.objects.get(bk_tenant_id=bk_tenant_id, data_link_name=bkbase_rt.data_link_name)
        datalink.apply_data_link(bk_biz_id=rt.bk_biz_id, data_source=ds, table_id=table_id)

        # 清理多余的存储链路
        es_binding_config = ESStorageBindingConfig.objects.filter(bk_tenant_id=bk_tenant_id, table_id=table_id).first()
        if not datalink_config.es_storage_config and es_binding_config:
            es_binding_config.delete_config()
        doris_binding_config = DorisStorageBindingConfig.objects.filter(
            bk_tenant_id=bk_tenant_id, table_id=table_id
        ).first()
        if not datalink_config.doris_storage_config and doris_binding_config:
            doris_binding_config.delete_config()

        # 清理transfer链路配置
        if ds.created_from != DataIdCreatedFromSystem.BKDATA.value:
            ds.created_from = DataIdCreatedFromSystem.BKDATA.value
            ds.save(update_fields=["created_from"])
            ds.delete_consul_config()
    else:
        # 使用transfer链路
        if ds.created_from != DataIdCreatedFromSystem.BKGSE.value:
            # 禁止从V4链路切换回transfer
            raise ValueError(f"apply_log_v4_datalink: tenant({bk_tenant_id}) {table_id} cannot switch to transfer")
