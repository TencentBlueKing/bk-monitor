"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
from collections import namedtuple
from dataclasses import dataclass, field
from distutils.version import StrictVersion
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import yaml
from bk_monitor_base.domains.uploaded_file.operation import get_file
from bk_monitor_base.metric_plugin import (
    CreatePluginParams,
    CreatePluginVersionParams,
    MetricPluginMetricGroup,
    MetricPluginNotFoundError,
    MetricPluginStatus,
    MetricPluginVersionNotFoundError,
    OSType,
    PluginIDExistsError,
    PluginIDInvalidError,
    UpdatePluginVersionParams,
    VersionTuple,
    apply_metric_plugin_data_link,
    check_metric_plugin_id,
    create_metric_plugin,
    create_metric_plugin_version,
    get_metric_plugin,
    get_metric_plugin_supported_os_types,
    parse_metric_plugin_package,
    register_metric_plugin,
    release_metric_plugin_version,
    update_metric_plugin_version,
    upload_plugin_file,
)
from django.conf import settings
from django.db.transaction import atomic
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.serializers import Serializer

from bkmonitor.utils.common_utils import safe_int
from bkmonitor.utils.request import get_request_tenant_id, get_request_username
from bkmonitor.utils.serializers import MetricJsonBaseSerializer
from constants.result_table import RT_RESERVED_WORD_EXACT, RT_RESERVED_WORD_FUZZY, RT_TABLE_NAME_WORD_EXACT
from core.drf_resource import Resource, resource
from core.drf_resource.exceptions import CustomException
from core.drf_resource.tools import format_serializer_errors
from core.errors.export_import import ExportImportError
from core.errors.plugin import (
    BizChangedError,
    JsonParseError,
    MetricNumberError,
    PluginIDExist,
    PluginIDFormatError,
    PluginIDNotExist,
    PluginParseError,
    PluginVersionNotExist,
    RegexParseError,
    RegisterPackageError,
    RelatedItemsExist,
    SNMPMetricNumberError,
    SubprocessCallError,
    UnsupportedPluginTypeError,
)
from monitor.models import GlobalConfig
from monitor_web.commons.data_access import PluginDataAccessor
from monitor_web.commons.file_manager import PluginFileManager
from monitor_web.models import CollectConfigMeta
from monitor_web.models.plugin import CollectorPluginMeta, PluginVersionHistory
from monitor_web.plugin.constant import (
    MAX_METRIC_NUM,
    OS_TYPE_TO_DIRNAME,
    SNMP_MAX_METRIC_NUM,
    ConflictMap,
    PluginType,
)
from monitor_web.plugin.serializers import (
    DataDogSerializer,
    ExporterSerializer,
    JmxSerializer,
    K8sSerializer,
    LogSerializer,
    PluginRegisterRequestSerializer,
    ProcessSerializer,
    PushgatewaySerializer,
    ScriptSerializer,
    SNMPSerializer,
    SNMPTrapSerializer,
)
from bk_monitor_base.metric_plugin import (
    dump_plugin_signature_to_yaml,
    parse_plugin_signature_from_yaml,
    verify_plugin_signature,
)
from utils import count_md5

logger = logging.getLogger(__name__)


@dataclass
class _PluginImportContext:
    # 导入链路里的中间态统一放在 context 中，避免 Resource 实例状态污染。
    tmp_path: str
    filename_dict: dict[Path, bytes] = field(default_factory=dict)
    plugin_id: str = ""
    plugin_type: str = ""
    meta_dict: dict[str, Any] = field(default_factory=dict)
    imported_meta: dict[str, Any] = field(default_factory=dict)
    imported_config: dict[str, Any] = field(default_factory=dict)
    imported_info: dict[str, Any] = field(default_factory=dict)
    imported_version: dict[str, Any] = field(default_factory=dict)
    current_version: PluginVersionHistory | None = None
    create_params: dict[str, Any] = field(
        default_factory=lambda: {
            "is_official": False,
            "is_safety": False,
            "duplicate_type": None,
            "conflict_detail": "",
            "conflict_title": "",
        }
    )


class PluginFileUploadResource(Resource):
    class RequestSerializer(serializers.Serializer):
        file_data = serializers.FileField(required=True)
        file_name = serializers.CharField(required=False)
        plugin_id = serializers.CharField(required=False)
        plugin_type = serializers.CharField(required=True)
        os = serializers.CharField(required=True)

    def perform_request(self, validated_request_data):
        bk_tenant_id = cast(str, get_request_tenant_id())
        os_type = OSType(validated_request_data["os"])
        plugin_type = validated_request_data["plugin_type"]
        file_data = validated_request_data["file_data"]

        try:
            file_info, extra_info = upload_plugin_file(
                plugin_type=plugin_type,
                bk_tenant_id=bk_tenant_id,
                file_or_content=file_data,
                os_type=os_type,
                operator=get_request_username(),
            )
        except Exception as err:
            logger.error(f"[plugin] Upload plugin failed, msg is {str(err)}")
            raise err

        return {
            "file_id": file_info.id,
            "actual_filename": file_info.file.name,
            "original_filename": file_info.filename,
            "file_md5": file_info.md5,
            **extra_info,
        }


class DataDogPluginUploadResource(Resource):
    class RequestSerializer(serializers.Serializer):
        file_data = serializers.FileField(required=True)
        os = serializers.CharField(required=True)
        plugin_id = serializers.CharField(required=False)

    def perform_request(self, validated_request_data):
        try:
            file_info, extra_info = upload_plugin_file(
                plugin_type=CollectorPluginMeta.PluginType.DATADOG,
                bk_tenant_id=cast(str, get_request_tenant_id()),
                file_or_content=validated_request_data["file_data"],
                os_type=OSType(validated_request_data["os"]),
                operator=get_request_username(),
            )
        except Exception as err:
            logger.error(f"[plugin] Upload plugin failed, msg is {str(err)}")
            raise err

        return {
            "file_id": file_info.id,
            "file_name": file_info.filename,
            "md5": file_info.md5,
            **extra_info,
        }


class SaveMetricResource(Resource):
    class RequestSerializer(MetricJsonBaseSerializer):
        plugin_id = serializers.RegexField(
            required=True, regex=r"^[a-zA-Z][a-zA-Z0-9_]*$", max_length=30, label="插件ID"
        )
        plugin_type = serializers.ChoiceField(
            required=True, choices=[choice[0] for choice in CollectorPluginMeta.PLUGIN_TYPE_CHOICES], label="插件类型"
        )
        config_version = serializers.IntegerField(required=True, label="插件版本")
        info_version = serializers.IntegerField(required=True, label="插件信息版本")
        need_upgrade = serializers.BooleanField(required=False, label="是否升级", default=False)
        enable_field_blacklist = serializers.BooleanField(label="是否开启黑名单", default=False)

    def delay(self, request_data: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        request_data = request_data or kwargs
        self.validate_request_data(request_data)
        return self.apply_async(request_data)

    @staticmethod
    def _clear_metric_tag_list(metric_json: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        关闭自动发现时，沿用旧链路行为，清空字段上的 tag_list。
        """
        normalized_metric_json = copy.deepcopy(metric_json)
        for metric_data in normalized_metric_json:
            for field_data in metric_data.get("fields", []):
                field_data["tag_list"] = []
        return normalized_metric_json

    @staticmethod
    def _build_metric_groups(metric_json: list[dict[str, Any]]) -> list[MetricPluginMetricGroup]:
        """将前端的 metric_json 转成 bk_monitor_base 的领域模型。

        实际逻辑委托给 ``compat.convert_metric_json_to_base``，
        保留此方法是为了不改变已有调用方的签名。
        """
        from monitor_web.plugin.compat import convert_metric_json_to_base

        return convert_metric_json_to_base(metric_json)

    @staticmethod
    def _validate_metric_limit(plugin_type: str, metric_json: list[dict[str, Any]]) -> None:
        """
        保留旧资源层的数量限制逻辑，确保迁移后接口校验行为不变。
        """
        if plugin_type == CollectorPluginMeta.PluginType.SNMP:
            if len(metric_json) > SNMP_MAX_METRIC_NUM:
                raise SNMPMetricNumberError(snmp_max_metric_num=SNMP_MAX_METRIC_NUM)
            return

        metric_num = len(
            [
                field
                for metric_data in metric_json
                for field in metric_data["fields"]
                if field["monitor_type"] == "metric"
            ]
        )
        if metric_num <= MAX_METRIC_NUM:
            return

        config, _ = GlobalConfig.objects.get_or_create(key="MAX_METRIC_NUM", defaults={"value": MAX_METRIC_NUM})
        if metric_num > safe_int(config.value, dft=MAX_METRIC_NUM):
            raise MetricNumberError(max_metric_num=safe_int(config.value, dft=MAX_METRIC_NUM))

    @staticmethod
    def _build_new_define(
        current_define: dict[str, Any], metric_json: list[dict[str, Any]]
    ) -> tuple[dict[str, Any], bool]:
        """
        `diff_fields` 仍然挂在 define/collector_json 上。
        它变化时需要升级 config_version，因为最终会影响插件包内容。
        """
        diff_fields = PluginVersionHistory.gen_diff_fields(metric_json)
        new_define = copy.deepcopy(current_define)
        if diff_fields:
            new_define["diff_fields"] = diff_fields
        else:
            new_define.pop("diff_fields", None)
        define_changed = count_md5(current_define) != count_md5(new_define)
        return new_define, define_changed

    @staticmethod
    def _append_metric_cache(
        bk_tenant_id: str, plugin_type: str, plugin_id: str, metric_json: list[dict[str, Any]]
    ) -> None:
        """
        `release_metric_plugin_version` 会负责数据链路和发布，
        但旧链路里额外触发的 metric cache 刷新仍然保留在这里。
        """
        from monitor_web.tasks import append_metric_list_cache

        result_table_id_list = [
            f"{plugin_type.lower()}_{plugin_id}.{metric_msg['table_name']}" for metric_msg in metric_json
        ]
        append_metric_list_cache.delay(bk_tenant_id, result_table_id_list)

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        bk_tenant_id = cast(str, get_request_tenant_id())
        operator = cast(str, get_request_username())
        plugin_id: str = validated_request_data["plugin_id"]
        plugin_type: str = validated_request_data["plugin_type"]
        metric_json: list[dict[str, Any]] = copy.deepcopy(validated_request_data["metric_json"])
        self._validate_metric_limit(plugin_type, metric_json)

        current_version = VersionTuple(
            major=validated_request_data["config_version"],
            minor=validated_request_data["info_version"],
        )
        current_plugin = get_metric_plugin(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            version=current_version,
        )

        enable_metric_discovery = validated_request_data["enable_field_blacklist"]
        if not enable_metric_discovery:
            metric_json = self._clear_metric_tag_list(metric_json)

        # 先比较指标内容，再比较 define 和自动发现开关，最后统一决定版本升级。
        current_metric_payload: list[dict[str, Any]] = [metric.model_dump() for metric in current_plugin.metrics]
        # 统一转换成 base 的结构后再比较，避免 `rule_list/rules` 之类字段名差异造成误判。
        new_metric_payload: list[dict[str, Any]] = [
            metric_group.model_dump() for metric_group in self._build_metric_groups(metric_json)
        ]
        metric_changed: bool = count_md5(current_metric_payload) != count_md5(new_metric_payload)
        new_define, define_changed = self._build_new_define(current_plugin.define, metric_json)
        discovery_changed: bool = current_plugin.enable_metric_discovery != enable_metric_discovery
        is_change: bool = metric_changed or define_changed or discovery_changed

        if not is_change:
            return {"config_version": current_version.major, "info_version": current_version.minor}

        # 继续沿用旧 save_metric 的版本语义：
        # info_version 在指标发生变化时递增，define 变化时额外推动 config_version 递增。
        target_version = VersionTuple(
            major=current_version.major + (1 if define_changed else 0),
            minor=current_version.minor + 1,
        )
        target_status = MetricPluginStatus.DEBUG if define_changed else MetricPluginStatus.RELEASE

        create_metric_plugin_version(
            bk_tenant_id=bk_tenant_id,
            plugin_id=plugin_id,
            operator=operator,
            params=CreatePluginVersionParams(
                version=target_version,
                status=target_status,
                version_log="update_metric",
                name=current_plugin.name,
                description_md=current_plugin.description_md,
                label=current_plugin.label,
                logo=current_plugin.logo,
                metrics=self._build_metric_groups(metric_json),
                enable_metric_discovery=enable_metric_discovery,
                params=current_plugin.params,
                define=new_define,
                is_support_remote=current_plugin.is_support_remote,
            ),
        )

        # define 变化会影响插件包内容，必须重新注册后再发布。
        if define_changed:
            register_metric_plugin(
                bk_tenant_id=bk_tenant_id,
                plugin_id=plugin_id,
                version=target_version,
                operator=operator,
            )
            release_metric_plugin_version(
                bk_tenant_id=bk_tenant_id,
                plugin_id=plugin_id,
                version=target_version,
                operator=operator,
            )
        else:
            # 纯指标/自动发现开关变化时不需要重打包，只需同步数据链路。
            apply_metric_plugin_data_link(
                bk_tenant_id=bk_tenant_id,
                plugin_id=plugin_id,
                version=target_version,
                operator=operator,
            )

        self._append_metric_cache(
            bk_tenant_id=bk_tenant_id,
            plugin_type=plugin_type,
            plugin_id=plugin_id,
            metric_json=metric_json,
        )
        return {"config_version": target_version.major, "info_version": target_version.minor}


class CreatePluginResource(Resource):
    SERIALIZERS: dict[str, type[Serializer]] = {
        CollectorPluginMeta.PluginType.EXPORTER: ExporterSerializer,
        CollectorPluginMeta.PluginType.JMX: JmxSerializer,
        CollectorPluginMeta.PluginType.SCRIPT: ScriptSerializer,
        CollectorPluginMeta.PluginType.PUSHGATEWAY: PushgatewaySerializer,
        CollectorPluginMeta.PluginType.DATADOG: DataDogSerializer,
        CollectorPluginMeta.PluginType.LOG: LogSerializer,
        CollectorPluginMeta.PluginType.PROCESS: ProcessSerializer,
        CollectorPluginMeta.PluginType.SNMP_TRAP: SNMPTrapSerializer,
        CollectorPluginMeta.PluginType.SNMP: SNMPSerializer,
        CollectorPluginMeta.PluginType.K8S: K8sSerializer,
    }

    def validate_request_data(self, request_data):
        if request_data.get("plugin_type") in self.SERIALIZERS:
            self.RequestSerializer = self.SERIALIZERS[request_data.get("plugin_type")]
        else:
            raise UnsupportedPluginTypeError({"plugin_type", request_data.get("plugin_type")})
        return super().validate_request_data(request_data)

    def perform_request(self, validated_request_data: dict[str, Any]):
        bk_tenant_id = cast(str, get_request_tenant_id())
        operator = cast(str, get_request_username())
        bk_biz_id: int = validated_request_data["bk_biz_id"]
        plugin_id: str = validated_request_data["plugin_id"]
        plugin_type: str = validated_request_data["plugin_type"]
        import_plugin_metric_json = validated_request_data.get("import_plugin_metric_json")

        major_version: int = validated_request_data["config_version"] or 1
        minor_version: int = validated_request_data["info_version"] or 0
        version = VersionTuple(major=major_version, minor=minor_version)

        metric_plugin = create_metric_plugin(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=bk_biz_id,
            operator=operator,
            params=CreatePluginParams(
                id=plugin_id,
                type=plugin_type,
                is_global=bk_biz_id == 0,
                is_internal=validated_request_data["is_internal"],
                name=validated_request_data["plugin_display_name"],
                description_md=validated_request_data["description_md"],
                label=validated_request_data["label"],
                logo=validated_request_data["logo"],
                metrics=import_plugin_metric_json if import_plugin_metric_json else [],
                enable_metric_discovery=True,
                params=validated_request_data["config_json"],
                define=validated_request_data["collector_json"],
                version=version,
                is_support_remote=validated_request_data["is_support_remote"],
            ),
        )

        validated_request_data["config_version"] = metric_plugin.version.major
        validated_request_data["info_version"] = metric_plugin.version.minor
        validated_request_data["os_type_list"] = get_metric_plugin_supported_os_types(bk_tenant_id, plugin_id)
        validated_request_data["need_debug"] = False
        validated_request_data["signature"] = ""
        validated_request_data["enable_field_blacklist"] = True
        return validated_request_data


class PluginRegisterResource(Resource):
    RequestSerializer = PluginRegisterRequestSerializer

    def delay(self, request_data: dict[str, Any] | None = None, **kwargs: Any) -> Any:
        request_data = request_data or kwargs
        self.validate_request_data(request_data)
        return self.apply_async(request_data)

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, list[str]]:
        bk_tenant_id = cast(str, get_request_tenant_id())
        operator = cast(str, get_request_username())
        plugin_id: str = validated_request_data["plugin_id"]
        version = VersionTuple(
            major=validated_request_data["config_version"],
            minor=validated_request_data["info_version"],
        )
        try:
            # 先通过 base 侧领域查询校验插件和目标版本存在，再执行注册。
            get_metric_plugin(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id, version=version)
        except MetricPluginNotFoundError:
            raise PluginIDNotExist
        except MetricPluginVersionNotFoundError:
            raise PluginVersionNotExist

        try:
            token_list = sorted(
                register_metric_plugin(
                    bk_tenant_id=bk_tenant_id,
                    plugin_id=plugin_id,
                    version=version,
                    operator=operator,
                )
            )
        except Exception as err:
            logger.exception(err)
            raise RegisterPackageError({"msg": str(err)})

        return {"token": token_list}


class PluginImportResource(Resource):
    INFO_FILENAMES = ("description.md", "config.json", "logo.png", "metrics.json", "signature.yaml", "release.md")
    CollectorFile = namedtuple("CollectorFile", ["name", "data"])

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        file_data = serializers.FileField(required=True)

    @staticmethod
    def un_tar_gz_file(tar_obj) -> dict[Path, bytes]:
        # 免解压读取文件内容到内存
        filename_dict: dict[Path, bytes] = {}
        with tarfile.open(fileobj=tar_obj) as package_file:
            for member in package_file.getmembers():
                # 取代 tarfile.extractall 的 filter="data"
                if not member.isreg():
                    continue
                with cast(io.BufferedReader, package_file.extractfile(member)) as f:
                    filename_dict[Path(member.name)] = f.read()
        return filename_dict

    @staticmethod
    def get_plugin(filename_dict: dict[Path, bytes]) -> tuple[str, str, dict[str, Any]]:
        meta_yaml_path: Path = Path("")
        plugin_id: str = ""
        # 获取plugin_id,meta.yaml必要信息
        for filename in filename_dict.keys():
            path = filename.parts
            if (
                len(path) >= 4
                and path[-1] == "meta.yaml"
                and path[-2] == "info"
                and path[-4] in list(OS_TYPE_TO_DIRNAME.values())
            ):
                plugin_id = path[-3]
                meta_yaml_path = filename
                break

        if not plugin_id:
            raise PluginParseError({"msg": _("无法解析plugin_id")})

        try:
            meta_content = filename_dict[meta_yaml_path]
        except OSError:
            raise PluginParseError({"msg": _("meta.yaml不存在，无法解析")})

        meta_dict = yaml.load(meta_content, Loader=yaml.FullLoader)
        # 检验plugin_type
        plugin_type_display = meta_dict.get("plugin_type")
        for name, display_name in CollectorPluginMeta.PLUGIN_TYPE_CHOICES:
            if display_name == plugin_type_display:
                return plugin_id, name, meta_dict
        raise PluginParseError({"msg": _("无法解析插件类型")})

    @staticmethod
    def get_signature(filename_dict: dict[Path, bytes], plugin_id: str) -> dict[str, Any] | str:
        signature_path = None
        for filename in filename_dict.keys():
            if filename.name == "signature.yaml":
                signature_path = filename
                break

        if not signature_path:
            return ""

        result = parse_plugin_signature_from_yaml(filename_dict[signature_path])
        if not result:
            logger.warning("[ImportPlugin] %s - signature parse returned empty", plugin_id)
        return result or ""

    @staticmethod
    def get_os_type_list(filename_dict: dict[Path, bytes]) -> list[str]:
        os_type_list = set()
        for filename in filename_dict.keys():
            path = filename.parts
            if len(path) < 2:
                continue
            os_dir = path[0]
            for os_type, dirname in OS_TYPE_TO_DIRNAME.items():
                if dirname == os_dir:
                    os_type_list.add(os_type)
                    break
        return sorted(os_type_list)

    @staticmethod
    def _strip_logo_prefix(logo: str) -> bytes | str:
        if not logo:
            return b""
        return logo.split(",", 1)[-1].encode("utf-8")

    @staticmethod
    def _build_file_collector_json(define: dict[str, Any], with_os_prefix: bool, bk_tenant_id: str) -> dict[str, Any]:
        collector_json = {}
        for os_type, file_config in define.items():
            if os_type not in OS_TYPE_TO_DIRNAME or not isinstance(file_config, dict):
                continue
            file_token = file_config.get("file_token")
            file_name = file_config.get("file_name")
            if not file_token or not file_name:
                continue

            file_info = get_file(bk_tenant_id=bk_tenant_id, file_token=file_token)
            if hasattr(file_info.file, "seek"):
                file_info.file.seek(0)
            legacy_file_name = f"{os_type}_{file_name}" if with_os_prefix else file_name
            file_manager = PluginFileManager.save_file(file_data=file_info.file.read(), file_name=legacy_file_name)
            collector_json[os_type] = {
                "file_id": file_manager.file_obj.pk,
                "file_name": file_manager.file_obj.actual_filename,
                "md5": file_manager.file_obj.file_md5,
            }
        return collector_json

    @staticmethod
    def _find_file_by_basename(filename_dict: dict[Path, bytes], *candidate_names: str) -> Path | None:
        for filename in filename_dict.keys():
            if filename.name in candidate_names:
                return filename
        return None

    @classmethod
    def _build_legacy_collector_json(
        cls,
        parsed_params: CreatePluginParams,
        filename_dict: dict[Path, bytes],
        plugin_type: str,
        bk_tenant_id: str,
    ) -> dict[str, Any]:
        # base 侧返回的是统一 define；这里需要回填成旧前端/旧 serializer 仍在使用的 collector_json 结构。
        define = parsed_params.define or {}

        if plugin_type == PluginType.EXPORTER:
            return cls._build_file_collector_json(define=define, with_os_prefix=True, bk_tenant_id=bk_tenant_id)

        if plugin_type == PluginType.DATADOG:
            collector_json = cls._build_file_collector_json(
                define=define, with_os_prefix=False, bk_tenant_id=bk_tenant_id
            )
            collector_json["config_yaml"] = define.get("config_yaml", "")
            collector_json["datadog_check_name"] = define.get("datadog_check_name", "")
            return collector_json

        if plugin_type == PluginType.SCRIPT:
            return {os_type: config for os_type, config in define.items() if os_type in OS_TYPE_TO_DIRNAME}

        if plugin_type == PluginType.JMX:
            config_yaml_path = cls._find_file_by_basename(filename_dict, "config.yaml.tpl")
            if not config_yaml_path:
                raise PluginParseError({"msg": _("无法获取JMX对应的配置文件")})
            return {"config_yaml": filename_dict[config_yaml_path].decode("utf-8")}

        if plugin_type == PluginType.SNMP:
            config_yaml_path = cls._find_file_by_basename(filename_dict, "config.yaml.tpl")
            if not config_yaml_path:
                raise PluginParseError({"msg": _("无法获取SNMP对应的配置文件")})
            content = yaml.load(filename_dict[config_yaml_path], Loader=yaml.FullLoader)
            content["if_mib"].pop("auth", None)
            return {
                "snmp_version": content["if_mib"].pop("version"),
                "filename": "snmp.yaml",
                "config_yaml": yaml.dump(content),
            }

        if plugin_type == PluginType.PUSHGATEWAY:
            return {}

        return define

    @classmethod
    def _build_import_payload(
        cls,
        parsed_params: CreatePluginParams,
        filename_dict: dict[Path, bytes],
        plugin_type: str,
        meta_dict: dict[str, Any],
        bk_tenant_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        # 直接返回导入结果需要的扁平参数，避免再构造一层伪版本对象去兼容旧结构。
        collector_json = cls._build_legacy_collector_json(
            parsed_params=parsed_params,
            filename_dict=filename_dict,
            plugin_type=plugin_type,
            bk_tenant_id=bk_tenant_id,
        )
        signature = cls.get_signature(filename_dict=filename_dict, plugin_id=parsed_params.id)
        imported_meta = {
            "plugin_id": parsed_params.id,
            "plugin_type": plugin_type,
            "tag": meta_dict.get("tag", "") or "",
            "label": parsed_params.label,
            "os_type_list": cls.get_os_type_list(filename_dict),
        }
        imported_config = {
            "config_json": [param.model_dump() for param in parsed_params.params],
            "collector_json": collector_json,
            "is_support_remote": parsed_params.is_support_remote,
        }
        imported_info = {
            "plugin_display_name": parsed_params.name,
            "metric_json": [metric.model_dump() for metric in parsed_params.metrics],
            "description_md": parsed_params.description_md,
            "logo": cls._strip_logo_prefix(parsed_params.logo),
            "enable_field_blacklist": True,
        }
        imported_version = {
            "config_version": parsed_params.version.major,
            "info_version": parsed_params.version.minor,
            "signature": signature,
            "version_log": parsed_params.version_log,
        }
        return imported_meta, imported_config, imported_info, imported_version

    @staticmethod
    def _build_import_version(imported_version: dict[str, Any]) -> str:
        return f"{imported_version['config_version']}.{imported_version['info_version']}"

    @staticmethod
    def _build_import_config_dict(imported_config: dict[str, Any]) -> dict[str, Any]:
        collector_json = copy.deepcopy(imported_config["collector_json"])
        collector_json.pop("diff_fields", None)
        return {
            "config_json": imported_config["config_json"],
            "collector_json": collector_json,
            "is_support_remote": imported_config["is_support_remote"],
        }

    @staticmethod
    def _build_import_info_dict(imported_info: dict[str, Any]) -> dict[str, Any]:
        return {
            "plugin_display_name": imported_info["plugin_display_name"],
            "description_md": imported_info["description_md"],
            "logo": imported_info["logo"],
            "metric_json": imported_info["metric_json"],
            "enable_field_blacklist": imported_info["enable_field_blacklist"],
        }

    @staticmethod
    def _normalize_collector_json_for_compare(config_value: dict[str, Any]) -> dict[str, Any]:
        collector_json = config_value.get("collector_json", {})
        if collector_json is not None:
            for config in list(collector_json.values()):
                if isinstance(config, dict):
                    # 避免导入包和原插件内容一致但文件名不同导致误判。
                    config.pop("file_name", None)
                    config.pop("file_id", None)
                    if config.get("script_content_base64") and isinstance(config["script_content_base64"], bytes):
                        config["script_content_base64"] = str(config["script_content_base64"], encoding="utf-8")
        return config_value

    @staticmethod
    def _is_imported_plugin_official(imported_meta: dict[str, Any]) -> bool:
        return imported_meta["plugin_id"].startswith("bkplugin_")

    @classmethod
    def _build_import_create_params(
        cls,
        imported_meta: dict[str, Any],
        imported_config: dict[str, Any],
        imported_info: dict[str, Any],
        imported_version: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            **cls._build_import_config_dict(imported_config),
            **cls._build_import_info_dict(imported_info),
            "plugin_id": imported_meta["plugin_id"],
            "plugin_type": imported_meta["plugin_type"],
            "tag": imported_meta["tag"],
            "label": imported_meta["label"],
            "signature": dump_plugin_signature_to_yaml(imported_version["signature"]),
            "config_version": imported_version["config_version"],
            "info_version": imported_version["info_version"],
            "version_log": imported_version["version_log"],
            "is_official": cls._is_imported_plugin_official(imported_meta),
            "is_safety": cls._check_imported_is_safety(imported_meta, imported_config, imported_info, imported_version),
            "related_conf_count": 0,
        }

    @classmethod
    def _check_imported_is_safety(
        cls,
        imported_meta: dict[str, Any],
        imported_config: dict[str, Any],
        imported_info: dict[str, Any],
        imported_version: dict[str, Any],
    ) -> bool:
        """基于导入的扁平字段构造临时 MetricPlugin 并调用 verify_plugin_signature 判断 is_safety。"""
        from bk_monitor_base.domains.metric_plugin.define import MetricPlugin, MetricPluginParams, VersionTuple

        signature_dict = imported_version.get("signature", {})
        if not signature_dict or not isinstance(signature_dict, dict):
            return False

        try:
            params = [MetricPluginParams(**p) for p in (imported_config.get("config_json") or [])]
            plugin = MetricPlugin(
                bk_tenant_id="default",
                bk_biz_id=0,
                id=imported_meta.get("plugin_id", ""),
                type=imported_meta.get("plugin_type", ""),
                name=imported_info.get("plugin_display_name", ""),
                description_md=imported_info.get("description_md", ""),
                params=params,
                define=imported_config.get("collector_json", {}),
                is_support_remote=imported_config.get("is_support_remote", False),
                version_log=imported_version.get("version_log", ""),
                version=VersionTuple(
                    imported_version.get("config_version", 1), imported_version.get("info_version", 0)
                ),
            )
            os_type_list = imported_version.get("os_type_list", ["linux"])
            return verify_plugin_signature(plugin, os_type_list, signature_dict, "safety")
        except Exception:
            return False

    @classmethod
    def check_conflict_mes(
        cls,
        create_params: dict[str, Any],
        current_version: PluginVersionHistory | None,
        imported_meta: dict[str, Any],
        imported_config: dict[str, Any],
        imported_info: dict[str, Any],
        imported_version: dict[str, Any],
    ) -> None:
        create_params["conflict_ids"] = []
        imported_version_text = cls._build_import_version(imported_version)
        imported_is_official = cls._is_imported_plugin_official(imported_meta)
        if not current_version:
            create_params["conflict_detail"] = f"""已经存在重名的插件, 上传的插件版本为: {imported_version_text}"""
            return
        if current_version.is_official:
            if imported_is_official:
                create_params["conflict_detail"] = (
                    f"""导入插件包版本为：{imported_version_text}；已有插件版本为：{current_version.version}"""
                )
                cls.check_conflict_title(
                    create_params=create_params,
                    current_version=current_version,
                    imported_meta=imported_meta,
                    imported_config=imported_config,
                    imported_info=imported_info,
                    imported_version=imported_version,
                )
                if not create_params["conflict_title"]:
                    create_params["conflict_detail"] = ""
                    create_params["duplicate_type"] = None
            else:
                create_params["conflict_detail"] = (
                    f"""导入插件包为非官方插件, 版本为: {imported_version_text}；当前插件为官方插件，版本为：{current_version.version}"""
                )
                cls.check_conflict_title(
                    create_params=create_params,
                    current_version=current_version,
                    imported_meta=imported_meta,
                    imported_config=imported_config,
                    imported_info=imported_info,
                    imported_version=imported_version,
                )
        else:
            if imported_is_official:
                create_params["conflict_detail"] = (
                    f"""导入插件包为官方插件，版本为：{imported_version_text}；当前插件为非官方插件，版本为：{current_version.version}"""
                )
            else:
                create_params["conflict_detail"] = (
                    f"""导入插件包版本为: {imported_version_text}；当前插件版本为: {current_version.version}"""
                )
                cls.check_conflict_title(
                    create_params=create_params,
                    current_version=current_version,
                    imported_meta=imported_meta,
                    imported_config=imported_config,
                    imported_info=imported_info,
                    imported_version=imported_version,
                )

    @classmethod
    def check_conflict_title(
        cls,
        create_params: dict[str, Any],
        current_version: PluginVersionHistory,
        imported_meta: dict[str, Any],
        imported_config: dict[str, Any],
        imported_info: dict[str, Any],
        imported_version: dict[str, Any],
    ) -> None:
        conflict_list = []
        conflict_ids = []

        create_params["conflict_title"] = ""
        imported_version_text = cls._build_import_version(imported_version)
        if cls._is_imported_plugin_official(imported_meta) and current_version.is_official:
            if StrictVersion(imported_version_text) <= StrictVersion(current_version.version):
                conflict_list.append(ConflictMap.VersionBelow.info)
                conflict_ids.append(ConflictMap.VersionBelow.id)
        else:
            if current_version.plugin.plugin_type != imported_meta["plugin_type"] and current_version.is_release:
                conflict_list.append(ConflictMap.PluginType.info)
                conflict_ids.append(ConflictMap.PluginType.id)
            if (
                current_version.config.is_support_remote != imported_config["is_support_remote"]
                and current_version.is_release
            ):
                conflict_list.append(ConflictMap.RemoteCollectorConfig.info)
                conflict_ids.append(ConflictMap.RemoteCollectorConfig.id)
            # 判断重名的非官方插件是否已经下发了采集任务（包含历史版本）
            # 新增跳过采集关联判断。 支持通过配置环境变量`BKAPP_PLUGIN_SKIP_RELATED_CHECK`跳过
            skip_related_check = os.getenv("BKAPP_PLUGIN_SKIP_RELATED_CHECK")
            if not skip_related_check and current_version.collecting_config_total > 0:
                conflict_list.append(
                    ConflictMap.RelatedCollectorConfig.info % (current_version.collecting_config_total)
                )
                conflict_ids.append(ConflictMap.RelatedCollectorConfig.id)

        old_config_data = copy.deepcopy(current_version.config.config2dict())
        tmp_config_data = copy.deepcopy(cls._build_import_config_dict(imported_config))
        old_config_data, tmp_config_data = list(
            map(cls._normalize_collector_json_for_compare, [old_config_data, tmp_config_data])
        )
        old_info_data = current_version.info.info2dict()
        tmp_info_data = cls._build_import_info_dict(imported_info)
        old_config_md5, new_config_md5, old_info_md5, new_info_md5 = list(
            map(count_md5, [old_config_data, tmp_config_data, old_info_data, tmp_info_data])
        )
        if (
            old_config_md5 == new_config_md5
            and old_info_md5 == new_info_md5
            and (imported_meta["tag"] == current_version.plugin.tag)
        ):
            conflict_list.append(ConflictMap.DuplicatedPlugin.info)
            conflict_ids.append(ConflictMap.DuplicatedPlugin.id)
        if conflict_list:
            create_params["conflict_title"] += _(", 且").join(conflict_list)
            create_params["conflict_ids"] = conflict_ids

    @staticmethod
    def check_duplicate(plugin_id: str) -> tuple[PluginVersionHistory | None, str | None]:
        try:
            resource.plugin.check_plugin_id({"plugin_id": plugin_id})
        except PluginIDExist:
            try:
                # 判断是否当前数据库存在重名
                current_version = CollectorPluginMeta.objects.get(
                    bk_tenant_id=get_request_tenant_id(), plugin_id=plugin_id
                ).current_version
                return current_version, "official" if current_version.is_official else "custom"
            except CollectorPluginMeta.DoesNotExist:
                return None, "custom"
        return None, None

    @classmethod
    def _parse_import_context(cls, validated_request_data: dict[str, Any]) -> _PluginImportContext:
        context = _PluginImportContext(tmp_path=os.path.join(settings.MEDIA_ROOT, "plugin", str(uuid4())))
        package_content = validated_request_data["file_data"].read()
        try:
            # 先保留原始压缩包内容给 base 侧解析，同时在资源层读取少量文件用于兼容旧字段转换。
            context.filename_dict = cls.un_tar_gz_file(BytesIO(package_content))
            context.plugin_id, context.plugin_type, context.meta_dict = cls.get_plugin(context.filename_dict)

            package_dir = Path(context.tmp_path)
            package_dir.mkdir(parents=True, exist_ok=True)
            package_file_path = package_dir / Path(validated_request_data["file_data"].name).name
            package_file_path.write_bytes(package_content)

            parsed_params = parse_metric_plugin_package(
                bk_tenant_id=cast(str, get_request_tenant_id()),
                package_file=package_file_path,
                operator=cast(str, get_request_username()),
            )
            (
                context.imported_meta,
                context.imported_config,
                context.imported_info,
                context.imported_version,
            ) = cls._build_import_payload(
                parsed_params=parsed_params,
                filename_dict=context.filename_dict,
                plugin_type=context.plugin_type,
                meta_dict=context.meta_dict,
                bk_tenant_id=cast(str, get_request_tenant_id()),
            )
            context.plugin_id = context.imported_meta["plugin_id"]
            context.plugin_type = context.imported_meta["plugin_type"]
            context.current_version, context.create_params["duplicate_type"] = cls.check_duplicate(context.plugin_id)
            if context.create_params["duplicate_type"]:
                cls.check_conflict_mes(
                    create_params=context.create_params,
                    current_version=context.current_version,
                    imported_meta=context.imported_meta,
                    imported_config=context.imported_config,
                    imported_info=context.imported_info,
                    imported_version=context.imported_version,
                )
        except PluginParseError:
            raise
        except Exception as err:
            raise PluginParseError({"msg": str(err)})
        finally:
            shutil.rmtree(context.tmp_path, ignore_errors=True)

        # 输出阶段继续保持旧接口字段名，避免前端和无前端导入链路一起改协议。
        context.create_params.update(
            cls._build_import_create_params(
                imported_meta=context.imported_meta,
                imported_config=context.imported_config,
                imported_info=context.imported_info,
                imported_version=context.imported_version,
            )
        )
        return context

    def perform_request(self, validated_request_data):
        return self._parse_import_context(validated_request_data).create_params


class CheckPluginIDResource(Resource):
    """检查插件ID是否合法"""

    class RequestSerializer(serializers.Serializer):
        plugin_id = serializers.CharField(label="插件ID")

    def perform_request(self, validated_request_data):
        bk_tenant_id = cast(str, get_request_tenant_id())
        plugin_id = validated_request_data["plugin_id"].strip()

        try:
            check_metric_plugin_id(bk_tenant_id=bk_tenant_id, plugin_id=plugin_id)
        except PluginIDExistsError:
            raise PluginIDExist({"msg": plugin_id})
        except PluginIDInvalidError as e:
            raise PluginIDFormatError({"msg": str(e)})


class SaveAndReleasePluginResource(Resource):
    """
    导入保存并发布插件。

    这个 Resource 负责承接“导入结果落库”这一步，统一编排 base 侧的创建、注册、更新和发布能力。
    当前策略分成两条分支：

    1. 插件不存在：按“创建 -> 注册 -> 发布”完整执行。
    2. 插件已存在：只允许更新次要版本字段，然后直接发布；如果主配置发生变化则直接报错。

    这里刻意不通过修改 `self.RequestSerializer` 来切换 serializer，
    避免 Resource 实例上残留动态状态，保持请求校验逻辑更接近纯函数。
    """

    SERIALIZERS: dict[str, type[Serializer]] = {
        CollectorPluginMeta.PluginType.EXPORTER: ExporterSerializer,
        CollectorPluginMeta.PluginType.JMX: JmxSerializer,
        CollectorPluginMeta.PluginType.SCRIPT: ScriptSerializer,
        CollectorPluginMeta.PluginType.PUSHGATEWAY: PushgatewaySerializer,
        CollectorPluginMeta.PluginType.DATADOG: DataDogSerializer,
        CollectorPluginMeta.PluginType.SNMP: SNMPSerializer,
    }

    @classmethod
    def _get_request_serializer(cls, plugin_type: str) -> type[Serializer]:
        """
        根据插件类型选择请求 serializer。

        `save_and_release_plugin` 需要复用各插件类型原有的入参校验规则，
        但这里不把选择结果挂到实例属性上，避免请求间状态污染。
        """
        serializer_class = cls.SERIALIZERS.get(plugin_type)
        if serializer_class is None:
            raise UnsupportedPluginTypeError({"plugin_type", plugin_type})
        return serializer_class

    @staticmethod
    def _build_version(validated_request_data: dict[str, Any]) -> VersionTuple:
        """从旧接口字段中提取 base 侧统一使用的版本对象。"""
        return VersionTuple(
            major=validated_request_data["config_version"],
            minor=validated_request_data["info_version"],
        )

    @staticmethod
    def _dump_param(param: Any) -> Any:
        """
        将参数对象归一化为可比较的 dict。

        base 领域模型中的 `params` 可能是 pydantic model，也可能已经是普通 dict，
        这里统一摊平成原生结构，避免比较时被对象类型差异干扰。
        """
        if hasattr(param, "model_dump"):
            return param.model_dump()
        return param

    @classmethod
    def _has_major_config_change(cls, current_plugin: Any, validated_request_data: dict[str, Any]) -> bool:
        """
        判断本次请求是否触发主配置变更。

        当前改造约束下，只有以下三类字段允许保持不变并执行 minor update：
        - `config_json` 对应 base 的 `params`
        - `collector_json` 对应 base 的 `define`
        - `is_support_remote`

        只要上述任一项变化，就说明已经超出“更新次要版本信息”的范围。
        """
        current_params = [cls._dump_param(param) for param in getattr(current_plugin, "params", [])]
        is_support_remote = validated_request_data.get("is_support_remote", False)
        return any(
            [
                current_params != validated_request_data["config_json"],
                getattr(current_plugin, "define", {}) != validated_request_data["collector_json"],
                getattr(current_plugin, "is_support_remote", False) != is_support_remote,
            ]
        )

    @staticmethod
    def _build_minor_update_params(validated_request_data: dict[str, Any]) -> UpdatePluginVersionParams:
        """
        将旧接口字段映射为 base 侧的 minor update 参数。

        这里仅包含允许更新的次要字段，不携带 `params/define/is_support_remote`，
        从而和上面的主配置变更约束保持一致。
        """
        return UpdatePluginVersionParams(
            name=validated_request_data["plugin_display_name"],
            description_md=validated_request_data["description_md"],
            label=validated_request_data["label"],
            logo=validated_request_data["logo"],
            metrics=SaveMetricResource._build_metric_groups(validated_request_data["metric_json"]),
            enable_metric_discovery=validated_request_data.get("enable_field_blacklist", True),
            version_log=validated_request_data.get("version_log", ""),
        )

    def validate_request_data(self, request_data):
        """
        使用插件类型对应的 serializer 做入参校验。

        这里复用了 `Resource.validate_request_data` 的错误格式，但把 serializer 的选择下沉到局部变量，
        避免通过修改 `self.RequestSerializer` 来切换类型。
        """
        serializer_class = self._get_request_serializer(request_data.get("plugin_type"))
        request_serializer = serializer_class(data=request_data, many=self.many_request_data)
        self._request_serializer = request_serializer
        if not request_serializer.is_valid():
            logger.error(
                f"Resource[{self.get_resource_name()}] 请求参数格式错误：%s",
                format_serializer_errors(request_serializer),
            )
            raise CustomException(
                _("Resource[{}] 请求参数格式错误：{}").format(
                    self.get_resource_name(), format_serializer_errors(request_serializer)
                )
            )
        return request_serializer.validated_data

    @atomic
    def perform_request(self, validated_request_data):
        """
        保存并发布插件。

        流程说明：
        - 先尝试走创建分支；如果插件不存在，沿用“创建 -> 注册 -> 发布”链路。
        - 如果创建阶段提示插件已存在，则转入更新分支。
        - 更新分支只允许 minor update；主配置变化直接报错，避免当前阶段误创建新主版本。
        """
        bk_tenant_id = cast(str, get_request_tenant_id())
        operator = cast(str, get_request_username())
        plugin_id = validated_request_data["plugin_id"]

        try:
            # 新建插件时复用已经 base 化的 create_plugin 逻辑；
            # 该步骤会返回注册和发布所需的版本信息。
            register_params = resource.plugin.create_plugin(**validated_request_data)
        except PluginIDExist:
            # 插件已存在时，不再走旧 manager 的 update_version/release，
            # 而是显式转成 base 侧的“minor update + release”链路。
            version = self._build_version(validated_request_data)
            current_plugin = get_metric_plugin(
                bk_tenant_id=bk_tenant_id,
                plugin_id=plugin_id,
                version=version,
            )
            if self._has_major_config_change(current_plugin, validated_request_data):
                # TODO: 主配置发生变化时，需要自动创建新主版本后再执行注册和发布。
                raise ExportImportError(
                    {"msg": "当前仅支持更新次要版本参数，请保持采集配置、采集器定义和远程采集配置不变"}
                )

            # minor update 只修改展示信息、指标定义等次要字段，不重新注册插件包。
            update_metric_plugin_version(
                bk_tenant_id=bk_tenant_id,
                plugin_id=plugin_id,
                version=version,
                operator=operator,
                params=self._build_minor_update_params(validated_request_data),
            )
            # release 在 base 侧具备幂等性，因此这里可以直接发布目标版本。
            release_metric_plugin_version(
                bk_tenant_id=bk_tenant_id,
                plugin_id=plugin_id,
                version=version,
                operator=operator,
            )
            return True

        # 创建成功后仍需先注册插件包，再发布该版本。
        resource.plugin.plugin_register(**register_params)
        release_metric_plugin_version(
            bk_tenant_id=bk_tenant_id,
            plugin_id=register_params["plugin_id"],
            version=VersionTuple(
                major=register_params["config_version"],
                minor=register_params["info_version"],
            ),
            operator=operator,
        )
        return True


class GetReservedWordResource(Resource):
    def perform_request(self, validated_request_data):
        return {
            "RT_RESERVED_WORD_EXACT": RT_RESERVED_WORD_EXACT,
            "RT_RESERVED_WORD_FUZZY": RT_RESERVED_WORD_FUZZY,
            "RT_TABLE_NAME_WORD_EXACT": RT_TABLE_NAME_WORD_EXACT,
        }


class PluginUpgradeInfoResource(Resource):
    """
    获取插件参数配置和版本发行历史
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        plugin_id = serializers.CharField(required=True, label="插件id")
        config_id = serializers.CharField(required=True, label="配置id")
        config_version = serializers.IntegerField(required=True, label="插件版本")
        info_version = serializers.IntegerField(required=True, label="插件信息版本")

    def perform_request(self, data):
        plugin = CollectorPluginMeta.objects.filter(
            bk_tenant_id=get_request_tenant_id(), plugin_id=data["plugin_id"]
        ).first()
        if plugin is None:
            raise PluginIDNotExist
        # 获取当前插件版本与最新版本之间的发行历史
        plugin_version_list = plugin.versions.filter(
            stage=PluginVersionHistory.Stage.RELEASE,
            config_version__gte=data["config_version"],
            info_version__gte=data["info_version"],
        ).order_by("-id")

        if not plugin_version_list:
            raise PluginVersionNotExist

        initial_version = plugin.initial_version
        newest_version = plugin.release_version

        version_log_list = []
        for plugin_version in plugin_version_list:
            if not plugin_version.version_log:
                if plugin_version == initial_version:
                    version_log = _("该插件诞生了!")
                else:
                    version_log = _("用户很懒,没有说明哦.")
            else:
                version_log = plugin_version.version_log
            version_log_list.append({"version": plugin_version.version, "version_log": version_log})

        config_id = data["config_id"]
        config_detail = resource.collecting.collect_config_detail(id=config_id, bk_biz_id=data["bk_biz_id"])
        runtime_params_dict = {}

        def param_key(param):
            return "{}|{}|{}".format(param.get("key", param["name"]), param["type"], param["mode"])

        config_json = config_detail["plugin_info"]["config_json"]
        if config_detail["collect_type"] == PluginType.SNMP:
            for key, item in enumerate(config_json):
                if item.get("auth_json"):
                    config_json.extend(config_json.pop(key).pop("auth_json"))
                    break
        for item in config_json:
            p_type = item["mode"] if item["mode"] == "collector" else "plugin"
            p_name = item.get("key", item["name"])
            p_value = config_detail["params"].get(p_type, {}).get(p_name)
            if p_value is not None:
                runtime_params_dict[param_key(item)] = p_value

        runtime_params = []
        for item in newest_version.config.config_json:
            if item.get("auth_json", []):
                for auth in item["auth_json"]:
                    auth["value"] = runtime_params_dict.get(param_key(auth), auth["default"])
            else:
                item["value"] = runtime_params_dict.get(param_key(item), item["default"])
            runtime_params.append(item)

        return {
            "runtime_params": runtime_params,
            "version_log": version_log_list,
            "plugin_id": data["plugin_id"],
            "plugin_display_name": newest_version.info.plugin_display_name,
            "plugin_version": "{}.{}".format(data["config_version"], data["info_version"]),
        }


class PluginImportWithoutFrontendResource(PluginImportResource):
    class RequestSerializer(PluginImportResource.RequestSerializer):
        operator = serializers.CharField(required=True)
        metric_json = serializers.JSONField(required=False, default={})

    def perform_request(self, validated_request_data):
        operator = validated_request_data.pop("operator")
        import_context = self._parse_import_context(validated_request_data)
        create_params = import_context.create_params
        current_version = import_context.current_version
        plugin_id = import_context.plugin_id
        plugin_type = import_context.plugin_type
        imported_version = import_context.imported_version

        create_params["bk_biz_id"] = validated_request_data["bk_biz_id"]

        # 覆盖metric_json
        if validated_request_data.get("metric_json"):
            create_params["metric_json"] = validated_request_data["metric_json"]

        # 避免节点管理存在，数据库不存在时报错
        if current_version:
            # 判断插件id是否在table_id，不在的话，抛错提示
            tables = PluginDataAccessor(current_version, operator=operator).contrast_rt()[1]
            # 避免插件id大写引起的问题
            if create_params["plugin_id"].lower() not in list(tables.keys())[0]:
                raise ExportImportError({"msg": "导入插件id与table_id不一致"})
        if create_params["logo"]:
            create_params["logo"] = ",".join(["data:image/png;base64", create_params["logo"].decode("utf8")])
        if isinstance(create_params["signature"], bytes):
            create_params["signature"] = create_params["signature"].decode("utf8")
        if create_params["plugin_type"] == PluginType.SCRIPT:
            for k, v in create_params["collector_json"].items():
                v["script_content_base64"] = v["script_content_base64"].decode("utf8")
        save_resource = SaveAndReleasePluginResource()
        # 业务变更,单>单不允许，单>全允许，全>单需要判断
        if current_version and create_params["bk_biz_id"] != current_version.plugin.bk_biz_id:
            if current_version.plugin.bk_biz_id and create_params["bk_biz_id"]:
                raise BizChangedError

            # 全>单判断是否有关联项
            if not current_version.plugin.bk_biz_id:
                collect_config = CollectConfigMeta.objects.filter(
                    bk_tenant_id=get_request_tenant_id(), plugin_id=plugin_id
                )
                if collect_config and [x for x in collect_config if x.bk_biz_id != create_params["bk_biz_id"]]:
                    raise RelatedItemsExist({"msg": "存在其余业务的关联项"})

        # 1.首次导入
        # 2.数据库不存在，节点管理存在时
        if (
            not create_params["duplicate_type"]
            or "已经存在重名的插件, 上传的插件版本为" in create_params["conflict_detail"]
        ):
            return save_resource.request(create_params)
        else:
            # 导入与原有插件完全一致
            if str(ConflictMap.DuplicatedPlugin.info) in create_params["conflict_title"]:
                return True
            # 只有数据库不存在，节点管理存在时conflict_title才会提示不同类型冲突，需要额外判断上传的包里插件类型与数据库中类型是否一致
            if (
                str(ConflictMap.DuplicatedPlugin.info) in create_params["conflict_title"]
                or current_version.plugin.plugin_type != plugin_type
            ):
                raise ExportImportError({"msg": "导入插件类型冲突"})
            if str(ConflictMap.RemoteCollectorConfig.info) in create_params["conflict_title"]:
                if current_version.config.is_support_remote:
                    raise ExportImportError({"msg": "已存在插件支持远程采集，导入插件不能关闭"})
            # 版本小于等于当前版本
            if StrictVersion(self._build_import_version(imported_version)) < StrictVersion(current_version.version):
                # 无前端导入覆盖时继续沿用旧行为：低版本包允许覆盖，但最终按当前高版本号落库。
                imported_version["config_version"] = create_params["config_version"] = current_version.config_version
                imported_version["info_version"] = create_params["info_version"] = current_version.info_version
            return save_resource.request(create_params)


class ProcessCollectorDebugResource(Resource):
    """
    进程采集数据 debug 接口
    """

    class RequestSerializer(serializers.Serializer):
        processes = serializers.CharField(required=True)
        match = serializers.CharField(required=True, allow_blank=True, allow_null=True)
        exclude = serializers.CharField(required=True, allow_blank=True, allow_null=True)
        dimensions = serializers.CharField(required=True, allow_blank=True, allow_null=True)
        process_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def perform_request(self, validated_request_data: dict):
        # 参数正则校验
        def _validate_regex(value_: str):
            """通用正则表达式验证方法"""
            if value_:
                try:
                    re.compile(value_)
                except re.error:
                    return False
            return True

        # 在此对参数进行正则校验
        for field_name in ["exclude", "dimensions", "process_name"]:
            value = validated_request_data.get(field_name, "")
            if value:
                if not _validate_regex(value):
                    raise RegexParseError({"msg": f"对应字字段为 {field_name}"})

        # 获取当前目录
        current_dir = Path(__file__).parent
        cmd_path = current_dir / "process_matcher" / "bin" / "process_matcher"

        # 提取参数
        match = validated_request_data.get("match", "")
        exclude = validated_request_data.get("exclude", "")
        dimensions = validated_request_data.get("dimensions", "")
        process_name = validated_request_data.get("process_name", "")
        processes = validated_request_data.get("processes", "")

        # 执行命令
        cmd_args = [
            str(cmd_path),
            f"--match={match}",
            f"--exclude={exclude}",
            f"--dimensions={dimensions}",
            f"--process_name={process_name}",
            f"--processes={processes}",
        ]
        try:
            result = subprocess.run(cmd_args, check=True, capture_output=True, text=True, timeout=15)
        except subprocess.TimeoutExpired as e:
            # 调用超时
            logger.error(f"Process matcher command timed out, error_message: {e}")
            raise SubprocessCallError({"msg": "Process matcher command timed out"})
        except subprocess.CalledProcessError as e:
            # 命令执行失败
            logger.error(f"Process matcher failed with code {e.returncode}: {e.stderr}")
            raise SubprocessCallError({"msg": f"Process matcher command failed, error_message: {e.stderr}"})
        except Exception as e:
            # 未知错误
            logger.error(f"Unexpected error executing process matcher: {e}")
            raise SubprocessCallError({"msg": f"Process matcher command failed, error_message: {e}"})

        # 返回结果
        try:
            # 解析 JSON 输出并返回结构化数据
            # 如果直接返回 result.stdout， 则会包含多余的转义字符， 所以这里先反序列化
            json_result = json.loads(result.stdout.strip())
            return json_result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse process matcher output: {e}")
            raise JsonParseError({"msg": f"json解析 stdout 失败: {e}"})
