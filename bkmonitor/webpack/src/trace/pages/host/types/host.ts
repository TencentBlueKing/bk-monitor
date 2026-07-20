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

/** 拓扑对象名称映射（如 biz / set / module 对应的中文名） */
export type IBkObjNameMap = Record<string, string>;

/** 主机告警统计 */
export type IHostAlarmCount = {
  count: number;
  level: number;
};

/** 主机列表项 */
export type IHostBaseInfo = {
  bk_biz_id: number;
  bk_cloud_id: number;
  bk_cloud_name: string;
  bk_host_id: number;
  bk_host_innerip: string;
  bk_host_name: string;
  bk_host_outerip: string;
  bk_os_name: string;
  bk_os_type: string;
  display_name: string;
  ignore_monitoring: boolean;
  is_shielding: boolean;
  module: IHostModule[];
  region: string;
};

/** 主机进程组件信息 */
export type IHostComponent = {
  display_name: string;
  ports: number[];
  protocol: string;
  status: number;
};

/** 带指标数据的主机列表项 */
export interface IHostMetricInfo extends IHostBaseInfo {
  id: string;
  alarm_count: IHostAlarmCount[];
  bk_host_innerip_v6: string;
  bk_host_outerip_v6: string;
  bk_state: string;
  component: IHostComponent[];
  cpu_load: number;
  cpu_usage: number;
  disk_in_use: number;
  io_util: number;
  mem_usage: number;
  psc_mem_usage: number;
  status: number;
}

/** 主机所属模块信息 */
export type IHostModule = {
  bk_inst_id: number;
  bk_inst_name: string;
  bk_obj_name_map: IBkObjNameMap;
  id: string;
  topo_link: string[];
  topo_link_display: string[];
};
