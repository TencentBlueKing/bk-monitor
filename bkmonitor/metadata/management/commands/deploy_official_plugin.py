"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings
from django.core.management import BaseCommand

from bkmonitor.models import GlobalConfig
from bkmonitor.utils.common_utils import split_list
from core.drf_resource import api


class Command(BaseCommand):
    """
    部署插件

    目前用来更新直连区域的bkmonitorproxy插件
    """

    def add_arguments(self, parser):
        """
        增加参数配置
        :param parser:
        :return:
        """

        parser.add_argument("--plugin_name", default="", help="Which plugin to deploy")

        parser.add_argument("--plugin_version", default="latest", help="version of plugin")

        parser.add_argument(
            "--target_hosts",
            default="",
            help="Target hosts for deployment, Only support default cloud area. Example: -t 127.0.0.1,127.0.0.2",
        )

        parser.add_argument("--bk_biz_id", default="", help="bk_biz_id of target hosts, default: blueking")

        parser.add_argument(
            "--node_man_version",
            default="2.0",
            choices=("1.3", "2.0"),
            required=False,
            help="node_man version, default: 2.0",
        )

    def handle(self, *args, **options):
        """
        1. 从参数中获取到插件名称plugin_name，以及目标机器的IP列表target_hosts
        2. 组装节点管理插件更新API参数
        3. 更新目标主机到全部配置
        :param args:
        :param options:
        :return:
        """
        plugin_name = options.get("plugin_name")
        if not plugin_name:
            raise Exception("Plugin name can not be empty")

        plugin_version = options.get("plugin_version", "latest")

        target_hosts = options.get("target_hosts", "")
        if not target_hosts:
            raise Exception("Target hosts can not be empty")
        target_hosts = list(set(split_list(target_hosts)))

        bk_biz_id = options.get("bk_biz_id")
        if not bk_biz_id:
            bk_biz_id = settings.DEFAULT_BK_BIZ_ID

        node_man_version = options.get("node_man_version")

        message = f"Start to deply plugin({plugin_name}@{plugin_version}) to target_hosts({target_hosts})"
        self.stdout.write(message)

        if node_man_version == "2.0":
            self.deploy_2_0(bk_biz_id, plugin_name, plugin_version, target_hosts)
        else:
            self.deploy_1_3(bk_biz_id, plugin_name, plugin_version, target_hosts)

        self.update_to_global_config(plugin_name, target_hosts=target_hosts)

    def deploy_2_0(self, bk_biz_id, plugin_name, plugin_version, target_hosts):
        print("deploy with nodeman2.0")
        try:
            ips = [{"ip": ip} for ip in target_hosts]
            hosts = api.cmdb.get_host_by_ip(ips=ips, bk_biz_id=bk_biz_id)
            bk_host_ids = [h.bk_host_id for h in hosts]
        except Exception:  # noqa
            self.stderr.write("Get host info from CMDB error")
        else:
            params = dict(
                plugin_params={"name": plugin_name, "version": plugin_version},
                job_type="MAIN_INSTALL_PLUGIN",
                bk_host_id=bk_host_ids,
            )
            try:
                result = api.node_man.plugin_operate(**params)
                message = f"update plugin success with result({result}), Please see detail in bk_nodeman SaaS"
                self.stdout.write(message)
            except Exception as e:  # noqa
                raise Exception(f"update plugin error:{e}, params:{params}")

    def deploy_1_3(self, bk_biz_id, plugin_name, plugin_version, target_hosts):
        print("deploy with nodeman1.3")
        try:
            plugin_info = api.node_man.get_process_info(process_name=plugin_name)
            package_list = api.node_man.get_package_info(process_name=plugin_name)

            package_info = None
            package_mtime = None
            for p in package_list:
                if plugin_version == p["version"]:
                    package_info = p
                    break
                p_mtime = p["pkg_mtime"]
                if package_mtime is None or p_mtime > package_mtime:
                    package_mtime = p_mtime
                    package_info = p
            control_info = api.node_man.get_control_info(process_name=plugin_name, plugin_package_id=package_info["id"])
        except Exception as e:  # noqa
            self.stderr.write(f"deploy plugin({plugin_name}) error, Can not get plugin info from bk_nodeman")
            return

        self.deploy_with_nodeman_1_3(bk_biz_id, plugin_info, package_info, control_info, target_hosts)

    def deploy_with_nodeman_1_3(self, bk_biz_id, plugin, package, control, hosts):
        params = {
            "creator": settings.COMMON_USERNAME,
            "bk_biz_id": bk_biz_id,
            "bk_cloud_id": "0",  # Only support default cloud area
            "op_type": "UPGRADE",
            "node_type": "PLUGIN",
            "hosts": [{"conn_ips": i} for i in hosts],
            "global_params": {
                "option": {"keep_config": False, "no_restart": False, "no_delegate": False},
                "upgrade_type": "APPEND",
                "plugin": plugin,
                "package": package,
                "control": control,
            },
        }
        try:
            result = api.node_man.tasks(params)
            message = f"update plugin success with result({result}), Please see detail in bk_nodeman SaaS"
            self.stdout.write(message)

        except Exception as e:  # noqa
            raise Exception(f"update plugin error:{e}, params:{params}")

    def update_to_global_config(self, plugin_name, target_hosts):
        plugin_name_global_config_key = {
            "bkmonitorproxy": "CUSTOM_REPORT_DEFAULT_PROXY_IP",
            "bk-collector": "CUSTOM_REPORT_DEFAULT_PROXY_IP",
        }.get(plugin_name)
        if not plugin_name_global_config_key:
            print("plugin_name(%s) does not exists global config, do nothing", plugin_name)
            return

        qs = GlobalConfig.objects.filter(key=plugin_name_global_config_key)
        if qs.exists():
            old_hosts = qs.first().value
            print(f"Old Proxy({old_hosts}) will be replace with New Proxy({target_hosts})")
        qs.update(value=target_hosts)
