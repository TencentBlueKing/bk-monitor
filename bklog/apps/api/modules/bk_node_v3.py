"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

"""
节点管理 V3 调用接口汇总

与 bk_node.py（V2 Subscription）完全独立：V3 只在 V3-only 模式下被导入与调用，
避免 V2 模式进程加载任何 V3 代码路径。
"""

from urllib.parse import urljoin

from django.conf import settings

from apps.api.base import DataAPI  # noqa
from apps.api.modules.utils import add_esb_info_before_request  # noqa
from apps.log_databus.nodeman_v3.compat import adapt_non_bkcc_for_bknode_v3


def get_bk_node_v3_request_before(params):
    params = add_esb_info_before_request(params)
    params = adapt_non_bkcc_for_bknode_v3(params)
    return params


class _BKNodeV3Api:
    MODULE = "节点管理V3"

    def _build_url(self, action: str) -> str:
        """
        V3 只有 APIGW 一条入口（ESB compapi 未提供 v3），base_url 支持独立配置以便联调环境直连。
        """
        base_url = settings.BKNODEMAN_V3_API_BASE_URL or (
            f"{settings.PAAS_API_HOST}/api/bk-nodeman/{settings.ENVIRONMENT}/"
        )
        if not base_url.endswith("/"):
            base_url += "/"
        return urljoin(base_url, action)

    def __init__(self):
        # ------------------------------------------------------------------
        # 主机与进程（读）
        # ------------------------------------------------------------------
        self.list_hosts = DataAPI(
            method="POST",
            url=self._build_url("api/v3/topo/host/list"),
            module=self.MODULE,
            description="查询主机列表",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )
        self.list_processes = DataAPI(
            method="POST",
            url=self._build_url("api/v3/process/list"),
            module=self.MODULE,
            description="查询插件进程列表",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )
        self.get_process_distribution_by_plugin_name = DataAPI(
            method="POST",
            url=self._build_url("api/v3/process/get_distribution_by_plugin_name"),
            module=self.MODULE,
            description="按插件名查询进程分布",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )

        # ------------------------------------------------------------------
        # 插件子配置（BKL-2 核心）
        # ------------------------------------------------------------------
        self.apply_subconfig = DataAPI(
            method="POST",
            url=self._build_url("api/v3/plugin/apply_subconfig"),
            module=self.MODULE,
            description="下发插件子配置",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )
        self.remove_subconfig = DataAPI(
            method="POST",
            url=self._build_url("api/v3/plugin/remove_subconfig"),
            module=self.MODULE,
            description="删除插件子配置（删除后触发插件 reload）",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )
        self.list_config_files = DataAPI(
            method="POST",
            url=self._build_url("api/v3/plugin/list_config_files"),
            module=self.MODULE,
            description="查询主机上插件的配置文件列表",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )
        self.list_plugins = DataAPI(
            method="POST",
            url=self._build_url("api/v3/plugin/list"),
            module=self.MODULE,
            description="查询插件列表",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )
        self.list_release_plugin_brief = DataAPI(
            method="POST",
            url=self._build_url("api/v3/package/release/plugin/list/brief"),
            module=self.MODULE,
            description="查询已发布插件包精简列表（用于把 latest 解析为具体版本）",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )

        # ------------------------------------------------------------------
        # 部署策略（采集项期望态载体）
        # ------------------------------------------------------------------
        self.create_deploy_policy = DataAPI(
            method="POST",
            url=self._build_url("api/v3/deploy_policy/create"),
            module=self.MODULE,
            description="创建部署策略",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )
        self.update_deploy_policy = DataAPI(
            method="POST",
            url=self._build_url("api/v3/deploy_policy/update"),
            module=self.MODULE,
            description="更新部署策略",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )
        self.execute_deploy_policy = DataAPI(
            method="POST",
            url=self._build_url("api/v3/deploy_policy/execute"),
            module=self.MODULE,
            description="执行部署策略（触发一次收敛，返回 trigger_id）",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )
        self.list_deploy_policies = DataAPI(
            method="POST",
            url=self._build_url("api/v3/deploy_policy/list"),
            module=self.MODULE,
            description="查询部署策略列表",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )

        # ------------------------------------------------------------------
        # Workflow / Operation（任务追踪）
        # ------------------------------------------------------------------
        self.list_workflows = DataAPI(
            method="POST",
            url=self._build_url("api/v3/plugin/workflow/list"),
            module=self.MODULE,
            description="查询插件工作流列表（支持按 deploy_policy_id 反查 workflow_id）",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )
        self.list_workflow_operations = DataAPI(
            method="POST",
            url=self._build_url("api/v3/plugin/workflow/operation/list"),
            module=self.MODULE,
            description="查询工作流操作列表",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )
        self.list_workflow_operation_instances = DataAPI(
            method="POST",
            url=self._build_url("api/v3/plugin/workflow/operation/instance/list"),
            module=self.MODULE,
            description="查询工作流操作实例列表",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )
        self.get_workflow_operation_instance_log = DataAPI(
            method="POST",
            url=self._build_url("api/v3/plugin/workflow/operation/instance/log/get"),
            module=self.MODULE,
            description="查询工作流操作实例日志",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )
        self.list_workflow_operation_instance_status_distribution = DataAPI(
            method="POST",
            url=self._build_url("api/v3/plugin/workflow/operation/instance/status_distribution/list"),
            module=self.MODULE,
            description="按 trigger_id 查询操作实例状态分布",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )
        self.retry_workflow_operation = DataAPI(
            method="POST",
            url=self._build_url("api/v3/plugin/workflow/operation/retry"),
            module=self.MODULE,
            description="重试工作流操作",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )
        self.terminate_workflow_operation = DataAPI(
            method="POST",
            url=self._build_url("api/v3/plugin/workflow/operation/terminate"),
            module=self.MODULE,
            description="终止工作流操作",
            before_request=get_bk_node_v3_request_before,
            use_superuser=True,
        )


BKNodeV3Api = _BKNodeV3Api()
