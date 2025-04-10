from typing import Any, Dict, List

from django.conf import settings

from apps.api import JobApi
from apps.constants import DEFAULT_EXECUTE_SCRIPT_TIMEOUT, ScriptType
from apps.log_commons.adapt_ipv6 import fill_bk_host_id, fill_ip_and_cloud_id


class JobHelper:
    @classmethod
    def adapt_hosts_target_server(cls, bk_biz_id: int, hosts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        转换JOB目标机器, IPV6环境下, 主机只能用host_id_list, IPV4环境下, ip_list/host_id_list都可以
        :param bk_biz_id: 业务ID
        :param hosts: 主机列表, [{"bk_host_id": 1, "ip": "127.0.0.1", "bk_cloud_id": 0}]
        :return: 转换后的目标机器
        """
        # 定义这两个是因为JOB不支持集群模板和服务模板, 所以需要将其转换成主机的形式
        if settings.ENABLE_DHCP:
            return {
                "host_id_list": [item["bk_host_id"] for item in fill_bk_host_id(ip_list=hosts, bk_biz_id=bk_biz_id)]
            }
        else:
            hosts = fill_ip_and_cloud_id(bk_biz_id=bk_biz_id, ip_list=hosts)
            return {"ip_list": [{"ip": item["ip"], "bk_cloud_id": item["bk_cloud_id"]} for item in hosts]}

    @classmethod
    def execute_script(
        cls,
        script_content: str,
        target_server: List[Dict[str, Any]],
        bk_biz_id: int,
        bk_username: str,
        account: str,
        task_name: str,
        script_param=None,
        script_language: int = ScriptType.SHELL.value,
        timeout: int = DEFAULT_EXECUTE_SCRIPT_TIMEOUT,
    ):
        """
        调用JOB平台的fast_execute_script执行脚本
        JOB目前支持以下四种形式target_server:
        - ip_list(主机)
        - host_id_list(主机)
        - dynamic_group_list(动态分组)
        - topo_node_list(拓扑节点)
        :param script_content: 脚本内容
        :param target_server: 目标机器
        :param bk_biz_id: 业务ID
        :param bk_username: 操作人
        :param account: 账号
        :param task_name: 任务名称
        :param script_param: 脚本参数
        :param script_language: 脚本语言, 默认shell
        :param timeout: 超时时间
        """
        kwargs = {
            "bk_biz_id": bk_biz_id,
            "bk_username": bk_username,
            "account_alias": account,
            "script_content": script_content,
            "script_language": script_language,
            "task_name": task_name,
            "target_server": target_server,
            "timeout": timeout,
            "operator": bk_username,
        }
        if script_param:
            kwargs["script_param"] = script_param
        return JobApi.fast_execute_script(kwargs, request_cookies=False)
