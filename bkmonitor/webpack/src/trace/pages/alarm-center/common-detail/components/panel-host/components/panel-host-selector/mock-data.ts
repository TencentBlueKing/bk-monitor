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

/** 模块级别mock数据 */
const moduleLevelList = new Array(Math.floor(Math.random() * 100)).fill(0).map((_, i) => ({
  bk_inst_id: i,
  bk_inst_name: `k8s-node-${i}`,
  bk_obj_id: 'module',
  bk_obj_name: '模块',
  id: `module|${i}`,
  bk_biz_id: 2,
  name: `k8s-node-${i}`,
}));

/** 主机级别mock数据 */
const hostLevelList = new Array(Math.floor(Math.random() * 100)).fill(0).map((_, i) => ({
  bk_host_id: i,
  display_name: `10.0.7.${i}`,
  ip: `10.0.7.${i}`,
  bk_host_innerip: `10.0.7.${i}`,
  bk_host_innerip_v6: '',
  bk_cloud_id: 0,
  bk_host_name: `VM-7-4-centos-${i}`,
  os_type: 'linux',
  bk_biz_id: 2,
  id: i,
  name: `10.0.7.${i}`,
  alias_name: `VM-7-4-centos-${i}`,
}));

export function getMockData(level: string) {
  return level === 'module' ? moduleLevelList : hostLevelList;
}
