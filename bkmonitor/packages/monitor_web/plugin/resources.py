"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
# pylint: disable=W

import base64
import copy
import hashlib
import logging
import os
import re
import shutil
import tarfile
import time
import pathlib
import subprocess
import json
from collections import namedtuple
from distutils.version import StrictVersion
from uuid import uuid4

import yaml
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import IntegrityError
from django.db.transaction import atomic
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from rest_framework import serializers

from bkmonitor.utils.common_utils import safe_int
from bkmonitor.utils.request import get_request, get_request_tenant_id
from bkmonitor.utils.serializers import MetricJsonBaseSerializer
from constants.result_table import (
    RT_RESERVED_WORD_EXACT,
    RT_RESERVED_WORD_FUZZY,
    RT_TABLE_NAME_WORD_EXACT,
)
from core.drf_resource import Resource, api, resource
from core.drf_resource.tasks import step
from core.errors.api import BKAPIError
from core.errors.export_import import ExportImportError
from core.errors.plugin import (
    BizChangedError,
    MetricNumberError,
    PluginIDExist,
    PluginIDFormatError,
    PluginIDNotExist,
    PluginParseError,
    PluginVersionNotExist,
    RegisterPackageError,
    RelatedItemsExist,
    SNMPMetricNumberError,
    UnsupportedPluginTypeError,
    RegexParseError,
    SubprocessCallError,
    JsonParseError,
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
    NodemanRegisterStatus,
    PluginType,
)
from monitor_web.plugin.manager import PluginFileManagerFactory, PluginManagerFactory
from monitor_web.plugin.manager.base import check_skip_debug
from monitor_web.plugin.manager.datadog import DataDogPluginFileManager
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
from monitor_web.plugin.signature import Signature
from utils import count_md5

logger = logging.getLogger(__name__)


class PluginFileUploadResource(Resource):
    class RequestSerializer(serializers.Serializer):
        file_data = serializers.FileField(required=True)
        file_name = serializers.CharField(required=False)
        plugin_id = serializers.CharField(required=False)
        plugin_type = serializers.CharField(required=True)
        os = serializers.CharField(required=True)

    def perform_request(self, validated_request_data):
        validated_request_data.setdefault("file_name", validated_request_data["file_data"].name)
        plugin_type = validated_request_data.get("plugin_type", CollectorPluginMeta.PluginType.EXPORTER)
        plugin_file_manager = PluginFileManagerFactory.get_manager(plugin_type)
        file_manager = plugin_file_manager.save_file(**validated_request_data)
        plugin_file_manager.valid_file(file_manager.file_obj.file_data, validated_request_data["os"])
        return {
            "file_id": file_manager.file_obj.id,
            "actual_filename": file_manager.file_obj.actual_filename,
            "original_filename": file_manager.file_obj.original_filename,
            "file_md5": file_manager.file_obj.file_md5,
        }


class DataDogPluginUploadResource(Resource):
    class RequestSerializer(serializers.Serializer):
        file_data = serializers.FileField(required=True)
        os = serializers.CharField(required=True)
        plugin_id = serializers.CharField(required=False)

    def perform_request(self, validated_request_data):
        base_path = None
        try:
            file_name = validated_request_data["file_data"].name
            validated_request_data["file_name"] = file_name
            base_path = DataDogPluginFileManager.extract_datadog_file(validated_request_data["file_data"])
            parser_content = DataDogPluginFileManager.parse_plugin_content(base_path, validated_request_data["os"])
            file_info = DataDogPluginFileManager.save_lib(
                base_path,
                parser_content["datadog_check_name"],
                validated_request_data["os"],
                validated_request_data.get("plugin_id"),
            )
            result = dict(parser_content, **file_info)
            return result
        except Exception as err:
            logger.error("[plugin] Upload plugin failed, msg is %s" % str(err))
            raise err
        finally:
            PluginFileManager.clean_dir(base_path)


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

    def delay(self, request_data=None, **kwargs):
        request_data = request_data or kwargs
        self.validate_request_data(request_data)
        return self.apply_async(request_data)

    def perform_request(self, validated_request_data):
        token_list = None
        plugin_id = validated_request_data["plugin_id"]
        plugin_type = validated_request_data["plugin_type"]

        # 对SNMP类型插件进行特殊处理，限制分组数量
        if plugin_type == CollectorPluginMeta.PluginType.SNMP:
            if len(validated_request_data["metric_json"]) > SNMP_MAX_METRIC_NUM:
                raise SNMPMetricNumberError(snmp_max_metric_num=SNMP_MAX_METRIC_NUM)
        else:
            # 计算非SNMP类型插件的指标数量
            metric_num = len(
                [
                    field
                    for metric_json in validated_request_data["metric_json"]
                    for field in metric_json["fields"]
                    if field["monitor_type"] == "metric"
                ]
            )
            # 限制指标数量,不能超过MAX_METRIC_NUM(2000)
            if metric_num > MAX_METRIC_NUM:
                # 超限制之后，将配置写入GlobalConfig，提供更改能力
                config, _ = GlobalConfig.objects.get_or_create(key="MAX_METRIC_NUM", defaults={"value": MAX_METRIC_NUM})
                if metric_num > safe_int(config.value, dft=MAX_METRIC_NUM):
                    raise MetricNumberError(max_metric_num=safe_int(config.value, dft=MAX_METRIC_NUM))
        plugin_manager = PluginManagerFactory.get_manager(
            bk_tenant_id=get_request_tenant_id(), plugin=plugin_id, plugin_type=plugin_type
        )
        config_version, info_version, is_change, need_make = plugin_manager.update_metric(validated_request_data)
        if need_make:
            register_info = {"plugin_id": plugin_id, "config_version": config_version, "info_version": info_version}
            token_list = PluginRegisterResource().request(register_info)["token"]
        plugin_manager.data_access(config_version, info_version)
        res = {"config_version": config_version, "info_version": info_version}
        # todo 已关联的采集配置，更新对应插件版本历史

        if token_list:
            res.update(dict(token=token_list))
        return res


class CreatePluginResource(Resource):
    SERIALIZERS = {
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

    def perform_request(self, params):
        # 新建插件默认开启自动发现
        params["enable_field_blacklist"] = True
        plugin_id = params["plugin_id"]
        plugin_type = params["plugin_type"]
        import_plugin_metric_json = params.get("import_plugin_metric_json")
        with atomic():
            plugin_manager = PluginManagerFactory.get_manager(
                bk_tenant_id=get_request_tenant_id(), plugin=plugin_id, plugin_type=plugin_type
            )
            plugin_manager.validate_config_info(params["collector_json"], params["config_json"])

            try:
                plugin = self.request_serializer.save()
            except IntegrityError:
                raise PluginIDExist({"msg": plugin_id})

            plugin_manager = PluginManagerFactory.get_manager(plugin=plugin)
            version, need_debug = plugin_manager.create_version(params)

            # 如果是新导入的插件，则需要保存其metric_json
            if import_plugin_metric_json:
                version.info.metric_json = import_plugin_metric_json
                version.info.save()

        params["config_version"] = version.config_version
        params["info_version"] = version.info_version
        params["os_type_list"] = version.os_type_list
        params["need_debug"] = check_skip_debug(need_debug)
        params["signature"] = Signature(version.signature).dumps2yaml() if version.signature else ""
        params["enable_field_blacklist"] = True
        return params


class PluginRegisterResource(Resource):
    def __init__(self):
        super().__init__()
        self.plugin_manager = None
        self.RequestSerializer = PluginRegisterRequestSerializer
        self.plugin_id = None
        self.operator = ""

        request = get_request(peaceful=True)
        if request and getattr(request, "user", None):
            self.operator = request.user.username

    def delay(self, request_data=None, **kwargs):
        request_data = request_data or kwargs
        self.validate_request_data(request_data)
        return self.apply_async(request_data)

    def perform_request(self, validated_request_data):
        bk_tenant_id = get_request_tenant_id()
        self.plugin_id = validated_request_data["plugin_id"]
        plugin = CollectorPluginMeta.objects.filter(bk_tenant_id=bk_tenant_id, plugin_id=self.plugin_id).first()
        if plugin is None:
            raise PluginIDNotExist
        config_version = validated_request_data["config_version"]
        info_version = validated_request_data["info_version"]
        version = PluginVersionHistory.objects.filter(
            bk_tenant_id=bk_tenant_id,
            plugin_id=self.plugin_id,
            config_version=config_version,
            info_version=info_version,
        ).first()
        if version is None:
            raise PluginVersionNotExist

        self.plugin_manager = PluginManagerFactory.get_manager(plugin=plugin, operator=self.operator)
        self.plugin_manager.version = version

        # 尝试进行打包、上传和注册操作
        try:
            tar_name = self.make_package()
            file_name = self.upload_file(tar_name)
            self.register_package(file_name)
            plugin_info = api.node_man.plugin_info(name=self.plugin_id, version=version.version)
            token_list = [i["md5"] for i in plugin_info]
            token_list.sort()
            release_version = self.plugin_manager.plugin.release_version
            if release_version is None or release_version.config_version != config_version:
                self.register_template(tar_name)

            version.stage = "debug"
            version.is_packaged = True
            version.save()
        except Exception as e:
            logger.exception(e)
            raise RegisterPackageError({"msg": str(e)})
        finally:
            # 清理临时文件夹
            if os.path.exists(self.plugin_manager.tmp_path):
                shutil.rmtree(self.plugin_manager.tmp_path)

        return {"token": token_list}

    @step(state="MAKE_PACKAGE", message=_lazy("文件正在打包中..."))
    def make_package(self):
        return self.plugin_manager.make_package()

    def get_file_md5(self, file_name):
        hash = hashlib.md5()
        try:
            with open(file_name, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash.update(chunk)
        except OSError:
            return "-1"

        return hash.hexdigest()

    @step(state="UPLOAD_FILE", message=_lazy("文件正在上传中..."))
    def upload_file(self, tar_name):
        # 调用节点管理上传文件接口
        with open(tar_name, "rb") as tf:
            md5 = self.get_file_md5(tar_name)
            if (
                settings.USE_CEPH
                and os.getenv("UPLOAD_PLUGIN_VIA_COS", os.getenv("BKAPP_UPLOAD_PLUGIN_VIA_COS", "")) == "true"
            ):
                default_storage.save(tar_name, tf)
                result = api.node_man.upload_cos(
                    file_name=tf.name.split("/")[-1], download_url=default_storage.url(tar_name), md5=md5
                )
            else:
                result = api.node_man.upload(package_file=tf, md5=md5, module="bkmonitor")
            return result["name"]

    @step(state="REGISTER_PACKAGE", message=_lazy("文件正在注册中..."))
    def register_package(self, file_name):
        """
        注册插件包
        :param file_name:
        :return:
        """
        # 调用插件包注册接口
        result = api.node_man.register_package(file_name=file_name, is_release=False)
        job_id = result["job_id"]
        # 最多轮询300次，每次间隔1s
        to_be_continue = 300
        while to_be_continue > 0:
            # 轮询注册插件包结果
            result = api.node_man.query_register_task(job_id=job_id)

            # 如果节点管理状态为失败，则Raise错误
            if result.get("status") == NodemanRegisterStatus.FAILED:
                logger.error(
                    "register package task({}) result: {} message: {}".format(
                        job_id, NodemanRegisterStatus.FAILED, result["message"]
                    )
                )
                raise RegisterPackageError({"msg": result["message"]})

            if result["is_finish"]:
                logger.info(f"register package task({job_id}) result: {result}")
                break
            time.sleep(1)
            to_be_continue -= 1
        else:
            # 轮询超时
            raise RegisterPackageError({"msg": _("轮询插件包注册任务超时，请检查节点管理celery是否正常运行")})

    @step(state="REGISTER_TEMPLATE", message=_lazy("配置模板正在注册中..."))
    def register_template(self, tar_name):
        params = {
            "plugin_version": "*",
            "version": self.plugin_manager.version.config_version,
            "format": "yaml",
            "is_release_version": False,
            "plugin_name": self.plugin_manager.plugin.plugin_id,
            "file_path": "etc",
        }
        top_path = os.path.dirname(tar_name)
        dir_path = os.path.join(top_path, self.plugin_id)
        yaml_path = os.path.join(dir_path, os.listdir(dir_path)[0], self.plugin_id, "etc")

        for root, dirs, filenames in os.walk(yaml_path):
            for filename in filenames:
                if not filename.endswith(".tpl"):
                    # 不以 .tpl 结尾的，不注册为模板
                    logger.info(f"template name ({filename}) not endswith .tpl, skip")
                    continue
                with open(os.path.join(root, filename), "rb") as f:
                    content = f.read()
                params["name"] = filename.replace(".tpl", "")
                params["content"] = base64.b64encode(content).decode("utf-8")
                params["md5"] = hashlib.md5(content).hexdigest()
                result = api.node_man.create_config_template(**params)
                logger.info("register template({}) result: {}".format(params["name"], result))


class PluginImportResource(Resource):
    INFO_FILENAMES = ("description.md", "config.json", "logo.png", "metrics.json", "signature.yaml", "release.md")
    CollectorFile = namedtuple("CollectorFile", ["name", "data"])

    def __init__(self):
        super().__init__()
        self.tmp_path = os.path.join(settings.MEDIA_ROOT, "plugin", str(uuid4()))
        self.plugin_id = None
        self.filename_list = []
        self.current_version = None
        self.tmp_version = None
        self.plugin_type = None
        self.create_params = {
            "is_official": False,
            "is_safety": False,
            "duplicate_type": None,
            "conflict_detail": "",
            "conflict_title": "",
        }

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        file_data = serializers.FileField(required=True)

    def un_tar_gz_file(self, tar_obj):
        # 解压文件到临时目录
        with tarfile.open(fileobj=tar_obj, mode="r:gz") as tar:
            tar.extractall(self.tmp_path, filter='data')
            self.filename_list = tar.getnames()

    def get_plugin(self):
        meta_yaml_path = ""
        # 获取plugin_id,meta.yaml必要信息
        for filename in self.filename_list:
            path = filename.split("/")
            if (
                len(path) >= 4
                and path[-1] == "meta.yaml"
                and path[-2] == "info"
                and path[-4] in list(OS_TYPE_TO_DIRNAME.values())
            ):
                self.plugin_id = path[-3]
                meta_yaml_path = os.path.join(self.tmp_path, filename)
                break

        if not self.plugin_id:
            raise PluginParseError({"msg": _("无法解析plugin_id")})

        try:
            with open(meta_yaml_path) as f:
                meta_content = f.read()
        except OSError:
            raise PluginParseError({"msg": _("meta.yaml不存在，无法解析")})

        meta_dict = yaml.load(meta_content, Loader=yaml.FullLoader)
        # 检验plugin_type
        plugin_type_display = meta_dict.get("plugin_type")
        for name, display_name in CollectorPluginMeta.PLUGIN_TYPE_CHOICES:
            if display_name == plugin_type_display:
                self.plugin_type = name
                break
        else:
            raise PluginParseError({"msg": _("无法解析插件类型")})

    def check_conflict_mes(self):
        self.create_params["conflict_ids"] = []
        if not self.current_version:
            self.create_params["conflict_detail"] = (
                f"""已经存在重名的插件, 上传的插件版本为: {self.tmp_version.version}"""
            )
            return
        if self.current_version.is_official:
            if self.tmp_version.is_official:
                self.create_params["conflict_detail"] = """导入插件包版本为：{}；已有插件版本为：{}""".format(
                    self.tmp_version.version, self.current_version.version
                )
                self.check_conflict_title()
                if not self.create_params["conflict_title"]:
                    self.create_params["conflict_detail"] = ""
                    self.create_params["duplicate_type"] = None
            else:
                self.create_params["conflict_detail"] = (
                    """导入插件包为非官方插件, 版本为: {}；当前插件为官方插件，版本为：{}""".format(
                        self.tmp_version.version, self.current_version.version
                    )
                )
                self.check_conflict_title()
        else:
            if self.tmp_version.is_official:
                self.create_params["conflict_detail"] = (
                    """导入插件包为官方插件，版本为：{}；当前插件为非官方插件，版本为：{}""".format(
                        self.tmp_version.version, self.current_version.version
                    )
                )
            else:
                self.create_params["conflict_detail"] = """导入插件包版本为: {}；当前插件版本为: {}""".format(
                    self.tmp_version.version, self.current_version.version
                )
                self.check_conflict_title()

    def check_conflict_title(self):
        conflict_list = []
        conflict_ids = []

        def handle_collector_json(config_value):
            for config in list(config_value.get("collector_json", {}).values()):
                if isinstance(config, dict):
                    # 避免导入包和原插件内容一致，文件名不同
                    config.pop("file_name", None)
                    config.pop("file_id", None)
                    if config.get("script_content_base64") and isinstance(config["script_content_base64"], bytes):
                        config["script_content_base64"] = str(config["script_content_base64"], encoding="utf-8")
            return config_value

        self.create_params["conflict_title"] = ""
        if self.tmp_version.is_official and self.current_version.is_official:
            if StrictVersion(self.tmp_version.version) <= StrictVersion(self.current_version.version):
                conflict_list.append(_(ConflictMap.VersionBelow.info))
                conflict_ids.append(ConflictMap.VersionBelow.id)
        else:
            if (
                self.current_version.plugin.plugin_type != self.tmp_version.plugin.plugin_type
                and self.current_version.is_release
            ):
                conflict_list.append(_(ConflictMap.PluginType.info))
                conflict_ids.append(ConflictMap.PluginType.id)
            if (
                self.current_version.config.is_support_remote != self.tmp_version.config.is_support_remote
                and self.current_version.is_release
            ):
                conflict_list.append(_(ConflictMap.RemoteCollectorConfig.info))
                conflict_ids.append(ConflictMap.RemoteCollectorConfig.id)
            # 判断重名的非官方插件是否已经下发了采集任务（包含历史版本）
            # 新增跳过采集关联判断。 支持通过配置环境变量`BKAPP_PLUGIN_SKIP_RELATED_CHECK`跳过
            skip_related_check = os.getenv("BKAPP_PLUGIN_SKIP_RELATED_CHECK")
            if not skip_related_check and self.current_version.collecting_config_total > 0:
                conflict_list.append(
                    _(ConflictMap.RelatedCollectorConfig.info) % (self.current_version.collecting_config_total)
                )
                conflict_ids.append(ConflictMap.RelatedCollectorConfig.id)

        old_config_data = copy.deepcopy(self.current_version.config.config2dict())
        tmp_config_data = copy.deepcopy(self.tmp_version.config.config2dict())
        old_config_data, tmp_config_data = list(map(handle_collector_json, [old_config_data, tmp_config_data]))
        old_info_data = self.current_version.info.info2dict()
        tmp_info_data = self.tmp_version.info.info2dict()
        old_config_md5, new_config_md5, old_info_md5, new_info_md5 = list(
            map(count_md5, [old_config_data, tmp_config_data, old_info_data, tmp_info_data])
        )
        if (
            old_config_md5 == new_config_md5
            and old_info_md5 == new_info_md5
            and (self.tmp_version.plugin.tag == self.current_version.plugin.tag)
        ):
            conflict_list.append(_(ConflictMap.DuplicatedPlugin.info))
            conflict_ids.append(ConflictMap.DuplicatedPlugin.id)
        if conflict_list:
            self.create_params["conflict_title"] += _(", 且").join(conflict_list)
            self.create_params["conflict_ids"] = conflict_ids

    def check_duplicate(self):
        try:
            resource.plugin.check_plugin_id({"plugin_id": self.plugin_id})
        except PluginIDExist:
            try:
                # 判断是否当前数据库存在重名
                self.current_version = CollectorPluginMeta.objects.get(
                    bk_tenant_id=get_request_tenant_id(), plugin_id=self.plugin_id
                ).current_version
                self.create_params["duplicate_type"] = "official" if self.current_version.is_official else "custom"
            except CollectorPluginMeta.DoesNotExist:
                self.create_params["duplicate_type"] = "custom"

    def perform_request(self, validated_request_data):
        try:
            # 解压插件包
            self.un_tar_gz_file(validated_request_data["file_data"])
            # 获取插件ID
            self.get_plugin()
            # 创建插件记录
            import_manager = PluginManagerFactory.get_manager(
                bk_tenant_id=get_request_tenant_id(),
                plugin=self.plugin_id,
                plugin_type=self.plugin_type,
                tmp_path=self.tmp_path,
            )
            self.tmp_version = import_manager.get_tmp_version()
            self.check_duplicate()
            if self.create_params["duplicate_type"]:
                self.check_conflict_mes()
        finally:
            shutil.rmtree(self.tmp_path, ignore_errors=True)
        self.create_params.update(self.tmp_version.config.config2dict())
        self.create_params.update(self.tmp_version.info.info2dict())
        self.create_params.update(
            {
                "plugin_id": self.plugin_id,
                "plugin_type": self.plugin_type,
                "tag": self.tmp_version.plugin.tag,
                "label": self.tmp_version.plugin.label,
                "signature": Signature(self.tmp_version.signature).dumps2yaml(),
                "config_version": self.tmp_version.config_version,
                "info_version": self.tmp_version.info_version,
                "version_log": self.tmp_version.version_log,
                "is_official": self.tmp_version.is_official,
                "is_safety": self.tmp_version.is_safety,
                "related_conf_count": self.tmp_version.get_related_config_count(),
            }
        )

        return self.create_params


class CheckPluginIDResource(Resource):
    class RequestSerializer(serializers.Serializer):
        plugin_id = serializers.CharField(required=True, label="插件ID")

    def perform_request(self, validated_request_data):
        plugin_id = validated_request_data["plugin_id"].strip()

        if len(plugin_id) > 30:
            raise PluginIDFormatError({"msg": _("插件ID长度不能超过30")})
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", plugin_id):
            raise PluginIDFormatError({"msg": _("插件ID只允许包含字母、数字、下划线，且必须以字母开头")})

        if CollectorPluginMeta.origin_objects.filter(
            bk_tenant_id=get_request_tenant_id(), plugin_id=plugin_id
        ).exists():
            raise PluginIDExist({"msg": plugin_id})

        try:
            api.node_man.plugin_info({"name": plugin_id})
        except BKAPIError as e:
            if isinstance(e.data, dict) and e.data.get("code", "") == 3800100:
                # 当code==VALIDATE_REEOR时视为，当前plugin_id在节点管理中不存在
                return None
            else:
                raise e
        else:
            raise PluginIDExist({"msg": plugin_id})


class SaveAndReleasePluginResource(Resource):
    SERIALIZERS = {
        CollectorPluginMeta.PluginType.EXPORTER: ExporterSerializer,
        CollectorPluginMeta.PluginType.JMX: JmxSerializer,
        CollectorPluginMeta.PluginType.SCRIPT: ScriptSerializer,
        CollectorPluginMeta.PluginType.PUSHGATEWAY: PushgatewaySerializer,
        CollectorPluginMeta.PluginType.DATADOG: DataDogSerializer,
        CollectorPluginMeta.PluginType.SNMP: SNMPSerializer,
    }

    def validate_request_data(self, request_data):
        if request_data.get("plugin_type") in self.SERIALIZERS:
            self.RequestSerializer = self.SERIALIZERS[request_data.get("plugin_type")]
        else:
            raise UnsupportedPluginTypeError({"plugin_type", request_data.get("plugin_type")})
        return super().validate_request_data(request_data)

    @atomic
    def perform_request(self, validated_request_data):
        try:
            # 导入创建官方插件
            register_params = resource.plugin.create_plugin(**validated_request_data)
        except PluginIDExist:
            # 更新官方插件
            plugin_id = validated_request_data["plugin_id"]
            plugin = CollectorPluginMeta.objects.get(bk_tenant_id=get_request_tenant_id(), plugin_id=plugin_id)
            plugin_manager = PluginManagerFactory.get_manager(plugin=plugin)
            serializer_class = plugin_manager.serializer_class
            serializer = serializer_class(plugin, data=validated_request_data, partial=True)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            with atomic():
                instance_obj = serializer.save()
                plugin_manager.plugin = instance_obj
                version, need_debug = plugin_manager.update_version(
                    data,
                    data["config_version"],
                    data["info_version"],
                )
            register_params = validated_request_data
            register_params.update(
                {
                    "config_version": version.config_version,
                    "info_version": version.info_version,
                    "os_type_list": version.os_type_list,
                    "stage": version.stage,
                    "need_debug": check_skip_debug(need_debug),
                }
            )

        token_list = resource.plugin.plugin_register(**register_params)
        plugin = CollectorPluginMeta.objects.get(
            bk_tenant_id=get_request_tenant_id(), plugin_id=register_params["plugin_id"]
        )
        plugin_manager = PluginManagerFactory.get_manager(plugin=plugin)
        release_params = {
            "config_version": register_params["config_version"],
            "info_version": register_params["info_version"],
            "token": token_list["token"],
        }
        plugin_manager.release(**release_params)
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


def update_collect_plugin_version(release_version):
    """
    当config不升级，info版本升级时，更新采集配置的插件版本信息
    """
    from monitor_web.models.collecting import CollectConfigMeta

    config_list = CollectConfigMeta.objects.select_related("deployment_config__plugin_version").filter(
        plugin_id=release_version.plugin_id
    )
    for config in config_list:
        if (
            config.deployment_config.plugin_version.config_version == release_version.config_version
            and config.deployment_config.plugin_version.info_version < release_version.info_version
        ):
            config.deployment_config.plugin_version = release_version
            config.deployment_config.save()


class PluginTypeResource(Resource):
    """
    获取插件类型
    """

    def perform_request(self, data):
        plugin_type_list = (
            CollectorPluginMeta.objects.filter(bk_tenant_id=get_request_tenant_id())
            .values_list("plugin_type", flat=True)
            .distinct()
        )
        return list(plugin_type_list)


class PluginImportWithoutFrontendResource(PluginImportResource):
    class RequestSerializer(PluginImportResource.RequestSerializer):
        operator = serializers.CharField(required=True)
        metric_json = serializers.JSONField(required=False, default={})

    def perform_request(self, validated_request_data):
        operator = validated_request_data.pop("operator")
        self.create_params = super().perform_request(validated_request_data)
        self.create_params["bk_biz_id"] = validated_request_data["bk_biz_id"]

        # 覆盖metric_json
        if validated_request_data.get("metric_json"):
            self.create_params["metric_json"] = validated_request_data["metric_json"]

        # 避免节点管理存在，数据库不存在时报错
        if self.current_version:
            # 判断插件id是否在table_id，不在的话，抛错提示
            tables = PluginDataAccessor(self.current_version, operator=operator).tables_info
            # 避免插件id大写引起的问题
            if self.create_params["plugin_id"].lower() not in list(tables.keys())[0]:
                raise ExportImportError({"msg": "导入插件id与table_id不一致"})

        if self.create_params["logo"]:
            self.create_params["logo"] = ",".join(["data:image/png;base64", self.create_params["logo"].decode("utf8")])
        self.create_params["signature"] = self.create_params["signature"].decode("utf8")
        if self.create_params["plugin_type"] == PluginType.SCRIPT:
            for k, v in self.create_params["collector_json"].items():
                v["script_content_base64"] = v["script_content_base64"].decode("utf8")
        save_resource = SaveAndReleasePluginResource()
        # 业务变更,单>单不允许，单>全允许，全>单需要判断
        if self.current_version and self.create_params["bk_biz_id"] != self.current_version.plugin.bk_biz_id:
            if self.current_version.plugin.bk_biz_id and self.create_params["bk_biz_id"]:
                raise BizChangedError

            # 全>单判断是否有关联项
            if not self.current_version.plugin.bk_biz_id:
                collect_config = CollectConfigMeta.objects.filter(
                    bk_tenant_id=get_request_tenant_id(), plugin_id=self.plugin_id
                )
                if collect_config and [x for x in collect_config if x.bk_biz_id != self.create_params["bk_biz_id"]]:
                    raise RelatedItemsExist({"msg": "存在其余业务的关联项"})

        # 1.首次导入
        # 2.数据库不存在，节点管理存在时
        if (
            not self.create_params["duplicate_type"]
            or "已经存在重名的插件, 上传的插件版本为" in self.create_params["conflict_detail"]
        ):
            return save_resource.request(self.create_params)
        else:
            # 导入与原有插件完全一致
            if str(ConflictMap.DuplicatedPlugin.info) in self.create_params["conflict_title"]:
                return True
            # 只有数据库不存在，节点管理存在时conflict_title才会提示不同类型冲突，需要额外判断上传的包里插件类型与数据库中类型是否一致
            if (
                str(ConflictMap.DuplicatedPlugin.info) in self.create_params["conflict_title"]
                or self.current_version.plugin.plugin_type != self.plugin_type
            ):
                raise ExportImportError({"msg": "导入插件类型冲突"})
            if str(ConflictMap.RemoteCollectorConfig.info) in self.create_params["conflict_title"]:
                if self.current_version.config.is_support_remote:
                    raise ExportImportError({"msg": "已存在插件支持远程采集，导入插件不能关闭"})
            # 版本小于等于当前版本
            if StrictVersion(self.tmp_version.version) < StrictVersion(self.current_version.version):
                # 将低版本的信息写入高版本,只需要将version信息，create_params中改为与当前版本一致即可
                self.tmp_version.config_version = self.create_params["config_version"] = (
                    self.current_version.config_version
                )
                self.tmp_version.info_version = self.create_params["info_version"] = self.current_version.info_version
            return save_resource.request(self.create_params)


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
        current_dir = pathlib.Path(__file__).parent
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
