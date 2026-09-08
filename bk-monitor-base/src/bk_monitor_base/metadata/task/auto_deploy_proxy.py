import logging
import re

from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID
from bk_monitor_base.infras.third_party_api.cmdb.api import HostPropertyFilter, format_ip_filter_rule
from bk_monitor_base.infras.third_party_api.nodeman.api import PluginOperateParams, PluginSearchParams
from bk_monitor_base.infras.third_party_api.user.api import list_tenant
from bk_monitor_base.metadata.config import settings
from bk_monitor_base.metadata.utils.version import get_max_version

logger = logging.getLogger("metadata")


class ProcStatus:
    NOT_REGISTED: int = 0
    RUNNING: int = 1
    TERMINATED: int = 2


class AutoDeployProxy:
    """
    Auto Deploy Proxy(bkmonitorproxy), include first deploy, upgrade
    """

    VERSION_PATTERN = re.compile(r"[vV]?(\d+\.){1,5}\d+$")

    @classmethod
    def deploy_proxy(
        cls, bk_tenant_id: str, plugin_name: str, plugin_version: str, bk_cloud_id: int, bk_host_ids: list[int]
    ):
        """
        在指定云区域的指定主机上部署插件
        :param bk_tenant_id: 租户ID
        :param plugin_name: 插件名称
        :param plugin_version: 插件版本
        :param bk_cloud_id: 云区域ID
        :param bk_host_ids: 主机ID列表
        """
        logger.info(
            f"update proxy on bk_cloud_id({bk_cloud_id}), get host_ids->[{','.join([str(h) for h in bk_host_ids])}]"
        )
        # 查询当前版本
        params = PluginSearchParams(
            conditions=[],
            bk_host_id=bk_host_ids,
            page=1,
            pagesize=len(bk_host_ids),
        )
        plugin_info_list = api.node_man.plugin_search(bk_tenant_id=bk_tenant_id, params=params)["list"]
        logger.info("get plugin info from nodeman -> [%s]", str(plugin_info_list))
        deploy_host_list: list[int] = []
        for plugin_info in plugin_info_list:
            plugin_status = plugin_info.get("plugin_status")
            proc_list = [i for i in plugin_status if i.get("name", "") == plugin_name]
            proc = {}
            if proc_list:
                proc = proc_list[0]

            current_plugin_version = cls.VERSION_PATTERN.search(proc.get("version", ""))
            current_plugin_version = current_plugin_version.group() if current_plugin_version else ""
            # 已经是最新的版本，则无需部署
            if current_plugin_version == plugin_version:
                continue

            deploy_host_list.append(plugin_info["bk_host_id"])

        logger.info("get deploy host list->[%s]", ",".join([str(h) for h in deploy_host_list]))
        if not deploy_host_list:
            logger.info("all proxy of bk_cloud_id({}) is already deployed")
            return

        params = PluginOperateParams(
            plugin_params={"name": plugin_name, "version": plugin_version},
            job_type="MAIN_INSTALL_PLUGIN",
            bk_host_id=deploy_host_list,
        )
        try:
            result = api.node_man.plugin_operate(bk_tenant_id=bk_tenant_id, params=params)
            message = f"update ({plugin_name}) to version({plugin_version}) success with result({result}), Please see detail in bk_nodeman SaaS"
            logger.info(message)
        except Exception as e:  # noqa
            raise Exception(f"update ({plugin_name}) error:{e}, params:{params}")

        logger.info("refresh bk_cloud_id->[%s] proxy success", bk_cloud_id)

    @classmethod
    def get_proxy_hosts_by_cloud(cls, bk_tenant_id: str, bk_cloud_id: int) -> list[int]:
        """
        获取指定云区域下的代理主机列表
        :param bk_tenant_id: 租户ID
        :param bk_cloud_id: 云区域ID
        :return: 代理主机列表
        """
        bk_host_ids: list[int] = []
        proxies = api.node_man.get_proxies(bk_tenant_id=bk_tenant_id, bk_cloud_id=bk_cloud_id)
        logger.info("bk_cloud_id->[%d] has %d proxies", bk_cloud_id, len(proxies))
        # 获取全体proxy主机列表
        for proxy in proxies:
            if proxy["status"] != "RUNNING":
                logger.warning("proxy({}) can not be use, because it's status not running".format(proxy["inner_ip"]))
                continue
            bk_host_ids.append(proxy["bk_host_id"])
        return bk_host_ids

    @classmethod
    def deploy_with_cloud_id(cls, bk_tenant_id: str, plugin_name: str, plugin_version: str, bk_cloud_id: int):
        """
        在指定云区域下部署插件
        :param bk_tenant_id: 租户ID
        :param plugin_name: 插件名称
        :param plugin_version: 插件版本
        :param bk_cloud_id: 云区域ID
        """
        bk_host_ids = cls.get_proxy_hosts_by_cloud(bk_tenant_id=bk_tenant_id, bk_cloud_id=bk_cloud_id)
        if len(bk_host_ids) == 0:
            logger.info("bk_cloud_id->[%s] has no proxy host, skip it", bk_cloud_id)
            return

        cls.deploy_proxy(
            bk_tenant_id=bk_tenant_id,
            plugin_name=plugin_name,
            plugin_version=plugin_version,
            bk_cloud_id=bk_cloud_id,
            bk_host_ids=bk_host_ids,
        )

    @classmethod
    def deploy_direct_area_proxy(cls, bk_tenant_id: str, plugin_name: str, plugin_version: str):
        """
        在直连区域下部署插件
        :param bk_tenant_id: 租户ID
        :param plugin_name: 插件名称
        :param plugin_version: 插件版本
        """
        proxy_ips = settings.metadata.custom_report_default_proxy_ip
        if not proxy_ips:
            logger.info("no proxy host in direct area, skip it")
            return
        ip_filters = format_ip_filter_rule(proxy_ips)
        _, hosts = api.cmdb.list_hosts_without_biz(
            bk_tenant_id=bk_tenant_id, host_property_filter=HostPropertyFilter(condition="AND", rules=ip_filters)
        )
        hosts = [h for h in hosts if h.bk_cloud_id == 0]
        bk_host_ids = [h.bk_host_id for h in hosts]

        if not bk_host_ids:
            logger.info("no proxy host in direct area, skip it")
            return

        cls.deploy_proxy(
            bk_tenant_id=bk_tenant_id,
            plugin_name=plugin_name,
            plugin_version=plugin_version,
            bk_cloud_id=0,
            bk_host_ids=bk_host_ids,
        )

    @classmethod
    def find_latest_version(cls, bk_tenant_id: str, plugin_name: str) -> str:
        """
        从节点管理获取插件的最新版本
        :param bk_tenant_id: 租户ID
        :param plugin_name: 插件名称
        :return: 最新版本
        """
        default_version = "0.0.0"
        plugin_infos = api.node_man.get_plugin_info(
            bk_tenant_id=bk_tenant_id,
            name=plugin_name,
        )
        version_str_list = [p.version or default_version for p in plugin_infos if p.is_ready]
        return get_max_version(default_version, version_str_list)

    @classmethod
    def _refresh(cls, bk_tenant_id: str, plugin_name: str):
        """
        自动部署单个租户下的插件
        :param bk_tenant_id: 租户ID
        :param plugin_name: 插件名称
        """

        # 获取插件的最新版本
        plugin_latest_version = cls.find_latest_version(bk_tenant_id=bk_tenant_id, plugin_name=plugin_name)
        logger.info(f"find {plugin_name} version {plugin_latest_version} from bk_nodeman, start auto deploy.")

        # 云区域
        cloud_infos = api.cmdb.search_cloud_area(bk_tenant_id=bk_tenant_id)
        for cloud_info in cloud_infos:
            bk_cloud_id = cloud_info.get("bk_cloud_id", -1)
            if int(bk_cloud_id) <= 0:
                continue

            try:
                cls.deploy_with_cloud_id(
                    bk_tenant_id=bk_tenant_id,
                    plugin_name=plugin_name,
                    plugin_version=plugin_latest_version,
                    bk_cloud_id=bk_cloud_id,
                )
            except Exception as e:
                logger.exception(f"Auto deploy {plugin_name} error, with bk_cloud_id({bk_cloud_id}), error({e}).")

        # 仅在默认租户下部署直连区域
        if bk_tenant_id == DEFAULT_TENANT_ID:
            try:
                cls.deploy_direct_area_proxy(
                    bk_tenant_id=bk_tenant_id, plugin_name=plugin_name, plugin_version=plugin_latest_version
                )
            except Exception as e:
                logger.exception(f"Auto deploy {plugin_name} error, with direct area, error({e}).")

    @classmethod
    def refresh(cls, plugin_name: str) -> None:
        """
        自动部署插件
        :param plugin_name: 插件名称
        """
        # 如果关闭自动部署，则直接返回
        if not settings.metadata.is_auto_deploy_custom_report_server:
            logger.info("auto deploy custom report server is closed. do nothing.")
            return

        # 遍历所有租户，自动部署插件
        for tenant in list_tenant():
            try:
                cls._refresh(bk_tenant_id=tenant["id"], plugin_name=plugin_name)
            except Exception as e:
                logger.exception(f"Auto deploy {plugin_name} error, with bk_tenant_id({tenant['id']}), error({e}).")


def main():
    AutoDeployProxy.refresh("bk-collector")
