"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
import json
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from kubernetes import client as k8s_client
from kubernetes.client.rest import ApiException
from kubernetes.dynamic import client as dynamic_client
from kubernetes.dynamic.exceptions import NotFoundError, ResourceNotFoundError
from kubernetes.dynamic.resource import ResourceInstance

from core.drf_resource import api
from metadata import config, models
from metadata.models import (
    BcsFederalClusterInfo,
    DataBusConfig,
    EventGroup,
    ResultTableConfig,
    TimeSeriesGroup,
    VMStorageBindingConfig,
)
from metadata.models.bcs.cluster import BCSClusterInfo
from metadata.models.bcs.resource import PodMonitorInfo, ServiceMonitorInfo
from metadata.models.bkdata.result_table import BkBaseResultTable
from metadata.models.constants import DataIdCreatedFromSystem
from metadata.models.data_link.data_link import DataLink
from metadata.models.data_link.utils import compose_bkdata_data_id_name, compose_bkdata_table_id
from metadata.models.data_source import DataSource
from metadata.models.influxdb_cluster import InfluxDBClusterInfo, InfluxDBHostInfo
from metadata.models.result_table import (
    DataSourceResultTable,
    LogV4DataLinkOption,
    ResultTable,
    ResultTableField,
    ResultTableFieldOption,
    ResultTableOption,
)
from metadata.models.space.constants import ENABLE_V4_DATALINK_ETL_CONFIGS, EtlConfigs, SpaceStatus, SpaceTypes
from metadata.models.space.space import Space, SpaceDataSource
from metadata.models.storage import (
    ClusterInfo,
    DorisStorage,
    ESStorage,
    InfluxDBProxyStorage,
    InfluxDBStorage,
    StorageClusterRecord,
)
from metadata.models.vm.record import AccessVMRecord
from metadata.utils import consul_tools, hash_util
from bkmonitor.utils.tenant import set_local_tenant_id


def recode_final_result(fun):
    """记录最终结果的装饰器"""
    status_priority = {
        Status.UNKNOWN: 0,
        Status.SUCCESS: 1,
        Status.WARNING: 2,
        Status.ERROR: 3,
        Status.NOT_FOUND: 4,
    }

    def inner(self: "Command", *args, **kwargs):
        result = fun(self, *args, **kwargs)
        status = result.get("status", Status.UNKNOWN).upper()

        current_priority = status_priority.get(status, 0)
        self_priority = status_priority.get(self.status, 0)

        if current_priority > self_priority:
            self.status = status

        if result.get("errors"):
            self.errors.extend(result["errors"])

        if result.get("issues"):
            self.issues.extend(result["issues"])

        if result.get("warnings"):
            self.warnings.extend(result["warnings"])

        return result

    return inner


# 定义状态的枚举类型
class Status:
    UNKNOWN = "UNKNOWN"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    NOT_FOUND = "NOT_FOUND"


class Command(BaseCommand):
    """
    BCS集群关联状态检测命令

    按 A→I 阶段顺序检测集群在整条监控链路中的运行状态：

    阶段 A · 集群基础
        A1. BCSClusterInfo DB 记录 + status=RUNNING
        A2. BCS API 可达性
        A3. BCS API Token（仅 A2 失败时执行兜底定位）

    阶段 B · DataSource 元数据登记
        B1. DataSource 三件套（K8sMetric/CustomMetric/K8sEvent）

    阶段 C · 采集配置下发（metadata → K8s）
        C1-C4. DataID CRD 定义、实例、与 DB 一致性（spec.dataID / spec.labels）
        C5. ServiceMonitor / PodMonitor DB vs K8s 实际数量对比

    阶段 D · K8s 负载状态（CoreV1Api / AppsV1Api 只读）
        D1. bkmonitor-operator Deployment ready
        D2. bkm-daemonset-worker DaemonSet ready
        D3. bkm-statefulset-worker StatefulSet ready
        D4. bkm-event-worker Deployment ready
        D5. ChildConfig Secret 存在

    阶段 E · MQ / GSE 路由
        E1-E3. mq_cluster + gse_stream_to_id + GSE 路由（按 stream_to_id 匹配）

    阶段 F · 落表配置
        F1-F2. DataSourceResultTable / ResultTable / ResultTableOption
        F3-F4. VM 数据链路（DataLink + 4 类 Config 的 status=Ok）
        F5. InfluxDB / Elasticsearch 存储（按存储类型）

    阶段 G · 查询路由
        G1-G2. Space + SpaceDataSource
        G3. VM 空间路由 Redis key
        G4. Consul 数据源配置同步（可降级）

    阶段 H · 数据完整性
        H1. TimeSeriesGroup
        H2. EventGroup

    阶段 I · 旁路
        I1. 日志 V4 数据链路（按需启用）
        I2. 联邦集群拓扑（仅联邦场景）

    边界：脚本只检查"bk-monitor 元数据 + K8s 资源状态"。
         Pod 启动后能否跑通是 K8s 自身的问题，不在脚本范围。
         Kafka 实际写入、Transfer 消费、VM 落库等由外部检查覆盖。

    使用示例:
    python manage.py check_bcs_cluster_status --cluster-id BCS-K8S-00001
    python manage.py check_bcs_cluster_status --cluster-id BCS-K8S-00001 -V             # 同时展示详细信息
    python manage.py check_bcs_cluster_status --cluster-id BCS-K8S-00001 --format json  # 输出JSON格式
    python manage.py check_bcs_cluster_status --cluster-id BCS-K8S-00001 --timeout 60   # 设置超时时间
    """

    help = "检测BCS集群在监控关联链路中的运行状态"

    def __init__(self, *args, **kwargs):
        self.cluster_info = None
        self.bk_biz_id = None
        self.bk_tenant_id = None
        self.format_type = None
        self.verbose = False  # 详细输出模式标志

        self.status = Status.UNKNOWN
        self.errors = []
        self.issues = []
        self.warnings = []

        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        """添加命令行参数配置"""
        parser.add_argument("--cluster-id", type=str, required=True, help="BCS集群ID，例如: BCS-K8S-00001")
        parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式，支持text和json")
        parser.add_argument("--timeout", type=int, default=30, help="连接测试超时时间（秒），默认30秒")
        parser.add_argument(
            "-V",
            "--verbose",
            action="store_true",
            help="启用详细输出模式，展示更多检查细节信息（仅在text模式下生效）",
        )

    @property
    def data_sources(self) -> dict[str, DataSource]:
        """获取数据源"""
        if getattr(self, "_data_sources", None):
            return self._data_sources

        data_ids = [
            self.cluster_info.K8sMetricDataID,
            self.cluster_info.CustomMetricDataID,
            self.cluster_info.K8sEventDataID,
        ]

        data_ids = [id for id in data_ids if id != 0]
        data_sources = {d.bk_data_id: d for d in DataSource.objects.filter(bk_data_id__in=data_ids)}
        self._data_sources = data_sources
        return data_sources

    def handle(self, *args, **options):
        """主处理函数，执行集群状态检测流程"""
        cluster_id = options["cluster_id"]
        self.format_type = options["format"]
        timeout = options["timeout"]
        self.verbose = options.get("verbose", False)

        try:
            # 输出检测开始信息
            if self.format_type == "text":
                self.stdout.write(self.style.SUCCESS("=" * 60))
                self.stdout.write(self.style.SUCCESS("BCS集群关联状态检测"))
                self.stdout.write(self.style.SUCCESS("=" * 60))
                self.stdout.write(f"集群ID: {cluster_id}")
                self.stdout.write(f"检测时间: {timezone.now().isoformat()}")
                if self.verbose:
                    self.stdout.write("输出模式: 详细模式")
                self.stdout.write("")

            # 执行集群状态检测（检测过程中已经实时输出结果）
            check_result = self.check_cluster_status(cluster_id, timeout)

            # 输出汇总信息
            if self.format_type == "json":
                self.stdout.write(json.dumps(check_result, indent=2, ensure_ascii=False, default=str))
            else:
                self.output_summary_report(check_result)

        except Exception as e:
            raise CommandError(f"集群状态检测失败: {e}")

    def output_check_result(self, component: str, result: dict):
        """立即输出单个检查项的结果"""
        if not isinstance(result, dict):
            return

        status = result.get("status", Status.UNKNOWN)
        style = self.get_status_style(status)

        self.stdout.write(f"    result: {style(status)}")

        # 输出问题信息
        if result.get("issues"):
            for issue in result["issues"]:
                self.stdout.write(f"    ⚠ issue:{issue}")

        # 打印警告信息
        if result.get("warnings"):
            for warning in result["warnings"]:
                self.stdout.write(f"    ⚠ warning:{warning}")

        # 调用对应的格式化函数输出关键信息
        formatter = result.get("formatter")
        if formatter and callable(formatter):
            try:
                lines = formatter(result.get("details", {}))
                for line in lines:
                    self.stdout.write(line)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"输出{component}格式化信息失败: {e}"))

        # 详细模式：输出完整的details信息
        if self.verbose and result.get("details"):
            self.stdout.write("    详细信息:")
            self._output_verbose_details(result["details"], indent=6)

        self.stdout.write("")  # 空行分隔

    def _output_verbose_details(self, data, indent=4):
        """递归输出详细信息（仅在verbose模式下）"""
        prefix = " " * indent

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict | list):
                    self.stdout.write(f"{prefix}{key}:")
                    self._output_verbose_details(value, indent + 2)
                else:
                    # 过滤掉一些不需要展示的内部字段
                    if key not in ["cluster_model", "formatter"]:
                        self.stdout.write(f"{prefix}{key}: {value}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, dict | list):
                    self.stdout.write(f"{prefix}[{i}]:")
                    self._output_verbose_details(item, indent + 2)
                else:
                    self.stdout.write(f"{prefix}[{i}]: {item}")
        else:
            self.stdout.write(f"{prefix}{data}")

    def check_cluster_status(self, cluster_id: str, timeout: int = 30) -> dict:
        """执行完整的集群状态检测"""
        start_time = time.time()

        check_result = {
            "cluster_id": cluster_id,
            "check_time": timezone.now().isoformat(),
            "status": Status.UNKNOWN,
            "details": {},
            "errors": [],
            "warnings": [],
            "execution_time": 0,
        }

        try:
            # ============ 阶段 A：集群基础 ============
            # A1. BCSClusterInfo DB 记录
            self.stdout.write(f"\n[A1] 正在检查集群 {cluster_id} 的数据库记录...")
            db_check = self.check_database_record(cluster_id)
            check_result["details"]["database"] = db_check
            self.output_check_result("database", db_check)

            if not db_check["exists"]:
                check_result["status"] = Status.NOT_FOUND
                check_result["errors"].append("集群在数据库中不存在")
                return check_result

            cluster_info: BCSClusterInfo = db_check["cluster_model"]
            self.cluster_info: BCSClusterInfo = cluster_info
            self.bk_biz_id = cluster_info.bk_biz_id
            self.bk_tenant_id = cluster_info.bk_tenant_id

            # 集群状态非 RUNNING（DELETED / init_failed 等）→ 后续所有检查无意义，提前结束
            if cluster_info.status not in [
                BCSClusterInfo.CLUSTER_STATUS_RUNNING,
                BCSClusterInfo.CLUSTER_RAW_STATUS_RUNNING,
            ]:
                check_result["status"] = Status.WARNING
                check_result["warnings"].append(f"集群状态为 {cluster_info.status}，跳过后续所有检查")
                self.stdout.write(f"\n集群状态为 {cluster_info.status}，跳过 A2 及之后的全部检查项。")
                return check_result

            # management command 无 Django request 上下文，
            # 显式设置线程级租户 ID，避免下游 api.* 调用反复打 WARNING
            if self.bk_tenant_id:
                set_local_tenant_id(self.bk_tenant_id)

            # A2. BCS API 可达性
            self.stdout.write("[A2] 正在测试 BCS API 连接...")
            bcs_api_check = self.check_bcs_api_connection(cluster_info, timeout)
            check_result["details"]["bcs_api"] = bcs_api_check
            self.output_check_result("check_bcs_api_connection", bcs_api_check)

            # BCS API 可达性决定 C 和 D 阶段是否能执行
            # （CRD 检查、ServiceMonitor K8s 对比、K8s 负载状态都依赖 BCS API）
            bcs_api_accessible = bool(bcs_api_check.get("details", {}).get("api_accessible"))
            cluster_found_in_bcs = bool(bcs_api_check.get("details", {}).get("cluster_found"))
            skip_k8s_stages = not (bcs_api_accessible and cluster_found_in_bcs)

            # A3. BCS API Token（仅 A2 失败时作兜底定位；A2 通过则 Token 必然有效，省略检查）
            bcs_api_check_status = bcs_api_check.get("status", Status.UNKNOWN)
            if bcs_api_check_status not in (Status.SUCCESS,):
                self.stdout.write("[A3] A2 异常，进入 BCS API Token 兜底诊断...")
                api_token_check = self.check_bcs_api_token(cluster_info)
                check_result["details"]["api_token"] = api_token_check
                self.output_check_result("check_bcs_api_token", api_token_check)

            # ============ 阶段 B：DataSource 元数据登记 ============
            # B1. DataSource 三件套
            self.stdout.write("[B1] 正在验证数据源配置...")
            datasource_check = self.check_datasource_configuration(cluster_info)
            check_result["details"]["datasources"] = datasource_check
            self.output_check_result("check_datasource_configuration", datasource_check)

            # ============ 阶段 C：采集配置下发（metadata → K8s）============
            if skip_k8s_stages:
                self.stdout.write("[C1-C5] BCS API 不可达或集群在 BCS 中未找到，跳过 CRD / 监控资源 K8s 侧对比")
                self.warnings.append("BCS API 不可达，已跳过 C 阶段（DataID CRD / ServiceMonitor K8s 对比）")
            else:
                # C1-C4. DataID CRD 定义、实例、一致性
                self.stdout.write("[C1-C4] 正在检查 BCS 集群 DataID CRD 资源...")
                crd_resource_check = self.check_bcs_cluster_crd_resource(cluster_info)
                check_result["details"]["crd_resources"] = crd_resource_check
                self.output_check_result("check_bcs_cluster_crd_resource", crd_resource_check)

                # C5. ServiceMonitor / PodMonitor DB vs K8s 数量对比
                self.stdout.write("[C5] 正在检查监控资源状态（ServiceMonitor / PodMonitor）...")
                monitor_check = self.check_monitor_resources(cluster_info)
                check_result["details"]["monitor_resources"] = monitor_check
                self.output_check_result("check_monitor_resources", monitor_check)

            # ============ 阶段 D：K8s 负载状态 ============
            if skip_k8s_stages:
                self.stdout.write("[D1-D5] BCS API 不可达或集群在 BCS 中未找到，跳过 K8s 负载状态检查")
                self.warnings.append("BCS API 不可达，已跳过 D 阶段（K8s 负载状态）")
            else:
                # D1-D5. operator / worker / event-worker / ChildConfig Secret
                self.stdout.write("[D1-D5] 正在检查 K8s 内 bkmonitor-operator 负载状态...")
                k8s_workloads_check = self.check_k8s_workloads(cluster_info)
                check_result["details"]["k8s_workloads"] = k8s_workloads_check
                self.output_check_result("check_k8s_workloads", k8s_workloads_check)

            # ============ 阶段 E：MQ / GSE 路由 ============
            # E1-E3. mq_cluster + gse_stream_to_id + GSE 路由
            self.stdout.write("[E1-E3] 正在检查 MQ 集群与 GSE 路由...")
            mq_cluster_check = self.check_mq_cluster(cluster_info)
            check_result["details"]["mq_cluster"] = mq_cluster_check
            self.output_check_result("check_mq_cluster", mq_cluster_check)

            # ============ 阶段 F：落表配置 ============
            # F1-F2. DataSourceResultTable + ResultTable + Option
            self.stdout.write("[F1-F2] 正在检查关联的结果表...")
            related_models_check = self.check_related_result_table(cluster_info)
            check_result["details"]["related_result_table"] = related_models_check
            self.output_check_result("check_related_result_table", related_models_check)

            # F3-F4. VM 数据链路（含 status 校验）
            self.stdout.write("[F3-F4] 正在检查 VM 数据链路依赖...")
            vm_datalink_check = self.check_vm_datalink_dependencies(cluster_info)
            check_result["details"]["vm_datalink_dependencies"] = vm_datalink_check
            self.output_check_result("check_vm_datalink_dependencies", vm_datalink_check)

            # F5. InfluxDB / ES 存储
            # InfluxDB 仅在 ENABLE_INFLUXDB_STORAGE=True 时是有效存储（BCS 集群默认走 VM）
            if getattr(settings, "ENABLE_INFLUXDB_STORAGE", True):
                self.stdout.write("[F5a] 正在检查 InfluxDB 存储配置...")
                influxdb_storage_check = self.check_influxdb_storage_config(cluster_info)
                check_result["details"]["influxdb_storage"] = influxdb_storage_check
                self.output_check_result("check_influxdb_storage_config", influxdb_storage_check)
            else:
                self.stdout.write("[F5a] ENABLE_INFLUXDB_STORAGE=False，跳过 InfluxDB 存储检查")

            self.stdout.write("[F5b] 正在检查 Elasticsearch 存储配置（事件存储）...")
            elasticsearch_storage_check = self.check_elasticsearch_storage_config(cluster_info)
            check_result["details"]["elasticsearch_storage"] = elasticsearch_storage_check
            self.output_check_result("check_elasticsearch_storage_config", elasticsearch_storage_check)

            # ============ 阶段 G：查询路由 ============
            # G1-G2. Space + SpaceDataSource
            self.stdout.write("[G1-G2] 正在检查 datasource / space 空间配置...")
            space_type_check = self.check_space_type_and_datasource(cluster_info)
            check_result["details"]["space_type"] = space_type_check
            self.output_check_result("check_space_type_and_datasource", space_type_check)

            # G3. VM 空间路由 Redis
            self.stdout.write("[G3] 正在检查 VM 发布空间路由...")
            vm_publish_space_router_check = self.check_vm_publish_space_router(cluster_info)
            check_result["details"]["vm_publish_space_router"] = vm_publish_space_router_check
            self.output_check_result("check_vm_publish_space_router", vm_publish_space_router_check)

            # G4. Consul 同步（可降级）
            self.stdout.write("[G4] 正在检查 datasource 的 Consul 配置...")
            consul_config = self.check_datasource_consul_config(cluster_info)
            check_result["details"]["datasource_consul_config"] = consul_config
            self.output_check_result("check_datasource_consul_config", consul_config)

            # ============ 阶段 H：数据完整性 ============
            # H1-H2. TimeSeriesGroup + EventGroup
            self.stdout.write("[H1-H2] 正在检查 TimeSeriesGroup 和 EventGroup 数据完整性...")
            custom_groups_check = self.check_custom_groups_integrity(cluster_info)
            check_result["details"]["custom_groups"] = custom_groups_check
            self.output_check_result("check_custom_groups_integrity", custom_groups_check)

            # ============ 阶段 I：旁路 ============
            # I1. 日志 V4 数据链路（可降级 WARNING）
            self.stdout.write("[I1] 正在检查日志 V4 数据链路...")
            log_v4_datalink_check = self.check_log_datalink(cluster_info)
            check_result["details"]["log_v4_datalink"] = log_v4_datalink_check
            self.output_check_result("check_log_datalink", log_v4_datalink_check)

            # I2. 联邦集群（仅联邦场景）
            if self.is_federation_cluster(cluster_info):
                self.stdout.write("[I2] 正在检查联邦集群关系...")
                federation_check = self.check_federation_cluster(cluster_info)
                check_result["details"]["federation"] = federation_check
                self.output_check_result("check_federation_cluster", federation_check)

            # 确定整体状态
            check_result["status"] = self.status
            check_result["errors"] = self.errors
            check_result["issues"] = self.issues
            check_result["warnings"] = self.warnings

        except Exception as e:
            check_result["status"] = Status.ERROR
            check_result["errors"].append(f"检测过程中发生异常: {str(e)}")

        finally:
            check_result["execution_time"] = round(time.time() - start_time, 2)

        return check_result

    @recode_final_result
    def check_database_record(self, cluster_id: str) -> dict:
        """检查集群在数据库中的记录状态"""
        result = {"exists": False, "cluster_info": None, "status": Status.UNKNOWN, "details": {}, "issues": []}

        def format_output(details: dict) -> list[str]:
            """格式化数据库检查输出"""
            lines = []
            if details:
                lines.append(f"    业务ID: {details.get('bk_biz_id')}")
                lines.append(f"    集群状态: {details.get('status')}")
            return lines

        result["formatter"] = format_output

        try:
            cluster_info = BCSClusterInfo.objects.get(cluster_id=cluster_id)
            result["exists"] = True
            result["cluster_model"] = cluster_info
            result["status"] = Status.SUCCESS

            # 收集集群基本信息
            result["details"] = {
                "bk_biz_id": cluster_info.bk_biz_id,
                "project_id": cluster_info.project_id,
                "status": cluster_info.status,
                "bk_tenant_id": cluster_info.bk_tenant_id,
                "domain_name": cluster_info.domain_name,
                "port": cluster_info.port,
                "data_ids": {
                    "K8sMetricDataID": cluster_info.K8sMetricDataID,
                    "CustomMetricDataID": cluster_info.CustomMetricDataID,
                    "K8sEventDataID": cluster_info.K8sEventDataID,
                },
            }

            # 检查集群状态
            if cluster_info.status not in [
                BCSClusterInfo.CLUSTER_STATUS_RUNNING,
                BCSClusterInfo.CLUSTER_RAW_STATUS_RUNNING,
            ]:
                message = f"[BCSClusterInfo] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}集群状态异常: {cluster_info.status}")
                # 非 RUNNING 集群不能算 SUCCESS
                result["status"] = Status.WARNING

            # 检查数据源ID配置
            missing_data_ids = []
            for data_type, data_id in result["details"]["data_ids"].items():
                if data_id == 0:
                    missing_data_ids.append(data_type)

            if missing_data_ids:
                message = f"[BCSClusterInfo] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}缺少数据源ID配置: {', '.join(missing_data_ids)}")

        except BCSClusterInfo.DoesNotExist:
            result["status"] = Status.NOT_FOUND
            message = f"[BCSClusterInfo] [cluster_id={cluster_id}] "
            result["issues"].append(f"{message}集群记录在数据库中不存在")
        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[BCSClusterInfo] [cluster_id={cluster_id}] "
            result["issues"].append(f"{message}数据库查询异常: {str(e)}")

        return result

    @recode_final_result
    def check_bcs_api_connection(self, cluster_info: BCSClusterInfo, timeout: int) -> dict:
        """检查BCS API连接状态"""
        result = {"status": Status.UNKNOWN, "details": {}, "issues": []}

        def format_output(details: dict) -> list[str]:
            """格式化BCS API连接检查输出"""
            lines = []
            if details:
                lines.append(f"    API可访问: {details.get('api_accessible', False)}")
                lines.append(f"    集群发现: {details.get('cluster_found', False)}")
                if details.get("cluster_status"):
                    lines.append(f"    集群状态: {details['cluster_status']}")
            return lines

        result["formatter"] = format_output

        try:
            # 尝试通过BCS API获取集群信息
            bcs_clusters = api.kubernetes.fetch_k8s_cluster_list(bk_tenant_id=cluster_info.bk_tenant_id)

            # 检查目标集群是否在返回列表中
            target_cluster = None
            for cluster in bcs_clusters:
                if cluster.get("cluster_id") == cluster_info.cluster_id:
                    target_cluster = cluster
                    break

            if target_cluster:
                result["status"] = Status.SUCCESS
                result["details"] = {
                    "api_accessible": True,  # API可访问
                    "cluster_found": True,
                    "cluster_status": target_cluster.get("status"),
                    "bk_biz_id": target_cluster.get("bk_biz_id"),
                }

                # 检查状态一致性
                if target_cluster.get("status") != cluster_info.status:
                    message = f"[BCSClusterInfo] [cluster_id={cluster_info.cluster_id}] "
                    result["issues"].append(
                        f"{message}集群状态不一致 - 数据库: {cluster_info.status}, BCS API: {target_cluster.get('status')}"
                    )
            else:
                result["status"] = Status.WARNING
                result["details"] = {"api_accessible": True, "cluster_found": False}
                message = f"[BCSClusterInfo] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}集群在BCS API中未找到，可能已被删除")

        except Exception as e:
            result["status"] = Status.ERROR
            result["details"] = {"api_accessible": False, "error": str(e)}
            message = f"[BCSClusterInfo] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}BCS API连接失败: {str(e)}")

        return result

    @recode_final_result
    def check_datasource_configuration(self, cluster_info: BCSClusterInfo) -> dict:
        """检查数据源配置状态"""
        result = {"status": Status.UNKNOWN, "details": {}, "issues": []}

        def format_output(details: dict) -> list[str]:
            """格式化数据源配置检查输出"""
            lines = []
            if details:
                data_ids = details.get("configured_data_ids", [])
                lines.append(f"    已配置数据源: {len(data_ids)}个")
                datasource_status = details.get("datasource_status", {})
                enabled_count = sum(1 for ds in datasource_status.values() if ds.get("is_enable", False))
                lines.append(f"    启用状态: {enabled_count}/{len(datasource_status)}")
            return lines

        result["formatter"] = format_output

        try:
            datasource_status = {}
            for data_id, datasource in self.data_sources.items():
                try:
                    # 检查数据源记录
                    datasource_status[data_id] = {
                        "exists": True,
                        "data_name": datasource.data_name,
                        "is_enable": datasource.is_enable,
                        "type_label": datasource.type_label,
                    }

                    # 检查数据源是否启用
                    if not datasource.is_enable:
                        message = f"[DataSource] [bk_data_id={data_id}] "
                        result["issues"].append(f"{message}未启用")

                except DataSource.DoesNotExist:
                    datasource_status[data_id] = {"exists": False}
                    message = f"[DataSource] [bk_data_id={data_id}] "
                    result["issues"].append(f"{message}不存在")

            result["details"] = {
                "configured_data_ids": list(self.data_sources.keys()),
                "datasource_status": datasource_status,
            }

            # 确定整体状态
            if not result["issues"]:
                result["status"] = Status.SUCCESS
            elif any("不存在" in issue for issue in result["issues"]):
                result["status"] = Status.ERROR
            else:
                result["status"] = Status.WARNING

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[DataSource] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}数据源配置检查异常: {str(e)}")

        return result

    @recode_final_result
    def check_monitor_resources(self, cluster_info: BCSClusterInfo) -> dict:
        """检查监控资源状态

        DB 侧：ServiceMonitorInfo / PodMonitorInfo（由 refresh_resource 周期任务从 K8s 同步）
        K8s 侧：实际部署的 ServiceMonitor / PodMonitor 自定义资源
        两者数量应一致；不一致说明同步任务异常。
        """
        result = {"status": Status.UNKNOWN, "details": {}, "issues": [], "warnings": []}

        def format_output(details: dict) -> list[str]:
            lines = []
            sm = details.get("service_monitors", {})
            pm = details.get("pod_monitors", {})
            lines.append(f"    ServiceMonitor: DB={sm.get('db_count', 0)} K8s={sm.get('k8s_count', '-')}")
            lines.append(f"    PodMonitor    : DB={pm.get('db_count', 0)} K8s={pm.get('k8s_count', '-')}")
            return lines

        result["formatter"] = format_output

        try:
            db_sm_count = ServiceMonitorInfo.objects.filter(cluster_id=cluster_info.cluster_id).count()
            db_pm_count = PodMonitorInfo.objects.filter(cluster_id=cluster_info.cluster_id).count()

            # 从 K8s 实际拉取数量，与 DB 对比（C5）
            k8s_sm_count = self._count_k8s_monitor_resources(
                cluster_info, plural="servicemonitors", issues=result["issues"], warnings=result["warnings"]
            )
            k8s_pm_count = self._count_k8s_monitor_resources(
                cluster_info, plural="podmonitors", issues=result["issues"], warnings=result["warnings"]
            )

            result["details"]["service_monitors"] = {"db_count": db_sm_count, "k8s_count": k8s_sm_count}
            result["details"]["pod_monitors"] = {"db_count": db_pm_count, "k8s_count": k8s_pm_count}

            # ServiceMonitor=0 才表示采集资源完全缺失；PodMonitor=0 合法
            if db_sm_count == 0 and (k8s_sm_count == 0 or k8s_sm_count is None):
                result["issues"].append(
                    f"[ServiceMonitor] [cluster_id={cluster_info.cluster_id}] 集群无 ServiceMonitor 资源"
                )

            # DB 与 K8s 数量不一致 → 同步任务（refresh_bcs_monitor_info）异常
            if k8s_sm_count is not None and k8s_sm_count != db_sm_count:
                result["issues"].append(
                    f"[ServiceMonitor] [cluster_id={cluster_info.cluster_id}] "
                    f"DB({db_sm_count}) 与 K8s({k8s_sm_count}) 数量不一致，"
                    "refresh_bcs_monitor_info 同步任务可能异常"
                )
            if k8s_pm_count is not None and k8s_pm_count != db_pm_count:
                result["issues"].append(
                    f"[PodMonitor] [cluster_id={cluster_info.cluster_id}] "
                    f"DB({db_pm_count}) 与 K8s({k8s_pm_count}) 数量不一致"
                )

            result["status"] = Status.ERROR if result["issues"] else Status.SUCCESS

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[ServiceMonitor/PodMonitor] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}监控资源检查异常: {str(e)}")

        return result

    def _count_k8s_monitor_resources(self, cluster_info: BCSClusterInfo, plural: str, issues: list, warnings: list):
        """通过 dynamic client 拉取 K8s 集群里 ServiceMonitor / PodMonitor 实际数量

        - CRD 未定义 → warning（PodMonitor 没装是常见情况）
        - 其他异常 → issue
        失败时返回 None，不参与后续 DB 对比
        """
        try:
            d_client = dynamic_client.DynamicClient(cluster_info.api_client)
            resource_api = d_client.resources.get(
                api_version="monitoring.coreos.com/v1",
                kind="ServiceMonitor" if plural == "servicemonitors" else "PodMonitor",
            )
            resp = resource_api.get()
            return len(resp.items or [])
        except ResourceNotFoundError:
            warnings.append(f"[{plural}] [cluster_id={cluster_info.cluster_id}] CRD 未定义于集群，跳过 K8s 数量对比")
            return None
        except Exception as e:
            issues.append(f"[{plural}] [cluster_id={cluster_info.cluster_id}] 拉取 K8s 资源异常: {str(e)}")
            return None

    @recode_final_result
    def check_datasource_consul_config(self, cluster_info: BCSClusterInfo) -> dict:
        """检查datasource Consul配置

        Consul 存放数据源配置供 transfer 等消费端读取。但实际上：
        - 配置完全缺失 → 真同步失败 → issue
        - 配置存在但内容不一致 → 多数为新加字段（bk_tenant_id/bk_biz_id/display_name）
          或 list 顺序差异，transfer 启动会重读且对元数据字段缺失有 fallback，
          不影响数据流稳定性 → warning
        """
        result = {"status": Status.UNKNOWN, "details": {}, "issues": [], "warnings": []}

        def format_output(details: dict) -> list[str]:
            """格式化Consul配置检查输出"""
            lines = []
            if details:
                consul_status = details.get("consul_status", {})
                consistent_count = sum(1 for status in consul_status.values() if status.get("is_consistent"))
                total_count = len(consul_status)
                lines.append(f"    配置一致性: {consistent_count}/{total_count}个数据源配置一致")

                if details.get("skipped_count", 0) > 0:
                    lines.append(f"    跳过检查: {details['skipped_count']}个数据源(不支持Consul同步)")
            return lines

        result["formatter"] = format_output

        try:
            hash_consul = consul_tools.HashConsul()
            consul_status = {}
            skipped_count = 0

            for data_id, datasource in self.data_sources.items():
                try:
                    # 检查数据源是否支持Consul配置刷新
                    if not datasource.can_refresh_consul_and_gse():
                        skipped_count += 1
                        consul_status[data_id] = {
                            "path": datasource.consul_config_path,
                            "skipped": True,
                            "reason": "数据源不支持Consul配置刷新",
                        }
                        continue

                    # 获取Consul中的配置
                    # consul Python client 的 Value 字段可能是 bytes / str / dict
                    num, consul_config = hash_consul.get(datasource.consul_config_path)
                    consul_config = consul_config.get("Value", {}) if consul_config else {}
                    if isinstance(consul_config, bytes):
                        consul_config = consul_config.decode("utf-8")
                    if isinstance(consul_config, str):
                        try:
                            consul_config = json.loads(consul_config)
                        except json.JSONDecodeError:
                            consul_status[data_id] = {"error": "Consul配置JSON解析失败"}
                            message = f"[Consul] [DataSource][bk_data_id={data_id}] "
                            result["issues"].append(f"{message}Consul配置JSON解析失败")
                            continue

                    if not consul_config:
                        consul_status[data_id] = {
                            "path": datasource.consul_config_path,
                            "exists": False,
                            "is_consistent": False,
                        }
                        message = f"[Consul] [DataSource][bk_data_id={data_id}]"
                        result["issues"].append(
                            f"{message} consul_path={datasource.consul_config_path}Consul配置不存在"
                        )
                        continue

                    # 生成数据源的标准配置
                    datasource_config = datasource.to_json(is_consul_config=True)

                    # 比较配置是否一致
                    is_consistent = consul_config == datasource_config
                    consul_status[data_id] = {
                        "path": datasource.consul_config_path,
                        "exists": True,
                        "is_consistent": is_consistent,
                    }

                    if not is_consistent:
                        # 精细化对比：只关注影响 transfer 消费的关键字段（连接信息+topic+RT）
                        # 元数据字段差异（bk_tenant_id/bk_biz_id/display_name 等）不影响数据流，忽略
                        critical_diffs = self._find_critical_consul_diff(consul_config, datasource_config)
                        all_diffs = self._find_config_diff(consul_config, datasource_config)
                        consul_status[data_id]["diff_keys"] = all_diffs
                        consul_status[data_id]["critical_diff_keys"] = critical_diffs
                        message = f"[Consul] [DataSource][bk_data_id={data_id}]"

                        if critical_diffs:
                            # 关键字段不一致 → 真影响 transfer，作为 issue
                            result["issues"].append(
                                f"{message} consul_path={datasource.consul_config_path} "
                                f"Consul 关键字段与 DB 不一致: {','.join(critical_diffs)}"
                            )
                        else:
                            # 仅非关键字段差异 → warning
                            result["warnings"].append(
                                f"{message} consul_path={datasource.consul_config_path} "
                                f"Consul 配置存在非关键字段差异（{len(all_diffs)} 项），不影响 transfer 消费"
                            )

                except Exception as e:
                    consul_status[data_id] = {"error": str(e)}
                    message = f"[Consul][DataSource] [bk_data_id={data_id}] "
                    result["issues"].append(f"{message}配置检查异常: {str(e)}")

            result["details"] = {
                "consul_status": consul_status,
                "skipped_count": skipped_count,
                "total_count": len(self.data_sources),
            }
            result["status"] = Status.SUCCESS if not result["issues"] else Status.WARNING

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[Consul] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}Consul配置检查异常: {str(e)}")

        return result

    # transfer 实际消费 Consul 配置时依赖的关键字段（dotted path）
    # 其他元数据字段（bk_tenant_id/bk_biz_id/display_name/result_table_list 中的非连接字段等）差异不影响数据流
    _CONSUL_CRITICAL_FIELDS = (
        "mq_config.cluster_config.cluster_id",
        "mq_config.cluster_config.domain_name",
        "mq_config.cluster_config.port",
        "mq_config.storage_config.topic",
        "mq_config.storage_config.partition",
        "etl_config",
        "data_id",
    )

    @staticmethod
    def _get_nested(d: dict, path: str):
        """按 dotted path 取嵌套值；任意一段缺失返回 sentinel 表示路径不存在"""
        sentinel = object()
        cur = d
        for seg in path.split("."):
            if not isinstance(cur, dict) or seg not in cur:
                return sentinel
            cur = cur[seg]
        return cur

    def _find_critical_consul_diff(self, consul_config: dict, datasource_config: dict) -> list[str]:
        """只对比 transfer 真正依赖的关键字段（连接信息 / topic / 分区 / etl_config / data_id）"""
        sentinel = object()
        diffs = []
        for path in self._CONSUL_CRITICAL_FIELDS:
            cv = self._get_nested(consul_config, path)
            dv = self._get_nested(datasource_config, path)
            # 双方都不存在 → 跳过；存在性或值不同 → diff
            if cv is sentinel and dv is sentinel:
                continue
            if cv != dv:
                diffs.append(path)
        return diffs

    def _find_config_diff(self, consul_config: dict, datasource_config: dict, prefix: str = "") -> list[str]:
        """查找两个配置字典的差异字段"""
        diff_keys = []
        all_keys = set(consul_config.keys()) | set(datasource_config.keys())

        for key in all_keys:
            current_path = f"{prefix}.{key}" if prefix else key

            if key not in consul_config:
                diff_keys.append(f"consul 配置缺失{current_path} 字段")
            elif key not in datasource_config:
                diff_keys.append(f"consul 配置多余{current_path} 字段")
            else:
                val1, val2 = consul_config[key], datasource_config[key]
                if isinstance(val1, dict) and isinstance(val2, dict):
                    # 递归比较嵌套字典
                    diff_keys.extend(self._find_config_diff(val1, val2, current_path))
                elif val1 != val2:
                    diff_keys.append(current_path)

        return diff_keys

    @recode_final_result
    def check_federation_cluster(self, cluster_info: BCSClusterInfo) -> dict:
        """检查联邦集群状态

        当前集群可能在联邦拓扑中扮演多种角色（fed_cluster_id / host_cluster_id / sub_cluster_id）。
        本检查：
        - 输出该集群所在的联邦拓扑（含嵌套），让运维清楚集群位置
        - 仅当集群是 fed_cluster_id（代理集群）时校验配置完整性

        校验规则：
        - fed_namespaces 缺失：operator 不知道采哪些 ns，真阻断 → issue
        - fed_builtin_metric/event_table_id 缺失：
            - V4 联邦汇聚链路（BCS_FEDERAL_PROXY_TIME_SERIES）启用 → issue（阻断汇聚）
            - V2 链路下子集群指标直接落子集群 RT，不依赖该字段 → warning
        """
        result = {"status": Status.UNKNOWN, "details": {}, "issues": [], "warnings": []}

        def format_output(details: dict) -> list[str]:
            """格式化联邦集群检查输出"""
            lines = []
            if not details:
                return lines

            role = details.get("current_role", "unknown")
            lines.append(f"    当前集群角色: {role}")

            if details.get("v4_fed_link_enabled") is not None:
                lines.append(f"    V4 联邦汇聚链路: {'启用' if details['v4_fed_link_enabled'] else '未启用'}")

            # 直接拼接拓扑可视化
            topo_lines = details.get("topology_lines") or []
            lines.extend(topo_lines)
            return lines

        result["formatter"] = format_output

        try:
            # 1. 渲染该集群所在的完整联邦拓扑（含嵌套），无论扮演什么角色
            topology_lines = self._render_federation_topology(cluster_info.cluster_id)

            # 2. 计算当前集群在拓扑中的角色（可能多个）
            roles = []
            if BcsFederalClusterInfo.objects.filter(fed_cluster_id=cluster_info.cluster_id, is_deleted=False).exists():
                roles.append("代理集群(fed)")
            if BcsFederalClusterInfo.objects.filter(host_cluster_id=cluster_info.cluster_id, is_deleted=False).exists():
                roles.append("HOST 集群")
            if BcsFederalClusterInfo.objects.filter(sub_cluster_id=cluster_info.cluster_id, is_deleted=False).exists():
                roles.append("子集群(sub)")
            current_role = " + ".join(roles) if roles else "无联邦关系"

            # 3. 仅当作为代理集群时校验配置完整性
            fed_clusters = BcsFederalClusterInfo.objects.filter(
                fed_cluster_id=cluster_info.cluster_id, is_deleted=False
            )

            federation_details = []
            v4_fed_link_enabled = None

            if fed_clusters.exists():
                for fed_cluster in fed_clusters:
                    federation_details.append(
                        {
                            "host_cluster_id": fed_cluster.host_cluster_id,
                            "sub_cluster_id": fed_cluster.sub_cluster_id,
                            "fed_namespaces": fed_cluster.fed_namespaces,
                            "builtin_metric_table_id": fed_cluster.fed_builtin_metric_table_id,
                            "builtin_event_table_id": fed_cluster.fed_builtin_event_table_id,
                        }
                    )

                # 判定该代理集群是否启用 V4 联邦汇聚链路
                v4_fed_link_enabled = DataLink.objects.filter(
                    bk_data_id__in=[
                        did
                        for did in [
                            cluster_info.K8sMetricDataID,
                            cluster_info.CustomMetricDataID,
                            cluster_info.K8sEventDataID,
                        ]
                        if did
                    ],
                    data_link_strategy=DataLink.BCS_FEDERAL_PROXY_TIME_SERIES,
                ).exists()

                # 校验联邦记录字段完整性
                for fed in federation_details:
                    if not fed["fed_namespaces"]:
                        message = f"[BcsFederalClusterInfo] [sub_cluster_id={fed['sub_cluster_id']}] "
                        result["issues"].append(f"{message}没有配置命名空间")

                    if not fed["builtin_metric_table_id"]:
                        message = f"[BcsFederalClusterInfo] [sub_cluster_id={fed['sub_cluster_id']}] "
                        if v4_fed_link_enabled:
                            result["issues"].append(f"{message}缺少内置指标表ID (V4 联邦汇聚链路依赖)")
                        else:
                            result["warnings"].append(f"{message}缺少内置指标表ID (V2 链路下不影响数据流)")

            result["details"] = {
                "current_role": current_role,
                "topology_lines": topology_lines,
                "federation_count": len(federation_details),
                "federations": federation_details,
                "v4_fed_link_enabled": v4_fed_link_enabled,
            }

            if result["issues"]:
                result["status"] = Status.ERROR
            elif result["warnings"]:
                result["status"] = Status.WARNING
            else:
                result["status"] = Status.SUCCESS

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[BcsFederalClusterInfo] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}联邦集群检查异常: {str(e)}")

        return result

    @recode_final_result
    def check_bcs_cluster_crd_resource(self, cluster_info: BCSClusterInfo) -> dict:
        """检查BCS集群CRD资源状态

        检查项目包括：
        1. DataIDResource CRD定义是否存在
        2. 集群的DataIDResource资源配置状态
        3. 资源配置与数据库配置的一致性
        4. 资源标签和元数据完整性

        联邦代理集群特殊处理：metadata 仅向其下发 customMetricDataID 带 -fed 后缀的 CRD。
        -fed CRD 缺失的影响判定与 I2 阶段一致，基于 V4 联邦汇聚链路是否启用：
        - V4 启用：BkBase 汇聚需 -fed CRD 路由标识，缺失影响汇聚 → issue
        - V4 未启用（仅嵌套联邦元数据登记）：子集群普通 CRD 已覆盖采集，不影响数据流 → warning
        """
        result = {"status": Status.UNKNOWN, "details": {}, "issues": [], "warnings": []}

        def format_output(details: dict) -> list[str]:
            """格式化CRD资源检查输出"""
            lines = []
            if details:
                crd_status = details.get("crd_status", {})
                if crd_status.get("exists"):
                    lines.append(f"    CRD定义: {crd_status.get('kind')}/{crd_status.get('version')}")

                resources = details.get("dataid_resources", [])
                if resources:
                    consistent_count = sum(1 for r in resources if r.get("is_consistent"))
                    lines.append(f"    DataID资源: {len(resources)}个, 配置一致: {consistent_count}/{len(resources)}")

                if details.get("v4_fed_link_enabled") is not None and details.get("is_fed_cluster"):
                    lines.append(f"    V4 联邦汇聚链路: {'启用' if details['v4_fed_link_enabled'] else '未启用'}")
            return lines

        result["formatter"] = format_output

        try:
            # 获取动态客户端
            try:
                d_client = dynamic_client.DynamicClient(cluster_info.api_client)
            except Exception as e:
                result["status"] = Status.ERROR
                message = f"[DynamicClient] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}无法连接到BCS集群: {str(e)}")
                return result

            # 1. 检查DataIDResource CRD定义是否存在
            try:
                resource_api = d_client.resources.get(
                    api_version=f"{config.BCS_RESOURCE_GROUP_NAME}/{config.BCS_RESOURCE_VERSION}",
                    kind=config.BCS_RESOURCE_DATA_ID_RESOURCE_KIND,
                )
                result["details"]["crd_status"] = {
                    "exists": True,
                    "kind": config.BCS_RESOURCE_DATA_ID_RESOURCE_KIND,
                    "version": config.BCS_RESOURCE_VERSION,
                    "group": config.BCS_RESOURCE_GROUP_NAME,
                }
            except ResourceNotFoundError:
                result["status"] = Status.ERROR
                result["details"]["crd_status"] = {"exists": False}
                message = f"[DataIDResource CRD] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}CRD未定义，集群不支持监控资源注入")
                return result
            except Exception as e:
                result["status"] = Status.ERROR
                message = f"[DataIDResource CRD] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}检查CRD定义失败: {str(e)}")
                return result

            # 2. 检查集群的DataIDResource资源配置状态
            dataid_resources = []
            is_fed_cluster = BcsFederalClusterInfo.objects.filter(
                fed_cluster_id=cluster_info.cluster_id, is_deleted=False
            ).exists()

            # 判定该代理集群是否启用 V4 联邦汇聚链路（决定 -fed CRD 缺失的严重程度）
            # 仅嵌套联邦元数据登记 + 未启用 V4 汇聚 → -fed CRD 缺失不影响数据流（warning）
            # V4 汇聚链路实际在跑 + -fed CRD 缺失 → 影响汇聚（issue）
            v4_fed_link_enabled = False
            if is_fed_cluster:
                v4_fed_link_enabled = DataLink.objects.filter(
                    bk_data_id__in=[
                        did
                        for did in [
                            cluster_info.K8sMetricDataID,
                            cluster_info.CustomMetricDataID,
                            cluster_info.K8sEventDataID,
                        ]
                        if did
                    ],
                    data_link_strategy=DataLink.BCS_FEDERAL_PROXY_TIME_SERIES,
                ).exists()
            result["details"]["v4_fed_link_enabled"] = v4_fed_link_enabled

            for usage, register_info in cluster_info.DATASOURCE_REGISTER_INFO.items():
                # 联邦集群跳过非自定义指标
                if is_fed_cluster and usage != cluster_info.DATA_TYPE_CUSTOM_METRIC:
                    continue

                data_id = getattr(cluster_info, register_info["datasource_name"])
                if data_id == 0:
                    continue

                resource_name = cluster_info.compose_dataid_resource_name(
                    register_info["datasource_name"].lower(), is_fed_cluster=is_fed_cluster
                )

                try:
                    # 获取集群中的资源实际配置

                    cluster_resource: ResourceInstance = d_client.get(resource=resource_api, name=resource_name)
                    cluster_resource: dict = cluster_resource.to_dict()
                    # 生成期望的配置
                    expected_config = cluster_info.make_config(
                        register_info, usage=usage, is_fed_cluster=is_fed_cluster
                    )

                    # 比较配置是否一致
                    is_consistent = self._compare_dataid_resource(cluster_resource, expected_config)

                    resource_detail = {
                        "name": resource_name,
                        "usage": usage,
                        "data_id": data_id,
                        "exists": True,
                        "is_consistent": is_consistent,
                        "spec": {
                            "dataID": cluster_resource.get("spec", {}).get("dataID"),
                            "labels": cluster_resource.get("spec", {}).get("labels", {}),
                        },
                        "metadata": {
                            "creation_timestamp": str(
                                cluster_resource.get("metadata", {}).get("creationTimestamp", "")
                            ),
                            "labels": cluster_resource.get("metadata", {}).get("labels", {}),
                        },
                        "current_resource_config": cluster_resource,
                        "expected_resource_config": expected_config,
                    }

                    if not is_consistent:
                        diff_info = self._get_dataid_resource_diff(cluster_resource, expected_config)
                        resource_detail["diff"] = diff_info
                        message = (
                            f"[DataIDResource] [cluster_id={cluster_info.cluster_id},resource_name={resource_name}] "
                        )
                        result["issues"].append(f"{message}配置不一致：{', '.join(diff_info)}")
                    dataid_resources.append(resource_detail)

                except NotFoundError:
                    # 资源不存在
                    dataid_resources.append(
                        {
                            "name": resource_name,
                            "usage": usage,
                            "data_id": data_id,
                            "exists": False,
                            "is_consistent": False,
                        }
                    )
                    message = (
                        f"[DataIDResource] [cluster_id={cluster_info.cluster_id},"
                        f"resource_name={resource_name},data_id={data_id}] "
                    )
                    if is_fed_cluster:
                        # 联邦代理集群的 -fed CRD 缺失分两种场景：
                        # - V4 联邦汇聚链路启用：BkBase 汇聚需 -fed CRD 路由标识，缺失影响汇聚 → issue
                        # - 未启用 V4 汇聚（仅 DB 登记嵌套关系）：子集群普通 CRD 已覆盖采集，不影响数据流 → warning
                        if v4_fed_link_enabled:
                            result["issues"].append(
                                f"{message}联邦 -fed CRD 不存在，但 V4 联邦汇聚链路已启用，影响数据汇聚"
                            )
                        else:
                            result["warnings"].append(
                                f"{message}联邦 -fed CRD 不存在。V4 联邦汇聚未启用，"
                                "子集群普通 DataID CRD 已覆盖采集需求，不影响数据流"
                            )
                    else:
                        result["issues"].append(f"{message}不存在于集群中")
                except Exception as e:
                    dataid_resources.append(
                        {
                            "name": resource_name,
                            "usage": usage,
                            "data_id": data_id,
                            "exists": False,
                            "error": str(e),
                        }
                    )
                    message = f"[DataIDResource] [cluster_id={cluster_info.cluster_id},resource_name={resource_name}] "
                    result["issues"].append(f"{message}检查异常: {str(e)}")

            result["details"]["dataid_resources"] = dataid_resources
            result["details"]["is_fed_cluster"] = is_fed_cluster

            # 确定整体状态（基于 issues / warnings 列表判定，
            # 不再仅看 exists 标志——联邦 -fed CRD 缺失是 warning 不是 issue）
            if not dataid_resources:
                result["status"] = Status.WARNING
                message = f"[DataIDResource] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}没有找到任何DataIDResource资源")
            elif result["issues"]:
                result["status"] = Status.ERROR
            elif result["warnings"]:
                result["status"] = Status.WARNING
            else:
                result["status"] = Status.SUCCESS

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[DataIDResource] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}CRD资源检查异常: {str(e)}")

        return result

    def _compare_dataid_resource(self, cluster_resource: dict, expected_config: dict) -> bool:
        """比较集群中的DataIDResource与期望配置是否一致"""
        try:
            # 比较spec中的关键字段
            cluster_spec = cluster_resource.get("spec", {})
            expected_spec = expected_config.get("spec", {})

            # 比较dataID
            if cluster_spec.get("dataID") != expected_spec.get("dataID"):
                return False

            # 比较labels
            cluster_labels = cluster_spec.get("labels", {})
            expected_labels = expected_spec.get("labels", {})
            if cluster_labels != expected_labels:
                return False

            # 比较metricReplace - 先转换为字典避免Kubernetes对象比较错误
            cluster_metric_replace = cluster_spec.get("metricReplace", {})
            expected_metric_replace = expected_spec.get("metricReplace", {})
            if cluster_metric_replace != expected_metric_replace:
                return False

            # 比较dimensionReplace - 先转换为字典避免Kubernetes对象比较错误
            cluster_dimension_replace = cluster_spec.get("dimensionReplace", {})
            expected_dimension_replace = expected_spec.get("dimensionReplace", {})
            if cluster_dimension_replace != expected_dimension_replace:
                return False

            return True
        except Exception:
            return False

    def _get_dataid_resource_diff(self, cluster_resource: dict, expected_config: dict) -> list[str]:
        """获取DataIDResource配置差异信息"""
        diff_info = []
        try:
            cluster_spec = cluster_resource.get("spec", {})
            expected_spec = expected_config.get("spec", {})

            # 检查dataID
            if cluster_spec.get("dataID") != expected_spec.get("dataID"):
                diff_info.append(
                    f"dataID不一致(current:{cluster_spec.get('dataID')}, expected:{expected_spec.get('dataID')})"
                )

            # 检查labels
            cluster_labels = cluster_spec.get("labels", {})
            expected_labels = expected_spec.get("labels", {})
            for key in set(cluster_labels.keys()) | set(expected_labels.keys()):
                if cluster_labels.get(key) != expected_labels.get(key):
                    diff_info.append(
                        f"labels.{key}不一致(current:{cluster_labels.get(key)}, expected:{expected_labels.get(key)})"
                    )

            # 检查metricReplace
            cluster_metric_replace = cluster_spec.get("metricReplace", {})
            expected_metric_replace = expected_spec.get("metricReplace", {})
            # 将Kubernetes对象转换为字典以避免比较错误
            if cluster_metric_replace != expected_metric_replace:
                # 计算键的差异
                cluster_keys = set(cluster_metric_replace.keys())
                expected_keys = set(expected_metric_replace.keys())
                missing_keys = expected_keys - cluster_keys  # 期望有但集群没有
                extra_keys = cluster_keys - expected_keys  # 集群有但不应该有

                # 计算值的差异
                common_keys = cluster_keys & expected_keys
                value_diff_keys = [
                    k for k in common_keys if cluster_metric_replace.get(k) != expected_metric_replace.get(k)
                ]

                # 组织详细差异信息
                if missing_keys:
                    missing_details = [f"{k}={expected_metric_replace.get(k)}" for k in sorted(missing_keys)]
                    diff_info.append(f"metricReplace缺少{len(missing_keys)}个键: [{', '.join(missing_details)}]")

                if extra_keys:
                    extra_details = [f"{k}={cluster_metric_replace.get(k)}" for k in sorted(extra_keys)]
                    diff_info.append(f"metricReplace多了{len(extra_keys)}个键: [{', '.join(extra_details)}]")

                if value_diff_keys:
                    value_details = [
                        f"{k}(current:{cluster_metric_replace.get(k)}, expected:{expected_metric_replace.get(k)})"
                        for k in sorted(value_diff_keys)
                    ]
                    diff_info.append(f"metricReplace有{len(value_diff_keys)}个键值不同: [{'; '.join(value_details)}]")

                # 如果没有具体差异，但字典不相等（可能是类型问题）
                if not missing_keys and not extra_keys and not value_diff_keys:
                    diff_info.append("metricReplace有差异（类型或结构不同）")

            # 检查dimensionReplace
            cluster_dimension_replace = cluster_spec.get("dimensionReplace", {})
            expected_dimension_replace = expected_spec.get("dimensionReplace", {})
            # 将Kubernetes对象转换为字典以避免比较错误
            if cluster_dimension_replace != expected_dimension_replace:
                # 计算键的差异
                cluster_keys = set(cluster_dimension_replace.keys())
                expected_keys = set(expected_dimension_replace.keys())
                missing_keys = expected_keys - cluster_keys  # 期望有但集群没有
                extra_keys = cluster_keys - expected_keys  # 集群有但不应该有

                # 计算值的差异
                common_keys = cluster_keys & expected_keys
                value_diff_keys = [
                    k for k in common_keys if cluster_dimension_replace.get(k) != expected_dimension_replace.get(k)
                ]

                # 组织详细差异信息
                if missing_keys:
                    missing_details = [f"{k}={expected_dimension_replace.get(k)}" for k in sorted(missing_keys)]
                    diff_info.append(f"dimensionReplace缺少{len(missing_keys)}个键: [{', '.join(missing_details)}]")

                if extra_keys:
                    extra_details = [f"{k}={cluster_dimension_replace.get(k)}" for k in sorted(extra_keys)]
                    diff_info.append(f"dimensionReplace多了{len(extra_keys)}个键: [{', '.join(extra_details)}]")

                if value_diff_keys:
                    value_details = [
                        f"{k}(current:{cluster_dimension_replace.get(k)}, expected:{expected_dimension_replace.get(k)})"
                        for k in sorted(value_diff_keys)
                    ]
                    diff_info.append(
                        f"dimensionReplace有{len(value_diff_keys)}个键值不同: [{'; '.join(value_details)}]"
                    )

                # 如果没有具体差异，但字典不相等（可能是类型问题）
                if not missing_keys and not extra_keys and not value_diff_keys:
                    diff_info.append("dimensionReplace有差异（类型或结构不同）")

        except Exception as e:
            diff_info.append(f"检查差异失败: {str(e)}")

        return diff_info

    @recode_final_result
    def check_k8s_workloads(self, cluster_info: BCSClusterInfo) -> dict:
        """检查 K8s 集群内 bkmonitor-operator 命名空间的核心负载状态

        通过 CoreV1Api / AppsV1Api 只读获取：
        - bkmonitor-operator Deployment
        - bkm-daemonset-worker DaemonSet
        - bkm-statefulset-worker StatefulSet
        - bkm-event-worker Deployment
        - ChildConfig Secret（operator 生成的采集配置）

        Pod 启动后能否跑通是 K8s 自身的问题，本检查只关注配置和负载状态。
        """
        result = {"status": Status.UNKNOWN, "details": {}, "issues": [], "warnings": []}
        namespace = "bkmonitor-operator"

        def format_output(details: dict) -> list[str]:
            lines = []
            workloads = details.get("workloads", {})
            for kind, info in workloads.items():
                if not info.get("found"):
                    lines.append(f"    {kind}: 未找到")
                    continue
                ready = info.get("ready", 0)
                desired = info.get("desired", 0)
                lines.append(f"    {kind}: {ready}/{desired} ready")
            secrets = details.get("child_config_secrets", {})
            if secrets:
                lines.append(
                    f"    ChildConfig Secret: ds={secrets.get('daemonset', 0)} "
                    f"sts={secrets.get('statefulset', 0)} event={secrets.get('event', 0)}"
                )
            return lines

        result["formatter"] = format_output

        try:
            apps_v1 = k8s_client.AppsV1Api(cluster_info.api_client)
            core_v1 = k8s_client.CoreV1Api(cluster_info.api_client)

            workloads = {}

            # D1. bkmonitor-operator Deployment
            workloads["bkm-operator"] = self._check_deployment(apps_v1, namespace, "bkm-operator", result["issues"])

            # D2. bkm-daemonset-worker DaemonSet
            workloads["bkm-daemonset-worker"] = self._check_daemonset(
                apps_v1, namespace, "bkm-daemonset-worker", result["issues"]
            )

            # D3. bkm-statefulset-worker StatefulSet
            workloads["bkm-statefulset-worker"] = self._check_statefulset(
                apps_v1, namespace, "bkm-statefulset-worker", result["issues"]
            )

            # D4. bkm-event-worker Deployment
            workloads["bkm-event-worker"] = self._check_deployment(
                apps_v1, namespace, "bkm-event-worker", result["issues"]
            )

            result["details"]["workloads"] = workloads

            # D5. ChildConfig Secret 存在性
            # 按 operator 源码（pkg/operator/common/tasks/tasks.go）规范：
            #   Secret 名: daemonset-worker-{node} / statefulset-worker-{idx} / event-worker-0
            #   Secret label: taskType=daemonset | statefulset | event
            # 优先按 label 选择，更稳健
            ds_secrets = self._count_task_secrets(core_v1, namespace, "daemonset", result["issues"])
            sts_secrets = self._count_task_secrets(core_v1, namespace, "statefulset", result["issues"])
            event_secrets = self._count_task_secrets(core_v1, namespace, "event", result["issues"])

            result["details"]["child_config_secrets"] = {
                "daemonset": ds_secrets,
                "statefulset": sts_secrets,
                "event": event_secrets,
            }

            # 只在 workload 已部署但对应 Secret=0 时报错
            if ds_secrets == 0 and workloads.get("bkm-daemonset-worker", {}).get("desired", 0) > 0:
                result["issues"].append(
                    f"[Secret] [namespace={namespace},taskType=daemonset] 未找到 ChildConfig Secret，"
                    "operator 可能未完成采集配置下发"
                )
            if sts_secrets == 0 and workloads.get("bkm-statefulset-worker", {}).get("desired", 0) > 0:
                result["issues"].append(
                    f"[Secret] [namespace={namespace},taskType=statefulset] 未找到 ChildConfig Secret"
                )

            if result["issues"]:
                result["status"] = Status.ERROR
            else:
                result["status"] = Status.SUCCESS

        except Exception as e:
            result["status"] = Status.ERROR
            result["issues"].append(f"[K8sWorkloads] [cluster_id={cluster_info.cluster_id}] 负载检查异常: {str(e)}")

        return result

    @staticmethod
    def _workload_status(found: bool, ready: int, desired: int, reason: str = "") -> dict:
        return {"found": found, "ready": ready, "desired": desired, "reason": reason}

    def _count_task_secrets(self, core_v1, namespace: str, task_type: str, issues: list) -> int:
        """按 taskType label 计数 operator 生成的 ChildConfig Secret

        operator 源码（pkg/operator/common/tasks/tasks.go）约定 LabelTaskType="taskType"
        失败时返回 0 并记录 issue，不中断其他检查
        """
        try:
            resp = core_v1.list_namespaced_secret(namespace=namespace, label_selector=f"taskType={task_type}")
            return len(resp.items or [])
        except ApiException as e:
            issues.append(f"[Secret] [namespace={namespace},taskType={task_type}] 列出 Secret 失败: {e.reason}")
            return 0

    def _check_deployment(self, apps_v1, namespace: str, name: str, issues: list) -> dict:
        try:
            d = apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
            ready = d.status.ready_replicas or 0
            desired = d.spec.replicas or 0
            if ready < desired:
                issues.append(f"[Deployment] [namespace={namespace},name={name}] ready={ready}/{desired} 未就绪")
            return self._workload_status(True, ready, desired)
        except ApiException as e:
            if e.status == 404:
                issues.append(f"[Deployment] [namespace={namespace},name={name}] 未找到")
                return self._workload_status(False, 0, 0, "not_found")
            issues.append(f"[Deployment] [namespace={namespace},name={name}] 查询异常: {e.reason}")
            return self._workload_status(False, 0, 0, str(e.reason))

    def _check_daemonset(self, apps_v1, namespace: str, name: str, issues: list) -> dict:
        try:
            d = apps_v1.read_namespaced_daemon_set(name=name, namespace=namespace)
            ready = d.status.number_ready or 0
            desired = d.status.desired_number_scheduled or 0
            if ready < desired:
                issues.append(f"[DaemonSet] [namespace={namespace},name={name}] ready={ready}/{desired} 未全部就绪")
            return self._workload_status(True, ready, desired)
        except ApiException as e:
            if e.status == 404:
                issues.append(f"[DaemonSet] [namespace={namespace},name={name}] 未找到")
                return self._workload_status(False, 0, 0, "not_found")
            issues.append(f"[DaemonSet] [namespace={namespace},name={name}] 查询异常: {e.reason}")
            return self._workload_status(False, 0, 0, str(e.reason))

    def _check_statefulset(self, apps_v1, namespace: str, name: str, issues: list) -> dict:
        try:
            s = apps_v1.read_namespaced_stateful_set(name=name, namespace=namespace)
            ready = s.status.ready_replicas or 0
            desired = s.spec.replicas or 0
            if ready < desired:
                issues.append(f"[StatefulSet] [namespace={namespace},name={name}] ready={ready}/{desired} 未就绪")
            return self._workload_status(True, ready, desired)
        except ApiException as e:
            if e.status == 404:
                issues.append(f"[StatefulSet] [namespace={namespace},name={name}] 未找到")
                return self._workload_status(False, 0, 0, "not_found")
            issues.append(f"[StatefulSet] [namespace={namespace},name={name}] 查询异常: {e.reason}")
            return self._workload_status(False, 0, 0, str(e.reason))

    @recode_final_result
    def check_cluster_init_resources(self, cluster_info: BCSClusterInfo) -> dict:
        """检查集群初始化资源状态

        检查项目包括：
        1. EventGroup 创建状态
        2. TimeSeriesGroup 创建状态
        3. SpaceDataSource 关联状态
        4. ConfigMap 配置状态
        """
        result = {"status": Status.UNKNOWN, "details": {}, "issues": []}

        def format_output(details: dict) -> list[str]:
            """格式化集群初始化资源检查输出"""
            lines = []
            if details:
                lines.append(f"    TimeSeriesGroup: {len(details.get('time_series_groups', []))}个")
                lines.append(f"    SpaceDataSource: {len(details.get('space_datasources', []))}个")
                lines.append(f"    ConfigMap配置: {len(details.get('configmap_configs', []))}个")
            return lines

        result["formatter"] = format_output

        try:
            # 1. 检查EventGroup创建状态
            if cluster_info.K8sEventDataID != 0:
                try:
                    # EventGroup 通过 bk_data_id 关联 DataSource，间接实现租户隔离
                    event_group = models.EventGroup.objects.get(bk_data_id=cluster_info.K8sEventDataID)
                    result["details"]["event_group"] = {
                        "exists": True,
                        "bk_data_id": event_group.bk_data_id,
                        "bk_biz_id": event_group.bk_biz_id,
                        "is_enable": event_group.is_enable,
                    }

                    if not event_group.is_enable:
                        message = f"[EventGroup] [bk_data_id={cluster_info.K8sEventDataID}] "
                        result["issues"].append(f"{message}EventGroup未启用")

                except models.EventGroup.DoesNotExist:
                    result["details"]["event_group"] = {"exists": False}
                    message = f"[EventGroup] [bk_data_id={cluster_info.K8sEventDataID}] "
                    result["issues"].append(f"{message}EventGroup不存在")

            # 2. 检查TimeSeriesGroup创建状态
            time_series_groups = []
            for data_id in [cluster_info.K8sMetricDataID, cluster_info.CustomMetricDataID]:
                if data_id == 0:
                    continue

                try:
                    # TimeSeriesGroup 通过 bk_data_id 关联 DataSource，间接实现租户隔离
                    ts_groups = models.TimeSeriesGroup.objects.filter(
                        bk_data_id=data_id, is_delete=False, bk_tenant_id=self.bk_tenant_id
                    )
                    for ts_group in ts_groups:
                        metrics_count = models.TimeSeriesMetric.objects.filter(
                            group_id=ts_group.time_series_group_id
                        ).count()

                        time_series_groups.append(
                            {
                                "group_id": ts_group.time_series_group_id,
                                "bk_data_id": ts_group.bk_data_id,
                                "table_id": ts_group.table_id,
                                "metrics_count": metrics_count,
                                "is_split_measurement": ts_group.is_split_measurement,
                            }
                        )

                except Exception as e:
                    message = f"[TimeSeriesGroup] [bk_data_id={data_id}] "
                    result["issues"].append(f"{message}TimeSeriesGroup检查异常: {str(e)}")

            result["details"]["time_series_groups"] = time_series_groups

            if not time_series_groups:
                message = f"[TimeSeriesGroup] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}没有找到任何TimeSeriesGroup记录")

            # 3. 检查SpaceDataSource关联状态
            space_datasources = []
            space_uid = f"bkcc__{cluster_info.bk_biz_id}"

            for data_id in [cluster_info.K8sMetricDataID, cluster_info.CustomMetricDataID, cluster_info.K8sEventDataID]:
                if data_id == 0:
                    continue

                try:
                    space_ds = models.SpaceDataSource.objects.filter(
                        bk_data_id=data_id, space_uid=space_uid, bk_tenant_id=self.bk_tenant_id
                    ).first()

                    if space_ds:
                        space_datasources.append(
                            {
                                "bk_data_id": space_ds.bk_data_id,
                                "space_uid": space_ds.space_uid,
                                "space_type_id": space_ds.space_type_id,
                                "space_id": space_ds.space_id,
                            }
                        )
                    else:
                        message = f"[SpaceDataSource] [bk_data_id={data_id},space_uid={space_uid}] "
                        result["issues"].append(f"{message}未关联到空间")

                except Exception as e:
                    message = f"[SpaceDataSource] [bk_data_id={data_id}] "
                    result["issues"].append(f"{message}SpaceDataSource检查异常: {str(e)}")

            result["details"]["space_datasources"] = space_datasources

            # 4. 检查ConfigMap配置状态
            try:
                core_api = cluster_info.core_api
                configmaps = core_api.list_namespaced_config_map(namespace="bkmonitor-operator")

                bk_collector_configs = []
                for cm in configmaps.items:
                    if "bk-collector" in cm.metadata.name and "config" in cm.metadata.name:
                        config_data = cm.data or {}

                        bk_collector_configs.append(
                            {
                                "name": cm.metadata.name,
                                "namespace": cm.metadata.namespace,
                                "creation_timestamp": str(cm.metadata.creation_timestamp),
                                "data_keys": list(config_data.keys()),
                                "data_size": sum(len(str(v)) for v in config_data.values()),
                            }
                        )

                result["details"]["configmap_configs"] = bk_collector_configs

                if not bk_collector_configs:
                    message = f"[ConfigMap] [cluster_id={cluster_info.cluster_id}] "
                    result["issues"].append(f"{message}未找到bk-collector相关的ConfigMap配置")

            except ApiException as e:
                message = f"[ConfigMap] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}ConfigMap检查失败: {e.reason}")
            except Exception as e:
                message = f"[ConfigMap] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}ConfigMap检查异常: {str(e)}")

            # 确定整体状态
            if not result["issues"]:
                result["status"] = Status.SUCCESS
            elif any("不存在" in issue or "异常" in issue for issue in result["issues"]):
                result["status"] = Status.ERROR
            else:
                result["status"] = Status.WARNING

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[ClusterInitResources] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}集群初始化资源检查异常: {str(e)}")

        return result

    @recode_final_result
    def check_bk_collector_config(self, cluster_info: BCSClusterInfo) -> dict:
        """检查bk-collector配置状态

        检查项目包括：
        1. bk-collector DaemonSet 部署状态
        2. bk-collector Pod 运行状态
        3. bk-collector 配置文件完整性
        4. 数据采集配置有效性
        """
        result = {"status": Status.UNKNOWN, "details": {}, "issues": []}

        def format_output(details: dict) -> list[str]:
            """格式化bk-collector配置检查输出"""
            lines = []
            if details.get("daemonset") and details["daemonset"].get("name"):
                ds = details["daemonset"]
                lines.append(f"    DaemonSet: {ds['ready_pods']}/{ds['desired_pods']} 就绪")
            lines.append(f"    Pod数量: {len(details.get('pods', []))}个")
            lines.append(f"    配置文件: {len(details.get('config_files', []))}个")
            return lines

        result["formatter"] = format_output

        try:
            core_api = cluster_info.core_api
            apps_api = cluster_info.apps_api

            # 1. 检查bk-collector DaemonSet部署状态
            try:
                daemonsets = apps_api.list_namespaced_daemon_set(namespace="bkmonitor-operator")
                bk_collector_ds = None

                for ds in daemonsets.items:
                    if "bk-collector" in ds.metadata.name:
                        bk_collector_ds = ds
                        break

                if bk_collector_ds:
                    result["details"]["daemonset"] = {
                        "name": bk_collector_ds.metadata.name,
                        "namespace": bk_collector_ds.metadata.namespace,
                        "desired_pods": bk_collector_ds.status.desired_number_scheduled,
                        "current_pods": bk_collector_ds.status.current_number_scheduled,
                        "ready_pods": bk_collector_ds.status.number_ready,
                        "available_pods": bk_collector_ds.status.number_available,
                    }

                    # 检查Pod状态
                    if bk_collector_ds.status.number_ready != bk_collector_ds.status.desired_number_scheduled:
                        result["issues"].append(
                            f"bk-collector DaemonSet中有{bk_collector_ds.status.desired_number_scheduled - bk_collector_ds.status.number_ready}个Pod未就绪"
                        )
                else:
                    result["details"]["daemonset"] = {"exists": False}
                    message = f"[DaemonSet] [cluster_id={cluster_info.cluster_id},name=bk-collector] "
                    result["issues"].append(f"{message}未部署")

            except ApiException as e:
                message = f"[DaemonSet] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}检查失败: {e.reason}")

            # 2. 检查bk-collector Pod运行状态
            try:
                pods = core_api.list_namespaced_pod(namespace="bkmonitor-operator", label_selector="app=bk-collector")

                pod_status = []
                for pod in pods.items:
                    container_statuses = []
                    if pod.status.container_statuses:
                        for container in pod.status.container_statuses:
                            container_statuses.append(
                                {
                                    "name": container.name,
                                    "ready": container.ready,
                                    "restart_count": container.restart_count,
                                    "state": str(container.state),
                                }
                            )

                    pod_status.append(
                        {
                            "name": pod.metadata.name,
                            "phase": pod.status.phase,
                            "node_name": pod.spec.node_name,
                            "containers": container_statuses,
                        }
                    )

                    # 检查Pod是否有异常
                    if pod.status.phase != "Running":
                        message = f"[Pod] [cluster_id={cluster_info.cluster_id},pod_name={pod.metadata.name}] "
                        result["issues"].append(f"{message}状态异常: {pod.status.phase}")

                    # 检查容器重启次数
                    if pod.status.container_statuses:
                        for container in pod.status.container_statuses:
                            if container.restart_count > 5:
                                message = f"[Pod] [cluster_id={cluster_info.cluster_id},pod_name={pod.metadata.name},container_name={container.name}] "
                                result["issues"].append(f"{message}容器重启次数过多: {container.restart_count}")

                result["details"]["pods"] = pod_status

            except ApiException as e:
                message = f"[Pod] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}检查失败: {e.reason}")

            # 3. 检查bk-collector配置文件完整性
            try:
                configmaps = core_api.list_namespaced_config_map(namespace="bkmonitor-operator")
                config_files = []

                for cm in configmaps.items:
                    if "bk-collector" in cm.metadata.name and "config" in cm.metadata.name:
                        config_data = cm.data or {}

                        # 检查关键配置文件
                        required_configs = ["config.yaml", "cluster_config.yaml"]
                        missing_configs = []

                        for config_name in required_configs:
                            if config_name not in config_data:
                                missing_configs.append(config_name)

                        config_files.append(
                            {
                                "name": cm.metadata.name,
                                "config_keys": list(config_data.keys()),
                                "missing_configs": missing_configs,
                            }
                        )

                        if missing_configs:
                            message = (
                                f"[ConfigMap] [cluster_id={cluster_info.cluster_id},configmap_name={cm.metadata.name}] "
                            )
                            result["issues"].append(f"{message}缺少关键配置: {', '.join(missing_configs)}")

                result["details"]["config_files"] = config_files

            except ApiException as e:
                message = f"[ConfigMap] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}配置文件检查失败: {e.reason}")

            # 4. 检查数据采集配置有效性（检查dataID是否正确配置）
            collection_configs = {
                "K8sMetricDataID": cluster_info.K8sMetricDataID,
                "CustomMetricDataID": cluster_info.CustomMetricDataID,
                "K8sEventDataID": cluster_info.K8sEventDataID,
            }

            invalid_configs = []
            for config_name, data_id in collection_configs.items():
                if data_id == 0:
                    invalid_configs.append(config_name)

            result["details"]["collection_configs"] = collection_configs

            if invalid_configs:
                message = f"[BCSClusterInfo] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}以下数据采集配置无效: {', '.join(invalid_configs)}")

            # 确定整体状态
            if not result["issues"]:
                result["status"] = Status.SUCCESS
            elif any("未部署" in issue or "失败" in issue for issue in result["issues"]):
                result["status"] = Status.ERROR
            else:
                result["status"] = Status.WARNING

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[BkCollector] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}bk-collector配置检查异常: {str(e)}")

        return result

    @recode_final_result
    def check_bcs_api_token(self, cluster_info: BCSClusterInfo) -> dict:
        """检查BCS API Token配置状态"""
        result = {"status": Status.UNKNOWN, "details": {}, "issues": []}

        def format_output(details: dict) -> list[str]:
            """格式化API Token检查输出"""
            lines = []
            if details:
                lines.append(f"    Token已配置: {details.get('api_key_configured', False)}")
                if "token_length" in details:
                    lines.append(f"    Token长度: {details['token_length']} 字符")
            return lines

        result["formatter"] = format_output

        try:
            # 检查API密钥是否配置
            if not cluster_info.api_key_content:
                message = f"[BCSClusterInfo] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}BCS API Token未配置")
                result["status"] = Status.ERROR
                result["details"] = {"api_key_configured": False}
                return result

            # 检查API密钥是否与当前配置一致
            from django.conf import settings

            if cluster_info.api_key_content != settings.BCS_API_GATEWAY_TOKEN:
                message = f"[BCSClusterInfo] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}BCS API Token与当前配置不一致")
                result["status"] = Status.WARNING
            else:
                result["status"] = Status.SUCCESS

            result["details"] = {
                "api_key_configured": True,
                "api_key_match": cluster_info.api_key_content == settings.BCS_API_GATEWAY_TOKEN,
                "token_length": len(cluster_info.api_key_content) if cluster_info.api_key_content else 0,
            }

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[BCSClusterInfo] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}BCS API Token检查异常: {str(e)}")

        return result

    def _get_space_info_by_biz_id(self, bk_biz_id: int, datasource: DataSource) -> dict:
        """
        通过业务ID获取空间信息
        """

        target_bk_biz_id = bk_biz_id
        data_id = datasource.bk_data_id

        if target_bk_biz_id == 0:
            if TimeSeriesGroup.objects.filter(bk_data_id=data_id, bk_tenant_id=self.bk_tenant_id).exists():
                # 自定义时序指标，查找所属空间
                target_bk_biz_id = datasource.data_name.split("_")[0]
            elif EventGroup.objects.filter(bk_data_id=data_id, bk_tenant_id=self.bk_tenant_id).exists():
                # 自定义事件，查找所属空间
                target_bk_biz_id = datasource.data_name.split("_")[-1]
            try:
                # 不符合要求的data_name，无法解析业务字段，使用默认全局业务。
                target_bk_biz_id = int(target_bk_biz_id)
            except (ValueError, TypeError):
                target_bk_biz_id = 0

        space_type_id = datasource.space_type_id
        space_uid = datasource.space_uid

        if target_bk_biz_id != 0:
            space = Space.objects.get_space_info_by_biz_id(bk_biz_id=int(target_bk_biz_id))
            space_type_id, space_uid = space["space_type"], space["space_id"]

        return {
            "space_type_id": space_type_id,
            "space_uid": space_uid,
        }

    @recode_final_result
    def check_space_type_and_datasource(self, cluster_info: BCSClusterInfo) -> dict:
        """检查空间类型与SpaceDataSource关联

        验证数据源的空间类型配置是否正确
        """
        result = {"status": Status.UNKNOWN, "details": {}, "issues": []}

        def format_output(details: dict) -> list[str]:
            """格式化空间类型检查输出"""
            lines = []
            if details:
                total_datasources = len(details)
                lines.append(f"    数据源数量: {total_datasources}")
                all_space_count = sum(1 for v in details.values() if isinstance(v, dict) and v.get("is_all_space_type"))
                lines.append(f"    全局空间类型: {all_space_count}/{total_datasources}")
            return lines

        result["formatter"] = format_output

        try:
            space_check_status = {}

            for data_id, datasource in self.data_sources.items():
                try:
                    space_info = self._get_space_info_by_biz_id(bk_biz_id=self.bk_biz_id, datasource=datasource)
                    space_type_id = space_info.get("space_type_id", datasource.space_type_id)
                    space_uid = space_info.get("space_uid", datasource.space_uid)

                    # 检查是否为全局空间类型
                    is_all_space_type = space_type_id == SpaceTypes.ALL.value

                    space_datasource_exists = False

                    if space_type_id and space_uid:
                        # 查询SpaceDataSource关联
                        space_ds = SpaceDataSource.objects.filter(
                            bk_data_id=data_id,
                            space_id=space_uid,
                            bk_tenant_id=self.bk_tenant_id,
                            space_type_id=space_type_id,
                        ).first()

                        if space_ds:
                            space_datasource_exists = True
                        else:
                            message = f"[SpaceDataSource] [bk_data_id={data_id},space_uid={space_uid},space_type_id={space_type_id}] "
                            result["issues"].append(f"{message}缺少SpaceDataSource关联")

                        space = Space.objects.filter(space_id=space_uid, space_type_id=space_type_id).first()
                        if not space:
                            message = f"[Space] [space_uid={space_uid},space_type_id={space_type_id}] "
                            result["issues"].append(f"{message}空间不存在")
                        elif space.status != SpaceStatus.NORMAL.value:
                            message = f"[Space] [space_uid={space_uid},space_type_id={space_type_id}] "
                            result["issues"].append(f"{message}空间状态异常: {space.status}")

                    space_check_status[data_id] = {
                        "space_uid": space_uid,
                        "space_type_id": space_type_id,
                        "is_all_space_type": is_all_space_type,
                        "space_datasource_exists": space_datasource_exists if not is_all_space_type else None,
                    }

                except Exception as e:
                    space_check_status[data_id] = {"error": str(e)}
                    message = f"[DataSource] [bk_data_id={data_id}] "
                    result["issues"].append(f"{message}空间类型检查异常: {str(e)}")

            result["details"] = space_check_status
            result["status"] = Status.SUCCESS if not result["issues"] else Status.ERROR

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[SpaceDataSource] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}空间类型检查异常: {str(e)}")

        return result

    @recode_final_result
    def check_related_result_table(self, cluster_info: BCSClusterInfo) -> dict:
        """检查关联的结果表

        验证结果表相关的配置数据是否完整
        """
        result = {"status": Status.UNKNOWN, "details": {}, "issues": []}

        def format_output(details: dict) -> list[str]:
            """格式化关联模型检查输出"""
            lines = []
            if details:
                ds_rt_count = len(details.get("datasource_result_table", {}))
                rt_options_count = len(details.get("result_table_options", {}))
                filter_alias_count = details.get("space_type_filter_alias", {}).get("total_count", 0)
                lines.append(f"    数据源结果表: {ds_rt_count}")
                lines.append(f"    结果表配置: {rt_options_count}")
                lines.append(f"    空间类型路由别名: {filter_alias_count}")
            return lines

        result["formatter"] = format_output

        try:
            datasource_result_table = {}
            result_table_options = {}
            result_table_fields = {}
            result_table_field_options = {}
            space_type_filter_alias = {}
            all_table_ids = set()

            # 检查 DataSourceResultTable
            for data_id, datasource in self.data_sources.items():
                try:
                    ds_rt = DataSourceResultTable.objects.filter(
                        bk_data_id=data_id, bk_tenant_id=self.bk_tenant_id
                    ).first()

                    if ds_rt:
                        table_id = ds_rt.table_id
                        all_table_ids.add(table_id)
                        tenant_consistent = ds_rt.bk_tenant_id == datasource.bk_tenant_id

                        datasource_result_table[data_id] = {
                            "table_id": table_id,
                            "relation_exists": True,
                            "tenant_consistent": tenant_consistent,
                        }

                        # 检查ResultTableOption
                        options = ResultTableOption.objects.filter(table_id=table_id, bk_tenant_id=self.bk_tenant_id)
                        option_names = [opt.name for opt in options]

                        result_table_options[table_id] = {
                            "options_count": len(option_names),
                            "required_options_present": True,
                            "configured_options": option_names,
                        }

                        # 检查ResultTableField
                        fields = ResultTableField.objects.filter(table_id=table_id, bk_tenant_id=self.bk_tenant_id)

                        time_field_exists = fields.filter(field_name="time").exists()
                        metric_fields = fields.filter(tag=ResultTableField.FIELD_TAG_METRIC)
                        dimension_fields = fields.filter(tag=ResultTableField.FIELD_TAG_DIMENSION)

                        result_table_fields[table_id] = {
                            "total_fields": fields.count(),
                            "time_field_exists": time_field_exists,
                            "metric_fields_count": metric_fields.count(),
                            "dimension_fields_count": dimension_fields.count(),
                        }

                        if not time_field_exists:
                            message = f"[ResultTableField] [table_id={table_id}] "
                            result["issues"].append(f"{message}缺少时间字段")

                        # 检查ResultTableFieldOption
                        field_options = ResultTableFieldOption.objects.filter(
                            table_id=table_id, bk_tenant_id=self.bk_tenant_id
                        )

                        result_table_field_options[table_id] = {
                            "fields_with_options": field_options.values("field_name").distinct().count(),
                        }

                    else:
                        datasource_result_table[data_id] = {"relation_exists": False}
                        message = f"[DataSourceResultTable] [bk_data_id={data_id}] "
                        result["issues"].append(f"{message}缺少结果表关联")

                except Exception as e:
                    message = f"[DataSourceResultTable] [bk_data_id={data_id}] "
                    result["issues"].append(f"{message}关联模型检查异常: {str(e)}")

            result["details"] = {
                "datasource_result_table": datasource_result_table,
                "result_table_options": result_table_options,
                "result_table_fields": result_table_fields,
                "result_table_field_options": result_table_field_options,
                "space_type_filter_alias": space_type_filter_alias,
            }

            result["status"] = Status.SUCCESS if not result["issues"] else Status.WARNING

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[ResultTable] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}关联模型检查异常: {str(e)}")

        return result

    @recode_final_result
    def check_influxdb_storage_config(self, cluster_info: BCSClusterInfo) -> dict:
        """检查InfluxDB存储配置

        验证InfluxDB存储相关配置的完整性和正确性
        """
        result = {"status": Status.UNKNOWN, "details": {}, "issues": []}

        def format_output(details: dict) -> list[str]:
            """格式化InfluxDB存储配置检查输出"""
            lines = []
            if details:
                proxy_count = details.get("influxdb_proxy_storage", {}).get("total_records", 0)
                cluster_count = details.get("influxdb_cluster_info", {}).get("total_clusters", 0)
                host_count = details.get("influxdb_host_info", {}).get("total_hosts", 0)
                lines.append(f"    代理存储: {proxy_count}")
                lines.append(f"    集群: {cluster_count}")
                lines.append(f"    主机: {host_count}")
            return lines

        result["formatter"] = format_output

        try:
            # 检查InfluxDBProxyStorage
            proxy_storage_details = []
            influxdb_storages = []

            for data_id, data_source in self.data_sources.items():
                try:
                    ds_rt = DataSourceResultTable.objects.filter(
                        bk_data_id=data_id, bk_tenant_id=self.bk_tenant_id
                    ).first()

                    if not ds_rt:
                        result["issues"].append(f"[DataSourceResultTable] [bk_data_id={data_id}] 数据源结果表不存在")
                        continue

                    result_table = ResultTable.objects.filter(
                        table_id=ds_rt.table_id, bk_tenant_id=self.bk_tenant_id
                    ).first()
                    if not result_table:
                        result["issues"].append(f"[ResultTable] [table_id={ds_rt.table_id}] 结果表不存在")
                        continue

                    if (
                        result_table.default_storage != ClusterInfo.TYPE_INFLUXDB
                        or not settings.ENABLE_INFLUXDB_STORAGE
                    ):
                        continue

                    # 查询InfluxDB存储
                    influx_storages = InfluxDBStorage.objects.filter(
                        table_id=ds_rt.table_id, bk_tenant_id=self.bk_tenant_id
                    )

                    if not influx_storages.exists():
                        message = f"[InfluxDBStorage] [table_id={ds_rt.table_id}] "
                        result["issues"].append(f"{message}InfluxDB存储不存在")
                        continue

                    for storage in influx_storages:
                        influxdb_storages.append(storage)

                        message = f"[InfluxDBStorage] [table_id={storage.table_id}] "
                        # 检查代理存储配置
                        if hasattr(storage, "influxdb_proxy_storage_id"):
                            try:
                                proxy_storage = InfluxDBProxyStorage.objects.filter(
                                    id=storage.influxdb_proxy_storage_id
                                ).first()

                                if proxy_storage:
                                    proxy_storage_details.append(
                                        {
                                            "proxy_cluster_id": proxy_storage.proxy_cluster_id,
                                            "service_name": proxy_storage.service_name,
                                            "instance_cluster_name": proxy_storage.instance_cluster_name,
                                            "is_default": proxy_storage.is_default,
                                        }
                                    )
                                else:
                                    result["issues"].append(
                                        f"{message}存储代理存储配置influxdb_proxy_storage_id[{storage.influxdb_proxy_storage_id}]不存在"
                                    )
                            except Exception as e:
                                result["issues"].append(
                                    f"{message}存储代理配置influxdb_proxy_storage_id[{storage.influxdb_proxy_storage_id}]检查异常: {str(e)}"
                                )
                        else:
                            result["issues"].append(f"{message}代理存储字段influxdb_proxy_storage_id为空")

                except Exception as e:
                    message = f"[InfluxDBStorage] [bk_data_id={data_id}] "
                    result["issues"].append(f"{message}InfluxDB存储检查异常: {str(e)}")

            # 检查InfluxDBClusterInfo
            cluster_details = []
            try:
                clusters = InfluxDBClusterInfo.objects.all()
                for cluster in clusters:
                    # 获取集群关联的主机数量
                    host_count = InfluxDBClusterInfo.objects.filter(cluster_name=cluster.cluster_name).count()

                    cluster_details.append(
                        {
                            "cluster_name": cluster.cluster_name,
                            "host_count": host_count,
                            "host_readable": cluster.host_readable,
                        }
                    )

            except Exception as e:
                message = f"[InfluxDBClusterInfo] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}检查异常: {str(e)}")

            # 检查InfluxDBHostInfo
            host_details = []
            try:
                hosts = InfluxDBHostInfo.objects.all()
                for host in hosts:
                    host_details.append(
                        {
                            "host_name": host.host_name,
                            "domain_name": host.domain_name,
                            "port": host.port,
                        }
                    )

            except Exception as e:
                message = f"[InfluxDBHostInfo] [cluster_id={cluster_info.cluster_id}] "
                result["issues"].append(f"{message}检查异常: {str(e)}")

            result["details"] = {
                "influxdb_proxy_storage": {
                    "total_records": len(proxy_storage_details),
                    "proxy_details": proxy_storage_details,
                },
                "influxdb_cluster_info": {
                    "total_clusters": len(set([c["cluster_name"] for c in cluster_details])),
                    "clusters_detail": cluster_details,
                },
                "influxdb_host_info": {
                    "total_hosts": len(host_details),
                    "host_details": host_details[:10],  # 只显示前10个
                },
            }

            result["status"] = Status.SUCCESS if not result["issues"] else Status.WARNING

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[InfluxDBStorage] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}InfluxDB存储配置检查异常: {str(e)}")

        return result

    @recode_final_result
    def check_elasticsearch_storage_config(self, cluster_info: BCSClusterInfo) -> dict:
        """检查Elasticsearch存储配置

        验证Elasticsearch存储相关配置的完整性和正确性
        """
        result = {"status": Status.UNKNOWN, "details": {}, "issues": []}

        def format_output(details: dict) -> list[str]:
            """格式化Elasticsearch存储配置检查输出"""
            lines = []
            if details:
                storage_count = details.get("es_storage", {}).get("total_storages", 0)
                cluster_count = details.get("cluster_info", {}).get("total_clusters", 0)
                record_count = details.get("storage_cluster_records", {}).get("total_records", 0)
                lines.append(f"    ES存储: {storage_count}")
                lines.append(f"    ES集群: {cluster_count}")
                lines.append(f"    存储集群记录: {record_count}")
            return lines

        result["formatter"] = format_output

        try:
            es_storage_details = []
            cluster_details = {}
            storage_cluster_records = []

            # 检查ESStorage配置
            for data_id, data_source in self.data_sources.items():
                try:
                    ds_rt = DataSourceResultTable.objects.filter(
                        bk_data_id=data_id, bk_tenant_id=self.bk_tenant_id
                    ).first()

                    if not ds_rt:
                        result["issues"].append(f"[DataSourceResultTable] [data_id={data_id}] 存储结果表不存在")
                        continue

                    result_table = ResultTable.objects.filter(
                        table_id=ds_rt.table_id, bk_tenant_id=self.bk_tenant_id
                    ).first()
                    if not result_table:
                        result["issues"].append(f"[ResultTable] [table_id={ds_rt.table_id}] 结果表不存在")
                        continue

                    if result_table.default_storage != ClusterInfo.TYPE_ES:
                        continue

                    # 查询ES存储
                    es_storages = ESStorage.objects.filter(table_id=ds_rt.table_id, bk_tenant_id=self.bk_tenant_id)
                    if not es_storages:
                        message = f"[ESStorage] [table_id={ds_rt.table_id}] "
                        result["issues"].append(f"{message}存储配置为空")
                        continue

                    for storage in es_storages:
                        message = f"[ESStorage] [table_id={storage.table_id}] "

                        # 检查存储集群配置
                        if not storage.storage_cluster:
                            result["issues"].append(
                                f"{message}[ClusterInfo][cluster_id={storage.storage_cluster_id}]存储集群配置为空"
                            )
                            continue

                        cluster = storage.storage_cluster

                        # 检查集群类型
                        if cluster.cluster_type != ClusterInfo.TYPE_ES:
                            message_cluster = (
                                f"[ClusterInfo] [cluster_id={cluster.cluster_id},cluster_type={cluster.cluster_type}] "
                            )
                            result["issues"].append(f"{message_cluster}集群类型不是ES")

                        # 收集集群信息
                        if cluster.cluster_id not in cluster_details:
                            cluster_details[cluster.cluster_id] = {
                                "cluster_name": cluster.cluster_name,
                                "cluster_type": cluster.cluster_type,
                                "domain_name": cluster.domain_name,
                                "port": cluster.port,
                                "is_default_cluster": cluster.is_default_cluster,
                                "storage_count": 0,
                            }
                        cluster_details[cluster.cluster_id]["storage_count"] += 1

                        # 检查关键配置项
                        storage_detail = {
                            "table_id": storage.table_id,
                            "cluster_id": storage.storage_cluster_id,
                            "date_format": storage.date_format,
                            "slice_size": storage.slice_size,
                            "slice_gap": storage.slice_gap,
                            "retention": storage.retention,
                            "warm_phase_days": storage.warm_phase_days,
                            "time_zone": storage.time_zone,
                            "source_type": storage.source_type,
                            "need_create_index": storage.need_create_index,
                        }

                        # 检查date_format是否合法(只包含数字)
                        try:
                            test_str = datetime.datetime.utcnow().strftime(storage.date_format)
                            if not test_str.isdigit():
                                result["issues"].append(f"{message}date_format格式不合法，包含非数字字符")
                        except Exception as e:
                            result["issues"].append(f"{message}date_format格式验证失败: {str(e)}")

                        # 检查时区设置是否合法(-12到12)
                        if not (-12 <= storage.time_zone <= 12):
                            result["issues"].append(f"{message}time_zone设置不合法: {storage.time_zone}")

                        # 检查暖数据配置
                        if storage.warm_phase_days > 0:
                            warm_settings = storage.warm_phase_settings
                            if not warm_settings:
                                result["issues"].append(f"{message}warm_phase_days>0但warm_phase_settings为空")
                            else:
                                required_fields = ["allocation_attr_name", "allocation_attr_value", "allocation_type"]
                                missing_fields = [f for f in required_fields if not warm_settings.get(f)]
                                if missing_fields:
                                    result["issues"].append(
                                        f"{message}warm_phase_settings缺少必填字段: {', '.join(missing_fields)}"
                                    )

                        # 检查index_settings和mapping_settings是否为有效JSON
                        try:
                            json.loads(storage.index_settings)
                        except (json.JSONDecodeError, TypeError):
                            result["issues"].append(f"{message}index_settings不是有效的JSON格式")

                        try:
                            json.loads(storage.mapping_settings)
                        except (json.JSONDecodeError, TypeError):
                            result["issues"].append(f"{message}mapping_settings不是有效的JSON格式")

                        es_storage_details.append(storage_detail)

                        # 检查StorageClusterRecord记录
                        try:
                            cluster_records = StorageClusterRecord.objects.filter(
                                table_id=storage.table_id, bk_tenant_id=self.bk_tenant_id, is_deleted=False
                            ).order_by("-create_time")

                            if not cluster_records.exists():
                                result["issues"].append(
                                    f"{message}[StorageClusterRecord][table_id={storage.table_id}]存储集群记录不存在"
                                )
                            else:
                                # 检查是否有当前使用的集群记录
                                current_record = cluster_records.filter(is_current=True).first()
                                if not current_record:
                                    result["issues"].append(f"{message}StorageClusterRecord没有is_current=True的记录")
                                elif current_record.cluster_id != storage.storage_cluster_id:
                                    message_record = f"[StorageClusterRecord] [table_id={storage.table_id},cluster_id={current_record.cluster_id}] "
                                    result["issues"].append(
                                        f"{message_record}当前集群ID与ESStorage的storage_cluster_id不一致，期望: {storage.storage_cluster_id}"
                                    )

                                # 收集集群记录信息
                                for record in cluster_records:
                                    record_detail = {
                                        "table_id": record.table_id,
                                        "cluster_id": record.cluster_id,
                                        "is_current": record.is_current,
                                        "enable_time": record.enable_time.isoformat() if record.enable_time else None,
                                        "disable_time": record.disable_time.isoformat()
                                        if record.disable_time
                                        else None,
                                        "create_time": record.create_time.isoformat() if record.create_time else None,
                                    }
                                    storage_cluster_records.append(record_detail)

                        except Exception as e:
                            result["issues"].append(f"{message}StorageClusterRecord检查异常: {str(e)}")

                except Exception as e:
                    message = f"[ESStorage] [bk_data_id={data_id}] "
                    result["issues"].append(f"{message}ES存储检查异常: {str(e)}")

            result["details"] = {
                "es_storage": {
                    "total_storages": len(es_storage_details),
                    "storage_details": es_storage_details[:10],  # 只显示前10个
                },
                "cluster_info": {
                    "total_clusters": len(cluster_details),
                    "clusters": list(cluster_details.values()),
                },
                "storage_cluster_records": {
                    "total_records": len(storage_cluster_records),
                    "records": storage_cluster_records[:20],  # 只显示前20个
                },
            }

            result["status"] = Status.SUCCESS if not result["issues"] else Status.WARNING

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[ESStorage] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}Elasticsearch存储配置检查异常: {str(e)}")

        return result

    @recode_final_result
    def check_vm_datalink_dependencies(self, cluster_info: BCSClusterInfo) -> dict:
        """检查VM数据链路依赖模型

        V2 链路（老）：通过 AccessVMRecord 直接接入 VM，不经 BkBase
        V4 链路（新）：通过 DataLink + BkBaseResultTable + 3 类 Config 走 BkBase
        判定方式：有 AccessVMRecord 但无 DataLink 即视为 V2 接入，跳过后续 V4 状态检查
        """
        result = {"status": Status.UNKNOWN, "details": {}, "issues": [], "warnings": []}

        def format_output(details: dict) -> list[str]:
            """格式化VM数据链路依赖检查输出"""
            lines = []
            if details:
                vm_record_count = details.get("access_vm_record", {}).get("total_records", 0)
                link_count = details.get("data_link", {}).get("total_links", 0)
                is_federal = details.get("federal_cluster_info", {}).get("is_federal", False)
                lines.append(f"    VM访问记录: {vm_record_count}")
                lines.append(f"    数据链路: {link_count}")
                lines.append(f"    联邦集群: {'是' if is_federal else '否'}")
            return lines

        result["formatter"] = format_output

        access_vm_records = []
        data_links = []

        # 检查是否是联邦代理集群
        is_federal = BcsFederalClusterInfo.objects.filter(
            fed_cluster_id=cluster_info.cluster_id, is_deleted=False
        ).exists()

        try:
            for data_id, data_source in self.data_sources.items():
                # 为每个数据源独立处理，遵循循环内异常隔离原则
                try:
                    # 1. 检查DataSourceResultTable关联
                    ds_rt = DataSourceResultTable.objects.filter(
                        bk_data_id=data_id, bk_tenant_id=self.bk_tenant_id
                    ).first()

                    if not ds_rt:
                        continue

                    # 2. 检查ResultTable配置
                    result_table = ResultTable.objects.filter(
                        table_id=ds_rt.table_id, bk_tenant_id=self.bk_tenant_id
                    ).first()

                    if not result_table:
                        result["issues"].append(
                            f"[DataSourceResultTable] [data_id={data_id}] "
                            f"未找到对应的结果表 [table_id={ds_rt.table_id}]"
                        )
                        continue

                    if result_table.default_storage != ClusterInfo.TYPE_INFLUXDB:
                        continue

                    need_continue = False
                    # 3. 没开启v4数据链路，并且也没开启vm数据链路，需要跳过
                    if (
                        data_source.etl_config not in ENABLE_V4_DATALINK_ETL_CONFIGS
                        and not settings.ENABLE_V2_VM_DATA_LINK
                    ):
                        need_continue = True

                    # 没开启INFLUXDB存储，需要进行vm数据链路检查
                    if not settings.ENABLE_INFLUXDB_STORAGE:
                        need_continue = False

                    # 6. 检查AccessVMRecord（参考apply_data_link流程中创建的记录）
                    vm_record = AccessVMRecord.objects.filter(
                        result_table_id=ds_rt.table_id, bk_tenant_id=self.bk_tenant_id
                    ).first()

                    # 在need_continue为True的状态下，vm_records为空,则跳过
                    if not vm_record and need_continue:
                        continue
                    # 在need_continue为False的状态下，vm_records不存在时，属于异常情况，需要记录异常信息
                    if not vm_record and not need_continue:
                        result["issues"].append(
                            f"[AccessVMRecord] [result_table_id={ds_rt.table_id}] 未找到对应的VM访问记录"
                        )
                        continue
                    # 在need_continue为True的状态下，vm_records存在时，也属于异常情况
                    # 可能之前创建过vm数据链路，所以需要进行vm数据链路检查
                    if vm_record and need_continue:
                        result["warnings"].append(
                            f"[ENABLE_V2_VM_DATA_LINK={settings.ENABLE_V2_VM_DATA_LINK}]"
                            f"[ENABLE_INFLUXDB_STORAGE={settings.ENABLE_INFLUXDB_STORAGE}]"
                            f"当前不支持接入vm数据链路，但存在VM访问记录"
                        )

                    # 收集VM访问记录
                    access_vm_records.append(
                        {
                            "result_table_id": vm_record.result_table_id,
                            "vm_result_table_id": vm_record.vm_result_table_id,
                            "vm_cluster_id": vm_record.vm_cluster_id,
                            "storage_cluster_id": vm_record.storage_cluster_id,
                            "data_type": vm_record.data_type,
                        }
                    )

                    # 优先级1: 检查是否是联邦代理集群
                    if is_federal:
                        data_link_strategy = DataLink.BCS_FEDERAL_PROXY_TIME_SERIES
                    # 优先级2: 根据ETL配置选择策略
                    elif data_source.etl_config == EtlConfigs.BK_EXPORTER.value:
                        data_link_strategy = DataLink.BK_EXPORTER_TIME_SERIES
                    elif data_source.etl_config == EtlConfigs.BK_STANDARD.value:
                        data_link_strategy = DataLink.BK_STANDARD_TIME_SERIES
                    else:
                        # 默认策略
                        data_link_strategy = DataLink.BK_STANDARD_V2_TIME_SERIES

                    # 8. 组装bkbase_data_name（与apply_data_link保持一致）
                    bkbase_data_name = compose_bkdata_data_id_name(
                        data_name=data_source.data_name, strategy=data_link_strategy
                    )

                    # 9. 检查DataLink配置（参考apply_data_link中创建/获取的BkBaseResultTable）
                    data_link = DataLink.objects.filter(
                        bk_tenant_id=data_source.bk_tenant_id,
                        data_link_name=bkbase_data_name,
                        namespace=settings.DEFAULT_VM_DATA_LINK_NAMESPACE,
                        data_link_strategy=data_link_strategy,
                    ).first()

                    if not data_link:
                        # 有 AccessVMRecord 但无 DataLink → V2 老链路接入（直连 VM，不经 BkBase）
                        # 跳过后续 V4 状态检查
                        if vm_record:
                            result["warnings"].append(
                                f"[DataLink] [data_link_name={bkbase_data_name}] "
                                "无 V4 数据链路记录，识别为 V2 链路接入（依赖 AccessVMRecord，不经 BkBase）"
                            )
                        else:
                            result["issues"].append(
                                f"[DataLink] [data_link_name={bkbase_data_name}] "
                                f"[strategy={data_link_strategy}] 未找到对应的数据链路配置"
                            )
                        continue

                    data_links.append(
                        {
                            "data_link_name": data_link.data_link_name,
                            "data_link_strategy": data_link.data_link_strategy,
                        }
                    )

                    # 10. 检查BkBaseResultTable（apply_data_link流程中首先创建的对象）
                    bk_base_result_table = BkBaseResultTable.objects.filter(
                        data_link_name=data_link.data_link_name, bk_tenant_id=self.bk_tenant_id
                    ).first()

                    if not bk_base_result_table:
                        result["issues"].append(
                            f"[BkBaseResultTable] [data_link_name={data_link.data_link_name}] "
                            f"未找到对应的BkBaseResultTable记录"
                        )

                    # 11. 组装bkbase_vmrt_name并检查相关配置（参考compose_configs流程）
                    bkbase_vmrt_name = compose_bkdata_table_id(table_id=ds_rt.table_id, strategy=data_link_strategy)

                    # 12. 检查ResultTableConfig（compose_configs中创建的第一个配置）
                    vm_table_id_ins = ResultTableConfig.objects.filter(
                        name=bkbase_vmrt_name,
                        data_link_name=data_link.data_link_name,
                        namespace=data_link.namespace,
                        bk_tenant_id=self.bk_tenant_id,
                    ).first()

                    if not vm_table_id_ins:
                        result["issues"].append(
                            f"[ResultTableConfig] [name={bkbase_vmrt_name}] "
                            f"[data_link_name={data_link.data_link_name}] 未找到对应的结果表配置"
                        )
                    elif vm_table_id_ins.status != "Ok":
                        result["issues"].append(
                            f"[ResultTableConfig] [name={bkbase_vmrt_name}] 状态异常: {vm_table_id_ins.status}"
                        )

                    # 13. 检查VMStorageBindingConfig（compose_configs中创建的第二个配置）
                    vm_storage_ins = VMStorageBindingConfig.objects.filter(
                        name=bkbase_vmrt_name,
                        data_link_name=data_link.data_link_name,
                        namespace=data_link.namespace,
                        bk_tenant_id=self.bk_tenant_id,
                    ).first()

                    if not vm_storage_ins:
                        result["issues"].append(
                            f"[VMStorageBindingConfig] [name={bkbase_vmrt_name}] "
                            f"[data_link_name={data_link.data_link_name}] 未找到对应的VM存储绑定配置"
                        )
                    elif vm_storage_ins.status != "Ok":
                        result["issues"].append(
                            f"[VMStorageBindingConfig] [name={bkbase_vmrt_name}] 状态异常: {vm_storage_ins.status}"
                        )

                    # 14. 检查DataBusConfig（compose_configs中创建的第三个配置）
                    data_bus_ins = DataBusConfig.objects.filter(
                        name=bkbase_vmrt_name,
                        data_link_name=data_link.data_link_name,
                        namespace=data_link.namespace,
                        bk_tenant_id=self.bk_tenant_id,
                    ).first()

                    if not data_bus_ins:
                        result["issues"].append(
                            f"[DataBusConfig] [name={bkbase_vmrt_name}] "
                            f"[data_link_name={data_link.data_link_name}] 未找到对应的DataBus配置"
                        )
                    elif data_bus_ins.status != "Ok":
                        result["issues"].append(
                            f"[DataBusConfig] [name={bkbase_vmrt_name}] 状态异常: {data_bus_ins.status}"
                        )

                    vm_cluster = ClusterInfo.objects.filter(
                        cluster_id=vm_record.vm_cluster_id, bk_tenant_id=self.bk_tenant_id
                    ).first()
                    if not vm_cluster:
                        result["issues"].append(
                            f"[ClusterInfo] [cluster_id={vm_record.vm_cluster_id}] 未找到对应的vm集群信息"
                        )
                        continue

                    # 注：不调 data_link.compose_configs（写路径函数会打 INFO 日志），
                    # 部署后配置一致性已由上面 ResultTableConfig / VMStorageBindingConfig / DataBusConfig
                    # 的 status=="Ok" 检查覆盖

                except Exception as e:
                    # 遵循循环内异常隔离原则，单个数据源检查失败不影响其他数据源
                    message = f"[DataSource] [bk_data_id={data_id}] "
                    result["issues"].append(f"{message}检查异常: {str(e)}")

            # 设置详细信息
            result["details"] = {
                "access_vm_record": {
                    "total_records": len(access_vm_records),
                    "records": access_vm_records,
                },
                "data_link": {
                    "total_links": len(data_links),
                    "links": data_links,
                },
                "federal_cluster_info": {
                    "is_federal": is_federal,
                },
            }

            # 设置状态
            if result["issues"]:
                result["status"] = Status.WARNING
            else:
                result["status"] = Status.SUCCESS

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[VMDataLink] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}VM数据链路依赖检查异常: {str(e)}")

        return result

    @recode_final_result
    def check_vm_publish_space_router(self, cluster_info: BCSClusterInfo) -> dict:
        """检查VM推送并发布空间路由功能"""
        result = {"status": Status.UNKNOWN, "details": {}, "issues": []}

        def format_output(details: dict) -> list[str]:
            """格式化VM空间路由检查输出"""
            lines = []
            if details:
                router_status = details.get("router_status", {})
                total_checked = len(router_status)
                missing_space = sum(
                    1 for v in router_status.values() if isinstance(v, dict) and not v.get("space_router_exists")
                )
                lines.append(f"    数据源数量: {total_checked}")
                lines.append(f"    空间路由缺失: {missing_space}/{total_checked}")
            return lines

        result["formatter"] = format_output

        try:
            from django.conf import settings

            from metadata.models.space.constants import (
                SPACE_TO_RESULT_TABLE_KEY,
            )
            from metadata.utils.redis_tools import RedisTools

            router_status = {}

            for data_id, datasource in self.data_sources.items():
                try:
                    is_v4_datalink_etl_config = datasource.etl_config in ENABLE_V4_DATALINK_ETL_CONFIGS
                    if (
                        is_v4_datalink_etl_config and settings.ENABLE_V2_VM_DATA_LINK
                    ) or not settings.ENABLE_INFLUXDB_STORAGE:
                        pass
                    else:
                        continue

                    # 获取空间信息
                    space_info = self._get_space_info_by_biz_id(self.bk_biz_id, datasource)
                    space_type_id = space_info.get("space_type_id", datasource.space_type_id)
                    space_uid = space_info.get("space_uid", datasource.space_uid)

                    # 构建多租户模式下的Redis键
                    if settings.ENABLE_MULTI_TENANT_MODE:
                        space_redis_key = f"{space_type_id}__{space_uid}|{self.bk_tenant_id}"
                    else:
                        space_redis_key = f"{space_type_id}__{space_uid}"

                    # 检查空间路由是否存在
                    space_router_values = RedisTools.hmget(SPACE_TO_RESULT_TABLE_KEY, [space_redis_key])
                    space_router_exists = bool(space_router_values and space_router_values[0])

                    router_status[data_id] = {
                        "space_redis_key": space_redis_key,
                        "space_router_exists": space_router_exists,
                    }

                    # 记录缺失项
                    if not space_router_exists:
                        message = f"[Redis] [bk_data_id={data_id},space_redis_key={space_redis_key}] "
                        result["issues"].append(
                            f"{message}缺少空间路由配置, key:{SPACE_TO_RESULT_TABLE_KEY}/{space_redis_key}"
                        )

                except Exception as e:
                    router_status[data_id] = {"error": str(e)}
                    message = f"[DataSource] [bk_data_id={data_id}] "
                    result["issues"].append(f"{message}空间路由检查异常: {str(e)}")

            result["details"] = {"router_status": router_status, "total_datasources": len(self.data_sources)}
            result["status"] = Status.SUCCESS if not result["issues"] else Status.WARNING

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[VMPublishSpaceRouter] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}VM空间路由检查异常: {str(e)}")

        return result

    @recode_final_result
    def check_log_datalink(self, cluster_info: BCSClusterInfo) -> dict:
        """检查日志V4数据链路配置

        验证集群日志数据链路配置是否正确，包括：
        1. V4数据链路启用配置
        2. 数据链路配置项完整性
        3. 存储集群(ES/Doris)配置有效性
        4. 数据源和结果表关联正常
        5. 计算平台链路配置正确性
        """
        result = {"status": Status.UNKNOWN, "details": {}, "issues": [], "warnings": []}

        def format_output(details: dict) -> list[str]:
            """格式化日志数据链路检查输出"""
            lines = []
            if details:
                # 全集群未启用 V4 时仅显示提示
                if details.get("v4_enabled_any") is False and details.get("note"):
                    lines.append(f"    {details['note']}")
                    return lines

                log_datasources = details.get("log_datasources", [])
                v4_enabled_count = sum(1 for ds in log_datasources if ds.get("v4_enabled"))
                lines.append(f"    日志数据源: {len(log_datasources)}个")
                lines.append(f"    V4链路启用: {v4_enabled_count}/{len(log_datasources)}")

                storage_check = details.get("storage_check", {})
                if storage_check:
                    es_ok = sum(1 for v in storage_check.values() if v.get("es_storage_exists"))
                    doris_ok = sum(1 for v in storage_check.values() if v.get("doris_storage_exists"))
                    lines.append(f"    ES存储配置: {es_ok}个")
                    lines.append(f"    Doris存储配置: {doris_ok}个")
            return lines

        result["formatter"] = format_output

        try:
            # 预检：本集群任一 data_id 是否启用了 V4 日志链路？
            # 全部未启用（V2 链路场景）→ 该 check 没有诊断价值，直接 SUCCESS + 提示并跳过详细遍历
            data_ids = list(self.data_sources.keys())
            any_v4_enabled = ResultTableOption.objects.filter(
                bk_tenant_id=self.bk_tenant_id,
                table_id__in=DataSourceResultTable.objects.filter(
                    bk_data_id__in=data_ids, bk_tenant_id=self.bk_tenant_id
                ).values_list("table_id", flat=True),
                name=ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK,
                value="true",
            ).exists()

            if not any_v4_enabled:
                result["status"] = Status.SUCCESS
                result["details"] = {
                    "log_datasources": [],
                    "v4_enabled_any": False,
                    "note": "本集群未启用 V4 日志数据链路，跳过详细检查（V2 链路或不需要日志采集）",
                }
                return result

            log_datasources = []
            storage_check = {}
            datalink_check = {}

            # 遍历所有数据源，检查日志相关配置
            for data_id, datasource in self.data_sources.items():
                try:
                    # 获取数据源关联的结果表
                    dsrt = DataSourceResultTable.objects.filter(
                        bk_data_id=data_id, bk_tenant_id=self.bk_tenant_id
                    ).last()

                    if not dsrt:
                        continue

                    table_id = dsrt.table_id

                    # 获取结果表信息
                    rt = ResultTable.objects.filter(bk_tenant_id=self.bk_tenant_id, table_id=table_id).first()

                    if not rt:
                        message = f"[ResultTable] [bk_data_id={data_id},table_id={table_id}] "
                        result["issues"].append(f"{message}结果表不存在")
                        continue

                    if rt.default_storage != ClusterInfo.TYPE_ES:
                        continue

                    # 检查是否启用V4数据链路
                    enabled_v4_option = ResultTableOption.objects.filter(
                        bk_tenant_id=self.bk_tenant_id,
                        table_id=table_id,
                        name=ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK,
                    ).first()

                    v4_enabled = False
                    if enabled_v4_option:
                        try:
                            v4_enabled = enabled_v4_option.to_json().get(
                                ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK, False
                            )
                        except Exception as e:
                            message = f"[ResultTableOption] [bk_data_id={data_id},table_id={table_id}] "
                            result["issues"].append(f"{message}V4链路启用配置解析失败: {str(e)}")

                    log_ds_info = {
                        "data_id": data_id,
                        "table_id": table_id,
                        "v4_enabled": v4_enabled,
                    }

                    # 如果启用了V4链路，进行详细检查
                    if v4_enabled:
                        # 检查V4数据链路配置项
                        datalink_option = ResultTableOption.objects.filter(
                            bk_tenant_id=self.bk_tenant_id,
                            table_id=table_id,
                            name=ResultTableOption.OPTION_V4_LOG_DATA_LINK,
                        ).first()

                        if not datalink_option:
                            message = f"[ResultTableOption] [bk_data_id={data_id},table_id={table_id}] "
                            result["issues"].append(f"{message}启用了V4链路但缺少数据链路配置项")
                            log_ds_info["config_exists"] = False
                        else:
                            log_ds_info["config_exists"] = True

                            # 校验配置格式
                            try:
                                datalink_config = LogV4DataLinkOption(**json.loads(datalink_option.value))
                                log_ds_info["config_valid"] = True

                                # 检查存储配置
                                es_storage_exists = False
                                doris_storage_exists = False

                                if datalink_config.es_storage_config:
                                    es_storage = ESStorage.objects.filter(
                                        bk_tenant_id=self.bk_tenant_id, table_id=table_id
                                    ).first()

                                    if es_storage:
                                        es_storage_exists = True
                                        storage_check[f"{data_id}_es"] = {
                                            "table_id": table_id,
                                            "storage_cluster_id": es_storage.storage_cluster_id,
                                            "es_storage_exists": True,
                                        }
                                    else:
                                        message = f"[ESStorage] [bk_data_id={data_id},table_id={table_id}] "
                                        result["issues"].append(f"{message}配置了ES存储但ES存储记录不存在")
                                        storage_check[f"{data_id}_es"] = {
                                            "table_id": table_id,
                                            "es_storage_exists": False,
                                            "error": "ES存储记录不存在",
                                        }

                                if datalink_config.doris_storage_config:
                                    doris_storage = DorisStorage.objects.filter(
                                        bk_tenant_id=self.bk_tenant_id, table_id=table_id
                                    ).first()

                                    if doris_storage:
                                        doris_storage_exists = True
                                        storage_check[f"{data_id}_doris"] = {
                                            "table_id": table_id,
                                            "storage_cluster_id": doris_storage.storage_cluster_id,
                                            "doris_storage_exists": True,
                                        }
                                    else:
                                        message = f"[DorisStorage] [bk_data_id={data_id},table_id={table_id}] "
                                        result["issues"].append(f"{message}配置了Doris存储但Doris存储记录不存在")
                                        storage_check[f"{data_id}_doris"] = {
                                            "table_id": table_id,
                                            "doris_storage_exists": False,
                                            "error": "Doris存储记录不存在",
                                        }

                                log_ds_info["es_storage_configured"] = bool(datalink_config.es_storage_config)
                                log_ds_info["doris_storage_configured"] = bool(datalink_config.doris_storage_config)
                                log_ds_info["es_storage_exists"] = es_storage_exists
                                log_ds_info["doris_storage_exists"] = doris_storage_exists

                            except (json.JSONDecodeError, TypeError) as e:
                                message = f"[ResultTableOption] [bk_data_id={data_id},table_id={table_id}] "
                                result["issues"].append(f"{message}数据链路配置JSON解析失败: {str(e)}")
                                log_ds_info["config_valid"] = False
                                log_ds_info["error"] = f"JSON解析失败: {str(e)}"
                            except Exception as e:
                                message = f"[ResultTableOption] [bk_data_id={data_id},table_id={table_id}] "
                                result["issues"].append(f"{message}数据链路配置验证失败: {str(e)}")
                                log_ds_info["config_valid"] = False
                                log_ds_info["error"] = f"配置验证失败: {str(e)}"

                        # 检查计算平台链路配置
                        bkbase_rt = BkBaseResultTable.objects.filter(
                            bk_tenant_id=self.bk_tenant_id, monitor_table_id=table_id
                        ).first()

                        if bkbase_rt:
                            # 检查DataLink是否存在
                            datalink = DataLink.objects.filter(
                                bk_tenant_id=self.bk_tenant_id,
                                namespace="bklog",
                                data_link_strategy=DataLink.BK_LOG,
                            ).first()

                            if datalink:
                                datalink_check[data_id] = {
                                    "table_id": table_id,
                                    "data_link_name": bkbase_rt.data_link_name,
                                    "datalink_exists": True,
                                    "data_link_strategy": datalink.data_link_strategy,
                                }
                            else:
                                message = f"[DataLink] [bk_data_id={data_id},namespace=bklog,data_link_name={bkbase_rt.data_link_name}] "
                                result["issues"].append(f"{message}计算平台结果表存在但DataLink不存在")
                                datalink_check[data_id] = {
                                    "table_id": table_id,
                                    "data_link_name": bkbase_rt.data_link_name,
                                    "datalink_exists": False,
                                }
                        else:
                            # V4链路应该有BkBaseResultTable记录
                            message = f"[BkBaseResultTable] [bk_data_id={data_id},table_id={table_id}] "
                            result["issues"].append(f"{message}启用了V4链路但缺少计算平台结果表记录")
                            datalink_check[data_id] = {
                                "table_id": table_id,
                                "bkbase_rt_exists": False,
                            }

                        # 检查数据源created_from字段
                        if datasource.created_from != DataIdCreatedFromSystem.BKDATA.value:
                            message = f"[DataSource] [bk_data_id={data_id}] "
                            result["issues"].append(
                                f"{message}启用了V4链路但created_from不是BKDATA: {datasource.created_from}"
                            )
                            log_ds_info["created_from_correct"] = False
                        else:
                            log_ds_info["created_from_correct"] = True

                    log_datasources.append(log_ds_info)

                except Exception as e:
                    message = f"[DataSource] [bk_data_id={data_id}] "
                    result["issues"].append(f"{message}日志链路检查异常: {str(e)}")

            result["details"] = {
                "log_datasources": log_datasources,
                "storage_check": storage_check,
                "datalink_check": datalink_check,
            }

            # 注：不再对"V4 链路未启用"输出 warning ——
            # V4 / V2 由用户主动选择，未启用 V4 是合法配置，并非"问题"。
            # format_output 已经显示 "V4链路启用: X/Y" 计数信息，避免重复噪音。

            result["status"] = Status.SUCCESS if not result["issues"] else Status.WARNING

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[LogDataLink] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}日志V4数据链路检查异常: {str(e)}")

        return result

    @recode_final_result
    def check_mq_cluster(self, cluster_info: BCSClusterInfo):
        """
        检查mq集群状态
        :param cluster_info: BCS集群信息
        :return: 检查结果
        """
        result = {"status": Status.UNKNOWN, "details": {}, "issues": [], "warnings": []}
        issues = set()

        def format_output(details: dict) -> list[str]:
            """格式化MQ集群检查输出"""
            lines = []
            if details:
                configured_count = len(details)
                lines.append(f"    数据源配置: {configured_count}个")

                error_count = sum(1 for detail in details.values() if detail.get("issues"))
                if error_count > 0:
                    lines.append(f"    异常配置: {error_count}个")

                for data_id, detail in list(details.items()):  # 只显示前3个详情
                    if isinstance(detail, dict):
                        lines.append(f"    数据源data_id`{data_id}`: 集群ID {detail.get('mq_cluster_id', 'N/A')}")
                        if detail.get("mq_cluster_type"):
                            lines.append(f"    集群类型mq_cluster_type: {detail['mq_cluster_type']}")
            return lines

        result["formatter"] = format_output

        try:
            for data_id, data_source in self.data_sources.items():
                mq_cluster_id = data_source.mq_cluster_id
                mq_config_id = data_source.mq_config_id
                details = result["details"].setdefault(data_id, {})

                mq_cluster = ClusterInfo.objects.filter(
                    cluster_id=mq_cluster_id, bk_tenant_id=self.bk_tenant_id
                ).first()
                details.update(
                    {
                        "mq_cluster_id": mq_cluster_id,
                    }
                )

                if not mq_cluster:
                    message = f"[ClusterInfo] [mq_cluster_id={mq_cluster_id}] "
                    error_message = f"{message}MQ集群未找到"
                    issues.add(error_message)
                    details.setdefault("issues", []).append(error_message)
                    continue

                details.update(
                    {
                        "mq_cluster_type": mq_cluster.cluster_type,
                    }
                )
                if mq_cluster.cluster_type not in data_source.MQ_CONFIG_DICT:
                    message = f"[ClusterInfo] [mq_cluster_id={mq_cluster_id},cluster_type={mq_cluster.cluster_type}] "
                    error_message = f"{message}MQ集群类型未找到"
                    issues.add(error_message)
                    details.setdefault("issues", []).append(error_message)
                    continue

                mq_config = (
                    data_source.MQ_CONFIG_DICT[mq_cluster.cluster_type].objects.filter(bk_data_id=data_id).first()
                )

                details.update(
                    {
                        "mq_config_id": mq_config_id,
                    }
                )
                if not mq_config:
                    message = f"[MQConfig] [mq_config_id={mq_config_id},bk_data_id={data_id}] "
                    error_message = f"{message}MQ配置未找到"
                    issues.add(error_message)
                    details.setdefault("issues", []).append(error_message)
                    continue

                # 如果要刷新consul和gse，mq_cluster必须已经初始化了
                if data_source.can_refresh_consul_and_gse() and mq_cluster.gse_stream_to_id == -1:
                    message = f"[ClusterInfo] [mq_cluster_id={mq_cluster_id},bk_data_id={data_id}] "
                    error_message = f"{message}消息队列未初始化，请联系管理员处理"
                    issues.add(error_message)
                    details.setdefault("issues", []).append(error_message)

                try:
                    params = {
                        "condition": {"plat_name": config.DEFAULT_GSE_API_PLAT_NAME, "channel_id": data_id},
                        "operation": {"operator_name": settings.COMMON_USERNAME},
                    }
                    details.update({"gse_route_query_params": params})
                    route_config = api.gse.query_route(**params)
                    if not route_config:
                        message = f"[ClusterInfo] [mq_cluster_id={mq_cluster_id},bk_data_id={data_id}] "
                        error_message = f"{message}[api.gse.query_route] 未查询到GSE路由配置"
                        issues.add(error_message)
                        details.setdefault("issues", []).append(error_message)
                        continue

                    # 查找 channel_id 下 stream_to_id 匹配的路由条目
                    # 路由名称前缀可能因平台配置不同而存在差异（如 bkmonitor/tgdp），
                    # 不以名称作为匹配键，只校验 stream_to_id 和 kafka topic 是否一致
                    expected_stream_to = data_source.gse_route_config["stream_to"]
                    gse_stream_to = None
                    for route_info in route_config:
                        if gse_stream_to:
                            break
                        for stream_to_info in route_info.get("route", []):
                            st = stream_to_info.get("stream_to", {})
                            if st.get("stream_to_id") == expected_stream_to["stream_to_id"]:
                                gse_stream_to = st
                                break

                    if gse_stream_to is None:
                        message = f"[ClusterInfo] [mq_cluster_id={mq_cluster_id},bk_data_id={data_id}] "
                        error_message = f"{message}[api.gse.query_route] GSE未找到匹配的stream_to_id={expected_stream_to['stream_to_id']}"
                        issues.add(error_message)
                        details.setdefault("issues", []).append(error_message)
                    elif hash_util.object_md5(gse_stream_to) != hash_util.object_md5(expected_stream_to):
                        message = f"[ClusterInfo] [mq_cluster_id={mq_cluster_id},bk_data_id={data_id}] "
                        error_message = (
                            f"{message}[api.gse.query_route] GSE路由配置不一致: "
                            f"期望={expected_stream_to}, 实际={gse_stream_to}"
                        )
                        issues.add(error_message)
                        details.setdefault("issues", []).append(error_message)

                except Exception as e:
                    message = f"[ClusterInfo] [mq_cluster_id={mq_cluster_id},bk_data_id={data_id}] "
                    error_message = f"{message}[api.gse.query_route] 查询GSE路由失败: {str(e)}"
                    issues.add(error_message)
                    details.setdefault("issues", []).append(error_message)
                    if config.is_built_in_data_id(data_id):
                        warning_msg = f"{message}[api.gse.query_route]查询GSE路由失败: {str(e)},{data_id} 是内置数据源"
                        details.setdefault("warnings", []).append(warning_msg)
                        result["warnings"].append(warning_msg)

            if not issues:
                result["status"] = Status.SUCCESS
            else:
                result["status"] = Status.ERROR

            result["issues"] = list(issues)
        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[ClusterInfo] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}MQ集群检查异常: {str(e)}")

        return result

    @recode_final_result
    def check_custom_groups_integrity(self, cluster_info: BCSClusterInfo) -> dict:
        """检查TimeSeriesGroup和EventGroup数据完整性

        必需 vs 可选：
        - EventGroup（关联 K8sEventDataID）：**必需**。
          transfer 落 ES 时依赖 event_group_id 作为 index 区分，缺失直接影响事件采集 → issue
        - TimeSeriesGroup（关联 CustomMetricDataID）：**可选**。
          仅影响 monitor-web 的指标/维度发现能力，不影响 transfer 落库 → warning
        """
        result = {"status": Status.UNKNOWN, "details": {}, "issues": [], "warnings": []}

        def format_output(details: dict) -> list[str]:
            """格式化自定义组检查输出"""
            lines = []
            if details:
                ts_info = details.get("time_series_group", {})
                event_info = details.get("event_group", {})

                if ts_info.get("exists"):
                    lines.append("    TimeSeriesGroup: 存在")
                    lines.append(f"      组ID: {ts_info.get('group_id')}")
                    lines.append(f"      组名: {ts_info.get('group_name')}")
                else:
                    lines.append("    TimeSeriesGroup: 不存在")

                if event_info.get("exists"):
                    lines.append("    EventGroup: 存在")
                    lines.append(f"      组ID: {event_info.get('group_id')}")
                    lines.append(f"      组名: {event_info.get('group_name')}")
                else:
                    lines.append("    EventGroup: 不存在")
            return lines

        result["formatter"] = format_output

        try:
            # 1. 检查TimeSeriesGroup（自定义指标）
            custom_metric_data_id = cluster_info.CustomMetricDataID
            if custom_metric_data_id and custom_metric_data_id != 0:
                ts_group = TimeSeriesGroup.objects.filter(
                    bk_data_id=custom_metric_data_id, bk_tenant_id=self.bk_tenant_id
                ).first()

                if ts_group:
                    result["details"]["time_series_group"] = {
                        "exists": True,
                        "group_id": ts_group.time_series_group_id,
                        "group_name": ts_group.time_series_group_name,
                        "table_id": ts_group.table_id,
                        "is_enable": ts_group.is_enable,
                        "data_label": ts_group.data_label,
                    }

                    # 检查TimeSeriesGroup是否启用
                    if not ts_group.is_enable:
                        message = f"[TimeSeriesGroup] [time_series_group_id={ts_group.time_series_group_id},bk_data_id={custom_metric_data_id}] "
                        result["warnings"].append(f"{message}自定义指标组未启用")
                else:
                    # TimeSeriesGroup 缺失不影响 transfer 落库，仅影响指标元数据发现 → warning
                    result["details"]["time_series_group"] = {"exists": False}
                    message = f"[TimeSeriesGroup] [bk_data_id={custom_metric_data_id}] "
                    result["warnings"].append(f"{message}自定义指标组不存在（不影响数据落库，仅影响指标元数据浏览）")
            else:
                result["details"]["time_series_group"] = {"exists": False, "data_id_not_configured": True}
                result["warnings"].append("[TimeSeriesGroup] CustomMetricDataID未配置")

            # 2. 检查EventGroup（自定义事件）
            k8s_event_data_id = cluster_info.K8sEventDataID
            if k8s_event_data_id and k8s_event_data_id != 0:
                event_group = EventGroup.objects.filter(
                    bk_data_id=k8s_event_data_id, bk_tenant_id=self.bk_tenant_id
                ).first()

                if event_group:
                    result["details"]["event_group"] = {
                        "exists": True,
                        "group_id": event_group.event_group_id,
                        "group_name": event_group.event_group_name,
                        "table_id": event_group.table_id,
                        "is_enable": event_group.is_enable,
                        "status": event_group.status,
                        "data_label": event_group.data_label,
                    }

                    # 检查EventGroup是否启用
                    if not event_group.is_enable:
                        message = f"[EventGroup] [event_group_id={event_group.event_group_id},bk_data_id={k8s_event_data_id}] "
                        result["warnings"].append(f"{message}自定义事件组未启用")

                else:
                    result["details"]["event_group"] = {"exists": False}
                    message = f"[EventGroup] [bk_data_id={k8s_event_data_id}] "
                    result["issues"].append(f"{message}自定义事件组不存在")
            else:
                result["details"]["event_group"] = {"exists": False, "data_id_not_configured": True}
                result["warnings"].append("[EventGroup] K8sEventDataID未配置")

            # 确定整体状态
            if not result["issues"]:
                result["status"] = Status.SUCCESS if not result["warnings"] else Status.WARNING
            else:
                result["status"] = Status.WARNING

        except Exception as e:
            result["status"] = Status.ERROR
            message = f"[CustomGroups] [cluster_id={cluster_info.cluster_id}] "
            result["issues"].append(f"{message}自定义组检查异常: {str(e)}")

        return result

    def is_federation_cluster(self, cluster_info: BCSClusterInfo) -> bool:
        """判断集群是否参与联邦拓扑（任意角色：fed / host / sub）

        覆盖所有角色，确保嵌套联邦下作为 host 或 sub 的集群也会触发 I2 联邦检查
        """
        try:
            from django.db.models import Q

            return BcsFederalClusterInfo.objects.filter(
                Q(fed_cluster_id=cluster_info.cluster_id)
                | Q(host_cluster_id=cluster_info.cluster_id)
                | Q(sub_cluster_id=cluster_info.cluster_id),
                is_deleted=False,
            ).exists()
        except Exception:
            return False

    def _discover_federation_topology(self, current_cluster_id: str) -> list[str]:
        """递归发现当前集群所在的联邦拓扑（含嵌套），返回涉及的 fed_cluster_id 列表

        遍历方式：从当前集群直接参与的联邦开始，每个 fed 本身可能又是上层 fed 的 sub/host，
        持续向上爬，直到没有新的联邦关系出现
        """
        from django.db.models import Q

        # 第一轮：直接关联的 fed_cluster_id
        related_fed_ids = set(
            BcsFederalClusterInfo.objects.filter(
                Q(fed_cluster_id=current_cluster_id)
                | Q(host_cluster_id=current_cluster_id)
                | Q(sub_cluster_id=current_cluster_id),
                is_deleted=False,
            ).values_list("fed_cluster_id", flat=True)
        )

        # 嵌套发现：每个 fed_cluster_id 自身是否也是上层 fed 的 sub/host
        visited: set[str] = set()
        to_visit = list(related_fed_ids)
        while to_visit:
            fed_id = to_visit.pop()
            if fed_id in visited:
                continue
            visited.add(fed_id)

            upper_fed_ids = BcsFederalClusterInfo.objects.filter(
                Q(sub_cluster_id=fed_id) | Q(host_cluster_id=fed_id),
                is_deleted=False,
            ).values_list("fed_cluster_id", flat=True)
            for upper_fed_id in upper_fed_ids:
                if upper_fed_id not in visited:
                    to_visit.append(upper_fed_id)

        return sorted(visited)

    def _render_federation_topology(self, current_cluster_id: str) -> list[str]:
        """渲染当前集群所在的联邦拓扑树（含嵌套）"""
        fed_ids = self._discover_federation_topology(current_cluster_id)
        if not fed_ids:
            return []

        lines = ["    联邦拓扑:"]
        for fed_id in fed_ids:
            recs = list(BcsFederalClusterInfo.objects.filter(fed_cluster_id=fed_id, is_deleted=False))
            if not recs:
                continue

            fed_marker = "  ← current" if fed_id == current_cluster_id else ""
            lines.append(f"      联邦 (fed={fed_id}){fed_marker}")

            # host_cluster_id 通常每个联邦只有一个（同一 fed 下所有记录共享 host）
            host_ids = sorted({r.host_cluster_id for r in recs})
            for hid in host_ids:
                marker = "  ← current" if hid == current_cluster_id else ""
                lines.append(f"        ├── host: {hid}{marker}")

            # sub_cluster_id 列表，每个对应不同的 ns 分组
            sub_records = sorted(recs, key=lambda r: r.sub_cluster_id)
            for i, r in enumerate(sub_records):
                is_last = i == len(sub_records) - 1
                prefix = "└──" if is_last else "├──"
                marker = "  ← current" if r.sub_cluster_id == current_cluster_id else ""
                ns_str = ",".join(r.fed_namespaces or []) if r.fed_namespaces else "(无)"
                lines.append(f"        {prefix} sub: {r.sub_cluster_id} ns=[{ns_str}]{marker}")

        return lines

    def output_summary_report(self, check_result: dict):
        """输出汇总报告（详细结果已在检查过程中输出）"""
        status = check_result["status"]

        # 输出分隔线
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("检测完成 - 汇总报告"))
        self.stdout.write("=" * 60)

        # 输出基本信息
        self.stdout.write(f"执行时间: {check_result['execution_time']}秒")

        # 输出整体状态
        status_style = self.get_status_style(status)
        self.stdout.write(f"\n整体状态: {status_style(status)}")

        # 输出错误和警告汇总
        if check_result.get("errors"):
            self.stdout.write(f"\n{self.style.ERROR('错误信息:')}（共{len(check_result['errors'])}条）")
            for error in check_result["errors"]:
                self.stdout.write(f"  • {self.style.ERROR(error)}")

        if check_result.get("warnings"):
            self.stdout.write(f"\n{self.style.WARNING('警告信息:')}（共{len(check_result['warnings'])}条）")
            for warning in check_result["warnings"]:
                self.stdout.write(f"  • {self.style.WARNING(warning)}")

        if check_result.get("issues"):
            self.stdout.write(f"\n{self.style.WARNING('问题信息:')}（共{len(check_result['issues'])}条）")
            for issue in check_result["issues"]:
                self.stdout.write(f"  • {self.style.WARNING(issue)}")

        # 输出结束信息
        self.stdout.write("\n" + "=" * 60)
        if status == Status.SUCCESS:
            self.stdout.write(self.style.SUCCESS("✅ 集群状态检测通过！"))
        elif status == Status.WARNING:
            self.stdout.write(self.style.WARNING("⚠️  集群状态检测完成，但存在警告项。"))
        elif status == Status.ERROR:
            self.stdout.write(self.style.ERROR("❌ 集群状态检测发现错误！"))
        elif status == Status.NOT_FOUND:
            self.stdout.write(self.style.ERROR("❌ 集群未找到！"))
        else:
            self.stdout.write(self.style.NOTICE("❓ 集群状态未知。"))
        self.stdout.write("=" * 60)

    def get_status_style(self, status: str):
        """根据状态获取样式函数"""
        status_styles = {
            Status.SUCCESS: self.style.SUCCESS,
            Status.WARNING: self.style.WARNING,
            Status.ERROR: self.style.ERROR,
            Status.NOT_FOUND: self.style.ERROR,
            Status.UNKNOWN: self.style.NOTICE,
        }
        return status_styles.get(status, self.style.NOTICE)
