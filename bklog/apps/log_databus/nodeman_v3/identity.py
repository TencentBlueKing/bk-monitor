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

import os

from apps.log_databus.nodeman_v3.constants import (
    RESOURCE_TYPE_COLLECTOR_CONFIG,
    SUB_CONFIG_NAME_DEPLOY_INFIX,
)


def build_sub_config_name(template_name: str, deploy_policy_id: int) -> str:
    """
    推导采集项子配置在主机上的落地文件名。

    同机多个采集项共用 bkunifylogbeat 且子配置都来自同名模板（如 bkunifylogbeat.conf），
    子配置身份由节点管理按「模板名 + 部署策略 ID」生成，规则见 NodeMan
    internal/backend/dpmgr/utils.go 的 genDeployPolicySubConfigNameByConfigTemplateName：
    `<模板名去扩展名>_deploy_<deploy_policy_id><扩展名>`。
    因为「一个采集项一个部署策略」，策略 ID 就构成了采集项之间的隔离。

    这里复刻该规则只用于状态对账与精确删除（list_config_files / remove_subconfig 都按文件名对齐），
    下发时不需要我们指定文件名。这是与 NodeMan 的隐式契约耦合点：若对方改了命名规则，
    对账会失配（表现为「已下发但查不到生效」），需要同步本函数。
    """
    stem, ext = os.path.splitext(template_name)
    return f"{stem}{SUB_CONFIG_NAME_DEPLOY_INFIX}{deploy_policy_id}{ext}"


def build_policy_name(collector_config_id: int) -> str:
    """
    部署策略名称。

    节点管理没有提供 deploy_policy 删除接口，策略对象只能复用不能销毁，
    因此策略名必须能由采集项 ID 稳定推导，用于本地 binding 丢失时按名称找回既有策略，
    避免给同一个采集项重复建策略（会导致同机出现两份子配置、日志重复上报）。
    """
    return f"bklog-collector-{collector_config_id}"


def build_resource_key(collector_config_id: int) -> str:
    return f"{RESOURCE_TYPE_COLLECTOR_CONFIG}:{collector_config_id}"
