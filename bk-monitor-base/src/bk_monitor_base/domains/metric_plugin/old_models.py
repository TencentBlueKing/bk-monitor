import base64
import datetime
import json
import logging
from pathlib import Path
from typing import Any, cast, final

import yaml
from bkcrypto.contrib.django.fields import SymmetricTextField
from django.db import models, transaction
from typing_extensions import override

from bk_monitor_base.config.storage import StorageName
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID, OLD_MONITOR_SAAS_DB_NAME
from bk_monitor_base.infras.db_models.manger import OldModelManager
from bk_monitor_base.infras.storage import get_storage_func

logger = logging.getLogger(__name__)


@final
class PluginType:
    EXPORTER = "Exporter"
    SCRIPT = "Script"
    JMX = "JMX"
    DATADOG = "DataDog"
    PUSHGATEWAY = "Pushgateway"
    BUILT_IN = "Built-In"
    LOG = "Log"
    PROCESS = "Process"
    SNMP_TRAP = "SNMP_Trap"
    SNMP = "SNMP"
    K8S = "K8S"


@final
class CollectorPluginMeta(models.Model):
    """
    采集插件源信息
    """

    PluginType = PluginType
    PLUGIN_TYPE_CHOICES = (
        (PluginType.EXPORTER, PluginType.EXPORTER),
        (PluginType.SCRIPT, PluginType.SCRIPT),
        (PluginType.JMX, PluginType.JMX),
        (PluginType.DATADOG, PluginType.DATADOG),
        (PluginType.PUSHGATEWAY, "BK-Pull"),
        (PluginType.BUILT_IN, "BK-Monitor"),
        (PluginType.LOG, PluginType.LOG),
        (PluginType.PROCESS, "Process"),
        (PluginType.SNMP_TRAP, PluginType.SNMP_TRAP),
        (PluginType.SNMP, PluginType.SNMP),
        (PluginType.K8S, PluginType.K8S),
    )

    VIRTUAL_PLUGIN_TYPE = [PluginType.LOG, PluginType.PROCESS, PluginType.SNMP_TRAP, PluginType.K8S]

    id = models.BigAutoField("ID", primary_key=True)
    bk_tenant_id = models.CharField("租户ID", max_length=128, default=DEFAULT_TENANT_ID)
    plugin_id = models.CharField("插件ID", max_length=64)
    bk_biz_id = models.IntegerField("业务ID", default=0, blank=True, db_index=True)
    bk_supplier_id = models.IntegerField("开发商ID", default=0, blank=True)
    plugin_type = models.CharField("插件类型", max_length=32, choices=PLUGIN_TYPE_CHOICES, db_index=True)
    tag = models.CharField("插件标签", max_length=64, default="")
    label = models.CharField("二级标签", max_length=64, default="")
    is_internal = models.BooleanField("是否内置", default=False)

    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    create_user = models.CharField("创建人", max_length=32, blank=True)
    update_time = models.DateTimeField("修改时间", auto_now=True)
    update_user = models.CharField("修改人", max_length=32, blank=True)
    is_deleted = models.BooleanField("是否删除", default=False)

    objects = OldModelManager(default_db_name=OLD_MONITOR_SAAS_DB_NAME)

    @override
    def __str__(self):
        return f"{self.plugin_type}-{self.plugin_id}"

    @final
    class Meta:
        db_table = "monitor_web_collectorpluginmeta"
        unique_together = ["bk_tenant_id", "plugin_id"]
        managed = False
        abstract = False


@final
class CollectorPluginInfo(models.Model):
    """
    采集器插件信息
    """

    plugin_display_name = models.CharField("插件别名", max_length=64, default="")
    # 原本是jsonfield
    metric_json = models.TextField("指标配置", default="[]")
    # 原本是jsonfield
    description_md = models.TextField("插件描述，markdown文本", default="")
    logo = models.ImageField("logo文件", null=True, storage=get_storage_func(StorageName.BKMONITOR))
    enable_field_blacklist = models.BooleanField("是否开启黑名单", default=False)

    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    create_user = models.CharField("创建人", max_length=32, blank=True)
    update_time = models.DateTimeField("修改时间", auto_now=True)
    update_user = models.CharField("修改人", max_length=32, blank=True)
    is_deleted = models.BooleanField("是否删除", default=False)

    objects = OldModelManager(default_db_name=OLD_MONITOR_SAAS_DB_NAME)

    @override
    def __str__(self):
        return f"{self.plugin_display_name}"

    @final
    class Meta:
        db_table = "monitor_web_collectorplugininfo"
        managed = False


@final
class CollectorPluginConfig(models.Model):
    """
    采集器插件功能信息
    """

    config_json = models.TextField("参数配置", default="[]")
    collector_json = models.TextField("采集器配置", default="[]")
    is_support_remote = models.BooleanField("是否支持远程采集", default=False)

    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    create_user = models.CharField("创建人", max_length=32, blank=True)
    update_time = models.DateTimeField("修改时间", auto_now=True)
    update_user = models.CharField("修改人", max_length=32, blank=True)
    is_deleted = models.BooleanField("是否删除", default=False)

    objects = OldModelManager(default_db_name=OLD_MONITOR_SAAS_DB_NAME)

    @override
    def __str__(self):
        return f"{self.__class__.__name__}<{self.pk}>"

    @final
    class Meta:
        db_table = "monitor_web_collectorpluginconfig"
        managed = False


@final
class PluginVersionHistory(models.Model):
    """
    采集插件版本历史
    """

    @final
    class Stage:
        """
        插件状态
        """

        UNREGISTER = "unregister"
        DEBUG = "debug"
        RELEASE = "release"

    STAGE_CHOICES = (
        (Stage.UNREGISTER, "未注册版本"),
        (Stage.DEBUG, "调试版本"),
        (Stage.RELEASE, "发布版本"),
    )

    bk_tenant_id = models.CharField("租户ID", max_length=128, default=DEFAULT_TENANT_ID)
    plugin_id = models.CharField("插件ID", max_length=64)
    stage = models.CharField("版本阶段", choices=STAGE_CHOICES, default=Stage.UNREGISTER, max_length=30)
    config = models.ForeignKey(
        CollectorPluginConfig, verbose_name="插件功能配置", related_name="version", on_delete=models.CASCADE
    )
    info = models.ForeignKey(
        CollectorPluginInfo, verbose_name="插件信息配置", related_name="version", on_delete=models.CASCADE
    )
    config_version = models.IntegerField("插件版本", default=1)
    info_version = models.IntegerField("插件信息版本", default=1)
    # 原本是yamlfield
    signature = models.TextField("版本签名", default="")
    version_log = models.CharField("版本修改日志", max_length=100, default="")
    is_packaged = models.BooleanField("是否已上传到节点管理", default=False)

    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    create_user = models.CharField("创建人", max_length=32, blank=True)
    update_time = models.DateTimeField("修改时间", auto_now=True)
    update_user = models.CharField("修改人", max_length=32, blank=True)
    is_deleted = models.BooleanField("是否删除", default=False)

    objects = OldModelManager(default_db_name=OLD_MONITOR_SAAS_DB_NAME)

    @final
    class Meta:
        db_table = "monitor_web_pluginversionhistory"
        ordering = ["config_version", "info_version", "create_time", "update_time"]
        unique_together = ["bk_tenant_id", "plugin_id", "config_version", "info_version"]
        managed = False


@final
class Status:
    """
    采集配置状态
    """

    STARTING = "STARTING"
    STARTED = "STARTED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    DEPLOYING = "DEPLOYING"
    AUTO_DEPLOYING = "AUTO_DEPLOYING"
    PREPARING = "PREPARING"


@final
class CollectStatus:
    SUCCESS = "SUCCESS"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    PENDING = "PENDING"
    UNKNOWN = "UNKNOWN"
    NODATA = "NODATA"


@final
class OperationType:
    ROLLBACK = "ROLLBACK"
    UPGRADE = "UPGRADE"
    CREATE = "CREATE"
    EDIT = "EDIT"
    START = "START"
    STOP = "STOP"
    ADD_DEL = "ADD_DEL"


@final
class OperationResult:
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    FAILED = "FAILED"
    DEPLOYING = "DEPLOYING"
    PREPARING = "PREPARING"


@final
class TaskStatus:
    PENDING = "PENDING"
    FAILED = "FAILED"
    WARNING = "WARNING"
    SUCCESS = "SUCCESS"
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    DEPLOYING = "DEPLOYING"
    AUTO_DEPLOYING = "AUTO_DEPLOYING"
    STOPPING = "STOPPING"
    STARTING = "STARTING"
    PREPARING = "PREPARING"


@final
class TargetObjectType:
    """
    目标对象类型
    """

    SERVICE = "SERVICE"
    HOST = "HOST"
    CLUSTER = "CLUSTER"


@final
class TargetNodeType:
    """
    目标节点类型
    """

    TOPO = "TOPO"  # 动态实例（拓扑）
    INSTANCE = "INSTANCE"  # 静态实例
    SERVICE_TEMPLATE = "SERVICE_TEMPLATE"  # 服务模板
    SET_TEMPLATE = "SET_TEMPLATE"  # 集群模板
    DYNAMIC_GROUP = "DYNAMIC_GROUP"  # 动态分组
    CLUSTER = "CLUSTER"  # BCS集群


@final
class DeploymentConfigVersion(models.Model):
    """
    部署版本历史
    """

    TARGET_NODE_TYPE_CHOICES = (
        (TargetNodeType.TOPO, "拓扑"),
        (TargetNodeType.INSTANCE, "实例"),
        (TargetNodeType.SERVICE_TEMPLATE, "服务模板"),
        (TargetNodeType.SET_TEMPLATE, "集群模板"),
        (TargetNodeType.CLUSTER, "集群"),
        (TargetNodeType.DYNAMIC_GROUP, "动态分组"),
    )

    plugin_version = models.ForeignKey(
        PluginVersionHistory,
        verbose_name="关联插件版本",
        related_name="deployment_versions",
        on_delete=models.CASCADE,
    )

    parent_id = models.IntegerField("父配置ID", default=None, null=True)
    config_meta_id = models.IntegerField("所属采集配置ID")
    subscription_id = models.IntegerField("节点管理订阅ID", default=0)

    target_node_type = models.CharField("采集目标类型", max_length=32, choices=TARGET_NODE_TYPE_CHOICES)

    # 采集参数配置 example
    # {
    #     'collector': {
    #         'period': 60,  # 采集周期
    #         'host': '${target_host.inner_ip}',  # TODO: 如何支持CMDB变量
    #         'port': '9107',
    #     },
    #     'plugin': {
    #         '--web.listen-address': '${host}:${port}',
    #     }
    # }
    # 原本是jsonfield
    params = SymmetricTextField("采集参数配置", default=None)

    # 采集目标节点列表，数据结构为以下其中一种
    # 服务拓扑
    # [
    #     {
    #         'bk_inst_id': 33,   # 节点实例ID
    #         'bk_obj_id': 'module',  # 节点对象ID
    #     }
    # ]
    # 业务拓扑
    # [
    #     {
    #         'bk_inst_id': 33,   # 节点实例ID
    #         'bk_obj_id': 'module',  # 节点对象ID
    #     }
    # ]
    # 主机实例
    # [
    #     {
    #         'ip': '127.0.0.1',
    #         'bk_cloud_id': 0,
    #         'bk_supplier_id': 0,
    #     }
    # ]
    # 原本是jsonfield
    target_nodes = models.TextField("采集目标节点", default="[]")

    # 远程采集，若为空则代表不使用远程采集模式
    # {
    #     'ip': '127.0.0.1',
    #     'bk_cloud_id': 0,
    #     'bk_supplier_id': 0,
    #     'is_collecting_only': True  # 是否为采集专用机器
    # }
    # 原本是jsonfield
    remote_collecting_host = models.TextField("远程采集机器", default="")
    # 原本是jsonfield
    task_ids = models.TextField("任务id列表", default="")

    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    create_user = models.CharField("创建人", max_length=32, blank=True)
    update_time = models.DateTimeField("修改时间", auto_now=True)
    update_user = models.CharField("修改人", max_length=32, blank=True)
    is_deleted = models.BooleanField("是否删除", default=False)

    objects = OldModelManager(default_db_name=OLD_MONITOR_SAAS_DB_NAME)

    @override
    def __str__(self):
        return f"{self.target_node_type}-{self.plugin_version}"

    @final
    class Meta:
        db_table = "monitor_web_deploymentconfigversion"
        managed = False


@final
class CollectConfigMeta(models.Model):
    """
    采集配置基本信息
    """

    STATUS_CHOICES = (
        (Status.STARTING, "启用中"),
        (Status.STARTED, "已启用"),
        (Status.STOPPING, "停用中"),
        (Status.STOPPED, "已停用"),
        (Status.DEPLOYING, "执行中"),
    )

    OPERATION_TYPE_CHOICES = (
        (OperationType.UPGRADE, "升级"),
        (OperationType.ROLLBACK, "回滚"),
        (OperationType.START, "启用"),
        (OperationType.STOP, "停用"),
        (OperationType.CREATE, "新增"),
        (OperationType.EDIT, "编辑"),
        (OperationType.ADD_DEL, "增删目标"),
    )

    OPERATION_RESULT_CHOICES = (
        (OperationResult.SUCCESS, "全部成功"),
        (OperationResult.WARNING, "部分成功"),
        (OperationResult.FAILED, "全部失败"),
        (OperationResult.DEPLOYING, "下发中"),
        (OperationResult.PREPARING, "准备中"),
    )

    @final
    class CollectType(CollectorPluginMeta.PluginType):
        LOG = "Log"
        SNMP_TRAP = "SNMP_Trap"

    COLLECT_TYPE_CHOICES = CollectorPluginMeta.PLUGIN_TYPE_CHOICES

    TARGET_OBJECT_TYPE_CHOICES = (
        (TargetObjectType.SERVICE, "服务"),
        (TargetObjectType.HOST, "主机"),
        (TargetObjectType.CLUSTER, "集群"),
    )

    bk_tenant_id = models.CharField("租户ID", max_length=128, default=DEFAULT_TENANT_ID)
    bk_biz_id = models.IntegerField("业务ID", db_index=True)
    name = models.CharField("配置名称", max_length=128)

    # 采集插件相关配置
    collect_type = models.CharField("采集方式", max_length=32, choices=COLLECT_TYPE_CHOICES, db_index=True)
    plugin_id = models.CharField("插件ID", max_length=64)

    # 采集目标相关配置
    # 取值范围
    # target_object_type     target_node_type     说明
    # SERVICE                TOPO                 服务拓扑
    # HOST                   TOPO                 业务拓扑
    # HOST                   INSTANCE             主机实例
    target_object_type = models.CharField("采集对象类型", max_length=32, choices=TARGET_OBJECT_TYPE_CHOICES)

    deployment_config = models.ForeignKey(
        DeploymentConfigVersion, verbose_name="当前的部署配置", on_delete=models.CASCADE
    )
    # 原本是jsonfield
    cache_data = models.TextField("缓存数据", default="")
    last_operation = models.CharField("最近一次操作", max_length=32, choices=OPERATION_TYPE_CHOICES)
    operation_result = models.CharField("最近一次任务结果", max_length=32, choices=OPERATION_RESULT_CHOICES)

    label = models.CharField("二级标签", max_length=64, default="")

    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    create_user = models.CharField("创建人", max_length=32, blank=True)
    update_time = models.DateTimeField("修改时间", auto_now=True)
    update_user = models.CharField("修改人", max_length=32, blank=True)
    is_deleted = models.BooleanField("是否删除", default=False)

    objects = OldModelManager(default_db_name=OLD_MONITOR_SAAS_DB_NAME)

    @final
    class Meta:
        db_table = "monitor_web_collectconfigmeta"
        managed = False


def export_old_models_to_json(bk_tenant_id: str, plugin_ids: list[str]) -> str:
    """
    导出旧模型为 JSON
    """
    data: dict[str, list[dict[str, Any]]] = {
        "CollectorPluginMeta": [],
        "CollectorPluginInfo": [],
        "CollectorPluginConfig": [],
        "PluginVersionHistory": [],
        "DeploymentConfigVersion": [],
        "CollectConfigMeta": [],
    }
    plugins = CollectorPluginMeta.objects.filter(bk_tenant_id=bk_tenant_id, plugin_id__in=plugin_ids).values()
    plugin_histories = PluginVersionHistory.objects.filter(bk_tenant_id=bk_tenant_id, plugin_id__in=plugin_ids).values()

    plugin_config_ids: list[int] = []
    plugin_info_ids: list[int] = []
    for history in plugin_histories:
        plugin_config_ids.append(history["config_id"])
        plugin_info_ids.append(history["info_id"])
    plugin_configs = CollectorPluginConfig.objects.filter(id__in=plugin_config_ids).values()
    plugin_infos = CollectorPluginInfo.objects.filter(id__in=plugin_info_ids).values()

    collect_configs = CollectConfigMeta.objects.filter(bk_tenant_id=bk_tenant_id, plugin_id__in=plugin_ids).values()
    deployments = DeploymentConfigVersion.objects.filter(
        config_meta_id__in=collect_configs.values_list("pk", flat=True)
    ).values()

    for plugin in plugins:
        data["CollectorPluginMeta"].append(dict(plugin))
    for plugin_config in plugin_configs:
        data["CollectorPluginConfig"].append(dict(plugin_config))
    for plugin_info in plugin_infos:
        data["CollectorPluginInfo"].append(dict(plugin_info))
    for plugin_history in plugin_histories:
        plugin_history["signature"] = yaml.safe_dump(plugin_history["signature"])
        data["PluginVersionHistory"].append(dict(plugin_history))
    for deployment in deployments:
        data["DeploymentConfigVersion"].append(dict(deployment))
    for collect_config in collect_configs:
        data["CollectConfigMeta"].append(dict(collect_config))

    # 处理所有datetime字段，转换为时间戳
    for model in data.values():
        for obj in model:
            for field_name, field_value in obj.items():
                if isinstance(field_value, datetime.datetime):
                    obj[field_name] = int(field_value.timestamp())

    result = json.dumps(obj=data, ensure_ascii=False)
    with open("old_plugin_config.json", "w+") as f:
        f.write(result)

    return result


def import_old_models_from_json(
    data: dict[str, list[dict[str, Any]]] | None = None, json_file_path: str | Path = "old_plugin_config.json"
):
    """
    导入旧模型从 JSON

    Args:
        data: 包含各模型数据的字典，键为模型名称，值为模型实例数据列表

    Returns:
        bool: 导入是否成功

    注意：
        原本是 jsonfield 的字段在导入前需要先进行 json.dumps() 处理
    """

    # 如果data为空，则从json文件中读取
    if data is None:
        with open(json_file_path) as f:
            old_models_data = json.load(f)
    else:
        old_models_data = data

    # 原本是jsonfield的字段，需要dumps之后才能存储
    json_fields = {
        "CollectorPluginInfo": ["metric_json", "description_md"],
        "CollectorPluginConfig": ["config_json", "collector_json"],
        "PluginVersionHistory": ["signature"],
        "DeploymentConfigVersion": ["params", "target_nodes", "remote_collecting_host", "task_ids"],
        "CollectConfigMeta": ["cache_data"],
    }

    for model in [
        CollectorPluginMeta,
        CollectorPluginInfo,
        CollectorPluginConfig,
        PluginVersionHistory,
        DeploymentConfigVersion,
        CollectConfigMeta,
    ]:
        model_name = model.__name__
        json_field_list = json_fields.get(model_name, [])

        for obj in old_models_data[model_name]:
            # 对原本是 jsonfield 的字段进行 dumps 处理
            for field_name in json_field_list:
                if field_name in obj:
                    # 如果字段值不是字符串，说明是 Python 对象，需要 dumps
                    if not isinstance(obj[field_name], str):
                        obj[field_name] = json.dumps(obj[field_name], ensure_ascii=False)

            # 处理所有时间戳字段，转换为 datetime
            for field_name, field_value in obj.items():
                if isinstance(field_value, int) and field_name in ["create_time", "update_time"]:
                    obj[field_name] = datetime.datetime.fromtimestamp(field_value, tz=datetime.UTC)

            obj_id = obj.pop("id")
            model.objects.update_or_create(id=obj_id, defaults=obj)

    return True


def _parse_json_field(value: str | dict[str, Any] | list[Any] | None) -> dict[str, Any] | list[Any]:
    """
    解析 JSON 字段

    Args:
        value: 可能是字符串、字典、列表或 None

    Returns:
        解析后的字典或列表
    """
    if value is None:
        return {}
    if isinstance(value, dict | list):
        return value

    if not value or value.strip() == "" or value == "[]" or value == "{}":
        return [] if "[]" in value else {}
    try:
        parsed: dict[str, Any] | list[Any] | None = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return parsed
        return {}
    except json.JSONDecodeError:
        # 如果解析失败，返回空字典
        return {}


def _convert_stage_to_status(stage: str) -> str:
    """
    将旧模型的 stage 转换为新模型的 status

    Args:
        stage: 旧模型的状态值

    Returns:
        新模型的状态值
    """
    if stage == PluginVersionHistory.Stage.RELEASE:
        return "release"
    return "debug"


def _convert_deployment_status(last_operation: str, operation_result: str) -> str:
    """
    将旧模型的部署状态转换为新模型状态

    旧模型中通过最后一次操作和结果来体现状态
    """
    if operation_result == OperationResult.DEPLOYING:
        return "deploying"

    if operation_result == OperationResult.PREPARING:
        return "initializing"

    if operation_result == OperationResult.FAILED:
        return "failed"

    if operation_result == OperationResult.SUCCESS:
        # 如果最后一次操作是停用，且成功，则状态为已停止
        if last_operation == OperationType.STOP:
            return "stopped"
        # 其他操作成功（启动、升级、回滚、增删目标）均视为运行中
        return "running"

    return "initializing"


def _restore_model_timestamps(
    model_cls: type[models.Model], obj_id: int, **timestamps: datetime.datetime | None
) -> None:
    """
    使用 `update()` 回写时间字段，避免 `auto_now` / `auto_now_add` 覆盖迁移时间。

    Args:
        model_cls: 目标 ORM 模型类
        obj_id: 目标记录主键
        **timestamps: 需要回写的时间字段
    """
    update_data = {field_name: field_value for field_name, field_value in timestamps.items() if field_value is not None}
    if not update_data:
        return

    model_cls.objects.filter(pk=obj_id).update(**update_data)


def collect_and_migrate_all_files(bk_tenant_id: str, plugin_ids: list[str]) -> dict[int, dict[str, str]]:
    """
    收集并迁移所有插件版本中需要的文件

    该函数会在迁移插件之前，先收集所有版本中 collector_json 里的 file_id，
    验证文件是否存在，然后一次性迁移所有文件。

    Args:
        bk_tenant_id: 租户ID
        plugin_ids: 插件ID列表

    Returns:
        文件ID到token映射的字典，格式为: {file_id: {"token": "...", "plugin_type": "..."}}

    Raises:
        ValueError: 如果文件不存在，立即抛出异常停止迁移
    """
    from bk_monitor_base.domains.uploaded_file.old_models import (
        UploadedFileInfo,
        migrate_uploaded_file_info_to_new_model,
    )

    # 收集所有需要迁移的文件ID
    all_file_ids: set[int] = set()
    file_id_to_plugin_type: dict[int, str] = {}  # 记录每个文件ID对应的插件类型

    # 查询所有插件及其版本
    old_plugins = CollectorPluginMeta.objects.filter(
        bk_tenant_id=bk_tenant_id, plugin_id__in=plugin_ids, is_deleted=False
    )

    for old_plugin in old_plugins:
        # 查询该插件的所有版本
        old_versions = PluginVersionHistory.objects.filter(
            bk_tenant_id=bk_tenant_id, plugin_id=old_plugin.plugin_id, is_deleted=False
        )

        for old_version in old_versions:
            try:
                old_config = old_version.config
                collector_json_raw = _parse_json_field(old_config.collector_json)

                # 提取 collector_json 中的所有 file_id
                if isinstance(collector_json_raw, dict):
                    for _os_type, os_config in collector_json_raw.items():
                        if isinstance(os_config, dict) and "file_id" in os_config:
                            file_id = cast(int, os_config["file_id"])
                            all_file_ids.add(file_id)
                            # 记录文件ID对应的插件类型（用于生成usage）
                            if file_id not in file_id_to_plugin_type:
                                file_id_to_plugin_type[file_id] = old_plugin.plugin_type
            except Exception as e:
                logger.warning(
                    f"提取文件ID失败: {old_plugin.plugin_id} "
                    + f"v{old_version.config_version}.{old_version.info_version} - {str(e)}"
                )
                continue

    # 如果没有需要迁移的文件，直接返回空字典
    if not all_file_ids:
        logger.debug("没有需要迁移的文件")
        return {}

    # 验证文件是否存在
    existing_file_ids = set(UploadedFileInfo.objects.filter(id__in=all_file_ids).values_list("id", flat=True))
    missing_file_ids = set(all_file_ids) - existing_file_ids

    if missing_file_ids:
        error_msg = (
            f"迁移失败：以下文件ID不存在: {sorted(missing_file_ids)}. 租户ID: {bk_tenant_id}, 插件列表: {plugin_ids}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    # 按插件类型分组迁移文件
    file_id_to_token_map: dict[int, dict[str, str]] = {}

    # 按插件类型分组文件ID
    plugin_type_to_file_ids: dict[str, list[int]] = {}
    for file_id in all_file_ids:
        plugin_type = file_id_to_plugin_type.get(file_id, "unknown")
        if plugin_type not in plugin_type_to_file_ids:
            plugin_type_to_file_ids[plugin_type] = []
        plugin_type_to_file_ids[plugin_type].append(file_id)

    # 按插件类型迁移文件
    for plugin_type, file_ids in plugin_type_to_file_ids.items():
        usage = f"metric_plugin.{plugin_type.lower()}"
        file_id_token_map = migrate_uploaded_file_info_to_new_model(
            bk_tenant_id=bk_tenant_id, usage=usage, file_ids=file_ids
        )

        # 构建完整的映射信息
        for file_id, token in file_id_token_map.items():
            file_id_to_token_map[file_id] = {"token": token, "plugin_type": plugin_type}

    logger.info(f"成功迁移 {len(file_id_to_token_map)} 个文件")
    return file_id_to_token_map


@transaction.atomic
def migrate_old_models_to_new_models(bk_tenant_id: str, plugin_ids: list[str]) -> dict[str, Any]:
    """
    将旧模型数据迁移到新模型

    Args:
        bk_tenant_id: 租户ID
        plugin_ids: 插件ID列表

    Returns:
        迁移结果统计信息

    Note:
        迁移策略：如果新模型中已存在相同插件ID，则更新记录
    """
    from .models import (
        MetricPluginDeploymentModel,
        MetricPluginDeploymentVersionModel,
        MetricPluginModel,
        MetricPluginVersionModel,
    )

    result: dict[str, Any] = {
        "plugins_migrated": 0,
        "versions_migrated": 0,
        "deployments_migrated": 0,
        "errors": [],
    }

    # 0. 首先收集并迁移所有需要的文件（如果有问题立刻报错）
    try:
        file_id_to_token_map = collect_and_migrate_all_files(bk_tenant_id=bk_tenant_id, plugin_ids=plugin_ids)
    except ValueError as e:
        # 文件不存在时，立即停止整个迁移过程
        error_msg = f"文件迁移失败，停止迁移: {str(e)}"
        result["errors"].append(error_msg)
        logger.error(error_msg)
        return result

    # 1. 查询旧模型的插件基础信息
    old_plugins = CollectorPluginMeta.objects.filter(
        bk_tenant_id=bk_tenant_id, plugin_id__in=plugin_ids, is_deleted=False
    )

    for old_plugin in old_plugins:
        try:
            # 检查新模型中是否已存在
            plugin_model, created = MetricPluginModel.objects.update_or_create(
                bk_tenant_id=old_plugin.bk_tenant_id,
                plugin_id=old_plugin.plugin_id,
                defaults={
                    "bk_biz_id": old_plugin.bk_biz_id,
                    "type": old_plugin.plugin_type.lower(),
                    "label": old_plugin.label,
                    "is_internal": old_plugin.is_internal,
                    "is_global": old_plugin.bk_biz_id == 0,  # 业务ID为0表示全局插件
                    "created_at": old_plugin.create_time,
                    "created_by": old_plugin.create_user,
                    "is_deleted": old_plugin.is_deleted,
                    "related_params": {"tag": old_plugin.tag} if old_plugin.tag else {},
                },
            )
            _restore_model_timestamps(MetricPluginModel, plugin_model.pk, created_at=old_plugin.create_time)

            if created:
                result["plugins_migrated"] += 1

            # 2. 迁移插件版本信息
            old_versions = PluginVersionHistory.objects.filter(
                bk_tenant_id=bk_tenant_id, plugin_id=old_plugin.plugin_id, is_deleted=False
            ).order_by("config_version", "info_version")

            for old_version in old_versions:
                try:
                    # 获取关联的配置和信息
                    old_config = old_version.config
                    old_info = old_version.info

                    # 解析 JSON 字段
                    metrics_data_raw = _parse_json_field(old_info.metric_json)
                    params_data_raw = _parse_json_field(old_config.config_json)
                    define_data_raw: dict[str, Any] = json.loads(old_config.collector_json)

                    # 替换 file_id 为 token，保留旧字段为 old_file_id
                    for value in define_data_raw.values():
                        if isinstance(value, dict) and "file_id" in value:
                            file_id = cast(int, value["file_id"])
                            if file_id in file_id_to_token_map:
                                value["file_token"] = file_id_to_token_map[file_id]["token"]
                                # 保留旧的 file_id 为 old_file_id，用于历史追溯
                                value["old_file_id"] = value.pop("file_id")
                            else:
                                raise ValueError(f"文件ID不存在: {file_id}")

                    # 转换指标和参数格式
                    metrics_data = metrics_data_raw if isinstance(metrics_data_raw, list) else []

                    # 转换状态
                    status = _convert_stage_to_status(old_version.stage)

                    # 创建或更新版本模型
                    version_model, version_created = MetricPluginVersionModel.objects.update_or_create(
                        bk_tenant_id=old_version.bk_tenant_id,
                        bk_biz_id=old_plugin.bk_biz_id,
                        plugin=plugin_model,
                        version=f"{int(old_version.config_version):06d}.{int(old_version.info_version):06d}",
                        defaults={
                            "name": old_info.plugin_display_name,
                            "description_md": old_info.description_md,
                            "metrics": metrics_data,
                            "enable_metric_discovery": old_info.enable_field_blacklist,
                            "params": params_data_raw,
                            "define": define_data_raw,
                            "is_support_remote": old_config.is_support_remote,
                            "version_log": old_version.version_log,
                            "status": status,
                            "updated_at": old_version.create_time,
                            "updated_by": old_version.create_user,
                        },
                    )

                    # 处理 logo 文件迁移
                    if old_info.logo and old_info.logo.name:
                        try:
                            # 读取旧 logo 文件
                            old_info.logo.open("rb")
                            logo_content: bytes = old_info.logo.read()
                            old_info.logo.close()

                            # 保存到新模型
                            if logo_content:
                                version_model.logo = base64.b64encode(logo_content).decode("utf-8")
                                version_model.save(update_fields=["logo"])
                        except Exception as e:
                            # Logo 迁移失败不影响整体迁移
                            result["errors"].append(
                                f"Logo迁移失败: {old_plugin.plugin_id} v{old_version.config_version}.{old_version.info_version} - {str(e)}"
                            )

                    # 更新插件的关联参数（存储 signature）
                    if old_version.signature:
                        plugin_model.related_params["signature"] = old_version.signature
                        plugin_model.save(update_fields=["related_params"])

                    _restore_model_timestamps(
                        MetricPluginVersionModel,
                        version_model.pk,
                        updated_at=old_version.create_time,
                    )

                    if version_created:
                        result["versions_migrated"] += 1

                except Exception as e:
                    error_msg = f"版本迁移失败: {old_plugin.plugin_id} v{old_version.config_version}.{old_version.info_version} - {str(e)}"
                    result["errors"].append(error_msg)
                    continue

            # 3. 迁移部署配置信息
            old_collect_configs = CollectConfigMeta.objects.filter(
                bk_tenant_id=bk_tenant_id, plugin_id=old_plugin.plugin_id, is_deleted=False
            )

            for old_collect_config in old_collect_configs:
                try:
                    # 获取当前的部署配置版本
                    old_deployment_config = old_collect_config.deployment_config

                    # 创建或更新部署模型，确保 id 与旧模型一致
                    old_collect_config_id = old_collect_config.pk
                    deployment_status = _convert_deployment_status(
                        old_collect_config.last_operation, old_collect_config.operation_result
                    )
                    deployment_model, deployment_created = MetricPluginDeploymentModel.objects.update_or_create(
                        id=old_collect_config_id,  # 使用旧模型的 id 作为查找条件，确保 id 一致
                        defaults={
                            "bk_tenant_id": old_collect_config.bk_tenant_id,
                            "bk_biz_id": old_collect_config.bk_biz_id,
                            "plugin": plugin_model,
                            "name": old_collect_config.name,
                            "related_params": {
                                "subscription_id": old_deployment_config.subscription_id,
                                "config_meta_id": old_collect_config_id,
                                "task_ids": old_deployment_config.task_ids,
                            },
                            "status": deployment_status,
                            "created_at": old_collect_config.create_time,
                            "created_by": old_collect_config.create_user,
                            "updated_at": old_collect_config.update_time,
                            "updated_by": old_collect_config.update_user,
                        },
                    )
                    _restore_model_timestamps(
                        MetricPluginDeploymentModel,
                        deployment_model.pk,
                        created_at=old_collect_config.create_time,
                        updated_at=old_collect_config.update_time,
                    )

                    if deployment_created:
                        result["deployments_migrated"] += 1

                    # 获取插件版本号
                    plugin_version_history = old_deployment_config.plugin_version
                    plugin_version_str = (
                        f"{plugin_version_history.config_version}.{plugin_version_history.info_version}"
                    )

                    # 解析部署参数
                    deployment_params: dict[str, Any] = {}
                    if old_deployment_config.params:
                        # SymmetricTextField 会自动解密
                        params_str = str(old_deployment_config.params)
                        if params_str:
                            params_parsed = _parse_json_field(params_str)
                            if isinstance(params_parsed, dict):
                                deployment_params = params_parsed

                    # 解析目标节点
                    target_nodes_raw = _parse_json_field(old_deployment_config.target_nodes)
                    target_nodes: list[dict[str, Any]] = target_nodes_raw if isinstance(target_nodes_raw, list) else []

                    # 解析远程采集主机
                    remote_collecting_host_raw = _parse_json_field(old_deployment_config.remote_collecting_host)
                    remote_nodes: list[dict[str, Any]] = []
                    remote_node_type = ""
                    if remote_collecting_host_raw:
                        if isinstance(remote_collecting_host_raw, dict):
                            remote_nodes = [remote_collecting_host_raw]
                            remote_node_type = "HOST"  # 默认为主机类型
                        else:
                            if remote_collecting_host_raw:
                                remote_nodes = remote_collecting_host_raw
                                remote_node_type = "HOST"

                    # 创建部署版本模型
                    # 查找该部署项的最大版本号
                    max_version = (
                        MetricPluginDeploymentVersionModel.objects.filter(deployment=deployment_model)
                        .order_by("-version")
                        .first()
                    )
                    next_version = (max_version.version + 1) if max_version else 1

                    # 将之前的版本设置为非当前版本
                    MetricPluginDeploymentVersionModel.objects.filter(deployment=deployment_model).update(
                        is_current=False
                    )

                    # 创建部署版本模型
                    deployment_version_model = MetricPluginDeploymentVersionModel.objects.create(
                        bk_tenant_id=old_collect_config.bk_tenant_id,
                        bk_biz_id=old_collect_config.bk_biz_id,
                        deployment=deployment_model,
                        plugin_version=plugin_version_str,
                        version=next_version,
                        is_current=True,
                        params=deployment_params,
                        target_node_type=old_deployment_config.target_node_type
                        if old_deployment_config.target_node_type != TargetNodeType.INSTANCE
                        else "HOST",
                        target_nodes=target_nodes,
                        remote_node_type=remote_node_type,
                        remote_nodes=remote_nodes,
                        created_at=old_deployment_config.create_time,
                        created_by=old_deployment_config.create_user,
                    )
                    _restore_model_timestamps(
                        MetricPluginDeploymentVersionModel,
                        deployment_version_model.pk,
                        created_at=old_deployment_config.create_time,
                    )

                except Exception as e:
                    error_msg = f"部署配置迁移失败: {old_collect_config.name} - {str(e)}"
                    result["errors"].append(error_msg)
                    continue

        except Exception as e:
            error_msg = f"插件迁移失败: {old_plugin.plugin_id} - {str(e)}"
            result["errors"].append(error_msg)
            continue

    return result
