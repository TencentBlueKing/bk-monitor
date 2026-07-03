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
export const HOST_PAGE_HEADER_NAV_BAR_LIST = [
  {
    label: '主机监控',
    value: 'host',
  },
  {
    label: '进程监控',
    value: 'process',
  },
] as const;

export type HostPageScene = (typeof HOST_PAGE_HEADER_NAV_BAR_LIST)[number]['value'];

/**
 * 内容区视角：
 * - topo：选中父级（业务/集群/模块）节点 → 主机列表 + 指标汇聚
 * - host：选中主机叶子节点 → 系统指标 + 进程
 */
export type HostPerspective = 'host' | 'topo';

/** 拓扑视角 Tab：主机列表、指标汇聚（label 为 i18n key，icon 为 icon-monitor 字体类名） */
export const HOST_TOPO_TAB_LIST = [
  {
    label: '主机列表',
    value: 'list',
    icon: 'icon-mc-list',
  },
  {
    label: '指标汇聚',
    value: 'metric',
    icon: 'icon-zhibiaojiansuo',
  },
] as const;

/** 主机视角 Tab：系统指标、进程 */
export const HOST_DETAIL_TAB_LIST = [
  {
    label: '系统指标',
    value: 'system',
    icon: 'icon-zhibiaojiansuo',
  },
  {
    label: '进程',
    value: 'process',
    icon: 'icon-mc-process',
  },
] as const;

/** 视角 → Tab 列表 注册表（新增视角/Tab 只需扩展此处 + 容器渲染分支） */
export const HOST_PERSPECTIVE_TAB_MAP = {
  topo: HOST_TOPO_TAB_LIST,
  host: HOST_DETAIL_TAB_LIST,
} as const;

/** 全部内容区 Tab 取值（两视角合集） */
export type HostContentTab =
  | (typeof HOST_DETAIL_TAB_LIST)[number]['value']
  | (typeof HOST_TOPO_TAB_LIST)[number]['value'];

/** 新版主机列表筛选字段名映射（camelCase → snake_case），与 table-store fieldData.id 保持一致 */
export const HOST_FILTER_FIELDS_ENUM = {
  hostDisplayName: 'host_display_name',
  bkHostId: 'bk_host_id',
  bkHostInnerIpV6: 'bk_host_innerip_v6',
  bkHostOuterIpV6: 'bk_host_outerip_v6',
  bkHostInnerIp: 'bk_host_innerip',
  bkHostOuterIp: 'bk_host_outerip',
  status: 'status',
  bkHostName: 'bk_host_name',
  bkOsName: 'bk_os_name',
  bkCloudName: 'bk_cloud_name',
  clusterModule: 'cluster_module',
  bkCluster: 'bk_cluster',
  bkInstName: 'bk_inst_name',
  alarmCount: 'alarm_count',
  cpuLoad: 'cpu_load',
  cpuUsage: 'cpu_usage',
  diskInUse: 'disk_in_use',
  ioUtil: 'io_util',
  memUsage: 'mem_usage',
  pscMemUsage: 'psc_mem_usage',
  kBizName: 'bk_biz_name',
  displayName: 'display_name',
} as const;
/** 筛选字段 snake_case 值类型，用于 where 条件类型约束 */
export type THostFilterField = (typeof HOST_FILTER_FIELDS_ENUM)[keyof typeof HOST_FILTER_FIELDS_ENUM];
