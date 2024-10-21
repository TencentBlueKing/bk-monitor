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


import logging
import os
from collections import namedtuple

from django.utils.translation import ugettext as _

from core.drf_resource import resource
from monitor_web.commons.file_manager import PluginFileManager
from monitor_web.plugin.constant import OS_TYPE_TO_DIRNAME, ParamMode
from monitor_web.plugin.manager.base import PluginManager
from monitor_web.plugin.serializers import ExporterSerializer

logger = logging.getLogger(__name__)


class ExporterPluginManager(PluginManager):
    """
    Exporter 插件
    """

    serializer_class = ExporterSerializer
    templates_dirname = "exporter_templates"
    CollectorFile = namedtuple("CollectorFile", ["name", "data"])

    def fetch_collector_file(self):
        file_dict = {}
        for os_type, exporter_info in list(self.version.config.file_config.items()):
            if os_type == "windows":
                filename = "{}.exe".format(self.plugin.plugin_id)
            else:
                filename = self.plugin.plugin_id
            file_instance = PluginFileManager(exporter_info["file_id"])
            file_dict[os_type] = [{"file_name": filename, "file_content": file_instance.file_obj.file_data.read()}]
        return file_dict

    def make_package(self, **kwargs):
        kwargs.update(dict(add_files=self.fetch_collector_file()))
        return super(ExporterPluginManager, self).make_package(**kwargs)

    def _get_debug_config_context(self, config_version, info_version, param, target_nodes):
        specific_version = self.plugin.get_version(config_version, info_version)
        config_json = specific_version.config.config_json

        # 采集器参数上下文
        collector_data = param["collector"]
        plugin_data = param["plugin"]
        collector_data["metric_url"] = "{}:{}/metrics".format(collector_data["host"], collector_data["port"])

        context = {
            "env.yaml": {},
            "bkmonitorbeat_debug.yaml": collector_data,
        }

        user_files = []

        cmd_args = ""

        dms_insert_params = {}

        # 节点管理base64识别前缀
        nodeman_base64_file_prefix = "$NODEMAN_BASE64_PREFIX$"

        for param in config_json:
            param_name = param["name"]
            param_mode = param["mode"]
            param_value = plugin_data.get(param_name)

            if param_value is None:
                continue

            if param["type"] == "file":
                user_files.append(
                    {"filename": param_value.get("filename"), "file_base64": param_value.get("file_base64")}
                )
                context["{{file" + str(len(user_files)) + "}}"] = {
                    f"file{len(user_files)}_content": nodeman_base64_file_prefix + param_value.get("file_base64", ""),
                    f"file{len(user_files)}": param_value.get("filename"),
                }
                # 改写参数值为 etc/xxx.yy
                param_value = "etc/" + param_value.get("filename")

            if param["type"] == "encrypt":
                param_value = resource.collecting.encrypt_password(password=param_value)

            # 使用采集器参数对变量进行渲染
            if isinstance(param_value, str):
                for k, v in list(collector_data.items()):
                    replace_key = "${%s}" % k
                    if isinstance(v, str) and param_mode != ParamMode.DMS_INSERT:
                        param_value = param_value.replace(replace_key, v)

            if param_mode == ParamMode.ENV and isinstance(param_value, str):
                context["env.yaml"][param_name] = param_value

            elif param_mode == ParamMode.OPT_CMD:
                if param["type"] == "switch":
                    if param_value == "true":
                        cmd_args += "{opt_name} ".format(opt_name=param_name)
                elif param_value:
                    cmd_args += "{opt_name} {opt_value} ".format(opt_name=param_name, opt_value=param_value)

            elif param_mode == ParamMode.POS_CMD:
                # 位置参数，直接将参数值拼接进去
                cmd_args += "{pos_value} ".format(pos_value=param_value)

            elif param_mode == ParamMode.DMS_INSERT:
                # 维度注入参数，更新至labels的模板中
                for dms_key, dms_value in list(param_value.items()):
                    if param["type"] == "host":
                        dms_insert_params[dms_key] = "{{ " + f"cmdb_instance.host.{dms_value} or '-'" + " }}"
                    else:
                        dms_insert_params[dms_key] = (
                            "{{ " + f"cmdb_instance.service.labels['{dms_value}'] or '-'" + " }}"
                        )

        if dms_insert_params:
            collector_data.update(
                {"labels": {"$for": "cmdb_instance.scope", "$item": "scope", "$body": {**dms_insert_params}}}
            )

        context["env.yaml"]["cmd_args"] = cmd_args
        return context

    def get_deploy_steps_params(self, plugin_version, param, target_nodes):
        config_json = plugin_version.config.config_json

        # 采集器参数上下文
        collector_params = param["collector"]
        plugin_params = param["plugin"]
        collector_params["config_name"] = self.plugin.plugin_id
        if collector_params.get("port"):
            plugin_params["port"] = collector_params["port"]
        else:
            plugin_params["port"] = "{{ control_info.listen_port }}"
            collector_params["port"] = "{{ step_data.%s.control_info.listen_port }}" % self.plugin.plugin_id
        collector_params["metric_url"] = "{}:{}/metrics".format(collector_params["host"], collector_params["port"])
        env_context = {}
        user_files = []
        cmd_args = ""

        # 节点管理base64识别前缀
        nodeman_base64_file_prefix = "$NODEMAN_BASE64_PREFIX$"

        for param in config_json:
            param_name = param["name"]
            param_mode = param["mode"]
            param_value = plugin_params.get(param_name)

            if param_value is None:
                continue

            if param["type"] == "file":
                user_files.append(
                    {"filename": param_value.get("filename"), "file_base64": param_value.get("file_base64")}
                )
                env_context[f"file{len(user_files)}"] = param_value.get("filename")
                env_context[f"file{len(user_files)}_content"] = nodeman_base64_file_prefix + param_value.get(
                    "file_base64", ""
                )
                # 改写参数值为 etc/xxx.yy
                param_value = "etc/" + param_value.get("filename")

            if param["type"] == "encrypt":
                param_value = resource.collecting.encrypt_password(password=param_value)

            # 使用采集器参数对变量进行渲染
            if isinstance(param_value, str):
                for k, v in list(collector_params.items()):
                    replace_key = "${%s}" % k
                    if isinstance(v, str) and param_mode != ParamMode.DMS_INSERT:
                        param_value = param_value.replace(replace_key, v)

            if param_mode == ParamMode.ENV and isinstance(param_value, str):
                env_context[param_name] = param_value

            elif param_mode == ParamMode.OPT_CMD:
                if param["type"] == "switch":
                    if param_value == "true":
                        cmd_args += "{opt_name} ".format(opt_name=param_name)
                elif param_value:
                    cmd_args += "{opt_name} {opt_value} ".format(opt_name=param_name, opt_value=param_value)

            elif param_mode == ParamMode.POS_CMD:
                # 位置参数，直接将参数值拼接进去
                cmd_args += "{pos_value} ".format(pos_value=param_value)

        env_context["cmd_args"] = cmd_args

        diff_metrics = plugin_version.config.diff_fields
        collector_params["diff_metrics"] = diff_metrics.split(",") if diff_metrics else []

        deploy_steps = [
            {
                "id": self.plugin.plugin_id,
                "type": "PLUGIN",
                "config": {
                    "plugin_name": self.plugin.plugin_id,
                    "plugin_version": plugin_version.version,
                    "config_templates": [{"name": "env.yaml", "version": str(plugin_version.config_version)}],
                },
                "params": {"context": env_context},
            },
            self._get_bkmonitorbeat_deploy_step("bkmonitorbeat_prometheus.conf", {"context": collector_params}),
        ]
        for index, file in enumerate(user_files):
            deploy_steps[0]["config"]["config_templates"].append(
                {
                    "name": "{{file" + str(index + 1) + "}}",
                    "version": str(plugin_version.config_version),
                    "content": "{{file" + str(index + 1) + "_content}}",
                }
            )
        return deploy_steps

    def _get_collector_json(self, plugin_params):
        collector_file = {}
        for sys_name, sys_dir in list(OS_TYPE_TO_DIRNAME.items()):
            # 获取不同操作系统下的文件名
            collector_name = "%s.exe" % self.plugin.plugin_id if sys_name == "windows" else self.plugin.plugin_id
            collector_path = os.path.join(sys_dir, self.plugin.plugin_id, collector_name)
            # _path = collector_path.replace('\\', '/')
            if any([collector_path in i for i in self.filename_list]):
                # 读取文件内容
                collector_file[sys_name] = self.CollectorFile(
                    data=self._read_file(os.path.join(self.tmp_path, collector_path)), name=collector_name
                )

        collector_json = {}
        # collector_json存入文件系统
        for sys_name, file_instance in list(collector_file.items()):
            file_name = "_".join([sys_name, file_instance.name])
            file_manager = PluginFileManager.save_file(file_data=file_instance.data, file_name=file_name)
            collector_json[sys_name] = {
                "file_id": file_manager.file_obj.id,
                "file_name": file_manager.file_obj.actual_filename,
                "md5": file_manager.file_obj.file_md5,
            }

        return collector_json


class ExporterPluginFileManager(PluginFileManager):
    @classmethod
    def valid_file(cls, file_data, os_type):
        getattr(cls, "valid_{}".format(os_type))(file_data)

    @classmethod
    def valid_windows(cls, file_data):
        if not file_data.name.endswith(".exe"):
            raise Exception(_("文件{}不是windows下的可执行文件").format(file_data.name))

    @classmethod
    def valid_linux(cls, file_data):
        if file_data.name.endswith(".exe"):
            raise Exception(_("文件{}不是linux下的可执行文件".format(file_data.name)))
        try:
            import magic

            stdout = magic.from_buffer(file_data.read())
            if "executable" not in stdout and "shared object" not in stdout:
                raise Exception(_("文件{}不是linux下的可执行文件").format(file_data.name))
        except ImportError as err:
            logging.error(err)

    @classmethod
    def valid_linux_aarch64(cls, file_data):
        cls.valid_linux(file_data)

    @classmethod
    def valid_aix(cls, file_data):
        pass
