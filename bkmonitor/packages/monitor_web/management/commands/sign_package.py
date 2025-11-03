"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import os
import shutil
import tarfile
import tempfile

import yaml
from django.core.management import BaseCommand
from django.utils.translation import gettext as _

from constants.common import DEFAULT_TENANT_ID
from core.errors.plugin import PluginParseError
from monitor_web.models.plugin import CollectorPluginMeta
from monitor_web.plugin.constant import OS_TYPE_TO_DIRNAME
from monitor_web.plugin.manager import PluginManagerFactory
from monitor_web.plugin.signature import load_plugin_signature_manager


class Command(BaseCommand):
    """
    对导出的插件包进行签名
    >>> python manage.py sign_package bkplugin_redis-1.1.tgz --dest /dest/path
    """

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--bk_tenant_id", dest="bk_tenant_id", default=DEFAULT_TENANT_ID, help="bk_tenant_id")
        parser.add_argument("src_path", type=str, help="the source package path")
        parser.add_argument("--dest", dest="dest_path", default=".", help="package dest path")
        parser.add_argument("--protocols", dest="protocols", default="strict,default", help="make an official package?")
        parser.add_argument("--ver", dest="ver", default="", help="package version")

    def handle(self, **kwargs):
        src_path = kwargs["src_path"]
        dest_path = kwargs["dest_path"]
        protocols = kwargs["protocols"].split(",")
        bk_tenant_id = kwargs["bk_tenant_id"]

        if not kwargs["ver"]:
            config_version, info_version = None, None
        else:
            try:
                config_version, info_version = kwargs["ver"].split(".")
            except Exception:
                raise ValueError("version number format error, example: 2.3")

        # 1. 解压插件包
        tmp_dir = tempfile.mkdtemp()
        print("1/4 unzip package")
        with open(src_path, "rb") as tar_obj:
            with tarfile.open(fileobj=tar_obj, mode="r:gz") as tar:
                print(f"Package unzip in tmp path: {tmp_dir}")
                filename_list = []
                for member in tar.getmembers():
                    # 只处理普通文件，避免符号链接等特殊文件类型带来的安全风险
                    if not member.isreg():
                        continue
                    # 规范化路径并检查安全性，防止路径遍历攻击
                    member_path = os.path.normpath(member.name)
                    if member_path.startswith("..") or member_path.startswith("/"):
                        continue
                    # 通过TarInfo对象安全地提取文件内容
                    with tar.extractfile(member) as f:
                        target_path = os.path.join(tmp_dir, member_path)
                        # 确保解压路径在预期的临时目录内
                        if not os.path.realpath(target_path).startswith(os.path.realpath(tmp_dir)):
                            continue
                        # 确保目标目录存在
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, "wb") as target_file:
                            target_file.write(f.read())
                    filename_list.append(member.name)

        # 2. 解析 meta.yaml
        print("2/4 parse meta.yaml")
        meta_yaml_path = ""
        plugin_id = None
        # 获取plugin_id, meta.yaml必要信息
        for filename in filename_list:
            path = filename.split("/")
            if path[-1] == "meta.yaml" and path[-2] == "info" and path[-4] in list(OS_TYPE_TO_DIRNAME.values()):
                plugin_id = path[-3]
                meta_yaml_path = os.path.join(tmp_dir, filename)
                break

        if not plugin_id:
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
                plugin_type = name
                break
        else:
            raise PluginParseError({"msg": _("无法解析插件类型")})

        print(f"Parse success. Plugin ID: {plugin_id}, Plugin Type: {plugin_type}")

        print("3/4 sign package")
        # 3. 根据插件包构造 db 条目，并执行签名
        import_manager = PluginManagerFactory.get_manager(
            bk_tenant_id=bk_tenant_id, plugin=plugin_id, plugin_type=plugin_type, tmp_path=tmp_dir
        )
        tmp_version = import_manager.get_tmp_version(config_version=config_version, info_version=info_version)

        sig_manager = load_plugin_signature_manager(tmp_version)
        tmp_version.signature = sig_manager.signature(protocols).dumps2python()

        # 4. 重新打包
        print(
            f"4/4 finish sign and make package: {plugin_id}({plugin_type}), version: {tmp_version.config_version}.{tmp_version.info_version}"
        )
        import_manager.make_package()
        package_path = os.path.join(import_manager.tmp_path, plugin_id + ".tgz")
        dest = os.path.join(dest_path, f"{tmp_version}-official.tgz")
        shutil.copyfile(package_path, dest)
        print(f"Package is saved in {dest}")
        shutil.rmtree(import_manager.tmp_path)
        print("done!")
