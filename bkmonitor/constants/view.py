# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


class ViewType(object):
    """
    视图类型（用于主机详情页视图、采集配置视图、自定义上报视图等面板）
    """

    Overview = "overview"  # 总览视图
    TopoNode = "topo_node"  # 拓扑视图
    LeafNode = "leaf_node"  # 叶子节点，即主机或实例视图
