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


import os
import shutil
import uuid
import zipfile

import yaml
from django.conf import settings
from django.template import engines
from django.template.base import VariableNode
from django.utils.translation import gettext as _

from core.errors.plugin import PluginParseError
from monitor_web.commons.file_manager import PluginFileManager
from monitor_web.plugin.constant import OS_TYPE_TO_DIRNAME
from monitor_web.plugin.manager.base import PluginManager
from monitor_web.plugin.serializers import DataDogSerializer


class DataDogPluginManager(PluginManager):
    """
    Datadog 插件
    """

    serializer_class = DataDogSerializer
    templates_dirname = "datadog_templates"

    def fetch_lib_dirs(self):
        file_dict = {}
        for os_type, exporter_info in list(self.version.config.file_config.items()):
            file_instance = PluginFileManager(exporter_info["file_id"])
            extract_dir = os.path.join(self.tmp_path, os_type, "lib")
            with zipfile.ZipFile(file_instance.file_obj.file_data.file, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
            file_dict[os_type] = [{"dir_name": "lib", "dir_path": extract_dir}]
        return file_dict

    def make_package(self, **kwargs):
        kwargs.update(dict(add_dirs=self.fetch_lib_dirs()))
        return super(DataDogPluginManager, self).make_package(**kwargs)

    def _get_debug_config_context(self, config_version, info_version, param, target_nodes):
        collector_data = param["collector"]
        plugin_data = param.get("plugin", {})

        context = {
            "conf.yaml": plugin_data,
            "env.yaml": plugin_data,
            "bkmonitorbeat_debug.yaml": collector_data,
        }

        return context

    def get_deploy_steps_params(self, plugin_version, param, target_nodes):
        plugin_params = param["plugin"]
        collector_params = param["collector"]

        # 补全逻辑：python_path参数应该放plugin_params里
        if collector_params.get("python_path"):
            plugin_params["python_path"] = collector_params["python_path"]

        collector_params[
            "command"
        ] = "{{{{ step_data.{}.control_info.setup_path }}}}/{{{{ step_data.{}.control_info.start_cmd }}}}".format(
            self.plugin.plugin_id, self.plugin.plugin_id
        )

        deploy_steps = [
            {
                "id": self.plugin.plugin_id,
                "type": "PLUGIN",
                "config": {
                    "plugin_name": self.plugin.plugin_id,
                    "plugin_version": plugin_version.version,
                    "config_templates": [
                        {"name": "env.yaml", "version": str(plugin_version.config_version)},
                        {"name": "conf.yaml", "version": str(plugin_version.config_version)},
                    ],
                },
                "params": {"context": plugin_params},
            },
            self._get_bkmonitorbeat_deploy_step("bkmonitorbeat_script.conf", {"context": collector_params}),
        ]
        return deploy_steps

    def _get_collector_json(self, plugin_params):
        meta_dict = yaml.load(plugin_params["meta.yaml"], Loader=yaml.FullLoader)

        if not meta_dict.get("datadog_check_name"):
            raise PluginParseError({"msg": _("meta.yaml 缺少 datadog_check_name")})

        collector_json = {"datadog_check_name": meta_dict["datadog_check_name"]}

        for sys_name, sys_dir in list(OS_TYPE_TO_DIRNAME.items()):
            # 获取不同操作系统下的文件名
            tmp_sys_plugin_path = os.path.join(self.tmp_path, sys_dir, self.plugin.plugin_id)
            if not os.path.exists(tmp_sys_plugin_path):
                continue

            lib_path = os.path.join(tmp_sys_plugin_path, "lib")
            if not os.path.exists(lib_path):
                raise PluginParseError({"msg": _("缺少 lib 文件夹")})

            lib_tar_name = "{}-lib-{}".format(self.plugin.plugin_id, sys_name)

            file_manager = PluginFileManager.save_dir(dir_path=lib_path, dir_name=lib_tar_name)
            collector_json[sys_name] = {
                "file_id": file_manager.file_obj.id,
                "file_name": file_manager.file_obj.actual_filename,
                "md5": file_manager.file_obj.file_md5,
            }

            config_yaml_path = os.path.join(tmp_sys_plugin_path, "etc", "conf.yaml.tpl")
            if not os.path.exists(config_yaml_path):
                raise PluginParseError({"msg": _("缺少 conf.yaml.tpl 配置模板文件")})

            config_template_content = self._read_file(config_yaml_path)
            collector_json["config_yaml"] = config_template_content

        return collector_json

    def validate_config_info(self, collector_info, config_info):
        config_yaml = collector_info["config_yaml"]
        template = engines["django"].from_string(config_yaml)
        context = self.get_config_context(config_info)
        no_render_params = []
        for node in template.template.nodelist:
            if isinstance(node, VariableNode):
                if str(node.filter_expression) not in context:
                    no_render_params.append(str(node.filter_expression))
        if no_render_params:
            raise PluginParseError({"msg": _("采集配置中配置的参数 %s 未定义") % no_render_params})

    @staticmethod
    def get_config_context(config_info):
        context = {}
        for config in config_info:
            context[config["name"]] = config["default"]
        return context


class DataDogPluginFileManager(PluginFileManager):
    @classmethod
    def extract_datadog_file(cls, file_data):
        plugin_tmp_dir = os.path.join(settings.MEDIA_ROOT, "plugin", str(uuid.uuid4()))
        os.makedirs(plugin_tmp_dir)
        return cls.extract_file(file_data, plugin_tmp_dir)

    @classmethod
    def save_lib(cls, plugin_base, check_name, os_type, plugin_id):
        plugin_os_path = str(os.path.join(plugin_base, OS_TYPE_TO_DIRNAME[os_type]))
        lib_path = os.path.join(plugin_os_path, os.listdir(plugin_os_path)[0], "lib")
        if not os.path.exists(lib_path):
            raise PluginParseError({"msg": _("缺少 lib 文件夹")})
        lib_tar_name = "{}-lib-{}".format(check_name, os_type)
        file_manager = cls.save_dir(dir_path=lib_path, dir_name=lib_tar_name, plugin_id=plugin_id)
        ret = {
            "file_id": file_manager.file_obj.id,
            "file_name": file_manager.file_obj.actual_filename,
            "md5": file_manager.file_obj.file_md5,
        }
        return ret

    @classmethod
    def save_dir(cls, dir_path, dir_name, plugin_id=None):
        """
        保存目录
        先将目录压缩成tgz，再进行
        """
        tar_name = f"{dir_name}.zip"
        tar_path = os.path.join(os.path.dirname(dir_path), tar_name)
        shutil.make_archive(os.path.join(str(os.path.dirname(dir_path)), dir_name), "zip", dir_path)

        with open(tar_path, "rb") as f:
            file_content = f.read()

        return cls.save_file(file_data=file_content, file_name=tar_name, is_dir=True, plugin_id=plugin_id)

    @classmethod
    def parse_plugin_content(cls, base_path, os_type):
        plugin_base = os.path.join(base_path, OS_TYPE_TO_DIRNAME[os_type])
        conf_content = cls.get_yaml_config_content(plugin_base)
        datadog_check_name = cls.get_datadog_check_name(plugin_base)
        return {"config_yaml": conf_content, "datadog_check_name": datadog_check_name}

    @classmethod
    def get_yaml_config_content(cls, plugin_base):
        conf_yaml_path = os.path.join(plugin_base, os.listdir(plugin_base)[0], "etc", "conf.yaml.tpl")
        if not os.path.exists(conf_yaml_path):
            conf_yaml_path = os.path.join(plugin_base, os.listdir(plugin_base)[0], "etc", "conf.yaml.example")
            if not os.path.exists(conf_yaml_path):
                raise PluginParseError({"msg": _("缺少 conf.yaml.example 配置模板文件")})
        with open(conf_yaml_path, "r", encoding="utf-8") as fp:
            conf_content = fp.read()
        return conf_content

    @classmethod
    def get_datadog_check_name(cls, plugin_base):
        meta_yaml_path = os.path.join(plugin_base, os.listdir(plugin_base)[0], "info", "meta.yaml")
        if not os.path.exists(meta_yaml_path):
            raise PluginParseError({"msg": _("缺少 meta.yaml 配置模板文件")})
        with open(meta_yaml_path, "r", encoding="utf-8") as fp:
            datadog_check_name = ""
            for line in fp.readlines():
                if "datadog_check_name" in line:
                    datadog_check_name = line.split(":")[1].strip()
            if not datadog_check_name:
                raise PluginParseError({"msg": _("meta.yaml 缺少 datadog_check_name")})
        return datadog_check_name
