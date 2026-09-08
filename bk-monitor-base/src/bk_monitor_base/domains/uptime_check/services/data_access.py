"""
数据接入服务

负责DataID的申请和管理
"""

import logging
from typing import final

from bk_monitor_base.domains.uptime_check.constants import UptimeCheckProtocol
from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.infras.third_party_api.metadata.api import (
    CreateDataSourceParams,
    CreateTimeSeriesGroupParams,
)

logger = logging.getLogger(__name__)


@final
class DataAccessService:
    """
    数据接入服务 - 对应原 UptimecheckDataAccessor

    负责为拨测任务申请和管理DataID
    """

    # 数据接入版本(用于幂等性控制)
    version = "v1"

    # 默认的DataID映射(用于公共数据源)
    DATAID_MAP = {
        UptimeCheckProtocol.HTTP: 1011,
        UptimeCheckProtocol.TCP: 1009,
        UptimeCheckProtocol.UDP: 1010,
        UptimeCheckProtocol.ICMP: 1100003,
    }

    def __init__(self, bk_tenant_id: str, bk_biz_id: int, protocol: str):
        """
        初始化数据接入服务

        Args:
            bk_tenant_id: 租户ID
            bk_biz_id: 业务ID
            protocol: 协议类型
        """
        self.bk_tenant_id = bk_tenant_id
        self.bk_biz_id = bk_biz_id
        self.protocol = protocol

    @property
    def db_name(self) -> str:
        """数据库名称"""
        return f"uptimecheck_{self.protocol.lower()}_{self.bk_biz_id}"

    @property
    def data_label(self) -> str:
        """数据标签"""
        return f"uptimecheck_{self.protocol.lower()}"

    def use_custom_report(self, independent: bool) -> bool:
        """是否使用自定义上报"""
        return independent

    def get_data_id(self, independent: bool = False) -> tuple[bool, int]:
        """
        获取数据链路ID (对应原 get_data_id 方法)

        Args:
            independent: 是否使用独立DataID

        Returns:
            (是否是自定义上报, 数据链路ID)
        """
        if not self.use_custom_report(independent):
            protocol_enum = UptimeCheckProtocol(self.protocol.upper())
            return False, self.DATAID_MAP[protocol_enum]

        # 调用三方接口获取数据源信息
        data_id_info = api.metadata.get_data_source(
            bk_tenant_id=self.bk_tenant_id,
            data_name=self.db_name,
        )
        return True, data_id_info["bk_data_id"]

    def create_data_id(self) -> int:
        """
        创建数据ID

        Returns:
            数据ID
        """
        try:
            data_id_info = api.metadata.get_data_source(
                bk_tenant_id=self.bk_tenant_id,
                data_name=self.db_name,
            )
            return data_id_info["bk_data_id"]
        except Exception:
            pass

        params: CreateDataSourceParams = {
            "data_name": self.db_name,
            "etl_config": "bk_standard_v2_time_series",
            "operator": "admin",
            "data_description": self.db_name,
            "type_label": "time_series",
            "source_label": "bk_monitor",
            "bk_biz_id": self.bk_biz_id,
            "is_custom_source": False,
            "option": {
                "inject_local_time": True,
                "allow_dimensions_missing": True,
                "is_split_measurement": True,
            },
        }

        return api.metadata.create_data_source(
            bk_tenant_id=self.bk_tenant_id,
            **params,
        )

    def access(self) -> int:
        """
        接入数据链路

        完整流程:
        1. 检查是否已接入(幂等性)
        2. 创建DataID
        3. 创建时序分组
        """

        # 步骤1: 获取数据ID
        try:
            _, data_id = self.get_data_id(independent=True)
            return data_id
        except BkApiError:
            # 步骤2: 创建数据ID
            data_id = self.create_data_id()
            logger.info(f"创建DataID成功: {data_id}")

        # 步骤3: 创建自定义时序分组
        params: CreateTimeSeriesGroupParams = {
            "operator": "admin",
            "bk_data_id": data_id,
            "bk_biz_id": self.bk_biz_id,
            "time_series_group_name": self.db_name,
            "label": "uptimecheck",
            "is_split_measurement": True,
            "metric_info_list": [],
            "data_label": self.data_label,
            "additional_options": {
                "enable_field_black_list": True,
                "enable_default_value": False,
            },
        }

        api.metadata.create_time_series_group(bk_tenant_id=self.bk_tenant_id, **params)
        logger.info(f"创建时序数据组成功: {self.db_name}")
        return data_id

    def get_or_create_data_id(self, independent: bool = False) -> tuple[bool, int]:
        """
        获取或创建DataID

        Args:
            task_id: 任务ID
            independent: 是否使用独立DataID

        Returns:
            (是否使用自定义DataID, DataID值)
        """
        # 如果不使用独立DataID,返回默认值
        if not independent:
            protocol_enum = UptimeCheckProtocol(self.protocol.upper())
            default_data_id = self.DATAID_MAP.get(protocol_enum, 1011)
            logger.info(f"使用默认DataID: {default_data_id} (协议: {self.protocol})")
            return False, default_data_id

        # 使用独立DataID,执行完整的数据接入流程
        try:
            data_id = self.access()
            logger.info(f"拨测数据接入完成,DataID: {data_id}")
        except Exception as e:
            raise ValueError(f"拨测数据接入失败: {e}") from e

        return True, data_id
