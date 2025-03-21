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
from django.conf import settings
from django.core.management.base import BaseCommand

from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api, resource
from metadata.models import CustomReportSubscription, TimeSeriesGroup
from metadata.models.storage import EventGroup
from monitor_web.commons.job import linux_system_info


def mark(msg, ok=True, prefix="\n"):
    SUCCESS = "[\033[32m√\033[0m]"
    ERROR = "[\033[31m×\033[0m]"
    if ok:
        print(f"{prefix}{SUCCESS}{msg}")
    else:
        print(f"{prefix}{ERROR}{msg}")


class Command(BaseCommand):
    """
    自定义上报无数据排障命令
    1. 确认data id是否创建成功
    2. 确认对应PROXY_IP列表
    3. 连接登录PROXY_IP执行命令检查10205端口被哪个插件进程占用
    4. 检查当前使用插件配置下发状态, 检查机器上配置文件是否成功下发该data_id
    5. 检查是否创建对应data_id订阅，打印对应订阅的step参数
    6. 若已创建对应订阅并且参数正确，重新执行订阅等待是否成功下发配置
    7. 若没有创建对应订阅，提示运行周期任务检查是否有报错日志
    """

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--data_id", type=int, required=True)

    def handle(self, **kwargs):
        bk_data_id = kwargs["data_id"]
        ts_qs = TimeSeriesGroup.objects.filter(bk_data_id=bk_data_id)
        event_qs = EventGroup.objects.filter(bk_data_id=bk_data_id)
        # 检查data id是否存在
        dataid_check_result = False
        bk_biz_id = None
        if ts_qs.exists():
            dataid_check_result = True
            bk_biz_id = ts_qs.first().bk_biz_id
        elif event_qs.exists():
            dataid_check_result = True
            bk_biz_id = event_qs.first().bk_biz_id

        mark("check data id status", dataid_check_result)
        if not dataid_check_result:
            print(f"- Description: dataid({bk_data_id})未成功创建，请确认对应自定义上报dataid创建状态")
            return
        else:
            print(f"- Description: dataid({bk_data_id})已成功创建，所属业务为: {bk_biz_id}")

        # 获取该业务对应云区域proxy ip
        proxies = api.node_man.get_proxies_by_biz(bk_biz_id=bk_biz_id)
        host_list = [{"ip": proxy.get("inner_ip", ""), "bk_cloud_id": proxy["bk_cloud_id"]} for proxy in proxies]
        proxy_biz_ids = {proxy["bk_biz_id"] for proxy in proxies}
        proxy_hosts = []
        for proxy_biz_id in proxy_biz_ids:
            current_proxy_hosts = api.cmdb.get_host_by_ip(
                ips=[
                    {"ip": proxy.get("inner_ip", ""), "bk_cloud_id": proxy["bk_cloud_id"]}
                    for proxy in proxies
                    if proxy["bk_biz_id"] == proxy_biz_id
                ],
                bk_biz_id=proxy_biz_id,
            )
            proxy_hosts.extend(current_proxy_hosts)
        bk_host_ids = [proxy.bk_host_id for proxy in proxy_hosts]

        # 获取直连云区域proxy ip
        proxy_ips = settings.CUSTOM_REPORT_DEFAULT_PROXY_IP
        hosts = api.cmdb.get_host_without_biz(ips=proxy_ips, bk_tenant_id=DEFAULT_TENANT_ID)["hosts"]
        host_list.extend([{"ip": host.bk_host_innerip, "bk_cloud_id": 0} for host in hosts if host.bk_cloud_id == 0])
        bk_host_ids.extend([host.bk_host_id for host in hosts])
        proxyip_check_result = host_list != []
        mark("check proxy ips status", proxyip_check_result)
        if proxyip_check_result:
            print(f"- Description: 应下发proxy机器列表如下：\n {host_list}")
        else:
            print("- Description: 应下发proxy机器列表为空，请确认是否在全局配置中设定默认自定义上报服务器")
            return

        # 确认自定义上报相关插件版本
        check_version_result = False
        params = {"page": 1, "pagesize": len(bk_host_ids), "conditions": [], "bk_host_id": bk_host_ids}
        plugin_info_list = api.node_man.plugin_search(params)["list"]
        if plugin_info_list:
            check_version_result = True
        mark("check plugin version", check_version_result)
        for plugin_info in plugin_info_list:
            proxy_ip = plugin_info.get("inner_ip", "")
            proxy_cloud_id = plugin_info.get("bk_cloud_id", "")
            plugin_status = plugin_info.get("plugin_status")
            proc_list = [i for i in plugin_status if i.get("name", "") in ["bk-collector", "bkmonitorproxy"]]
            for proc in proc_list:
                current_plugin_version = proc.get("version", "")
                mark(
                    f"proxy_ip({proxy_ip}|{proxy_cloud_id})" f" {proc['name']}插件版本为：{current_plugin_version}",
                    current_plugin_version,
                    "- Description: ",
                )

        # 检查proxy ip当前使用插件类型
        check_plugin_content = (
            """#!/bin/bash
            output=$(lsof -i :10205 | grep LISTEN)
            process_name=$(echo ${output} | awk '{print $1}')
            pid=$(echo ${output} | awk '{print $2}')
            if [[ -n ${pid} ]]; then
                full_process_name=$(ps -p ${pid} -o comm=)
                echo ${full_process_name}
            else
                echo ${process_name}
            fi
            pids=$(pgrep ${full_process_name})
            if [[ -n $pids ]]; then
                for pid in $pids; do
                    path=$(readlink -f /proc/$pid/exe)
                    parent_dir=$(dirname $(dirname "$path"))
                    echo "-process_path: $parent_dir"
            """
            + f"""
                     echo "-bk-collector:$(grep -r "{bk_data_id}" $parent_dir/etc/bk-collector/ | wc -l)"
                     echo "-bkmonitorproxy:$(grep -r "{bk_data_id}" $parent_dir/etc/bkmonitorproxy/ | wc -l)"
                done
            else
                echo "- Description: No processes found"
            fi
            """
        )

        result = resource.commons.fast_execute_script(
            host_list=[{"bk_host_id": host_id} for host_id in bk_host_ids],
            bk_biz_id=9991001,
            account_alias=linux_system_info.job_execute_account,
            script_content=check_plugin_content,
            script_type=linux_system_info.script_type,
            bk_scope_type="biz_set",
        )

        check_plugin_result = False
        if not result["failed"]:
            check_plugin_result = True
        plugin_name = None
        mark("check current plugin type", check_plugin_result)
        for proxy_result in result["success"]:
            log_content = proxy_result["log_content"]
            plugin_name = log_content.split("\n")[0]
            proxy_ip = proxy_result["ip"]
            bk_cloud_id = proxy_result["bk_cloud_id"]
            mark(f"proxy_ip({proxy_ip}|{bk_cloud_id}) 当前使用插件类型为：{plugin_name}", True, "- Description: ")

        for proxy_result in result["failed"]:
            proxy_ip = proxy_result["ip"]
            bk_cloud_id = proxy_result["bk_cloud_id"]
            errmsg = proxy_result["errmsg"]
            mark(f"登录proxy_ip({proxy_ip}|{bk_cloud_id}) 获取当前使用插件类型失败，输出日志为：\n{errmsg}", False, "- Description: ")

        mark("check data id exist", check_plugin_result)
        for proxy_result in result["success"]:
            log_content = proxy_result["log_content"]
            proxy_ip = proxy_result["ip"]
            bk_cloud_id = proxy_result["bk_cloud_id"]
            plugin_name = log_content.split("\n")[0]
            print(f"\n-----------proxy_ip({proxy_ip}|{bk_cloud_id})-------------\n")
            for log in log_content.split('\n')[1:]:
                prefix = log.split(":")[0]
                if "-process_path" in prefix:
                    print(f"当前gse插件下发配置路径为 {log.split(':')[-1]}")

                if plugin_name == "bk-collector" and "-bk-collector" in prefix:
                    collector_dataid_count = log.split(":")[-1].strip(" ")
                    try:
                        collector_dataid_exist = int(collector_dataid_count) != 0
                    except (ValueError, TypeError):
                        collector_dataid_exist = False
                    mark(
                        f"data id({bk_data_id}) collector配置{'成功' if collector_dataid_exist else '未成功'}下发",
                        collector_dataid_exist,
                        "- Description: ",
                    )

                if "-bkmonitorproxy" in prefix:
                    proxy_dataid_count = log.split(":")[-1].strip(" ")
                    try:
                        proxy_dataid_exist = int(proxy_dataid_count) != 0
                    except (ValueError, TypeError):
                        proxy_dataid_exist = False
                    mark(
                        f"data id({bk_data_id}) bkmonitorproxy配置{'成功' if proxy_dataid_exist else '未成功'}下发",
                        proxy_dataid_exist,
                        "- Description: ",
                    )

        for proxy_result in result["failed"]:
            proxy_ip = proxy_result["ip"]
            bk_cloud_id = proxy_result["bk_cloud_id"]
            print(f"\n-----------proxy_ip({proxy_ip}|{bk_cloud_id})-------------\n")
            mark(f"获取proxy_ip[{proxy_ip}|{bk_cloud_id}] 获取data id数量信息失败", False, "- Description: ")

        collector_qs = CustomReportSubscription.objects.filter(bk_data_id=bk_data_id)
        proxy_qs = CustomReportSubscription.objects.filter(bk_biz_id=bk_biz_id, bk_data_id=0)

        if plugin_name and plugin_name == "bk-collector":
            if collector_qs.exists():
                check_config_exist_result = check_scope_result = check_step_result = True
                scope = collector_qs.first().config.get("scope", {})
                steps = collector_qs.first().config.get("steps", [])
                subscription_id = collector_qs.first().subscription_id
                nodes = scope.get("nodes", [])
                for bk_host_id in bk_host_ids:
                    if {"bk_host_id": bk_host_id} not in nodes:
                        check_scope_result = False
                        break
                if not steps:
                    check_step_result = False

                all_collector_check = check_config_exist_result and check_scope_result and check_step_result
                mark("check bk-collector subscription config", all_collector_check)
                mark(
                    f"data id({bk_data_id})相关bk-collector订阅已创建, 订阅id为 {subscription_id}",
                    check_config_exist_result,
                    "- Description: ",
                )
                mark(
                    f"订阅scope下发节点中目标porxy host id {bk_host_ids}{'已存在' if check_scope_result else '不存在'}" f"\n {scope}",
                    check_scope_result,
                    "- Description: ",
                )
                mark(f"订阅steps下发参数{'正确' if check_step_result else '错误,' + steps}", check_step_result, "- Description: ")
                if all_collector_check:
                    api.node_man.run_subscription(subscription_id=subscription_id, actions={plugin_name: "INSTALL"})
                    print("collector订阅配置正确，若data id仍未成功下发将重新执行相关订阅，请五分钟后再次使用命令检查相关配置，依然存在问题需联系节点管理。")
                    return
            else:
                mark("check bk-collector subscription config", False)
                print(
                    f"- Description: data id({bk_data_id})相关bk-collector订阅未创建，"
                    f"请确认周期任务refresh_custom_report_to_node_man是否成功执行"
                )

        if proxy_qs.exists():
            check_config_exist_result = check_scope_result = True
            check_step_result = False
            scope = proxy_qs.first().config.get("scope", {})
            steps = proxy_qs.first().config.get("steps", [])
            if steps:
                items = steps[0]["params"]["context"]["items"]
                for item in items:
                    if item.get("dataid", "") == bk_data_id:
                        check_step_result = True
                        break
            subscription_id = proxy_qs.first().subscription_id
            nodes = scope.get("nodes", [])
            for bk_host_id in bk_host_ids:
                if {"bk_host_id": bk_host_id} not in nodes:
                    check_scope_result = False
                    break

            mark(
                "check bkmonitorproxy subscription config",
                check_config_exist_result and check_scope_result and check_step_result,
            )
            mark(
                f"data id({bk_data_id})相关bkmonitorproxy订阅已创建, 订阅id为 {subscription_id}",
                check_config_exist_result,
                "- Description: ",
            )
            mark(
                f"订阅scope下发节点中目标porxy host id {bk_host_ids}{'已存在' if check_scope_result else '不存在'}" f"\n {scope}",
                check_scope_result,
                "- Description: ",
            )
            mark(
                f"订阅steps下发参数中data id {bk_data_id}{'已存在' if check_step_result else '不存在，请确认bkmonitorproxy是否停用'}",
                check_step_result,
                "- Description: ",
            )
            if check_config_exist_result and check_scope_result and check_step_result:
                api.node_man.run_subscription(subscription_id=subscription_id, actions={plugin_name: "INSTALL"})
                print("bkmonitorproxy订阅配置正确，若data id仍未成功下发将重新执行相关订阅，请五分钟后再次使用命令检查相关配置，依然存在问题需联系节点管理。")
                return
        else:
            mark("check bkmonitorproxy subscription config", False)
            mark(
                f"data id({bk_data_id})相关bkmonitorproxy订阅未创建，" f"请确认周期任务refresh_custom_report_to_node_man是否成功执行",
                False,
                "- Description: ",
            )
