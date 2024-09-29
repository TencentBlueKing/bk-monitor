# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
import base64
import copy
import json
import logging
import os
import shutil
import stat
import tarfile
import time
from functools import partial
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import yaml
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import engines
from django.utils.translation import gettext

from bkmonitor.utils import time_tools
from bkmonitor.utils.serializers import MetricJsonSerializer
from core.drf_resource import api
from core.errors.api import BKAPIError
from core.errors.plugin import (
    ExportPluginError,
    ExportPluginTimeout,
    MakePackageError,
    NodeManDeleteError,
    ParsingDataError,
    PluginError,
    PluginParseError,
    RemoteCollectError,
)
from monitor_web.commons.data_access import PluginDataAccessor
from monitor_web.models.plugin import (
    CollectorPluginConfig,
    CollectorPluginInfo,
    CollectorPluginMeta,
    PluginVersionHistory,
)
from monitor_web.plugin.constant import (
    BEAT_ERR,
    BEAT_RUN_ERR,
    HEARTBEAT_MESSAGE_ID,
    INNER_DIMENSIONS,
    OS_TYPE_TO_DIRNAME,
    PLUGIN_TEMPLATES_PATH,
    DebugStatus,
    PluginType,
)
from monitor_web.plugin.signature import Signature, load_plugin_signature_manager
from monitor_web.tasks import append_metric_list_cache
from utils import count_md5

logger = logging.getLogger(__name__)


def check_skip_debug(need_debug):
    # 如果设置了编辑跳过debug的配置
    if settings.SKIP_PLUGIN_DEBUG:
        need_debug = False
    return need_debug


class BasePluginManager:
    def __init__(self, plugin: CollectorPluginMeta, operator: str, tmp_path=None):
        self.plugin = plugin
        self.operator = operator
        self.tmp_path = tmp_path
        self.version: Optional[PluginVersionHistory] = PluginVersionHistory.objects.filter(
            plugin_id=self.plugin.plugin_id
        ).last()

    def _update_version_params(self, data, version, current_version, stag=None):
        """
        更新插件版本参数
        """
        sig_manager = load_plugin_signature_manager(version)
        version.signature = sig_manager.signature().dumps2python()

        if data.get("version_log", ""):
            version.version_log = data.get("version_log", "")

        # 如果是官方插件，且当前版本不是官方版本，则删除当前版本的所有历史版本
        if version.is_official:
            if not current_version.is_official:
                PluginVersionHistory.origin_objects.filter(plugin=version.plugin).delete()
            version.config_version = data.get("config_version", 1)
            version.info_version = data.get("info_version", 1)

        if stag:
            version.stage = stag
        version.save()

    @classmethod
    def _update_config(cls, update_config_data: Dict[str, Any], version: PluginVersionHistory):
        """
        更新插件config字段
        """
        for attr, value in update_config_data.items():
            setattr(version.config, attr, value)
        version.config.save()

    def _update_info(self, update_info_data, now_info_data, current_version, version):
        """
        更新插件info字段
        """
        update_logo = update_info_data.pop("logo", "")

        # 如果有更新的字段，则更新
        for attr, value in update_info_data.items():
            setattr(version.info, attr, value)
        version.info.save()

        # 如果有更新logo，则保存logo文件
        if not update_logo:
            version.info.logo = ""
            version.info.save()
        elif update_logo != now_info_data["logo"] and update_logo:
            self.save_logo_file(version.info, update_logo)
        else:
            version.info.logo = current_version.info.logo
            version.info.save()

    @staticmethod
    def _get_new_collector_json(collector_json, diff_value):
        new_collector_json = copy.deepcopy(collector_json)
        if diff_value:
            new_collector_json.update({"diff_fields": diff_value})
        else:
            new_collector_json.pop("diff_fields", "")
        return new_collector_json

    def _get_version(self, config_version, info_version):
        version = self.plugin.generate_version(config_version, info_version)
        version.stage = "unregister"
        return version

    def validate_config_info(self, collector_info: Dict[str, Any], config_info: List[Dict[str, Any]]) -> None:
        """
        配置检查
        """

    def save_logo_file(self, info: CollectorPluginInfo, logo_base64: str) -> None:
        """
        保存logo文件
        """
        logo_base64 = logo_base64.split(",")[-1]
        img = ContentFile(base64.b64decode(logo_base64))
        info.logo.save(f"{self.plugin.plugin_id}.png", img)

    def start_debug(
        self,
        config_version: int,
        info_version: int,
        param: Dict[str, Any],
        host_info: Dict[str, Any],
        target_nodes=None,
    ) -> Optional[str]:
        """
        开始插件调试
        """

    def stop_debug(self, task_id: str) -> None:
        """
        停止插件调试
        """

    def query_debug(self, task_id: str) -> Dict[str, Any]:
        """
        获取调试信息
        """
        return {}

    def data_access(self, config_version: int, info_version: int) -> None:
        """
        数据接入
        """
        current_version = self.plugin.get_version(config_version, info_version)

        try:
            # 接入数据源
            PluginDataAccessor(current_version, self.operator).access()
        except Exception as err:
            logger.exception("[plugin] data_access error, msg is %s" % str(err))
            current_version.stage = "unregister"
            current_version.save()
            raise err

        try:
            # 更新指标后，指标缓存同步更新
            result_table_id_list = [
                "{}_{}.{}".format(self.plugin.plugin_type.lower(), self.plugin.plugin_id, metric_msg["table_name"])
                for metric_msg in current_version.info.metric_json
            ]
            append_metric_list_cache.delay(result_table_id_list)
        except Exception as err:
            logger.error("[update_plugin_metric_cache] error, msg is {}".format(err))

    def update_metric(self, data: Dict[str, Any]) -> Tuple[int, int, bool, bool]:
        """
        更新插件指标维度信息
        """
        current_version = self.plugin.get_version(data["config_version"], data["info_version"])
        metric_json = data["metric_json"]
        info_obj = current_version.info
        now_info_data = info_obj.info2dict()
        current_config_version = current_version.config_version
        current_info_version = current_version.info_version
        old_metric_md5, new_metric_md5 = list(map(count_md5, [info_obj.metric_json, metric_json]))
        need_make_package = False
        is_change = False
        # metric_json 存在变更或者 切换了黑名单的开启，生成新的 version
        if (
            old_metric_md5 != new_metric_md5
            or current_version.info.enable_field_blacklist != data["enable_field_blacklist"]
        ):
            is_change = True
            current_info_version = current_info_version + 1
            update_info_data = copy.deepcopy(now_info_data)
            # 白名单模式下，清除 tag_list 内的值
            if not data["enable_field_blacklist"]:
                for metric_data in metric_json:
                    for field_data in metric_data["fields"]:
                        field_data["tag_list"] = []
            update_info_data["metric_json"] = metric_json
            update_info_data["enable_field_blacklist"] = data["enable_field_blacklist"]
            config_obj = current_version.config
            diff_value = PluginVersionHistory.gen_diff_fields(metric_json)
            old_collector_json = config_obj.collector_json
            new_collector_json = self._get_new_collector_json(old_collector_json, diff_value)
            old_collector_md5, new_collector_md5 = list(map(count_md5, [old_collector_json, new_collector_json]))
            if old_collector_md5 != new_collector_md5:
                current_config_version = current_config_version + 1
                need_make_package = True
            version = self._get_version(current_config_version, current_info_version)
            update_config_data = config_obj.config2dict()
            update_config_data["collector_json"] = new_collector_json
            self._update_config(update_config_data, version)
            self._update_info(update_info_data, now_info_data, current_version, version)
            version.stage = "unregister" if need_make_package else "release"
            version.is_packaged = False
            version.signature = current_version.signature
            version.version_log = "update_metric"
            version.save()
            if not current_version.info.metric_json:
                current_version.info.metric_json = metric_json
                current_version.info.save()
        return current_config_version, current_info_version, is_change, need_make_package

    @abc.abstractmethod
    def release(
        self,
        config_version: int,
        info_version: int,
        token: List[str] = None,
        debug: bool = True,
    ) -> PluginVersionHistory:
        """
        发布插件包
        :param config_version: 插件config版本
        :param info_version: 插件info版本
        :param token: 插件包文件md5列表
        :param debug: 是否为调试模式
        """

    def create_version(self, data) -> Tuple[PluginVersionHistory, bool]:
        version = self.plugin.generate_version(data["config_version"], data["info_version"])
        version.version_log = data.get("version_log", "")
        version.save()

        config_data = {
            "config_json": data.get("config_json", []),
            "collector_json": data.get("collector_json", []),
            "is_support_remote": data.get("is_support_remote", False),
        }
        for attr, value in list(config_data.items()):
            setattr(version.config, attr, value)
        version.config.save()

        info_data = {
            "plugin_display_name": (
                data["plugin_display_name"] if data["plugin_display_name"] else self.plugin.plugin_id
            ),
            "logo": None,
            "description_md": data["description_md"],
            "metric_json": data["metric_json"],
        }
        for attr, value in list(info_data.items()):
            setattr(version.info, attr, value)
        version.info.save()

        if len(data["logo"]) > 1:
            self.save_logo_file(version.info, data["logo"])

        need_debug = True
        if data.get("signature"):
            version.signature = Signature().load_from_yaml(data["signature"]).dumps2python()
            if version.is_safety:
                need_debug = False
            else:
                sig_manager = load_plugin_signature_manager(version)
                version.signature = sig_manager.signature().dumps2python()
        else:
            sig_manager = load_plugin_signature_manager(version)
            version.signature = sig_manager.signature().dumps2python()
        version.save()

        return version, need_debug

    def update_version(self, data, target_config_version: int = None, target_info_version: int = None):
        """
        更新插件版本
        """
        need_debug = True
        current_version = self.plugin.current_version
        if not data.get("is_support_remote", False):
            if current_version.is_release and current_version.config.is_support_remote:
                raise RemoteCollectError({"msg": gettext("已开启远程采集的插件无法关闭远程采集")})

        config = current_version.config
        info = current_version.info
        now_config_data = config.config2dict()
        update_config_data = config.config2dict(data)

        now_info_data = info.info2dict()
        update_info_data = info.info2dict(data)

        old_config_md5, new_config_md5, old_info_md5, new_info_md5 = list(
            map(count_md5, [now_config_data, update_config_data, now_info_data, update_info_data])
        )

        current_config_version = current_version.config_version
        current_info_version = current_version.info_version

        if old_info_md5 != new_info_md5 and current_version.is_release:
            current_info_version += 1

        if old_config_md5 != new_config_md5 and current_version.is_release:
            current_config_version += 1

        # 如果有指定的目标版本，则强制设置
        if target_config_version:
            current_config_version = target_config_version
        if target_info_version:
            current_info_version = target_info_version

        if old_config_md5 == new_config_md5:
            if current_version.is_release:
                need_debug = False
            if old_info_md5 != new_info_md5 and current_version.is_release:
                version = self._get_version(current_config_version, current_info_version)
                self._update_config(update_config_data, version)
                self._update_info(update_info_data, now_info_data, current_version, version)
                self._update_version_params(data, version, current_version, stag="release")
            else:
                # 包内容一样，则更新发布日志
                setattr(current_version, "version_log", data.get("version_log", ""))
                if data.get("signature"):
                    current_version.signature = Signature().load_from_yaml(data["signature"]).dumps2python()
                current_version.save()
                version = current_version
        else:
            version = self._get_version(current_config_version, current_info_version)
            self._update_config(update_config_data, version)
            self._update_info(update_info_data, now_info_data, current_version, version)
            self._update_version_params(data, version, current_version)

        return version, need_debug

    @abc.abstractmethod
    def make_package(
        self,
        add_files: Dict[str, List[Dict[str, str]]] = None,
        add_dirs: Dict[str, List[Dict[str, str]]] = None,
        need_tar: bool = True,
    ) -> Optional[str]:
        """
        制作插件包，在tmp_path下制作插件包
        :param add_files: 是否有额外文件
        :param add_dirs: 是否有额外目录
        :param need_tar: 是否需要打包
        example:
        add_files: {
            "linux": [
                {
                    "file_name": "xxx.sh",
                    "file_content": "xxxx",
                }
            ],
        }
        add_dirs: {
            "linux": [
                {
                    "dir_name": "xxx",
                    "dir_path": "/x/y/z/"
                }
            ]
        }
        :return: 如果需要打包，则返回打包后的文件路径，否则返回None
        """

    @abc.abstractmethod
    def run_export(self) -> str:
        """
        运行exporter
        """


class PluginManager(BasePluginManager):
    """
    插件管理基类
    """

    # 需要注册的模板文件
    config_files = ["env.yaml.tpl"]
    # 插件包模板目录名称
    templates_dirname = ""
    # 插件数据校验类
    serializer_class = None

    def __init__(self, plugin, operator, tmp_path=None):
        """
        :param plugin: CollectorPluginMeta Instance
        """
        super(PluginManager, self).__init__(plugin, operator, tmp_path)

        self.tmp_path: str = os.path.join(settings.MEDIA_ROOT, "plugin", str(uuid4())) if not tmp_path else tmp_path
        self.filename_list = []
        for dir_path, _, filename_list in os.walk(self.tmp_path):
            for filename in filename_list:
                self.filename_list.append(os.path.join(dir_path, filename))

    def _render_config(self, config_version, config_name, context):
        """
        配置
        :param config_version: 配置版本（大版本）
        :param config_name: 配置名称
        :param context: 配置上下文
        :return: 节点管理的配置实例ID
        """
        param = {
            "plugin_name": self.plugin.plugin_id,
            "plugin_version": "*",
            "name": config_name,
            "version": config_version,
            "data": context,
        }
        render_result = api.node_man.render_config_template(param)
        return render_result["id"]

    def _run_debug(self, config_version, config_ids, host):
        debug_version = self.plugin.get_debug_version(config_version)
        param = {
            "plugin_name": self.plugin.plugin_id,
            "version": "{}.{}".format(debug_version.config_version, debug_version.info_version),
            "config_ids": config_ids,
            "host_info": host,
        }
        debug_result = api.node_man.start_debug(param)
        return debug_result

    @abc.abstractmethod
    def _get_debug_config_context(self, config_version, info_version, param, target_nodes):
        """
        获取配置实例渲染上下文，需要子类实现
        example
        {
            "config.yaml": {
                'username': 'aaa',
                'password': 'bbb',
            }
        }
        """
        return {}

    @staticmethod
    def _get_bkmonitorbeat_deploy_step(conf_name, collector_params, step_id="bkmonitorbeat"):
        if "context" not in collector_params:
            collector_params = {"context": collector_params}
        return {
            "id": step_id,
            "type": "PLUGIN",
            "config": {
                "plugin_name": "bkmonitorbeat",
                "plugin_version": "latest",
                "config_templates": [{"name": conf_name, "version": "latest"}],
            },
            "params": collector_params,
        }

    @staticmethod
    def _get_bkprocessbeat_deploy_step(conf_name, collector_params):
        if "context" not in collector_params:
            collector_params = {"context": collector_params}
        # 进程采集由processbeat下发切换为bkmonitorbeat
        return {
            "id": "bkmonitorbeat",
            "type": "PLUGIN",
            "config": {
                "plugin_name": "bkmonitorbeat",
                "plugin_version": "latest",
                "config_templates": [{"name": conf_name, "version": "latest"}],
            },
            "params": collector_params,
        }

    def _parser_log_error(self, log_content):
        message_list = log_content.strip().split("\n")
        for detail in reversed(message_list):
            is_invalid, message_detail = self._valid_data(detail)
            if is_invalid:
                continue
            error_message = self._get_error_message(message_detail)
            if error_message:
                log_content += error_message
            break
        return log_content

    @staticmethod
    def _check_metric_name_duplicate(metric_json):
        metric_name = set()
        dimension_name = set()
        for metric in metric_json:
            metric_name.add(metric["metric_name"])
            for dimension in metric["dimensions"]:
                dimension_name.add(dimension["dimension_name"])
        intersection = set(metric_name) & set(dimension_name)
        if metric_name & dimension_name:
            raise PluginError({"msg": gettext("指标维度存在重名,{}".format(intersection))})

    @staticmethod
    def _get_error_message(message):
        err_message = ""
        error_code = message.get("error_code") or 0
        if error_code in BEAT_ERR:
            err_message = "\n\n\n{}".format(BEAT_ERR[error_code].format(message.get("message", "UNKNOWN")))
        elif "error" in message and message["error"]:
            err_message = "\n\n\n{}".format(BEAT_ERR[BEAT_RUN_ERR].format(message["error"]))
        return err_message

    @staticmethod
    def _valid_data(data):
        if '"beat"' not in data:
            return True, data
        try:
            message_detail = json.loads(data)
        except Exception as error:
            logger.exception("[query_debug] Parsing data error：%s；The last 50 char:%s", error, data[-50:])
            raise ParsingDataError()
        if message_detail["dataid"] == HEARTBEAT_MESSAGE_ID or message_detail["type"] == "status":
            # 心跳数据，不需要
            return True, data
        return False, message_detail

    def _parser_log_content(self, log_content):
        metric_json = []
        message_list = log_content.strip().split("\n")
        metric_name_cache = []
        dimension_info = {}
        log_type = None
        valid_message = {}
        for detail in message_list:
            is_invalid, message_detail = self._valid_data(detail)
            if is_invalid:
                continue
            if not log_type:
                log_type = self._get_log_type(message_detail)
            valid_message = message_detail
            if log_type == "exporter":
                self._exporter_log_parser(message_detail, metric_json, metric_name_cache)
            else:
                self._common_log_parser(message_detail, metric_json, metric_name_cache, dimension_info)
        else:
            last_time = time_tools.date_convert(valid_message.get("time", int(time.time())), "datetime")
        self._check_metric_name_duplicate(metric_json)
        return metric_json, last_time

    @staticmethod
    def _get_log_type(message_detail):
        if "prometheus" in message_detail:
            return "exporter"
        return "common"

    @staticmethod
    def _exporter_log_parser(message_detail, metric_json, metric_name_cache):
        metrics = message_detail["prometheus"]["collector"].get("metrics", [])
        for metric in metrics:
            if metric["key"] not in metric_name_cache:
                if not metric["key"].strip():
                    continue
                dimensions = []
                for key, value in list(metric["labels"].items()):
                    if key in INNER_DIMENSIONS:
                        continue
                    dimensions.append({"dimension_name": key, "dimension_value": value})
                metric_json.append(
                    {"metric_name": metric["key"], "metric_value": metric["value"], "dimensions": dimensions}
                )
                metric_name_cache.append(metric["key"])

    @staticmethod
    def _common_log_parser(message_detail, metric_json, metric_name_cache, dimension_info):
        if message_detail.get("message", "") != "success":
            return
        for metric_name, metric_value in message_detail["metrics"].items():
            if not metric_name.strip():
                continue
            if metric_name not in metric_name_cache:
                dimension_info[metric_name] = {"dimensions": [], "dimension_name": []}
                for key, value in list(message_detail["dimensions"].items()):
                    if key in INNER_DIMENSIONS:
                        continue
                    dimension_info[metric_name]["dimensions"].append({"dimension_name": key, "dimension_value": value})
                    dimension_info[metric_name]["dimension_name"].append(key)
                metric_json.append(
                    {
                        "metric_name": metric_name,
                        "metric_value": metric_value,
                        "dimensions": dimension_info[metric_name]["dimensions"],
                    }
                )
                metric_name_cache.append(metric_name)
            else:
                for key, value in list(message_detail["dimensions"].items()):
                    if key in INNER_DIMENSIONS:
                        continue
                    if key not in dimension_info[metric_name]["dimension_name"]:
                        dimension_info[metric_name]["dimensions"].append(
                            {"dimension_name": key, "dimension_value": value}
                        )
                        dimension_info[metric_name]["dimension_name"].append(key)

    def _release_config(self, config_version, info_version, name):
        """
        发布配置文件
        :return:
        """
        param = {
            "plugin_name": self.plugin.plugin_id,
            "plugin_version": "{}_{}".format(config_version, info_version),
            "name": name,
            "version": config_version,
        }
        api.node_man.release_config(param)

    def _update_version_params(self, data, version, current_version, stag=None):
        """
        更新插件版本参数
        """
        super()._update_version_params(data, version, current_version, stag)
        # 如果是官方插件，且当前版本不是官方版本，则删除当前版本的所有历史版本
        if version.is_official and not current_version.is_official:
            try:
                api.node_man.delete_plugin(name=version.plugin.plugin_id)
            except BKAPIError:
                raise NodeManDeleteError

    def _tar_gz_file(self, filename_list):
        t = tarfile.open(os.path.join(self.tmp_path, self.plugin.plugin_id + ".tgz"), "w:gz")
        for root, _, files in os.walk(filename_list):
            for filename in files:
                full_path = os.path.join(root, filename)
                file_save_path = full_path.replace(os.path.join(self.tmp_path, self.plugin.plugin_id), "")
                t.add(str(full_path), arcname=str(file_save_path))
        t.close()
        return t.name

    def _get_context(self):
        context = {
            "metric_json": self.version.info.metric_json,
            "plugin_id": self.plugin.plugin_id,
            "plugin_display_name": self.version.info.plugin_display_name,
            "version": self.version.version,
            "config_version": self.version.config_version,
            "plugin_type": self.plugin.get_plugin_type_display(),
            "tag": self.plugin.tag,
            "label": self.plugin.label,
            "description_md": self.version.info.description_md,
            "config_json": self.version.config.config_json,
            "collector_json": self.version.config.collector_json,
            "signature": "",
            "is_support_remote": self.version.config.is_support_remote,
            "version_log": self.version.version_log,
        }
        if self.version.signature:
            context["signature"] = Signature(self.version.signature).dumps2yaml()
        if self.plugin.plugin_type in [PluginType.EXPORTER, PluginType.JMX, PluginType.SNMP]:
            try:
                default_port = [x for x in self.version.config.config_json if x["name"] == "port"][0]["default"]
                context["port_range"] = "%s,10000-65535" % default_port
            except (KeyError, IndexError):
                context["port_range"] = "10000-65535"

        return context

    @classmethod
    def _read_file(cls, filename):
        try:
            with open(filename, "rb") as f:
                file_content = f.read()
        except IOError:
            raise PluginParseError({"msg": gettext("%s文件读取失败") % filename})

        try:
            file_content = file_content.decode("utf-8")
        except UnicodeDecodeError:
            pass
        return file_content

    def _parse_info_path(self):
        read_filename_list = []
        for dir_path, dirname, filename_list in os.walk(self.tmp_path):
            if dir_path.endswith(os.path.join(self.plugin.plugin_id, "info")) and len(dirname) == 0:
                plugin_info_path = dir_path
                read_filename_list = [os.path.join(plugin_info_path, filename) for filename in filename_list]
                break

        if not read_filename_list:
            raise PluginParseError({"msg": gettext("不存在info文件夹，无法解析插件包")})

        plugin_params = {}
        for file_instance in read_filename_list:
            plugin_params[os.path.basename(file_instance)] = self._read_file(file_instance)

        self._get_meta_info(plugin_params)
        self._get_config_mes(plugin_params)
        self._get_info_msg(plugin_params)
        self._get_version_mes(plugin_params)
        self._parse_plugin_version_str()

    def _get_meta_info(self, plugin_params):
        meta_dict = yaml.load(plugin_params["meta.yaml"], Loader=yaml.FullLoader)
        self.plugin.tag = meta_dict.get("tag") if meta_dict.get("tag") else ""
        self.plugin.label = meta_dict.get("label", "other_rt")
        self.version.config.is_support_remote = self._get_remote_stage(meta_dict)
        self.version.info.plugin_display_name = meta_dict.get("plugin_display_name") or self.plugin.plugin_id

    def _get_remote_stage(self, meta_dict):
        if meta_dict.get("is_support_remote") is True:
            return True
        return False

    @abc.abstractmethod
    def _get_collector_json(self, plugin_params):
        pass

    def _get_config_mes(self, plugin_params):
        # load config_json
        try:
            self.version.config.config_json = json.loads(plugin_params["config.json"])
        except (TypeError, ValueError):
            self.version.config.config_json = []

        # load collector_json
        self.version.config.collector_json = self._get_collector_json(plugin_params)

    def _parse_plugin_version_str(self):
        version_path = ""
        for filename in self.filename_list:
            if filename.endswith("VERSION"):
                version_path = filename
                break

        try:
            version_str = self._read_file(os.path.join(self.tmp_path, version_path))
            version_split = version_str.split(".")
            config_version = int(version_split[0])
            info_version = int(version_split[1])
        except Exception as e:
            logger.exception("[ImportPlugin] {} - parse version error: {}".format(self.plugin.plugin_id, e))
            config_version = info_version = 1

        self.version.config_version = config_version
        self.version.info_version = info_version

    def _get_info_msg(self, plugin_params):
        # load metric_json
        try:
            metric_json = json.loads(plugin_params["metrics.json"])
            serializer = MetricJsonSerializer(data=metric_json, many=True)
            if serializer.is_valid():
                self.version.info.metric_json = serializer.validated_data
            else:
                logger.warning(
                    "[ImportPlugin] {} - metric_json invalid: {}".format(self.plugin.plugin_id, serializer.errors)
                )
                self.version.info.metric_json = []
        except (ValueError, TypeError):
            self.version.info.metric_json = []
        self.version.info.description_md = plugin_params.get("description.md", "")
        # 获取图片
        if plugin_params.get("logo.png", ""):
            self.version.info.logo.save(
                self.plugin.plugin_id + ".png",
                SimpleUploadedFile("%s.png" % self.plugin.plugin_id, plugin_params["logo.png"]),
            )

    def _get_version_mes(self, plugin_params):
        # load signature
        try:
            self.version.signature = Signature().load_from_yaml(plugin_params.get("signature.yaml")).dumps2python()
        except Exception as e:
            logger.exception("[ImportPlugin] {} - signature error: {}".format(self.plugin.plugin_id, e))
            self.version.signature = ""

        # load version_log
        self.version.version_log = plugin_params.get("release.md", "")

    @abc.abstractmethod
    def get_deploy_steps_params(self, plugin_version, param, target_nodes):
        return []

    def start_debug(self, config_version, info_version, param, host_info, target_nodes=None):
        """
        开始插件调试
        """
        all_context = self._get_debug_config_context(config_version, info_version, param, target_nodes)

        # 将配置模板渲染为配置实例，并获取配置实例ID
        config_ids = []
        for config_name, context in list(all_context.items()):
            config_id = self._render_config(config_version, config_name, context)
            config_ids.append(config_id)

        task_id = self._run_debug(config_version, config_ids, host_info)
        return task_id

    def stop_debug(self, task_id: str):
        """
        停止插件调试
        """
        return api.node_man.stop_debug(task_id=task_id)

    def query_debug(self, task_id):
        """
        获取调试信息
        """
        result = api.node_man.query_debug(task_id=task_id)

        metric_json, last_time = self._parser_log_content(result["message"])
        log_content = self._parser_log_error(result["message"])
        if result["status"] in [DebugStatus.FAILED, DebugStatus.SUCCESS]:
            task_status = result["status"]
            return {
                "status": task_status,
                "log_content": log_content,
                "metric_json": metric_json,
                "last_time": last_time,
            }

        if result["step"] in ["DEBUG_PROCESS", "STOP_DEBUG_PROCESS"]:
            # 处于 debug 步骤则为获取数据
            task_status = DebugStatus.FETCH_DATA
        else:
            task_status = DebugStatus.INSTALL

        return {"status": task_status, "log_content": log_content, "metric_json": metric_json, "last_time": last_time}

    def get_tmp_version(self, config_version=None, info_version=None):
        """
        通过已上传的包创建一个临时版本
        """
        config = CollectorPluginConfig()
        info = CollectorPluginInfo()
        self.version = PluginVersionHistory(plugin=self.plugin, config=config, info=info)
        self._parse_info_path()
        self.version.update_diff_fields()

        if config_version is not None:
            self.version.config_version = config_version
        if info_version is not None:
            self.version.info_version = info_version

        return self.version

    def release(self, config_version, info_version, token=None, debug=True):
        """
        发布插件包

        """
        try:
            current_version = self.plugin.get_version(config_version, info_version)
            # 接入数据源
            PluginDataAccessor(current_version, self.operator).access()

            if debug:
                release_version = self.plugin.get_debug_version(config_version)
            else:
                release_version = current_version

            # 调用节点管理接口，发布配置文件
            release_config = partial(self._release_config, release_version.config_version, release_version.info_version)
            list(map(release_config, self.config_files))
            # 调用节点管理接口，发布插件包
            api.node_man.release_plugin(
                {
                    "name": self.plugin.plugin_id,
                    "version": "{}.{}".format(release_version.config_version, release_version.info_version),
                    "md5_list": token,
                }
            )
            # 将插件版本状态置为release
            release_version.stage = "release"
            release_version.save()

            if debug:
                current_version.stage = "release"
                current_version.save()
        except Exception as err:
            logger.error("[plugin] release plugin {} error, msg is {}".format(self.plugin.plugin_id, str(err)))
            self.plugin.rollback_version_status(config_version)
            raise err
        return current_version

    def make_package(self, add_files=None, add_dirs=None, need_tar=True):
        """
        制作插件包
        :param add_files: 是否有额外文件
        :param add_dirs: 是否有额外目录
        :param need_tar: 是否需要打包
        example:
        add_files: {
            "linux": [
                {
                    "file_name": "xxx.sh",
                    "file_content": "xxxx",
                }
            ],
        }
        add_dirs: {
            "linux": [
                {
                    "dir_name": "xxx",
                    "dir_path": "/x/y/z/"
                }
            ]
        }
        :return:
        """
        try:
            if not os.path.exists(self.tmp_path):
                os.makedirs(self.tmp_path)

            top_dir = os.path.join(self.tmp_path, self.plugin.plugin_id)

            templates_path = os.path.join(PLUGIN_TEMPLATES_PATH, self.templates_dirname)
            prefix_length = len(templates_path) + 1

            context = self._get_context()
            for root, dirs, files in os.walk(templates_path):
                path_rest = root[prefix_length:]
                real_path_rest = path_rest.replace("plugin_name", self.plugin.plugin_id)
                target_dir = os.path.join(top_dir, real_path_rest)
                os.makedirs(target_dir)

                for filename in files:
                    old_path = os.path.join(root, filename)
                    new_path = os.path.join(target_dir, filename)

                    try:
                        with open(old_path, "r", encoding="utf-8") as template_file:
                            content = template_file.read()
                        template = engines["django"].from_string(content)
                        content = template.render(context)
                        content = content.encode("utf-8")
                        with open(new_path, "wb") as new_file:
                            new_file.write(content)
                    except Exception:
                        # 非文本类文件无需渲染，直接拷贝
                        shutil.copyfile(old_path, new_path)
            template_dir = set(os.listdir(top_dir))
            need_package_dir = {OS_TYPE_TO_DIRNAME[os_type] for os_type in self.version.os_type_list}
            rm_dir = template_dir - need_package_dir
            for dir_name in rm_dir:
                shutil.rmtree(os.path.join(top_dir, dir_name))

            if add_files:
                # 追加文件
                for os_type, file_list in list(add_files.items()):
                    dest_dir = os.path.join(top_dir, OS_TYPE_TO_DIRNAME[os_type], self.plugin.plugin_id)

                    # 如果存在文件配置，追加到etc文件夹下
                    file_index = 1
                    for index, config in enumerate(context["config_json"]):
                        if config.get("type") == "file":
                            with open(
                                os.path.join(dest_dir, "etc", "{{file" + str(file_index) + "}}.tpl"), "w"
                            ) as template_file:
                                template_file.write("{{file" + str(file_index) + "_content}}")
                                file_index += 1

                    for file_info in file_list:
                        file_path = os.path.join(dest_dir, file_info["file_name"])
                        with open(file_path, "wb+") as fd:
                            fd.write(file_info["file_content"])

            if add_dirs:
                for os_type, dir_list in list(add_dirs.items()):
                    for dir_info in dir_list:
                        dest_dir = os.path.join(
                            top_dir, OS_TYPE_TO_DIRNAME[os_type], self.plugin.plugin_id, dir_info["dir_name"]
                        )
                        shutil.copytree(dir_info["dir_path"], dest_dir)

            # 插入logo.png
            if self.version.info.logo:
                for dirs in os.listdir(top_dir):
                    logo_path = os.path.join(top_dir, dirs, self.plugin.plugin_id, "info", "logo.png")
                    with open(logo_path, "wb") as logo_fd:
                        self.version.info.logo.file.seek(0)
                        logo_fd.write(self.version.info.logo.file.read())
                    # shutil.copyfile(self.version.info.logo.path, logo_path)

            # 添加可执行权限
            for root, dirs, files in os.walk(top_dir):
                if not root.endswith(self.plugin.plugin_id):
                    continue

                for filename in files:
                    os.chmod(os.path.join(root, filename), stat.S_IRWXU)

            if need_tar:
                tar_name = self._tar_gz_file(top_dir)
                return tar_name
        except Exception as e:
            logger.exception(e)
            raise MakePackageError({"msg": e})

    def run_export(self):
        # 判断是否有可导出的release版本
        release_version = self.plugin.release_version
        if not release_version:
            raise ExportPluginError({"msg": gettext("该插件没有release版本可导出")})

        param = {
            "category": "gse_plugin",
            "query_params": {"project": self.plugin.plugin_id, "version": release_version.version},
            "creator": self.operator,
        }
        package_result = api.node_man.export_raw_package(param)
        job_id = package_result["job_id"]
        i = 0
        download_url = ""
        while i < 15:
            query_result = api.node_man.export_query_task({"job_id": job_id})
            if query_result["is_failed"]:
                raise ExportPluginError({"msg": query_result.get("error_message", "")})

            if query_result["is_finish"]:
                download_url = query_result["download_url"]
                break

            i = i + 1
            time.sleep(2)

        if not download_url:
            raise ExportPluginTimeout

        return download_url
