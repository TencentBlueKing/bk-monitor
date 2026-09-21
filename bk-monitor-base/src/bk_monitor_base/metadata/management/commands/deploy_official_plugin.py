import re

from django.core.management import BaseCommand

from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID
from bk_monitor_base.infras.third_party_api.cmdb.api import HostIPParams
from bk_monitor_base.infras.third_party_api.nodeman.api import PluginOperateParams
from bk_monitor_base.metadata.config import settings


def split_list(raw_string):
    if isinstance(raw_string, tuple | list | set):
        return raw_string
    return [x for x in re.compile(r"\s*[;,]\s*").split(raw_string) if x]


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
            bk_biz_id = settings.blueking.default_bk_biz_id

        node_man_version = options.get("node_man_version")

        message = f"Start to deply plugin({plugin_name}@{plugin_version}) to target_hosts({target_hosts})"
        self.stdout.write(message)

        if node_man_version == "2.0":
            self.deploy_2_0(bk_biz_id, plugin_name, plugin_version, target_hosts)

    def deploy_2_0(self, bk_biz_id: int, plugin_name: str, plugin_version: str, target_hosts: list[str]):
        print("deploy with nodeman2.0")
        try:
            ips: list[HostIPParams] = [{"ip": ip} for ip in target_hosts]
            hosts = api.cmdb.get_host_by_ip(bk_tenant_id=DEFAULT_TENANT_ID, ips=ips, bk_biz_id=bk_biz_id)
            bk_host_ids: list[int] = [h.bk_host_id for h in hosts]
        except Exception:  # noqa
            self.stderr.write("Get host info from CMDB error")
        else:
            params = PluginOperateParams(
                plugin_params={"name": plugin_name, "version": plugin_version},
                job_type="MAIN_INSTALL_PLUGIN",
                bk_host_id=bk_host_ids,
            )
            try:
                result = api.node_man.plugin_operate(bk_tenant_id=DEFAULT_TENANT_ID, params=params)
                message = f"update plugin success with result({result}), Please see detail in bk_nodeman SaaS"
                self.stdout.write(message)
            except Exception as e:  # noqa
                raise Exception(f"update plugin error:{e}, params:{params}")
