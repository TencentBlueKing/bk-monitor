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

import type { IHostTopoHostNode, IHostTopoInstNode, IHostTopoTree } from '../types';

/** mock 实例节点附带 bk-tree 初始展开标记（isOpen 由组件库消费，非业务字段） */
type IMockInstNode = IHostTopoInstNode & { isOpen?: boolean };

/** 主机 id 自增种子，保证 mock 主机节点唯一 */
let hostIdSeed = 10000;

/**
 * @description 生成一个 mock 主机叶子节点
 * @param ip 内网 IP
 * @param aliasName 主机别名（操作系统主机名）
 */
const createMockHost = (ip: string, aliasName: string): IHostTopoHostNode => {
  const hostId = ++hostIdSeed;
  return {
    alias_name: aliasName,
    bk_biz_id: 2,
    bk_cloud_id: 0,
    bk_host_id: hostId,
    bk_host_innerip: ip,
    bk_host_innerip_v6: '',
    bk_host_name: aliasName,
    display_name: ip,
    id: `host-${hostId}`,
    ip,
    name: ip,
    os_type: 'linux',
  };
};

/**
 * @description 批量生成 mock 主机（用于填充节点下的主机数量）
 * @param count 主机数量
 * @param ipPrefix IP 前缀
 * @param aliasPrefix 别名前缀
 */
const createMockHosts = (count: number, ipPrefix: string, aliasPrefix: string): IHostTopoHostNode[] =>
  Array.from({ length: count }, (_, index) =>
    createMockHost(`${ipPrefix}.${index + 1}`, `${aliasPrefix}-${index + 1}-tencentos`)
  );

/**
 * @description 生成 mock 实例节点（业务 / 集群 / 模块）
 */
const createMockInst = (
  partial: Pick<IHostTopoInstNode, 'bk_inst_id' | 'bk_obj_id' | 'bk_obj_name' | 'name'>,
  children: IHostTopoInstNode['children'],
  isOpen = false
): IMockInstNode => ({
  bk_biz_id: 2,
  bk_inst_id: partial.bk_inst_id,
  bk_inst_name: partial.name,
  bk_obj_id: partial.bk_obj_id,
  bk_obj_name: partial.bk_obj_name,
  children,
  id: `${partial.bk_obj_id}-${partial.bk_inst_id}`,
  isOpen,
  name: partial.name,
});

/**
 * @description 主机拓扑树 mock 数据，结构对齐 getHostTopoTreeByBizId 返回类型
 * 根节点 EDTEST 共 24 台主机：lde_Pool(4) + 蓝鲸平台(k8s-master 16 + k8s-node 4)
 */
export const getMockHostTopoTree = (): IHostTopoTree[] => {
  const ldePool = createMockInst(
    { bk_inst_id: 101, bk_obj_id: 'module', bk_obj_name: '模块', name: 'lde_Pool' },
    [
      createMockHost('11.147.2.124', 'VM-2-124-tencentos'),
      createMockHost('11.147.2.184', 'VM-2-184-tencentos'),
      createMockHost('11.147.3.241', 'VM-2-184-tencentos'),
      createMockHost('11.147.3.27', 'VM-2-27-tencentos'),
    ],
    true
  );

  const k8sMaster = createMockInst(
    { bk_inst_id: 201, bk_obj_id: 'module', bk_obj_name: '模块', name: 'k8s-master' },
    createMockHosts(16, '11.148.1', 'VM-master')
  );

  const k8sNode = createMockInst(
    { bk_inst_id: 202, bk_obj_id: 'module', bk_obj_name: '模块', name: 'k8s-node' },
    createMockHosts(4, '11.148.2', 'VM-node')
  );

  const blueKing = createMockInst(
    { bk_inst_id: 200, bk_obj_id: 'set', bk_obj_name: '集群', name: '蓝鲸平台' },
    [k8sMaster, k8sNode],
    true
  );

  const root = createMockInst(
    { bk_inst_id: 2, bk_obj_id: 'biz', bk_obj_name: '业务', name: 'EDTEST' },
    [ldePool, blueKing],
    true
  );

  return [root];
};
