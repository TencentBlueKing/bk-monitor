#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DataID V3 -> V4 链路迁移脚本

将数据源从 V3 链路迁移到 V4 链路:
- 指标类型: V3 (GSE -> Transfer -> InfluxDB) -> V4 (GSE -> BKBase -> VictoriaMetrics)
- 日志类型: V3 (GSE -> Transfer -> ES) -> V4 (GSE -> BKBase -> ES/Doris)

支持的 ETL 配置:
- bk_standard_v2_time_series: 指标类型，使用 access_v2_bkdata_vm()
- bk_flat_batch: 日志类型，使用 apply_log_datalink()

在 monitor-api pod 中执行:
    # 诊断模式 - 只查看状态不做任何变更
    python migrate_dataid_to_v4.py <data_id> --diagnose

    # 执行迁移
    python migrate_dataid_to_v4.py <data_id> --migrate

    # 重试迁移 (用于 BKBase 配置下发失败后的重试)
    python migrate_dataid_to_v4.py <data_id> --retry

    # 回滚到 V3
    python migrate_dataid_to_v4.py <data_id> --rollback

    # 批量迁移
    python migrate_dataid_to_v4.py 1001,1002,1003 --migrate

    # 指定 kafka 名称 (计算平台侧)
    python migrate_dataid_to_v4.py <data_id> --migrate --kafka-name kafka_outer_default

功能:
    1. 诊断: 分析 DataID 当前状态和迁移可行性
    2. 迁移: 执行 V3 -> V4 链路迁移
    3. 重试: 重试 BKBase 配置下发和 V4 数据链路创建（用于网络超时等临时失败场景）
    4. 回滚: 将 V4 链路回滚到 V3
    5. 验证: 检查迁移后组件状态

迁移步骤 (V3 -> V4):
    Step 1. 校验 etl_config 兼容性
    Step 2. 更改 created_from 为 bkdata，删除 Consul 配置
    Step 3. 创建 DataIdConfig (计算平台侧)
    Step 4. 下发 DataId Config 至 BKBase
    Step 5. 创建完整 V4 数据链路
        - 指标类型: 调用 access_v2_bkdata_vm() 创建 VM 存储
        - 日志类型: 设置 ResultTableOption 后调用 apply_log_datalink()
    Step 6. 验证组件状态

回滚步骤 (V4 -> V3):
    Step 1. 更改 created_from 为 bkgse
    Step 2. 刷新 Consul 配置和 GSE 路由

注意:
    - 迁移操作会停止 Transfer 处理该 DataID
    - 回滚操作会重新启用 Transfer 处理
    - 建议在低峰期执行迁移
    - 日志类型迁移会设置 ResultTableOption enable_log_v4_data_link=True
"""

import argparse
import json
import os
import random
import string
import sys
from datetime import datetime
from typing import Optional

# Django 初始化
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

try:
    import django

    django.setup()
except Exception as e:
    print(f"[ERROR] Django 初始化失败: {e}")
    print("请确保在 monitor-api pod 内执行此脚本")
    sys.exit(1)

# Django 初始化后导入模型和服务
from django.conf import settings

from core.drf_resource import api
from metadata import models
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link import utils as datalink_utils
from metadata.models.space.constants import (
    ENABLE_V4_DATALINK_ETL_CONFIGS,
    EtlConfigs,
    LOG_EVENT_ETL_CONFIGS,
)
from metadata.models.data_link.constants import (
    BKBASE_NAMESPACE_BK_APM,
    BKBASE_NAMESPACE_BK_LOG,
    BKBASE_NAMESPACE_BK_MONITOR,
    DataLinkKind,
    DataLinkResourceStatus,
)
from metadata.models.data_link.utils import generate_result_table_field_list
from metadata.models.vm.utils import access_v2_bkdata_vm
from metadata.models.result_table import ResultTableOption
from metadata.service.data_source import modify_data_id_source
from metadata.task.datalink import apply_log_datalink

# 日志平台模块导入（用于构建 log_v4_data_link 配置）
try:
    from apps.log_databus.models import CollectorConfig
    from apps.log_databus.handlers.etl_storage import EtlStorage
    from apps.log_databus.handlers.collector_scenario import CollectorScenario

    BKLOG_AVAILABLE = True
except ImportError:
    BKLOG_AVAILABLE = False
    print("[WARNING] 无法导入日志平台模块，日志类型迁移将使用默认配置")


class Printer:
    """终端输出工具类，统一管理所有打印格式"""

    # 终端颜色常量
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"

    @classmethod
    def colorize(cls, text: str, color: str) -> str:
        """添加颜色"""
        return f"{color}{text}{cls.ENDC}"

    @classmethod
    def header(cls, title: str):
        """打印标题"""
        print()
        print(cls.colorize("=" * 70, cls.CYAN))
        print(cls.colorize(f" {title}", cls.CYAN + cls.BOLD))
        print(cls.colorize("=" * 70, cls.CYAN))

    @classmethod
    def section(cls, title: str):
        """打印小节"""
        print()
        print(cls.colorize(f"▶ {title}", cls.BLUE + cls.BOLD))
        print(cls.colorize("-" * 50, cls.BLUE))

    @classmethod
    def step(cls, step_num: int, title: str):
        """打印步骤"""
        print()
        print(cls.colorize(f"  Step {step_num}: {title}", cls.BOLD))

    @classmethod
    def kv(cls, key: str, value, indent: int = 4, color: str = None):
        """打印键值对"""
        spaces = " " * indent
        if color:
            value = cls.colorize(str(value), color)
        print(f"{spaces}{key}: {value}")

    @classmethod
    def warning(cls, msg: str):
        """打印警告"""
        print(cls.colorize(f"    ⚠ {msg}", cls.YELLOW))

    @classmethod
    def error(cls, msg: str):
        """打印错误"""
        print(cls.colorize(f"    ✗ {msg}", cls.RED))

    @classmethod
    def success(cls, msg: str):
        """打印成功"""
        print(cls.colorize(f"    ✓ {msg}", cls.GREEN))

    @classmethod
    def info(cls, msg: str):
        """打印信息"""
        print(cls.colorize(f"    ℹ {msg}", cls.BLUE))

    @classmethod
    def banner(cls, msg: str, color: str = None):
        """打印横幅消息"""
        if color is None:
            color = cls.GREEN
        print()
        print(cls.colorize("=" * 70, color))
        print(cls.colorize(f" {msg}", color + cls.BOLD))
        print(cls.colorize("=" * 70, color))


class DataIDMigrator:
    """DataID 链路迁移器"""

    # 支持迁移到 V4 的 ETL 配置
    # 指标类型: bk_standard_v2_time_series, bk_standard, bk_exporter (后两者需要 ENABLE_PLUGIN_ACCESS_V4_DATA_LINK)
    # 日志类型: bk_flat_batch (需要单独的迁移逻辑)
    SUPPORTED_ETL_CONFIGS = [
        EtlConfigs.BK_STANDARD_V2_TIME_SERIES.value,
        EtlConfigs.BK_FLAT_BATCH.value,  # 日志类型
    ]

    # 如果启用了插件接入 V4 数据链路，则支持 bk_standard 和 bk_exporter
    if getattr(settings, "ENABLE_PLUGIN_ACCESS_V4_DATA_LINK", False):
        SUPPORTED_ETL_CONFIGS.extend(
            [
                EtlConfigs.BK_EXPORTER.value,
                EtlConfigs.BK_STANDARD.value,
            ]
        )

    # 日志类型 ETL 配置
    LOG_ETL_CONFIGS = [
        EtlConfigs.BK_FLAT_BATCH.value,
    ]

    def __init__(
        self,
        bk_data_id: int,
        kafka_name: str = "kafka_outer_default",
        bk_biz_id: Optional[int] = None,
    ):
        self.bk_data_id = bk_data_id
        self.kafka_name = kafka_name
        self.bk_biz_id = bk_biz_id
        self.datasource = None
        self.errors = []
        self.warnings = []

    def load_datasource(self) -> bool:
        """加载 DataSource"""
        try:
            self.datasource = models.DataSource.objects.get(bk_data_id=self.bk_data_id)
            return True
        except models.DataSource.DoesNotExist:
            self.errors.append(f"DataSource 不存在: bk_data_id={self.bk_data_id}")
            return False

    def get_current_version(self) -> str:
        """获取当前链路版本"""
        if self.datasource.created_from == DataIdCreatedFromSystem.BKDATA.value:
            return "V4"
        return "V3"

    def is_log_type(self) -> bool:
        """判断是否是日志类型（包含 APM Trace，因为 APM Trace 的 etl_config 也是 bk_flat_batch）"""
        if not self.datasource:
            return False
        return self.datasource.etl_config in self.LOG_ETL_CONFIGS

    def is_apm_type(self) -> bool:
        """
        判断是否是 APM 数据类型

        APM Trace 的 etl_config 也是 bk_flat_batch，与日志相同，
        但数据结构完全不同（trace_id/span_id 等字段），需要单独处理。
        通过 table_id 前缀区分，参考 metadata/migration_util.py 中的 filter_apm_log_table_ids()
        """
        if not self.datasource or not self.is_log_type():
            return False
        table_id = self.get_result_table()
        if not table_id:
            return False
        return (
            table_id.startswith("bkapm_")
            or table_id.startswith("apm_global")
            or "_bkapm" in table_id
        )

    def is_pure_log_type(self) -> bool:
        """判断是否是纯日志类型（排除 APM）"""
        return self.is_log_type() and not self.is_apm_type()

    def get_result_table(self) -> Optional[str]:
        """获取关联的结果表"""
        try:
            rt = models.DataSourceResultTable.objects.get(bk_data_id=self.bk_data_id)
            return rt.table_id
        except models.DataSourceResultTable.DoesNotExist:
            return None

    def get_collector_config(self) -> Optional["CollectorConfig"]:
        """获取关联的采集配置"""
        if not BKLOG_AVAILABLE:
            return None
        try:
            return CollectorConfig.objects.get(bk_data_id=self.bk_data_id)
        except CollectorConfig.DoesNotExist:
            return None

    def build_log_v4_data_link_config(self, table_id: str) -> Optional[dict]:
        """
        构建日志 V4 链路配置 (log_v4_data_link)

        注意: APM 类型不应调用此方法。APM 使用 TransferAdaptor 方案，
        配置由 _apply_apm_v4_datalink() 直接构建。

        尝试以下方式构建配置：
        1. 如果能获取到 CollectorConfig，使用 bklog 的 EtlStorage 构建
        2. 否则，使用默认配置模板

        Args:
            table_id: 结果表 ID

        Returns:
            log_v4_data_link 配置字典，如果无法构建则返回 None
        """
        # APM 类型使用 TransferAdaptor 方案，不需要通过此方法构建 clean_rules
        # TransferAdaptor 配置在 _apply_apm_v4_datalink() 中直接构建
        if self.is_apm_type():
            Printer.info("APM TransferAdaptor 方案: 跳过 build_log_v4_data_link_config, 配置由 _apply_apm_v4_datalink() 构建")
            return None

        # 尝试从 CollectorConfig 获取配置
        collector_config = self.get_collector_config()

        if collector_config and BKLOG_AVAILABLE:
            return self._build_config_from_collector(collector_config, table_id)
        else:
            return self._build_default_config(table_id)

    def _build_config_from_collector(
        self, collector_config, table_id: str
    ) -> Optional[dict]:
        """从 CollectorConfig 构建 log_v4_data_link 配置"""
        try:
            # 获取 ETL 配置信息
            etl_config_data = collector_config.get_etl_config()
            fields = etl_config_data.get("fields", [])
            etl_params = etl_config_data.get("etl_params", {})

            # 获取 EtlStorage 实例
            etl_config_type = collector_config.etl_config or "bk_log_text"
            etl_storage = EtlStorage.get_instance(etl_config=etl_config_type)

            # 获取内置配置
            collector_scenario = CollectorScenario.get_instance(
                collector_scenario_id=collector_config.collector_scenario_id
            )
            built_in_config = collector_scenario.get_built_in_config(
                es_version="7.X",  # 使用 7.X 版本配置
                etl_config=etl_config_type,
            )

            # 添加 separator_configs 如果存在 path_regexp
            path_regexp = etl_params.get("path_regexp", "")
            if path_regexp:
                built_in_config["option"]["separator_configs"] = [
                    {
                        "separator_node_name": "bk_separator_object_path",
                        "separator_node_action": "regexp",
                        "separator_node_source": "filename",
                        "separator_regexp": path_regexp,
                    }
                ]

            # 构建 log_v4_data_link 配置
            log_v4_config = etl_storage.build_log_v4_data_link(
                fields=fields, etl_params=etl_params, built_in_config=built_in_config
            )

            Printer.success(f"从 CollectorConfig 构建 log_v4_data_link 配置成功")
            Printer.kv("etl_config", etl_config_type, indent=6)
            Printer.kv("fields_count", len(fields), indent=6)

            return log_v4_config

        except Exception as e:
            Printer.warning(f"从 CollectorConfig 构建配置失败: {e}")
            Printer.info("将使用默认配置模板")
            return self._build_default_config(table_id)

    def _build_default_config(self, table_id: str) -> dict:
        """
        构建默认的 log_v4_data_link 配置

        用于以下场景：
        1. 无法获取 CollectorConfig
        2. bklog 模块不可用
        3. 从 CollectorConfig 构建失败
        """
        # 获取 ES 存储配置以确定 unique_field_list
        unique_field_list = [
            "cloudId",
            "serverIp",
            "path",
            "gseIndex",
            "iterationIndex",
            "bk_host_id",
            "dtEventTimeStamp",
        ]

        try:
            es_storage = models.ESStorage.objects.filter(table_id=table_id).first()
            if es_storage:
                # 尝试从 ResultTableOption 获取 es_unique_field_list
                option = models.ResultTableOption.objects.filter(
                    table_id=table_id, name="es_unique_field_list"
                ).first()
                if option:
                    value = option.get_value()
                    if isinstance(value, list):
                        unique_field_list = value
        except Exception as e:
            Printer.warning(f"获取 ES 配置失败，使用默认 unique_field_list: {e}")

        # 构建默认的 clean_rules（直接入库类型）
        default_config = {
            "clean_rules": [
                # 1. JSON 解析阶段
                {
                    "input_id": "__raw_data",
                    "output_id": "json_data",
                    "operator": {"type": "json_de", "error_strategy": "drop"},
                },
                # 2. 提取内置字段 - bk_host_id
                {
                    "input_id": "json_data",
                    "output_id": "bk_host_id",
                    "operator": {
                        "type": "assign",
                        "key_index": "bk_host_id",
                        "alias": "bk_host_id",
                        "desc": "主机ID",
                        "input_type": None,
                        "output_type": "long",
                        "fixed_value": None,
                        "is_time_field": None,
                        "time_format": None,
                        "in_place_time_parsing": None,
                        "default_value": None,
                    },
                },
                # 3. 提取内置字段 - cloudId
                {
                    "input_id": "json_data",
                    "output_id": "cloudId",
                    "operator": {
                        "type": "assign",
                        "key_index": "cloudid",
                        "alias": "cloudId",
                        "desc": "云区域ID",
                        "input_type": None,
                        "output_type": "long",
                        "fixed_value": None,
                        "is_time_field": None,
                        "time_format": None,
                        "in_place_time_parsing": None,
                        "default_value": None,
                    },
                },
                # 4. 提取内置字段 - serverIp
                {
                    "input_id": "json_data",
                    "output_id": "serverIp",
                    "operator": {
                        "type": "assign",
                        "key_index": "ip",
                        "alias": "serverIp",
                        "desc": "ip",
                        "input_type": None,
                        "output_type": "string",
                        "fixed_value": None,
                        "is_time_field": None,
                        "time_format": None,
                        "in_place_time_parsing": None,
                        "default_value": None,
                    },
                },
                # 5. 提取内置字段 - path
                {
                    "input_id": "json_data",
                    "output_id": "path",
                    "operator": {
                        "type": "assign",
                        "key_index": "filename",
                        "alias": "path",
                        "desc": "日志路径",
                        "input_type": None,
                        "output_type": "string",
                        "fixed_value": None,
                        "is_time_field": None,
                        "time_format": None,
                        "in_place_time_parsing": None,
                        "default_value": None,
                    },
                },
                # 6. 提取内置字段 - gseIndex
                {
                    "input_id": "json_data",
                    "output_id": "gseIndex",
                    "operator": {
                        "type": "assign",
                        "key_index": "gseindex",
                        "alias": "gseIndex",
                        "desc": "gse索引",
                        "input_type": None,
                        "output_type": "long",
                        "fixed_value": None,
                        "is_time_field": None,
                        "time_format": None,
                        "in_place_time_parsing": None,
                        "default_value": None,
                    },
                },
                # 7. 提取时间字段 - dtEventTimeStamp
                {
                    "input_id": "json_data",
                    "output_id": "dtEventTimeStamp",
                    "operator": {
                        "type": "assign",
                        "key_index": "utctime",
                        "alias": "dtEventTimeStamp",
                        "desc": "数据时间",
                        "input_type": None,
                        "output_type": "long",
                        "fixed_value": None,
                        "is_time_field": None,
                        "time_format": None,
                        "in_place_time_parsing": {
                            "from": {"format": "%Y-%m-%d %H:%M:%S", "zone": 0},
                            "interval_format": None,
                            "to": "millis",
                            "now_if_parse_failed": True,
                        },
                        "default_value": None,
                    },
                },
                # 8. 提取 items 数组
                {
                    "input_id": "json_data",
                    "output_id": "items",
                    "operator": {
                        "type": "get",
                        "key_index": [{"type": "key", "value": "items"}],
                        "missing_strategy": None,
                    },
                },
                # 9. 迭代 items
                {
                    "input_id": "items",
                    "output_id": "iter_item",
                    "operator": {"type": "iter"},
                },
                # 10. 提取原文
                {
                    "input_id": "iter_item",
                    "output_id": "log",
                    "operator": {
                        "type": "assign",
                        "key_index": "data",
                        "alias": "log",
                        "output_type": "string",
                    },
                },
            ],
            "es_storage_config": {
                "unique_field_list": unique_field_list,
                "timezone": 8,
            },
            "doris_storage_config": None,
        }

        Printer.info("使用默认配置模板构建 log_v4_data_link")
        Printer.kv("unique_field_list", unique_field_list, indent=6)

        return default_config

    def _build_apm_transfer_adaptor_transform(self, ds) -> dict:
        """
        构建 APM 数据类型的 TransferAdaptor transform JSON

        选项 C 方案: 不手写 clean_rules，而是构造 BkFlatBatchConfig JSON，
        让 BKBase Databus 运行时自动通过 generate_etl_rules() 生成正确的清洗规则。

        BKBase 运行时处理流程:
        TransferAdaptor(BkFlatBatchConfig)
          → TryInto::<EtlConfig>
          → ResultTable.generate_etl_rules()
          → 根据 field_list 自动生成 clean rules（含 time 字段、nested 类型等正确处理）

        参考:
        - bk_flat_batch.rs: BkFlatBatchConfig 结构体 + generate_etl_rules()
        - bk_flat_batch_test_trace.rs: APM Trace 的完整 BkFlatBatchConfig JSON 示例
        - transform.rs: TransformConfig enum, #[serde(tag = "kind")]

        Args:
            ds: DataSource 实例

        Returns:
            TransferAdaptor transform dict，可直接嵌入 Databus spec.transforms
        """
        # 从 DataSource.to_json() 获取完整配置
        ds_json = ds.to_json(is_consul_config=False, with_rt_info=True)
        Printer.info("从 DataSource.to_json() 获取配置")
        Printer.kv("bk_data_id", ds_json["bk_data_id"], indent=6)
        Printer.kv("etl_config", ds_json["etl_config"], indent=6)
        Printer.kv("data_name", ds_json["data_name"], indent=6)

        if not ds_json.get("result_table_list"):
            raise ValueError("DataSource.to_json() 返回的 result_table_list 为空")

        # 适配 mq_config: DataSource.to_json() 包含 batch_size/flush_interval/consume_rate，
        # BkFlatBatchConfig 需要 cluster_type 和 auth_info
        mq_config = ds_json["mq_config"]
        # 确保有 cluster_type（来自 consul_config）
        if "cluster_type" not in mq_config:
            mq_config["cluster_type"] = "kafka"
        # 确保有 auth_info
        if "auth_info" not in mq_config:
            mq_config["auth_info"] = {"password": "", "username": ""}
        # 移除 BkFlatBatchConfig 不需要的字段
        for key in ["batch_size", "flush_interval", "consume_rate"]:
            mq_config.pop(key, None)

        # 适配 result_table_list
        adapted_rt_list = []
        for rt_info in ds_json["result_table_list"]:
            field_list = rt_info.get("field_list", [])

            # 检查 field_list 中是否包含 time 字段（tag=timestamp）
            # BkFlatBatchConfig 要求有 time 字段，否则 generate_etl_rules() 无法正确生成时间解析规则
            has_time_field = any(
                f.get("field_name") == "time" and f.get("tag") == "timestamp"
                for f in field_list
            )
            if not has_time_field:
                Printer.warning("field_list 中缺少 time 字段（tag=timestamp），手动补充")
                field_list.append({
                    "field_name": "time",
                    "type": "timestamp",
                    "tag": "timestamp",
                    "option": {
                        "es_type": "date",
                        "es_format": "epoch_millis",
                        "time_format": "yyyy-MM-dd HH:mm:ss",
                        "time_zone": 0,
                    },
                })

            # 适配 option: 确保有 es_unique_field_list，且不含 separator_node_action
            rt_option = rt_info.get("option", {})
            if "es_unique_field_list" not in rt_option:
                # 使用 APM Trace 默认的 unique_field_list
                rt_option["es_unique_field_list"] = [
                    "trace_id", "span_id", "parent_span_id",
                    "start_time", "end_time", "span_name",
                ]
                Printer.warning("option 中缺少 es_unique_field_list，使用 APM Trace 默认值")

            # 确保不含 separator_node_action（None 触发 ItemsObjectAction，APM 需要这个）
            if "separator_node_action" in rt_option:
                Printer.warning("移除 option 中的 separator_node_action（APM 需要 ItemsObjectAction）")
                del rt_option["separator_node_action"]

            adapted_rt = {
                "bk_biz_id": rt_info["bk_biz_id"],
                "result_table": rt_info["result_table"],
                "schema_type": rt_info.get("schema_type", "free"),
                "shipper_list": rt_info.get("shipper_list", []),
                "field_list": field_list,
                "option": rt_option,
            }
            adapted_rt_list.append(adapted_rt)

        # 构造 TransferAdaptor transform
        transfer_adaptor = {
            "kind": "TransferAdaptor",
            "bk_data_id": ds_json["bk_data_id"],
            "data_id": ds_json["bk_data_id"],
            "etl_config": ds_json.get("etl_config", "bk_flat_batch"),
            "data_name": ds_json["data_name"],
            "mq_config": mq_config,
            "result_table_list": adapted_rt_list,
        }

        Printer.success("TransferAdaptor transform 构建完成")
        Printer.kv("result_table_count", len(adapted_rt_list), indent=6)
        for rt in adapted_rt_list:
            Printer.kv("result_table", rt["result_table"], indent=8)
            Printer.kv("field_count", len(rt["field_list"]), indent=8)
            field_names = [f["field_name"] for f in rt["field_list"]]
            Printer.kv("fields", field_names, indent=8)

        return transfer_adaptor

    def _setup_apm_v4_options(self, ds, table_id: str, creator: str = "migrate_script"):
        """
        设置 APM V4 链路的 ResultTableOption

        选项 C 方案下，APM 不需要在 ResultTableOption 中存储 clean_rules，
        因为清洗规则由 BKBase 运行时通过 TransferAdaptor(BkFlatBatchConfig) 自动生成。
        此方法仅设置 enable_log_v4_data_link=True 标记。

        Args:
            ds: DataSource 实例
            table_id: 结果表 ID
            creator: 创建者标识
        """
        # 设置 ResultTableOption: enable_log_v4_data_link
        Printer.info("设置 ResultTableOption enable_log_v4_data_link=True (APM TransferAdaptor 方案)")
        option, opt_created = models.ResultTableOption.objects.update_or_create(
            table_id=table_id,
            name=ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK,
            bk_tenant_id=ds.bk_tenant_id,
            defaults={
                "value": "true",
                "value_type": ResultTableOption.TYPE_BOOL,
                "creator": creator,
            },
        )
        if opt_created:
            Printer.success("ResultTableOption enable_log_v4_data_link 创建成功")
        else:
            Printer.info("ResultTableOption enable_log_v4_data_link 已存在，已更新")

        # 注意: 选项 C 方案下，不再设置 OPTION_V4_LOG_DATA_LINK (log_v4_data_link)
        # APM 的清洗规则由 BKBase 运行时通过 TransferAdaptor(BkFlatBatchConfig) 自动生成
        # 而非通过 ResultTableOption 中的 clean_rules 传递
        Printer.info("APM TransferAdaptor 方案: 跳过设置 log_v4_data_link option（清洗由 BKBase 运行时自动处理）")

    def _apply_apm_v4_datalink(self, ds, table_id: str, bk_biz_id: int):
        """
        APM 专用: 创建 V4 数据链路（TransferAdaptor 方案）

        不使用 apply_log_datalink()，因为其内部 compose_log_config() 硬编码了 kind: "Clean"。
        APM 需要 kind: "TransferAdaptor" + BkFlatBatchConfig，让 BKBase 运行时自动生成清洗规则。

        流程参考 apply_log_datalink() (task/datalink.py:21-131) 和
        compose_log_configs() (data_link.py:327-469)，但 Databus JSON 手动构建。

        Args:
            ds: DataSource 实例
            table_id: 结果表 ID
            bk_biz_id: 业务 ID
        """
        from django.db import transaction

        Printer.section("APM TransferAdaptor V4 数据链路创建")

        # 1. 如果 DataSource 是 GSE 创建的，需要在 BKBase 上注册
        if ds.created_from != DataIdCreatedFromSystem.BKDATA.value:
            Printer.info("DataSource 非 BKBase 创建，先注册到 BKBase")
            # FIXME: 疑点 - APM 的 namespace 应该使用 bkapm 还是 bklog？
            #  此处沿用 bklog 与 _apply_dataid_config_to_bkbase 中的 FIXME 一致
            ds.register_to_bkbase(bk_biz_id=bk_biz_id, namespace=BKBASE_NAMESPACE_BK_LOG)
            Printer.success("DataSource 注册到 BKBase 完成")

        # 2. 获取 ES 存储信息
        es_storage = models.ESStorage.objects.filter(
            bk_tenant_id=ds.bk_tenant_id, table_id=table_id
        ).first()
        if not es_storage:
            raise ValueError(f"APM V4 链路: 未找到 ES 存储配置 (table_id={table_id})")
        Printer.kv("ES 集群", es_storage.storage_cluster.cluster_name)

        # 3. 获取或创建 DataLink + BkBaseResultTable
        bkbase_data_name = datalink_utils.compose_bkdata_data_id_name(ds.data_name)
        Printer.kv("bkbase_data_name", bkbase_data_name)

        bkbase_rt = models.BkBaseResultTable.objects.filter(
            bk_tenant_id=ds.bk_tenant_id, monitor_table_id=table_id
        ).first()

        # FIXME: 疑点 - namespace 应该使用 bkapm 还是 bklog？
        #  与 _apply_dataid_config_to_bkbase 中的 FIXME 一致，暂用 bklog
        namespace = BKBASE_NAMESPACE_BK_LOG

        if not bkbase_rt:
            # 生成链路名称
            if bk_biz_id < 0:
                bk_biz_id_str = f"space_{-bk_biz_id}"
            else:
                bk_biz_id_str = str(bk_biz_id)

            random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=16))
            data_link_name = f"bkapm_{bk_biz_id_str}_{random_str}"

            # 确保唯一
            while models.DataLink.objects.filter(data_link_name=data_link_name).exists():
                random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=16))
                data_link_name = f"bkapm_{bk_biz_id_str}_{random_str}"

            Printer.kv("data_link_name", data_link_name)
            Printer.info("创建新 DataLink")

            datalink = models.DataLink.objects.create(
                bk_tenant_id=ds.bk_tenant_id,
                data_link_name=data_link_name,
                namespace=namespace,
                data_link_strategy=models.DataLink.BK_LOG,
                **({
                    "bk_data_id": ds.bk_data_id,
                    "table_ids": [table_id],
                } if hasattr(models.DataLink, "bk_data_id") else {}),
            )
        else:
            data_link_name = bkbase_rt.data_link_name
            Printer.kv("data_link_name", data_link_name, color=Printer.YELLOW)
            Printer.info("DataLink 已存在，复用")

            datalink = models.DataLink.objects.get(
                bk_tenant_id=ds.bk_tenant_id,
                data_link_name=data_link_name,
                namespace=namespace,
            )
            # DataLink.bk_data_id / table_ids 可能在旧版本中不存在，安全更新
            update_fields = []
            if hasattr(datalink, "bk_data_id") and datalink.bk_data_id != ds.bk_data_id:
                datalink.bk_data_id = ds.bk_data_id
                update_fields.append("bk_data_id")
            if hasattr(datalink, "table_ids") and datalink.table_ids != [table_id]:
                datalink.table_ids = [table_id]
                update_fields.append("table_ids")
            if update_fields:
                datalink.save(update_fields=update_fields)

        # 4. 创建 ORM 配置记录 + 组装 config_list
        Printer.info("组装 V4 链路配置 (TransferAdaptor)")

        with transaction.atomic():
            # 4a. ResultTableConfig ORM
            fields = generate_result_table_field_list(table_id=table_id, bk_tenant_id=ds.bk_tenant_id)
            Printer.kv("ResultTable fields 数量", len(fields))

            result_table_config, _ = models.ResultTableConfig.objects.update_or_create(
                bk_tenant_id=ds.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                namespace=namespace,
                data_link_name=data_link_name,
                name=data_link_name,
                # NOTE: table_id 字段在较新版本才有，旧版本环境不存在该字段
                # compose_config() 不依赖 self.table_id，所以此处不设置
            )

            # 4b. ESStorageBindingConfig ORM
            index_name = table_id.replace(".", "_")
            write_alias = f"write_%Y%m%d_{index_name}"

            # APM Trace 的 unique_field_list
            unique_field_list = [
                "trace_id", "span_id", "parent_span_id",
                "start_time", "end_time", "span_name",
            ]

            es_binding, _ = models.ESStorageBindingConfig.objects.update_or_create(
                bk_tenant_id=ds.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                namespace=namespace,
                data_link_name=data_link_name,
                name=data_link_name,
                defaults={
                    "es_cluster_name": es_storage.storage_cluster.cluster_name,
                    "timezone": es_storage.time_zone,
                    # NOTE: table_id 字段在较新版本才有，旧版本环境不存在该字段
                    # compose_config() 不依赖 self.table_id，所以此处不设置
                },
            )

            es_binding_config = es_binding.compose_config(
                storage_cluster_name=es_storage.storage_cluster.cluster_name,
                write_alias_format=write_alias,
                unique_field_list=unique_field_list,
            )

            databus_sinks = [
                {
                    "kind": DataLinkKind.ESSTORAGEBINDING.value,
                    "name": data_link_name,
                    "namespace": namespace,
                }
            ]

            # 4c. DataBusConfig ORM（只创建 ORM 记录，不用 compose_log_config）
            # NOTE: bk_data_id 字段在较新版本才有，旧版本环境不存在该字段
            databus_orm, _ = models.DataBusConfig.objects.update_or_create(
                bk_tenant_id=ds.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                namespace=namespace,
                data_link_name=data_link_name,
                name=data_link_name,
                data_id_name=bkbase_data_name,
            )

            # 4d. 手动构建 Databus JSON（TransferAdaptor，不用 compose_log_config 的 Clean 模板）
            transfer_adaptor = self._build_apm_transfer_adaptor_transform(ds)

            maintainer = getattr(settings, "BK_DATA_PROJECT_MAINTAINER", "admin").split(",")

            databus_json = {
                "kind": "Databus",
                "metadata": {
                    "name": data_link_name,
                    "namespace": namespace,
                    "labels": {"bk_biz_id": str(databus_orm.datalink_biz_ids.label_biz_id)},
                },
                "spec": {
                    "maintainers": maintainer,
                    "sinks": databus_sinks,
                    "sources": [
                        {
                            "kind": "DataId",
                            "name": bkbase_data_name,
                            "namespace": namespace,
                        }
                    ],
                    "transforms": [transfer_adaptor],
                },
            }

            # 多租户模式下添加 tenant 字段
            if getattr(settings, "ENABLE_MULTI_TENANT_MODE", False):
                databus_json["metadata"]["tenant"] = ds.bk_tenant_id
                databus_json["spec"]["sources"][0]["tenant"] = ds.bk_tenant_id

            # 4e. 组装 config_list
            config_list = [
                result_table_config.compose_config(fields=fields),
                es_binding_config,
                databus_json,
            ]

        # 5. 创建 BkBaseResultTable ORM
        Printer.info("创建/更新 BkBaseResultTable 记录")
        models.BkBaseResultTable.objects.get_or_create(
            data_link_name=data_link_name,
            monitor_table_id=table_id,
            bkbase_data_name=data_link_name,
            storage_type="elasticsearch",
            defaults={
                "status": DataLinkResourceStatus.INITIALIZING.value,
            },
            bk_tenant_id=ds.bk_tenant_id,
        )

        # 6. 调用 API 下发
        Printer.info("下发 APM V4 链路配置到 BKBase")
        Printer.kv("config 数量", len(config_list))
        for i, cfg in enumerate(config_list):
            Printer.kv(f"config[{i}].kind", cfg.get("kind", "unknown"), indent=6)

        response = api.bkdata.apply_data_link(
            bk_tenant_id=ds.bk_tenant_id,
            config=config_list,
        )
        Printer.success("APM V4 链路配置下发成功")
        Printer.kv("response", response, indent=6)

        # 7. 清理 transfer 链路配置（如果 DataSource 原来不是 BKBase 创建的）
        if ds.created_from != DataIdCreatedFromSystem.BKDATA.value:
            Printer.info("清理旧 transfer 链路的 Consul 配置")
            ds.delete_consul_config()
            Printer.success("Consul 配置已清理")

    def get_bk_biz_id(self) -> int:
        """获取业务 ID"""
        if self.bk_biz_id:
            return self.bk_biz_id

        # 尝试从结果表获取
        table_id = self.get_result_table()
        if table_id:
            try:
                rt = models.ResultTable.objects.get(table_id=table_id)
                if rt.bk_biz_id:
                    return rt.bk_biz_id
            except models.ResultTable.DoesNotExist:
                pass

        # 使用默认业务 ID
        return getattr(settings, "DEFAULT_BKDATA_BIZ_ID", 0)

    def validate_for_migration(self) -> bool:
        """校验是否可以迁移到 V4"""
        self.errors = []
        self.warnings = []

        if not self.load_datasource():
            return False

        ds = self.datasource

        # 1. 检查是否已经是 V4
        if ds.created_from == DataIdCreatedFromSystem.BKDATA.value:
            self.errors.append("该 DataID 已经是 V4 链路，无需迁移")
            return False

        # 2. 检查是否启用
        if not ds.is_enable:
            self.errors.append("该 DataID 已禁用 (is_enable=False)，请先启用")
            return False

        # 3. 检查 etl_config 是否支持
        if ds.etl_config not in self.SUPPORTED_ETL_CONFIGS:
            self.errors.append(f"etl_config '{ds.etl_config}' 不支持迁移到 V4")
            self.errors.append(f"支持的 etl_config: {self.SUPPORTED_ETL_CONFIGS}")
            return False

        # 4. 检查全局开关 (仅对指标类型有效，日志类型使用 ResultTableOption 控制)
        if not self.is_log_type():
            if not getattr(settings, "ENABLE_V2_VM_DATA_LINK", False):
                self.warnings.append("全局开关 ENABLE_V2_VM_DATA_LINK 未启用")
                self.warnings.append("迁移后需要启用此开关才能正常工作")

        # 5. 检查是否有关联结果表
        table_id = self.get_result_table()
        if not table_id:
            self.errors.append("该 DataID 无关联结果表，无法迁移")
            return False

        # 6. 检查存储记录
        if self.is_apm_type():
            # APM 类型: 检查 ES 存储
            if not models.ESStorage.objects.filter(table_id=table_id).exists():
                self.warnings.append(f"结果表 {table_id} 无 ES 存储记录")
                self.warnings.append("APM 类型迁移后数据将使用 APM 专用清洗规则存储")
            # 检查是否已有 V4 配置
            try:
                option = models.ResultTableOption.objects.get(
                    table_id=table_id,
                    name=ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK,
                )
                log_v4_enabled = (
                    option.value.lower() == "true"
                    if isinstance(option.value, str)
                    else bool(option.value)
                )
                if log_v4_enabled:
                    self.warnings.append(f"结果表 {table_id} 已启用 V4 链路")
            except models.ResultTableOption.DoesNotExist:
                pass
        elif self.is_pure_log_type():
            # 日志类型: 检查 ES 存储
            if not models.ESStorage.objects.filter(table_id=table_id).exists():
                self.warnings.append(f"结果表 {table_id} 无 ES 存储记录")
                self.warnings.append("日志类型迁移后数据将存储到 Doris/ES")
            # 检查是否已有日志 V4 配置
            try:
                option = models.ResultTableOption.objects.get(
                    table_id=table_id,
                    name=ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK,
                )
                log_v4_enabled = (
                    option.value.lower() == "true"
                    if isinstance(option.value, str)
                    else bool(option.value)
                )
                if log_v4_enabled:
                    self.warnings.append(f"结果表 {table_id} 已启用日志 V4 链路")
            except models.ResultTableOption.DoesNotExist:
                pass
        else:
            # 指标类型: 检查 VM 记录
            if models.AccessVMRecord.objects.filter(result_table_id=table_id).exists():
                self.warnings.append(
                    f"结果表 {table_id} 已有 AccessVMRecord，迁移时将跳过创建"
                )

        # 7. 检查 Kafka 配置
        try:
            kafka_topic = models.KafkaTopicInfo.objects.get(bk_data_id=self.bk_data_id)
        except models.KafkaTopicInfo.DoesNotExist:
            self.errors.append("该 DataID 无 Kafka Topic 配置")
            return False

        return len(self.errors) == 0

    def validate_for_rollback(self) -> bool:
        """校验是否可以回滚到 V3"""
        self.errors = []
        self.warnings = []

        if not self.load_datasource():
            return False

        ds = self.datasource

        # 1. 检查是否是 V4
        if ds.created_from != DataIdCreatedFromSystem.BKDATA.value:
            self.errors.append("该 DataID 不是 V4 链路，无法回滚")
            return False

        # 2. 检查是否启用
        if not ds.is_enable:
            self.warnings.append("该 DataID 已禁用，回滚后需要手动启用")

        return len(self.errors) == 0

    def diagnose(self):
        """诊断 DataID 状态"""
        Printer.header(f"DataID {self.bk_data_id} 迁移诊断")
        print(f"  诊断时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if not self.load_datasource():
            Printer.error(self.errors[0])
            return

        ds = self.datasource
        current_version = self.get_current_version()
        table_id = self.get_result_table()

        # 基本信息
        Printer.section("1. 基本信息")
        Printer.kv("bk_data_id", ds.bk_data_id)
        Printer.kv("data_name", ds.data_name)
        Printer.kv("bk_tenant_id", ds.bk_tenant_id)
        Printer.kv("etl_config", ds.etl_config)
        Printer.kv(
            "is_enable",
            ds.is_enable,
            color=Printer.GREEN if ds.is_enable else Printer.RED,
        )
        Printer.kv(
            "created_from",
            ds.created_from,
            color=Printer.GREEN if ds.created_from == "bkdata" else Printer.YELLOW,
        )
        Printer.kv("transfer_cluster_id", ds.transfer_cluster_id)

        # 当前链路版本
        Printer.section("2. 当前链路版本")
        version_color = Printer.GREEN if current_version == "V4" else Printer.YELLOW
        Printer.kv("链路版本", current_version, color=version_color)

        if current_version == "V3":
            Printer.info("V3 链路: GSE -> Transfer -> InfluxDB")
        else:
            Printer.info("V4 链路: GSE -> BKBase -> VictoriaMetrics")

        # 关联结果表
        Printer.section("3. 关联结果表")
        if table_id:
            Printer.kv("table_id", table_id)
            try:
                rt = models.ResultTable.objects.get(table_id=table_id)
                Printer.kv("bk_biz_id", rt.bk_biz_id)
                Printer.kv("schema_type", rt.schema_type)
                Printer.kv("default_storage", rt.default_storage)
            except models.ResultTable.DoesNotExist:
                Printer.warning("结果表详情未找到")
        else:
            Printer.error("无关联结果表")

        # 存储记录
        Printer.section("4. 存储记录")

        # V4 (VM) 记录
        if table_id:
            try:
                vm_record = models.AccessVMRecord.objects.get(result_table_id=table_id)
                Printer.success("存在 VM 记录 (V4)")
                Printer.kv("vm_result_table_id", vm_record.vm_result_table_id, indent=6)
                Printer.kv("bk_base_data_id", vm_record.bk_base_data_id, indent=6)
                Printer.kv("vm_cluster_id", vm_record.vm_cluster_id, indent=6)
            except models.AccessVMRecord.DoesNotExist:
                Printer.info("无 VM 记录")

            # V3 (InfluxDB) 记录
            try:
                influx = models.InfluxDBStorage.objects.get(table_id=table_id)
                Printer.success("存在 InfluxDB 记录 (V3)")
                Printer.kv("database", influx.database, indent=6)
                Printer.kv("real_table_name", influx.real_table_name, indent=6)
                Printer.kv("proxy_cluster_name", influx.proxy_cluster_name, indent=6)
            except models.InfluxDBStorage.DoesNotExist:
                Printer.info("无 InfluxDB 记录")

        # 迁移可行性分析
        Printer.section("5. 迁移可行性分析")

        can_migrate = self.validate_for_migration()

        if can_migrate:
            Printer.success("可以迁移到 V4")
        else:
            Printer.error("无法迁移到 V4")
            for error in self.errors:
                Printer.error(error)

        if self.warnings:
            print()
            print("  警告:")
            for warning in self.warnings:
                Printer.warning(warning)

        # 回滚可行性分析
        Printer.section("6. 回滚可行性分析")

        # 重置错误列表
        self.errors = []
        self.warnings = []
        can_rollback = self.validate_for_rollback()

        if can_rollback:
            Printer.success("可以回滚到 V3")
        else:
            Printer.error("无法回滚到 V3")
            for error in self.errors:
                Printer.error(error)

        # 全局配置
        Printer.section("7. 全局配置状态")
        Printer.kv(
            "ENABLE_V2_VM_DATA_LINK", getattr(settings, "ENABLE_V2_VM_DATA_LINK", False)
        )
        Printer.kv(
            "ENABLE_INFLUXDB_STORAGE",
            getattr(settings, "ENABLE_INFLUXDB_STORAGE", True),
        )
        Printer.kv("DEFAULT_BKDATA_BIZ_ID", getattr(settings, "DEFAULT_BKDATA_BIZ_ID", 0))

        print()
        print(Printer.colorize("=" * 70, Printer.CYAN))
        print(Printer.colorize(" 诊断完成", Printer.CYAN + Printer.BOLD))
        print(Printer.colorize("=" * 70, Printer.CYAN))

    def migrate(self):
        """执行 V3 -> V4 迁移"""
        Printer.header(f"DataID {self.bk_data_id} 迁移 V3 -> V4")
        print(f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 校验
        if not self.validate_for_migration():
            Printer.section("校验失败")
            for error in self.errors:
                Printer.error(error)
            return False

        ds = self.datasource
        table_id = self.get_result_table()
        bk_biz_id = self.get_bk_biz_id()

        try:
            # Step 1: 校验 etl_config
            Printer.step(1, "校验 ETL 配置兼容性")
            Printer.kv("etl_config", ds.etl_config)
            Printer.success("校验通过")

            # Step 2: 更改 created_from，删除 Consul 配置
            Printer.step(2, "更改数据源来源为 bkdata")
            Printer.info(f"原始值: {ds.created_from}")

            modify_data_id_source(
                bk_tenant_id=ds.bk_tenant_id,
                data_id_list=[self.bk_data_id],
                source_type=DataIdCreatedFromSystem.BKDATA.value,
            )
            Printer.success(
                f"已更改 created_from 为 {DataIdCreatedFromSystem.BKDATA.value}"
            )
            Printer.success("已删除 Consul 配置")

            # Step 3-4: 创建 DataIdConfig 并下发至 BKBase
            Printer.step(3, "创建 DataIdConfig (计算平台侧)")
            Printer.step(4, "下发 DataId Config 至 BKBase")
            data_id_ins = self._apply_dataid_config_to_bkbase(ds, bk_biz_id)

            # Step 5: 创建完整 V4 数据链路
            Printer.step(5, "创建完整 V4 数据链路")
            self._create_v4_datalink(ds, table_id, bk_biz_id)

            # Step 6: 验证组件状态
            Printer.step(6, "验证组件状态")
            self._verify_migration_result(data_id_ins, table_id)

            print()
            print(Printer.colorize("=" * 70, Printer.GREEN))
            print(
                Printer.colorize(
                    f" 迁移成功! DataID {self.bk_data_id} 已切换至 V4 链路",
                    Printer.GREEN + Printer.BOLD,
                )
            )
            print(Printer.colorize("=" * 70, Printer.GREEN))
            return True

        except Exception as e:
            Printer.error(f"迁移失败: {e}")
            print()
            print(Printer.colorize("  建议: 使用 --rollback 回滚到 V3 链路", Printer.YELLOW))
            return False

    def retry_migrate(self):
        """重试 V3 -> V4 迁移 (用于 BKBase 配置下发失败后的重试)"""
        Printer.header(f"DataID {self.bk_data_id} 重试迁移 V3 -> V4")
        print(f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 加载数据源
        if not self.load_datasource():
            Printer.section("加载失败")
            for error in self.errors:
                Printer.error(error)
            return False

        ds = self.datasource
        table_id = self.get_result_table()
        bk_biz_id = self.get_bk_biz_id()

        # 检查是否已经是 V4 链路
        if ds.created_from != DataIdCreatedFromSystem.BKDATA.value:
            Printer.error("该 DataID 不是 V4 链路，无法重试")
            Printer.info("请先使用 --migrate 执行完整迁移")
            return False

        # 检查是否有关联结果表
        if not table_id:
            Printer.error("该 DataID 无关联结果表，无法重试")
            return False

        try:
            # Step 1-2: 获取或创建 DataIdConfig 并下发至 BKBase
            Printer.step(1, "获取或创建 DataIdConfig (计算平台侧)")
            Printer.step(2, "重试下发 DataId Config 至 BKBase")
            data_id_ins = self._apply_dataid_config_to_bkbase(ds, bk_biz_id)

            # Step 3: 创建完整 V4 数据链路
            Printer.step(3, "创建完整 V4 数据链路")
            self._create_v4_datalink(ds, table_id, bk_biz_id)

            # Step 4: 验证组件状态
            Printer.step(4, "验证组件状态")
            self._verify_migration_result(data_id_ins, table_id)

            print()
            print(Printer.colorize("=" * 70, Printer.GREEN))
            print(
                Printer.colorize(
                    f" 重试迁移成功! DataID {self.bk_data_id} 已切换至 V4 链路",
                    Printer.GREEN + Printer.BOLD,
                )
            )
            print(Printer.colorize("=" * 70, Printer.GREEN))
            return True

        except Exception as e:
            Printer.error(f"重试迁移失败: {e}")
            return False

    def rollback(self):
        """回滚 V4 -> V3"""
        Printer.header(f"DataID {self.bk_data_id} 回滚 V4 -> V3")
        print(f"  开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 校验
        if not self.validate_for_rollback():
            Printer.section("校验失败")
            for error in self.errors:
                Printer.error(error)
            return False

        ds = self.datasource

        try:
            # Step 1: 更改 created_from，恢复 Consul 配置
            Printer.step(1, "更改数据源来源为 bkgse")
            Printer.info(f"原始值: {ds.created_from}")

            modify_data_id_source(
                bk_tenant_id=ds.bk_tenant_id,
                data_id_list=[self.bk_data_id],
                source_type=DataIdCreatedFromSystem.BKGSE.value,
            )
            Printer.success(
                f"已更改 created_from 为 {DataIdCreatedFromSystem.BKGSE.value}"
            )
            Printer.success("已刷新 Consul 配置和 GSE 路由")

            print()
            print(Printer.colorize("=" * 70, Printer.GREEN))
            print(
                Printer.colorize(
                    f" 回滚成功! DataID {self.bk_data_id} 已切换至 V3 链路",
                    Printer.GREEN + Printer.BOLD,
                )
            )
            print(Printer.colorize("=" * 70, Printer.GREEN))
            print()
            print(Printer.colorize("  注意事项:", Printer.YELLOW))
            print(
                Printer.colorize("  - BKBase 侧的链路配置仍然存在，不会自动删除", Printer.YELLOW)
            )
            print(
                Printer.colorize("  - AccessVMRecord 记录仍然存在，不会自动删除", Printer.YELLOW)
            )
            print(
                Printer.colorize(
                    "  - 数据将重新通过 Transfer -> InfluxDB 链路处理", Printer.YELLOW
                )
            )
            return True

        except Exception as e:
            Printer.error(f"回滚失败: {e}")
            return False

    def _apply_dataid_config_to_bkbase(
        self, ds, bk_biz_id: int, step_prefix: str = ""
    ) -> "models.DataIdConfig":
        """
        创建 DataIdConfig 并下发至 BKBase

        Args:
            ds: DataSource 实例
            bk_biz_id: 业务 ID
            step_prefix: 步骤前缀，用于日志输出 (如 "Step 3: " 或 "Step 1: ")

        Returns:
            DataIdConfig 实例
        """
        # 创建 DataIdConfig
        bkbase_data_name = datalink_utils.compose_bkdata_data_id_name(ds.data_name)
        Printer.kv("bkbase_data_name", bkbase_data_name)

        # 日志类型使用 bklog namespace，指标类型使用 bkmonitor namespace
        # FIXME: 疑点 - APM 数据类型(is_apm_type())的 namespace 应该使用 BKBASE_NAMESPACE_BK_APM ("bkapm")
        #  而非 BKBASE_NAMESPACE_BK_LOG ("bklog")。常量 BKBASE_NAMESPACE_BK_APM 已在
        #  metadata/models/data_link/constants.py 中定义但从未使用。
        #  此处怀疑应改为三路判断: apm -> bkapm, log -> bklog, metric -> bkmonitor
        dataid_namespace = (
            BKBASE_NAMESPACE_BK_LOG
            if self.is_log_type()
            else BKBASE_NAMESPACE_BK_MONITOR
        )
        Printer.kv("dataid_namespace", dataid_namespace)

        data_id_ins, created = models.DataIdConfig.objects.get_or_create(
            name=bkbase_data_name, namespace=dataid_namespace, bk_biz_id=bk_biz_id
        )
        if created:
            Printer.success("DataIdConfig 创建成功")
        else:
            Printer.info("DataIdConfig 已存在，复用")

        # 组装并下发配置至 BKBase
        config = self._compose_data_id_config(data_id_ins, ds)
        config["spec"]["predefined"]["dataId"] = int(
            config["spec"]["predefined"]["dataId"]
        )

        Printer.info(f"配置内容: {json.dumps(config, indent=2, ensure_ascii=False)}")

        api.bkdata.apply_data_link(bk_tenant_id=ds.bk_tenant_id, config=[config])
        Printer.success("DataId Config 下发成功")

        return data_id_ins

    def _setup_log_v4_options(self, ds, table_id: str, creator: str = "migrate_script"):
        """
        设置日志 V4 链路的 ResultTableOption

        Args:
            ds: DataSource 实例
            table_id: 结果表 ID
            creator: 创建者标识
        """
        # 构建 log_v4_data_link 配置
        Printer.info("构建 log_v4_data_link 配置")
        log_v4_config = self.build_log_v4_data_link_config(table_id)
        if not log_v4_config:
            raise ValueError("无法构建 log_v4_data_link 配置")

        # 设置 ResultTableOption: enable_log_v4_data_link
        Printer.info("设置 ResultTableOption enable_log_v4_data_link=True")
        option, opt_created = models.ResultTableOption.objects.update_or_create(
            table_id=table_id,
            name=ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK,
            bk_tenant_id=ds.bk_tenant_id,
            defaults={
                "value": "true",
                "value_type": ResultTableOption.TYPE_BOOL,
                "creator": creator,
            },
        )
        if opt_created:
            Printer.success("ResultTableOption enable_log_v4_data_link 创建成功")
        else:
            Printer.info("ResultTableOption enable_log_v4_data_link 已存在，已更新")

        # 设置 ResultTableOption: log_v4_data_link
        Printer.info("设置 ResultTableOption log_v4_data_link")
        option2, opt2_created = models.ResultTableOption.objects.update_or_create(
            table_id=table_id,
            name=ResultTableOption.OPTION_V4_LOG_DATA_LINK,
            bk_tenant_id=ds.bk_tenant_id,
            defaults={
                "value": json.dumps(log_v4_config),
                "value_type": ResultTableOption.TYPE_DICT,
                "creator": creator,
            },
        )
        if opt2_created:
            Printer.success("ResultTableOption log_v4_data_link 创建成功")
        else:
            Printer.info("ResultTableOption log_v4_data_link 已存在，已更新")

    def _create_v4_datalink(self, ds, table_id: str, bk_biz_id: int):
        """
        创建 V4 数据链路（APM、日志或指标类型）

        Args:
            ds: DataSource 实例
            table_id: 结果表 ID
            bk_biz_id: 业务 ID
        """
        Printer.kv("table_id", table_id)
        Printer.kv("bk_biz_id", bk_biz_id)

        if self.is_apm_type():
            # APM 类型: 使用 TransferAdaptor 方案，直接构建 BkFlatBatchConfig 下发
            Printer.kv("链路类型", "APM V4 链路 (TransferAdaptor)", color=Printer.CYAN)

            # 设置 APM V4 的 ResultTableOption（仅 enable flag，不设 clean_rules）
            self._setup_apm_v4_options(ds, table_id)

            # 构建并下发 TransferAdaptor 链路配置
            self._apply_apm_v4_datalink(ds, table_id, bk_biz_id)
            Printer.success("APM V4 数据链路创建成功 (TransferAdaptor)")
        elif self.is_pure_log_type():
            # 日志类型: 使用 apply_log_datalink
            Printer.kv("链路类型", "日志 V4 链路", color=Printer.CYAN)

            # 设置日志 V4 的 ResultTableOption
            self._setup_log_v4_options(ds, table_id)

            # 调用日志 V4 链路创建
            Printer.info("调用 apply_log_datalink() 创建日志 V4 数据链路")
            apply_log_datalink(bk_tenant_id=ds.bk_tenant_id, table_id=table_id)
            Printer.success("日志 V4 数据链路创建成功")
        else:
            # 指标类型: 使用 access_v2_bkdata_vm
            Printer.kv("链路类型", "指标 V4 链路", color=Printer.GREEN)
            access_v2_bkdata_vm(
                bk_tenant_id=ds.bk_tenant_id,
                bk_biz_id=bk_biz_id,
                table_id=table_id,
                data_id=self.bk_data_id,
            )
            Printer.success("指标 V4 数据链路创建成功")

    def _verify_migration_result(self, data_id_ins, table_id: str):
        """
        验证迁移结果

        Args:
            data_id_ins: DataIdConfig 实例
            table_id: 结果表 ID
        """
        # 刷新 data_id_ins 以获取最新状态
        data_id_ins.refresh_from_db()
        component_config = data_id_ins.component_config
        Printer.kv(
            "component_config",
            (
                json.dumps(component_config, indent=2, ensure_ascii=False)
                if component_config
                else "(空)"
            ),
        )

        if self.is_apm_type():
            # APM 类型 (TransferAdaptor 方案): 验证 enable flag 和 BkBaseResultTable
            try:
                option = models.ResultTableOption.objects.get(
                    table_id=table_id,
                    name=ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK,
                )
                Printer.success(f"ResultTableOption 已设置: {option.name}={option.value}")
            except models.ResultTableOption.DoesNotExist:
                Printer.warning("ResultTableOption enable_log_v4_data_link 未找到")

            # 验证 BkBaseResultTable 记录（TransferAdaptor 链路下发的产物）
            bkbase_rt = models.BkBaseResultTable.objects.filter(
                monitor_table_id=table_id,
            ).first()
            if bkbase_rt:
                Printer.success(f"BkBaseResultTable 已创建: data_link_name={bkbase_rt.data_link_name}, status={bkbase_rt.status}")
            else:
                Printer.warning("BkBaseResultTable 未创建，TransferAdaptor 链路可能未下发")
        elif self.is_pure_log_type():
            # 日志类型: 检查 ResultTableOption
            try:
                option = models.ResultTableOption.objects.get(
                    table_id=table_id,
                    name=ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK,
                )
                Printer.success(f"ResultTableOption 已设置: {option.name}={option.value}")
            except models.ResultTableOption.DoesNotExist:
                Printer.warning("ResultTableOption 未找到")
        else:
            # 指标类型: 检查 AccessVMRecord
            try:
                vm_record = models.AccessVMRecord.objects.get(result_table_id=table_id)
                Printer.success("AccessVMRecord 已创建")
                Printer.kv("vm_result_table_id", vm_record.vm_result_table_id, indent=6)
                Printer.kv("bk_base_data_id", vm_record.bk_base_data_id, indent=6)
            except models.AccessVMRecord.DoesNotExist:
                Printer.warning("AccessVMRecord 未创建，可能仍在处理中")

    def _compose_data_id_config(self, data_id_ins, datasource) -> dict:
        """组装生成 DataId 配置"""
        from metadata.models.space.constants import LOG_EVENT_ETL_CONFIGS

        bk_data_id = int(datasource.bk_data_id)
        topic = str(datasource.mq_config.topic)
        # 根据 etl_config 判断 event_type: 日志类型为 "log"，指标类型为 "metric"
        event_type = (
            "log" if datasource.etl_config in LOG_EVENT_ETL_CONFIGS else "metric"
        )

        tpl = """
        {
            "kind": "DataId",
            "metadata": {
                "name": "{{name}}",
                "namespace": "{{namespace}}",
                "labels": {"bk_biz_id": "{{bk_biz_id}}"}
            },
            "spec": {
                "alias": "{{name}}",
                "bizId": {{monitor_biz_id}},
                "description": "{{name}}",
                "maintainers": {{maintainers}},
                "predefined": {
                    "dataId": "{{bk_data_id}}",
                    "channel": {
                        "kind": "KafkaChannel",
                        "namespace": "{{namespace}}",
                        "name": "{{kafka_name}}"
                    },
                    "topic": "{{topic_name}}"
                },
                "eventType": "{{event_type}}"
            }
        }
        """

        maintainer = getattr(settings, "BK_DATA_PROJECT_MAINTAINER", "admin").split(",")

        return datalink_utils.compose_config(
            tpl=tpl,
            render_params={
                "name": data_id_ins.name,
                "namespace": data_id_ins.namespace,
                "bk_biz_id": data_id_ins.bk_biz_id,
                "monitor_biz_id": getattr(settings, "DEFAULT_BKDATA_BIZ_ID", 0),
                "maintainers": json.dumps(maintainer),
                "bk_data_id": bk_data_id,
                "kafka_name": self.kafka_name,
                "topic_name": topic,
                "event_type": event_type,
            },
            err_msg_prefix="compose data_id config",
        )


def batch_migrate(
    data_id_list: list, action: str, kafka_name: str, bk_biz_id: Optional[int] = None
):
    """批量迁移"""
    success_count = 0
    fail_count = 0

    Printer.header(f"批量 {action} - 共 {len(data_id_list)} 个 DataID")

    for i, data_id in enumerate(data_id_list, 1):
        print()
        print(
            Printer.colorize(f"[{i}/{len(data_id_list)}] 处理 DataID: {data_id}", Printer.BOLD)
        )
        print(Printer.colorize("-" * 50, Printer.CYAN))

        migrator = DataIDMigrator(data_id, kafka_name=kafka_name, bk_biz_id=bk_biz_id)

        try:
            if action == "migrate":
                result = migrator.migrate()
            elif action == "rollback":
                result = migrator.rollback()
            elif action == "diagnose":
                migrator.diagnose()
                result = True
            elif action == "retry":
                result = migrator.retry_migrate()
            else:
                result = False

            if result:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            Printer.error(f"处理 DataID {data_id} 时发生异常: {e}")
            fail_count += 1

    # 汇总
    print()
    print(Printer.colorize("=" * 70, Printer.CYAN))
    print(Printer.colorize(" 批量处理完成", Printer.CYAN + Printer.BOLD))
    print(Printer.colorize("=" * 70, Printer.CYAN))
    Printer.kv("总计", len(data_id_list))
    Printer.kv("成功", success_count, color=Printer.GREEN)
    Printer.kv("失败", fail_count, color=Printer.RED if fail_count > 0 else Printer.GREEN)


def main():
    parser = argparse.ArgumentParser(
        description="DataID V3 -> V4 链路迁移工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    # 诊断 DataID 状态
    python migrate_dataid_to_v4.py 1572869 --diagnose
    
    # 执行迁移
    python migrate_dataid_to_v4.py 1572869 --migrate
    
    # 重试迁移 (用于 BKBase 配置下发失败后的重试)
    python migrate_dataid_to_v4.py 1572869 --retry
    
    # 回滚到 V3
    python migrate_dataid_to_v4.py 1572869 --rollback
    
    # 批量迁移
    python migrate_dataid_to_v4.py 1001,1002,1003 --migrate
    
    # 指定业务 ID 和 Kafka 名称
    python migrate_dataid_to_v4.py 1572869 --migrate --bk-biz-id 2 --kafka-name kafka_outer_default

链路版本说明:
    V3: 数据流向 GSE -> Transfer -> InfluxDB/ES
    V4 (指标): 数据流向 GSE -> BKBase -> VictoriaMetrics
    V4 (日志): 数据流向 GSE -> BKBase -> ES/Doris

支持的 ETL 配置:
    指标类型: bk_standard_v2_time_series (使用 access_v2_bkdata_vm)
    日志类型: bk_flat_batch (使用 apply_log_datalink)
        """,
    )

    parser.add_argument("data_ids", type=str, help="要处理的 data_id，多个用逗号分隔")

    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--diagnose", action="store_true", help="诊断模式 - 只查看状态"
    )
    action_group.add_argument(
        "--migrate", action="store_true", help="执行迁移 V3 -> V4"
    )
    action_group.add_argument(
        "--retry",
        action="store_true",
        help="重试迁移 (用于 BKBase 配置下发失败后的重试)",
    )
    action_group.add_argument("--rollback", action="store_true", help="回滚 V4 -> V3")

    parser.add_argument(
        "--kafka-name",
        type=str,
        default="kafka_outer_default",
        help="BKBase 侧 Kafka 名称 (默认: kafka_outer_default)",
    )
    parser.add_argument(
        "--bk-biz-id",
        type=int,
        default=None,
        help="业务 ID (默认: 从结果表获取或使用 DEFAULT_BKDATA_BIZ_ID)",
    )

    args = parser.parse_args()

    # 解析 data_ids
    try:
        data_id_list = [int(x.strip()) for x in args.data_ids.split(",")]
    except ValueError:
        Printer.error("data_ids 格式错误，请使用逗号分隔的数字")
        sys.exit(1)

    # 确定操作类型
    if args.diagnose:
        action = "diagnose"
    elif args.migrate:
        action = "migrate"
    elif args.retry:
        action = "retry"
    elif args.rollback:
        action = "rollback"
    else:
        action = "diagnose"

    # 执行
    if len(data_id_list) == 1:
        migrator = DataIDMigrator(
            data_id_list[0], kafka_name=args.kafka_name, bk_biz_id=args.bk_biz_id
        )
        if action == "diagnose":
            migrator.diagnose()
        elif action == "migrate":
            migrator.migrate()
        elif action == "retry":
            migrator.retry_migrate()
        elif action == "rollback":
            migrator.rollback()
    else:
        batch_migrate(data_id_list, action, args.kafka_name, args.bk_biz_id)


if __name__ == "__main__":
    main()
