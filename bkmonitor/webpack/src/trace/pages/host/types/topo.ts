/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

/** 拓扑树主机叶子节点 */
export type IHostTopoHostNode = {
  alias_name: string;
  bk_biz_id: number;
  bk_cloud_id: number;
  bk_host_id: number;
  bk_host_innerip: string;
  bk_host_innerip_v6: string;
  bk_host_name: string;
  display_name: string;
  id: string;
  ip: string;
  name: string;
  os_type: string;
};

/** 拓扑树 CMDB 实例节点（业务 / 集群 / 模块等） */
export type IHostTopoInstNode = {
  bk_biz_id: number;
  bk_inst_id: number;
  bk_inst_name: string;
  bk_obj_id: string;
  bk_obj_name: string;
  children: IHostTopoTreeNode[];
  id: string;
  name: string;
};

/** 主机拓扑树根节点 */
export type IHostTopoTree = IHostTopoInstNode;

/** 拓扑树节点 */
export type IHostTopoTreeNode = IHostTopoHostNode | IHostTopoInstNode;
