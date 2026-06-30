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

import { isHostNode } from '../utils/topo-tree';
import { getMockHostTopoTree } from './host-topo';

import type { IBkObjNameMap, IHostBaseInfo, IHostComponent, IHostMetricInfo, IHostModule } from '../types/host';
import type { IHostTopoHostNode, IHostTopoTreeNode } from '../types/topo';

/**
 * 模块定义：topo_link / 展示名采用与拓扑树节点一致的 id 格式（`${bk_obj_id}-${bk_inst_id}`），
 * 从而保证「选中拓扑节点 → 过滤主机列表」可在纯前端按 topo_link 命中。
 */
interface IMockModuleDef {
  count: number;
  id: string;
  instId: number;
  name: string;
  objNameMap: IBkObjNameMap;
  topoLink: string[];
  topoLinkDisplay: string[];
}

const MOCK_MODULE_DEFS: IMockModuleDef[] = [
  {
    id: 'module-101',
    instId: 101,
    name: 'lde_Pool',
    topoLink: ['biz-2', 'module-101'],
    topoLinkDisplay: ['EDTEST', 'lde_Pool'],
    objNameMap: { biz: '业务', module: '模块' },
    count: 40,
  },
  {
    id: 'module-201',
    instId: 201,
    name: 'k8s-master',
    topoLink: ['biz-2', 'set-200', 'module-201'],
    topoLinkDisplay: ['EDTEST', '蓝鲸平台', 'k8s-master'],
    objNameMap: { biz: '业务', set: '集群', module: '模块' },
    count: 120,
  },
  {
    id: 'module-202',
    instId: 202,
    name: 'k8s-node',
    topoLink: ['biz-2', 'set-200', 'module-202'],
    topoLinkDisplay: ['EDTEST', '蓝鲸平台', 'k8s-node'],
    objNameMap: { biz: '业务', set: '集群', module: '模块' },
    count: 38,
  },
];

const OS_NAME_POOL = ['linux(centos)', 'TencentOS Server', 'Windows Server 2019'];
const CLOUD_NAME_POOL = ['默认管控区域', '管控区域-A'];
const PROCESS_POOL = ['mongodb', 'zookeeper', 'mysql', 'influxdb-proxy', 'redis', 'nginx'];
/** 采集状态候选（按权重铺开，正常占多数） */
const STATUS_POOL = [0, 0, 0, 0, 0, 2, 3, -1];

/** 确定性伪随机数（mulberry32），保证多次加载 mock 数据稳定，避免渲染抖动 */
const createRandom = (seed: number) => {
  let state = seed >>> 0;
  return () => {
    state |= 0;
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};

/** 遍历拓扑树，按「所属模块节点 id」归集主机叶子，便于复用其身份以支持主机级联动 */
const collectTreeHostsByModule = (): Map<string, IHostTopoHostNode[]> => {
  const map = new Map<string, IHostTopoHostNode[]>();
  const walk = (nodes: IHostTopoTreeNode[], moduleId: string) => {
    for (const node of nodes) {
      if (isHostNode(node)) {
        if (moduleId) {
          const list = map.get(moduleId) ?? [];
          list.push(node);
          map.set(moduleId, list);
        }
        continue;
      }
      const nextModuleId = node.bk_obj_id === 'module' ? node.id : moduleId;
      walk(node.children ?? [], nextModuleId);
    }
  };
  walk(getMockHostTopoTree(), '');
  return map;
};

/** 生成主机所属模块信息 */
const createModule = (def: IMockModuleDef): IHostModule => ({
  bk_inst_id: def.instId,
  bk_inst_name: def.name,
  bk_obj_name_map: def.objNameMap,
  id: def.id,
  topo_link: [...def.topoLink],
  topo_link_display: [...def.topoLinkDisplay],
});

/** 生成进程组件列表 */
const createComponents = (random: () => number): IHostComponent[] => {
  const count = Math.floor(random() * 3); // 0 ~ 2 个进程
  const result: IHostComponent[] = [];
  const used = new Set<string>();
  for (let i = 0; i < count; i++) {
    const name = PROCESS_POOL[Math.floor(random() * PROCESS_POOL.length)];
    if (used.has(name)) continue;
    used.add(name);
    result.push({
      display_name: name,
      ports: [8000 + Math.floor(random() * 1000)],
      protocol: 'TCP',
      status: random() > 0.7 ? 0 : 1,
    });
  }
  return result;
};

/** 生成未恢复告警统计（约 1/4 主机有告警） */
const createAlarmCount = (random: () => number): IHostMetricInfo['alarm_count'] => {
  if (random() > 0.25) {
    return [];
  }
  const level = [1, 2, 3][Math.floor(random() * 3)];
  return [{ level, count: 1 + Math.floor(random() * 8) }];
};

/** 生成单台主机的完整指标数据 */
const createMetricHost = (
  def: IMockModuleDef,
  index: number,
  hostId: number,
  ip: string,
  hostName: string
): IHostMetricInfo => {
  const random = createRandom(hostId * 31 + index);
  const status = STATUS_POOL[Math.floor(random() * STATUS_POOL.length)];
  // 无 Agent / 未知 状态主机无指标数据（与真实场景一致）
  const hasMetric = status === 0 || status === 3;
  const metric = (base: number) => (hasMetric ? Number((base + random() * (95 - base)).toFixed(2)) : 0);
  return {
    bk_biz_id: 2,
    bk_cloud_id: 0,
    bk_cloud_name: CLOUD_NAME_POOL[index % CLOUD_NAME_POOL.length],
    bk_host_id: hostId,
    bk_host_innerip: ip,
    bk_host_innerip_v6: '',
    bk_host_outerip: '',
    bk_host_outerip_v6: '',
    bk_host_name: hostName,
    bk_os_name: OS_NAME_POOL[index % OS_NAME_POOL.length],
    bk_os_type: '1',
    bk_state: '',
    display_name: ip,
    region: '',
    ignore_monitoring: false,
    is_shielding: false,
    module: [createModule(def)],
    alarm_count: createAlarmCount(random),
    component: createComponents(random),
    cpu_load: hasMetric ? Number((random() * 4).toFixed(2)) : 0,
    cpu_usage: metric(2),
    mem_usage: metric(2),
    disk_in_use: metric(2),
    io_util: metric(2),
    psc_mem_usage: metric(2),
    status,
  };
};

/** 自增主机 id 种子（避开拓扑树 mock 占用的 10000+ 区间） */
let fillerHostIdSeed = 90000;

/**
 * @description 生成带指标的主机列表 mock 数据（约 198 条，分布在 3 个模块下）。
 * 每个模块优先复用拓扑树的主机叶子身份（bk_host_id / ip），保证「选中主机节点」也能命中列表行。
 */
export const getMockHostMetricList = (): IHostMetricInfo[] => {
  fillerHostIdSeed = 90000;
  const treeHostsByModule = collectTreeHostsByModule();
  const list: IHostMetricInfo[] = [];
  for (const def of MOCK_MODULE_DEFS) {
    const seedHosts = treeHostsByModule.get(def.id) ?? [];
    for (let i = 0; i < def.count; i++) {
      const seed = seedHosts[i];
      const hostId = seed ? seed.bk_host_id : ++fillerHostIdSeed;
      const ip = seed ? seed.ip : `${def.topoLink.length > 2 ? '11.148' : '11.147'}.${def.instId % 100}.${i + 1}`;
      const hostName = seed ? seed.bk_host_name : `VM-${def.name}-${i + 1}-tencentos`;
      list.push(createMetricHost(def, i, hostId, ip, hostName));
    }
  }
  return list;
};

/** 指标专属字段（基础接口不返回，用于从全量数据裁剪出「第一屏」基础数据） */
const METRIC_ONLY_KEYS = [
  'alarm_count',
  'bk_host_innerip_v6',
  'bk_host_outerip_v6',
  'bk_state',
  'component',
  'cpu_load',
  'cpu_usage',
  'disk_in_use',
  'io_util',
  'mem_usage',
  'psc_mem_usage',
  'status',
] as const;

/**
 * @description 生成基础主机列表 mock 数据（不含指标，用于第一屏快速渲染）。
 * 由全量指标数据裁剪而来，保证与指标数据行一一对应。
 */
export const getMockHostBaseList = (): IHostBaseInfo[] =>
  getMockHostMetricList().map(host => {
    const base = { ...host } as Partial<IHostMetricInfo>;
    for (const key of METRIC_ONLY_KEYS) {
      delete base[key];
    }
    return base as IHostBaseInfo;
  });
